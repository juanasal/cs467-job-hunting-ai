
import pytest

from app.job_normalizer import normalize_adzuna_job

# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Help implement JH-027 by converting raw Adzuna API responses
# into the project's shared job-data format and adding tests for the
# required normalization and error-handling cases.
# GenAI usage is documented in the project Progress Report.

RETRIEVED_AT = "2026-10-27T19:00:00Z"


def test_normalizes_complete_adzuna_job():
    raw_job = {
        "id": "5930203280",
        "title": "Principal Software Engineer",
        "company": {"display_name": "Govcio LLC"},
        "location": {"display_name": "Triangle, Prince William County"},
        "description": (
            "This position will be located in Quantico, VA, "
            "and will be a hybrid position within the United States."
        ),
        "salary_min": 213926.73,
        "salary_max": 213926.73,
        "salary_is_predicted": "1",
        "created": "2026-10-16T03:25:41Z",
        "redirect_url": "https://www.adzuna.com/land/ad/5930203280",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result == {
        "external_job_id": "5930203280",
        "source": "adzuna",
        "title": "Principal Software Engineer",
        "company": "Govcio LLC",
        "location": "Triangle, Prince William County",
        "workplace_type": "hybrid",
        "salary_min": 213926.73,
        "salary_max": 213926.73,
        "salary_currency": None,
        "salary_is_predicted": True,
        "description": (
            "This position will be located in Quantico, VA, "
            "and will be a hybrid position within the United States."
        ),
        "date_posted": "2026-10-16",
        "job_url": "https://www.adzuna.com/land/ad/5930203280",
        "retrieved_at": RETRIEVED_AT,
    }


def test_missing_optional_fields_are_not_invented():
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build and maintain software applications.",
        "created": "2026-10-20T12:00:00Z",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["company"] is None
    assert result["location"] is None
    assert result["workplace_type"] == "unknown"
    assert result["salary_min"] is None
    assert result["salary_max"] is None
    assert result["salary_currency"] is None
    assert result["salary_is_predicted"] is None


def test_unusable_record_is_skipped(caplog):
    raw_job = {
        "id": "12345",
        "description": "Job description without a title.",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(
        raw_job,
        retrieved_at=RETRIEVED_AT,
    )

    assert result is None
    assert "missing required field(s): title" in caplog.text


def test_onsite_description_is_not_misclassified_as_remote():
    raw_job = {
        "id": "5932203103",
        "title": "Software Engineer - Embedded",
        "description": (
            "This position is onsite only. "
            "Applications for remote employment will not be considered."
        ),
        "redirect_url": "https://www.adzuna.com/details/5932203103",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["workplace_type"] == "onsite"


def test_salary_values_are_normalized_to_numbers_or_none():
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "salary_min": "125000.50",
        "salary_max": "not available",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["salary_min"] == 125000.50
    assert result["salary_max"] is None


def test_invalid_job_url_is_skipped(caplog):
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "redirect_url": "not-a-valid-url",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result is None
    assert "missing required field(s): job_url" in caplog.text


def test_invalid_retrieved_at_is_skipped(caplog):
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(
        raw_job,
        retrieved_at="not-a-valid-timestamp",
    )

    assert result is None
    assert "invalid retrieved_at timestamp" in caplog.text


def test_negated_hybrid_description_returns_unknown():
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": (
            "This is not a hybrid position. "
            "Employees are expected to work from the assigned location."
        ),
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["workplace_type"] == "unknown"


def test_non_finite_salary_values_become_none():
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "salary_min": "NaN",
        "salary_max": "Infinity",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["salary_min"] is None
    assert result["salary_max"] is None

    raw_job["salary_min"] = "1e999"

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["salary_min"] is None


@pytest.mark.parametrize(
    "invalid_url",
    [
        "https://exa mple.com/job",
        "https://:443/job",
        "https:///[broken",
        "https://example.com:invalid/job",
    ],
)
def test_malformed_job_urls_are_skipped(invalid_url, caplog):
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "redirect_url": invalid_url,
    }

    result = normalize_adzuna_job(
        raw_job,
        retrieved_at=RETRIEVED_AT,
    )

    assert result is None
    assert "missing required field(s): job_url" in caplog.text


@pytest.mark.parametrize(
    "invalid_timestamp",
    [
        "2026-10-27",
        "2026-10-27T19:00:00",
    ],
)
def test_retrieved_at_requires_time_and_timezone(invalid_timestamp, caplog):
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": "Build software applications.",
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(
        raw_job,
        retrieved_at=invalid_timestamp,
    )

    assert result is None
    assert "invalid retrieved_at timestamp" in caplog.text


@pytest.mark.parametrize(
    "description",
    [
        "This is not a hybrid role.",
        "Experience with hybrid cloud software is required.",
        "This is a hybrid position and a fully remote position.",
        "This is not a remote position.",
    ],
)
def test_ambiguous_workplace_descriptions_return_unknown(description):
    raw_job = {
        "id": "12345",
        "title": "Software Engineer",
        "description": description,
        "redirect_url": "https://www.adzuna.com/details/12345",
    }

    result = normalize_adzuna_job(raw_job, retrieved_at=RETRIEVED_AT)

    assert result["workplace_type"] == "unknown"
