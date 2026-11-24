# Job qualification scoring

The scorer compares a person's skills, education, and experience with the
qualifications listed in a job. It returns a score from 0 to 100 and explains which
qualifications matched, which did not, and where information was missing. Skills can
contribute up to 80 points; education and experience can each contribute up to 10.
The same inputs always produce the same result.

The caller supplies structured qualifications alongside the job record. The rule-based
extractor below can build those qualifications from the job's description. The scorer
matches normalized skill names exactly and can give partial credit for documented
one-way skill relationships.

The score describes how well the profile matches the available qualification evidence.
It is not a chance of being hired, and it does not check preferences such as salary,
location, or remote work. Missing information earns no points, but does not prove that
the person lacks a qualification.

`app.job_matching.score_job(profile, job, *, requirements, method_version="related-v1")` is a pure backend
qualification calculation. It accepts shared profile/job dictionaries and explicit
`PreparedRequirements`, returning a dictionary. There are no network, database, HTTP,
clock, or AI dependencies.

## Decision and boundaries

The `exact-v1` baseline adopts the qualification rules in the
[matching design](decisions/matching.md), including unspecified priorities.
JH-036 adds `related-v1`, the default method. Pass `method_version="exact-v1"`
to reproduce baseline scoring. Filtering policy and the public diagnostics schema
remain proposals.
The [shared contract](DATA_CONTRACT.md) is unchanged.

The module uses dictionaries consistently with the job normalizer and repository;
there is no shared profile/job Python model.
This module follows that dictionary convention. It checks IDs, nonempty profile skills,
profile enums, and a nonempty job description; callers must validate the remaining
shared-record fields upstream. Invalid scoring inputs raise `ValueError`, producing no
score. Missing required profile fields are invalid, rather than silently treated as a
valid incomplete profile. Valid `other` education is unevaluable.

A score makes no inclusion/exclusion decision. No preference points, filter, ranking,
persistence, endpoint, or frontend control is added. A zero score is qualification
alignment of zero; it never means a confirmed preference exclusion. Future assembly
must evaluate preferences separately and keep exclusions distinct from scores and
unknown compatibility. Until then results must not be presented as eligible or fully
compatible recommendations.

## Extracting requirements from job descriptions

Call `app.job_requirements.extract_requirements(job)` with a normalized job dictionary.
It reads `description` and returns `technical_skills`, `soft_skills`, their combined
`skills` list, scorable `education` and `experience` minima, and `warnings`. All targets
include their priority and an exact source sentence, clause, or bullet. `education_mentions` and
`experience_mentions` retain individual explicit minima when multiple statements occur.

```python
extracted = extract_requirements(job)
prepared = prepare_requirements(job, extracted, warnings=extracted["warnings"])
```

This preparation step requires a persisted job ID and a nonblank description. Extraction
also works on normalized jobs before persistence and returns empty targets for missing
or blank descriptions.

- Technical vocabulary covers Python, SQL, AWS, Docker, Git, Linux, Excel, Java,
  JavaScript, TypeScript, C++, C#, PostgreSQL, React, React.js, and UI development.
- Soft-skill vocabulary covers communication (including written and verbal communication),
  communication skills, teamwork, leadership, and problem solving.
- Education recognizes high school diploma, associate, bachelor and master degrees,
  and doctorate, doctoral degree or PhD. Experience recognizes explicit entry, mid,
  or senior experience. Numeric years have no agreed mapping to these levels.

The rules recognize simple lists, qualification headings, and phrases such as “must
have”, “required”, “preferred”, and “experience with”. An explicit priority suffix
before a semicolon closes that clause. A new heading or an
unrecognized plain-text line ends the preceding qualification section. Wording such as “should have”
has `unspecified` priority. Negation and alternatives can suppress a whole statement.
Ambiguous abbreviations such as `R` and `MS` are skipped. Conflicting level statements
leave the scorable minimum empty and produce a warning. The fixed vocabulary and simple
statement grammar can miss qualifications in complex sentences. An ending ellipsis
produces `description_partial`; an unmarked cutoff may go undetected. Extraction only
uses the visible text.

## Preparing structured requirements

Call `prepare_requirements(job, structured, warnings=())` with extracted or hand-authored
requirements from the available description. Each target needs `priority` (`required`, `preferred`,
`unspecified`) and `evidence` (one exact nonempty source span). Skills additionally need
`name`; education/experience need an allowed `minimum`. Supply `skills: []` and
`education: None` / `experience: None` when unknown or ambiguous. Optional omitted level
categories also mean unknown. Use warnings for ambiguities and partial descriptions;
warning detection is the caller's responsibility.

Preparation validates source spans, normalizes and deduplicates targets, and freezes
them together with the exact description and job ID. Scoring rejects a different ID or
changed description. This prevents stale requirements from being silently scored for a
different job. Other job fields earn no points. Matching a source span is only a
provenance check: the author must determine that it is an applicant qualification,
not employer technology, a negation, or ambiguous alternative. This is not a parser.
Ambiguous minima/years without an agreed level mapping must be withheld as `None`,
with a warning; `other` education minima remain unevaluable. Supporting spans from
duplicate skills are all retained, deduplicated and sorted.

## Complete example

This fictional example includes both shared records and the hand-authored requirements.
The job snippet names only Python. Although the person also knows SQL and has known
education and experience levels, those cannot earn points without corresponding job
requirements. The expected score is therefore 80: all 80 skill points and zero points
for education and experience.

