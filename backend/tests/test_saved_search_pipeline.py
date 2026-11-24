"""Tests for JH-029 saved search job collection.

GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Write isolated pytest tests for the JH-029 saved search
pipeline, including query mapping, limits, normalization,
deduplication, missing preferences, and transaction rollback.
Reviewed and adapted for the CS467 Job Hunting AI project.
"""

from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from app import saved_search_pipeline as pipeline


def make_preferences(
    titles=None,
    locations=None,
    result_count=20,
):
    return SimpleNamespace(
        job_titles=(
            ["Software Engineer"] if titles is None else titles
        ),
        locations=(
            ["Los Angeles"] if locations is None else locations
        ),
        workplace_type=["remote"],
        salary_min=None,
        salary_max=None,
        result_count=result_count,
    )


def make_raw_job(job_id):
    return {
        "id": str(job_id),
        "title": "Software Engineer",
        "description": "Develop and maintain software.",
        "redirect_url": f"https://example.com/jobs/{job_id}",
        "company": {"display_name": "Example Company"},
        "location": {"display_name": "Los Angeles"},
        "created": "2026-11-01T12:00:00Z",
    }


class FakeAdzunaClient:
    max_pages = 5

    def __init__(self, responses=None):
        self.responses = responses or {}
        self.calls = []

    def fetch_page(self, page=1, **params):
        self.calls.append((page, params))

        key = (
            params.get("what"),
            params.get("where"),
            page,
        )

        return {
            "results": self.responses.get(key, []),
        }


def test_build_queries_from_saved_titles_and_locations():
    preferences = make_preferences(
        titles=["Software Engineer", "Data Analyst"],
        locations=["Los Angeles", "Seattle"],
    )

    queries = pipeline.build_adzuna_queries(preferences)

    assert queries == [
        {"what": "Software Engineer", "where": "Los Angeles"},
        {"what": "Software Engineer", "where": "Seattle"},
        {"what": "Data Analyst", "where": "Los Angeles"},
        {"what": "Data Analyst", "where": "Seattle"},
    ]


def test_duplicate_queries_are_removed():
    preferences = make_preferences(
        titles=["Python Developer", "python developer"],
        locations=["Seattle", "SEATTLE"],
    )

    queries = pipeline.build_adzuna_queries(preferences)

    assert queries == [
        {"what": "Python Developer", "where": "Seattle"},
    ]


def test_missing_location_omits_where_parameter():
    preferences = make_preferences(locations=[])

    assert pipeline.build_adzuna_queries(preferences) == [
        {"what": "Software Engineer"},
    ]


def test_missing_titles_prevents_collection():
    preferences = make_preferences(titles=[])

    with pytest.raises(
        pipeline.SavedSearchError,
        match="at least one job title",
    ):
        pipeline.collect_jobs(
            preferences,
            FakeAdzunaClient(),
        )


def test_query_limit_is_enforced():
    preferences = make_preferences(
        titles=[f"Job {i}" for i in range(20)],
        locations=["Seattle"],
    )

    queries = pipeline.build_adzuna_queries(preferences)

    assert len(queries) == pipeline.MAX_QUERIES


def test_invalid_query_limit_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        pipeline.build_adzuna_queries(
            make_preferences(),
            max_queries=0,
        )


def test_collection_normalizes_jobs_and_ignores_duplicates():
    preferences = make_preferences(
        locations=["Los Angeles", "Seattle"],
        result_count=10,
    )

    client = FakeAdzunaClient({
        ("Software Engineer", "Los Angeles", 1): [
            make_raw_job(101),
            make_raw_job(102),
        ],
        ("Software Engineer", "Seattle", 1): [
            make_raw_job(101),
            make_raw_job(103),
        ],
    })

    result = pipeline.collect_jobs(preferences, client)

    assert len(result["jobs"]) == 3
    assert {
        job["external_job_id"] for job in result["jobs"]
    } == {"101", "102", "103"}

    assert all(
        job["source"] == "adzuna"
        for job in result["jobs"]
    )

    assert result["queries_requested"] == 2
    assert result["pages_requested"] == 2


