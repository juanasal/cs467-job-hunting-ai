"""Tests for JH-028: saving jobs without duplicates.

GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write unit and MySQL integration tests for the JH-028 job
repository, covering inserts, duplicate updates, first-seen timestamps,
and rollback behavior.
"""

import os
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pymysql
import pytest
from dotenv import load_dotenv

from app import job_repository
from app.config import ENV_FILE, get_settings
from app.db import fetch_one, transaction
from app.job_repository import upsert_job


def make_job(**overrides):
    """Return a complete normalized job for testing."""
    job = {
        "external_job_id": "test-123",
        "source": "adzuna",
        "title": "Software Engineer",
        "company": "Example Company",
        "location": "Portland, OR",
        "workplace_type": "remote",
        "salary_min": 80000,
        "salary_max": 110000,
        "salary_currency": None,
        "salary_is_predicted": False,
        "description": "Build software using Python.",
        "date_posted": "2026-11-01",
        "job_url": "https://example.com/jobs/123",
        "retrieved_at": "2026-11-01T12:00:00Z",
    }
    job.update(overrides)
    return job


# ---------------------------------------------------------------------------
# Unit tests: no database required.
# ---------------------------------------------------------------------------


def test_insert_uses_upsert_and_returns_job_id(monkeypatch):
    conn = MagicMock()
    calls = []

    def fake_execute(connection, sql, params):
        calls.append((connection, sql, params))
        return 1

    def fake_fetch_one(connection, sql, params):
        return {"job_id": 42}

    monkeypatch.setattr(job_repository, "execute", fake_execute)
    monkeypatch.setattr(job_repository, "fetch_one", fake_fetch_one)

    result = upsert_job(conn, make_job())

    assert result == 42
    assert len(calls) == 1

    connection, sql, params = calls[0]

    assert connection is conn
    assert "INSERT INTO jobs" in sql
    assert "ON DUPLICATE KEY UPDATE" in sql
    assert "first_seen_at" in sql
    assert "first_seen_at = VALUES" not in sql
    assert "%s" in sql

    # The first observation is initially the retrieval time.
    expected_time = datetime(2026, 11, 1, 12, 0)
    assert params[-1] == expected_time
    assert params[-2] == expected_time


def test_update_includes_changed_fields(monkeypatch):
    conn = MagicMock()
    captured = {}

    def fake_execute(connection, sql, params):
        captured["sql"] = sql
        captured["params"] = params
        return 2

    monkeypatch.setattr(job_repository, "execute", fake_execute)
    monkeypatch.setattr(
        job_repository,
        "fetch_one",
        lambda *args: {"job_id": 42},
    )

    updated_job = make_job(
        title="Senior Software Engineer",
        salary_min=100000,
        retrieved_at="2026-11-05T12:00:00Z",
    )

    assert upsert_job(conn, updated_job) == 42

    sql = captured["sql"]
    params = captured["params"]

    assert (
        "title = IF(VALUES(retrieved_at) >= retrieved_at, "
        "VALUES(title), title)"
    ) in sql
    assert (
        "salary_min = IF(VALUES(retrieved_at) >= retrieved_at, "
        "VALUES(salary_min), salary_min)"
    ) in sql
    assert (
        "retrieved_at = GREATEST(retrieved_at, VALUES(retrieved_at))"
    ) in sql
    assert "first_seen_at = VALUES(first_seen_at)" not in sql

    assert "Senior Software Engineer" in params
    assert 100000 in params
    assert datetime(2026, 11, 5, 12, 0) in params


def test_different_sources_use_composite_identity(monkeypatch):
    conn = MagicMock()
    captured = []

    monkeypatch.setattr(
        job_repository,
        "execute",
        lambda connection, sql, params: captured.append(params),
    )
    monkeypatch.setattr(
        job_repository,
        "fetch_one",
        lambda *args: {"job_id": 1},
    )

    upsert_job(conn, make_job(source="adzuna"))
    upsert_job(conn, make_job(source="another_source"))

    assert captured[0][0] == captured[1][0] == "test-123"
    assert captured[0][1] == "adzuna"
    assert captured[1][1] == "another_source"


def test_timezone_is_converted_to_utc(monkeypatch):
    conn = MagicMock()
    captured = {}

    def fake_execute(connection, sql, params):
        captured["params"] = params

    monkeypatch.setattr(job_repository, "execute", fake_execute)
    monkeypatch.setattr(
        job_repository,
        "fetch_one",
        lambda *args: {"job_id": 1},
    )

    upsert_job(
        conn,
        make_job(retrieved_at="2026-11-01T08:00:00-04:00"),
    )

    assert captured["params"][-1] == datetime(2026, 11, 1, 12, 0)


@pytest.mark.parametrize(
    "timestamp",
    [
        "not-a-date",
        "2026-11-01T12:00:00",
        None,
        12345,
    ],
)
def test_invalid_timestamp_is_rejected(timestamp, monkeypatch):
    execute_mock = MagicMock()
    monkeypatch.setattr(job_repository, "execute", execute_mock)

    with pytest.raises(ValueError):
        upsert_job(
            MagicMock(),
            make_job(retrieved_at=timestamp),
        )

    execute_mock.assert_not_called()


@pytest.mark.parametrize(
    "missing_field",
    [
        "external_job_id",
        "source",
        "title",
        "description",
        "job_url",
        "retrieved_at",
    ],
)
def test_missing_fields_are_rejected(missing_field, monkeypatch):
    execute_mock = MagicMock()
    monkeypatch.setattr(job_repository, "execute", execute_mock)

    job = make_job()
    del job[missing_field]

    with pytest.raises(ValueError):
        upsert_job(MagicMock(), job)

    execute_mock.assert_not_called()


