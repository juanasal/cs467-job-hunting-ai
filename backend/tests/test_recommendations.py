"""JH-041/JH-051: recommendations and job details API.

Integration tests against the TEST_DB_* database (skipped when it isn't set).
"""

import uuid
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app import recommendations
from app.adzuna_client import AdzunaClient, AdzunaRequestError
from app.authentication import get_current_user
from app.db import get_db, transaction
from app.job_repository import upsert_job
from app.main import app
from app.saved_search_pipeline import run_saved_search
from app.search_preferences import SearchPreferencesResponse

# Reuse the TEST_DB_* setup and logged-in user helper from the tracking tests.
from test_auth import auth_client  # noqa: F401
from test_job_repository import make_job
from test_profile import sample_profile
from test_tracking import make_user, test_settings  # noqa: F401


@pytest.fixture
def make_jobs(test_settings):  # noqa: F811
    """Return a function that stores n made-up jobs, deleted afterwards.

    Deleting a job also deletes its match results and tracking rows.
    """
    created = []

    def _make_jobs(n, **overrides):
        ids = []
        with transaction(test_settings) as conn:
            for _ in range(n):
                job = make_job(
                    external_job_id=f"jh051-{uuid.uuid4().hex}", **overrides
                )
                ids.append(upsert_job(conn, job))
        created.extend(ids)
        return ids

    yield _make_jobs

    with transaction(test_settings) as conn:
        for job_id in created:
            conn.cursor().execute("DELETE FROM jobs WHERE job_id = %s", (job_id,))


def add_match(settings, user_id, job_id, score, skills=()):
    with transaction(settings) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO match_results "
            "(user_id, job_id, match_score, match_explanation, created_at) "
            "VALUES (%s, %s, %s, %s, '2026-11-20 12:00:00')",
            (user_id, job_id, score, f"Explanation for job {job_id}."),
        )
        for skill in skills:
            cursor.execute(
                "INSERT INTO match_result_skills (user_id, job_id, skill) "
                "VALUES (%s, %s, %s)",
                (user_id, job_id, skill),
            )


def save_matching_inputs(client, headers, *, skills=("Python",), **preferences):
    response = client.put("/api/profile", headers=headers, json=sample_profile(skills=list(skills)))
    assert response.status_code == 200, response.text
    response = client.put(
        "/api/preferences", headers=headers,
        json={"job_titles": ["Software Engineer"], **preferences},
    )
    assert response.status_code == 200, response.text


def set_inactive(settings, job_id):
    with transaction(settings) as conn:
        conn.cursor().execute("UPDATE jobs SET is_active = FALSE WHERE job_id = %s", (job_id,))


def feed_job_ids(client):
    response = client.get("/api/recommendations")
    assert response.status_code == 200, response.text
    return [item["job"]["job_id"] for item in response.json()["recommendations"]]


def test_feed_uses_current_matching_inputs_without_mysql(monkeypatch):
    user_id = 7
    conn = object()
    profile = {"user_id": user_id, **sample_profile(skills=["Python"])}
    preferences = SearchPreferencesResponse(user_id=user_id, job_titles=["Engineer"])
    timestamp = datetime(2026, 11, 1, 12)
    jobs = [
        {
            **make_job(description=f"Required: {skill}."),
            "job_id": job_id,
            "date_posted": timestamp.date(),
            "retrieved_at": timestamp,
            "first_seen_at": timestamp,
            "is_active": True,
        }
        for job_id, skill in ((1, "Java"), (2, "Python"))
    ]

    def load_jobs(connection, requested_user_id):
        assert (connection, requested_user_id) == (conn, user_id)
        return jobs

    def unexpected_request(*args, **kwargs):
        pytest.fail("The recommendation feed called the external job source")

    monkeypatch.setitem(app.dependency_overrides, get_db, lambda: conn)
    monkeypatch.setitem(app.dependency_overrides, get_current_user, lambda: {"user_id": user_id})
    monkeypatch.setattr(recommendations, "load_profile", lambda *_: profile)
    monkeypatch.setattr(recommendations, "load_preferences", lambda *_: preferences)
    monkeypatch.setattr(recommendations, "load_recommendation_jobs", load_jobs)
    monkeypatch.setattr(AdzunaClient, "fetch_page", unexpected_request)

    client = TestClient(app)
    response = client.get("/api/recommendations?user_id=99")
    assert response.status_code == 200, response.text
    first, second = response.json()["recommendations"]
    assert [first["job"]["job_id"], second["job"]["job_id"]] == [2, 1]
    assert first["match"]["user_id"] == user_id
    assert first["match"]["match_score"] > second["match"]["match_score"]
    assert "Direct skill matches include Python." in first["match"]["match_explanation"]

    profile["skills"] = ["Java"]
    assert feed_job_ids(client) == [1, 2]
    jobs.clear()
    assert feed_job_ids(client) == []
    profile["skills"] = []
    assert feed_job_ids(client) == []


