"""Collect jobs using a user's saved search preferences.

GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Implement JH-029 using the existing Search Preferences API,
Adzuna client, job normalizer, and MySQL upsert repository.
Include query limits, deduplication, transaction handling, and tests.
Reviewed and adapted for the CS467 Job Hunting AI project.
"""

from app.adzuna_client import AdzunaClient, get_adzuna_credentials
from app.config import get_settings
from app.db import transaction
from app.job_normalizer import normalize_adzuna_job
from app.job_repository import upsert_job
from app.search_preferences import load_preferences


MAX_QUERIES = 10
MAX_RESULTS = 100
RESULTS_PER_PAGE = 20
MAX_PAGES = 5


class SavedSearchError(ValueError):
    """Raised when a saved search cannot be performed."""


def build_adzuna_queries(preferences, max_queries=MAX_QUERIES):
    """Build unique title/location queries from saved preferences.

    Unsupported filters are intentionally not sent to Adzuna.
    """
    if max_queries < 1:
        raise ValueError("max_queries must be positive.")

    titles = preferences.job_titles
    locations = preferences.locations or [None]

    queries = []
    seen = set()

    for title in titles:
        title = title.strip()

        if not title:
            continue

        for location in locations:
            location = location.strip() if location else None
            location = location or None

            key = (
                title.casefold(),
                location.casefold() if location else None,
            )

            if key in seen:
                continue

            seen.add(key)

            query = {"what": title}

            if location:
                query["where"] = location

            queries.append(query)

            if len(queries) >= max_queries:
                return queries

    return queries


def collect_jobs(preferences, client):
    """Fetch and normalize jobs from saved search preferences.

    Returns normalized jobs and collection statistics.
    No database changes are made by this function.
    """
    queries = build_adzuna_queries(preferences)

    if not queries:
        raise SavedSearchError(
            "Add at least one job title to your search preferences."
        )

    result_limit = min(preferences.result_count, MAX_RESULTS)

    if result_limit < 1:
        raise SavedSearchError(
            "The requested result count must be positive."
        )

    normalized_jobs = []
    seen_jobs = set()
    pages_requested = 0
    queries_requested = 0
    skipped_jobs = 0

    for query in queries:
        if len(normalized_jobs) >= result_limit:
            break

        queries_requested += 1

        for page in range(1, min(client.max_pages, MAX_PAGES) + 1):
            if len(normalized_jobs) >= result_limit:
                break

            # Keep page size constant to avoid overlapping API results.
            count = RESULTS_PER_PAGE

            response = client.fetch_page(
                page=page,
                results_per_page=count,
                **query,
            )

            pages_requested += 1
            raw_jobs = response["results"]

            if not raw_jobs:
                break

            for raw_job in raw_jobs:
                job = normalize_adzuna_job(raw_job)

                if job is None:
                    skipped_jobs += 1
                    continue

                key = (
                    job["source"],
                    job["external_job_id"],
                )

                if key in seen_jobs:
                    continue

                seen_jobs.add(key)
                normalized_jobs.append(job)

                if len(normalized_jobs) >= result_limit:
                    break

            # A short page usually means there are no more results.
            if len(raw_jobs) < count:
                break

    return {
        "jobs": normalized_jobs,
        "queries_requested": queries_requested,
        "pages_requested": pages_requested,
        "skipped_jobs": skipped_jobs,
        "result_limit": result_limit,
    }


def run_saved_search(user_id, client=None, settings=None):
    """Load preferences, fetch Adzuna jobs, and save them to MySQL.

    Network requests happen outside the write transaction.
    A failed database write rolls back the entire save operation.

    An optional client can be supplied for testing.
    """
    if not isinstance(user_id, int) or isinstance(user_id, bool):
        raise ValueError("user_id must be an integer.")

    if user_id < 1:
        raise ValueError("user_id must be positive.")

    if settings is None:
        settings = get_settings()

    # Read the saved preferences in a short transaction.
    with transaction(settings) as conn:
        preferences = load_preferences(conn, user_id)

    if preferences is None:
        raise SavedSearchError(
            "No saved search preferences were found for this user."
        )

    owned_client = None

    if client is None:
        app_id, app_key = get_adzuna_credentials()
        owned_client = AdzunaClient(
            app_id=app_id,
            app_key=app_key,
        )
        client = owned_client

    try:
        collection = collect_jobs(preferences, client)
    finally:
        if owned_client is not None:
            owned_client.http_client.close()

    # Save all normalized jobs in one transaction.
    # upsert_job preserves existing job IDs and avoids duplicates.
    with transaction(settings) as conn:
        for job in collection["jobs"]:
            upsert_job(conn, job)

    return {
        "user_id": user_id,
        "jobs_saved": len(collection["jobs"]),
        "queries_requested": collection["queries_requested"],
        "pages_requested": collection["pages_requested"],
        "skipped_jobs": collection["skipped_jobs"],
        "result_limit": collection["result_limit"],
    }
