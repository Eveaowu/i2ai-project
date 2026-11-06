"""Rank electives and explain the evidence without constructing schedules."""
import ast
import re
from pathlib import Path

import numpy as np

from .catalog import DEFAULT_DATA, Catalog
from .model import RecommendationModel
from .schemas import StudentProfile
from .taxonomy import TAXONOMY


def prerequisites_met(expression, completed):
    if not expression.strip():
        return True
    expression = re.sub(r"\b\d{2}-\d{3}\b", lambda match: str(match.group() in completed), expression)
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, ValueError):
        return False

    def check(node):
        if isinstance(node, ast.Expression):
            return check(node.body)
        if isinstance(node, ast.Constant) and type(node.value) is bool:
            return node.value
        if isinstance(node, ast.BoolOp) and isinstance(node.op, (ast.And, ast.Or)):
            values = [check(value) for value in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        raise ValueError("Unsupported prerequisite expression")

    try:
        return check(tree)
    except ValueError:
        return False


def _title(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


class RecommendationService:
    def __init__(self, catalog, model):
        self.catalog, self.model = catalog, model

    @classmethod
    def from_artifact(cls, model_path, data_dir=DEFAULT_DATA):
        catalog = Catalog(data_dir)
        return cls(catalog, RecommendationModel.load(Path(model_path), catalog))

    def recommend(self, profile: StudentProfile | dict, *, term=None, top_k=10):
        profile = StudentProfile.model_validate(profile)
        if type(top_k) is not int or not 1 <= top_k <= 50:
            raise ValueError("top_k must be an integer between 1 and 50")
        if term is not None and term not in self.catalog.known_terms:
            raise ValueError(f"Unknown offering term {term!r}; available terms: {', '.join(self.catalog.known_terms)}. Use null for catalog-wide suggestions.")
        sid = profile.student_id
        if sid and sid not in self.catalog.students:
            raise ValueError(f"Unknown student_id: {sid}")
        roster_program = self.catalog.students[sid]["declared_program_id"] if sid else None
        if roster_program and profile.program_id and roster_program != profile.program_id:
            raise ValueError("program_id conflicts with the student's declared program")
        program = profile.program_id or roster_program
        if program not in self.catalog.core:
            raise ValueError("Provide a known student_id or a supported program_id")
        for category in TAXONOMY:
            for choice in getattr(profile.interests, category):
                if choice.id not in TAXONOMY[category]:
                    raise ValueError(f"Unknown {category} interest: {choice.id}")

        interests = profile.interests
        fallback_count = 0
        fallback = not (interests.career or interests.academic)
        if fallback:
            interests, fallback_count = self.model.population_interests(exclude_student=sid)
        interest_scores = np.zeros(len(self.model.ids))
        interest_texts = []
        category_count = sum(bool(getattr(interests, category)) for category in TAXONOMY)
        for category in TAXONOMY:
            choices = getattr(interests, category)
            total = sum(choice.weight for choice in choices)
            for choice in choices:
                text = TAXONOMY[category][choice.id].text
                interest_scores += self.model.similarity(text) * choice.weight / total / category_count
                interest_texts.append(text)

        experience = profile.experience
        experience_text = " ".join(experience.skills + [f"{entry.title} {entry.description}" for entry in experience.work_experience + experience.projects])
        completed = self.catalog.completed(sid)
        academic_text = " ".join(self.catalog.courses[cid]["title"] for cid in sorted(completed) if cid in self.catalog.courses)
        uploads = [row for row in experience.academic_records if row.status in {"completed", "in_progress"}
                   and (row.grade or "").upper() not in {"F", "W", "NP", "N", "I"}]
        academic_text += " " + " ".join(row.title for row in uploads)
        academic_text = academic_text.strip()

        weights = {"interests": 0.65, "experience": 0.25 if experience_text.strip() else 0.0,
                   "academic": 0.10 if academic_text else 0.0}
        total_weight = sum(weights.values())
        weights = {key: value / total_weight for key, value in weights.items()}
        components = {"interests": interest_scores, "experience": self.model.similarity(experience_text),
                      "academic": self.model.similarity(academic_text)}
        scores = sum(weights[key] * vector for key, vector in components.items())
        texts = {"interests": " ".join(interest_texts), "experience": experience_text, "academic": academic_text}

        warnings = ["Credit discrepancies in the provided roster are excluded from ranking; degree progress is not evaluated."]
        if fallback:
            warnings.append("Interests were inferred from course completions across other students, not from stated preferences. The supplied roster's representativeness has not been established.")
        if experience.academic_records:
            warnings.append("Uploaded academic records are unverified: titles inform relevance and claimed completed catalog courses are suppressed, but uploads do not satisfy prerequisites or grant waivers.")
        if term is None:
            warnings.append("Catalog-wide suggestions: availability in a particular future term is not guaranteed.")

        # A claimed completed course may suppress repeats without authorizing access
        # to prerequisite-restricted courses. Ambiguous external title matches do not.
        claimed_completed = set()
        for row in uploads:
            if row.status != "completed" or (row.grade or "").upper() in {"I", "IP", "IN PROGRESS", "N/A"}:
                continue
            course = self.catalog.courses.get(row.course_id)
            if course and _title(course["title"]) == _title(row.title):
                claimed_completed.add(row.course_id)
        taken = completed | claimed_completed
        completed_titles = {_title(self.catalog.courses[cid]["title"]) for cid in taken if cid in self.catalog.courses}
        offered = self.catalog.offered(term) if term is not None else None
        exclusions = {"program_core": 0, "completed": 0, "not_offered": 0, "prerequisites_unmet_or_unverified": 0,
                      "corequisites_not_completed": 0}
        eligible = []
        for cid in self.model.ids:
            course = self.catalog.courses[cid]
            if cid in self.catalog.core[program]:
                exclusions["program_core"] += 1
            elif cid in taken or _title(course["title"]) in completed_titles:
                exclusions["completed"] += 1
            elif offered is not None and cid not in offered:
                exclusions["not_offered"] += 1
            elif not prerequisites_met(course["prerequisites"], completed):
                exclusions["prerequisites_unmet_or_unverified"] += 1
            elif not prerequisites_met(course["corequisites"], completed):
                exclusions["corequisites_not_completed"] += 1
            else:
                eligible.append(cid)
        eligible.sort(key=lambda cid: (-float(scores[self.model.index[cid]]), cid))
        recommended, seen_titles = [], set()
        for cid in eligible:
            course = self.catalog.courses[cid]
            key = _title(course["title"])
            if key in seen_titles:
                continue
            seen_titles.add(key)
            index = self.model.index[cid]
            score = float(scores[index])
            if score <= 0:
                continue
            matches = {signal: self.model.matching_terms(texts[signal], cid) for signal in texts}
            reasons = []
            for signal in sorted(weights, key=lambda key: -weights[key] * float(components[key][index])):
                if weights[signal] and matches[signal]:
                    reasons.append(f"Matches {'inferred population interests' if signal == 'interests' and fallback else signal}: {', '.join(matches[signal][:4])}.")
            if not reasons:
                reasons.append("Related to the input through learned course topics.")
            sections = [r for r in self.catalog.sections if r["course_id"] == cid and r["section_status"] == "Offered"
                        and (term is None or r["term"] == term)]
            recommended.append({
                "rank": len(recommended) + 1, "course_id": cid, "title": course["title"],
                "units": float(course["units_typical"]) if course["units_typical"] else None,
                "description": course["description"], "score": round(score, 6),
                "score_components": {key: round(float(vector[index]), 6) for key, vector in components.items()},
                "reasons": reasons, "matching_terms": matches,
                "prerequisites": course["prerequisites"], "prerequisites_met": True,
                "corequisites": course["corequisites"], "corequisites_met": True,
                "offered_terms": sorted({r["term"] for r in sections}),
                "section_ids": sorted(r["section_id"] for r in sections),
                "has_tba_meetings": any("TBA" in r["days_times"] for r in sections),
            })
            if len(recommended) == top_k:
                break
        if len(recommended) < top_k:
            warnings.append(f"Only {len(recommended)} distinct eligible courses with positive relevance were found; results were not padded.")
        return {
            "schema_version": "1.0", "student_id": sid, "program_id": program, "term": term,
            "interest_source": "population_course_history_proxy" if fallback else "explicit",
            "population_students_used": fallback_count, "effective_interests": interests.model_dump(),
            "weights": weights, "eligible_courses_before_title_deduplication": len(eligible),
            "excluded_counts": exclusions, "recommendations": recommended,
            "selected_course_ids": [row["course_id"] for row in recommended],
            "warnings": warnings, "score_meaning": "relative relevance, not a probability or predicted grade",
        }

