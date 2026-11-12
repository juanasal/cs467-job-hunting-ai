
import os
import hashlib

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import authentication
from app.config import ENV_FILE, get_settings
from app.db import get_db_connection
from app.main import app


TEST_EMAIL = "testuser_lifecycle@example.com"
TEST_PASSWORD = "SecurePassword123!"


@pytest.fixture(scope="module")
def auth_client():
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
            "TEST_DB_* settings not set; "
            "skipping authentication integration test"
        )

    if (env["DB_HOST"], env["DB_NAME"]) == (
        os.environ.get("DB_HOST"),
        os.environ.get("DB_NAME"),
    ):
        pytest.fail(
            "TEST_DB_* must point at a separate test database, "
            "not the main one"
        )

    test_settings = get_settings(env)

    def test_connection():
        return get_db_connection(test_settings)

    original_get_db_connection = authentication.get_db_connection
    authentication.get_db_connection = test_connection

    try:
        with TestClient(app) as client:
            yield client
    finally:
        authentication.get_db_connection = original_get_db_connection


@pytest.fixture
def test_db_connection(auth_client):
    """Return the connection function configured for the test database."""
    return authentication.get_db_connection


def print_step_header(step_num, title):
    print("\n" + "=" * 60)
    print(f" STEP {step_num}: {title}")
    print("=" * 60)


def print_step_footer(status, details=""):
    print(f"-> STATUS: {'PASSED ✅' if status else 'FAILED ❌'}")

    if details:
        print(f"-> DETAILS: {details}")

    print("-" * 60)


def ensure_test_user(client):
    """Create the test user if it does not already exist."""
    response = client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code in (201, 409), response.text


def login_test_user(client):
    """Log in using the valid test account."""
    response = client.post(
        "/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    assert response.status_code == 200, response.text

    return response


def test_auth_full_lifecycle(auth_client):
    print("\n🚀 STARTING AUTHENTICATION LIFECYCLE TESTS")

    # -------------------------------------------------------------
    # STEP 1: Registration
    # -------------------------------------------------------------
    print_step_header(1, "POST /api/auth/register (User Registration)")

    response = auth_client.post(
        "/api/auth/register",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code in (201, 409)

    print_step_footer(
        success,
        f"Code was {response.status_code} (Acceptable: 201 or 409)",
    )

    assert success

    # -------------------------------------------------------------
    # STEP 2: Login
    # -------------------------------------------------------------
    print_step_header(2, "POST /api/auth/login (User Authentication)")

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": TEST_PASSWORD,
        },
    )

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    print(f"Cookies Set by Server: {list(auth_client.cookies.keys())}")

    success = (
        response.status_code == 200
        and "user" in response.json()
    )

    print_step_footer(
        success,
        "Session cookies successfully established.",
    )

    assert success

    # -------------------------------------------------------------
    # STEP 3: Verify active session
    # -------------------------------------------------------------
    print_step_header(3, "GET /api/auth/me (Verify Active Session)")

    response = auth_client.get("/api/auth/me")

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = (
        response.status_code == 200
        and response.json()["user"]["email"] == TEST_EMAIL
    )

    print_step_footer(
        success,
        "Authenticated user retrieved successfully.",
    )

    assert success

    # -------------------------------------------------------------
    # STEP 4: Retrieve CSRF token
    # -------------------------------------------------------------
    print_step_header(4, "GET /api/auth/csrf (Retrieve CSRF Token)")

    response = auth_client.get("/api/auth/csrf")
    data = response.json()
    csrf_token = data.get("csrf_token")

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {data}")

    success = (
        response.status_code == 200
        and csrf_token is not None
    )

    print_step_footer(
        success,
        "CSRF token successfully retrieved.",
    )

    assert success

    # -------------------------------------------------------------
    # STEP 5: Logout
    # -------------------------------------------------------------
    print_step_header(5, "POST /api/auth/logout (Revoke Session)")

    response = auth_client.post(
        "/api/auth/logout",
        headers={
            "Origin": "http://localhost:3000",
            "X-CSRF-Token": csrf_token,
        },
    )

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")
    print(f"Remaining Cookies: {list(auth_client.cookies.keys())}")

    success = (
        response.status_code == 200
        and response.json() == {
            "message": "Logged out successfully."
        }
    )

    print_step_footer(
        success,
        "Session revoked and cookies cleared.",
    )

    assert success

    # -------------------------------------------------------------
    # STEP 6: Verify logout
    # -------------------------------------------------------------
    print_step_header(6, "GET /api/auth/me (Post-Logout Check)")

    response = auth_client.get("/api/auth/me")

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 401

    print_step_footer(
        success,
        "Revoked session rejected with 401.",
    )

    assert success

    print("\n🎉 AUTHENTICATION LIFECYCLE TEST COMPLETED!\n")


def test_login_wrong_password(auth_client):
    """Incorrect passwords must not authenticate users."""
    print_step_header(7, "POST /api/auth/login (Incorrect Password)")

    auth_client.cookies.clear()
    ensure_test_user(auth_client)

    response = auth_client.post(
        "/api/auth/login",
        json={
            "email": TEST_EMAIL,
            "password": "WrongPassword123!",
        },
    )

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 401

    print_step_footer(
        success,
        "Incorrect password rejected with 401 Unauthorized.",
    )

    assert response.status_code == 401


def test_altered_session_cookie(auth_client):
    """An altered session token must not authenticate a user."""
    print_step_header(8, "GET /api/auth/me (Altered Session Cookie)")

    auth_client.cookies.clear()
    ensure_test_user(auth_client)
    login_test_user(auth_client)

    cookie_name = authentication.COOKIE_NAME
    original_token = auth_client.cookies.get(cookie_name)

    assert original_token, "Login did not establish a session cookie."

    # Replace the valid session token with an invalid token.
    auth_client.cookies.set(
        cookie_name,
        "altered-invalid-session-token",
    )

    response = auth_client.get("/api/auth/me")

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 401

    print_step_footer(
        success,
        "Altered session token rejected with 401 Unauthorized.",
    )

    assert response.status_code == 401


def test_expired_session(auth_client, test_db_connection):
    """A session with an expired database timestamp must be rejected."""
    print_step_header(9, "GET /api/auth/me (Expired Session)")

    auth_client.cookies.clear()
    ensure_test_user(auth_client)
    login_test_user(auth_client)

    cookie_name = authentication.COOKIE_NAME
    session_token = auth_client.cookies.get(cookie_name)

    assert session_token, "Login did not establish a session cookie."

    # The database stores a hash of the session token.
    token_hash = hashlib.sha256(
        session_token.encode("utf-8")
    ).hexdigest()

    # Expire the session in the isolated test database.
    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET expires_at = DATE_SUB(
                    UTC_TIMESTAMP(),
                    INTERVAL 1 DAY
                )
                WHERE token_hash = %s
                  AND revoked_at IS NULL
                """,
                (token_hash,),
            )

            updated_rows = cursor.rowcount

        connection.commit()

    assert updated_rows == 1, (
        "Expected to find and expire exactly one active test session."
    )

    # The cookie is still present, but the database session is expired.
    response = auth_client.get("/api/auth/me")

    print(f"Response Status Code: {response.status_code}")
    print(f"Response Body: {response.json()}")

    success = response.status_code == 401

    print_step_footer(
        success,
        "Expired session rejected with 401 Unauthorized.",
    )

    assert response.status_code == 401
