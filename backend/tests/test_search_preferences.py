
# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Review and correct JH-018 integration tests for search
# preferences, including isolated MySQL access, authentication,
# CSRF, validation, persistence, and user isolation.
# Reviewed and adapted for the CS467 Job Hunting AI project.

"""Integration tests for the JH-018 search preferences API."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.config import get_frontend_origins, get_settings
from app.db import get_db, transaction
from app.main import app

from test_auth import TEST_PASSWORD, auth_client  # noqa: F401


PREFERENCES_URL = "/api/preferences"


def sample_preferences(**overrides):
    """Return valid search preferences."""
    data = {
        "job_titles": ["Software Engineer", "Data Engineer"],
        "locations": ["Portland, OR", "Seattle, WA"],
        "workplace_type": ["remote", "hybrid"],
        "salary_min": 80000,
        "salary_max": 150000,
        "salary_currency": "USD",
        "result_count": 20,
    }
    data.update(overrides)
    return data


@pytest.fixture
def preferences_client(auth_client):
    """Use the isolated MySQL test database for API requests."""
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
        pytest.skip("TEST_DB_* settings are not configured.")

    if (
        env["DB_HOST"],
        env["DB_NAME"],
    ) == (
        os.environ.get("DB_HOST"),
        os.environ.get("DB_NAME"),
    ):
        pytest.fail(
            "TEST_DB_* must use a separate test database."
        )

    test_settings = get_settings(env)

    def override_get_db():
        with transaction(test_settings) as conn:
            yield conn

    previous_override = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = override_get_db

    try:
        yield auth_client
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_db, None)
        else:
            app.dependency_overrides[get_db] = previous_override


def register_and_login(client):
    """Register a unique user and obtain CSRF headers."""
    email = f"preferences-{uuid4().hex}@example.com"

    response = client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 201, response.text

    response = client.post(
        "/api/auth/login",
        json={
            "email": email,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text

    user_id = response.json()["user"]["user_id"]

    response = client.get("/api/auth/csrf")
    assert response.status_code == 200, response.text

    csrf_token = response.json()["csrf_token"]

    origins = sorted(get_frontend_origins())
    assert origins, "No trusted frontend origins configured."

    headers = {
        "Origin": origins[0],
        "X-CSRF-Token": csrf_token,
    }

    return user_id, email, headers


def save_preferences(client, headers, data=None):
    """Save preferences using an authenticated PUT request."""
    return client.put(
        PREFERENCES_URL,
        json=data if data is not None else sample_preferences(),
        headers=headers,
    )


def test_get_requires_login(preferences_client):
    """Anonymous users cannot read preferences."""
    with TestClient(app) as client:
        response = client.get(PREFERENCES_URL)

    assert response.status_code == 401, response.text


def test_put_requires_login(preferences_client):
    """Anonymous users cannot save preferences."""
    with TestClient(app) as client:
        response = client.put(
            PREFERENCES_URL,
            json=sample_preferences(),
        )

    assert response.status_code in (401, 403), response.text


def test_get_missing_preferences(preferences_client):
    """A new user has no preferences yet."""
    register_and_login(preferences_client)

    response = preferences_client.get(PREFERENCES_URL)

    assert response.status_code == 404, response.text


def test_create_and_read_preferences(preferences_client):
    """Preferences are saved and retrieved from MySQL."""
    user_id, _, headers = register_and_login(preferences_client)

    response = save_preferences(preferences_client, headers)
    assert response.status_code == 200, response.text

    saved = response.json()
    assert saved["user_id"] == user_id
    assert saved["result_count"] == 20

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text

    data = response.json()

    assert data["user_id"] == user_id
    assert data["job_titles"] == [
        "Data Engineer",
        "Software Engineer",
    ]
    assert data["locations"] == [
        "Portland, OR",
        "Seattle, WA",
    ]
    assert set(data["workplace_type"]) == {
        "remote",
        "hybrid",
    }
    assert float(data["salary_min"]) == 80000
    assert float(data["salary_max"]) == 150000
    assert data["salary_currency"] == "USD"
    assert data["result_count"] == 20


def test_update_preferences(preferences_client):
    """Existing preferences can be replaced."""
    _, _, headers = register_and_login(preferences_client)

    response = save_preferences(preferences_client, headers)
    assert response.status_code == 200, response.text

    updated = sample_preferences(
        job_titles=["Backend Developer"],
        locations=["Los Angeles, CA"],
        workplace_type=["onsite"],
        salary_min=None,
        salary_max=None,
        result_count=10,
    )

    response = save_preferences(
        preferences_client,
        headers,
        updated,
    )
    assert response.status_code == 200, response.text

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text

    data = response.json()

    assert data["job_titles"] == ["Backend Developer"]
    assert data["locations"] == ["Los Angeles, CA"]
    assert data["workplace_type"] == ["onsite"]
    assert data["salary_min"] is None
    assert data["salary_max"] is None
    assert data["result_count"] == 10


@pytest.mark.parametrize(
    "invalid_data",
    [
        sample_preferences(
            salary_min=150000,
            salary_max=80000,
        ),
        sample_preferences(salary_min=-1),
        sample_preferences(salary_max=-1),
        sample_preferences(result_count=0),
        sample_preferences(result_count=-5),
        sample_preferences(result_count=1.5),
        sample_preferences(salary_currency="EUR"),
        sample_preferences(
            workplace_type=["remote", "unknown"],
        ),
        sample_preferences(
            job_titles=[
                "Python Developer",
                "python developer",
            ],
        ),
        sample_preferences(
            locations=["Seattle", "seattle"],
        ),
        sample_preferences(
            workplace_type=["remote", "remote"],
        ),
        sample_preferences(job_titles=[""]),
        sample_preferences(locations=["   "]),
    ],
)
def test_invalid_preferences_rejected(
    preferences_client,
    invalid_data,
):
    """Invalid preferences return HTTP 422."""
    _, _, headers = register_and_login(preferences_client)

    response = save_preferences(
        preferences_client,
        headers,
        invalid_data,
    )

    assert response.status_code == 422, response.text


def test_invalid_update_preserves_preferences(preferences_client):
    """Invalid updates must not overwrite existing preferences."""
    _, _, headers = register_and_login(preferences_client)

    response = save_preferences(preferences_client, headers)
    assert response.status_code == 200, response.text

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text
    original = response.json()

    response = save_preferences(
        preferences_client,
        headers,
        sample_preferences(
            salary_min=200000,
            salary_max=100000,
        ),
    )
    assert response.status_code == 422, response.text

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text
    assert response.json() == original


def test_put_requires_csrf(preferences_client):
    """PUT requires valid CSRF and Origin headers."""
    _, _, headers = register_and_login(preferences_client)

    response = preferences_client.put(
        PREFERENCES_URL,
        json=sample_preferences(),
        headers={
            "Origin": headers["Origin"],
        },
    )
    assert response.status_code == 403, response.text

    response = preferences_client.put(
        PREFERENCES_URL,
        json=sample_preferences(),
        headers={
            "Origin": "https://untrusted.example.com",
            "X-CSRF-Token": headers["X-CSRF-Token"],
        },
    )
    assert response.status_code == 403, response.text


def test_users_cannot_access_other_preferences(preferences_client):
    """Each user can access only their own preferences."""
    user_a, email_a, headers_a = register_and_login(
        preferences_client
    )

    response = save_preferences(
        preferences_client,
        headers_a,
        sample_preferences(job_titles=["Developer A"]),
    )
    assert response.status_code == 200, response.text

    user_b, _, headers_b = register_and_login(
        preferences_client
    )

    response = save_preferences(
        preferences_client,
        headers_b,
        sample_preferences(job_titles=["Developer B"]),
    )
    assert response.status_code == 200, response.text

    # Attempt to read user A's preferences while logged in as B.
    response = preferences_client.get(
        PREFERENCES_URL,
        params={"user_id": user_a},
    )

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == user_b
    assert response.json()["job_titles"] == ["Developer B"]

    # Attempt to update A's preferences while logged in as B.
    response = preferences_client.put(
        PREFERENCES_URL,
        params={"user_id": user_a},
        json=sample_preferences(
            job_titles=["Updated B"],
        ),
        headers=headers_b,
    )
    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == user_b

    # Log back in as user A.
    response = preferences_client.post(
        "/api/auth/login",
        json={
            "email": email_a,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text

    response = preferences_client.get(PREFERENCES_URL)

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == user_a
    assert response.json()["job_titles"] == ["Developer A"]


def test_reordered_lists_preserve_preferences(preferences_client):
    """Changing list order does not change saved preference values."""
    _, _, headers = register_and_login(preferences_client)

    response = save_preferences(preferences_client, headers)
    assert response.status_code == 200, response.text

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text
    original = response.json()

    reordered = sample_preferences(
        job_titles=[
            "Data Engineer",
            "Software Engineer",
        ],
        locations=[
            "Seattle, WA",
            "Portland, OR",
        ],
        workplace_type=[
            "hybrid",
            "remote",
        ],
    )

    response = save_preferences(
        preferences_client,
        headers,
        reordered,
    )
    assert response.status_code == 200, response.text

    response = preferences_client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text
    assert response.json() == original


# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Write an isolated integration test for JH-018 that creates
# its own test job and match results, includes first_seen_at required
# by migration 002, checks recalculation on meaningful changes,
# and verifies user isolation.
# Reviewed and adapted for the CS467 Job Hunting AI project.


@pytest.mark.parametrize("change", [
    {"job_titles": ["Backend Developer"]},
    {"strict_location": True},
    {"strict_workplace": True},
    {"strict_salary": True},
])
def test_preferences_change_marks_matches_for_recalculation(preferences_client, change):
    """Changing preferences flags only the current user's matches."""
    client = preferences_client
    user_a, email_a, headers_a = register_and_login(client)
    initial_data = sample_preferences()

    response = save_preferences(client, headers_a, initial_data)
    assert response.status_code == 200, response.text

    user_b, _, headers_b = register_and_login(client)
    response = save_preferences(client, headers_b, initial_data)
    assert response.status_code == 200, response.text

    # Use the same isolated test database as the API.
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
    settings = get_settings(env)

    # Create a test job and matches for both users.
    with transaction(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO jobs (
                    external_job_id,
                    source,
                    title,
                    description,
                    job_url,
                    retrieved_at,
                    first_seen_at
                )
                VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    f"test-{uuid4().hex}",
                    "test",
                    "Software Engineer",
                    "Integration test job",
                    "https://example.com/test-job",
                ),
            )

            job_id = cursor.lastrowid

            for user_id in (user_a, user_b):
                cursor.execute(
                    """
                    INSERT INTO match_results (
                        user_id,
                        job_id,
                        match_score,
                        match_explanation,
                        needs_recalculation
                    )
                    VALUES (%s, %s, %s, %s, FALSE)
                    """,
                    (
                        user_id,
                        job_id,
                        85,
                        "Integration test match",
                    ),
                )

    def read_flags():
        """Read both users' recalculation flags."""
        with transaction(settings) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, needs_recalculation
                    FROM match_results
                    WHERE job_id = %s
                    """,
                    (job_id,),
                )
                return {
                    row["user_id"]: row["needs_recalculation"]
                    for row in cursor.fetchall()
                }

    assert read_flags() == {
        user_a: 0,
        user_b: 0,
    }

    # Log back in as user A.
    response = client.post(
        "/api/auth/login",
        json={
            "email": email_a,
            "password": TEST_PASSWORD,
        },
    )
    assert response.status_code == 200, response.text

    response = client.get("/api/auth/csrf")
    assert response.status_code == 200, response.text

    headers_a["X-CSRF-Token"] = response.json()["csrf_token"]

    # Identical preferences must not trigger recalculation.
    response = save_preferences(client, headers_a, initial_data)
    assert response.status_code == 200, response.text

    assert read_flags() == {
        user_a: 0,
        user_b: 0,
    }

    # Changing A's preferences must flag only A's matches.
    updated_data = sample_preferences(**change)

    response = save_preferences(client, headers_a, updated_data)
    assert response.status_code == 200, response.text

    response = client.get(PREFERENCES_URL)
    assert response.status_code == 200, response.text
    for flag in ("strict_location", "strict_workplace", "strict_salary"):
        assert response.json()[flag] is change.get(flag, False)

    assert read_flags() == {
        user_a: 1,
        user_b: 0,
    }

    # Reset A's flag to verify an unchanged update.
    with transaction(settings) as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                UPDATE match_results
                SET needs_recalculation = FALSE
                WHERE user_id = %s AND job_id = %s
                """,
                (user_a, job_id),
            )

    # Saving the same updated preferences must not flag again.
    response = save_preferences(client, headers_a, updated_data)
    assert response.status_code == 200, response.text

    assert read_flags() == {
        user_a: 0,
        user_b: 0,
    }
