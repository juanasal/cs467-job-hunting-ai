"""Load backend settings from environment variables (or backend/.env)."""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

REQUIRED_SETTINGS = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")


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
    # repr=False keeps the password out of logs if Settings is ever printed.
    db_password: str = field(repr=False)
    # Optional path to the server's CA certificate (needed for Aiven, which requires SSL).
    db_ssl_ca: str | None = None


def get_settings(env=None):
    """Return Settings, or raise SettingsError naming what needs fixing.

    By default reads backend/.env (if present) and then the process environment.
    Variables already set in the environment take priority over the .env file.
    """
    if env is None:
        load_dotenv(ENV_FILE)
        env = os.environ

    missing = [name for name in REQUIRED_SETTINGS if not env.get(name, "").strip()]
    if missing:
        raise SettingsError(
            f"Missing required settings: {', '.join(missing)}. "
            "Copy backend/.env.example to backend/.env and fill them in."
        )

    try:
        db_port = int(env["DB_PORT"])
    except ValueError:
        raise SettingsError("DB_PORT must be a whole number, e.g. 3306.") from None

    return Settings(
        db_host=env["DB_HOST"],
        db_port=db_port,
        db_name=env["DB_NAME"],
        db_user=env["DB_USER"],
        db_password=env["DB_PASSWORD"],
        db_ssl_ca=env.get("DB_SSL_CA", "").strip() or None,
    )
