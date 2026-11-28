"""Optional production smoke checks for the deployed Vercel/Render/Aiven path.

Run these commands from the repository root. Replace the example URL with the
public Vercel frontend URL (for example, `https://cs467-job-hunting-ai.vercel.app`):

    npm --prefix frontend/my-react-app run build

PowerShell:

    $env:DEPLOYED_FRONTEND_URL = "https://your-project.vercel.app"
    python -m pytest backend/tests/test_deployment.py -q

Bash/Zsh:

    DEPLOYED_FRONTEND_URL=https://your-project.vercel.app python -m pytest backend/tests/test_deployment.py -q

The hosted checks are skipped when DEPLOYED_FRONTEND_URL is unset. The build
artifact check uses frontend/my-react-app/dist by default and is skipped when
that directory does not exist. Set FRONTEND_BUILD_DIR to inspect another build.
"""

import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import urlopen

import pytest
from dotenv import dotenv_values


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_ROOT = REPOSITORY_ROOT / "frontend" / "my-react-app"
SECRET_NAME = re.compile(r"(PASSWORD|SECRET|TOKEN|_KEY)$", re.IGNORECASE)
PLACEHOLDERS = {"your_password", "your_database_password", "changeme", "change_me"}


def _frontend_base_url():
    value = os.getenv("DEPLOYED_FRONTEND_URL", "").strip().rstrip("/")
    if not value:
        pytest.skip("Set DEPLOYED_FRONTEND_URL to run deployed HTTPS checks.")

    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        pytest.fail("DEPLOYED_FRONTEND_URL must be an HTTPS URL.")
    return value


def _get_json(url):
    try:
        with urlopen(url, timeout=30) as response:
            assert response.status == 200, "deployment health route returned a non-200 status"
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        pytest.fail(f"Could not verify deployed health route ({type(exc).__name__}).")


def test_public_frontend_proxies_backend_health_over_https():
    base_url = _frontend_base_url()
    assert _get_json(f"{base_url}/api/health") == {"status": "ok"}


def test_hosted_backend_can_reach_mysql_through_public_frontend():
    base_url = _frontend_base_url()
    assert _get_json(f"{base_url}/api/health/db") == {
        "status": "ok",
        "database": "ok",
    }


def _configured_secret_values():
    """Read likely secret values for comparison without ever printing them."""
    configured = dict(os.environ)
    backend_env = REPOSITORY_ROOT / "backend" / ".env"
    if backend_env.is_file():
        configured.update(
            {key: value for key, value in dotenv_values(backend_env).items() if value}
        )

    values = set()
    for name, value in configured.items():
        if not SECRET_NAME.search(name) or not value or len(value) < 8:
            continue
        if value.strip().lower() in PLACEHOLDERS:
            continue
        values.add(value)
    return values


def _text_files_under(roots):
    roots = [path for path in roots if path.exists()]
    return (
        file_path
        for root in roots
        for file_path in (root.rglob("*") if root.is_dir() else (root,))
        if file_path.is_file()
    )


def _assert_no_configured_secret_values(files, secrets):
    leaked_files = []
    for file_path in files:
        try:
            contents = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if any(secret in contents for secret in secrets):
            try:
                display_path = file_path.relative_to(REPOSITORY_ROOT).as_posix()
            except ValueError:
                display_path = str(file_path)
            leaked_files.append(display_path)

    assert not leaked_files, (
        "Configured secret value(s) appear in frontend source/build files: "
        + ", ".join(leaked_files)
    )


def test_configured_secret_values_are_absent_from_frontend_source():
    secrets = _configured_secret_values()
    if not secrets:
        pytest.skip("No configured secret values are available to compare.")

    _assert_no_configured_secret_values(
        _text_files_under([FRONTEND_ROOT / "src"]), secrets
    )


def test_configured_secret_values_are_absent_from_downloadable_build_files():
    secrets = _configured_secret_values()
    if not secrets:
        pytest.skip("No configured secret values are available to compare.")

    build_dir = Path(
        os.getenv("FRONTEND_BUILD_DIR", str(FRONTEND_ROOT / "dist"))
    )
    if not build_dir.exists():
        pytest.skip("Build the frontend first to check downloadable build files.")

    _assert_no_configured_secret_values(_text_files_under([build_dir]), secrets)
