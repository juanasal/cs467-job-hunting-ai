import json
from pathlib import Path

import httpx2
import pytest

from app.adzuna_client import (
    ADZUNA_BASE_URL,
    AdzunaClient,
    AdzunaConfigError,
    AdzunaRequestError,
    get_adzuna_credentials,
)


VALID_ADZUNA_ENV = {
    "ADZUNA_APP_ID": "test-app-id",
    "ADZUNA_APP_KEY": "test-secret-key",
}

SAMPLE_RESPONSE_PATH = (
    Path(__file__).resolve().parents[2]
    / "documentation"
    / "samples"
    / "adzuna_search_sample.json"
)


def load_sample_response():
    with SAMPLE_RESPONSE_PATH.open(encoding="utf-8") as sample_file:
        return json.load(sample_file)


def test_adzuna_credentials_load_from_env():
    app_id, app_key = get_adzuna_credentials(VALID_ADZUNA_ENV)

    assert app_id == "test-app-id"
    assert app_key == "test-secret-key"


def test_missing_adzuna_credentials_are_named_without_values():
    env = {
        "ADZUNA_APP_ID": "",
        "ADZUNA_APP_KEY": "test-secret-key",
    }

    with pytest.raises(AdzunaConfigError) as exc_info:
        get_adzuna_credentials(env)

    message = str(exc_info.value)

    assert "ADZUNA_APP_ID" in message
    assert "test-secret-key" not in message


def test_both_missing_adzuna_credentials_are_named():
    with pytest.raises(AdzunaConfigError) as exc_info:
        get_adzuna_credentials({})

    message = str(exc_info.value)

    assert "ADZUNA_APP_ID" in message
    assert "ADZUNA_APP_KEY" in message


def test_fetch_page_sends_correct_request_using_saved_response():
    sample_response = load_sample_response()

    def handler(request):
        assert str(request.url).startswith(f"{ADZUNA_BASE_URL}/2")
        assert request.url.params["app_id"] == "test-app-id"
        assert request.url.params["app_key"] == "test-secret-key"
        assert request.url.params["what"] == "software engineer"
        assert request.url.params["where"] == "Los Angeles"

        return httpx2.Response(
            200,
            json=sample_response,
        )

    transport = httpx2.MockTransport(handler)

    with httpx2.Client(transport=transport) as http_client:
        client = AdzunaClient(
            app_id="test-app-id",
            app_key="test-secret-key",
            http_client=http_client,
        )

        result = client.fetch_page(
            page=2,
            what="software engineer",
            where="Los Angeles",
        )

    assert result == sample_response
    assert "results" in result
    assert len(result["results"]) > 0


def test_fetch_jobs_requests_multiple_pages_and_combines_results():
    requested_pages = []

    def handler(request):
        page = int(request.url.path.rstrip("/").split("/")[-1])
        requested_pages.append(page)

        return httpx2.Response(
            200,
            json={
                "results": [
                    {
                        "id": str(page),
                        "title": f"Job from page {page}",
                    }
                ]
            },
        )

    transport = httpx2.MockTransport(handler)

    with httpx2.Client(transport=transport) as http_client:
        client = AdzunaClient(
            app_id="test-app-id",
            app_key="test-secret-key",
            http_client=http_client,
        )

        jobs = client.fetch_jobs(
            pages=3,
            what="software engineer",
        )

    assert requested_pages == [1, 2, 3]
    assert len(jobs) == 3
    assert jobs[0]["title"] == "Job from page 1"
    assert jobs[2]["title"] == "Job from page 3"


def test_fetch_jobs_does_not_exceed_max_pages():
    requested_pages = []

    def handler(request):
        page = int(request.url.path.rstrip("/").split("/")[-1])
        requested_pages.append(page)

        return httpx2.Response(
            200,
            json={
                "results": [
                    {
                        "id": str(page),
                        "title": f"Job from page {page}",
                    }
                ]
            },
        )

    transport = httpx2.MockTransport(handler)

    with httpx2.Client(transport=transport) as http_client:
        client = AdzunaClient(
            app_id="test-app-id",
            app_key="test-secret-key",
            http_client=http_client,
            max_pages=2,
        )

        jobs = client.fetch_jobs(
            pages=10,
            what="software engineer",
        )

    assert requested_pages == [1, 2]
    assert len(jobs) == 2


