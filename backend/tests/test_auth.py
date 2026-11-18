"""Database-backed tests for authentication and server-side sessions.

These tests require an isolated MySQL database configured with TEST_DB_*.
They intentionally use the real FastAPI routes and the test database.
"""

import hashlib
import os
import secrets

import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient

from app import authentication
from app.config import ENV_FILE, get_settings
from app.db import get_db_connection
from app.main import app


TEST_EMAIL = "testuser_lifecycle@example.com"
TEST_PASSWORD = "SecurePassword123!"
TRUSTED_ORIGIN = "http://localhost:3000"


@pytest.fixture(scope="module")
def auth_client():
    """Run the app against TEST_DB_* and refuse to use the application DB."""
    load_dotenv(ENV_FILE)

    names = (
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
        "DB_SSL_CA",
    )
    env = {name: os.environ.get(f"TEST_{name}", "") for name in names}

    if not env["DB_NAME"]:
        pytest.skip(
            "TEST_DB_* settings not set; skipping authentication integration tests"
        )

    if (env["DB_HOST"], env["DB_NAME"]) == (
        os.environ.get("DB_HOST"),
        os.environ.get("DB_NAME"),
    ):
        pytest.fail(
            "TEST_DB_* must point at a separate test database, not the main one"
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


@pytest.fixture(autouse=True)
def clear_client_cookies(auth_client):
    """Prevent a prior test's browser cookies from affecting the next test."""
    auth_client.cookies.clear()
    yield
    auth_client.cookies.clear()


@pytest.fixture
def test_db_connection(auth_client):
    """Return the connection factory patched to the isolated test database."""
    return authentication.get_db_connection


def ensure_test_user(client):
    response = client.post(
        "/api/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert response.status_code in (201, 409), response.text


def login_test_user(client, password=TEST_PASSWORD, email=TEST_EMAIL):
    return client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )


def login_with_session(client):
    ensure_test_user(client)
    response = login_test_user(client)
    assert response.status_code == 200, response.text
    token = response.cookies.get(authentication.COOKIE_NAME)
    csrf = response.cookies.get("csrf_token")
    assert token, "Successful login did not set the session cookie."
    assert csrf, "Successful login did not set the CSRF cookie."
    return token, csrf, response


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def fetch_session(connection_factory, token):
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT session_id, user_id, created_at, last_activity_at,
                       expires_at, revoked_at
                FROM user_sessions
                WHERE token_hash = %s
                """,
                (token_digest(token),),
            )
            return cursor.fetchone()


def count_sessions_for_test_user(connection_factory):
    with connection_factory() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(*) AS session_count
                FROM user_sessions s
                JOIN users u ON u.user_id = s.user_id
                WHERE u.email = %s
                """,
                (TEST_EMAIL,),
            )
            return cursor.fetchone()["session_count"]


def test_auth_full_lifecycle(auth_client):
    """Registration, successful login, protected access, CSRF, and logout."""
    registration = auth_client.post(
        "/api/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert registration.status_code in (201, 409), registration.text

    login = login_test_user(auth_client)
    assert login.status_code == 200, login.text
    assert login.json()["user"]["email"] == TEST_EMAIL
    original_token = login.cookies.get(authentication.COOKIE_NAME)
    csrf_token = login.cookies.get("csrf_token")
    assert original_token
    assert csrf_token

    me = auth_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == TEST_EMAIL

    logout = auth_client.post(
        "/api/auth/logout",
        headers={"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": csrf_token},
    )
    assert logout.status_code == 200, logout.text
    assert logout.json() == {"message": "Logged out successfully."}
    assert auth_client.cookies.get(authentication.COOKIE_NAME) is None
    assert auth_client.cookies.get("csrf_token") is None

    # Replay the exact original token. This proves server-side revocation,
    # independently of the browser cookie deletion response.
    replay = auth_client.get(
        "/api/auth/me",
        headers={"Cookie": f"{authentication.COOKIE_NAME}={original_token}"},
    )
    assert replay.status_code == 401


def test_login_wrong_password(auth_client, test_db_connection):
    ensure_test_user(auth_client)
    before = count_sessions_for_test_user(test_db_connection)

    response = login_test_user(auth_client, password="WrongPassword123!")

    assert response.status_code == 401
    assert response.cookies.get(authentication.COOKIE_NAME) is None
    assert count_sessions_for_test_user(test_db_connection) == before


def test_login_unknown_email(auth_client, test_db_connection):
    unknown_email = f"unknown_{secrets.token_hex(8)}@example.com"
    before = count_sessions_for_test_user(test_db_connection)

    response = login_test_user(
        auth_client,
        email=unknown_email,
        password=TEST_PASSWORD,
    )

    assert response.status_code == 401
    assert response.cookies.get(authentication.COOKIE_NAME) is None
    assert response.cookies.get("csrf_token") is None
    assert count_sessions_for_test_user(test_db_connection) == before


def test_successful_login_creates_session_and_cookie(auth_client, test_db_connection):
    ensure_test_user(auth_client)

    response = login_test_user(auth_client)

    assert response.status_code == 200
    token = response.cookies.get(authentication.COOKIE_NAME)
    assert token
    assert response.cookies.get("csrf_token")

    stored_session = fetch_session(test_db_connection, token)
    assert stored_session is not None
    assert stored_session["revoked_at"] is None
    assert stored_session["expires_at"] > stored_session["created_at"]

    set_cookie_headers = response.headers.get_list("set-cookie")
    session_header = next(
        header for header in set_cookie_headers
        if header.startswith(f"{authentication.COOKIE_NAME}=")
    )
    assert "httponly" in session_header.lower()
    assert "path=/" in session_header.lower()


def test_altered_session_cookie_is_rejected(auth_client):
    login_with_session(auth_client)

    # An explicit Cookie header replaces the client's cookie jar for this
    # request, so the original valid cookie cannot be sent alongside it.
    response = auth_client.get(
        "/api/auth/me",
        headers={
            "Cookie": f"{authentication.COOKIE_NAME}=altered-invalid-session-token"
        },
    )
    assert response.status_code == 401


def test_expired_session_is_rejected(auth_client, test_db_connection):
    token, _, _ = login_with_session(auth_client)

    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET expires_at = DATE_SUB(UTC_TIMESTAMP(), INTERVAL 1 SECOND)
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_digest(token),),
            )
            assert cursor.rowcount == 1
        connection.commit()

    response = auth_client.get("/api/auth/me")
    assert response.status_code == 401


