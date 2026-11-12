
"""Load backend settings from environment variables (or backend/.env)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

REQUIRED_SETTINGS = (
    "DB_HOST",
    "DB_PORT",
    "DB_NAME",
    "DB_USER",
    "DB_PASSWORD",
)

DEFAULT_FRONTEND_ORIGINS = ("http://localhost:3000",)


class SettingsError(RuntimeError):
    """Raised when settings are missing or invalid.

    Messages only name the setting, never its value, so secrets are not exposed.
    """


@dataclass(frozen=True)
class Settings:
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str = field(repr=False)
    db_ssl_ca: str | None = None
    frontend_origins: tuple[str, ...] = DEFAULT_FRONTEND_ORIGINS


def load_environment():
    """Load backend/.env and return the process environment."""
    load_dotenv(ENV_FILE)
    return os.environ


def get_frontend_origins(env=None):
    """Return the configured frontend origins."""
    if env is None:
        env = load_environment()

    raw_origins = env.get(
        "FRONTEND_ORIGINS",
        ",".join(DEFAULT_FRONTEND_ORIGINS),
    )

    origins = tuple(
        origin.strip().rstrip("/")
        for origin in raw_origins.split(",")
        if origin.strip()
    )

    if not origins:
        raise SettingsError(
            "FRONTEND_ORIGINS must contain at least one frontend origin."
        )

    return origins


def get_settings(env=None):
    """Return Settings, or raise SettingsError naming what needs fixing.

    By default reads backend/.env (if present) and then the process environment.
    Variables already set in the environment take priority over the .env file.
    """
    if env is None:
        env = load_environment()

    missing = [
        name
        for name in REQUIRED_SETTINGS
        if not env.get(name, "").strip()
    ]

    if missing:
        raise SettingsError(
            f"Missing required settings: {', '.join(missing)}. "
            "Copy backend/.env.example to backend/.env and fill them in."
        )

    try:
        db_port = int(env["DB_PORT"])
    except ValueError:
        raise SettingsError(
            "DB_PORT must be a whole number, e.g. 3306."
        ) from None

    return Settings(
        db_host=env["DB_HOST"],
        db_port=db_port,
        db_name=env["DB_NAME"],
        db_user=env["DB_USER"],
        db_password=env["DB_PASSWORD"],
        db_ssl_ca=env.get("DB_SSL_CA", "").strip() or None,
        frontend_origins=get_frontend_origins(env),
    )
