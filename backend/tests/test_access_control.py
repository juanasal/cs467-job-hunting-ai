"""JH-011: users can read and change only their own private records.

Uses a throwaway test_private_records table and a test-only route so this
does not depend on the profile/preferences APIs. The route takes the user
from get_current_user (the session cookie) and ignores any user_id the
client sends, which is the pattern real protected routes should follow.
"""

import pytest
from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel

from app import authentication
from app.authentication import get_current_user
from app.main import app

# Reuse the TEST_DB_* setup from the authentication tests.
from test_auth import TEST_PASSWORD, auth_client  # noqa: F401

EMAIL_A = "access_user_a@example.com"
EMAIL_B = "access_user_b@example.com"

router = APIRouter(prefix="/test/private-record")


class RecordUpdate(BaseModel):
    note: str


@router.get("")
def read_own_record(current_user: dict = Depends(get_current_user)):
    with authentication.get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT note FROM test_private_records WHERE user_id = %s",
                (current_user["user_id"],),
            )
            row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Record not found.")

    return {"user_id": current_user["user_id"], "note": row["note"]}


@router.put("")
def update_own_record(
    body: RecordUpdate,
    current_user: dict = Depends(get_current_user),
):
    with authentication.get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO test_private_records (user_id, note)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE note = VALUES(note)
                """,
                (current_user["user_id"], body.note),
            )
        connection.commit()

    return {"user_id": current_user["user_id"], "note": body.note}


@pytest.fixture(scope="module")
def test_app(auth_client):  # noqa: F811
    """Small app with the auth routes and the private-record route."""
    with authentication.get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS test_private_records (
                    user_id INT UNSIGNED NOT NULL PRIMARY KEY,
                    note    VARCHAR(255) NOT NULL
                )
                """
            )
        connection.commit()

    isolated_app = FastAPI(exception_handlers=app.exception_handlers)
    isolated_app.include_router(authentication.router)
    isolated_app.include_router(router)

    yield isolated_app

    with authentication.get_db_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS test_private_records")
        connection.commit()


def logged_in_client(test_app, email):
    """Return (client, user_id) for a registered, logged-in account."""
    client = TestClient(test_app)

    response = client.post(
        "/api/auth/register",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code in (201, 409), response.text

    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": TEST_PASSWORD},
    )
    assert response.status_code == 200, response.text

    return client, response.json()["user"]["user_id"]


@pytest.fixture
def two_users(test_app):
    """Log in accounts A and B, each with their own private record."""
    client_a, user_a = logged_in_client(test_app, EMAIL_A)
    client_b, user_b = logged_in_client(test_app, EMAIL_B)

    assert client_a.put("/test/private-record", json={"note": "A's note"}).status_code == 200
    assert client_b.put("/test/private-record", json={"note": "B's note"}).status_code == 200

    return client_a, user_a, client_b, user_b


def test_requires_login(test_app):
    client = TestClient(test_app)

    assert client.get("/test/private-record").status_code == 401
    assert client.put(
        "/test/private-record", json={"note": "no login"}
    ).status_code == 401


def test_user_cannot_read_other_users_record(two_users):
    client_a, user_a, client_b, user_b = two_users

    # A asks for B's record by user ID; the session decides whose record it is.
    response = client_a.get(
        "/test/private-record", params={"user_id": user_b}
    )

    assert response.status_code == 200
    assert response.json() == {"user_id": user_a, "note": "A's note"}


def test_user_cannot_change_other_users_record(two_users):
    client_a, user_a, client_b, user_b = two_users

    # A tries to target B by sending B's user ID in the query and body.
    response = client_a.put(
        "/test/private-record",
        params={"user_id": user_b},
        json={"user_id": user_b, "note": "changed by A"},
    )

    assert response.status_code == 200
    assert response.json()["user_id"] == user_a

    # B's record is unchanged; only A's own record was updated.
    response = client_b.get("/test/private-record")
    assert response.json() == {"user_id": user_b, "note": "B's note"}

    response = client_a.get("/test/private-record")
    assert response.json() == {"user_id": user_a, "note": "changed by A"}