def test_requires_login(test_settings, make_jobs):  # noqa: F811
    (job_id,) = make_jobs(1)
    client = TestClient(app)

    assert client.get("/api/recommendations").status_code == 401
    assert client.get(f"/api/jobs/{job_id}").status_code == 401


def test_insufficient_profile_returns_empty_feed(test_settings, make_user, make_jobs):
    client, _, user_id = make_user()
    (job_id,) = make_jobs(1)
    add_match(test_settings, user_id, job_id, 90)

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    assert response.json() == {"recommendations": []}


def test_feed_returns_contract_fields(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, user_id = make_user()
    (job_id,) = make_jobs(1, source="manual", description="Required: Python and SQL.")
    save_matching_inputs(client, headers, skills=["Python", "SQL"])

    response = client.get("/api/recommendations")

    assert response.status_code == 200, response.text
    (item,) = response.json()["recommendations"]
    match = item["match"]
    assert match == {
        "user_id": user_id,
        "job_id": job_id,
        "match_score": 80,
        "matched_skills": ["Python", "SQL"],
        "match_explanation": match["match_explanation"],
        "created_at": match["created_at"],
    }
    assert "Direct skill matches include Python, SQL." in match["match_explanation"]
    assert match["created_at"].endswith("Z")
    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["match"]["match_score"] == match["match_score"]
    assert detail["match"]["match_explanation"] == match["match_explanation"]
    job = item["job"]
    assert job["job_id"] == job_id
    assert job["title"] == "Software Engineer"
    assert job["salary_min"] == 80000
    assert job["salary_currency"] is None
    assert job["salary_is_predicted"] is False
    assert job["date_posted"] == "2026-11-01"
    assert job["retrieved_at"] == "2026-11-01T12:00:00Z"
    assert job["first_seen_at"] == "2026-11-01T12:00:00Z"
    assert job["is_active"] is True


def test_feed_sorts_by_score_then_job_id(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, _ = make_user()
    (low,) = make_jobs(1, description="Required: Java.")
    tie_a, tie_b = make_jobs(2, description="Required: Python.")
    save_matching_inputs(client, headers)

    assert feed_job_ids(client) == [tie_a, tie_b, low]
    response = client.put("/api/profile", json=sample_profile(skills=["Java"]), headers=headers)
    assert response.status_code == 200, response.text
    assert feed_job_ids(client) == [low, tie_a, tie_b]


def test_feed_uses_result_count(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, _ = make_user()
    first, second, _ = make_jobs(3, description="Required: Python.")
    save_matching_inputs(client, headers, result_count=2)

    assert feed_job_ids(client) == [first, second]


def test_feed_hides_only_dismissed_jobs(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, _ = make_user()
    saved, dismissed, applied = make_jobs(3)
    save_matching_inputs(client, headers)

    for job_id, status in ((saved, "saved"), (dismissed, "dismissed"), (applied, "applied")):
        response = client.put(f"/api/tracking/{job_id}", json={"status": status}, headers=headers)
        assert response.status_code == 200, response.text

    assert feed_job_ids(client) == [saved, applied]

    # Undoing the dismissal puts the job back in the feed.
    assert client.delete(f"/api/tracking/{dismissed}", headers=headers).status_code == 204
    assert feed_job_ids(client) == [saved, dismissed, applied]


def test_feed_hides_inactive_jobs(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, _ = make_user()
    active, inactive = make_jobs(2)
    save_matching_inputs(client, headers)
    set_inactive(test_settings, inactive)

    assert feed_job_ids(client) == [active]


def test_saved_preferences_are_applied_before_result_limit(make_user, make_jobs):
    client, headers, _ = make_user()
    (remote,) = make_jobs(1, workplace_type="remote", description="Required: Python.")
    (onsite,) = make_jobs(1, workplace_type="onsite", description="Required: Java.")
    save_matching_inputs(
        client, headers, workplace_type=["onsite"], strict_workplace=True, result_count=1
    )
    assert feed_job_ids(client) == [onsite]
    save_matching_inputs(
        client, headers, workplace_type=["remote"], strict_workplace=True, result_count=1
    )
    assert feed_job_ids(client) == [remote]


def test_pending_and_failed_ingestion_keep_feed_available(
    test_settings, make_user, make_jobs, monkeypatch
):
    client, headers, user_id = make_user()
    save_matching_inputs(client, headers)
    source_calls = []

    def fail_request(*args, **kwargs):
        source_calls.append(True)
        raise AdzunaRequestError("Adzuna API request failed.")

    monkeypatch.setattr(AdzunaClient, "fetch_page", fail_request)
    assert feed_job_ids(client) == []
    assert source_calls == []

    source = AdzunaClient(app_id="test", app_key="test")
    try:
        with pytest.raises(AdzunaRequestError):
            run_saved_search(user_id, client=source, settings=test_settings)
        assert feed_job_ids(client) == []
        (job_id,) = make_jobs(1, source="manual")
        with pytest.raises(AdzunaRequestError):
            run_saved_search(user_id, client=source, settings=test_settings)
        assert feed_job_ids(client) == [job_id]
        assert feed_job_ids(client) == [job_id]
        assert source_calls == [True, True]
    finally:
        source.http_client.close()


def test_job_details_returns_inactive_job(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, user_id = make_user()
    (job_id,) = make_jobs(1)
    add_match(test_settings, user_id, job_id, 90)
    assert client.put(
        f"/api/tracking/{job_id}", json={"status": "saved"}, headers=headers
    ).status_code == 200
    set_inactive(test_settings, job_id)

    # A saved job that goes inactive can still be opened, with its match.
    response = client.get(f"/api/jobs/{job_id}")
    assert response.status_code == 200, response.text
    assert response.json()["job"]["is_active"] is False
    assert response.json()["match"]["match_score"] == 90


def test_job_details_with_and_without_match(test_settings, make_user, make_jobs):  # noqa: F811
    client, _, user_id = make_user()
    matched, unmatched = make_jobs(2)
    add_match(test_settings, user_id, matched, 65, skills=["Python"])

    response = client.get(f"/api/jobs/{matched}")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["job"]["job_id"] == matched
    assert body["match"]["match_score"] == 65
    assert body["match"]["matched_skills"] == ["Python"]

    response = client.get(f"/api/jobs/{unmatched}")
    assert response.status_code == 200, response.text
    assert response.json()["job"]["job_id"] == unmatched
    assert response.json()["match"] is None


def test_job_details_unknown_and_invalid_ids(test_settings, make_user):  # noqa: F811
    client, _, _ = make_user()

    response = client.get("/api/jobs/999999999")
    assert response.status_code == 404
    assert response.json() == {"error": {"status": 404, "message": "Job not found."}}

    assert client.get("/api/jobs/0").status_code == 422
    assert client.get("/api/jobs/abc").status_code == 422


def test_users_cannot_see_each_others_matches(test_settings, make_user, make_jobs):  # noqa: F811
    client_a, headers_a, user_a = make_user()
    client_b, headers_b, user_b = make_user()
    job_a, job_b = make_jobs(2)
    add_match(test_settings, user_a, job_a, 95, skills=["Python"])
    add_match(test_settings, user_b, job_b, 50, skills=["Java"])

    save_matching_inputs(client_a, headers_a)
    assert feed_job_ids(client_a) == [job_a, job_b]
    assert feed_job_ids(client_b) == []

    # B can open A's job but doesn't get A's match data.
    response = client_b.get(f"/api/jobs/{job_a}")
    assert response.status_code == 200
    assert response.json()["match"] is None

    # A user_id in the query string is ignored; the session decides the user.
    response = client_b.get(f"/api/recommendations?user_id={user_a}")
    assert response.json() == {"recommendations": []}
    response = client_b.get(f"/api/jobs/{job_a}?user_id={user_a}")
    assert response.json()["match"] is None

    # B dismissing A's job doesn't hide it from A's feed.
    assert client_b.put(
        f"/api/tracking/{job_a}", json={"status": "dismissed"}, headers=headers_b
    ).status_code == 200
    assert feed_job_ids(client_a) == [job_a, job_b]
