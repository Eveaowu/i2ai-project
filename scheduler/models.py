"""Plain data objects. Every object has to_dict() so the frontend gets clean JSON."""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Optional

DAY_LETTERS = "MTWRFSU"


# --------------------------------------------------------------------------- time
@dataclass(frozen=True)
class TimeSlot:
    day: str        # one of M T W R F S U
    start: int      # minutes from midnight
    end: int

    def overlaps(self, other: "TimeSlot") -> bool:
        return self.day == other.day and self.start < other.end and other.start < self.end

    @staticmethod
    def _to_min(t: str) -> int:  # "02:00PM" -> 840
        h, m = int(t[:-5].split(":")[0]), int(t[-4:-2])
        return (h % 12 + (12 if t.endswith("PM") else 0)) * 60 + m

    @classmethod
    def parse(cls, days_times: str) -> list["TimeSlot"]:
        """'MW 02:00PM-03:20PM; F 09:30AM-10:50AM' -> [TimeSlot, ...]; 'TBA' -> []"""
        if not isinstance(days_times, str) or days_times.strip().upper() == "TBA":
            return []
        slots = []
        for chunk in days_times.split(";"):
            m = re.match(r"\s*([A-Z]+)\s+(\d{1,2}:\d{2}[AP]M)-(\d{1,2}:\d{2}[AP]M)", chunk)
            if m:
                days, a, b = m.groups()
                slots += [cls(d, cls._to_min(a), cls._to_min(b)) for d in days if d in DAY_LETTERS]
        return slots


# --------------------------------------------------------------------------- student
@dataclass
class Preferences:
    time_of_day: Optional[str] = None   # morning / afternoon / evening
    modality: Optional[str] = None      # in_person / online / hybrid

    def to_dict(self):
        return asdict(self)


@dataclass
class Student:
    id: str
    name: str
    program_id: str
    completed: set[str]
    credits_completed: int
    credits_in_progress: int
    preferences: Preferences

    def to_dict(self):
        return {"id": self.id, "name": self.name, "program_id": self.program_id,
                "completed": sorted(self.completed),
                "credits_completed": self.credits_completed,
                "credits_in_progress": self.credits_in_progress,
                "preferences": self.preferences.to_dict()}


# --------------------------------------------------------------------------- catalog
@dataclass
class Course:
    id: str
    title: str
    course_type: str
    description: str
    units: int
    prerequisites: str          # raw boolean string, "" if none
    typical_terms: str

    @property
    def is_regular(self) -> bool:
        return self.course_type == "Regular course"

    def to_dict(self):
        return {"id": self.id, "title": self.title, "units": self.units,
                "prerequisites": self.prerequisites, "typical_terms": self.typical_terms}


MODALITY_GROUPS = {  # section.modality -> student preference value
    "In-person Expectation": "in_person",
    "In-person Expectation Rotation": "in_person",
    "Remote only": "online",
    "In-person + remote": "hybrid",
    "In-Person + Technology": "hybrid",
}


@dataclass
class Section:
    id: str
    course_id: str
    term: str
    code: str
    days_times: str
    modality: str
    instructor: str
    status: str
    slots: list[TimeSlot] = field(default_factory=list)

    @property
    def mini_half(self) -> Optional[str]:
        """'1'..'4' if it runs only half the semester, None if full semester."""
        return self.code[-1] if self.code and self.code[-1] in "1234" else None

    @property
    def is_tba(self) -> bool:
        return not self.slots

    @property
    def modality_group(self) -> Optional[str]:
        return MODALITY_GROUPS.get(self.modality)

    @property
    def time_of_day(self) -> Optional[str]:
        if not self.slots:
            return None
        start = min(s.start for s in self.slots)
        return "morning" if start < 720 else "afternoon" if start < 1020 else "evening"

    def conflicts_with(self, other: "Section") -> bool:
        a, b = self.mini_half, other.mini_half
        if a and b and a != b:          # different halves never overlap
            return False
        return any(x.overlaps(y) for x in self.slots for y in other.slots)

    def to_dict(self):
        return {"id": self.id, "course_id": self.course_id, "term": self.term,
                "days_times": self.days_times, "modality": self.modality,
                "modality_group": self.modality_group, "time_of_day": self.time_of_day,
                "mini_half": self.mini_half, "instructor": self.instructor,
                "slots": [asdict(s) for s in self.slots]}


@dataclass
class Program:
    id: str
    name: str
    track: str
    core_courses: set[str]
    waivable: set[str]
    elective_credits: int
    active_terms: dict[str, bool]   # {"F26": True, "S27": True, "M27": True, "F27": False}


# --------------------------------------------------------------------------- results
@dataclass
class ScheduledCourse:
    course: Course
    section: Section
    is_core: bool
    interest_score: float

    def to_dict(self):
        return {"course": self.course.to_dict(), "section": self.section.to_dict(),
                "is_core": self.is_core, "interest_score": round(self.interest_score, 3)}


@dataclass
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


@dataclass
class Schedule:
    term: str
    items: list[ScheduledCourse]
    score: float = 0.0
    label: str = ""
    validation: Optional[ValidationResult] = None
    graduation: Optional["GraduationProjection"] = None

    @property
    def units(self) -> int:
        return sum(i.course.units for i in self.items)

    @property
    def course_ids(self) -> frozenset[str]:
        return frozenset(i.course.id for i in self.items)

    @property
    def sections(self) -> list[Section]:
        return [i.section for i in self.items]

    def to_dict(self):
        return {"term": self.term, "label": self.label, "score": round(self.score, 3),
                "units": self.units, "courses": [i.to_dict() for i in self.items],
                "validation": self.validation.to_dict() if self.validation else None,
                "graduation": self.graduation.to_dict() if self.graduation else None}


@dataclass
class RequirementStatus:
    remaining_core: list[str]
    elective_credits_needed: int
    elective_credits_done: int

    @property
    def elective_credits_left(self) -> int:
        return max(0, self.elective_credits_needed - self.elective_credits_done)

    def to_dict(self):
        return {"remaining_core": self.remaining_core,
                "elective_credits_needed": self.elective_credits_needed,
                "elective_credits_done": self.elective_credits_done,
                "elective_credits_left": self.elective_credits_left}


@dataclass
class GraduationProjection:
    term: str
    units_remaining: int
    terms_needed: list[str]

    def to_dict(self):
        return asdict(self)
