
import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

import pymysql.cursors
from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    Header,
    HTTPException,
    Request,
    Response,
    status,
)
from pydantic import BaseModel, Field
from pwdlib import PasswordHash
from pymysql.err import IntegrityError

from app.config import get_frontend_origins, load_environment
from app.db import get_db_connection

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

# Explicitly use Argon2id via pwdlib configuration/recommended factory.
password_hash = PasswordHash.recommended()

# Session configuration.
IDLE_TIMEOUT_MINUTES = 30
MAX_SESSION_DAYS = 7


def get_cookie_settings(env=None):
    """Resolve cookie settings after loading backend/.env when env is omitted."""
    if env is None:
        env = load_environment()

    app_env = env.get("APP_ENV", "development").strip().lower()
    production = app_env == "production"
    cookie_name = "__Host-session" if production else "session"
    return app_env, production, cookie_name


# Load backend/.env before reading APP_ENV. Process environment values still win.
APP_ENV, PRODUCTION, COOKIE_NAME = get_cookie_settings()


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=128)


def normalize_email(email: str) -> str:
    email = email.strip().lower()

    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a valid email address.",
        )

    return email


# ==========================================
# DEPENDENCIES: Session Validation & CSRF
# ==========================================

def get_current_user(
    session: str | None = Cookie(default=None, alias=COOKIE_NAME)
) -> dict:
    """
    Validates server-side sessions stored in MySQL.
    Enforces absolute lifetime (7 days) and idle timeout (30 minutes).
    Locks the session row while validating and refreshing activity so logout
    cannot commit a revocation between the active-session check and refresh.
    Requests that already passed validation may finish after logout commits.
    """
    if not session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    token_hash = hashlib.sha256(session.encode("utf-8")).hexdigest()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(cursor=pymysql.cursors.DictCursor)

            try:
                cursor.execute(
                    """
                    SELECT s.session_id, s.user_id, s.created_at,
                           s.last_activity_at, s.expires_at,
                           u.email
                    FROM user_sessions s
                    JOIN users u ON s.user_id = u.user_id
                    WHERE s.token_hash = %s
                      AND s.revoked_at IS NULL
                    FOR UPDATE
                    """,
                    (token_hash,),
                )

                db_session = cursor.fetchone()

                if not db_session:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or revoked session.",
                    )

                # 1. Check absolute expiration (maximum session lifetime: 7 days).
                if db_session["expires_at"] <= now:
                    cursor.execute(
                        "DELETE FROM user_sessions WHERE session_id = %s",
                        (db_session["session_id"],),
                    )
                    connection.commit()

                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session has expired.",
                    )

                # 2. Check idle timeout (30 minutes).
                idle_limit = db_session["last_activity_at"] + timedelta(
                    minutes=IDLE_TIMEOUT_MINUTES
                )

                if idle_limit <= now:
                    cursor.execute(
                        "DELETE FROM user_sessions WHERE session_id = %s",
                        (db_session["session_id"],),
                    )
                    connection.commit()

                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Session timed out due to inactivity.",
                    )

                # 3. Update sliding last_activity_at window.
                cursor.execute(
                    """
                    UPDATE user_sessions
                    SET last_activity_at = %s
                    WHERE session_id = %s
                      AND revoked_at IS NULL
                    """,
                    (now, db_session["session_id"]),
                )

                if cursor.rowcount != 1:
                    connection.rollback()
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Invalid or revoked session.",
                    )

                connection.commit()

                return {
                    "user_id": db_session["user_id"],
                    "email": db_session["email"],
                }

            finally:
                cursor.close()

    except HTTPException:
        raise

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during session validation.",
        ) from None


def verify_csrf_and_origin(
    request: Request,
    x_csrf_token: str | None = Header(default=None),
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
):
    """
    Validates the Origin header against configured frontend origins and
    enforces Double Submit Cookie verification for state-changing requests.
    """
    origin = request.headers.get("Origin")
    trusted_origins = get_frontend_origins()

    # Require an Origin header and reject origins not explicitly trusted.
    if not origin or origin not in trusted_origins:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Untrusted or missing origin header.",
        )

    # CSRF Token validation via Double Submit Cookie check.
    if (
        not x_csrf_token
        or not csrf_cookie
        or not secrets.compare_digest(x_csrf_token, csrf_cookie)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token validation failed.",
        )


