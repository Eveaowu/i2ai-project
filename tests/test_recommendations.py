import copy
import json
import shutil

import numpy as np
import pytest
from pydantic import ValidationError

from recommender.catalog import Catalog
from recommender.model import RecommendationModel
from recommender.schemas import StudentProfile
from recommender.service import RecommendationService, prerequisites_met
from recommender.taxonomy import TAXONOMY


def profile(career="software_engineer", program="AIM12", **extra):
    return {"program_id": program, "interests": {"career": [{"id": career}]}, **extra}


@pytest.mark.parametrize("expression,completed,expected", [
    ("", set(), True),
    ("95-888 or 95-896", {"95-896"}, True),
    ("(95-888 or 95-896) and (95-796)", {"95-896"}, False),
    ("(95-888 or 95-896) and (95-796)", {"95-896", "95-796"}, True),
    ("11-785", set(), False),
    ("advisor permission", set(), False),
    ("__import__('os').system('echo unsafe')", set(), False),
])
def test_prerequisite_logic(expression, completed, expected):
    assert prerequisites_met(expression, completed) is expected


def test_all_roster_students_receive_only_eligible_electives(service):
    for sid, student in service.catalog.students.items():
        result = service.recommend({"student_id": sid, "interests": {"academic": [{"id": "data_science"}]}}, term="S27")
        ids = result["selected_course_ids"]
        assert ids and len(ids) == len(set(ids))
        completed = service.catalog.completed(sid)
        titles = set()
        for course in result["recommendations"]:
            cid = course["course_id"]
            assert service.catalog.regular(cid)
            assert cid not in service.catalog.core[student["declared_program_id"]]
            assert cid not in completed
            assert cid in service.catalog.offered("S27")
            assert prerequisites_met(course["prerequisites"], completed)
            assert prerequisites_met(course["corequisites"], completed)
            assert course["title"].casefold() not in titles
            titles.add(course["title"].casefold())
        scores = [row["score"] for row in result["recommendations"]]
        assert scores == sorted(scores, reverse=True)


def test_distinct_careers_change_rankings(service):
    product = service.recommend(profile("product_manager"), top_k=5)
    security = service.recommend(profile("cybersecurity_analyst"), top_k=5)
    software = service.recommend(profile(), top_k=5)
    assert "product" in " ".join(row["title"].lower() for row in product["recommendations"])
    assert any("security" in row["title"].lower() for row in security["recommendations"])
    assert any("software" in row["title"].lower() or "python" in row["title"].lower() for row in software["recommendations"])
    assert product["selected_course_ids"] != security["selected_course_ids"]


def test_experience_changes_scores(service):
    plain = profile("product_manager")
    experienced = copy.deepcopy(plain)
    experienced["experience"] = {"skills": ["Python", "web development", "distributed systems"]}
    a, b = service.recommend(plain, top_k=50), service.recommend(experienced, top_k=50)
    assert a["weights"]["experience"] == 0
    assert b["weights"]["experience"] > 0
    shared = set(a["selected_course_ids"]) & set(b["selected_course_ids"])
    score_a = {row["course_id"]: row["score"] for row in a["recommendations"]}
    score_b = {row["course_id"]: row["score"] for row in b["recommendations"]}
    assert any(score_a[cid] != score_b[cid] for cid in shared)


def test_missing_interests_use_other_students(service):
    existing = service.recommend({"student_id": "S003"})
    newcomer = service.recommend({"program_id": "AIM16"})
    assert existing["interest_source"] == "population_course_history_proxy"
    assert existing["population_students_used"] == 99
    assert newcomer["population_students_used"] == 100
    assert existing["effective_interests"]["career"]
    assert existing["effective_interests"]["academic"]
    assert service.recommend({"student_id": "S003"}) == existing


def test_unverified_transcript_does_not_unlock_prerequisites(service):
    request = profile("data_scientist", experience={"academic_records": [
        {"course_id": "95-888", "title": "Data Focused Python", "grade": "A", "status": "completed"}
    ]})
    result = service.recommend(request, top_k=50)
    assert "95-888" not in result["selected_course_ids"]
    assert "95-865" not in result["selected_course_ids"]
    assert "95-885" not in result["selected_course_ids"]
    assert any("unverified" in warning for warning in result["warnings"])


@pytest.mark.parametrize("payload", [
    {"student_id": "unknown"}, {},
    {"student_id": "S001", "program_id": "AIM16"},
    profile("mathematician"),
])
def test_invalid_identity_or_interest_rejected(service, payload):
    with pytest.raises(ValueError):
        service.recommend(payload)


def test_unknown_term_rejected(service):
    with pytest.raises(ValueError, match="Unknown offering term"):
        service.recommend(profile(), term="S99")


def test_corequisite_requires_completed_evidence(service, monkeypatch):
    monkeypatch.setattr(service.catalog, "completed", lambda sid: {"94-846"})
    result = service.recommend(profile("ai_engineer"), top_k=50)
    assert "95-879" not in result["selected_course_ids"]
    assert result["excluded_counts"]["corequisites_not_completed"] == 1
    monkeypatch.setattr(service.catalog, "completed", lambda sid: {"94-846", "94-815"})
    result = service.recommend(profile("ai_engineer"), top_k=50)
    assert result["excluded_counts"]["corequisites_not_completed"] == 0


@pytest.mark.parametrize("weight", [0, -1, 1.1, float("nan"), float("inf")])
def test_invalid_interest_weights_rejected(weight):
    with pytest.raises(ValidationError):
        StudentProfile.model_validate({"program_id": "AIM12", "interests": {"career": [{"id": "software_engineer", "weight": weight}]}})


def test_duplicate_interests_rejected():
    with pytest.raises(ValidationError):
        StudentProfile.model_validate({"interests": {"academic": [{"id": "data_science"}, {"id": "data_science"}]}})


def test_taxonomy_is_catalog_supported(service):
    for options in TAXONOMY.values():
        for interest in options.values():
            assert interest.example_course_ids
            assert all(cid in service.catalog.courses and service.catalog.regular(cid) for cid in interest.example_course_ids)
            assert any(cid not in service.catalog.core["AIM12"] for cid in interest.example_course_ids)


def test_persistence_and_stale_data(service, tmp_path):
    path = tmp_path / "model.joblib"
    service.model.save(path)
    loaded = RecommendationService.from_artifact(path)
    assert loaded.recommend(profile()) == service.recommend(profile())
    for filename in service.model.report["source_hashes"]:
        shutil.copy(service.catalog.data_dir / filename, tmp_path / filename)
    with (tmp_path / "courses.csv").open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="retrain"):
        RecommendationModel.load(path, Catalog(tmp_path))


def test_credit_amounts_do_not_affect_model(service):
    catalog = copy.deepcopy(service.catalog)
    for student in catalog.students.values():
        rows = json.loads(student["completed_courses"])
        for row in rows:
            row["credits"] = 999
        student["completed_courses"] = json.dumps(rows)
        student["credits_completed"] = "99999"
        student["current_gpa"] = "0"
    model = RecommendationModel().fit(catalog)
    assert model.population.keys() == service.model.population.keys()
    for sid in model.population:
        np.testing.assert_allclose(model.population[sid], service.model.population[sid])
    assert RecommendationService(catalog, model).recommend(profile()) == service.recommend(profile())

