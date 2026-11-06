"""Reproduce synthetic frontend profiles and plain-text experience documents."""
import json
import random
from pathlib import Path

from recommender.catalog import DEFAULT_DATA, Catalog
from recommender.schemas import StudentProfile
from recommender.taxonomy import TAXONOMY, taxonomy_payload

OUTPUT = DEFAULT_DATA / "samples"
BUNDLES = (
    ("ai_engineer", ["generative_ai_nlp", "machine_learning"]),
    ("product_manager", ["product_innovation", "visualization"]),
    ("cybersecurity_analyst", ["cybersecurity", "privacy_governance"]),
    ("policy_analyst", ["policy_analytics", "data_science"]),
    ("financial_data_analyst", ["financial_analytics", "data_science"]),
    ("software_engineer", ["software_systems", "databases"]),
    ("machine_learning_engineer", ["machine_learning", "data_science"]),
    ("data_engineer", ["databases", "software_systems"]),
    ("data_scientist", ["data_science", "visualization"]),
    ("technology_consultant", ["technology_management", "product_innovation"]),
    ("ai_governance_specialist", ["privacy_governance", "artificial_intelligence"]),
    ("healthcare_analyst", ["healthcare_analytics", "policy_analytics"]),
)
SCENARIOS = (
    ("ai_engineer", "S001", 0, "AI Research Assistant | Fictional Analytics Lab | 2024-2025",
     "Python, machine learning, NLP, generative AI, SQL",
     "Built a Python document retrieval prototype and compared large language model outputs for a small research project.",
     "Document Question Answering", "Developed a natural language processing pipeline with retrieval and model evaluation.",
     [("CS101", "Python Programming", "A", 3), ("ML201", "Applied Machine Learning", "A-", 3), ("STAT101", "Statistics", "B+", 3)]),
    ("product_manager", "S002", 1, "Product Analytics Intern | Fictional Product Studio | 2024-2025",
     "product management, SQL, Tableau, A/B testing, agile",
     "Analyzed product adoption and designed an A/B testing plan to compare onboarding workflows.",
     "Customer Insights Dashboard", "Created Tableau visualizations and prioritized product improvements using customer data.",
     [("BUS201", "Product Strategy", "A-", 3), ("STAT210", "Experimental Design", "A", 3), ("DS101", "Data Visualization", "B+", 3)]),
    ("cybersecurity", "S051", 2, "Security Operations Intern | Fictional Security Team | 2024-2025",
     "cybersecurity, Python, network security, privacy, SQL",
     "Investigated security alerts and documented network defense procedures and information security risks.",
     "Threat Analysis Project", "Used Python to analyze security logs and categorize potential network threats.",
     [("SEC101", "Information Security", "A", 3), ("NET201", "Computer Networks", "A-", 3), ("CS102", "Python Programming", "B+", 3)]),
    ("policy_analytics", "S052", 3, "Policy Research Assistant | Fictional Policy Center | 2024-2025",
     "R, statistics, econometrics, data analysis, data visualization",
     "Analyzed survey data to evaluate public programs and communicated findings to policy stakeholders.",
     "Transit Access Study", "Combined geographic information and public policy evidence to study access to transportation.",
     [("ECON201", "Applied Econometrics", "A", 3), ("POL101", "Public Policy Analysis", "A-", 3), ("GIS101", "Geographic Information Systems", "B+", 3)]),
    ("financial_analytics", "S053", 4, "Financial Analytics Intern | Fictional Finance Group | 2024-2025",
     "Python, SQL, forecasting, statistics, data analysis",
     "Developed time series forecasting summaries and analyzed accounting and finance data for investment research.",
     "Financial Forecasting", "Compared forecasting models using historical financial data and evaluated decision uncertainty.",
     [("FIN201", "Financial Analysis", "A-", 3), ("STAT301", "Time Series Forecasting", "A", 3), ("ECON101", "Economics", "B+", 3)]),
    ("no_interests", "S003", None, "Software Development Intern | Fictional Software Group | 2024-2025",
     "Python, SQL, web development, data engineering",
     "Built web application endpoints and SQL queries for an internal data tool.",
     "Data Application", "Developed a Python web application and database pipeline with repeatable data validation.",
     [("CS101", "Python Programming", "A", 3), ("DB101", "Database Systems", "A-", 3), ("CS201", "Software Engineering", "B+", 3)]),
)


def write_json(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def interests_for(bundle):
    career, academic = bundle
    return {"career": [{"id": career, "weight": 1.0}],
            "academic": [{"id": academic[0], "weight": 0.7}, {"id": academic[1], "weight": 0.3}]}


def main():
    rng = random.Random(42)
    catalog = Catalog()
    records = []
    for index, (sid, student) in enumerate(sorted(catalog.students.items())):
        profile = StudentProfile.model_validate({"student_id": sid, "program_id": student["declared_program_id"],
                                                "interests": {} if index % 5 == 0 else interests_for(rng.choice(BUNDLES))})
        records.append({"synthetic": True, "profile": profile.model_dump()})
    manifest = []
    for name, sid, bundle_index, role, skills, work, project_title, project, rows in SCENARIOS:
        profile = StudentProfile.model_validate({"student_id": sid, "program_id": catalog.students[sid]["declared_program_id"],
                                                "interests": interests_for(BUNDLES[bundle_index]) if bundle_index is not None else {}})
        profile_path = OUTPUT / "profiles" / f"{name}.json"
        resume_path = OUTPUT / "documents" / f"{name}_resume.txt"
        transcript_path = OUTPUT / "documents" / f"{name}_transcript.txt"
        write_json(profile_path, profile.model_dump())
        resume_path.parent.mkdir(parents=True, exist_ok=True)
        resume_path.write_text(f"SYNTHETIC RESUME FOR DEVELOPMENT ONLY\nStudent: {sid}\n\nSkills\n{skills}\n\nWork Experience\n{role}\n{work}\n\nProjects\n{project_title}\n{project}\n\nEducation\nFictional Example University\n", encoding="utf-8")
        transcript = "SYNTHETIC TRANSCRIPT FOR DEVELOPMENT ONLY\nInstitution: Fictional Example University\nStudent: " + sid + "\n\nCourse ID | Title | Grade | Credits | Term | Status\n"
        transcript += "\n".join(f"{cid} | {title} | {grade} | {credits} | Spring 2024 | completed" for cid, title, grade, credits in rows)
        transcript_path.write_text(transcript + "\n", encoding="utf-8")
        manifest.append({"scenario": name, "synthetic": True, "profile": profile_path.relative_to(DEFAULT_DATA).as_posix(),
                         "resume": resume_path.relative_to(DEFAULT_DATA).as_posix(), "transcript": transcript_path.relative_to(DEFAULT_DATA).as_posix()})
    write_json(OUTPUT / "interest_records.json", {"schema_version": "1.0", "synthetic": True, "random_seed": 42,
               "purpose": "Frontend/development fixtures, excluded from model training and population fallback", "records": records})
    write_json(OUTPUT / "manifest.json", {"schema_version": "1.0", "synthetic": True, "scenarios": manifest})
    write_json(OUTPUT / "interest_taxonomy.json", taxonomy_payload())
    print(f"Generated {len(records)} synthetic profiles and {len(manifest)} resume/transcript pairs in {OUTPUT}")


if __name__ == "__main__":
    main()

