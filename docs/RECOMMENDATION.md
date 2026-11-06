# Recommendation backend contract

This backend ranks elective courses. It does not allocate meeting times, evaluate
graduation progress, or change the existing scheduler. It uses local NLP and an
unsupervised trained model; no LLM API key or external inference call is needed.

## Frontend input

The profile schema is version `1.0`. This is a complete valid request to
`POST /recommendations`:

```json
{
  "profile": {
    "schema_version": "1.0",
    "student_id": "S001",
    "program_id": "AIM12",
    "interests": {
      "career": [{"id": "ai_engineer", "weight": 1.0}],
      "academic": [
        {"id": "generative_ai_nlp", "weight": 0.7},
        {"id": "machine_learning", "weight": 0.3}
      ]
    },
    "experience": {
      "skills": ["Python", "natural language processing"],
      "work_experience": [
        {
          "title": "Research Assistant",
          "organization": "Example Lab",
          "description": "Built a Python document retrieval prototype.",
          "source": "resume.txt"
        }
      ],
      "projects": [
        {
          "title": "Document Question Answering",
          "description": "Compared model outputs and retrieval methods.",
          "source": "resume.txt"
        }
      ],
      "academic_records": [
        {
          "course_id": "ML201",
          "title": "Applied Machine Learning",
          "institution": "Example University",
          "grade": "A-",
          "credits": 3,
          "term": "Spring 2024",
          "status": "completed",
          "source": "transcript.txt"
        }
      ]
    }
  },
  "term": "S27",
  "top_k": 10
}
```

### Identity and options

- `student_id` is optional. When present it must identify a provided roster
  student; that student's completed courses and declared program are used.
- `program_id` is optional with a known student ID. Otherwise it is required and
  must be `AIM12` or `AIM16`. A program conflicting with the roster is rejected.
- `term` is optional or null for catalog-wide recommendations. A supplied term
  must exist in the offering data: M26, F26, or S27. Unsupported future terms are
  rejected rather than assumed available.
- `top_k` defaults to 10 and must be an integer between 1 and 50.
- Unexpected input fields are rejected. Omitted interests and experience default
  to empty objects. JSON null is not a substitute for an empty interest object.

### Interest selections

Fetch `GET /interests` to populate UI controls. Store the stable `id` values,
not display labels or arbitrary text. The catalog currently supports 12 career
interests and 14 academic interests, with example course IDs for each.

Careers include software engineer, AI engineer, machine learning engineer, data
scientist, data engineer, product manager, cybersecurity analyst, technology
consultant, AI governance specialist, policy analyst, healthcare analyst, and
financial data analyst. Academic topics include AI, machine learning, generative
AI/NLP, data science, software systems, databases, security, privacy/governance,
product innovation, technology management, policy analytics, healthcare analytics,
financial analytics, and visualization.

Pure mathematics and a standalone quantitative-research career are intentionally
omitted: the provided course coverage supports financial analytics more directly.
Do not add a new interest without reviewing its support in the actual catalog.
Interest definitions are in `recommender/taxonomy.py`; retrain after editing them.

Both categories are arrays of `{ "id": string, "weight": number }`. Weights
default to 1 and must be finite, greater than zero, and at most 1. They need not
sum to 1; they are normalized within each category. Duplicate IDs and unknown IDs
are rejected. A category with no selections is an empty array. If only one
category is selected, that category supplies the interest signal. If both are
selected, career and academic relevance receive equal weight within that signal.

When both arrays are empty or interests are omitted, the population fallback is
used. The backend does not silently load a synthetic interest profile for a real
student ID.

### Experience structure

`skills` is a list of strings. `work_experience` and `projects` are lists of
entries with optional `title`, optional `organization`, required nonempty
`description`, and optional `source` (defaults to `user_input`).

`academic_records` is a list of entries with required nonempty `title`, optional
`course_id`, `institution`, `grade`, `credits`, `term`, and `source`. `status` is
one of `completed`, `in_progress`, `failed`, or `unknown` and defaults to `unknown`.
Grade and term are strings because external institutions use different systems.
External credits are retained as extracted facts but are never treated as
equivalent to CMU units. The lists have finite limits defined in the OpenAPI
schema, and text fields have length limits.

