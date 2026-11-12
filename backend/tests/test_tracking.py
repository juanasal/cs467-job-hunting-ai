"""JH-045: saved, dismissed, and applied job tracking API.

Integration tests against the TEST_DB_* database (skipped when it isn't set).
"""

import os
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.db import fetch_all, fetch_one, transaction
from app.job_repository import upsert_job
from app.main import app

# Reuse the TEST_DB_* setup from the authentication tests.
from test_auth import TEST_PASSWORD, auth_client  # noqa: F401
from test_job_repository import make_job

ORIGIN = "http://localhost:3000"


@pytest.fixture
def test_settings(auth_client, monkeypatch):  # noqa: F811
    """Point DbConnection routes at the test database for one test."""
    names = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD", "DB_SSL_CA")
    settings = get_settings({name: os.environ.get(f"TEST_{name}", "") for name in names})

    # auth_client already ran app startup, so this replacement sticks.
    monkeypatch.setattr(app.state, "settings", settings)
    return settings


@pytest.fixture
def job_id(test_settings):
    """A made-up job, deleted afterwards (which also deletes its tracking)."""
    job = make_job(external_job_id=f"jh045-{uuid.uuid4().hex}")

    with transaction(test_settings) as conn:
        new_id = upsert_job(conn, job)

    yield new_id

    with transaction(test_settings) as conn:
        conn.cursor().execute("DELETE FROM jobs WHERE job_id = %s", (new_id,))


@pytest.fixture
def make_user(test_settings):
    """Return a function that logs in a new user: (client, headers, user_id)."""
    emails = []

    def _make_user():
        email = f"jh045_{uuid.uuid4().hex}@example.com"
        emails.append(email)
        client = TestClient(app)
        login = {"email": email, "password": TEST_PASSWORD}

        assert client.post("/api/auth/register", json=login).status_code == 201
        response = client.post("/api/auth/login", json=login)
        assert response.status_code == 200, response.text

        csrf = client.get("/api/auth/csrf").json()["csrf_token"]
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf}
        return client, headers, response.json()["user"]["user_id"]

    yield _make_user

    with transaction(test_settings) as conn:
        for email in emails:
            conn.cursor().execute("DELETE FROM users WHERE email = %s", (email,))


def tracking_rows(settings, job_id):
    with transaction(settings) as conn:
        return fetch_all(
            conn,
            "SELECT user_id, status FROM job_tracking WHERE job_id = %s ORDER BY user_id",
            (job_id,),
        )


def test_requires_login(test_settings, job_id):
    client = TestClient(app)

    assert client.get("/api/tracking").status_code == 401
    assert client.put(
        f"/api/tracking/{job_id}", json={"status": "saved"}
    ).status_code in (401, 403)
    assert client.delete(f"/api/tracking/{job_id}").status_code in (401, 403)


def test_repeating_an_action_does_not_duplicate(test_settings, job_id, make_user):
    client, headers, user_id = make_user()
    url = f"/api/tracking/{job_id}"

    first = client.put(url, json={"status": "saved"}, headers=headers)
    second = client.put(url, json={"status": "saved"}, headers=headers)

    assert first.status_code == 200, first.text
    assert second.json() == first.json()
    assert second.json()["status"] == "saved"
    assert tracking_rows(test_settings, job_id) == [{"user_id": user_id, "status": "saved"}]

    # Changing the status updates the same row.
    response = client.put(url, json={"status": "applied"}, headers=headers)
    assert response.json()["status"] == "applied"
    assert tracking_rows(test_settings, job_id) == [{"user_id": user_id, "status": "applied"}]

    # Undo removes it; undoing again finds nothing to undo.
    assert client.delete(url, headers=headers).status_code == 204
    assert tracking_rows(test_settings, job_id) == []
    assert client.delete(url, headers=headers).status_code == 404


def test_two_users_track_same_job_differently(test_settings, job_id, make_user):
    client_a, headers_a, user_a = make_user()
    client_b, headers_b, user_b = make_user()
    url = f"/api/tracking/{job_id}"

    assert client_a.put(url, json={"status": "saved"}, headers=headers_a).status_code == 200
    assert client_b.put(url, json={"status": "dismissed"}, headers=headers_b).status_code == 200

    assert tracking_rows(test_settings, job_id) == sorted(
        [{"user_id": user_a, "status": "saved"}, {"user_id": user_b, "status": "dismissed"}],
        key=lambda row: row["user_id"],
    )

    # Each user's list shows only their own status.
    list_a = client_a.get("/api/tracking").json()["tracking"]
    list_b = client_b.get("/api/tracking", params={"status": "dismissed"}).json()["tracking"]

    assert [(t["user_id"], t["job_id"], t["status"]) for t in list_a] == [(user_a, job_id, "saved")]
    assert [(t["user_id"], t["job_id"], t["status"]) for t in list_b] == [(user_b, job_id, "dismissed")]
    assert client_a.get("/api/tracking", params={"status": "dismissed"}).json() == {"tracking": []}


def test_wrong_ids_and_values_are_rejected(test_settings, job_id, make_user):
    client, headers, _ = make_user()

    with transaction(test_settings) as conn:
        missing_id = fetch_one(conn, "SELECT COALESCE(MAX(job_id), 0) + 1000 AS id FROM jobs")["id"]

    assert client.put(
        f"/api/tracking/{missing_id}", json={"status": "saved"}, headers=headers
    ).status_code == 404
    assert client.delete(f"/api/tracking/{missing_id}", headers=headers).status_code == 404

    for bad_id in ("0", "-1", "abc"):
        assert client.put(
            f"/api/tracking/{bad_id}", json={"status": "saved"}, headers=headers
        ).status_code == 422

    assert client.put(
        f"/api/tracking/{job_id}", json={"status": "deleted"}, headers=headers
    ).status_code == 422
    assert client.get("/api/tracking", params={"status": "deleted"}).status_code == 422
    assert tracking_rows(test_settings, job_id) == []


def test_cannot_change_another_users_tracking(test_settings, job_id, make_user):
    client_a, headers_a, user_a = make_user()
    client_b, headers_b, user_b = make_user()
    url = f"/api/tracking/{job_id}"

    assert client_b.put(url, json={"status": "dismissed"}, headers=headers_b).status_code == 200

    # A can't name B as the owner in the body.
    response = client_a.put(
        url, json={"status": "applied", "user_id": user_b}, headers=headers_a
    )
    assert response.status_code == 422

    # A can't undo B's tracking; A has nothing to undo for this job.
    assert client_a.delete(url, params={"user_id": user_b}, headers=headers_a).status_code == 404

    # A user_id in the query is ignored: the session decides whose row changes.
    response = client_a.put(
        url, params={"user_id": user_b}, json={"status": "saved"}, headers=headers_a
    )
    assert response.json()["user_id"] == user_a

    rows = {row["user_id"]: row["status"] for row in tracking_rows(test_settings, job_id)}
    assert rows == {user_a: "saved", user_b: "dismissed"}

