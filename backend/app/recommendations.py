"""API endpoints for the signed-in user's recommendations and job details.

These routes return match results already saved in match_results. Running the
matcher and saving new results is handled by JH-051.

The user always comes from the session cookie, never from the request, so
users can only see their own match data.
"""

from fastapi import APIRouter, Depends, HTTPException, Path

from app.authentication import get_current_user
from app.db import DbConnection, fetch_all, fetch_one


router = APIRouter(prefix="/api", tags=["Recommendations"])

# Used when the user hasn't saved search preferences yet.
DEFAULT_RESULT_COUNT = 20

JOB_COLUMNS = """
    j.job_id, j.external_job_id, j.source, j.title, j.company, j.location,
    j.workplace_type, j.salary_min, j.salary_max, j.salary_currency,
    j.salary_is_predicted, j.description, j.date_posted, j.job_url,
    j.retrieved_at, j.first_seen_at, j.is_active
"""

MATCH_COLUMNS = """
    m.user_id AS match_user_id, m.match_score, m.match_explanation,
    m.created_at AS match_created_at
"""


def to_iso(value):
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


def to_number(value):
    """Return DECIMAL values as JSON numbers (int when there's no fraction)."""
    if value is None:
        return None
    return int(value) if value == int(value) else float(value)


def job_response(row):
    """Return a jobs row in the data contract format."""
    predicted = row["salary_is_predicted"]
    return {
        "job_id": row["job_id"],
        "external_job_id": row["external_job_id"],
        "source": row["source"],
        "title": row["title"],
        "company": row["company"],
        "location": row["location"],
        "workplace_type": row["workplace_type"],
        "salary_min": to_number(row["salary_min"]),
        "salary_max": to_number(row["salary_max"]),
        "salary_currency": row["salary_currency"],
        "salary_is_predicted": None if predicted is None else bool(predicted),
        "description": row["description"],
        "date_posted": row["date_posted"].isoformat() if row["date_posted"] else None,
        "job_url": row["job_url"],
        "retrieved_at": to_iso(row["retrieved_at"]),
        "first_seen_at": to_iso(row["first_seen_at"]),
        "is_active": bool(row["is_active"]),
    }


def match_response(row, skills):
    """Return a match_results row in the data contract format."""
    return {
        "user_id": row["match_user_id"],
        "job_id": row["job_id"],
        "match_score": to_number(row["match_score"]),
        "matched_skills": skills,
        "match_explanation": row["match_explanation"],
        "created_at": to_iso(row["match_created_at"]),
    }


def matched_skills(conn, user_id, job_ids):
    """Return {job_id: [skill, ...]} for the user's match results."""
    skills = {job_id: [] for job_id in job_ids}
    if not job_ids:
        return skills

    placeholders = ", ".join(["%s"] * len(job_ids))
    rows = fetch_all(
        conn,
        f"""
        SELECT job_id, skill
        FROM match_result_skills
        WHERE user_id = %s AND job_id IN ({placeholders})
        ORDER BY job_id, skill
        """,
        (user_id, *job_ids),
    )
    for row in rows:
        skills[row["job_id"]].append(row["skill"])
    return skills


@router.get("/recommendations")
def list_recommendations(
    conn: DbConnection,
    current_user: dict = Depends(get_current_user),
):
    """Return the signed-in user's saved match results, best match first.

    Inactive and dismissed jobs are left out. Saved and applied jobs stay.
    """
    user_id = current_user["user_id"]

    preferences = fetch_one(
        conn,
        "SELECT result_count FROM search_preferences WHERE user_id = %s",
        (user_id,),
    )
    limit = preferences["result_count"] if preferences else DEFAULT_RESULT_COUNT

    rows = fetch_all(
        conn,
        f"""
        SELECT {JOB_COLUMNS}, {MATCH_COLUMNS}
        FROM match_results m
        JOIN jobs j ON j.job_id = m.job_id
        WHERE m.user_id = %s
          AND j.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM job_tracking t
              WHERE t.user_id = %s AND t.job_id = j.job_id AND t.status = 'dismissed'
          )
        ORDER BY m.match_score DESC, j.job_id
        LIMIT %s
        """,
        (user_id, user_id, limit),
    )

    skills = matched_skills(conn, user_id, [row["job_id"] for row in rows])
    return {
        "recommendations": [
            {"job": job_response(row), "match": match_response(row, skills[row["job_id"]])}
            for row in rows
        ]
    }


@router.get("/jobs/{job_id}")
def get_job(
    conn: DbConnection,
    job_id: int = Path(gt=0),
    current_user: dict = Depends(get_current_user),
):
    """Return one job and the signed-in user's match for it (or null).

    Inactive jobs are still returned so saved and applied jobs can be opened.
    """
    user_id = current_user["user_id"]

    row = fetch_one(
        conn,
        f"""
        SELECT {JOB_COLUMNS}, {MATCH_COLUMNS}
        FROM jobs j
        LEFT JOIN match_results m ON m.job_id = j.job_id AND m.user_id = %s
        WHERE j.job_id = %s
        """,
        (user_id, job_id),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    match = None
    if row["match_user_id"] is not None:
        skills = matched_skills(conn, user_id, [job_id])
        match = match_response(row, skills[job_id])

    return {"job": job_response(row), "match": match}
