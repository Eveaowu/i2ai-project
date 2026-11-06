"""Local, deterministic extraction. Documents provide evidence, never instructions."""
import io
import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

from pypdf.errors import PdfReadError

from .schemas import AcademicRecord, Experience, ExperienceEntry

MAX_BYTES = 5 * 1024 * 1024
MAX_TEXT = 200_000
SKILLS = {
    "python": r"\bpython\b", "sql": r"\bsql\b", "r": r"\bR\b",
    "machine learning": r"\bmachine learning\b|\bML\b",
    "deep learning": r"\bdeep learning\b|\bpytorch\b|\btensorflow\b",
    "natural language processing": r"\bnatural language processing\b|\bNLP\b",
    "generative AI": r"\bgenerative ai\b|\bLLMs?\b|large language models?",
    "data analysis": r"\bdata analy(?:sis|tics)\b|\bpandas\b",
    "data engineering": r"\bdata engineering\b|\bETL\b|data pipelines?",
    "web development": r"\bweb development\b|\bFastAPI\b|\bDjango\b|\bReact\b",
    "cloud computing": r"\bcloud\b|\bAWS\b|\bAzure\b",
    "cybersecurity": r"\bcybersecurity\b|\bnetwork security\b|\bsecurity operations\b",
    "privacy": r"\bprivacy\b", "AI governance": r"\bAI governance\b|\bresponsible AI\b",
    "project management": r"\bproject management\b|\bagile\b|\bscrum\b",
    "product management": r"\bproduct manag(?:ement|er)\b",
    "experimentation": r"\bA/B test(?:ing)?\b|\bexperimentation\b",
    "data visualization": r"\bTableau\b|\bPower BI\b|\bdata visualization\b",
    "statistics": r"\bstatistics\b|\bstatistical\b|\beconometrics\b",
    "forecasting": r"\bforecasting\b|\btime series\b",
}
HEADINGS = {
    "work experience": "work", "professional experience": "work", "experience": "work",
    "employment": "work", "projects": "projects", "project experience": "projects",
    "skills": "skills", "technical skills": "skills", "education": "education",
    "summary": "summary", "profile": "summary",
}


def extract_text(data: bytes, filename: str) -> str:
    if not data or len(data) > MAX_BYTES:
        raise ValueError("Document must contain between 1 byte and 5 MiB")
    extension = Path(filename).suffix.lower()
    try:
        if extension in {".txt", ".md", ".json"}:
            text = data.decode("utf-8-sig")
        elif extension == ".docx":
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                info = archive.getinfo("word/document.xml")
                if sum(item.file_size for item in archive.infolist()) > 20 * MAX_BYTES:
                    raise ValueError("Expanded DOCX exceeds the supported size")
                xml = ElementTree.fromstring(archive.read(info))
                ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
                paragraphs = []
                # Preserve table columns as delimiters for transcript parsing.
                for block in xml.findall("w:body/*", ns):
                    if block.tag.endswith("}tbl"):
                        for row in block.findall("w:tr", ns):
                            paragraphs.append(" | ".join("".join(cell.itertext()) for cell in row.findall("w:tc", ns)))
                    else:
                        paragraphs.append("".join(t.text or "" for t in block.findall(".//w:t", ns)))
                text = "\n".join(paragraphs)
        elif extension == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or len(reader.pages) > 30:
                raise ValueError("Use an unencrypted PDF of at most 30 pages")
            pages = []
            for page in reader.pages:
                content = page.get_contents()
                if content and len(content.get_data()) > 10 * MAX_BYTES:
                    raise ValueError("PDF page content exceeds the supported size")
                pages.append(page.extract_text(extraction_mode="layout") or "")
            text = "\n".join(pages)
        else:
            raise ValueError("Supported formats: UTF-8 TXT, MD, JSON, DOCX, and text-based PDF")
    except (UnicodeError, zipfile.BadZipFile, KeyError, ElementTree.ParseError, PdfReadError, EOFError) as exc:
        raise ValueError("Document is not valid for its declared file type") from exc
    if not text.strip():
        raise ValueError("No extractable text; scanned documents require OCR before upload")
    if len(text) > MAX_TEXT:
        raise ValueError("Extracted text exceeds 200,000 characters")
    return text


