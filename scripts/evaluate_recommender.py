"""Run synthetic scenarios, save recommendations, and report constraint checks."""
import json
from pathlib import Path

from recommender.catalog import DEFAULT_DATA, ROOT
from recommender.documents import extract_document, merge_experience
from recommender.schemas import Experience, StudentProfile
from recommender.service import RecommendationService, prerequisites_met


def main():
    output = ROOT / "artifacts" / "examples"
    output.mkdir(parents=True, exist_ok=True)
    service = RecommendationService.from_artifact(ROOT / "artifacts/recommender.joblib")
    manifest = json.loads((DEFAULT_DATA / "samples/manifest.json").read_text(encoding="utf-8"))
    summary = {"evaluation_type": "synthetic_scenario_and_constraint_checks", "relevance_accuracy": None,
               "note": "No observed student judgments or held-out relevance labels are available.", "scenarios": []}
    for sample in manifest["scenarios"]:
        profile = StudentProfile.model_validate_json((DEFAULT_DATA / sample["profile"]).read_text(encoding="utf-8"))
        experiences, extraction_warnings = [profile.experience], []
        for kind in ("resume", "transcript"):
            path = DEFAULT_DATA / sample[kind]
            extracted = extract_document(path.read_bytes(), path.name, kind)
            experiences.append(Experience.model_validate(extracted["experience"]))
            extraction_warnings.extend(extracted["warnings"])
        profile.experience = merge_experience(*experiences)
        result = service.recommend(profile, term="S27", top_k=10)
        result["warnings"] = list(dict.fromkeys(extraction_warnings + result["warnings"]))
        completed = service.catalog.completed(profile.student_id)
        for course in result["recommendations"]:
            assert course["course_id"] not in service.catalog.core[result["program_id"]]
            assert course["course_id"] not in completed
            assert service.catalog.regular(course["course_id"])
            assert course["course_id"] in service.catalog.offered("S27")
            assert prerequisites_met(course["prerequisites"], completed)
            assert prerequisites_met(course["corequisites"], completed)
        (output / f"{sample['scenario']}.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        summary["scenarios"].append({"scenario": sample["scenario"], "synthetic": True,
                                     "recommendation_count": len(result["recommendations"]),
                                     "interest_source": result["interest_source"], "eligibility_checks_passed": True,
                                     "top_five": [{"course_id": course["course_id"], "title": course["title"]} for course in result["recommendations"][:5]]})
    (output.parent / "evaluation.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()

