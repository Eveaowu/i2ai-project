"""Student-facing schedule generation.

    from scheduler import SchedulePlanner
    planner = SchedulePlanner.from_csv("dataset")
    result = planner.plan("S001", interest="machine learning")
    result.to_dict()   # JSON-ready for the frontend
"""
from .generator import DEFAULT_STRATEGIES, ScheduleGenerator, Strategy
from .models import (Course, GraduationProjection, Preferences, Program, RequirementStatus,
                     Schedule, ScheduledCourse, Section, Student, TimeSlot, ValidationResult)
from .planner import PlanResult, SchedulePlanner
from .repository import DataRepository
from .rules import GraduationProjector, PrerequisiteChecker, RequirementTracker, ScheduleValidator
