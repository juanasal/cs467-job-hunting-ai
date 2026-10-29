
import re
import mysql.connector
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from pwdlib import PasswordHash

from app.database import get_db_connection

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Response

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
password_hash = PasswordHash.recommended()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


def normalize_email(email: str) -> str:
    email = email.strip().lower()

    # Basic email format validation.
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )

    return email


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    email = normalize_email(request.email)

    # Hash the password before storing it.
    hashed_password = password_hash.hash(request.password)

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor()

            try:
                cursor.execute(
                    "SELECT user_id FROM users WHERE email = %s",
                    (email,),
                )

                if cursor.fetchone():
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="An account with this email already exists.",
                    )

                cursor.execute(
                    """
                    INSERT INTO users (email, password_hash)
                    VALUES (%s, %s)
                    """,
                    (email, hashed_password),
                )

                user_id = cursor.lastrowid
                connection.commit()

            except mysql.connector.IntegrityError:
                # Also handles a concurrent registration for the same email.
                connection.rollback()
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="An account with this email already exists.",
                ) from None

            finally:
                cursor.close()

    except HTTPException:
        raise

    return {
        "message": "Account created successfully.",
        "user": {
            "user_id": user_id,
            "email": email,
        },
    }

class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)



@router.post("/login")
def login(request: LoginRequest, response: Response):
    email = normalize_email(request.email)

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(dictionary=True)

            try:
                cursor.execute(
                    """
                    SELECT user_id, email, password_hash
                    FROM users
                    WHERE email = %s
                    """,
                    (email,),
                )
                user = cursor.fetchone()

                if not user or not password_hash.verify(
                    request.password, user["password_hash"]
                ):
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid email or password.",
                    )

                # Generate a cryptographically random session token.
                session_token = secrets.token_urlsafe(32)
                token_hash = hashlib.sha256(
                    session_token.encode("utf-8")
                ).hexdigest()

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                expires_at = now + timedelta(days=7)

                cursor.execute(
                    """
                    INSERT INTO user_sessions
                        (user_id, token_hash, created_at,
                         last_activity_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        user["user_id"],
                        token_hash,
                        now,
                        now,
                        expires_at,
                    ),
                )
                connection.commit()

            finally:
                cursor.close()

    except HTTPException:
        raise

    # Use the secure __Host- cookie in production over HTTPS.
    # For local HTTP development, use a different cookie name.
    import os

    production = os.getenv("APP_ENV") == "production"
    cookie_name = "__Host-session" if production else "session"

    response.set_cookie(
        key=cookie_name,
        value=session_token,
        httponly=True,
        secure=production,
        samesite="lax",
        path="/",
        max_age=7 * 24 * 60 * 60,
    )

    return {
        "message": "Login successful.",
        "user": {
            "user_id": user["user_id"],
            "email": user["email"],
        },
    }

