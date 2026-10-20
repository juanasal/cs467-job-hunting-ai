# Data Contract

## Purpose

This document defines the shared MVP data fields used across the Job Hunting AI Web Tool. The goal is to keep the frontend, backend, database, job-ingestion pipeline, and matching engine aligned on the same field names, types, and meanings.

This contract covers only the fields needed for the MVP.

## MVP Assumptions

- Resume upload is not included.
- Work history is represented by a simple experience level.
- Education is represented by a simple education level.
- Skills are stored as a simple list.
- Application tracking is limited to `saved`, `dismissed`, and `applied`.
- External job data may be incomplete.
- Missing external values should use `null` rather than invented values.
- Dates and timestamps should use ISO-style formats.
- Match scores use a `0–100` scale.

---

# 1. User Account

Stores basic account information needed for authentication.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `user_id` | integer | Yes | Positive integer | Internal unique user identifier |
| `email` | string | Yes | Valid email address | User login email |
| `password_hash` | string | Yes | Hashed value | Securely stored password hash |
| `created_at` | datetime | Yes | ISO 8601 | Account creation timestamp |

### Example

```json
{
  "user_id": 1,
  "email": "user@example.com",
  "created_at": "2026-10-19T18:30:00Z"
}
```

Passwords must never be returned through the API.

---

# 2. User Profile

Stores the user information used by the matching engine.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `user_id` | integer | Yes | Existing user ID | Links profile to account |
| `skills` | array of strings | Yes | Example: `["Python", "SQL"]` | User's technical or professional skills |
| `education_level` | string | Yes | `high_school`, `associate`, `bachelor`, `master`, `doctorate`, `other` | Highest relevant education level |
| `experience_level` | string | Yes | `entry`, `mid`, `senior` | Simplified professional experience level |

### Example

```json
{
  "user_id": 1,
  "skills": [
    "Python",
    "SQL",
    "React"
  ],
  "education_level": "bachelor",
  "experience_level": "entry"
}
```

---

# 3. Search Preferences

Stores the user's current job-search criteria.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `user_id` | integer | Yes | Existing user ID | Owner of the preferences |
| `job_titles` | array of strings | Yes | Example: `["Software Engineer"]` | Desired job titles |
| `locations` | array of strings | Yes | Example: `["Portland, OR"]` | Preferred job locations |
| `workplace_type` | array of strings | Yes | `remote`, `hybrid`, `onsite` | Acceptable workplace arrangements |
| `salary_min` | number or null | No | Annual salary | Minimum desired salary |
| `salary_max` | number or null | No | Annual salary | Maximum desired salary, if applicable |
| `salary_currency` | string | Yes | `USD` for MVP | Salary currency |
| `result_count` | integer | Yes | Positive integer | Number of recommendations requested |

### Example

```json
{
  "user_id": 1,
  "job_titles": [
    "Software Engineer",
    "Data Engineer"
  ],
  "locations": [
    "Portland, OR",
    "Seattle, WA"
  ],
  "workplace_type": [
    "remote",
    "hybrid"
  ],
  "salary_min": 80000,
  "salary_max": null,
  "salary_currency": "USD",
  "result_count": 20
}
```

A `null` salary value means the user did not specify that limit.

---

# 4. Job Posting

Stores a standardized job listing retrieved from an external source such as Adzuna.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `job_id` | integer | Yes | Positive integer | Internal unique job identifier |
| `external_job_id` | string | Yes | Source-provided identifier | Job ID from Adzuna or another source |
| `source` | string | Yes | Example: `adzuna` | Source of the listing |
| `title` | string | Yes | — | Job title |
| `company` | string or null | No | — | Employer name |
| `location` | string or null | No | — | Job location |
| `workplace_type` | string | Yes | `remote`, `hybrid`, `onsite`, `unknown` | Workplace arrangement |
| `salary_min` | number or null | No | Annual salary | Minimum listed salary |
| `salary_max` | number or null | No | Annual salary | Maximum listed salary |
| `salary_currency` | string or null | No | Example: `USD` | Salary currency |
| `description` | string | Yes | — | Full or available job description |
| `date_posted` | date or null | No | `YYYY-MM-DD` | Original posting date |
| `job_url` | string | Yes | Valid URL | Link to original listing |
| `retrieved_at` | datetime | Yes | ISO 8601 | When the application retrieved the listing |

### Example

