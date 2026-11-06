# AIM course advising backend

Recommend Heinz elective courses using career and academic interests, resume
experience, and academic records. The recommendation backend runs locally without
an LLM API key. The existing scheduling backend is preserved.

## Run a complete example

Python 3.11 is the tested runtime. Install the dependencies in your Python
environment, then run these commands from the repository root:

```powershell
py -3.11 -m pip install -r requirements-dev.txt
py -3.11 -B -m recommender train
py -3.11 -B -m recommender recommend --profile dataset/samples/profiles/ai_engineer.json --resume dataset/samples/documents/ai_engineer_resume.txt --transcript dataset/samples/documents/ai_engineer_transcript.txt --term S27 --top-k 10 --output artifacts/demo.json
py -3.11 -B -m scripts.evaluate_recommender
py -3.11 -B -m pytest -q
```

On macOS/Linux, use `python` in place of `py -3.11`. For runtime dependencies
without test tools, install `requirements.txt`. A virtual environment is
recommended. All generated models and result files are under `artifacts/`, which
is ignored by Git. Training writes `recommender.joblib` and
`recommender.report.json`. Evaluation writes six example recommendation lists and
an eligibility-check report. Rerun training after changing any input CSV or the
interest taxonomy. Only load locally generated model artifacts.

## HTTP API

Train the model first, then start the local development server:

```powershell
py -3.11 -B -m uvicorn recommender.api:app --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Check that a trained, current model loaded successfully. |
| `GET /interests` | Retrieve supported interest IDs, labels, and course examples. |
| `POST /extract` | Upload a resume or transcript as multipart fields `file` and `kind`; return editable structured experience. |
| `POST /recommendations` | Submit a JSON profile, optional offering term, and `top_k`; receive ranked electives and explanations. |

This server is a local prototype with no account authentication or persistent
student-profile storage. Keep it bound to loopback during development. Uploaded
documents are processed in memory and are not saved by the API. Application or
proxy logging should also avoid request bodies containing student information.

## Inputs, samples, and model details

- [Recommendation contract and frontend integration](docs/RECOMMENDATION.md)
  describes every profile field, sample generation, document formats, ranking,
  population fallback, and response semantics.
- [Original dataset schema and joins](docs/DATA_SCHEMA.md) describes all six CSVs.
- [Dataset preparation and provenance](dataset/DATA_NOTES.md) records the approved
  elective rule, generated descriptions, flexible TBA assumption, and date changes.
- [Sample manifest](dataset/samples/manifest.json) connects six profiles to their
  synthetic resume/transcript documents.

There are 100 seeded synthetic interest profiles, six scenario profiles, and
six pairs of plain-text resume/transcript documents. They are clearly marked as
development fixtures and are excluded from model training and population-interest
inference. Reproduce them with `py -3.11 -B -m scripts.generate_samples`.

For AIM12 and AIM16, regular courses outside the student's program core
requirements may count as electives. Recommendations also exclude completed
courses, check prerequisites against the provided roster, and optionally filter
by actual term offerings. TBA meetings do not reduce recommendation scores.

## Model and evidence limits

Training fits TF-IDF and 16 NMF topics to 168 regular courses. It also fits a
population-interest profile from the provided students' completed-course content.
Ranking combines interests, work/project experience, and academic topics. Scores
express relative relevance, not success probabilities. Missing interests use an
explicitly identified population proxy; course enrollment is not proof of a
student's preference, and the provided roster's representativeness is unknown.

The 621 previously identified student-course credit discrepancies remain. Credit
amounts and GPA do not influence recommendation training or ranking. The model
uses course identities and content; grades only help distinguish completed roster
courses from failed/unfinished courses. Degree-progress calculations still require
credit reconciliation. No student relevance judgments are available, so the
evaluation reports constraint checks and synthetic scenarios, not measured
recommendation accuracy.

## Existing scheduler

The original CLI remains `py -3.11 -B main.py S001 "machine learning" --json`.
Recommendation results contain course IDs and offered section IDs for future
selection and scheduling integration. The current scheduler does not yet accept a
fixed list of selected recommendation IDs. No scheduling algorithm changes or
frontend were added.
