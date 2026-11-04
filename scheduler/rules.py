"""Business rules: prerequisites, requirements, validation, graduation."""
from __future__ import annotations

import re

from .models import (GraduationProjection, Program, RequirementStatus, Schedule,
                     Student, ValidationResult)

COURSE_ID = re.compile(r"\d{2}-\d{3}")
TERM_ORDER = ["S26", "M26", "F26", "S27", "M27", "F27", "S28", "M28", "F28"]


class PrerequisiteChecker:
    """Evaluates strings like '(90-711 or 95-796) and (94-834)'."""

    @staticmethod
    def is_met(prereq: str, completed: set[str]) -> bool:
        if not prereq or not prereq.strip():
            return True
        expr = COURSE_ID.sub(lambda m: str(m.group() in completed), prereq)
        words = set(re.findall(r"[A-Za-z]+", expr))
        if words - {"True", "False", "and", "or"} or not re.fullmatch(r"[\sA-Za-z()]*", expr):
            return False  # unparseable -> not met, let an advisor decide
        return bool(eval(expr))  # safe: only True/False/and/or/() remain

    @staticmethod
    def courses_mentioned(prereq: str) -> list[str]:
        return COURSE_ID.findall(prereq or "")


class RequirementTracker:
    def __init__(self, repo):
        self.repo = repo

    def status(self, student: Student) -> RequirementStatus:
        program = self.repo.get_program(student.program_id)
        non_core_done = student.completed - program.core_courses
        elective_done = sum(c.units for cid in non_core_done if (c := self.repo.get_course(cid)))
        return RequirementStatus(
            remaining_core=sorted(program.core_courses - student.completed),
            elective_credits_needed=program.elective_credits,
            elective_credits_done=elective_done)


class ScheduleValidator:
    def __init__(self, repo, prereqs: PrerequisiteChecker | None = None):
        self.repo = repo
        self.prereqs = prereqs or PrerequisiteChecker()

    def validate(self, student: Student, schedule: Schedule) -> ValidationResult:
        errors, warnings = [], []
        for item in schedule.items:
            c = item.course
            if c.id in student.completed:
                errors.append(f"{c.id} already completed")
            if not self.prereqs.is_met(c.prerequisites, student.completed):
                errors.append(f"{c.id} prerequisites not met: {c.prerequisites}")
        secs = schedule.sections
        for i, a in enumerate(secs):
            for b in secs[i + 1:]:
                if a.course_id == b.course_id:
                    errors.append(f"{a.course_id} scheduled twice")
                elif a.conflicts_with(b):
                    errors.append(f"time conflict: {a.id} vs {b.id}")
        tba = [s.id for s in secs if s.is_tba]
        if tba:
            warnings.append(f"time TBA, conflicts not checked: {', '.join(tba)}")
        return ValidationResult(valid=not errors, errors=errors, warnings=warnings)


class GraduationProjector:
    def __init__(self, repo, units_per_term: int = 48):
        self.repo = repo
        self.units_per_term = units_per_term

    def project(self, student: Student, status: RequirementStatus,
                next_term: str = "S27", planned_units: int = 0) -> GraduationProjection:
        """Next term removes `planned_units`, each later active term removes units_per_term."""
        program: Program = self.repo.get_program(student.program_id)
        core_units = sum(c.units for cid in status.remaining_core if (c := self.repo.get_course(cid)))
        left = core_units + status.elective_credits_left
        total = left
        terms = [t for t in TERM_ORDER[TERM_ORDER.index(next_term):]
                 if program.active_terms.get(t, True)]   # terms after the plan grid assumed active
        used = []
        for i, t in enumerate(terms):
            used.append(t)
            left -= planned_units if i == 0 else self.units_per_term
            if left <= 0:
                return GraduationProjection(term=t, units_remaining=total, terms_needed=used)
        return GraduationProjection(term=f"after {terms[-1]}", units_remaining=total, terms_needed=used)
