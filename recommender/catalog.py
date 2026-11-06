"""Read recommendation inputs without depending on the scheduler's unit defaults."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA = ROOT / "dataset"
SOURCE_FILES = ("courses.csv", "student_data.csv", "program_requirements.csv", "course_terms.csv", "course_section.csv")


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def source_hashes(data_dir):
    return {name: hashlib.sha256((Path(data_dir) / name).read_bytes()).hexdigest() for name in SOURCE_FILES}


class Catalog:
    def __init__(self, data_dir=DEFAULT_DATA):
        self.data_dir = Path(data_dir)
        self.courses = {row["course_id"]: row for row in read_csv(self.data_dir / "courses.csv")}
        self.students = {row["student_id"]: row for row in read_csv(self.data_dir / "student_data.csv")}
        self.core = {}
        for row in read_csv(self.data_dir / "program_requirements.csv"):
            self.core.setdefault(row["program_id"], set())
            if row["core"] == "1":
                self.core[row["program_id"]].add(row["req_course_id"])
        self.sections = read_csv(self.data_dir / "course_section.csv")
        self.terms = read_csv(self.data_dir / "course_terms.csv")
        self.known_terms = sorted({row["term_code"] for row in self.terms})

    def completed(self, student_id):
        if not student_id:
            return set()
        return {r["course_id"] for r in json.loads(self.students[student_id]["completed_courses"])
                if str(r.get("grade", "")).upper() not in {"F", "W", "I", "NP", "N", ""}}

    def offered(self, term):
        courses = {r["course_id"] for r in self.terms if r["term_code"] == term and r["status"] == "Offered"}
        sections = {r["course_id"] for r in self.sections if r["term"] == term and r["section_status"] == "Offered"}
        return courses & sections

    def regular(self, course_id):
        return self.courses[course_id]["course_type"] == "Regular course"

