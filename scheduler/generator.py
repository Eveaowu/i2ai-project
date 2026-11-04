"""ScheduleGenerator: builds candidate schedules for one term."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import product

from .models import Course, Preferences, Schedule, ScheduledCourse, Section, Student
from .rules import PrerequisiteChecker, RequirementTracker


@dataclass
class Strategy:
    """One 'flavor' of schedule. Different strategies -> different options for the student."""
    label: str
    interest_weight: float = 3.0
    preference_weight: float = 1.0
    target_units: int = 48


DEFAULT_STRATEGIES = [
    Strategy("Best match for your interests", interest_weight=5.0, preference_weight=0.5),
    Strategy("Best fit for your time & format", interest_weight=1.0, preference_weight=3.0),
    Strategy("Lighter load", interest_weight=3.0, preference_weight=1.0, target_units=36),
]


@dataclass
class Candidate:
    course: Course
    is_core: bool
    interest: float


class ScheduleGenerator:
    def __init__(self, repo, matcher, tracker: RequirementTracker,
                 prereqs: PrerequisiteChecker | None = None,
                 elective_pool_size: int = 12, sections_per_course: int = 3):
        self.repo = repo
        self.matcher = matcher
        self.tracker = tracker
        self.prereqs = prereqs or PrerequisiteChecker()
        self.elective_pool_size = elective_pool_size
        self.sections_per_course = sections_per_course

    # ------------------------------------------------------------------ public
    def generate(self, student: Student, term: str, interest: str = "",
                 strategies: list[Strategy] = DEFAULT_STRATEGIES) -> list[Schedule]:
        candidates = self.candidates(student, term, interest)
        results: list[Schedule] = []
        for strat in strategies:
            sched = self._build(student, term, candidates, strat, exclude=[r.course_ids for r in results])
            if sched:
                results.append(sched)
        return results

    def candidates(self, student: Student, term: str, interest: str) -> list[Candidate]:
        """Offered this term, regular course, not taken yet, prerequisites met."""
        status = self.tracker.status(student)
        scores = self.matcher.score(interest)
        offered = {s.course_id for s in self.repo.sections_for(term)}
        out = []
        for cid in offered:
            c = self.repo.get_course(cid)
            if (c and c.is_regular and cid not in student.completed
                    and self.prereqs.is_met(c.prerequisites, student.completed)):
                out.append(Candidate(c, cid in status.remaining_core, scores.get(cid, 0.0)))
        return out

    # ------------------------------------------------------------------ internals
    def _build(self, student, term, candidates, strat: Strategy, exclude) -> Schedule | None:
        core = [c for c in candidates if c.is_core]
        electives = sorted((c for c in candidates if not c.is_core),
                           key=lambda c: -c.interest)[: self.elective_pool_size]
        # Try different starting points in the elective list until we get a new course set.
        for skip in range(max(1, len(electives))):
            chosen = self._pick_courses(core, electives[skip:], strat.target_units)
            sched = self._best_sections(student.preferences, term, chosen, strat)
            if sched and sched.course_ids not in exclude:
                sched.label = strat.label
                return sched
        return None

    @staticmethod
    def _pick_courses(core, electives, target) -> list[Candidate]:
        chosen, units = [], 0
        for c in core + electives:            # core first, then electives by interest
            if units + c.course.units <= target:
                chosen.append(c)
                units += c.course.units
        return chosen

    def _section_score(self, s: Section, prefs: Preferences) -> float:
        return (s.modality_group == prefs.modality) + (s.time_of_day == prefs.time_of_day)

    def _best_sections(self, prefs, term, chosen: list[Candidate], strat: Strategy) -> Schedule | None:
        options = []
        for cand in chosen:
            secs = sorted(self.repo.sections_for(term, cand.course.id),
                          key=lambda s: -self._section_score(s, prefs))[: self.sections_per_course]
            if secs:
                options.append([(cand, s) for s in secs])
        best = None
        for combo in product(*options):
            secs = [s for _, s in combo]
            if any(a.conflicts_with(b) for i, a in enumerate(secs) for b in secs[i + 1:]):
                continue
            score = sum(strat.interest_weight * c.interest
                        + strat.preference_weight * self._section_score(s, prefs) for c, s in combo)
            if best is None or score > best[0]:
                best = (score, combo)
        if best is None:
            # nothing fits together -> drop the lowest-priority course and retry
            return self._best_sections(prefs, term, chosen[:-1], strat) if len(chosen) > 1 else None
        items = [ScheduledCourse(c.course, s, c.is_core, c.interest) for c, s in best[1]]
        return Schedule(term=term, items=items, score=best[0])
