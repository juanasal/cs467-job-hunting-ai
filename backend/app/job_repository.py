"""Save normalized job postings without creating duplicates.

GenAI attribution:
Developed with assistance from ChatGPT (OpenAI).
Prompt: Help implement JH-028 using MySQL upsert, the existing database
helpers, and the normalized Adzuna job data contract.
"""

from datetime import datetime, timezone

from app.db import execute, fetch_one


JOB_FIELDS = (
    "external_job_id",
    "source",
    "title",
    "company",
    "location",
    "workplace_type",
    "salary_min",
    "salary_max",
    "salary_currency",
    "salary_is_predicted",
    "description",
    "date_posted",
    "job_url",
    "retrieved_at",
)


def _to_mysql_datetime(value):
    """Convert an ISO 8601 timestamp to a UTC MySQL DATETIME."""
    if not isinstance(value, str):
        raise ValueError("retrieved_at must be an ISO 8601 string")

    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid retrieved_at timestamp") from exc

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("retrieved_at must include a timezone")

    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def upsert_job(conn, job):
    """Insert or update a normalized job within the caller's transaction.

    A job is identified by (source, external_job_id).
    Existing job_id and first_seen_at values are preserved.
    Older imports do not overwrite newer stored job data.
    """
    if not isinstance(job, dict):
        raise ValueError("job must be a dictionary")

    missing = [field for field in JOB_FIELDS if field not in job]
    if missing:
        raise ValueError(f"Missing job fields: {', '.join(missing)}")

    if not job["source"] or not job["external_job_id"]:
        raise ValueError("source and external_job_id are required")

    if not job["title"] or not job["description"] or not job["job_url"]:
        raise ValueError("title, description, and job_url are required")

    retrieved_at = _to_mysql_datetime(job["retrieved_at"])

    values = {
        **job,
        "retrieved_at": retrieved_at,
    }

    insert_fields = (*JOB_FIELDS, "first_seen_at")
    columns = ", ".join(insert_fields)
    placeholders = ", ".join(["%s"] * len(insert_fields))

    # The unique key on (source, external_job_id) detects duplicates.
    # first_seen_at is intentionally excluded from the update.
    update_fields = [
        field
        for field in JOB_FIELDS
        if field not in ("source", "external_job_id", "retrieved_at")
    ]

    # Update job details only when the incoming record is not older.
    updates = ", ".join(
        f"{field} = IF(VALUES(retrieved_at) >= retrieved_at, "
        f"VALUES({field}), {field})"
        for field in update_fields
    )

    # Keep the latest retrieval timestamp. This assignment must come last
    # so the comparisons above use the previously stored timestamp.
    updates += (
        ", retrieved_at = GREATEST(retrieved_at, VALUES(retrieved_at))"
    )

    sql = (
        f"INSERT INTO jobs ({columns}) "
        f"VALUES ({placeholders}) "
        f"ON DUPLICATE KEY UPDATE {updates}"
    )

    params = tuple(values[field] for field in JOB_FIELDS) + (retrieved_at,)

    execute(conn, sql, params)

    row = fetch_one(
        conn,
        """
        SELECT job_id
        FROM jobs
        WHERE source = %s AND external_job_id = %s
        """,
        (job["source"], job["external_job_id"]),
    )

    if row is None:
        raise RuntimeError("Job was not found after upsert")

    return row["job_id"]
