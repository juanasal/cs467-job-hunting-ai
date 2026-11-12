# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Help create integration tests for JH-017, including profile
# creation, updates, validation, authentication, user isolation,
# CSRF protection, and marking job matches for recalculation.

"""Integration tests for JH-017: Profile API."""

import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from test_auth import TEST_PASSWORD, auth_client  # noqa: F401


PROFILE_URL = "/api/profile"
ORIGIN = "http://localhost:3000"


def sample_profile(**changes):
    """Return a valid profile with optional changes."""
    profile = {
        "skills": ["Python", "SQL"],
        "education_level": "bachelor",
        "experience_level": "entry",
    }
    profile.update(changes)
    return profile


@pytest.fixture
def profile_client(auth_client, monkeypatch):
    """Configure Profile API to use the isolated test database."""
    from app.config import get_settings

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

    # TestClient startup resets app.state.settings.
    # Apply test settings after startup.
    with TestClient(app) as client:
        monkeypatch.setattr(app.state, "settings", settings)
        yield client


@pytest.fixture
def test_connection(profile_client):
    """Return a connection to the isolated test database."""
    from app import authentication

    return authentication.get_db_connection


def register_and_login(client):
    """Create a unique user and return their ID and CSRF headers."""
    email = f"jh017_{uuid4().hex}@example.com"

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

    headers = {
        "Origin": ORIGIN,
        "X-CSRF-Token": response.json()["csrf_token"],
    }

    return user_id, headers


def update_profile(client, headers, profile=None):
    """Send an authenticated profile update."""
    return client.put(
        PROFILE_URL,
        json=profile if profile is not None else sample_profile(),
        headers=headers,
    )


def test_get_requires_login(profile_client):
    """Anonymous users cannot read a profile."""
    response = profile_client.get(PROFILE_URL)

    assert response.status_code == 401


def test_put_requires_login(profile_client):
    """Anonymous users cannot update a profile."""
    response = profile_client.put(
        PROFILE_URL,
        json=sample_profile(),
    )

    assert response.status_code in (401, 403)


def test_create_and_read_profile(profile_client):
    """A saved profile can be retrieved."""
    user_id, headers = register_and_login(profile_client)

    response = update_profile(profile_client, headers)

    assert response.status_code == 200, response.text
    assert response.json()["user_id"] == user_id

    response = profile_client.get(PROFILE_URL)

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["user_id"] == user_id
    assert data["skills"] == ["Python", "SQL"]
    assert data["education_level"] == "bachelor"
    assert data["experience_level"] == "entry"


def test_update_profile(profile_client):
    """Updated profile values persist in the database."""
    _, headers = register_and_login(profile_client)

    response = update_profile(profile_client, headers)
    assert response.status_code == 200, response.text

    updated = sample_profile(
        skills=["Python", "React"],
        education_level="master",
        experience_level="mid",
    )

    response = update_profile(profile_client, headers, updated)

    assert response.status_code == 200, response.text

    response = profile_client.get(PROFILE_URL)

    assert response.status_code == 200, response.text

    data = response.json()

    assert data["skills"] == ["Python", "React"]
    assert data["education_level"] == "master"
    assert data["experience_level"] == "mid"


@pytest.mark.parametrize(
    "invalid_profile",
    [
        sample_profile(skills=[]),
        sample_profile(skills=[""]),
        sample_profile(skills=["   "]),
        sample_profile(skills=["Python", "python"]),
        sample_profile(skills=["x" * 101]),
        sample_profile(education_level="invalid"),
        sample_profile(experience_level="invalid"),
        sample_profile(skills="Python"),
    ],
)
def test_invalid_profile_rejected(profile_client, invalid_profile):
    """Invalid profile data returns a validation error."""
    _, headers = register_and_login(profile_client)

    response = update_profile(
        profile_client,
        headers,
        invalid_profile,
    )

    assert response.status_code == 422, response.text


def test_invalid_update_preserves_profile(profile_client):
    """A rejected update must not overwrite valid profile data."""
    _, headers = register_and_login(profile_client)

    response = update_profile(profile_client, headers)
    assert response.status_code == 200, response.text

    response = update_profile(
        profile_client,
        headers,
        sample_profile(skills=["Python", "python"]),
    )

    assert response.status_code == 422, response.text

    response = profile_client.get(PROFILE_URL)

    assert response.status_code == 200, response.text
    assert response.json()["skills"] == ["Python", "SQL"]


