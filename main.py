"""CLI demo.
    python main.py S001 "machine learning, NLP"
    python main.py S001 "machine learning" --json > plan.json
"""
import json
import sys

from scheduler import SchedulePlanner


def fmt_time(m: int) -> str:
    return f"{m // 60:02d}:{m % 60:02d}"


def print_plan(result):
    st, req = result.student, result.requirements
    print(f"{st.id} {st.name} | {st.program_id} | prefs: {st.preferences.to_dict()}")
    print(f"Interest: {result.interest!r} | term: {result.term}")
    print(f"Remaining core ({len(req.remaining_core)}): {', '.join(req.remaining_core)}")
    print(f"Elective credits left: {req.elective_credits_left}")
    for i, s in enumerate(result.schedules, 1):
        v = s.validation
        print(f"\nOption {i}: {s.label}  ({s.units} units, score {s.score:.2f}, valid={v.valid})")
        for it in s.items:
            tag = "CORE" if it.is_core else "elec"
            print(f"  [{tag}] {it.section.id:16} {it.course.title[:40]:40} "
                  f"{it.section.days_times:38} {it.section.modality}")
        for msg in v.errors + v.warnings:
            print("   !", msg)
        print(f"  -> projected graduation: {s.graduation.term}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--json"]
    sid = args[0] if args else "S001"
    interest = args[1] if len(args) > 1 else "machine learning"
    result = SchedulePlanner.from_csv().plan(sid, interest)
    if "--json" in sys.argv:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print_plan(result)
