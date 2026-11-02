"""Normalize raw Adzuna job listings into the shared job data contract."""

# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Help implement JH-027 by converting raw Adzuna API responses
# into the project's shared job-data format and adding tests for the
# required normalization and error-handling cases.
# GenAI usage is documented in the project Progress Report.

import logging
from datetime import datetime, timezone
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


def _clean_string(value):
    """Return a stripped string or None for missing/blank values."""
    if not isinstance(value, str):
        return None

    value = value.strip()
    return value or None


def _nested_display_name(job, field):
    """Return display_name from a nested Adzuna object."""
    value = job.get(field)

    if not isinstance(value, dict):
        return None

    return _clean_string(value.get("display_name"))


def _detect_workplace_type(job):
    """Infer workplace type only when the listing provides clear evidence."""
    text = " ".join(
        filter(
            None,
            [
                _clean_string(job.get("title")),
                _clean_string(job.get("description")),
            ],
        )
    ).lower()

    hybrid_negative_phrases = (
        "not a hybrid position",
        "not hybrid",
        "no hybrid",
    )

    if "hybrid" in text:
        if any(phrase in text for phrase in hybrid_negative_phrases):
            return "unknown"
        return "hybrid"

    onsite_phrases = (
        "onsite only",
        "on-site only",
        "on site only",
        "onsite position",
        "on-site position",
        "on site position",
    )

    if any(phrase in text for phrase in onsite_phrases):
        return "onsite"

    remote_phrases = (
        "remote position",
        "fully remote",
        "100% remote",
        "work remotely",
    )

    if any(phrase in text for phrase in remote_phrases):
        return "remote"

    return "unknown"


def _normalize_predicted_salary(value):
    """Convert Adzuna salary prediction values to bool or None."""
    if value in (True, 1, "1"):
        return True

    if value in (False, 0, "0"):
        return False

    return None


def _normalize_salary(value):
    """Convert salary values to numbers or None."""
    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return value

    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None

    return None


def _normalize_url(value):
    """Return a valid HTTP(S) URL or None."""
    value = _clean_string(value)

    if value is None:
        return None

    parsed = urlparse(value)

    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    return value


def _normalize_date(value):
    """Convert an Adzuna timestamp to YYYY-MM-DD when possible."""
    value = _clean_string(value)

    if value is None:
        return None

    try:
        return datetime.fromisoformat(
            value.replace("Z", "+00:00")
        ).date().isoformat()
    except ValueError:
        return None


def _normalize_timestamp(value):
    """Return a valid ISO 8601 timestamp or None."""
    value = _clean_string(value)

    if value is None:
        return None

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

    return value


def normalize_adzuna_job(job, retrieved_at=None):
    """Convert one raw Adzuna job into a pre-insert Job Posting record.

    The database-generated job_id is intentionally omitted and is assigned
    when the normalized record is saved to the database. Return None when
    the record is missing fields required to make it usable.
    """
    if not isinstance(job, dict):
        return None

    external_job_id = (
        _clean_string(str(job["id"]))
        if job.get("id") is not None
        else None
    )
    title = _clean_string(job.get("title"))
    description = _clean_string(job.get("description"))
    job_url = _normalize_url(job.get("redirect_url"))

    missing_required_fields = [
        field_name
        for field_name, value in (
            ("external_job_id", external_job_id),
            ("title", title),
            ("description", description),
            ("job_url", job_url),
        )
        if not value
    ]

    if missing_required_fields:
        logger.warning(
            "Skipping unusable Adzuna job: missing required field(s): %s",
            ", ".join(missing_required_fields),
        )
        return None

    if retrieved_at is None:
        retrieved_at = (
            datetime.now(timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )
    else:
        retrieved_at = _normalize_timestamp(retrieved_at)

        if retrieved_at is None:
            logger.warning(
                "Skipping unusable Adzuna job: invalid retrieved_at timestamp"
            )
            return None

    return {
        "external_job_id": external_job_id,
        "source": "adzuna",
        "title": title,
        "company": _nested_display_name(job, "company"),
        "location": _nested_display_name(job, "location"),
        "workplace_type": _detect_workplace_type(job),
        "salary_min": _normalize_salary(job.get("salary_min")),
        "salary_max": _normalize_salary(job.get("salary_max")),
        "salary_currency": None,
        "salary_is_predicted": _normalize_predicted_salary(
            job.get("salary_is_predicted")
        ),
        "description": description,
        "date_posted": _normalize_date(job.get("created")),
        "job_url": job_url,
        "retrieved_at": retrieved_at,
    }