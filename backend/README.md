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
| `DB_HOST` | Yes | MySQL host |
| `DB_PORT` | Yes | MySQL port (whole number, e.g. `3306`) |
| `DB_NAME` | Yes | Database name |
| `DB_USER` | Yes | Database user |
| `DB_PASSWORD` | Yes | Database password |
| `DB_SSL_CA` | For Aiven | Path to the server's CA certificate (`ca.pem` from the Aiven console). Turns on SSL. |
| `TEST_DB_*` | For DB tests | Separate test database used by `tests/test_db.py` and `tests/test_job_repository.py` (see [Run the tests](#run-the-tests)) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | For Adzuna client | Adzuna API credentials |

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
- converts salary values to numbers or `null`;
- validates job URLs and retrieval timestamps;
- normalizes posting dates and predicted salary values;
- conservatively infers `remote`, `hybrid`, or `onsite` when the listing provides clear evidence, and otherwise uses `unknown`.

The returned record does not include `job_id` because that value is generated when the job is inserted into the database.

Run the normalizer tests from the `backend/` directory:

```bash
python -m pytest tests/test_job_normalizer.py
```

## Database setup

The SQL scripts that create the tables, plus made-up example data, are in [`db/`](db/README.md). That README explains how to apply them and how to add new migration scripts.

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

Use `DbConnection` rather than `Depends(get_db)`. It makes FastAPI save changes *before* sending the response, so a failed save returns an error instead of a false success.

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

## Run the server

```bash
uvicorn app.main:app --reload
```

- Health check: http://127.0.0.1:8000/health → `{"status": "ok"}` (does not check the database)
- API docs: http://127.0.0.1:8000/docs

## Run the tests

```bash
pytest
```

The tests do not need a `.env` file or a database. The database integration tests in `tests/test_db.py` and `tests/test_job_repository.py` are skipped unless `TEST_DB_*` settings are set.

### Install and start Docker (first time only)

Docker runs a separate local MySQL server for the integration tests. You do not need to install MySQL on your computer.

1. Install Docker Desktop using the instructions for [Mac](https://docs.docker.com/desktop/setup/install/mac-install/), [Windows](https://docs.docker.com/desktop/setup/install/windows-install/), or [Linux](https://docs.docker.com/desktop/setup/install/linux/). On Mac, choose the download for your chip (Apple silicon or Intel). On Windows, follow the WSL 2 prerequisites and use Linux containers. Linux users can also use [Docker Engine](https://docs.docker.com/engine/install/).
2. Open Docker Desktop, finish its initial setup, and wait for the engine to start. Keep it running while using the test database.
3. In a new terminal, verify the installation and engine:

```bash
docker --version
docker info
docker run --rm hello-world
```

If `docker` is not found, finish installation and reopen your terminal. If it cannot connect to the Docker daemon, start Docker Desktop (or the Docker Engine service on Linux) and retry. The `hello-world` command downloads a small image and prints a success message.

### Run the database integration tests

Complete the Python setup above and activate your virtual environment first. The commands below use Bash or Zsh (macOS/Linux; on Windows use a WSL Bash terminal with Docker Desktop integration enabled). Run them from `backend/`.

Start a throwaway MySQL in Docker, create the tables, and set the test settings (in `backend/.env` or your shell). The password below is only for this local container:

```bash
docker run -d --name jh-test-mysql -p 127.0.0.1:3307:3306 \
  -e MYSQL_ROOT_PASSWORD=local_root_pw \
  -e MYSQL_DATABASE=job_hunting_ai_test \
  -e MYSQL_USER=jh_test \
  -e MYSQL_PASSWORD=local_test_pw \
  mysql:8.4

```

The first run downloads the MySQL image. Check whether MySQL is ready:

```bash
docker exec jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test -e "SELECT 1;"
```

If it reports a connection error, wait a few seconds and retry. Continue once it prints `1`. If it keeps failing, inspect `docker logs jh-test-mysql`.

Create the tables once for this container, then run the tests:

```bash
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/001_create_tables.sql
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/002_add_jobs_first_seen_at.sql

TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3307 TEST_DB_NAME=job_hunting_ai_test \
  TEST_DB_USER=jh_test TEST_DB_PASSWORD=local_test_pw \
  python -m pytest -q
```

This runs the full backend test suite, including database integration tests when the separate MySQL test database is configured. Without the `TEST_DB_*` settings, database integration tests are skipped. Check the pytest output to confirm that the integration tests ran rather than being skipped.

Stop it with `docker stop jh-test-mysql` and start it again later with `docker start jh-test-mysql`. On subsequent runs, start Docker Desktop and the existing container, check readiness, and rerun the test command; do not recreate the container or reapply the initial migration. If the container name is already in use, use `docker start` instead of `docker run`. If port `3307` is occupied, choose another host port in `-p` and use that same port for `TEST_DB_PORT`. Never point `TEST_DB_*` at the shared or production database.

## Browse the local database with DBeaver

[DBeaver Community](https://dbeaver.io/download/) is a free desktop app for browsing tables and running SQL. Install it separately from VS Code; the MySQL server stays in Docker.

1. Download the installer for your operating system. On Mac, choose Apple silicon or Intel to match your chip, open the downloaded disk image, and drag DBeaver into Applications. On Windows or Linux, follow the [installation instructions](https://dbeaver.com/docs/dbeaver/Installation/) for your download.
2. Complete the Docker database setup and initial migration in [Run the database integration tests](#run-the-database-integration-tests) above. Keep Docker Desktop and `jh-test-mysql` running. If the container already exists but is stopped, run `docker start jh-test-mysql`.
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
