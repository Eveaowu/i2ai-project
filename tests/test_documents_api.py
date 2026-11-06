import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from recommender.catalog import DEFAULT_DATA
from recommender.documents import MAX_BYTES, extract_document, extract_text


def test_sample_documents_are_extractable():
    manifest = json.loads((DEFAULT_DATA / "samples/manifest.json").read_text())
    for sample in manifest["scenarios"]:
        for kind in ("resume", "transcript"):
            path = DEFAULT_DATA / sample[kind]
            parsed = extract_document(path.read_bytes(), path.name, kind)
            if kind == "resume":
                assert parsed["experience"]["skills"]
                assert parsed["experience"]["work_experience"]
                assert parsed["experience"]["projects"]
            else:
                assert len(parsed["experience"]["academic_records"]) == 3


def test_transcript_grades_override_conflicting_status():
    text = b"Institution: Example\n95-888 | Data Focused Python | F | 6 | S25 | completed\n95-796 | Statistics | IP | 6 | S25 | completed"
    rows = extract_document(text, "transcript.txt", "transcript")["experience"]["academic_records"]
    assert [row["status"] for row in rows] == ["failed", "in_progress"]


def test_json_and_docx_extraction():
    result = extract_document(b'{"skills":["Python"],"projects":[{"description":"Built a data tool"}]}', "resume.json", "resume")
    assert result["experience"]["projects"][0]["source"] == "resume.json"
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Skills</w:t></w:r></w:p><w:p><w:r><w:t>Python, SQL</w:t></w:r></w:p></w:body></w:document>')
    result = extract_document(output.getvalue(), "resume.docx", "resume")
    assert result["experience"]["skills"] == ["python", "sql"]


def test_blank_pdf_requests_ocr():
    writer, output = PdfWriter(), io.BytesIO()
    writer.add_blank_page(width=612, height=792)
    writer.write(output)
    with pytest.raises(ValueError, match="OCR"):
        extract_text(output.getvalue(), "scan.pdf")


def test_text_pdf_extraction():
    writer, output = PdfWriter(), io.BytesIO()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 50 700 Td (Skills) Tj 0 -20 Td (Python, SQL) Tj ET")
    page[NameObject("/Contents")] = content
    writer.write(output)
    result = extract_document(output.getvalue(), "resume.pdf", "resume")
    assert result["experience"]["skills"] == ["python", "sql"]


def test_docx_transcript_table():
    output = io.BytesIO()
    cells = "".join(f"<w:tc><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:tc>" for text in
                    ["CS101", "Python Programming", "A", "3", "Spring 2024", "completed"])
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr("word/document.xml", f'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:tbl><w:tr>{cells}</w:tr></w:tbl></w:body></w:document>')
    rows = extract_document(output.getvalue(), "transcript.docx", "transcript")["experience"]["academic_records"]
    assert len(rows) == 1 and rows[0]["title"] == "Python Programming"


@pytest.mark.parametrize("data,filename", [(b"bad", "resume.exe"), (b"", "resume.txt"), (b"x" * (MAX_BYTES + 1), "resume.txt"), (b"bad", "resume.docx"), (b"bad", "resume.pdf")])
def test_invalid_documents_rejected(data, filename):
    with pytest.raises(ValueError):
        extract_document(data, filename, "resume")


def test_unparsed_transcript_has_review_warning():
    result = extract_document(b"Some university transcript in an unknown layout", "transcript.txt", "transcript")
    assert result["experience"]["academic_records"] == []
    assert any("No course rows parsed" in warning for warning in result["warnings"])


def test_api_end_to_end(service, tmp_path, monkeypatch):
    from recommender.api import app
    model_path = tmp_path / "api.joblib"
    service.model.save(model_path)
    monkeypatch.setenv("RECOMMENDER_MODEL", str(model_path))
    with TestClient(app) as client:
        assert client.get("/health").json()["status"] == "ok"
        assert len(client.get("/interests").json()["career"]) == 12
        path = DEFAULT_DATA / "samples/documents/ai_engineer_resume.txt"
        response = client.post("/extract", data={"kind": "resume"}, files={"file": (path.name, path.read_bytes(), "text/plain")})
        assert response.status_code == 200
        response = client.post("/recommendations", json={"profile": {"student_id": "S001", "experience": response.json()["experience"]}, "term": "S27", "top_k": 5})
        assert response.status_code == 200
        assert len(response.json()["recommendations"]) == 5
        assert response.json()["interest_source"] == "population_course_history_proxy"
        assert client.post("/recommendations", json={"profile": {"student_id": "unknown"}}).status_code == 422
        assert client.post("/recommendations", json={"profile": {"program_id": "AIM12"}, "top_k": 0}).status_code == 422
        assert client.post("/extract", data={"kind": "resume"}, files={"file": ("bad.pdf", b"bad", "application/pdf")}).status_code == 422

