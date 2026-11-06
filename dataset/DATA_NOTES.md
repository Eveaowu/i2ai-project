# Dataset assumptions and preparation

These updates were requested on November 6, 2026. The CSV column schemas and
record counts are preserved.

## Elective eligibility

For both AIM12 and AIM16, a course may count as an elective if:

- `courses.course_type` equals `Regular course`.
- Its `course_id` is not in the declared program's core requirements, identified
  by `program_requirements.program_id`, `core = 1`, and `req_course_id`.

Core membership is determined for the student's declared program. This is the
project's agreed eligibility assumption, not an independently verified catalog
policy. No additional elective approval table is required under this assumption.
The existing `ScheduleGenerator.candidates` method already restricts candidates
to regular courses and distinguishes core courses from electives. Prerequisites,
completed courses, and term availability remain separate recommendation filters.

## Missing course descriptions

Filled all 21 previously empty `description` cells in `courses.csv`, including
10 regular courses and 11 other course types. Each addition is a concise,
single-paragraph summary inferred from the course title and type. These are
AI-generated project descriptions, not official syllabi or verified statements
of specific assignments, prerequisites, teaching format, or learning outcomes.
Existing descriptions were preserved.

The generated descriptions belong to these course IDs:

| Course type | Course IDs |
| --- | --- |
| Regular course | 94-710, 94-722, 94-723, 94-728, 95-800, 95-802, 95-841, 95-867, 95-879, 95-895 |
| Independent Study | 94-400, 94-902, 94-903, 94-904, 94-905 |
| Internship | 94-899, 94-900, 94-901 |
| Residency | 95-861, 95-863 |
| Study Abroad | 94-050 |

Replace generated descriptions with official descriptions when available. Do not
treat these additions as observed student preferences or recommendation labels.

## TBA meeting times

For recommendation work, TBA meeting times may be treated as flexible and
arrangeable into continuous time slots. No fixed meeting time was invented or
written into `course_section.csv`. Allocating actual time slots is deferred to
future scheduling work. The existing scheduler remains unchanged; its current
TBA behavior does not allocate a concrete time slot and may report that conflicts
were not checked.

## Student-history term changes

Applied the following one-time mappings to the JSON history entries in
`student_data.csv`, in both `completed_courses` and `enrollment_history`:

| Original term | Updated term | Completed-course entries changed | Enrollment-history entries changed |
| --- | --- | ---: | ---: |
| S26 | S25 | 521 | 100 |
| M26 | M25 | 480 | 100 |
| S27 | S26 | 0 | 0 |

There were no S27 entries in either history field. Each mapping is applied once
to its original value, so an original S27 would become S26, not S25. The JSON
field name remains `term`; only its value changes. F26 entries, course offering
terms, program planning terms, credit amounts, grades, GPA, and other student
fields are unchanged. All 100 students retain their original history entry counts.

These edits shift specified historical dates; they do not validate attendance
against historical offerings. The offering tables do not cover S25 or M25.

## Remaining credit reconciliation

The earlier audit found 621 of 1,001 completed-course entries whose recorded
credits disagree with their course's fixed catalog units. These discrepancies
remain after the term changes. For example, S001 records 12 credits for 95-856,
where the catalog lists 6 units, and S002 records 12 credits for 95-871, where
the catalog lists 0 units.

Determine whether to use historical earned units or current catalog units as
the authoritative source. If the histories are synthetic and should follow the
current catalog, correct the course credit values and reconcile dependent credit
totals. If the histories represent actual records, preserve earned units and
document legitimate historical differences. Do not silently overwrite credits
or use inconsistent records as training or evaluation ground truth.