Academic course titles and supplied work/project descriptions inform relevance.
Failed or unknown-status academic records do not supply the academic signal.
Roster course identities provide prior academic topics. Credit amounts and GPA
are not ranking features.

## Resume and transcript extraction

Send multipart form fields `file` and `kind` (`resume` or `transcript`) to
`POST /extract`. The response includes `experience`, `warnings`, `source`, and
`extracted_text`. Show the extracted fields and warnings for review and editing,
then merge the reviewed experience into the profile sent to `/recommendations`.
Multiple uploads can contribute to a single profile. The CLI merges repeated
`--resume` and `--transcript` inputs automatically.

Supported inputs are UTF-8 TXT/MD, structured JSON, DOCX paragraphs/tables, and
text-based PDF. Each file is limited to 5 MiB, PDF files to 30 pages, and extracted
text to 200,000 characters. Encrypted and text-free PDFs are rejected. Scanned
transcripts need OCR before upload; this baseline does not provide OCR.
Documents are processed locally and their contents are not sent to an LLM.

Resume extraction recognizes `Skills`, `Technical Skills`, `Work Experience`,
`Professional Experience`, `Experience`, `Employment`, `Projects`, and
`Project Experience` headings, case-insensitively. Work/project sections are split
on blank paragraphs; an entry's first line can use `title | organization | dates`.
Dates are preserved in the description rather than inferred into a timeline.
Known skill phrases and abbreviations are normalized. This rule-based parser
does not claim to fully understand every resume layout or distinguish every
negated or aspirational skill; review remains necessary.

Transcript rows should have these columns, separated by pipes, tabs, or at least
two spaces:

```text
Institution: Example University
Course ID | Title | Grade | Credits | Term | Status
CS101 | Python Programming | A | 3 | Spring 2024 | completed
ML201 | Machine Learning | IP | 3 | Fall 2024 | in_progress
```

The first four columns are needed for deterministic parsing; term and status are
optional. Common letter grades, P/PASS/S, NP, W, I, and IP are supported. A failing
or incomplete grade overrides an incompatible `completed` label. Unknown layouts
return a review warning and no invented course records. For a different grading
scheme, submit reviewed structured `academic_records` instead.

A JSON document must contain an `Experience` object, using the fields described
above, without a surrounding profile or request envelope. This offers an explicit
alternative to heuristic text parsing.

Document course IDs and titles are unverified. An exact uploaded catalog ID/title
pair marked completed can suppress repeat recommendations, but it does not grant
prerequisite credit, transfer credit, or waivers. External similarly named courses
do not automatically map to catalog IDs. Formal equivalency verification is a
future advisor workflow. The trusted completion source in this prototype is the
provided roster; a production service needs an authenticated academic-record source.

## Training and fallback model

`python -m recommender train` fits a TF-IDF vectorizer with English stop words,
unigrams/bigrams, and logarithmic term frequency to the 168 regular courses. Each
course title appears three times alongside its description. Common abbreviations
such as AI, ML, NLP, LLM, and ETL are expanded transparently. A seeded NMF model
learns 16 nonnegative topics. Text similarity combines 80% TF-IDF cosine similarity
and 20% cosine similarity in the learned topic representation.

The population model uses all 100 provided students with completed regular
courses. It averages distinct completed-course vectors for each student and
normalizes each student vector. This gives students equal contribution regardless
of credit amounts or course load. For missing-interest inference, it averages
those student vectors, excludes the requesting roster student, and compares the
centroid to the curated career and academic definitions. The top three positively
matched interests in each category become weighted fallback interests.

An existing student therefore uses 99 other students; a newcomer uses all 100.
If no other usable students exist, inference returns a clear error. The response
identifies the source as `population_course_history_proxy`, reports the population
count, and returns the effective interests. These are inferred common academic
patterns, not measured career aspirations. The roster's origin and
representativeness have not been established. Synthetic fixture interests and
documents are never loaded during training or population inference.

