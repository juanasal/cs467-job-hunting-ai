# Backend (FastAPI)

The backend API for the Job Hunting AI Web Tool. Requires Python 3.11+ (tested with 3.13).

## Setup

Run these from the `backend/` folder:

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Then edit `backend/.env` with your values. **Never commit `.env`.**

## Settings

Settings are read from `backend/.env`. Variables already set in your shell take priority over the file.

| Name | Required | Description |
| --- | --- | --- |
| `DB_HOST` | Yes | MySQL host for the application |
| `DB_PORT` | Yes | MySQL port (whole number, e.g. `3306`) |
| `DB_NAME` | Yes | Application database name |
| `DB_USER` | Yes | Application database user |
| `DB_PASSWORD` | Yes | Application database password |
| `DB_SSL_CA` | For Aiven | Path to the server's CA certificate (`ca.pem` from the Aiven console). Turns on SSL. |
| `TEST_DB_*` | For DB tests | Separate test database used by database integration tests and `tests/test_job_repository.py` (see [Run the tests](#run-the-tests)) |
| `FRONTEND_ORIGINS` | No | Comma-separated frontend origins trusted by CORS and Origin validation. Defaults to `http://localhost:3000`. For local Vite use, add the exact origin printed by Vite, usually `http://localhost:5173`. |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | For Adzuna client | Adzuna API credentials |

The server requires valid `DB_*` settings at startup. Authentication routes also use these application database settings. `TEST_DB_*` settings are separate and are only used by database integration tests.

The error names a missing or invalid setting but never shows its value.
The server will not start if a required setting is missing or invalid. The error names the setting but never shows its value.

## Adzuna job client

Adzuna is the external job-search API used to retrieve job listings for the application.

- `app/adzuna_client.py` fetches job listings from Adzuna and supports search parameters, pagination, page limits, and request timeouts.
- `tests/test_adzuna_client.py` tests the client using saved and simulated responses, so the tests do not require live API calls or Adzuna credentials.
- HTTP/network failures raise `AdzunaRequestError` without exposing credentials. Malformed JSON or invalid result shapes also raise `AdzunaRequestError`; a valid response must contain a `results` list of job objects (an empty list is allowed). A later-page failure stops pagination and raises rather than returning partial results.

Run the Adzuna client tests from the `backend/` directory:

```bash
python -m pytest tests/test_adzuna_client.py
```

More details about the Adzuna API and our findings are documented in [`documentation/ADZUNA_RESEARCH.md`](../documentation/ADZUNA_RESEARCH.md).

## Adzuna job normalization

`app/job_normalizer.py` converts raw Adzuna job listings into the project's shared job-data format before they are saved to the database.

The normalizer:
- validates required fields and skips unusable records;
- retains salary bounds only with verified annual units and currency;
- validates job URLs and retrieval timestamps;
- normalizes posting dates and predicted salary values;
- conservatively infers `remote`, `hybrid`, or `onsite` when the listing provides clear evidence, and otherwise uses `unknown`.

The returned record does not include `job_id` because that value is generated when the job is inserted into the database.

Run the normalizer tests from the `backend/` directory:

```bash
python -m pytest tests/test_job_normalizer.py
```

## Job matching and recommendations

`app/job_requirements.py` extracts qualifications from job descriptions.
`app/job_matching.py` scores prepared requirements using `related-v1` by default.
Pass `method_version="exact-v1"` to select the exact-match baseline.
`app/match_evaluation.py` evaluates saved preferences and exposes
`recommend_jobs(profile, jobs, preferences)` for ranked recommendations with
evidence-based explanations. It accepts normalized, persisted job records and
applies the saved result limit after sorting.
See [usage, rules, and comparison results](../documentation/JOB_MATCHING.md).
Run `python -m pytest tests/test_job_requirements.py tests/test_job_matching.py tests/test_match_evaluation.py -q` from `backend/`.

## Database setup

The SQL scripts that create the tables and example data are in [`db/`](db/README.md). That README explains how to apply them and how to add new migration scripts.

Apply database migrations in numerical order. JH-028 adds `002_add_jobs_first_seen_at.sql`, which tracks the retrieval timestamp of the first stored observation of a job.

## Database helpers

`app/db.py` handles connections so features don't repeat that code.

- In a route, add a parameter typed `DbConnection`. Each request gets its own connection and transaction: changes are saved if the route finishes, undone if it raises, and the connection is always closed.
- Outside a request (scripts, the job pipeline), use `with transaction(get_settings()) as conn:`. It behaves the same way.
- Run SQL with `fetch_one`, `fetch_all`, or `execute`. Pass user-entered values as `params` with `%s` placeholders, **never** by building the SQL string yourself:

```python
from app.db import DbConnection, fetch_one

@app.get("/jobs/{job_id}")
def read_job(job_id: int, conn: DbConnection):
    return fetch_one(conn, "SELECT * FROM jobs WHERE job_id = %s", (job_id,))
```

Use `DbConnection` rather than `Depends(get_db)`. It makes FastAPI save changes before sending the response, so a failed save returns an error instead of a false success.

## Job repository

`app/job_repository.py` provides `upsert_job(conn, job)` to save normalized job postings without creating duplicates.

Jobs are identified by the combination of `source` and `external_job_id`. New jobs are inserted, while existing jobs are updated when newer data is retrieved.

The repository preserves the existing `job_id` and `first_seen_at` values. Older imports do not overwrite newer job details or retrieval timestamps.

Use `upsert_job()` inside a database transaction:

```python
from app.config import get_settings
from app.db import transaction
from app.job_repository import upsert_job

with transaction(get_settings()) as conn:
    job_id = upsert_job(conn, normalized_job)
```

Here, `normalized_job` is the dictionary returned by the job normalizer.

The transaction commits when the block completes successfully. If an error occurs, the transaction rolls back, preserving previously stored data.

Run the job repository tests from the `backend/` directory:

```bash
python -m pytest tests/test_job_repository.py -v
```

These tests cover inserting new jobs, updating existing jobs, preventing duplicates, handling older imports, timestamp validation, and database failures.

## Job tracking API

`app/tracking.py` lets the signed-in user save, dismiss, or mark a job as applied. All routes require login, and the user always comes from the session cookie, not from the request. `PUT` and `DELETE` also need the `Origin` and `X-CSRF-Token` headers (see [`documentation/AUTHENTICATION_LAYOUT.md`](../documentation/AUTHENTICATION_LAYOUT.md)).

| Route | Body | Result |
| --- | --- | --- |
| `GET /api/tracking?status=saved` | — | `{"tracking": [...]}`: the user's tracked jobs, newest first. `status` is optional. |
| `PUT /api/tracking/{job_id}` | `{"status": "saved"}`, `"dismissed"`, or `"applied"` | The tracking record (`user_id`, `job_id`, `status`, `updated_at`). Use this both to set a status and to change it. |
| `DELETE /api/tracking/{job_id}` | — | `204`. Undoes tracking so the job is untracked again. |

- Each user has at most one status per job (`job_tracking`'s primary key is `user_id` + `job_id`). Repeating the same action leaves that one row unchanged, and choosing a new status replaces the old one.
- Unknown job IDs return `404`. Invalid IDs or statuses, or an extra field like `user_id` in the body, return `422`. Undoing a job the user hasn't tracked returns `404`.
- `applied` only records what the user says they did. The app does not submit job applications.

**Dismissed jobs and the feed.** The recommendations feed excludes jobs the signed-in user has dismissed. Saved and applied jobs remain candidates for ranking when they pass the job activity and preference checks. The feed filters dismissals with this SQL:

```sql
AND NOT EXISTS (
    SELECT 1 FROM job_tracking t
    WHERE t.user_id = %s AND t.job_id = j.job_id AND t.status = 'dismissed'
)
```

Users can still see their dismissed jobs with `GET /api/tracking?status=dismissed`. Undoing (`DELETE`) or choosing another status puts the job back in the feed.

Run the tracking tests (they need the `TEST_DB_*` settings, see below) from the `backend/` directory:

```bash
python -m pytest tests/test_tracking.py -v
```

## Recommendations and job details API

`app/recommendations.py` ranks stored jobs for the signed-in user. Both routes require login and use the session cookie to select the user. A `user_id` in the request is ignored.

The feed loads the user's saved skills, education, experience, and search preferences from MySQL. It reads active jobs from any import source, including manual imports, and excludes jobs the user dismissed. The existing matcher extracts requirements, evaluates preferences, scores qualification fit (including related skills), and explains each result. Changes to saved matching inputs and stored jobs take effect on the next request.

| Route | Result |
| --- | --- |
| `GET /api/recommendations` | `{"recommendations": [{"job": {...}, "match": {...}}, ...]}`, best match first |
| `GET /api/jobs/{job_id}` | `{"job": {...}, "match": {...}}`, with a current match for a scorable, eligible active job or `null` when no match is available. When current matching inputs are unavailable or the job is inactive, details can return the user's previously saved match. |

`job` has the [Job Posting](../documentation/DATA_CONTRACT.md#4-job-posting) fields and `match` has the [Match Result](../documentation/DATA_CONTRACT.md#5-match-result) fields:

```json
{
  "recommendations": [
    {
      "job": {
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
        "salary_is_predicted": false,
        "description": "We are seeking a software engineer with Python and SQL experience.",
        "date_posted": "2026-10-18",
        "job_url": "https://example.com/jobs/123456",
        "retrieved_at": "2026-10-19T18:30:00Z",
        "first_seen_at": "2026-10-19T18:30:00Z",
        "is_active": true
      },
      "match": {
        "user_id": 1,
        "job_id": 1001,
        "match_score": 80,
        "matched_skills": ["Python", "SQL"],
        "match_explanation": "Direct skill matches include Python, SQL. ...",
        "created_at": "2026-10-19T18:35:00Z"
      }
    }
  ]
}
```

Rules:

- **Order:** highest `match_score` first; ties go to the lower `job_id` (the same rule as `recommend_jobs`).
- **Preferences.** The saved `result_count` applies after ranking. Strict location, workplace, and salary mismatches exclude a job. Soft mismatches and unverified values appear in the explanation. Saved titles guide explicit collection.
- **Tracking.** Dismissed jobs are excluded from the feed. Saved and applied jobs remain eligible subject to job activity, preferences, and the result limit. Job details still work for a dismissed job. See the [Job tracking API](#job-tracking-api).
- **Inactive jobs** (`is_active = false`) are left out of the feed. Job details still returns them, with `is_active: false`, so saved and applied jobs can still be opened. Nothing marks jobs inactive automatically yet (see `db/README.md`).
- **Evaluation time.** For current matches, `created_at` is the UTC evaluation time. The feed recomputes matches on each request and does not write match rows. It scans the eligible stored pool before applying the result limit.
- **Insufficient profile or preferences.** The feed returns `200` with `{"recommendations": []}` when the user has no saved profile, no saved skills, no saved search preferences, or no saved job titles.
- **No eligible jobs.** An empty job table, excluded jobs, or jobs without usable matching data return the same empty response.
- **Pending ingestion.** The feed immediately returns matches from committed jobs, or the same empty response when none are eligible. This MVP has no ingestion status in the response.
- **External source or ingestion failure.** The explicit `run_saved_search` caller receives the failure. Source failures happen before job writes, and failed writes roll back. The feed continues to use previously committed jobs or returns the same empty response. A failure reading MySQL uses the standard `500` error response.
- **Collection limits.** Dashboard requests make zero Adzuna requests and start no ingestion. Explicit saved searches retain the existing limits of 10 queries, five pages per query, and 100 collected results. The Adzuna client uses a 10-second HTTP timeout setting and makes no automatic retries.
- **Errors:** an unknown job ID returns `404` (`"Job not found."`), an invalid ID (`0`, `abc`) returns `422`, and requests without a valid session return `401`, all in the standard [error format](#error-format).

Run the tests (they need the `TEST_DB_*` settings, see below) from the `backend/` directory:

```bash
python -m pytest tests/test_recommendations.py -v
```

## Run the server

```bash
uvicorn app.main:app --reload
```

- Health check: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) → `{"status": "ok"}` (does not check the database)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

## Run the tests

Run all commands below from `backend/` using Bash or Zsh. On Windows, use a WSL Bash terminal with Docker Desktop integration enabled. Database tests create and change records, so use a separate local test database, never the shared or production database.

### First-time setup

**1. Prepare Python.** Install Python 3.11+ (CI uses 3.13), then create and activate a virtual environment and install the backend dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

If `.venv` already exists, activate it and install the requirements without recreating it. Dependency installation requires network access.

**2. Start Docker.** Install Docker Desktop for [Mac](https://docs.docker.com/desktop/setup/install/mac-install/), [Windows](https://docs.docker.com/desktop/setup/install/windows-install/), or [Linux](https://docs.docker.com/desktop/setup/install/linux/) if needed. Open it and wait for the engine to start. Linux users can also use Docker Engine. Verify that the engine is available:

```bash
docker info
```

**3. Create an isolated MySQL database.** This downloads the MySQL image if needed and publishes MySQL on local port `3307`. The credentials below are for this local test database only. If the named container already exists, follow [Subsequent runs](#subsequent-runs) instead.
docker run --rm hello-world
```

If `docker` is not found, finish installation and reopen your terminal. If it cannot connect to the Docker daemon, start Docker Desktop (or the Docker Engine service on Linux) and retry. The `hello-world` command downloads a small image and prints a success message.

### Run the database integration tests

Complete the Python setup above and activate your virtual environment first. The commands below use Bash or Zsh (macOS/Linux; on Windows use a WSL Bash terminal with Docker Desktop integration enabled). Run them from `backend/`.

Start a throwaway MySQL instance in Docker, apply the migrations in the order shown below, and set the test settings in `backend/.env` or your shell. The password below is only for this local container:

```bash
docker run -d --name jh-test-mysql -p 127.0.0.1:3307:3306 \
  -e MYSQL_ROOT_PASSWORD=local_root_pw -e MYSQL_DATABASE=job_hunting_ai_test \
  -e MYSQL_USER=jh_test -e MYSQL_PASSWORD=local_test_pw mysql:8.4

```

Check readiness with this command; repeat it until the output includes `mysqld is alive`:

```bash
docker exec jh-test-mysql mysqladmin ping -h 127.0.0.1 -uroot -plocal_root_pw
```

Confirm the host port before configuring the tests:

```bash
docker port jh-test-mysql
```

Expect `3306/tcp -> 127.0.0.1:3307`. If the mapping differs or is missing, see [Troubleshooting](#troubleshooting).

**4. Apply migrations once to the new, empty database.** Run them in order, stopping if any command fails:

```bash
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/001_create_tables.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/002_add_jobs_first_seen_at.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/003_add_match_results_recalculation_flag.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/003_create_user_sessions.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/004_add_strict_preferences.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/005_add_jobs_is_active.sql
```

Migration `003_add_match_results_recalculation_flag.sql` is introduced by JH-017; these instructions assume that change has been merged. After pulling changes, also apply any later migrations present in `db/migrations/`, in numerical order. Do not reapply migrations already run against this database. No seed data is required for the tests.

**5. Configure the test session.** Export these settings in the terminal where you will run pytest:

```bash
export TEST_DB_HOST=127.0.0.1
export TEST_DB_PORT=3307
export TEST_DB_NAME=job_hunting_ai_test
export TEST_DB_USER=jh_test
export TEST_DB_PASSWORD=local_test_pw
export TEST_DB_SSL_CA=

# App startup requires valid settings even though integration tests use TEST_DB_*.
# These placeholders keep the application database separate from the test database.
export DB_HOST=127.0.0.1
export DB_PORT=3307
export DB_NAME=unused_app_db
export DB_USER=unused
export DB_PASSWORD=unused
export DB_SSL_CA=
export APP_ENV=development
export FRONTEND_ORIGINS=http://localhost:3000,http://localhost:5173
```

These exports affect only this shell and its child processes; they override values in `.env` without editing the file. Use a separate terminal for running the application with its normal settings. If you chose another host port, update `TEST_DB_PORT` to match it.

**6. Run the tests.** Run the full suite, including database integration tests:

```bash
python -m pytest -q -rs
```

Or select individual test files using the same environment:

```bash
# Authentication integration tests
python -m pytest tests/test_auth.py -q -rs

# Account isolation integration tests
python -m pytest tests/test_access_control.py -q -rs

# Database helpers and job persistence
python -m pytest tests/test_db.py tests/test_job_repository.py -q -rs

# Adzuna client and normalization tests (no database needed)
python -m pytest tests/test_adzuna_client.py tests/test_job_normalizer.py -q
```

To select another test file, replace the path after `pytest` with its path under `tests/`. The `-rs` option explains skipped tests. A passing run with database tests skipped does not verify database behavior.

### Subsequent runs

Open Docker Desktop and, from `backend/`, activate the existing Python environment and start the existing container:

```bash
source .venv/bin/activate
docker start jh-test-mysql
docker exec jh-test-mysql mysqladmin ping -h 127.0.0.1 -uroot -plocal_root_pw
```

Repeat the readiness command until MySQL reports `mysqld is alive`. If dependencies have changed, run `python -m pip install -r requirements.txt`. Apply only new migrations added since your last run, using the same `docker exec -i ... < db/migrations/...` pattern from first-time setup.

In a new terminal session, repeat the exports from step 5, then run the suite or one of the individual-file commands above:

```bash
python -m pytest -q -rs
```

Do not recreate the container or rerun the initial migrations for each test run. When finished, you can stop MySQL without deleting its data:

```bash
docker stop jh-test-mysql
```

### Troubleshooting

**Container name already in use:** Inspect existing containers, including stopped ones:

```bash
docker ps -a --filter name=jh-test-mysql
```

If this is your existing test container, use `docker start jh-test-mysql`, then check readiness and its port mapping. Starting a container preserves its original credentials and port configuration.

**Port already allocated:** Identify running containers using the port:

```bash
docker ps --filter publish=3307 --format 'table {{.Names}}\t{{.Ports}}'
```

If it is a container you can stop, stop it by name before starting the test container. Otherwise create a separate test container with a different name and host port:

```bash
docker run -d --name jh-test-mysql-3308 -p 127.0.0.1:3308:3306 -e MYSQL_ROOT_PASSWORD=local_root_pw -e MYSQL_DATABASE=job_hunting_ai_test -e MYSQL_USER=jh_test -e MYSQL_PASSWORD=local_test_pw mysql:8.4
```

Use `jh-test-mysql-3308` in every readiness, migration, start, stop, and port command for that container. Apply all migrations to its new database and set `export TEST_DB_PORT=3308` before testing. This preserves the original container and its data.

**No output from `docker port jh-test-mysql`:** The container has no published host port. MySQL can respond to `docker exec` while remaining inaccessible to Python on your host. Starting it again does not add a port mapping. Create a separate container using the `3308` command above, then follow the new-database setup for it.

**Table or column already exists:** A migration may already have been applied. Do not rerun all migrations. Inspect the schema to determine which changes are already present:

```bash
docker exec jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test -e "SHOW TABLES; SHOW COLUMNS FROM jobs;"
```

The `003_create_user_sessions.sql` migration creates `user_sessions`, and `002_add_jobs_first_seen_at.sql` adds `jobs.first_seen_at`. Compare the schema with each migration and apply only missing changes. If uncertain, create a separate fresh test container to preserve existing data.

**`No module named fastapi` (or another dependency):** Activate the virtual environment and install the requirements with its Python:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**`No module named python`:** The command contains a duplicated `python -m`. Use `python -m pytest -q -rs` exactly once.

**Database tests skipped:** Run `python -m pytest -q -rs` to see the reason. Export all `TEST_DB_*` settings from step 5 in the same terminal before testing. Without test database configuration, integration tests intentionally skip. Keep `DB_NAME` different from `TEST_DB_NAME`; the tests reject settings that point at the application database.

**Connection refused or startup settings errors:** Check that Docker is running, MySQL is ready, and `docker port` matches `TEST_DB_PORT`. Repeat the step 5 exports if application startup reports missing `DB_*` settings. The MySQL password-on-command-line warning is expected for these local commands and does not itself indicate failure.
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/003_create_user_sessions.sql

TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3307 TEST_DB_NAME=job_hunting_ai_test \
  TEST_DB_USER=jh_test TEST_DB_PASSWORD=local_test_pw python -m pytest -q
```

This runs the full backend test suite, including database integration tests when the separate MySQL test database is configured. Without the `TEST_DB_*` settings, database integration tests are skipped. Check the pytest output to confirm that the integration tests ran rather than being skipped.

Stop it with `docker stop jh-test-mysql` and start it again later with `docker start jh-test-mysql`. On subsequent runs, start Docker Desktop and the existing container, check readiness, and rerun the test command; do not recreate the container or reapply the initial migration. If the container name is already in use, use `docker start` instead of `docker run`. If port `3307` is occupied, choose another host port in `-p` and use that same port for `TEST_DB_PORT`. Never point `TEST_DB_*` at the shared or production database.

## Browse the local database with DBeaver

[DBeaver Community](https://dbeaver.io/download/) is a free desktop app for browsing tables and running SQL. Install it separately from VS Code; the MySQL server stays in Docker.

1. Download the installer for your operating system. On Mac, choose Apple silicon or Intel to match your chip, open the downloaded disk image, and drag DBeaver into Applications. On Windows or Linux, follow the [installation instructions](https://dbeaver.com/docs/dbeaver/Installation/) for your download.
2. Complete [First-time setup](#first-time-setup) above, including the database migrations. Keep Docker Desktop and your test container running. For an existing container, follow [Subsequent runs](#subsequent-runs).
3. Open DBeaver and select **Database → New Database Connection**, choose **MySQL**, and click **Next**. Enter:

| Setting | Value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `3307` |
| Database | `job_hunting_ai_test` |
| Username | `jh_test` |
| Password | `local_test_pw` |

Use your chosen host port if you changed `3307` in the Docker command. These credentials belong to the local test container.

4. Click **Test Connection**. If prompted, allow DBeaver to download the MySQL driver (requires internet access). Once the connection succeeds, click **Finish**. See DBeaver's [connection guide](https://dbeaver.com/docs/dbeaver/Create-Connection/) for more details.
5. In **Database Navigator**, expand the connection, then `job_hunting_ai_test` → **Tables**. Right-click a table and choose **View Data → All Rows** to inspect it. Open **SQL Editor → New SQL Script** on the connection to run queries such as:

```sql
SELECT * FROM users;
SELECT * FROM user_profiles;
```

Empty tables are expected after the integration tests, which clean up their test records. To browse made-up example records, run this once from `backend/`, then refresh the table data in DBeaver:

```bash
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/seed/dev_seed.sql
```

You will need to refresh the database/tables in order to see the seeded data. If the connection is refused, check `docker ps --filter name=jh-test-mysql` and the MySQL readiness command above. If you get **Public Key Retrieval is not allowed**, edit the connection, open **Driver properties**, and set `allowPublicKeyRetrieval` to `true`, then test again. Use this setting only for this local Docker connection; configure verified SSL for a remote database (see DBeaver's [SSL configuration guide](https://dbeaver.com/docs/dbeaver/SSL-Configuration/)).

The suite includes application startup with isolated fake environment settings, API error/validation handling, and Adzuna timeout, HTTP failure, malformed response, and pagination coverage. GitHub Actions runs the suite on Python 3.13; see the [CI guide](../documentation/CI_GUIDE.md) and [testing guide](../documentation/TESTING_GUIDE.md).

## Error format

All error responses use the same JSON shape:

```json
{"error": {"status": 404, "message": "Not Found"}}
```

Request validation errors (422) also include a `details` list with the location and reason for each problem. Unexpected server errors return a generic `500` message so internal details aren't exposed.
## AI use

The FastAPI starter app (JH-004: `app/main.py`, `app/config.py`, `tests/test_main.py`, and the setup, settings, server, test, and error-format sections of this README) was generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/3RvCU2Xy81gspyqaBzijSs](https://claude.ai/artifact/3RvCU2Xy81gspyqaBzijSs) documents the GenAI interaction that led to my code.

The database helpers (JH-006: `app/db.py`, the `DB_SSL_CA` setting in `app/config.py`, `tests/test_db.py`, and the database helpers and test database sections of this README) were generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/WMYqeJ8Qys4vLCKxaAGtpN](https://claude.ai/artifact/WMYqeJ8Qys4vLCKxaAGtpN) documents the GenAI interaction that led to my code.

The access control tests (JH-011: `tests/test_access_control.py`, the `TEST_DB_*` settings in `.github/workflows/ci.yml`, and the related updates to `documentation/AUTHENTICATION_TESTING.md`, `documentation/CI_GUIDE.md`, and `documentation/TESTING_GUIDE.md`) were generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/5b1fkct6Vcvo2VJVTtxanX](https://claude.ai/artifact/5b1fkct6Vcvo2VJVTtxanX) documents the GenAI interaction that led to my code.

The registration tests (JH-009: the registration tests in `tests/test_auth.py` and the related updates to `documentation/AUTHENTICATION_TESTING.md`) were generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/HTwKKJGpPc4Pj9i6zh3rrX](https://claude.ai/artifact/HTwKKJGpPc4Pj9i6zh3rrX) documents the GenAI interaction that led to my code.

The recommendations and job details API (JH-041: `app/recommendations.py`, the router registration in `app/main.py`, `tests/test_recommendations.py`, `db/migrations/005_add_jobs_is_active.sql` and its step in `.github/workflows/ci.yml`, the recommendations and job details API section of this README, and the related updates to `db/README.md`, `documentation/DATA_CONTRACT.md`, and `documentation/TESTING_GUIDE.md`) was generated with the help of Claude (Claude Code). This transcript [https://claude.ai/artifact/EXzzqUxUhQVS5W6WbbnsxM](https://claude.ai/artifact/EXzzqUxUhQVS5W6WbbnsxM) documents the GenAI interaction that led to my code.
