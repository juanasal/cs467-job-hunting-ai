"""JH-041: recommendations and job details API.

Integration tests against the TEST_DB_* database (skipped when it isn't set).
"""

import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import transaction
from app.job_repository import upsert_job
from app.main import app

# Reuse the TEST_DB_* setup and logged-in user helper from the tracking tests.
from test_auth import auth_client  # noqa: F401
from test_job_repository import make_job
from test_tracking import make_user, test_settings  # noqa: F401


@pytest.fixture
def make_jobs(test_settings):  # noqa: F811
    """Return a function that stores n made-up jobs, deleted afterwards.

    Deleting a job also deletes its match results and tracking rows.
    """
    created = []

    def _make_jobs(n):
        ids = []
        with transaction(test_settings) as conn:
            for _ in range(n):
                job = make_job(external_job_id=f"jh041-{uuid.uuid4().hex}")
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


def set_result_count(settings, user_id, result_count):
    with transaction(settings) as conn:
        conn.cursor().execute(
            "INSERT INTO search_preferences (user_id, result_count) VALUES (%s, %s)",
            (user_id, result_count),
        )


def feed_job_ids(client):
    response = client.get("/api/recommendations")
    assert response.status_code == 200, response.text
    return [item["job"]["job_id"] for item in response.json()["recommendations"]]


def test_requires_login(test_settings, make_jobs):  # noqa: F811
    (job_id,) = make_jobs(1)
    client = TestClient(app)

    assert client.get("/api/recommendations").status_code == 401
    assert client.get(f"/api/jobs/{job_id}").status_code == 401


def test_empty_feed(test_settings, make_user):  # noqa: F811
    client, _, _ = make_user()

    response = client.get("/api/recommendations")

    assert response.status_code == 200
    assert response.json() == {"recommendations": []}


def test_feed_returns_contract_fields(test_settings, make_user, make_jobs):  # noqa: F811
    client, _, user_id = make_user()
    (job_id,) = make_jobs(1)
    add_match(test_settings, user_id, job_id, 80, skills=["SQL", "Python"])

    response = client.get("/api/recommendations")

    assert response.status_code == 200, response.text
    (item,) = response.json()["recommendations"]
    assert item["match"] == {
        "user_id": user_id,
        "job_id": job_id,
        "match_score": 80,
        "matched_skills": ["Python", "SQL"],
        "match_explanation": f"Explanation for job {job_id}.",
        "created_at": "2026-11-20T12:00:00Z",
    }
    job = item["job"]
    assert job["job_id"] == job_id
    assert job["title"] == "Software Engineer"
    assert job["salary_min"] == 80000
    assert job["salary_currency"] is None
    assert job["salary_is_predicted"] is False
    assert job["date_posted"] == "2026-11-01"
    assert job["retrieved_at"] == "2026-11-01T12:00:00Z"
    assert job["first_seen_at"] == "2026-11-01T12:00:00Z"


def test_feed_sorts_by_score_then_job_id(test_settings, make_user, make_jobs):  # noqa: F811
    client, _, user_id = make_user()
    low, tie_a, tie_b = make_jobs(3)
    add_match(test_settings, user_id, low, 40)
    add_match(test_settings, user_id, tie_b, 90)
    add_match(test_settings, user_id, tie_a, 90)

    assert feed_job_ids(client) == [tie_a, tie_b, low]


def test_feed_uses_result_count(test_settings, make_user, make_jobs):  # noqa: F811
    client, _, user_id = make_user()
    first, second, third = make_jobs(3)
    add_match(test_settings, user_id, first, 90)
    add_match(test_settings, user_id, second, 80)
    add_match(test_settings, user_id, third, 70)
    set_result_count(test_settings, user_id, 2)

    assert feed_job_ids(client) == [first, second]


def test_feed_hides_only_dismissed_jobs(test_settings, make_user, make_jobs):  # noqa: F811
    client, headers, user_id = make_user()
    saved, dismissed, applied = make_jobs(3)
    for job_id in (saved, dismissed, applied):
        add_match(test_settings, user_id, job_id, 75)

    for job_id, status in ((saved, "saved"), (dismissed, "dismissed"), (applied, "applied")):
        response = client.put(f"/api/tracking/{job_id}", json={"status": status}, headers=headers)
        assert response.status_code == 200, response.text

    assert feed_job_ids(client) == [saved, applied]

    # Undoing the dismissal puts the job back in the feed.
    assert client.delete(f"/api/tracking/{dismissed}", headers=headers).status_code == 204
    assert feed_job_ids(client) == [saved, dismissed, applied]


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
    client_a, _, user_a = make_user()
    client_b, headers_b, user_b = make_user()
    job_a, job_b = make_jobs(2)
    add_match(test_settings, user_a, job_a, 95, skills=["Python"])
    add_match(test_settings, user_b, job_b, 50, skills=["Java"])

    # Each feed only has the user's own results.
    assert feed_job_ids(client_a) == [job_a]
    assert feed_job_ids(client_b) == [job_b]

    # B can open A's job but doesn't get A's match data.
    response = client_b.get(f"/api/jobs/{job_a}")
    assert response.status_code == 200
    assert response.json()["match"] is None

    # A user_id in the query string is ignored; the session decides the user.
    response = client_b.get(f"/api/recommendations?user_id={user_a}")
    assert [item["job"]["job_id"] for item in response.json()["recommendations"]] == [job_b]
    response = client_b.get(f"/api/jobs/{job_a}?user_id={user_a}")
    assert response.json()["match"] is None

    # B dismissing A's job doesn't hide it from A's feed.
    assert client_b.put(
        f"/api/tracking/{job_a}", json={"status": "dismissed"}, headers=headers_b
    ).status_code == 200
    assert feed_job_ids(client_a) == [job_a]