Artifacts include source CSV hashes, a taxonomy hash, Python/scikit-learn versions,
seed, vocabulary size, topic terms, reconstruction error, and NMF iteration count.
Loading rejects a stale dataset/taxonomy or a changed scikit-learn version. Joblib
artifacts are trusted local files and must never be accepted as uploads.

## Ranking and eligibility

The default ranking weights are 0.65 interests, 0.25 work/project/skill evidence,
and 0.10 academic topics. Missing experience signals receive zero weight and the
remaining weights are renormalized. Interest-category weights are handled as
described above. There is no supervised relevance target in the data; these
weights are transparent configuration choices, not learned preference weights.

The backend ranks only regular courses outside the declared program's core.
It removes roster-completed courses, exact claimed completed catalog courses,
and duplicate-title alternatives to completed courses. Prerequisites must be
satisfied by the provided roster; unknown external course references remain
unmet. For the one catalog course with a corequisite, that corequisite must
already be completed. Concurrent enrollment needs later schedule-aware validation.
Term-specific results require offered course and section records. Cancelled
sections are excluded, TBA does not reduce scores, and seat counts are unavailable.

The output suppresses repeated titles, returns only positive-relevance candidates,
and may contain fewer than `top_k` courses when there are too few eligible matches.
Titles duplicated under different catalog IDs are not treated as formal transfer
equivalencies. Each result includes course ID/title, catalog units, description,
score, component scores, matching terms, explanation, prerequisite/corequisite
status, offered terms, section IDs, and whether any meetings are TBA. Exclusion
counts and warnings explain relevant limitations. Scores are relative relevance,
not probabilities, predicted grades, or guaranteed degree applicability.

`selected_course_ids` lists the returned course IDs as a convenience. A future
frontend should submit only the student's clicked subset for scheduling. The
existing scheduler currently accepts free-text interests and constructs its own
candidate pool; wiring a fixed selected subset into it is future integration work.

## Synthetic fixtures and reproducibility

Run `python -m scripts.generate_samples` to recreate fixtures with seed 42.

- `dataset/samples/interest_records.json` has metadata (`schema_version`,
  `synthetic`, `random_seed`, `purpose`) and 100 records. Each record contains
  `synthetic: true` and a valid `profile`. Profiles use existing student/program
  IDs, a seeded choice among 12 catalog-supported interest bundles, and empty
  experience. Every fifth profile has no interests, yielding 20 fallback cases.
- `dataset/samples/profiles/*.json` contains six directly usable profiles:
  AI engineering, product management, cybersecurity, policy analytics, financial
  analytics, and no stated interests. These use deliberate scenarios rather than
  random choices so behavior can be inspected consistently.
- `dataset/samples/documents/*_resume.txt` and `*_transcript.txt` contain six
  document pairs, marked synthetic. Workplaces and the university are fictional;
  external courses do not claim CMU prerequisite equivalencies.
- `dataset/samples/manifest.json` links each scenario to the profile and document
  paths relative to `dataset/`. `interest_taxonomy.json` mirrors the UI taxonomy.

These are development examples, not authentic student records or relevance
labels. Generation does not edit the original six CSVs. The evaluation script
saves six full recommendation responses in `artifacts/examples/` and a scenario
summary in `artifacts/evaluation.json`.

## Verification and remaining limitations

Tests cover all roster students' recommendation eligibility, prerequisite boolean
logic, career-sensitive rankings, experience effects, missing-interest fallback,
credit independence, persistence and stale-data rejection, document parsing and
invalid-file handling, and the upload-to-recommendation HTTP flow.

Synthetic scenarios check that the pipeline works and respects constraints. They
do not establish real recommendation quality. Before comparing models, collect
student/advisor relevance judgments, hold out students and their feedback for
evaluation, and measure ranking quality against a simple baseline. Enrollment
history alone is not an unbiased relevance label.

The original 621 credit discrepancies still need reconciliation for degree
progress. The model deliberately excludes credit amounts and GPA, and it does
not evaluate graduation. Generated course descriptions are provisional; the
catalog and provided completion identities are otherwise taken as inputs. There
is no production authentication, verified transfer/waiver workflow, OCR, feedback
store, capacity check, or fixed-selection scheduler integration in this version.
