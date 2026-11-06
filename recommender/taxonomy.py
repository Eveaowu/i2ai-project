"""Curated interests anchored to topics present in the Heinz course catalog."""
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class Interest:
    id: str
    label: str
    text: str
    example_course_ids: tuple[str, ...]


CAREER = (
    Interest("software_engineer", "Software Engineer", "software engineering development programming Python web applications distributed systems algorithms databases Linux", ("95-881", "95-896", "95-702")),
    Interest("ai_engineer", "AI Engineer", "artificial intelligence generative AI agents large language models machine learning deployment software", ("94-846", "95-820", "95-800")),
    Interest("machine_learning_engineer", "Machine Learning Engineer", "machine learning deep learning predictive models Python software data science deployment", ("95-828", "95-876", "95-829")),
    Interest("data_scientist", "Data Scientist", "data science statistical analysis exploratory data analytics machine learning experimentation Python", ("95-885", "95-868", "95-819")),
    Interest("data_engineer", "Data Engineer", "data engineering database management SQL NoSQL distributed systems data pipelines cloud", ("95-703", "95-736", "95-737")),
    Interest("product_manager", "Product Manager", "product management product analytics experimentation A/B testing design strategy agile innovation customer", ("95-851", "95-819", "95-874")),
    Interest("cybersecurity_analyst", "Cybersecurity Analyst", "cybersecurity information security network defense threat analysis risk privacy security operations", ("95-752", "95-884", "95-889")),
    Interest("technology_consultant", "Technology Consultant", "management consulting technology strategy digital transformation organizational change project management", ("94-808", "95-722", "95-867")),
    Interest("ai_governance_specialist", "AI Governance Specialist", "responsible artificial intelligence governance ethics fairness accountability privacy risk policy", ("94-847", "95-841", "95-802")),
    Interest("policy_analyst", "Policy Analyst", "public policy analysis evidence econometrics surveys geographic information social programs", ("94-834", "94-828", "94-710")),
    Interest("healthcare_analyst", "Healthcare Analyst", "healthcare health economics digital health analytics information systems policy", ("94-705", "94-709", "94-826")),
    Interest("financial_data_analyst", "Financial Data Analyst", "financial investing accounting finance analytics time series forecasting decision uncertainty", ("94-818", "95-719", "95-835")),
)

ACADEMIC = (
    Interest("machine_learning", "Machine Learning", "machine learning supervised unsupervised predictive models model evaluation", ("95-828", "94-489")),
    Interest("artificial_intelligence", "Artificial Intelligence", "artificial intelligence AI intelligent systems agents planning", ("95-800", "94-846")),
    Interest("generative_ai_nlp", "Generative AI and NLP", "generative AI natural language processing NLP LLM large language models agents", ("95-820", "94-846", "94-728")),
    Interest("data_science", "Data Science", "data science analytics statistics exploratory data analysis big data", ("95-885", "95-868")),
    Interest("software_systems", "Software Systems", "software engineering programming Python web development distributed systems Linux algorithms", ("95-881", "95-896", "95-702")),
    Interest("databases", "Databases and Data Engineering", "database management relational SQL NoSQL data engineering data pipelines", ("95-703", "95-736", "95-737")),
    Interest("cybersecurity", "Cybersecurity", "cybersecurity network security threat analysis defenses penetration testing information security", ("95-752", "95-883", "95-884")),
    Interest("privacy_governance", "Privacy and AI Governance", "privacy responsible AI ethics governance fairness accountability risk policy", ("94-806", "94-847", "95-841")),
    Interest("product_innovation", "Product and Innovation", "product management innovation entrepreneurship agile design strategy experimentation A/B testing", ("95-851", "94-855", "95-819")),
    Interest("technology_management", "Technology Management", "technology strategy management digital transformation consulting organizational change", ("95-722", "94-808", "95-867")),
    Interest("policy_analytics", "Policy Analytics", "public policy econometrics causal analysis surveys evidence geographic information GIS", ("94-710", "94-834", "94-802")),
    Interest("healthcare_analytics", "Healthcare Analytics", "healthcare health economics digital health analytics information systems", ("94-705", "94-709", "94-826")),
    Interest("financial_analytics", "Financial Analytics", "finance financial investing accounting time series forecasting uncertainty", ("94-818", "95-719", "95-835")),
    Interest("visualization", "Data Visualization", "data visualization Tableau storytelling communicating data business intelligence", ("94-819", "94-870", "95-877")),
)

TAXONOMY = {"career": {i.id: i for i in CAREER}, "academic": {i.id: i for i in ACADEMIC}}


def taxonomy_payload():
    return {"schema_version": "1.0", **{kind: [asdict(item) for item in items.values()] for kind, items in TAXONOMY.items()}}