def test_expiration_boundary_is_rejected(auth_client, test_db_connection):
    token, _, _ = login_with_session(auth_client)

    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            # The endpoint checks expires_at <= its current UTC timestamp.
            cursor.execute(
                """
                UPDATE user_sessions
                SET expires_at = UTC_TIMESTAMP()
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_digest(token),),
            )
            assert cursor.rowcount == 1
        connection.commit()

    response = auth_client.get("/api/auth/me")
    assert response.status_code == 401


def test_idle_timeout_boundary_is_rejected(auth_client, test_db_connection):
    token, _, _ = login_with_session(auth_client)

    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET last_activity_at = DATE_SUB(
                    UTC_TIMESTAMP(), INTERVAL 30 MINUTE
                )
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_digest(token),),
            )
            assert cursor.rowcount == 1
        connection.commit()

    response = auth_client.get("/api/auth/me")
    assert response.status_code == 401


def test_activity_refresh_does_not_extend_absolute_lifetime(
    auth_client, test_db_connection
):
    token, _, _ = login_with_session(auth_client)

    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE user_sessions
                SET last_activity_at = DATE_SUB(
                    UTC_TIMESTAMP(), INTERVAL 20 MINUTE
                )
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_digest(token),),
            )
            assert cursor.rowcount == 1
        connection.commit()

    before = fetch_session(test_db_connection, token)
    response = auth_client.get("/api/auth/me")
    assert response.status_code == 200
    after = fetch_session(test_db_connection, token)

    assert after["last_activity_at"] > before["last_activity_at"]
    assert after["expires_at"] == before["expires_at"]


@pytest.mark.parametrize(
    "failure_case",
    [
        "missing_csrf_header",
        "mismatched_csrf_header",
        "missing_csrf_cookie",
        "missing_origin",
        "untrusted_origin",
    ],
)
def test_rejected_logout_preserves_session(auth_client, failure_case):
    _, csrf_token, _ = login_with_session(auth_client)

    headers = {"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": csrf_token}
    if failure_case == "missing_csrf_header":
        headers.pop("X-CSRF-Token")
    elif failure_case == "mismatched_csrf_header":
        headers["X-CSRF-Token"] = "not-the-csrf-token"
    elif failure_case == "missing_csrf_cookie":
        auth_client.cookies.delete("csrf_token")
    elif failure_case == "missing_origin":
        headers.pop("Origin")
    elif failure_case == "untrusted_origin":
        headers["Origin"] = "https://attacker.example"

    response = auth_client.post("/api/auth/logout", headers=headers)
    assert response.status_code == 403

    # A rejected logout must not revoke the valid server-side session.
    still_authenticated = auth_client.get("/api/auth/me")
    assert still_authenticated.status_code == 200


def test_logout_of_one_session_preserves_another(
    auth_client, test_db_connection
):
    first_token, _, _ = login_with_session(auth_client)
    second_login = login_test_user(auth_client)
    assert second_login.status_code == 200
    second_token = second_login.cookies.get(authentication.COOKIE_NAME)
    second_csrf = second_login.cookies.get("csrf_token")
    assert second_token and second_token != first_token
    assert second_csrf

    logout = auth_client.post(
        "/api/auth/logout",
        headers={"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": second_csrf},
    )
    assert logout.status_code == 200

    first_session = fetch_session(test_db_connection, first_token)
    second_session = fetch_session(test_db_connection, second_token)
    assert first_session is not None and first_session["revoked_at"] is None
    assert second_session is not None and second_session["revoked_at"] is not None

    first_session_access = auth_client.get(
        "/api/auth/me",
        headers={"Cookie": f"{authentication.COOKIE_NAME}={first_token}"},
    )
    assert first_session_access.status_code == 200



def test_logout_database_failure_does_not_claim_success(auth_client, monkeypatch):
    """A failed revocation must preserve cookies and return an error."""
    login_with_session(auth_client)
    csrf_token = auth_client.cookies.get("csrf_token")
    original_factory = authentication.get_db_connection
    connection_calls = 0

    from contextlib import contextmanager

    @contextmanager
    def fail_second_connection():
        nonlocal connection_calls
        connection_calls += 1
        if connection_calls == 2:
            raise RuntimeError("simulated database failure during revocation")
        with original_factory() as connection:
            yield connection

    monkeypatch.setattr(
        authentication, "get_db_connection", fail_second_connection
    )
    response = auth_client.post(
        "/api/auth/logout",
        headers={"Origin": TRUSTED_ORIGIN, "X-CSRF-Token": csrf_token},
    )

    assert response.status_code == 500
    assert auth_client.cookies.get(authentication.COOKIE_NAME)
    assert auth_client.cookies.get("csrf_token")

    monkeypatch.setattr(authentication, "get_db_connection", original_factory)
    still_authenticated = auth_client.get("/api/auth/me")
    assert still_authenticated.status_code == 200




def test_cookie_settings_load_app_env_before_selection(monkeypatch):
    """Cookie selection must use the environment returned by the .env loader."""
    monkeypatch.setattr(
        authentication,
        "load_environment",
        lambda: {"APP_ENV": "production"},
    )

    app_env, production, cookie_name = authentication.get_cookie_settings()

    assert app_env == "production"
    assert production is True
    assert cookie_name == "__Host-session"



    assert response.status_code == 401


# -------------------------------------------------------------
# JH-009: Registration
# -------------------------------------------------------------

REGISTER_EMAIL = "testuser_register@example.com"


def get_stored_hashes(test_db_connection, email):
    """Return the password_hash of every users row with this email."""
    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT password_hash FROM users WHERE email = %s",
                (email,),
            )
            return [row["password_hash"] for row in cursor.fetchall()]


def test_register_creates_one_account_with_hashed_password(
    auth_client, test_db_connection
):
    """A valid request creates one account and stores only a hash."""
    with test_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM users WHERE email = %s",
                (REGISTER_EMAIL,),
            )
        connection.commit()

    response = auth_client.post(
        "/api/auth/register",
        json={"email": REGISTER_EMAIL, "password": TEST_PASSWORD},
    )

    assert response.status_code == 201, response.text
    assert response.json()["user"]["email"] == REGISTER_EMAIL

    hashes = get_stored_hashes(test_db_connection, REGISTER_EMAIL)

    assert len(hashes) == 1
    assert hashes[0] != TEST_PASSWORD
    assert hashes[0].startswith("$argon2id$")
    assert authentication.password_hash.verify(TEST_PASSWORD, hashes[0])

    # Neither the password nor its hash is sent back.
    assert TEST_PASSWORD not in response.text
    assert hashes[0] not in response.text
    assert "password" not in response.text


def test_register_duplicate_email_rejected(auth_client, test_db_connection):
    """The same email (any case) cannot create a second account."""
    ensure_test_user(auth_client)

    response = auth_client.post(
        "/api/auth/register",
        json={"email": f" {TEST_EMAIL.upper()} ", "password": "OtherPassword456!"},
    )

    assert response.status_code == 409, response.text
    assert response.json()["error"]["message"] == (
        "An account with this email already exists."
    )
    assert "OtherPassword456!" not in response.text
    assert len(get_stored_hashes(test_db_connection, TEST_EMAIL)) == 1


@pytest.mark.parametrize(
    "body, expected_message, bad_field",
    [
        (
            {"email": "not-an-email", "password": TEST_PASSWORD},
            "Enter a valid email address.",
            None,
        ),
        (
            {"email": "short_pw@example.com", "password": "Short1!"},
            "Request validation failed",
            "password",
        ),
        (
            {"email": "no_pw@example.com"},
            "Request validation failed",
            "password",
        ),
        (
            {"password": TEST_PASSWORD},
            "Request validation failed",
            "email",
        ),
    ],
)
def test_register_invalid_request_rejected(
    auth_client, test_db_connection, body, expected_message, bad_field
):
    """Invalid submissions get a 422 that names the problem and no account."""
    response = auth_client.post("/api/auth/register", json=body)

    assert response.status_code == 422, response.text

    error = response.json()["error"]
    assert error["message"] == expected_message

    if bad_field:
        assert any(d["loc"][-1] == bad_field for d in error["details"])

    if "password" in body:
        assert body["password"] not in response.text

    if "email" in body:
        assert get_stored_hashes(test_db_connection, body["email"]) == []