```json
{
  "job_id": 1001,
  "external_job_id": "ADZ-123456",
  "source": "adzuna",
  "title": "Junior Software Engineer",
  "company": "Example Corp",
  "location": "Portland, OR",
  "workplace_type": "hybrid",
  "salary_min": 75000,
  "salary_max": 90000,
  "salary_currency": "USD",
  "description": "We are seeking a software engineer with Python and SQL experience.",
  "date_posted": "2026-10-18",
  "job_url": "https://example.com/jobs/123456",
  "retrieved_at": "2026-10-19T18:30:00Z"
}
```

If an external source does not provide a field such as salary or location, that field should be stored as `null`.

If workplace type cannot be determined, use:

```text
unknown
```

---

# 5. Match Result

Stores the result of comparing a user profile and preferences with a job posting.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `user_id` | integer | Yes | Existing user ID | User receiving the recommendation |
| `job_id` | integer | Yes | Existing job ID | Job being evaluated |
| `match_score` | number | Yes | `0–100` | Overall relevance score |
| `matched_skills` | array of strings | Yes | — | User skills that align with the posting |
| `match_explanation` | string | Yes | — | Short explanation of why the job matches |
| `created_at` | datetime | Yes | ISO 8601 | When the score was generated |

### Example

```json
{
  "user_id": 1,
  "job_id": 1001,
  "match_score": 86,
  "matched_skills": [
    "Python",
    "SQL"
  ],
  "match_explanation": "Strong skill alignment and the position matches the user's preferred experience level and location.",
  "created_at": "2026-10-19T18:35:00Z"
}
```

### Match Score Convention

- `0` = no meaningful match
- `100` = strongest possible match

The exact scoring algorithm may change during development, but the API should continue returning scores on the same `0–100` scale.

---

# 6. Job Tracking

Stores the user's interaction with a job posting.

| Field | Type | Required | Allowed Values / Format | Description |
|---|---|---:|---|---|
| `user_id` | integer | Yes | Existing user ID | User tracking the job |
| `job_id` | integer | Yes | Existing job ID | Tracked job |
| `status` | string | Yes | `saved`, `dismissed`, `applied` | Current tracking status |
| `updated_at` | datetime | Yes | ISO 8601 | Most recent status change |

### Example

```json
{
  "user_id": 1,
  "job_id": 1001,
  "status": "saved",
  "updated_at": "2026-10-19T18:40:00Z"
}
```

Only one current tracking status should exist for each user/job combination.

---

# Shared Conventions

## IDs

Internal database records should use unique numeric IDs such as:

```text
user_id
job_id
```

External job IDs should be stored separately so they are not confused with internal database identifiers.

## Dates

Dates:

```text
YYYY-MM-DD
```

Example:

```text
2026-10-19
```

Timestamps should use ISO 8601.

Example:

```text
2026-10-19T18:30:00Z
```

## Missing Values

Use `null` when optional information is unknown or unavailable.

Example:

```json
{
  "salary_min": null,
  "salary_max": null
}
```

Do not use values such as:

```text
"N/A"
"Unknown"
0
""
```

unless the field specifically defines one of those values.

## Workplace Type

Use only:

```text
remote
hybrid
onsite
unknown
```

`unknown` should primarily be used for external job postings where the source does not provide enough information.

## Salary

For the MVP:

- Salaries are treated as annual amounts.
- Currency should be stored separately.
- User search preferences use `USD`.
- Missing salary information should use `null`.

Example:

```json
{
  "salary_min": 80000,
  "salary_max": 100000,
  "salary_currency": "USD"
}
```

## Arrays

Fields such as skills, job titles, and locations may contain multiple values.

Example:

```json
{
  "skills": [
    "Python",
    "SQL",
    "React"
  ]
}
```

---

# MVP Entity Relationships

```text
User Account
    |
    +-- User Profile
    |
    +-- Search Preferences
    |
    +-- Match Results ---- Job Posting
    |
    +-- Job Tracking ---- Job Posting
```

The job-ingestion pipeline creates standardized `Job Posting` records.

The matching engine combines:

```text
User Profile
+ Search Preferences
+ Job Posting
```

to generate:

```text
Match Result
```

The frontend uses these records to display recommendations and allow users to save, dismiss, or mark jobs as applied.

---

# JH-002 Completion Criteria

JH-002 is complete when:

- The team reviews and agrees on these entities and fields.
- Frontend, backend, job-pipeline, and matching work use the same field names.
- Required and optional fields are understood.
- Missing external job data has a defined representation.
- Salary, date, workplace type, and match-score conventions are agreed upon.
- Any changes to this contract are documented here before dependent components are changed.