The example can be run from `backend/` with the project dependencies installed:

```python
from app.job_matching import prepare_requirements, score_job

profile = {
    "user_id": 1,
    "skills": ["Python", "SQL"],
    "education_level": "bachelor",
    "experience_level": "mid",
}
job = {
    "job_id": 1001,
    "external_job_id": "fictional-001",
    "source": "fictional",
    "title": "Software Engineer",
    "company": "Example Company",
    "location": None,
    "workplace_type": "unknown",
    "salary_min": None,
    "salary_max": None,
    "salary_currency": None,
    "salary_is_predicted": None,
    "description": "Required: Python. Additional qualifications…",
    "date_posted": "2026-11-01",
    "job_url": "https://example.com/jobs/001",
    "retrieved_at": "2026-11-10T18:00:00Z",
    "first_seen_at": "2026-11-10T18:00:00Z",
}

requirements = prepare_requirements(job, {
    "skills": [{"name": "Python", "priority": "required",
                "evidence": "Required: Python."}],
    "education": None,
    "experience": None,
}, warnings=["description_partial"])
result = score_job(profile, job, requirements=requirements)
print(result["match_score"])
print(result["matched_skills"])
print(result["component_points"])
print(result["warnings"])
```

Expected output for those four fields:

```text
80
['Python']
{'skills': 80.0, 'education': 0.0, 'experience': 0.0}
['description_partial']
```

The full result also explains the exact Python match and the missing education and
experience requirements. The partial-description warning is supplied by the caller;
the scorer does not detect incomplete descriptions automatically.

The result includes contract fields `user_id`, `job_id`, `match_score`,
`matched_skills`, and `match_explanation`. The caller supplies `created_at` outside the
calculation if assembling a stored result. Internal diagnostics include `method_version`,
`qualification_fit`, normalized `skill_targets` with weights, evidence, source skills,
credits and statuses; education/experience comparisons; `component_points`, `raw_score`,
`component_coverage`, and sorted `warnings`. These diagnostics are not new public API or
database fields. Explanations give component contributions, matched/unmatched targets,
source evidence, level shortfalls versus insufficient evidence, warnings, and the fact
that preferences have not been evaluated. All ordering is stable. Inputs are unchanged.

## Implemented rules

- Skills: 80 × sum of (target weight × credit) / total target weight. With no
  targets the skill score is zero. Exact matches earn 1 in both methods.
  Required/preferred/unspecified weights are 2/1/0.5.
- Unicode NFKC, casefold, trim and collapse whitespace; punctuation stays distinct
  (`C`, `C++`, `C#`). Matching uses whole normalized names.
- `related-v1` gives 0.75 for React → UI development, PostgreSQL → SQL, and
  TypeScript → JavaScript. Java → C# earns zero per the matching design.
  Unlisted pairs earn zero. The lookup uses only direct edges from profile skills.
- The highest credit wins per target. Equal-credit sources are resolved by normalized
  alphabetical order. Each credited target's explanation names the source skill and
  job requirement and includes the job evidence.
- Count each normalized profile skill/target once. Highest target priority wins.
  Matched profile strings retain their first original spelling, sorted by normalized name.
- Education: high_school < associate < bachelor < master < doctorate. Experience:
  entry < mid < senior. Meeting/exceeding required/preferred/unspecified minima earns
  10/5/2.5 points. Known shortfall, unknown requirements, and unevaluable education earn
  zero. Weights never redistribute. No degree-field inference or years conversion.
- Use exact rational arithmetic internally; round only the final total with
  `floor(raw + 0.5)`. Diagnostic numbers are floats, with no effect on calculation.
  Scores >=60 receive the `good` qualification-fit label, otherwise `weak`.
- Component coverage is the fraction of base weights with evaluable inputs, including
  known shortfalls; it is informational and never changes the score.

## Validation and limitations

From `backend/` with dependencies installed:

```bash
python -m pytest tests/test_job_requirements.py tests/test_job_matching.py -q
python -m pytest -q
```

Tests compare both methods using the same synthetic profiles and extracted requirements.
The first seven cases each have one required skill target. The last case has required
PostgreSQL and Docker, with preferred SQL. All cases lack education and experience targets.

| Profile skills | Job skills | `exact-v1` | `related-v1` |
| --- | --- | ---: | ---: |
| React | UI development | 0 | 60 |
| PostgreSQL | SQL | 0 | 60 |
| TypeScript | JavaScript | 0 | 60 |
| Python | UI development | 0 | 0 |
| UI development | React | 0 | 0 |
| Java | C# | 0 | 0 |
| React, UI development | UI development | 80 | 80 |
| PostgreSQL | PostgreSQL, SQL, Docker | 32 | 44 |

The JH-036 validation run passed all 53 matching and requirement-extraction tests,
including the comparisons above.

This measures alignment with visible qualifications, not hiring probability or verified
proficiency. Exact matching misses related skills and spelling variants. Incomplete
source snippets omit qualifications; missing evidence earns zero and must not be called
proof of inability. Sparse requirements can also inflate visible skill coverage: one
matched target can outscore four of five matched targets. Component coverage does not
measure description completeness or confidence.

Preference policy, supporting contract gaps, recommendation assembly, ranking, and
public diagnostic output remain open.
