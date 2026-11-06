"""python -m recommender train|recommend|extract|taxonomy"""
import argparse
import json
from pathlib import Path

from .catalog import DEFAULT_DATA, ROOT, Catalog
from .documents import extract_document, merge_experience
from .model import RecommendationModel
from .schemas import Experience, StudentProfile
from .service import RecommendationService
from .taxonomy import taxonomy_payload

DEFAULT_MODEL = ROOT / "artifacts" / "recommender.joblib"


def main():
    parser = argparse.ArgumentParser(description="Train and run elective recommendations")
    sub = parser.add_subparsers(dest="command", required=True)
    train = sub.add_parser("train")
    train.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    train.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    train.add_argument("--topics", type=int, default=16)
    recommend = sub.add_parser("recommend")
    recommend.add_argument("--profile", type=Path, required=True)
    recommend.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    recommend.add_argument("--model", type=Path, default=DEFAULT_MODEL)
    recommend.add_argument("--resume", type=Path, action="append", default=[])
    recommend.add_argument("--transcript", type=Path, action="append", default=[])
    recommend.add_argument("--term")
    recommend.add_argument("--top-k", type=int, default=10)
    recommend.add_argument("--output", type=Path)
    extract = sub.add_parser("extract")
    extract.add_argument("file", type=Path)
    extract.add_argument("--kind", choices=["resume", "transcript"], required=True)
    extract.add_argument("--output", type=Path)
    sub.add_parser("taxonomy")
    args = parser.parse_args()
    try:
        if args.command == "train":
            if not 2 <= args.topics <= 64:
                raise ValueError("topics must be between 2 and 64")
            model = RecommendationModel().fit(Catalog(args.data_dir), n_topics=args.topics)
            model.save(args.model)
            output = model.report
        elif args.command == "recommend":
            profile = StudentProfile.model_validate_json(args.profile.read_text(encoding="utf-8-sig"))
            experiences, warnings = [profile.experience], []
            for kind in ("resume", "transcript"):
                for path in getattr(args, kind):
                    result = extract_document(path.read_bytes(), path.name, kind)
                    experiences.append(Experience.model_validate(result["experience"]))
                    warnings.extend(result["warnings"])
            profile.experience = merge_experience(*experiences)
            service = RecommendationService.from_artifact(args.model, args.data_dir)
            output = service.recommend(profile, term=args.term, top_k=args.top_k)
            output["warnings"] = list(dict.fromkeys(warnings + output["warnings"]))
        elif args.command == "extract":
            output = extract_document(args.file.read_bytes(), args.file.name, args.kind)
        else:
            output = taxonomy_payload()
        text = json.dumps(output, indent=2, ensure_ascii=False) + "\n"
        if getattr(args, "output", None):
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(text, encoding="utf-8")
            print(f"Wrote {args.output}")
        else:
            print(text)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()