def test_collection_skips_invalid_jobs():
    preferences = make_preferences(result_count=5)

    client = FakeAdzunaClient({
        ("Software Engineer", "Los Angeles", 1): [
            make_raw_job(101),
            {"id": "invalid"},
        ],
    })

    result = pipeline.collect_jobs(preferences, client)

    assert len(result["jobs"]) == 1
    assert result["skipped_jobs"] == 1


def test_result_limit_stops_collection():
    preferences = make_preferences(result_count=2)

    client = FakeAdzunaClient({
        ("Software Engineer", "Los Angeles", 1): [
            make_raw_job(101),
            make_raw_job(102),
            make_raw_job(103),
        ],
    })

    result = pipeline.collect_jobs(preferences, client)

    assert len(result["jobs"]) == 2
    assert result["result_limit"] == 2
    assert len(client.calls) == 1
    assert client.calls[0][1]["results_per_page"] == 20


def test_large_result_count_is_capped():
    preferences = make_preferences(result_count=1000)

    result = pipeline.collect_jobs(
        preferences,
        FakeAdzunaClient(),
    )

    assert result["result_limit"] == pipeline.MAX_RESULTS


def test_run_saved_search_loads_and_saves_jobs(monkeypatch):
    preferences = make_preferences(result_count=5)
    saved_jobs = []
    connections = []

    @contextmanager
    def fake_transaction(settings):
        conn = object()
        connections.append(conn)
        yield conn

    monkeypatch.setattr(
        pipeline,
        "transaction",
        fake_transaction,
    )

    monkeypatch.setattr(
        pipeline,
        "load_preferences",
        lambda conn, user_id: preferences,
    )

    monkeypatch.setattr(
        pipeline,
        "upsert_job",
        lambda conn, job: saved_jobs.append(job),
    )

    client = FakeAdzunaClient({
        ("Software Engineer", "Los Angeles", 1): [
            make_raw_job(101),
            make_raw_job(102),
        ],
    })

    result = pipeline.run_saved_search(
        user_id=1,
        client=client,
        settings=object(),
    )

    assert result["user_id"] == 1
    assert result["jobs_saved"] == 2
    assert len(saved_jobs) == 2
    assert len(connections) == 2


def test_run_saved_search_rejects_missing_preferences(monkeypatch):
    @contextmanager
    def fake_transaction(settings):
        yield object()

    monkeypatch.setattr(
        pipeline,
        "transaction",
        fake_transaction,
    )

    monkeypatch.setattr(
        pipeline,
        "load_preferences",
        lambda conn, user_id: None,
    )

    with pytest.raises(
        pipeline.SavedSearchError,
        match="No saved search preferences",
    ):
        pipeline.run_saved_search(
            user_id=1,
            client=FakeAdzunaClient(),
            settings=object(),
        )


def test_invalid_user_id_is_rejected():
    with pytest.raises(ValueError, match="positive"):
        pipeline.run_saved_search(
            user_id=0,
            client=FakeAdzunaClient(),
            settings=object(),
        )


def test_database_failure_propagates(monkeypatch):
    preferences = make_preferences(result_count=5)
    rolled_back = []

    @contextmanager
    def fake_transaction(settings):
        try:
            yield object()
        except Exception:
            rolled_back.append(True)
            raise

    def failing_upsert(conn, job):
        raise RuntimeError("Database write failed")

    monkeypatch.setattr(
        pipeline,
        "transaction",
        fake_transaction,
    )

    monkeypatch.setattr(
        pipeline,
        "load_preferences",
        lambda conn, user_id: preferences,
    )

    monkeypatch.setattr(
        pipeline,
        "upsert_job",
        failing_upsert,
    )

    client = FakeAdzunaClient({
        ("Software Engineer", "Los Angeles", 1): [
            make_raw_job(101),
        ],
    })

    with pytest.raises(RuntimeError, match="Database write failed"):
        pipeline.run_saved_search(
            user_id=1,
            client=client,
            settings=object(),
        )

    assert rolled_back == [True]
