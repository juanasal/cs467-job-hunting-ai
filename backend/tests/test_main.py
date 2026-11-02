import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import SettingsError, get_settings
from app.main import app
import app.config as config

# Not using "with TestClient(app)" means startup (settings loading) is skipped,
# so these tests don't need a real backend/.env.
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def isolated_app():
    """Exercise production handlers without adding routes to the shared app."""
    test_app = FastAPI(exception_handlers=app.exception_handlers)
    return test_app


@pytest.fixture
def startup_env(monkeypatch, tmp_path):
    # Prevent a developer's .env from masking missing settings.
    monkeypatch.setattr(config, "ENV_FILE", tmp_path / ".env")
    for name, value in VALID_ENV.items():
        monkeypatch.setenv(name, value)

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


def test_unexpected_error_hides_details(isolated_app):
    @isolated_app.get("/test-unexpected-error")
    def boom():
        raise RuntimeError("internal detail that should not leak")

    with TestClient(isolated_app, raise_server_exceptions=False) as test_client:
        response = test_client.get("/test-unexpected-error")
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


def test_startup_loads_settings(startup_env):
    with TestClient(app) as test_client:
        assert app.state.settings.db_port == 3306
        assert app.state.settings.db_user == "tester"
        assert test_client.get("/health").json() == {"status": "ok"}


@pytest.mark.parametrize("setting", config.REQUIRED_SETTINGS)
def test_startup_rejects_missing_setting(startup_env, monkeypatch, setting):
    monkeypatch.delenv(setting)
    with pytest.raises(SettingsError, match=setting) as error:
        with TestClient(app):
            pytest.fail("Startup should reject missing configuration")
    assert VALID_ENV["DB_PASSWORD"] not in str(error.value)


def test_startup_rejects_invalid_port(startup_env, monkeypatch):
    monkeypatch.setenv("DB_PORT", "invalid-secret-value")
    with pytest.raises(SettingsError, match="DB_PORT must be a whole number") as error:
        with TestClient(app):
            pytest.fail("Startup should reject an invalid port")
    assert "invalid-secret-value" not in str(error.value)


def test_validation_error_omits_submitted_input(isolated_app):
    @isolated_app.get("/validated")
    def validated(count: int):
        return {"count": count}

    with TestClient(isolated_app) as test_client:
        response = test_client.get("/validated", params={"count": "private-input"})
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["status"] == 422
    assert error["message"] == "Request validation failed"
    assert error["details"][0]["loc"] == ["query", "count"]
    assert set(error["details"][0]) == {"loc", "message", "type"}
    assert "private-input" not in response.text


def test_http_error_preserves_headers(isolated_app):
    @isolated_app.get("/protected")
    def protected():
        raise HTTPException(401, "Authentication required", headers={"WWW-Authenticate": "Bearer"})

    with TestClient(isolated_app) as test_client:
        response = test_client.get("/protected")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"
    assert response.json() == {"error": {"status": 401, "message": "Authentication required"}}


def test_method_not_allowed_uses_error_format():
    response = client.post("/health")
    assert response.status_code == 405
    assert response.json() == {"error": {"status": 405, "message": "Method Not Allowed"}}
