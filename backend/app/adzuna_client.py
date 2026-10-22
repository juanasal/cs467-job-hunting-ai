"""Client for fetching job listings from the Adzuna API."""

import os

import httpx2


ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/us/search"
DEFAULT_TIMEOUT_SECONDS = 10
DEFAULT_MAX_PAGES = 5


class AdzunaConfigError(RuntimeError):
    """Raised when required Adzuna configuration is missing."""


class AdzunaRequestError(RuntimeError):
    """Raised when an Adzuna API request fails."""


def get_adzuna_credentials(env=None):
    """Return Adzuna credentials from environment variables."""
    if env is None:
        env = os.environ

    app_id = env.get("ADZUNA_APP_ID", "").strip()
    app_key = env.get("ADZUNA_APP_KEY", "").strip()

    missing = []

    if not app_id:
        missing.append("ADZUNA_APP_ID")

    if not app_key:
        missing.append("ADZUNA_APP_KEY")

    if missing:
        raise AdzunaConfigError(
            f"Missing required Adzuna settings: {', '.join(missing)}."
        )

    return app_id, app_key


class AdzunaClient:
    """Reusable client for requesting job listings from Adzuna."""

    def __init__(
        self,
        app_id,
        app_key,
        http_client=None,
        timeout=DEFAULT_TIMEOUT_SECONDS,
        max_pages=DEFAULT_MAX_PAGES,
    ):
        self.app_id = app_id
        self.app_key = app_key
        self.timeout = timeout
        self.max_pages = max_pages
        self.http_client = http_client or httpx2.Client()

    def fetch_page(self, page=1, **search_params):
        """Fetch one page of job listings from Adzuna."""
        params = {
            "app_id": self.app_id,
            "app_key": self.app_key,
            **search_params,
        }

        try:
            response = self.http_client.get(
                f"{ADZUNA_BASE_URL}/{page}",
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
        except Exception as exc:
            raise AdzunaRequestError(
                "Adzuna API request failed."
            ) from None

        return response.json()

    def fetch_jobs(self, pages=1, **search_params):
        """Fetch job listings from multiple Adzuna result pages."""
        if pages < 1:
            raise ValueError("pages must be at least 1.")

        pages_to_fetch = min(pages, self.max_pages)
        jobs = []

        for page in range(1, pages_to_fetch + 1):
            data = self.fetch_page(page=page, **search_params)
            results = data.get("results", [])

            jobs.extend(results)

            if not results:
                break

        return jobs