"""Versioned input contracts shared by the CLI and HTTP API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InterestChoice(StrictModel):
    id: str = Field(min_length=1, max_length=80)
    weight: float = Field(default=1.0, gt=0, le=1, allow_inf_nan=False)


class Interests(StrictModel):
    career: list[InterestChoice] = Field(default_factory=list, max_length=20)
    academic: list[InterestChoice] = Field(default_factory=list, max_length=30)

    @model_validator(mode="after")
    def unique_choices(self):
        for kind in (self.career, self.academic):
            ids = [item.id for item in kind]
            if len(ids) != len(set(ids)):
                raise ValueError("Interest IDs must be unique within each category")
        return self


class ExperienceEntry(StrictModel):
    title: str = Field(default="", max_length=300)
    organization: str = Field(default="", max_length=300)
    description: str = Field(min_length=1, max_length=12000)
    source: str = Field(default="user_input", max_length=300)


class AcademicRecord(StrictModel):
    course_id: str | None = Field(default=None, max_length=80)
    title: str = Field(min_length=1, max_length=500)
    institution: str = Field(default="", max_length=300)
    grade: str | None = Field(default=None, max_length=30)
    credits: float | None = Field(default=None, ge=0, le=1000, allow_inf_nan=False)
    term: str | None = Field(default=None, max_length=80)
    status: Literal["completed", "in_progress", "failed", "unknown"] = "unknown"
    source: str = Field(default="user_input", max_length=300)


class Experience(StrictModel):
    skills: list[str] = Field(default_factory=list, max_length=100)
    work_experience: list[ExperienceEntry] = Field(default_factory=list, max_length=100)
    projects: list[ExperienceEntry] = Field(default_factory=list, max_length=100)
    academic_records: list[AcademicRecord] = Field(default_factory=list, max_length=300)


class StudentProfile(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    student_id: str | None = Field(default=None, max_length=80)
    program_id: Literal["AIM12", "AIM16"] | None = None
    interests: Interests = Field(default_factory=Interests)
    experience: Experience = Field(default_factory=Experience)


class RecommendationRequest(StrictModel):
    profile: StudentProfile
    term: str | None = Field(default=None, max_length=10)
    top_k: int = Field(default=10, ge=1, le=50)

