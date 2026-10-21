import pytest
from fastapi.testclient import TestClient

from app.config import SettingsError, get_settings
from app.main import app

# Not using "with TestClient(app)" means startup (settings loading) is skipped,
# so these tests don't need a real backend/.env.
client = TestClient(app, raise_server_exceptions=False)

VALID_ENV = {
    "DB_HOST": "localhost",
    "DB_PORT": "3306",
    "DB_NAME": "job_hunting_ai",
    "DB_USER": "tester",
    "DB_PASSWORD": "super-secret-password",
}


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_docs_open():
    assert client.get("/docs").status_code == 200


def test_unknown_route_uses_error_format():
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.json() == {"error": {"status": 404, "message": "Not Found"}}


def test_unexpected_error_hides_details():
    @app.get("/test-unexpected-error")
    def boom():
        raise RuntimeError("internal detail that should not leak")

    response = client.get("/test-unexpected-error")
    assert response.status_code == 500
    assert response.json() == {"error": {"status": 500, "message": "Internal server error"}}


def test_settings_load_from_env():
    settings = get_settings(VALID_ENV)
    assert settings.db_port == 3306
    assert "super-secret-password" not in repr(settings)


def test_missing_settings_are_named_without_values():
    env = {**VALID_ENV, "DB_USER": "", "DB_NAME": "   "}
    del env["DB_HOST"]
    with pytest.raises(SettingsError) as exc_info:
        get_settings(env)
    message = str(exc_info.value)
    assert "DB_HOST" in message and "DB_NAME" in message and "DB_USER" in message
    assert "DB_PASSWORD" not in message
    assert "super-secret-password" not in message


def test_invalid_port_is_readable():
    with pytest.raises(SettingsError, match="DB_PORT must be a whole number"):
        get_settings({**VALID_ENV, "DB_PORT": "abc"})
