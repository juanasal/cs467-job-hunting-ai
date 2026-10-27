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

The tests do not need a `.env` file or a database.

## Error format

All error responses use the same JSON shape:

```json
{"error": {"status": 404, "message": "Not Found"}}
```

Request validation errors (422) also include a `details` list with the location and reason for each problem. Unexpected server errors return a generic `500` message so internal details aren't exposed.