# ==========================================
# ENDPOINTS
# ==========================================

@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(request: RegisterRequest):
    email = normalize_email(request.email)

    # Hashed via Argon2id through pwdlib[argon2].
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
                    INSERT INTO users (email, password_hash, created_at)
                    VALUES (%s, %s, %s)
                    """,
                    (
                        email,
                        hashed_password,
                        datetime.now(timezone.utc).replace(tzinfo=None),
                    ),
                )

                user_id = cursor.lastrowid
                connection.commit()

            except IntegrityError:
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
        "user": {"user_id": user_id, "email": email},
    }


@router.post("/login")
def login(request: LoginRequest, response: Response):
    email = normalize_email(request.email)

    try:
        with get_db_connection() as connection:
            cursor = connection.cursor(cursor=pymysql.cursors.DictCursor)

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

                # Generate session and CSRF tokens.
                session_token = secrets.token_urlsafe(32)

                token_hash = hashlib.sha256(
                    session_token.encode("utf-8")
                ).hexdigest()

                csrf_token = secrets.token_urlsafe(32)

                now = datetime.now(timezone.utc).replace(tzinfo=None)
                expires_at = now + timedelta(days=MAX_SESSION_DAYS)

                # Store session in MySQL (allows multiple sessions per user).
                cursor.execute(
                    """
                    INSERT INTO user_sessions
                        (user_id, token_hash, created_at, last_activity_at, expires_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (user["user_id"], token_hash, now, now, expires_at),
                )

                connection.commit()

            finally:
                cursor.close()

    except HTTPException:
        raise

    # Set session cookie.
    response.set_cookie(
        key=COOKIE_NAME,
        value=session_token,
        httponly=True,
        secure=PRODUCTION,
        samesite="lax",
        path="/",
        max_age=MAX_SESSION_DAYS * 24 * 60 * 60,
    )

    # Set CSRF token cookie (readable by client JavaScript).
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=PRODUCTION,
        samesite="lax",
        path="/",
        max_age=MAX_SESSION_DAYS * 24 * 60 * 60,
    )

    return {
        "message": "Login successful.",
        "user": {"user_id": user["user_id"], "email": user["email"]},
    }


@router.get("/me")
def get_me(current_user: dict = Depends(get_current_user)):
    """Return the profile of the currently authenticated user."""
    return {"user": current_user}


@router.get("/csrf")
def get_csrf_token(
    response: Response,
    csrf_cookie: str | None = Cookie(default=None, alias="csrf_token"),
):
    """Ensure a CSRF token cookie exists and return it for client use."""
    if not csrf_cookie:
        csrf_token = secrets.token_urlsafe(32)

        response.set_cookie(
            key="csrf_token",
            value=csrf_token,
            httponly=False,
            secure=PRODUCTION,
            samesite="lax",
            path="/",
            max_age=MAX_SESSION_DAYS * 24 * 60 * 60,
        )

        return {"csrf_token": csrf_token}

    return {"csrf_token": csrf_cookie}


@router.post("/logout", dependencies=[Depends(verify_csrf_and_origin)])
def logout(
    response: Response,
    current_user: dict = Depends(get_current_user),
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
):
    """
    Revokes the current session from MySQL database and clears browser cookies.
    Protected against CSRF and requires valid authentication context.
    """
    if session:
        token_hash = hashlib.sha256(session.encode("utf-8")).hexdigest()
        now = datetime.now(timezone.utc).replace(tzinfo=None)

        try:
            with get_db_connection() as connection:
                cursor = connection.cursor()

                try:
                    cursor.execute(
                        """
                        UPDATE user_sessions
                        SET revoked_at = %s
                        WHERE token_hash = %s
                          AND revoked_at IS NULL
                        """,
                        (now, token_hash),
                    )

                    connection.commit()

                finally:
                    cursor.close()

        except Exception:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to log out. Please try again.",
            ) from None

    # Clear authentication and CSRF cookies.
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        secure=PRODUCTION,
        samesite="lax",
    )

    response.delete_cookie(
        key="csrf_token",
        path="/",
        secure=PRODUCTION,
        samesite="lax",
    )

    return {"message": "Logged out successfully."}