def test_fetch_jobs_stops_when_results_are_empty():
    requested_pages = []

    def handler(request):
        page = int(request.url.path.rstrip("/").split("/")[-1])
        requested_pages.append(page)

        if page == 2:
            return httpx2.Response(
                200,
                json={"results": []},
            )

        return httpx2.Response(
            200,
            json={
                "results": [
                    {
                        "id": str(page),
                        "title": f"Job from page {page}",
                    }
                ]
            },
        )

    transport = httpx2.MockTransport(handler)

    with httpx2.Client(transport=transport) as http_client:
        client = AdzunaClient(
            app_id="test-app-id",
            app_key="test-secret-key",
            http_client=http_client,
        )

        jobs = client.fetch_jobs(
            pages=5,
            what="software engineer",
        )

    assert requested_pages == [1, 2]
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Job from page 1"


@pytest.mark.parametrize("pages", [0, -1])
def test_fetch_jobs_rejects_invalid_page_count(pages):
    client = AdzunaClient(
        app_id="test-app-id",
        app_key="test-secret-key",
    )

    with pytest.raises(ValueError, match="pages must be at least 1"):
        client.fetch_jobs(
            pages=pages,
            what="software engineer",
        )


def test_fetch_page_uses_configured_timeout():
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"results": []}

    class FakeHttpClient:
        def __init__(self):
            self.timeout = None

        def get(self, url, params=None, timeout=None):
            self.timeout = timeout
            return FakeResponse()

    http_client = FakeHttpClient()

    client = AdzunaClient(
        app_id="test-app-id",
        app_key="test-secret-key",
        http_client=http_client,
        timeout=7,
    )

    client.fetch_page(
        page=1,
        what="software engineer",
    )

    assert http_client.timeout == 7


def test_request_error_does_not_expose_credentials():
    def handler(request):
        return httpx2.Response(
            500,
            request=request,
        )

    transport = httpx2.MockTransport(handler)

    with httpx2.Client(transport=transport) as http_client:
        client = AdzunaClient(
            app_id="test-app-id",
            app_key="test-secret-key",
            http_client=http_client,
        )

        with pytest.raises(AdzunaRequestError) as exc_info:
            client.fetch_page(
                page=1,
                what="software engineer",
            )

    message = str(exc_info.value)

    assert message == "Adzuna API request failed."
    assert "test-app-id" not in message
    assert "test-secret-key" not in message

@pytest.mark.parametrize("status", [401, 429, 500])
def test_http_failures_have_safe_errors(status):
    def handler(request):
        return httpx2.Response(status, text="test-secret-key", request=request)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = AdzunaClient("test-app-id", "test-secret-key", http_client=http_client)
        with pytest.raises(AdzunaRequestError, match="^Adzuna API request failed\\.$") as error:
            client.fetch_jobs()
    assert "test-secret-key" not in str(error.value)


@pytest.mark.parametrize("failure", [httpx2.ConnectError, httpx2.ReadTimeout])
def test_network_failures_have_safe_errors(failure):
    def handler(request):
        raise failure("request contained test-secret-key", request=request)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = AdzunaClient("test-app-id", "test-secret-key", http_client=http_client)
        with pytest.raises(AdzunaRequestError, match="^Adzuna API request failed\\.$") as error:
            client.fetch_page()
    assert "test-secret-key" not in str(error.value)


@pytest.mark.parametrize("payload", [None, [], {}, {"results": None}, {"results": {}},
                                     {"results": "bad"}, {"results": ["bad"]}])
def test_invalid_response_shapes_are_rejected(payload):
    def handler(request):
        return httpx2.Response(200, content=json.dumps(payload), request=request)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = AdzunaClient("test-app-id", "test-secret-key", http_client=http_client)
        with pytest.raises(AdzunaRequestError, match="invalid response"):
            client.fetch_jobs()


def test_malformed_json_has_safe_error():
    def handler(request):
        return httpx2.Response(200, text="not-json test-secret-key", request=request)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = AdzunaClient("test-app-id", "test-secret-key", http_client=http_client)
        with pytest.raises(AdzunaRequestError, match="invalid response") as error:
            client.fetch_page()
    assert "test-secret-key" not in str(error.value)


def test_pagination_stops_on_failure_without_returning_partial_results():
    requested_pages = []

    def handler(request):
        page = int(request.url.path.split("/")[-1])
        requested_pages.append(page)
        if page == 2:
            return httpx2.Response(429, request=request)
        return httpx2.Response(200, json={"results": [{"id": str(page)}]}, request=request)

    with httpx2.Client(transport=httpx2.MockTransport(handler)) as http_client:
        client = AdzunaClient("test-app-id", "test-secret-key", http_client=http_client)
        with pytest.raises(AdzunaRequestError):
            client.fetch_jobs(pages=3)
    assert requested_pages == [1, 2]
