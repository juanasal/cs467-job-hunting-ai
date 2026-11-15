# Exact-match scoring baseline

`app.job_matching.score_job(profile, job, *, requirements)` is a pure backend
qualification calculation. It accepts shared profile/job dictionaries and explicit
`PreparedRequirements`, returning a dictionary. There are no network, database, HTTP,
clock, or AI dependencies.

## Decision and boundaries

The `exact-v1` baseline adopts the qualification rules in the
[matching design](decisions/matching.md), including unspecified priorities, with
preference filtering assigned to a separate layer. Filtering policy, related-skill
credit, and the public diagnostics schema remain proposals.
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

## Preparing structured requirements

Call `prepare_requirements(job, structured, warnings=())` with hand-authored requirements
from the available description. Each target needs `priority` (`required`, `preferred`,
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

Example (from `backend/`, using otherwise validated shared records):

```python
from app.job_matching import prepare_requirements, score_job

profile = {"user_id": 1, "skills": ["Python", "SQL"],
           "education_level": "bachelor", "experience_level": "mid"}
# job is a shared job record, including job_id=1001 and this description:
# "Required: Python. Additional qualifications…"
requirements = prepare_requirements(job, {
    "skills": [{"name": "Python", "priority": "required",
                "evidence": "Required: Python."}],
    "education": None,
    "experience": None,
}, warnings=["description_partial"])
result = score_job(profile, job, requirements=requirements)
# result["match_score"] == 80
# result["matched_skills"] == ["Python"]
# result["component_points"] == {"skills": 80.0, "education": 0.0, "experience": 0.0}
```

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

- Skills: 80 × matched weight / total weight; no targets yields zero. Exact matches
  earn full target credit. Required/preferred/unspecified weights are 2/1/0.5.
- Unicode NFKC, casefold, trim and collapse whitespace; punctuation stays distinct
  (`C`, `C++`, `C#`). No aliases, substrings, stemming, or related-skill credit.
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
python -m pytest tests/test_job_matching.py -q
python -m pytest -q
```

Tests use synthetic shared records and hand-authored requirements with independently
calculated scores, including the matching design’s strong/unrelated, partial-description,
and weighting examples. They test baseline expectations rather than future related-skill expectations.

This measures alignment with visible qualifications, not hiring probability or verified
proficiency. Exact matching misses related skills and spelling variants. Incomplete
source snippets omit qualifications; missing evidence earns zero and must not be called
proof of inability. Sparse requirements can also inflate visible skill coverage: one
matched target can outscore four of five matched targets. Component coverage does not
measure description completeness or confidence.

JH-035 remains responsible for extracting applicant requirements, priorities, supporting
spans, ambiguities, and partial-description warnings. JH-036 remains responsible for a
separately versioned related-skill method and its evaluation. Preference policy and its
supporting contract gaps, recommendation assembly, ranking, and public diagnostic output
remain separate work; this baseline resolves none of those proposals silently.
