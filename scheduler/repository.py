"""DataRepository: the ONLY place that reads CSVs. Swap this for a database later
and nothing else has to change."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from .models import Course, Preferences, Program, Section, Student, TimeSlot


class DataRepository:
    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        self.courses: dict[str, Course] = self._load_courses(data_dir / "courses.csv")
        self.sections: list[Section] = self._load_sections(data_dir / "course_section.csv")
        self.programs: dict[str, Program] = self._load_programs(data_dir / "program_requirements.csv")
        self.students: dict[str, Student] = self._load_students(data_dir / "student_data.csv")

    # ------------------------------------------------------------------ queries
    def get_student(self, student_id: str) -> Student:
        if student_id not in self.students:
            raise KeyError(f"Unknown student {student_id}")
        return self.students[student_id]

    def get_program(self, program_id: str) -> Program:
        return self.programs[program_id]

    def get_course(self, course_id: str) -> Course | None:
        return self.courses.get(course_id)

    def sections_for(self, term: str, course_id: str | None = None, offered_only=True) -> list[Section]:
        return [s for s in self.sections
                if s.term == term
                and (course_id is None or s.course_id == course_id)
                and (not offered_only or s.status == "Offered")]

    # ------------------------------------------------------------------ loaders
    @staticmethod
    def _str(v) -> str:
        return "" if pd.isna(v) else str(v)

    def _load_courses(self, path) -> dict[str, Course]:
        df = pd.read_csv(path)
        out = {}
        for r in df.itertuples():
            units = r.units_typical
            out[r.course_id] = Course(
                id=r.course_id, title=self._str(r.title), course_type=self._str(r.course_type),
                description=self._str(r.description),
                units=12 if pd.isna(units) or units == 0 else int(units),
                prerequisites=self._str(r.prerequisites),
                typical_terms=self._str(r.typical_terms_offered))
        return out

    def _load_sections(self, path) -> list[Section]:
        df = pd.read_csv(path)
        return [Section(id=r.section_id, course_id=r.course_id, term=r.term,
                        code=self._str(r.section_code), days_times=self._str(r.days_times),
                        modality=self._str(r.modality), instructor=self._str(r.instructor_name),
                        status=self._str(r.section_status),
                        slots=TimeSlot.parse(r.days_times))
                for r in df.itertuples()]

    def _load_programs(self, path) -> dict[str, Program]:
        df = pd.read_csv(path)
        term_cols = [c for c in ["F26", "S27", "M27", "F27"] if c in df.columns]
        out = {}
        for pid, g in df.groupby("program_id"):
            first = g.iloc[0]
            out[pid] = Program(
                id=pid, name=first.program_name, track=first.track,
                core_courses=set(g[g.core == 1].req_course_id),
                waivable=set(g[g.waivable == 1].req_course_id),
                elective_credits=int(first.elective_credits),
                active_terms={t: bool(first[t]) for t in term_cols})
        return out

    def _load_students(self, path) -> dict[str, Student]:
        df = pd.read_csv(path)
        out = {}
        for r in df.itertuples():
            prefs = json.loads(r.preferences) if isinstance(r.preferences, str) else {}
            out[r.student_id] = Student(
                id=r.student_id, name=r.name, program_id=r.declared_program_id,
                completed={c["course_id"] for c in json.loads(r.completed_courses)},
                credits_completed=int(r.credits_completed),
                credits_in_progress=int(r.credits_in_progress),
                preferences=Preferences(prefs.get("preferred_time_of_day"),
                                        prefs.get("preferred_modality")))
        return out
