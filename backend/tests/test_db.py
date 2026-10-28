import os
import uuid

import pymysql
import pytest
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import db
from app.config import ENV_FILE, get_settings
from app.db import DbConnection, execute, fetch_all, fetch_one, transaction

VALID_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_NAME": "job_hunting_ai",
    "DB_USER": "tester",
    "DB_PASSWORD": "super-secret-password",
}


# ---------------------------------------------------------------------------
# Unit tests: a fake connection stands in for MySQL, so no database is needed.
# ---------------------------------------------------------------------------
class FakeConnection:
    def __init__(self, fail_commit=False, fail_rollback=False):
        self.fail_commit = fail_commit
        self.fail_rollback = fail_rollback
        self.calls = []

    def commit(self):
        self.calls.append("commit")
        if self.fail_commit:
            raise pymysql.OperationalError("commit failed")

    def rollback(self):
        self.calls.append("rollback")
        if self.fail_rollback:
            raise pymysql.InterfaceError(0, "")

    def close(self):
        self.calls.append("close")


@pytest.fixture
def fake_conn(monkeypatch):
    conn = FakeConnection()
    monkeypatch.setattr(db, "connect", lambda settings: conn)
    return conn


@pytest.fixture
def client():
    test_app = FastAPI()
    test_app.state.settings = get_settings(VALID_ENV)

    @test_app.get("/ok")
    def ok(conn: DbConnection):
        return {"status": "ok"}

    @test_app.get("/error")
    def error(conn: DbConnection):
        raise RuntimeError("something went wrong mid-request")

    return TestClient(test_app, raise_server_exceptions=False)


def test_transaction_commits_and_closes_on_success(fake_conn):
    with transaction(get_settings(VALID_ENV)):
        pass
    assert fake_conn.calls == ["commit", "close"]


def test_transaction_rolls_back_and_closes_on_error(fake_conn):
    with pytest.raises(ValueError):
        with transaction(get_settings(VALID_ENV)):
            raise ValueError("step two failed")
    assert fake_conn.calls == ["rollback", "close"]


def test_lost_connection_keeps_original_error(fake_conn):
    # When the connection drops, rollback() fails too. The caller should still see
    # the real cause, not the rollback's error.
    fake_conn.fail_commit = True
    fake_conn.fail_rollback = True
    with pytest.raises(pymysql.OperationalError, match="commit failed"):
        with transaction(get_settings(VALID_ENV)):
            pass
    assert fake_conn.calls == ["commit", "rollback", "close"]


def test_request_connection_closes_after_success(fake_conn, client):
    assert client.get("/ok").status_code == 200
    assert fake_conn.calls == ["commit", "close"]


def test_request_connection_closes_after_error(fake_conn, client):
    assert client.get("/error").status_code == 500
    assert fake_conn.calls == ["rollback", "close"]


def test_failed_commit_returns_error_not_success(fake_conn, client):
    # The commit must happen before the response is sent, or the user would see
    # "success" for a change that was never saved.
    fake_conn.fail_commit = True
    assert client.get("/ok").status_code == 500
    assert fake_conn.calls == ["commit", "rollback", "close"]


def test_connect_uses_ssl_only_when_ca_is_set(monkeypatch):
    captured = []
    monkeypatch.setattr(db.pymysql, "connect", lambda **kwargs: captured.append(kwargs))

    db.connect(get_settings(VALID_ENV))
    db.connect(get_settings({**VALID_ENV, "DB_SSL_CA": "/path/to/ca.pem"}))

    assert captured[0]["ssl"] is None
    assert captured[1]["ssl"] == {"ca": "/path/to/ca.pem"}
    assert captured[0]["autocommit"] is False


# ---------------------------------------------------------------------------
# Integration tests: run against a real, separate test database.
# Skipped unless TEST_DB_* settings are set (see backend/README.md).
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def test_db_settings():
    load_dotenv(ENV_FILE)
    names = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSL_CA")
    env = {name: os.environ.get(f"TEST_{name}", "") for name in names}
    if not env["DB_NAME"]:
        pytest.skip("TEST_DB_* settings not set; skipping database integration tests")
    if (env["DB_HOST"], env["DB_NAME"]) == (os.environ.get("DB_HOST"), os.environ.get("DB_NAME")):
        pytest.fail("TEST_DB_* must point at a separate test database, not the main one")
    return get_settings(env)


@pytest.fixture
def made_up_email(test_db_settings):
    email = f"jh006-test-{uuid.uuid4().hex[:8]}@example.com"
    yield email
    # Clean up. Deleting the user also deletes its other rows.
    with transaction(test_db_settings) as conn:
        execute(conn, "DELETE FROM users WHERE email = %s", (email,))


def test_add_and_read_made_up_record(test_db_settings, made_up_email):
    # Looks like an attack, but must be stored as plain text because it is passed as a parameter.
    tricky_skill = "O'Brien'); DROP TABLE users; --"

    with transaction(test_db_settings) as conn:
        execute(
            conn,
            "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (made_up_email, "placeholder-not-a-real-hash"),
        )
        user_id = conn.insert_id()
        execute(conn, "INSERT INTO user_skills (user_id, skill) VALUES (%s, %s)", (user_id, tricky_skill))
    assert not conn.open

    with transaction(test_db_settings) as conn:
        user = fetch_one(conn, "SELECT user_id, email FROM users WHERE email = %s", (made_up_email,))
        skills = fetch_all(conn, "SELECT skill FROM user_skills WHERE user_id = %s", (user_id,))

    assert user == {"user_id": user_id, "email": made_up_email}
    assert skills == [{"skill": tricky_skill}]


def test_update_counts_matched_rows_not_changed_rows(test_db_settings, made_up_email):
    with transaction(test_db_settings) as conn:
        execute(
            conn,
            "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (made_up_email, "placeholder-not-a-real-hash"),
        )
        user_id = conn.insert_id()
        execute(
            conn,
            "INSERT INTO user_profiles (user_id, education_level, experience_level) VALUES (%s, %s, %s)",
            (user_id, "bachelor", "entry"),
        )
        update = "UPDATE user_profiles SET experience_level = %s WHERE user_id = %s"

        # Saving the same values still finds the row, so a route won't send a false 404.
        assert execute(conn, update, ("entry", user_id)) == 1
        assert execute(conn, update, ("entry", 0)) == 0


def test_failed_multi_step_update_saves_nothing(test_db_settings, made_up_email):
    with pytest.raises(pymysql.MySQLError):
        with transaction(test_db_settings) as conn:
            execute(
                conn,
                "INSERT INTO users (email, password_hash) VALUES (%s, %s)",
                (made_up_email, "placeholder-not-a-real-hash"),
            )
            user_id = conn.insert_id()
            execute(conn, "INSERT INTO user_skills (user_id, skill) VALUES (%s, %s)", (user_id, "Python"))
            # Last step fails: 'kindergarten' is not an allowed education_level.
            execute(
                conn,
                "INSERT INTO user_profiles (user_id, education_level, experience_level) VALUES (%s, %s, %s)",
                (user_id, "kindergarten", "entry"),
            )
    assert not conn.open

    with transaction(test_db_settings) as conn:
        assert fetch_one(conn, "SELECT user_id FROM users WHERE email = %s", (made_up_email,)) is None
        assert fetch_all(conn, "SELECT skill FROM user_skills WHERE user_id = %s", (user_id,)) == []