def test_database_error_is_propagated(monkeypatch):
    def fail_execute(*args):
        raise pymysql.IntegrityError(1048, "Invalid job data")

    monkeypatch.setattr(job_repository, "execute", fail_execute)

    with pytest.raises(pymysql.IntegrityError):
        upsert_job(MagicMock(), make_job())


def test_missing_row_after_upsert_raises(monkeypatch):
    monkeypatch.setattr(
        job_repository,
        "execute",
        lambda *args: 1,
    )
    monkeypatch.setattr(
        job_repository,
        "fetch_one",
        lambda *args: None,
    )

    with pytest.raises(RuntimeError, match="not found"):
        upsert_job(MagicMock(), make_job())


# ---------------------------------------------------------------------------
# Integration tests: require a separate MySQL test database.
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def test_db_settings():
    load_dotenv(ENV_FILE)

    names = (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSL_CA",
    )

    env = {
        name: os.environ.get(f"TEST_{name}", "")
        for name in names
    }

    if not env["DB_NAME"]:
        pytest.skip(
            "TEST_DB_* not configured; skipping MySQL integration tests"
        )

    if (
        env["DB_HOST"],
        env["DB_NAME"],
    ) == (
        os.environ.get("DB_HOST"),
        os.environ.get("DB_NAME"),
    ):
        pytest.fail(
            "TEST_DB_* must use a separate database"
        )

    return get_settings(env)


@pytest.fixture
def unique_job(test_db_settings):
    """Create a unique source ID and clean it up after each test."""
    external_id = f"jh028-{uuid.uuid4().hex}"

    yield make_job(external_job_id=external_id)

    with transaction(test_db_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM jobs
                WHERE source = %s AND external_job_id = %s
                """,
                ("adzuna", external_id),
            )


def read_job(settings, external_id):
    """Read one test job from the database."""
    with transaction(settings) as conn:
        return fetch_one(
            conn,
            """
            SELECT *
            FROM jobs
            WHERE source = %s AND external_job_id = %s
            """,
            ("adzuna", external_id),
        )


def test_real_insert_and_duplicate_update(
    test_db_settings,
    unique_job,
):
    """Importing the same job twice must keep one row and job_id."""
    first_job = unique_job

    with transaction(test_db_settings) as conn:
        first_id = upsert_job(conn, first_job)

    original = read_job(
        test_db_settings,
        first_job["external_job_id"],
    )

    assert original is not None
    assert original["job_id"] == first_id
    assert original["first_seen_at"] == datetime(2026, 11, 1, 12, 0)

    updated_job = {
        **first_job,
        "title": "Senior Software Engineer",
        "salary_min": 120000,
        "retrieved_at": "2026-11-05T12:00:00Z",
    }

    with transaction(test_db_settings) as conn:
        second_id = upsert_job(conn, updated_job)

    updated = read_job(
        test_db_settings,
        first_job["external_job_id"],
    )

    assert second_id == first_id
    assert updated["job_id"] == first_id
    assert updated["title"] == "Senior Software Engineer"
    assert updated["salary_min"] == 120000
    assert updated["first_seen_at"] == original["first_seen_at"]
    assert updated["retrieved_at"] == datetime(2026, 11, 5, 12, 0)

    with transaction(test_db_settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM jobs
                WHERE source = %s AND external_job_id = %s
                """,
                ("adzuna", first_job["external_job_id"]),
            )
            assert cursor.fetchone()["count"] == 1


def test_failed_import_preserves_existing_job(
    test_db_settings,
    unique_job,
):
    """A failed transaction must not overwrite usable job data."""
    with transaction(test_db_settings) as conn:
        upsert_job(conn, unique_job)

    original = read_job(
        test_db_settings,
        unique_job["external_job_id"],
    )

    with pytest.raises(RuntimeError, match="Simulated failure"):
        with transaction(test_db_settings) as conn:
            upsert_job(
                conn,
                {
                    **unique_job,
                    "title": "Changed title",
                    "retrieved_at": "2026-11-05T12:00:00Z",
                },
            )
            raise RuntimeError("Simulated failure")

    after_failure = read_job(
        test_db_settings,
        unique_job["external_job_id"],
    )

    assert after_failure["job_id"] == original["job_id"]
    assert after_failure["title"] == original["title"]
    assert after_failure["retrieved_at"] == original["retrieved_at"]
    assert after_failure["first_seen_at"] == original["first_seen_at"]

def test_older_import_does_not_overwrite_newer_job(
    test_db_settings,
    unique_job,
):
    """An older retrieval must not replace newer stored job details."""
    newest_job = {
        **unique_job,
        "title": "Senior Software Engineer",
        "salary_min": 120000,
        "retrieved_at": "2026-11-05T12:00:00Z",
    }

    with transaction(test_db_settings) as conn:
        first_id = upsert_job(conn, newest_job)

    original = read_job(
        test_db_settings,
        unique_job["external_job_id"],
    )

    older_job = {
        **unique_job,
        "title": "Outdated Software Engineer",
        "salary_min": 70000,
        "retrieved_at": "2026-11-04T12:00:00Z",
    }

    with transaction(test_db_settings) as conn:
        second_id = upsert_job(conn, older_job)

    stored = read_job(
        test_db_settings,
        unique_job["external_job_id"],
    )

    assert second_id == first_id
    assert stored["job_id"] == first_id
    assert stored["title"] == "Senior Software Engineer"
    assert stored["salary_min"] == 120000
    assert stored["retrieved_at"] == datetime(2026, 11, 5, 12, 0)
    assert stored["first_seen_at"] == original["first_seen_at"]