def _entries(text, source):
    result = []
    for paragraph in re.split(r"\n\s*\n", text.strip()):
        lines = paragraph.strip().splitlines()
        if not lines:
            continue
        header = [part.strip() for part in lines[0].split("|")]
        result.append(ExperienceEntry(title=header[0][:300], organization=header[1][:300] if len(header) > 1 else "",
                                      description="\n".join(lines)[:12000], source=source))
    return result


def _transcript(text, source):
    institution = re.search(r"^\s*Institution\s*:\s*(.+)$", text, re.M | re.I)
    records = []
    for line in text.splitlines():
        parts = [part.strip() for part in re.split(r"\s*\|\s*|\t+|\s{2,}", line.strip())]
        if len(parts) < 4 or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.\-]{1,79}", parts[0]):
            continue
        if parts[0].lower() in {"course", "course_id", "id", "course-id"} or not parts[1]:
            continue
        grade = parts[2].upper()
        if not re.fullmatch(r"[A-F][+-]?|P|PASS|S|NP|W|I|IP|IN PROGRESS|N/A", grade):
            continue
        credits = float(parts[3]) if re.fullmatch(r"\d+(?:\.\d+)?", parts[3]) else None
        status = (parts[5].lower().replace(" ", "_") if len(parts) > 5 else "unknown")
        # A failing, withdrawn, or incomplete grade overrides a conflicting label.
        if grade in {"F", "NP", "W"}:
            status = "failed"
        elif grade in {"I", "IP", "IN PROGRESS"}:
            status = "in_progress"
        elif status not in {"completed", "in_progress", "failed", "unknown"}:
            status = "unknown"
        if status == "unknown" and grade not in {"N/A", "I", "IP"}:
            status = "completed"
        records.append(AcademicRecord(course_id=parts[0], title=parts[1], grade=grade, credits=credits,
                                      term=parts[4] if len(parts) > 4 and parts[4] else None,
                                      institution=institution.group(1).strip() if institution else "",
                                      status=status, source=source))
    return records


def extract_document(data: bytes, filename: str, kind: str) -> dict:
    if kind not in {"resume", "transcript"}:
        raise ValueError("Document kind must be resume or transcript")
    source = Path(filename.replace("\\", "/")).name[:300]
    text = extract_text(data, source)
    warnings = []
    if Path(source).suffix.lower() == ".json":
        try:
            payload = json.loads(text)
            experience = Experience.model_validate(payload)
        except (ValueError, TypeError) as exc:
            raise ValueError("JSON documents must follow the documented Experience schema") from exc
        for item in experience.work_experience + experience.projects + experience.academic_records:
            item.source = source
    elif kind == "transcript":
        records = _transcript(text, source)
        experience = Experience(academic_records=records)
        if not records:
            warnings.append("No course rows parsed. Review the text and supply structured academic_records using the documented schema.")
    else:
        sections = {key: [] for key in set(HEADINGS.values())}
        current = "summary"
        for line in text.splitlines():
            heading = line.strip().strip("#:").lower()
            if heading in HEADINGS:
                current = HEADINGS[heading]
            else:
                sections[current].append(line)
        relevant = "\n".join(sections["skills"] + sections["work"] + sections["projects"])
        skills = [name for name, pattern in SKILLS.items() if re.search(pattern, relevant, 0 if name == "r" else re.I)]
        experience = Experience(skills=skills, work_experience=_entries("\n".join(sections["work"]), source),
                                projects=_entries("\n".join(sections["projects"]), source))
        if not experience.work_experience and not experience.projects:
            warnings.append("No work/project sections found. Use headings such as Work Experience and Projects, or submit structured experience.")
    warnings.append("Extracted information is unverified; review it before submitting the profile. Uploads do not grant prerequisite credit.")
    return {"schema_version": "1.0", "document_kind": kind, "source": source,
            "experience": experience.model_dump(), "warnings": warnings, "extracted_text": text}


def merge_experience(*items: Experience) -> Experience:
    merged = Experience()
    for item in items:
        merged.skills.extend(item.skills)
        merged.work_experience.extend(item.work_experience)
        merged.projects.extend(item.projects)
        merged.academic_records.extend(item.academic_records)
    merged.skills = sorted(set(merged.skills))
    # Validate combined limits as well as the limits on each individual upload.
    return Experience.model_validate(merged.model_dump())

