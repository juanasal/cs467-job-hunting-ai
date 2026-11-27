# JH-029 — Saved Search Job Collection

## Overview

This module connects saved user search preferences to the existing
Adzuna job collection, normalization, and database upsert components.

The implementation is in `app/saved_search_pipeline.py`.

## Workflow

1. Load the user's saved preferences from MySQL.
2. Build Adzuna queries using job titles and locations.
3. Fetch job listings from Adzuna.
4. Normalize each listing using `normalize_adzuna_job()`.
5. Remove duplicate jobs based on source and external job ID.
6. Save normalized jobs using `upsert_job()`.

The database repository preserves existing job IDs and prevents
duplicate job records.

## Supported Search Parameters

| Saved preference | Adzuna parameter | Behavior |
|---|---|---|
| job_titles | what | One query per title/location combination |
| locations | where | Optional; omitted when no location is saved |
| result_count | N/A | Limits the total number of jobs collected, up to 100. Each Adzuna request uses a fixed `results_per_page=20`. |

## Filters Not Sent to Adzuna

The following saved preferences are not currently translated
into Adzuna API parameters:

- workplace_type
- salary_min
- salary_max
- salary_currency

The local [matching stage](../documentation/JOB_MATCHING.md#ranking-and-explaining-recommendations)
uses these saved preferences and their strictness flags to evaluate eligibility
and explain compatibility. This collection module uses title and location to
build Adzuna queries.

## Query Limits

- Maximum 10 unique title/location queries per execution.
- Maximum 5 pages per query.
- Maximum 20 requested results per page.
- Maximum 100 normalized jobs collected per execution.
- Collection stops when the result limit is reached.
- Repeated title/location combinations are skipped.
- Duplicate jobs are removed before database upsert.
- Searches without job titles are rejected.
- Searches without locations omit the `where` parameter.

The limits are application-level safeguards, not Adzuna's
official API quotas.

Each explicit collection run gathers up to the saved `result_count`, capped at
100 jobs. The recommendation endpoint reads active jobs already committed in
MySQL, including jobs from earlier runs and manual imports. It applies the
saved `result_count` after filtering, scoring, and sorting that pool. The feed
can return fewer results when fewer candidates are usable or eligible.

## Error Handling

- Missing saved preferences produce `SavedSearchError`.
- Missing job titles produce `SavedSearchError`.
- Missing or blank Adzuna credentials produce `AdzunaConfigError`.
- Credentials rejected by Adzuna, or other failed Adzuna requests, produce `AdzunaRequestError`.
- Invalid or incomplete job records are skipped.
- Database failures trigger a transaction rollback.

Adzuna requests are completed before the database write
transaction begins.

## Usage

From backend application code:

```python
from app.saved_search_pipeline import run_saved_search

result = run_saved_search(user_id=1)
```

The user ID must come from an authenticated or otherwise
trusted backend context.

Adzuna credentials must be configured through the existing
environment variables:

- ADZUNA_APP_ID
- ADZUNA_APP_KEY

Saving search preferences does not automatically trigger job
collection. The pipeline runs only when backend code explicitly
calls `run_saved_search(user_id)`.

This module does not introduce a public API endpoint or
automatic scheduled collection. `run_saved_search()` returns collection
statistics. The backend ranker is a separate function that takes persisted job
records as input.

## Testing

Run from the `backend/` directory:

```bash
python -m pytest tests/test_saved_search_pipeline.py -v
python -m pytest tests/ -q
```

Tests use fake Adzuna responses and mocked database operations.
They do not require live Adzuna API requests.

## GenAI Attribution

ChatGPT (OpenAI) assisted with designing the query mapping,
collection pipeline, validation, tests, and documentation.
The implementation was reviewed and adapted for the CS467 project.
