"""SchedulePlanner: the single entry point your frontend / API calls."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .generator import DEFAULT_STRATEGIES, ScheduleGenerator, Strategy
from .interest import InterestMatcher
from .models import RequirementStatus, Schedule, Student
from .repository import DataRepository
from .rules import GraduationProjector, PrerequisiteChecker, RequirementTracker, ScheduleValidator


@dataclass
class PlanResult:
    student: Student
    term: str
    interest: str
    requirements: RequirementStatus
    schedules: list[Schedule]

    def to_dict(self):
        return {"student": self.student.to_dict(), "term": self.term, "interest": self.interest,
                "requirements": self.requirements.to_dict(),
                "schedules": [s.to_dict() for s in self.schedules]}


class SchedulePlanner:
    def __init__(self, repo: DataRepository, units_per_term: int = 48):
        self.repo = repo
        prereqs = PrerequisiteChecker()
        self.tracker = RequirementTracker(repo)
        self.validator = ScheduleValidator(repo, prereqs)
        self.projector = GraduationProjector(repo, units_per_term)
        self.generator = ScheduleGenerator(repo, InterestMatcher(repo.courses), self.tracker, prereqs)

    @classmethod
    def from_csv(cls, data_dir: str | Path = Path(__file__).resolve().parent.parent / "dataset"):
        return cls(DataRepository(data_dir))

    def plan(self, student_id: str, interest: str = "", term: str = "S27",
             strategies: list[Strategy] = DEFAULT_STRATEGIES) -> PlanResult:
        student = self.repo.get_student(student_id)
        status = self.tracker.status(student)
        schedules = self.generator.generate(student, term, interest, strategies)
        for s in schedules:
            s.validation = self.validator.validate(student, s)
            s.graduation = self.projector.project(student, status, term, planned_units=s.units)
        return PlanResult(student, term, interest, status, schedules)