def test_put_requires_csrf(profile_client):
    """Profile updates require a valid CSRF token."""
    register_and_login(profile_client)

    response = profile_client.put(
        PROFILE_URL,
        json=sample_profile(),
    )

    assert response.status_code == 403, response.text


def test_users_cannot_access_other_profiles(profile_client, monkeypatch):
    """Each account can read and update only its own profile."""
    user_a, headers_a = register_and_login(profile_client)

    response = update_profile(
        profile_client,
        headers_a,
        sample_profile(skills=["Python"]),
    )
    assert response.status_code == 200, response.text

    # Preserve test database settings before starting another client.
    test_settings = app.state.settings

    with TestClient(app) as client_b:
        # The second client also runs lifespan.
        monkeypatch.setattr(app.state, "settings", test_settings)

        user_b, headers_b = register_and_login(client_b)

        response = update_profile(
            client_b,
            headers_b,
            sample_profile(skills=["Java"]),
        )
        assert response.status_code == 200, response.text

        # User A cannot read B's profile using a user_id parameter.
        response = profile_client.get(
            PROFILE_URL,
            params={"user_id": user_b},
        )

        assert response.status_code == 200, response.text
        assert response.json()["user_id"] == user_a
        assert response.json()["skills"] == ["Python"]

        # User A cannot modify B's profile.
        response = profile_client.put(
            PROFILE_URL,
            params={"user_id": user_b},
            json=sample_profile(skills=["Go"]),
            headers=headers_a,
        )

        assert response.status_code == 200, response.text
        assert response.json()["user_id"] == user_a

        # User B's profile must remain unchanged.
        response = client_b.get(PROFILE_URL)

        assert response.status_code == 200, response.text
        assert response.json()["user_id"] == user_b
        assert response.json()["skills"] == ["Java"]

        # Only User A's profile was updated.
        response = profile_client.get(PROFILE_URL)

        assert response.status_code == 200, response.text
        assert response.json()["skills"] == ["Go"]


def test_profile_change_marks_matches_for_recalculation(
    profile_client,
    test_connection,
):
    """Changing a profile marks existing match results as stale."""
    user_id, headers = register_and_login(profile_client)

    response = update_profile(profile_client, headers)
    assert response.status_code == 200, response.text

    external_job_id = f"jh017-test-{uuid4().hex}"
    job_id = None

    try:
        # Create a temporary job in the test database.
        with test_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO jobs (
                        external_job_id,
                        source,
                        title,
                        company,
                        description,
                        job_url,
                        retrieved_at,
                        first_seen_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, NOW(), NOW()
                    )
                    """,
                    (
                        external_job_id,
                        "test",
                        "Software Engineer",
                        "Test Company",
                        "Temporary job for profile API testing.",
                        "https://example.com/test-job",
                    ),
                )
                job_id = cursor.lastrowid

                # Create an existing match that is not stale.
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
                        80,
                        "Test match",
                    ),
                )

            connection.commit()

        # Updating skills should mark the existing match as stale.
        updated = sample_profile(skills=["Python", "React"])

        response = update_profile(
            profile_client,
            headers,
            updated,
        )

        assert response.status_code == 200, response.text

        with test_connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT needs_recalculation
                    FROM match_results
                    WHERE user_id = %s AND job_id = %s
                    """,
                    (user_id, job_id),
                )
                result = cursor.fetchone()

        assert result is not None
        assert result["needs_recalculation"] == 1

    finally:
        # Remove temporary data even if the test fails.
        if job_id is not None:
            with test_connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        DELETE FROM match_result_skills
                        WHERE user_id = %s AND job_id = %s
                        """,
                        (user_id, job_id),
                    )

                    cursor.execute(
                        """
                        DELETE FROM match_results
                        WHERE user_id = %s AND job_id = %s
                        """,
                        (user_id, job_id),
                    )

                    cursor.execute(
                        """
                        DELETE FROM jobs
                        WHERE job_id = %s
                        """,
                        (job_id,),
                    )

                connection.commit()
