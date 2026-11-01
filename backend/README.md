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
| `TEST_DB_*` | For DB tests | Separate test database used by `tests/test_db.py` (see [Run the tests](#run-the-tests)) |
| `ADZUNA_APP_ID`, `ADZUNA_APP_KEY` | For Adzuna client | Adzuna API credentials |

The server will not start if a required setting is missing or invalid. The error names the setting but never shows its value.
Nothing connects to the database yet, so the placeholder values in `.env.example` are enough to run the server locally.

## Adzuna job client

Adzuna is the external job-search API used to retrieve job listings for the application.

- `app/adzuna_client.py` fetches job listings from Adzuna and supports search parameters, pagination, page limits, and request timeouts.
- `tests/test_adzuna_client.py` tests the client using saved and simulated responses, so the tests do not require live API calls or Adzuna credentials.

Run the Adzuna client tests from the `backend/` directory:

```bash
python -m pytest tests/test_adzuna_client.py
```
More details about the Adzuna API and our findings are documented in [`documentation/ADZUNA_RESEARCH.md`](../documentation/ADZUNA_RESEARCH.md).
## Database setup

The SQL scripts that create the tables, plus made-up example data, are in [`db/`](db/README.md). That README explains how to apply them and how to add new migration scripts.

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

The tests do not need a `.env` file or a database. The database integration tests in `tests/test_db.py` are skipped unless `TEST_DB_*` settings are set.

To run them, start a throwaway MySQL in Docker, create the tables, and set the test settings (in `backend/.env` or your shell). The password below is only for this local container:

```bash
docker run -d --name jh-test-mysql -p 127.0.0.1:3307:3306 \
  -e MYSQL_ROOT_PASSWORD=local_root_pw -e MYSQL_DATABASE=job_hunting_ai_test \
  -e MYSQL_USER=jh_test -e MYSQL_PASSWORD=local_test_pw mysql:8.4
# Wait about 20 seconds for MySQL to start, then:
docker exec -i jh-test-mysql mysql -ujh_test -plocal_test_pw job_hunting_ai_test < db/migrations/001_create_tables.sql

TEST_DB_HOST=127.0.0.1 TEST_DB_PORT=3307 TEST_DB_NAME=job_hunting_ai_test \
  TEST_DB_USER=jh_test TEST_DB_PASSWORD=local_test_pw pytest
```

Stop it with `docker stop jh-test-mysql` and start it again later with `docker start jh-test-mysql`. Never point `TEST_DB_*` at the shared or production database.

## Error format

All error responses use the same JSON shape:

```json
{"error": {"status": 404, "message": "Not Found"}}
```

Request validation errors (422) also include a `details` list with the location and reason for each problem. Unexpected server errors return a generic `500` message so internal details aren't exposed.
