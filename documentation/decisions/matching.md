# Job matching: proposed design and evaluation examples

This document gives the team a starting point for building and evaluating job matching.
The proposal has two parts: remove jobs that violate a user's strict preferences, then
score the remaining jobs by skills, education, and experience. A later version gives
partial credit for a small set of related skills.

The examples describe our judgments about fit. A qualification score of 80 means strong
alignment with visible qualifications under these rules; it does **not** mean an 80%
chance of being hired.

**Status:** design proposal for team review. The repository already defines the input
fields and a 0–100 score scale. The filtering policies, weights, thresholds, and
related-skill rules below are proposals. This document originally added no algorithm.

**JH-034 implementation update (2026-11-13):** The requester approved adopting the
qualification-scoring rules, including unspecified priorities, normalization, duplicate
handling, final rounding, and qualification-fit threshold, as `exact-v1`. See the
[implemented baseline](../JOB_MATCHING.md) for its interface and tests. Preference
filtering, related-skill credit, and public diagnostics remain separate proposals;
this update does not approve or implement those policies.

## Section index

| Section | Summary | TL;DR |
| --- | --- | --- |
| [Purpose and available inputs](#purpose-and-available-inputs) | Describes the profile, preference, job, and result fields, along with Adzuna data limitations. | What matching uses and what the source data cannot establish. |
| [Hard filters](#hard-filters) | Explains strict and soft preferences, salary comparisons, and handling of unknown or incomplete inputs. | Known strict-preference violations exclude jobs; unknowns stay unverified. |
| [Baseline scoring rules](#baseline-scoring-rules) | Defines exact matching, component calculations, missing evidence, rounding, and score explanations. | Skills earn up to 80 points; education and experience earn 10 each. |
| [Related-skill method](#related-skill-method) | Introduces a directed skill lookup table, partial credit, duplicate prevention, and limitations. | Three one-way skill relationships earn partial credit. |
| [Fictional evaluation cases](#fictional-evaluation-cases) | Provides fictional inputs, expected eligibility and fit, reasons, and pass/fail checks. | Thirty-one cases cover both methods and input validation. |
| [How the team can use these examples](#how-the-team-can-use-these-examples) | Explains how later extraction, scoring, ranking, and evaluation work can share the same cases. | Reuse the cases to build, rank, and compare matching methods. |
| [Questions for team review](#questions-for-team-review) | Lists proposed policies, contract gaps, and source-access questions requiring team decisions. | Policy choices and missing prerequisites still need agreement. |
| [Appendix: implementation reference](#appendix-implementation-reference) | Specifies test records, extracted requirements, result diagnostics, and documentation acceptance criteria. | Reproducible test inputs, evidence formats, and validation details. |


## Purpose and available inputs

The [data contract](../DATA_CONTRACT.md) defines the matching inputs:

| Record | Field | Data type | Example | Notes |
| --- | --- | --- | --- | --- |
| Profile | `user_id` | Integer | `1` |  |
| Profile | `skills` | Array of strings | `["Python", "SQL"]` |  |
| Profile | `education_level` | String | `"bachelor"` | Allowed: `high_school`, `associate`, `bachelor`, `master`, `doctorate`, `other`. |
| Profile | `experience_level` | String | `"mid"` | Allowed: `entry`, `mid`, `senior`. |
| Search preferences | `user_id` | Integer | `1` |  |
| Search preferences | `job_titles` | Array of strings | `["Software Engineer"]` |  |
| Search preferences | `locations` | Array of strings | `["Portland, OR"]` |  |
| Search preferences | `workplace_type` | Array of strings | `["remote", "hybrid"]` | Allowed values: `remote`, `hybrid`, `onsite`. |
| Search preferences | `salary_min` | Number or `null` | `80000` |  |
| Search preferences | `salary_max` | Number or `null` | `null` |  |
| Search preferences | `salary_currency` | String | `"USD"` | `USD` for the MVP. |
| Search preferences | `result_count` | Integer | `20` | Must be positive. |
| Job | `job_id` | Integer | `1001` |  |
| Job | `title` | String | `"Software Engineer"` |  |
| Job | `description` | String | `"Required: Python; SQL."` |  |
| Job | `location` | String or `null` | `"Portland, OR"` |  |
| Job | `workplace_type` | String | `"hybrid"` | Allowed: `remote`, `hybrid`, `onsite`, `unknown`. |
| Job | `salary_min` | Number or `null` | `90000` |  |
| Job | `salary_max` | Number or `null` | `110000` |  |
| Job | `salary_currency` | String or `null` | `"USD"` |  |
| Job | `salary_is_predicted` | Boolean or `null` | `false` |  |
| Match result | `user_id` | Integer | `1` |  |
| Match result | `job_id` | Integer | `1001` |  |
| Match result | `match_score` | Number | `80` |  |
| Match result | `matched_skills` | Array of strings | `["Python", "SQL"]` |  |
| Match result | `match_explanation` | String | `"Python and SQL match the listed skills."` |  |
| Match result | `created_at` | Datetime | `"2026-11-10T18:00:00Z"` |  |

The profile and preferences share a positive integer `user_id`; jobs have a positive
integer `job_id`. IDs, company names, and posting/retrieval dates earn no points. Source
IDs, URLs, and timestamps provide traceability. `job_titles` guides job retrieval, and
`result_count` limits the final list; neither affects this score. The contract has no
structured job qualifications, so those must come from the available description.

### What the source data can tell us

The [Adzuna research](../ADZUNA_RESEARCH.md) found shortened descriptions, varying
location detail, predicted salaries, and no structured workplace field. The
[normalizer](../../backend/README.md#adzuna-job-normalization) infers workplace type
only from clear evidence. For example, “remote sensing” does not establish remote work.
Contract time/type and coordinates observed in the research are outside this MVP
matching design.

These limits matter: a qualification missing from a snippet may still be required by the
employer. A country-only location cannot establish a city match. A predicted salary is
not an employer's offer. Matching should show these uncertainties.

The research also records unresolved questions about continued academic use, storage,
attribution, and account limits. Those need confirmation before live evaluation or
continued collection. These fictional examples need no API access. The design assumes
neither access to full descriptions nor permission to scrape them. Source URLs and
required attribution remain relevant to later displays.

No earlier matching algorithm decision was found in repository Markdown. The contract's
example score of 86 illustrates the output format; it does not define the scoring
formula.

### Three separate results

The proposed numeric **qualification score** measures skills, education, and experience
only. “Good” and “weak” describe qualification fit, not overall suitability. A 100 can
coexist with an unknown salary or incompatible soft preferences.

**Preference compatibility** is assessed separately for location, workplace, and salary:
compatible, incompatible, unverified, or not constrained. **Inclusion** means a
validated record has no known strict violation. Invalid input is rejected before either
outcome is assigned. These distinctions should remain visible in explanations,
especially when good qualification fit has unverified preferences.

The existing API field remains `match_score`; “qualification score” describes the
proposed formula, not a field rename. The contract calls that field overall relevance,
so the team should reconcile that wording before adopting this design. Compatibility
statuses and component diagnostics are proposed evaluation concepts, not additions to
the established API contract.

## Hard filters

A **strict preference** is a must-have: a known violation excludes the job before
scoring. A **soft preference** does not exclude it. In this first proposal, soft
mismatches appear in the explanation but do not change the score. Qualifications improve
the score; even a missing required qualification is not an automatic exclusion, given
the limitations of snippets and requirement extraction.

The current contract does not distinguish strict and soft preferences. This design
proposes an explicit choice for location, workplace, and salary, with all three soft by
default. The examples choose strict preferences unless stated otherwise. The team must
agree how to represent those choices before implementation.

### Known violations and unknown information

| Situation | Proposed result |
| --- | --- |
| Physical-attendance job outside a strict location preference | Exclude when the attendance location is known and comparable. |
| Remote job with a different posting city | Posting city alone does not establish worker eligibility; mark geography unverified. |
| Explicit remote worker restriction incompatible with every preferred location | Exclude if location is strict; otherwise report the incompatibility. |
| Known workplace type outside the strict acceptable list | Exclude. |
| Reliable salary bounds establish a strict violation | Exclude, even if only one job endpoint is known. |
| Unknown location or workplace type | Include, but mark the preference unverified. |
| Insufficient salary bounds, predicted salary, or incomparable units/currency | Include, but mark salary unverified. |
| Known mismatch with a soft preference | Include and explain the mismatch; no score adjustment. |

This policy favors keeping potentially useful jobs when information is missing. Its
consequence is that an included job may still need verification, even for a strict
preference. “Included” means no known strict violation, not that every preference has
been confirmed.

Location comparison uses Unicode NFKC normalization, case folding, trimming, and
collapsed whitespace. Identically spelled city/state values are comparable. Country-only
locations, alternate spellings without an agreed equivalence, and ambiguous regions
remain unverified. There is no distance or geocoding model.

For `onsite` and `hybrid`, a known posting location is treated as the attendance
location unless the description contradicts it; contradictory evidence remains
unverified. For `remote`, posting location is not worker eligibility, even when it
happens to match a preferred city. For `unknown` workplace type, a listed city alone
cannot establish attendance or remote eligibility; location stays unverified unless
explicit evidence resolves it.

Proposed restriction extraction recognizes only explicit, simple statements such as
“Workers must reside in Seattle, WA,” retaining that exact text. A restriction is
compatible if it explicitly permits at least one preferred location, and incompatible if
it clearly rules out all of them. Ambiguous or broad restrictions without an agreed
geographic mapping remain unverified. `locations` represents acceptable work locations,
not a new claim about the user's residence. This extraction output is separate from the
job contract, which has no worker-eligibility field. Remote never implies permission to
work anywhere.

### Salary ranges

Salary comparison uses annual USD amounts with reliable unit provenance,
`salary_is_predicted: false`, and matching currency. A missing prediction flag,
predicted values, unknown units, or incompatible currency means unverified before
comparing numbers. Known bounds must be nonnegative; two known endpoints must be
ordered. Negative or reversed intervals are validation errors.

Let `Umin`/`Umax` be the user's limits and `Jmin`/`Jmax` the job's known endpoints. A
null user bound is unconstrained, while a null job endpoint is unknown. Apply this table
from top to bottom after validating the available values:

| Evidence | Salary compatibility | Strict-filter consequence |
| --- | --- | --- |
| Both user limits are `null` | Not constrained | No salary exclusion. |
| Salary is not reliable/comparable | Unverified | Include with a warning. |
| Known `Jmax < Umin`, or known `Jmin > Umax` | Confirmed violation | Exclude; the other job endpoint is unnecessary. |
| Both job bounds known and neither violation holds | Confirmed overlap | Include. Equality at a boundary counts as overlap. |
| Only `Jmin` known, no user maximum, and `Jmin >= Umin` | Confirmed compatibility with the minimum-only preference | Include; every salary at or above that bound meets the minimum. |
| Only `Jmax` known, no user minimum, and `Jmax <= Umax` | Confirmed compatibility with the maximum-only preference | Include. |
| All other incomplete-bound situations | Insufficient information | Include as unverified, not confirmed compatible. |

Comparisons involving a null user bound are omitted. For example, a known maximum of
$79,999 violates an $80,000 minimum even if the job minimum is unknown. A known minimum
of $96,000 violates a $95,000 maximum even if the job maximum is unknown. But a known
maximum of $100,000 with no minimum does not establish that the job range reaches
$80,000: compatibility is unverified.

Overlap means an acceptable offer is possible, not guaranteed. The MVP performs no
currency or hourly-to-annual conversion. Raw hourly values must be withheld from annual
fields, leaving salary endpoints `null` until a conversion policy exists. The contract
has no explicit salary-unit provenance field yet.

### Incomplete records

Validation comes first. Missing required profile fields, empty skills/title/ location
lists under the database guidance, and a missing required job description are rejected
inputs. They receive no inclusion/exclusion decision, qualification fit label, or
recommendation score, and cannot create a stored recommendation. MATCH-012 and MATCH-014
test this validation boundary.

A valid but limited profile still earns only supported qualification points. For
example, `education_level: "other"` is valid but cannot establish an ordered degree
minimum. A shortened description is also valid: its visible requirements can be scored,
with a partial-description warning.

Optional defensive scorer behavior can be checked separately: a hand-authored empty
skill set with known education and experience would yield 20, and an empty requirement
set yields 0. These arithmetic checks do not turn rejected records into included
recommendations and require no diagnostic adapter.

Excluded jobs have exclusion reasons rather than recommendation scores. An included
score of zero means weak or insufficiently evidenced qualification fit; it does not mean
excluded.

## Baseline scoring rules

The proposed baseline gives most weight to skills because they provide the most specific
comparison available in the MVP. Education and experience provide smaller contributions
because the profile records only broad levels.

| Component | Maximum points | Calculation |
| --- | ---: | --- |
| Skills | 80 | Weighted proportion of job skill targets matched by the profile. |
| Education | 10 | Full credit for a met required minimum; half for preferred; one quarter for unspecified priority. |
| Experience | 10 | Full credit for a met required minimum; half for preferred; one quarter for unspecified priority. |

### Skills

An exact match earns 1 credit for a skill target; an unmatched target earns 0. Required
targets have weight 2, preferred targets weight 1, and applicant qualifications with
unspecified priority weight 0.5:

```text
S = sum(target weight × credit) / sum(target weight)
skill points = 80 × S
```

For example, matching required UI development but missing preferred SQL gives `S = 2/3`,
or 53⅓ skill points. Extra profile skills do not reduce the score.

Exact matching normalizes Unicode with NFKC, ignores case, trims outer whitespace, and
collapses internal whitespace. Punctuation is preserved, so `C`, `C++`, and `C#` differ.
There is no substring matching, stemming, or implicit aliasing: `React.js` and `React`
need an approved alias to count as equal.

Each normalized profile skill and job target counts once. If a target appears multiple
times, the highest explicit priority wins (`required > preferred > unspecified`), with
all supporting text spans retained. Duplicate skills cannot increase the score.

### Education and experience

Education follows `high_school < associate < bachelor < master < doctorate`. Experience
follows `entry < mid < senior`. Meeting or exceeding a known required minimum gives 10
points; meeting a preferred minimum gives 5. A known shortfall gives zero. `other`
education and ambiguous or missing values are unevaluable, also worth zero, with an
explanation that the evidence is missing.

An unspecified-priority education or experience minimum earns 2.5 points when met (`E`
or `X` = 0.25). There is at most one unambiguous minimum for each category. The design
does not infer a degree field or convert years of work into an experience level.

### Missing evidence, totals, and explanations

A component with insufficient evidence contributes zero. The remaining weights stay
fixed. If a snippet mentions only Python and the user knows Python, the score is 80, not
100. This makes sparse records score conservatively, although missing requirements can
also make the visible skill targets easier to satisfy. Scores must therefore be shown
with an indication of the available evidence.

```text
raw score = 80 × S + 10 × E + 10 × X
final score = floor(raw score + 0.5)
```

Here `E` and `X` are 1 for a met required minimum, 0.5 for a met preferred minimum, 0.25
for a met unspecified-priority minimum, and 0 otherwise. If no skill targets are
evaluable, `S = 0`. Rounding happens only once, at the end. A rounded score of **60 or
more is good qualification fit**; a lower score is **weak qualification fit**. Neither
label verifies preference compatibility. These weights and the threshold are design
judgments for team review.

Each result should explain its skill, education, and experience points; the text
supporting the requirements; exact versus related matches; and unknown information or
preference mismatches. “Insufficient evidence” is more accurate than “unqualified” when
nothing can be evaluated.

`matched_skills` contains the original profile skill strings that earned credit,
deduplicated by normalized name, retaining the first spelling, and sorted by normalized
name. A related match identifies both the profile skill and the job target in
`match_explanation`. Included results sort by rounded score descending, then numeric
`job_id` ascending to resolve ties consistently.


### Limits when comparing different jobs

This formula measures coverage of **visible** qualifications. A user matching a job's
sole visible required skill can score higher than the same user matching four of five
required skills in another job. MATCH-030 and MATCH-031 hold education and experience
evidence constant: their scores are 100 and 84 respectively. The first ranks higher
despite its thinner evidence. This is a known limitation, not a claim that the first job
is more suitable.

The component-coverage indicator only says which categories have usable inputs. Both
examples have 100% component coverage. It measures neither description completeness nor
recommendation confidence and does not solve omitted requirements.

## Related-skill method

A small, reviewed lookup table can extend exact matching without an LLM, external
service, or new dependency. The proposal starts with three one-way relationships:

| Profile skill | Job target | Credit | Rationale |
| --- | --- | ---: | --- |
| React | UI development | 0.75 | Building React interfaces provides relevant UI experience, even if the job never says “React.” |
| PostgreSQL | SQL | 0.75 | PostgreSQL experience supports SQL work without establishing every SQL dialect. |
| TypeScript | JavaScript | 0.75 | TypeScript builds on JavaScript, but use does not establish all JavaScript runtime or ecosystem skills. |

Exact matches still earn 1. All unlisted relationships earn zero, including Python → UI
development, React → SQL, and Excel → C#. Relationships do not reverse automatically: UI
development alone does not establish React experience. They also do not chain through
intermediate skills.

For each job target, the highest available credit wins. Exact UI development plus React
still earns only 1 for a UI development target, not 1.75. One profile skill may support
several distinct targets, but each target counts only once. When several source skills
provide the same credit, normalized alphabetical order chooses the one used in the
explanation. The other scoring rules remain unchanged.

The table is deliberately small and explainable. Its limitations are equally important:
someone may have shallow framework experience, transfer between skills varies, and
related credit is not proof that a required skill is met. These credit values and the
60-point threshold are proposed heuristics, not validated matching quality. The shared
0.75 credit remains a reviewable starting point; it was not selected as evidence that
these cases ought to cross “good.” Java → C# is unlisted and earns zero. JavaScript →
TypeScript is also unlisted: JavaScript knowledge alone does not establish TypeScript
type-system experience. Changes to the table should have a recorded version so results
can be compared over time.

## Fictional evaluation cases

### Shared example inputs

The examples use the following starting point. Each row changes only the values it
names. A replacement description supplies all of that job's qualification evidence;
requirements from the starting description do not carry over.

| Record | Starting values |
| --- | --- |
| Profile | `user_id: 1`, `skills: ["Python", "SQL"]`, `education_level: "bachelor"`, `experience_level: "mid"` |
| Preferences | `user_id: 1`, `job_titles: ["Software Engineer"]`, `locations: ["Portland, OR"]`, `workplace_type: ["hybrid"]`, `salary_min: 80000`, `salary_max: null`, `salary_currency: "USD"`, `result_count: 20` |
| Strict choices | Location, workplace, and salary are all strict. These are proposed choices outside the current contract. |
| Job | `title: "Software Engineer"`, `location: "Portland, OR"`, `workplace_type: "hybrid"`, `salary_min: 90000`, `salary_max: 110000`, `salary_currency: "USD"`, `salary_is_predicted: false` |
| Job description | `"Required: Python; SQL. Bachelor degree required. Mid experience required."` |

All examples are fictional and salaries are annual unless noted. **Baseline** means
exact matching; **related** means the same formula with related-skill credit. The scores
are expectations calculated from this proposal, not measured results. A case passes only
if its result, reason, and additional check all hold; otherwise it fails. “Good” and
“weak” in every row mean qualification fit only. B means baseline; R means related.
Preference compatibility is independent. Unless a row says otherwise, the shared
location, workplace, and salary are compatible. Excluded cases have neither a
recommendation fit label nor score; invalid cases have no matching decision at all.
Valid included cases may produce stored results; excluded or rejected cases must not.
Checks apply to both methods unless specified.

### Qualification matches

| Case | Profile, job, and preferences | Expected result and checks |
| --- | --- | --- |
| **MATCH-001** — Strong exact match and normalization | **Profile:** `skills: [" python ", "SQL", "PYTHON"]`; other profile defaults. **Job:** defaults. Preferences: defaults; strict defaults. | **included; Baseline good 100; Related good 100.** duplicate/case variations do not change two exact targets; education and experience meet minima. Check: S=1, E=1, X=1; skill points=80; duplicate Python earns no extra credit; total=100 in both methods. |
| **MATCH-002** — Unrelated qualifications | **Profile:** `skills: ["Excel"]`, `education_level: "high_school"`, `experience_level: "entry"`. **Job:** defaults. Preferences: defaults; strict defaults. | **included; Baseline weak 0; Related weak 0.** acceptable preferences but no qualification credit. Check: no exclusion; S=E=X=0; no matched skills; no Excel-to-Python/SQL edge. |
| **MATCH-003** — React supports UI without word overlap | **Profile:** `skills: ["React"]`; other profile defaults. **Job:** `title: "UI Engineer"`, `description: "Required: UI development."`. **Preferences:** defaults; strict defaults. | **included; Baseline weak 0; Related good 60.** no exact React target; directed related edge supplies partial UI credit. Check: B S=0; R S=0.75; E=X=0 (unknown requirements); R explanation names React → UI development and supporting text; no exact-match claim. |
| **MATCH-004** — PostgreSQL supports SQL | **Profile:** `skills: ["PostgreSQL"]`; other profile defaults. **Job:** `title: "SQL Developer"`, `description: "Required: SQL."`. **Preferences:** defaults; strict defaults. | **included; Baseline weak 0; Related good 60.** specific database experience transfers partially to SQL. Check: B S=0; R S=0.75; E=X=0; explanation identifies the directed edge. |
| **MATCH-005** — TypeScript supports JavaScript | **Profile:** `skills: ["TypeScript"]`; other profile defaults. **Job:** `title: "JavaScript Developer"`, `description: "Required: JavaScript."`. **Preferences:** defaults; strict defaults. | **included; Baseline weak 0; Related good 60.** proposed TypeScript-to-JavaScript relationship, not proof of all JavaScript skills. Check: B S=0; R S=0.75; E=X=0; matched profile skill is TypeScript, not invented JavaScript. |
| **MATCH-006** — Unrelated-skill negative control | **Profile:** `skills: ["Python"]`; other profile defaults. **Job:** `title: "UI Engineer"`, `description: "Required: UI development."`. **Preferences:** defaults; strict defaults. | **included; Baseline weak 0; Related weak 0.** Python alone earns no UI edge. Check: identical job requirements to MATCH-003; both S=0; R MATCH-003 ranks above this case. |

### Strict preferences and missing information

| Case | Profile, job, and preferences | Expected result and checks |
| --- | --- | --- |
| **MATCH-007** — Strict location violation | **Profile:** defaults. Job: `location: "Seattle, WA"`; remaining defaults. **Preferences:** defaults; strict defaults. | **excluded; Baseline/related fit and score not applicable.** known city outside the strict Portland preference. Check: location exclusion; no recommendation score, despite full qualification alignment. |
| **MATCH-008** — Strict workplace violation | **Profile:** defaults. Job: `workplace_type: "onsite"`; remaining defaults. **Preferences:** defaults; strict defaults. | **excluded; Baseline/related fit and score not applicable.** onsite is outside the strict hybrid list. Check: workplace exclusion; qualifications cannot restore inclusion. |
| **MATCH-009** — Strict salary violation | **Profile:** defaults. Job: `salary_min: 60000`, `salary_max: 79999`; remaining defaults. **Preferences:** defaults; strict defaults. | **excluded; Baseline/related fit and score not applicable.** entire known employer range is below 80000. Check: salary exclusion in both methods; do not compare only qualification points. |
| **MATCH-010** — Missing salary | **Profile:** defaults. Job: `salary_min: null`, `salary_max: null`, `salary_currency: null`, `salary_is_predicted: null`. **Preferences:** defaults; strict defaults. | **included; Baseline good 100; Related good 100.** **Salary unverified; location/workplace compatible.** Salary cannot be checked; observed qualifications still align. Check: `salary_unverified`; no claim salary meets 80000; no invented salary or salary penalty; explanation must not call this fully verified suitability. |
| **MATCH-011** — Unknown workplace and location | **Profile:** defaults. Job: `workplace_type: "unknown"`, `location: null`. **Preferences:** defaults; strict defaults. | **included; Baseline good 100; Related good 100.** **Location/workplace unverified; salary compatible.** Strict preferences have no known violations, but cannot be confirmed. Check: both `workplace_unverified` and `location_unverified`; never label the job confirmed hybrid, Portland, or fully verified suitability. |
| **MATCH-012** — Incomplete skill profile | **Profile:** `skills: []`; other defaults. **Job and preferences:** defaults. | **Validation rejected; B/R score, fit, and inclusion not applicable.** The database guidance requires nonempty skills. Check: validation reports the empty list; scoring is not invoked in the normal workflow; no recommendation is persisted. |
| **MATCH-013** — Shortened description | **Profile:** defaults. Job: `description: "Required: Python. Additional qualifications…"`. **Preferences:** defaults; strict defaults. | **included; Baseline good 80; Related good 80.** Python is visible; SQL, education, and experience requirements are unknown. Check: only one extracted target; S=1, E=X=0; `description_partial`; no default requirements inherited from the replaced description. |
| **MATCH-014** — Missing required description | **Profile and preferences:** defaults. **Job:** remove `description` entirely. | **Validation rejected; B/R score, fit, and inclusion not applicable.** Description is a required field. Check: ingestion skips/rejects the job; no extraction, recommendation scoring, or persistence occurs. |
| **MATCH-015** — Salary boundary overlap | **Profile:** defaults. Job: `salary_min: 70000`, `salary_max: 80000`. **Preferences:** defaults; strict defaults. | **included; Baseline good 100; Related good 100.** endpoint equals desired minimum; possible overlap is sufficient. Check: no salary exclusion; explain overlap without guaranteeing an 80000 offer. |

### Scoring boundaries and soft preferences

| Case | Profile, job, and preferences | Expected result and checks |
| --- | --- | --- |
| **MATCH-016** — Preferred targets and duplicate-credit prevention | **Profile:** `skills: ["React", "UI development", "UI development"]`; other defaults. **Job:** `description: "Required: UI development. Preferred: SQL. Bachelor degree required. Mid experience required."`. **Preferences:** defaults; strict defaults. | **included; Baseline good 73; Related good 73.** exact UI credit wins over related credit; preferred SQL is unmatched. Check: S=2/3, E=X=1; raw=220/3, rounded=73; R UI credit is 1, never 1.75; missing SQL reduces skill points but is not an exclusion. |
| **MATCH-017** — Directionality negative control | **Profile:** `skills: ["UI development"]`; other defaults. **Job:** `title: "React Developer"`, `description: "Required: React."`. **Preferences:** defaults; strict defaults. | **included; Baseline weak 0; Related weak 0.** reverse edge is not approved. Check: no UI development → React credit; S=E=X=0 in both versions. |
| **MATCH-018** — Incompatible currency | **Profile:** defaults. Job: `salary_min: 50000`, `salary_max: 60000`, `salary_currency: "EUR"`. **Preferences:** defaults; strict defaults. | **included; Baseline good 100; Related good 100.** numeric values cannot be compared as annual USD. Check: `salary_unverified`; no conversion, strict salary exclusion, or claim the USD minimum is met. |
| **MATCH-019** — Predicted low salary | **Profile:** defaults. Job: `salary_min: 60000`, `salary_max: 70000`, `salary_is_predicted: true`. **Preferences:** defaults; strict defaults. | **included; Baseline good 100; Related good 100.** predicted values cannot establish a strict violation. Check: `salary_unverified` and prediction disclosed; do not exclude or present values as employer-provided. |
| **MATCH-020** — Soft preferences | **Profile:** defaults. Job: `location: "Seattle, WA"`, `workplace_type: "onsite"`, `salary_min: 60000`, `salary_max: 70000`. **Preferences:** defaults, but `strict: {location: false, workplace: false, salary: false}`. | **included; Baseline good 100; Related good 100.** **Location, workplace, and salary incompatible (soft).** All known preference mismatches are soft; baseline awards qualification points only. Check: three mismatch warnings; no exclusions or preference points; explanation discloses preference mismatch despite good qualification fit; never label this fully compatible. |

### Remote eligibility and partial salaries

| Case | Profile, job, and preferences | Expected result and checks |
| --- | --- | --- |
| **MATCH-021** — Remote posting city is not worker eligibility | **Profile:** defaults. **Preferences:** `workplace_type: ["remote"]`; other preferences and strict choices unchanged. **Job:** `workplace_type: "remote"`, `location: "Seattle, WA"`; default description. | **Included; B/R good qualification fit 100.** Workplace and salary compatible; geographic eligibility unverified because there is no worker restriction evidence. Check: extract no worker restriction; `location_unverified`; no location exclusion or claim of work-from-anywhere permission. |
| **MATCH-022** — Explicit incompatible remote restriction | **Profile:** defaults. **Preferences:** `workplace_type: ["remote"]`; strict Portland location unchanged. **Job:** `workplace_type: "remote"`, `location: "Seattle, WA"`; append `"Workers must reside in Seattle, WA."` to the default description. | **Excluded; B/R recommendation score and fit not applicable.** Explicit residence restriction conflicts with the only acceptable work location. Check: retain that sentence as worker-restriction evidence; location incompatible; workplace/salary compatible; no persisted recommendation. |
| **MATCH-023** — Known maximum below minimum | **Profile and preferences:** defaults. **Job:** `salary_min: null`, `salary_max: 79999`; reliable annual USD, not predicted. | **Excluded; B/R recommendation score and fit not applicable.** The maximum alone proves salary incompatibility. Check: strict salary exclusion despite missing job minimum; no salary-unverified substitution. |
| **MATCH-024** — Known minimum above maximum | **Profile:** defaults. **Preferences:** `salary_max: 95000`; other defaults. **Job:** `salary_min: 96000`, `salary_max: null`; reliable annual USD, not predicted. | **Excluded; B/R recommendation score and fit not applicable.** The minimum alone proves salary incompatibility. Check: strict salary exclusion despite missing job maximum; no persisted recommendation. |
| **MATCH-025** — One bound cannot settle compatibility | **Profile and preferences:** defaults. **Job:** `salary_min: null`, `salary_max: 100000`; reliable annual USD, not predicted. | **Included; B/R good qualification fit 100.** Salary unverified; location/workplace compatible. The maximum neither proves a violation nor establishes overlap with the desired interval. Check: `salary_unverified`; no invented minimum or confirmed salary compatibility. |

### Qualification wording and sparse descriptions

In MATCH-026–029, the quoted sentence replaces the whole description. Education and
experience requirements are unknown, even though the profile retains its known levels.
MATCH-030–031 deliberately use the same profile and the same degree and experience
evidence to expose the cross-job comparison limitation.

| Case | Profile, job, and preferences | Expected result and checks |
| --- | --- | --- |
| **MATCH-026** — Explicit requirement | **Profile and preferences:** defaults. **Job:** `description: "Python is required."`. | **Included; B/R good qualification fit 80.** Preferences compatible; Python is an explicit required target. Check: extract Python/required with the full sentence as evidence; S=1, E=X=0; do not invent SQL. |
| **MATCH-027** — Explicit preference | **Profile and preferences:** defaults. **Job:** `description: "Python is preferred."`. | **Included; B/R good qualification fit 80.** Preferences compatible; Python is preferred, not required. Check: extract Python/preferred with the full sentence; denominator=1; S=1, E=X=0. A sole preferred target still gives full skill coverage. |
| **MATCH-028** — Employer technology | **Profile and preferences:** defaults. **Job:** `description: "Our team uses Python."`. | **Included; B/R weak qualification fit 0.** Preferences compatible; employer technology is not an applicant qualification. Check: extracted skills=[], education=null, experience=null; S=E=X=0; no matched skills; insufficient qualification evidence, not proven lack of ability. |
| **MATCH-029** — Unspecified applicant priority | **Profile and preferences:** defaults. **Job:** `description: "Applicants should have Python experience."`. | **Included; B/R good qualification fit 80.** Preferences compatible; an applicant qualification is visible, but required/preferred priority is unspecified. Check: extract Python/unspecified, retain the sentence and ambiguity; target weight=0.5; S=1, E=X=0; never relabel required. |
| **MATCH-030** — Sole visible skill | **Profile:** `skills: ["Python", "SQL", "Git", "Linux"]`; other profile and preference defaults. **Job:** `description: "Python is required. Bachelor degree required. Mid experience required."`. | **Included; B/R good qualification fit 100.** Preferences compatible; the profile covers the only visible skill and both level minima. Check: extract only required Python, bachelor, mid; S=1, E=X=1; component coverage=100%; do not interpret this as a complete description or high confidence. |
| **MATCH-031** — Four of five visible skills | **Profile:** same as MATCH-030; preferences default. **Job:** `description: "Required: Python; SQL; Git; Linux; Docker. Bachelor degree required. Mid experience required."`. | **Included; B/R good qualification fit 84.** Preferences compatible; four of five required skills match. Check: extract five distinct required skill targets, bachelor, mid; S=4/5, E=X=1; 64+10+10=84; component coverage=100%; rank below MATCH-030 despite more visible matching evidence. |

### Other useful boundary checks

The same examples also provide a few useful boundary checks:

- MATCH-018 with raw hourly pay: upstream withholds unconverted endpoints as
  `null`; expect included 100 with salary unverified. No silent multiplication.
- MATCH-009 with `salary_min: null`: still exclude because its known maximum
  is below the strict minimum. MATCH-023 makes this a distinct case.
- MATCH-015 with user `salary_max: 95000` and job range 96000–110000: exclude
  for strict salary maximum violation. With both user bounds null: include.
- MATCH-011 with `location: "United States"`: still location unverified.
- MATCH-016 with preferred bachelor and preferred mid instead: E=X=0.5;
  raw=190/3, rounded=63, good. With profile entry and high_school: E=X=0,
  rounded=53, weak; required shortfalls lower score, never filter.
- Replace MATCH-005 target with `C++`: no TypeScript relationship and no
  substring credit. Java → C# remains a zero-credit negative control.

## How the team can use these examples

The workflow starts with input validation, then separates four responsibilities. These
are conceptual interfaces. JH-034 now implements qualification scoring and explicit
requirement preparation as described in the [baseline guide](../JOB_MATCHING.md); the
other responsibilities remain future work. These interfaces do not change the API:

| Component | Inputs | Outputs |
| --- | --- | --- |
| Requirement extraction | A validated job description | Skill targets and education/experience minima, priorities, exact supporting text, and ambiguity/partial-description warnings. A separate proposed output holds explicit worker-location restrictions and their evidence. |
| Qualification scoring | Validated profile, extracted qualification targets, and method version | S/E/X, component points, rounded qualification score, matched profile skills, and contributing reasons. It does not decide preference compatibility. |
| Preference evaluation | Validated preferences, proposed strict choices, job location/workplace/salary, unit provenance, and extracted worker restrictions | Per-preference compatibility, evidence/warnings, and included or excluded with reasons. It does not award qualification points. |
| Recommendation assembly and ranking | Qualification results and preference decisions for valid records | Included results ordered by score then job ID, concise explanations that preserve incompatibility/uncertainty, and up to `result_count` results. Excluded and rejected records do not create persisted recommendations. |

Baseline scoring tests can supply hand-authored extracted requirements directly, so a
score failure can be separated from an extraction failure. Description-based tests
separately compare extracted targets, priorities, and evidence against the expectations
below. No diagnostic adapter is required for invalid records.

Once the baseline works, the related-skill method should improve MATCH-003 through
MATCH-005 while preserving exact matches and leaving the unrelated controls weak. The
same profiles, jobs, and expected outcomes can then compare both methods. The combined
workflow applies qualification weights and preference filters separately; ranking orders
included jobs and supplies their explanations. A later proposal that gives soft
preferences points will need its own reviewed expectations.

Ranking checks should use one profile across several jobs. With MATCH-001's profile, job
1001 scores 100 and job 1003 scores 0 in both methods. With MATCH-003's React profile,
jobs 1003 and 1006 each score 60 under the related method, above job 1005 (JavaScript
target) at 0. The UI jobs tie, so job 1003 comes first. For the profile shared by
MATCH-030–031, job 1030 ranks above job 1031, 100 versus 84, illustrating
sparse-description bias rather than more evidence.

Evaluation should report each case's inclusion, fit, score, missing-information
warnings, and failed checks for both methods. Expectations stay independent of
implementation results. A disagreement calls for investigation; changing the expectation
requires a documented team decision and a new version of the examples. These synthetic
cases support regression testing, not claims about real-world hiring accuracy or
fairness.

## Questions for team review

| Decision | Why it matters |
| --- | --- |
| Strict versus soft choices and unknown-inclusive filtering | The contract has no strictness fields. The proposed policy can include jobs with unverified must-haves; the team may prefer a separate verified-only option. |
| Salary overlap, maximum limits, and predicted pay | Overlap permits an offer below the user's minimum. Predicted ranges never exclude; reliable partial ranges can establish violations. Unit provenance also needs a representation. |
| Weights, threshold, and missing-evidence treatment | The proposed 80/10/10 split and 60-point threshold are judgments. Fixed weights can disadvantage incomplete descriptions; soft preferences currently earn no points. |
| Requirement extraction and normalization | Structured qualifications, unspecified-priority weights, worker-location restrictions, aliases, geographic equivalences, and years-to-level mappings need agreement. |
| Related-skill table | The direction and 0.75 credit for React, PostgreSQL, and TypeScript need agreement; no credit is validated proficiency. |
| Invalid inputs and output shape | The contract requires a description but generally says missing external values use `null`; normalization skips unusable jobs. Required list cardinalities are clearer in the database README than in the contract. Match results have no eligibility or component fields; their “overall relevance” description needs reconciliation with qualification-only scoring. |
| Adzuna access and permitted use | Continued academic access, storage/expiration, attribution, and account limits remain prerequisites for live evaluation. |

## Appendix: implementation reference

These details make the proposal reproducible without changing the existing data
contract. They are reference formats for later tests, not new persisted fields.

### Test records and strict choices

A case numbered N uses `job_id = 1000 + N`. Its other job fields are `external_job_id:
"fictional-NNN"`, `source: "fictional"`, `company: "Fictional Example NNN"`, `job_url:
"https://example.com/jobs/NNN"`, `date_posted: "2026-11-01"`, and `retrieved_at` and
`first_seen_at` both set to `"2026-11-10T18:00:00Z"`. NNN is the three-digit case
number.

The proposed test-only strictness representation is:

```json
{"strict": {"location": true, "workplace": true, "salary": true}}
```

Unknown optional fields retain the contract's `null` convention; unknown job workplace
type is `"unknown"`. The deliberately invalid missing description and empty skill list
cases test validation rejection, not included recommendations.

### Extracted requirements

A small proposed structure separates extracted evidence from source job fields:

```json
{
  "skills": [
    {"name": "Python", "priority": "required", "evidence": "Required: Python."}
  ],
  "education": {
    "minimum": "bachelor",
    "priority": "required",
    "evidence": "Bachelor degree required."
  },
  "experience": {
    "minimum": "mid",
    "priority": "required",
    "evidence": "Mid experience required."
  }
}
```

Unknown education or experience requirements use `null`; no supported skill targets use
`[]`. A “Required: A; B.” sentence supplies two required skill targets; “UI development”
is one phrase. Priorities are `required`, `preferred`, or `unspecified`; unmarked
qualifications are not silently required.

| Description evidence | Expected extraction | Scoring treatment |
| --- | --- | --- |
| “Python is required.” | Python, required | Target weight 2. |
| “Python is preferred.” | Python, preferred | Target weight 1. |
| “Applicants should have Python experience.” | Python, unspecified | Target weight 0.5; preserve the priority ambiguity. |
| “Our team uses Python.” | No applicant qualification | No target or skill points from this sentence. |

The lower unspecified weight is a conservative, implementable proposal. It does not
assert that the qualification is optional. For a sole skill target, weights cancel in
the coverage ratio, so required, preferred, and unspecified exact matches each earn 80
skill points. Priority affects relative contributions when multiple targets exist.
Unspecified-priority education and experience minima use 0.25 credit when met. Employer
technologies and descriptions of work alone do not establish applicant requirements.

Supporting text comes from the description, not the job title, company boilerplate, or
negated statements. Ambiguous alternatives such as “degree or equivalent experience,”
contradictory minima, and years without an agreed level mapping remain unevaluable and
are explained as such. Skills do not establish a degree, and missing information does
not establish a qualification failure.

### Expected extraction for the cases

Each listed target retains its exact supporting phrase from that case's description.
“Default” means required Python and SQL, required bachelor, and required mid, using the
shared description. A replacement description never inherits default targets. Missing
categories use `null`; no skill targets use `[]`. This table is the extraction
expectation; the case tables separately specify scoring, preference, validation, and
persistence outcomes.

| Cases | Expected qualification extraction | Additional evidence |
| --- | --- | --- |
| MATCH-001–002, 007–011, 015, 018–025 | Default qualifications. | MATCH-022 additionally extracts the Seattle-only worker restriction from its appended sentence. MATCH-021 extracts no worker restriction. |
| MATCH-003, 006 | Required UI development; education/experience unknown. | Exact “Required: UI development.” sentence. |
| MATCH-004 | Required SQL; education/experience unknown. | Exact “Required: SQL.” sentence. |
| MATCH-005 | Required JavaScript; education/experience unknown. | Exact “Required: JavaScript.” sentence. |
| MATCH-012, 014 | No workflow extraction expectation: validation rejects first. | No normal scoring or persistence. |
| MATCH-013 | Required Python only; education/experience unknown. | “Required: Python.” plus a partial-description warning. |
| MATCH-016 | Required UI development, preferred SQL, required bachelor and mid. | Corresponding sentences in the replacement description. |
| MATCH-017 | Required React; education/experience unknown. | Exact “Required: React.” sentence. |
| MATCH-026 | Required Python; education/experience unknown. | “Python is required.” |
| MATCH-027 | Preferred Python; education/experience unknown. | “Python is preferred.” |
| MATCH-028 | No qualification targets. | “Our team uses Python.” is context, not applicant evidence. |
| MATCH-029 | Unspecified-priority Python; education/experience unknown. | “Applicants should have Python experience.”; retain priority ambiguity. |
| MATCH-030 | Required Python, bachelor, and mid. | Corresponding sentences in its description. |
| MATCH-031 | Required Python, SQL, Git, Linux, Docker, bachelor, and mid. | Corresponding clauses in its description. |

### Result details for checking the calculation

Beyond the existing match-result fields, evaluation needs the method/policy version,
eligibility or validation errors, normalized targets, priorities and weights, supporting
text, source profile skills, per-target credits, and the three component totals. It also
records the raw total, rounded score, and uncertainty warnings. Exclusion reasons use
location, workplace, then salary order.

Proposed warning names are `location_unverified`, `workplace_unverified`,
`salary_unverified`, and `description_partial`. An evidence-coverage indicator is the
sum of component base weights with usable profile and job evidence, divided by 100. An
empty profile skill list has no usable skill evidence. Coverage is informational and
does not alter the score; it measures evaluable components, not description completeness
or recommendation confidence. The team still needs to agree how these details fit the
API and storage model.

### Documentation acceptance criteria

```gherkin
Feature: A shared matching design and reusable examples
  Scenario: The design is grounded in the repository
    Given the data contract and Adzuna research
    When a teammate reads the design
    Then the input fields, units, and limitations link to their sources
    And proposed rules are distinguishable from existing decisions

  Scenario: Examples can evaluate either method
    Given at least 12 distinct fictional pairs with stable IDs
    When their shared values and case-specific inputs are combined
    Then every case has either a validation rejection or an eligibility result and a reason
    And included cases have an expected qualification fit and score for each method
    And rejected records have no recommendation score or inclusion decision
    And every case has checks whose failure makes the case fail

  Scenario: Strict preferences and uncertain evidence are distinct
    Given examples of known violations and missing information
    When their expected results are reviewed
    Then known strict violations exclude regardless of qualifications
    And unknown information remains explicitly unverified
    And remote posting cities alone do not establish worker eligibility
    And reliable one-sided salary bounds can establish a strict violation

  Scenario: The calculations are reproducible
    Given the formula, rounding rule, and related-skill table
    When a teammate calculates the example scores
    Then the totals agree with the expected results
    And duplicate, unrelated, and reverse-direction skills earn no extra credit
    And unspecified applicant qualifications are not labeled required
    And employer technology statements produce no applicant targets
    And sparse-description comparisons retain their documented score limitation

  Scenario: The document is ready for team review
    Given the completed document
    When case completeness, arithmetic, and local links are checked
    Then those checks pass and unresolved choices are listed
    And no algorithm implementation or dependency has been added
```

### Documentation validation

The [testing guide](../TESTING_GUIDE.md#3-choose-tests-for-the-change) recommends review
and link checks for documentation-only changes. The configured [CI
checks](../CI_GUIDE.md#configured-checks) cover backend tests and frontend lint/build;
there is no configured Markdown-specific check. Validation for this rewrite covers all
31 case rows, expected results and checks, score arithmetic, local links and section
anchors, and whitespace. Application behavior is unchanged, so application tests are
unnecessary.

AI Use References:
- https://chatgpt.com/share/6af3645c-c6c4-83e8-8c7f-b885b516458a
- https://chatgpt.com/s/cx_6af36482c43481918fbe311a231ef610
