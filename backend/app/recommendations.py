"""API endpoints for the signed-in user's recommendations and job details.

The user always comes from the session cookie, never from the request, so
users can only see their own match data.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Path

from app.authentication import get_current_user
from app.db import DbConnection, fetch_all, fetch_one
from app.job_repository import JOB_COLUMNS, load_recommendation_jobs
from app.match_evaluation import recommend_jobs
from app.profile import load_profile
from app.search_preferences import load_preferences


router = APIRouter(prefix="/api", tags=["Recommendations"])

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


def matching_inputs(conn, user_id):
    profile = load_profile(conn, user_id)
    if not profile or not profile["skills"]:
        return None, None
    preferences = load_preferences(conn, user_id)
    if not preferences or not preferences.job_titles:
        return None, None
    return profile, preferences


def current_matches(profile, jobs, preferences):
    matches = recommend_jobs(profile, jobs, preferences)
    evaluated_at = to_iso(datetime.now(timezone.utc))
    for match in matches:
        match["created_at"] = evaluated_at
    return matches


@router.get("/recommendations")
def list_recommendations(
    conn: DbConnection,
    current_user: dict = Depends(get_current_user),
):
    """Rank stored jobs against the signed-in user's current matching inputs."""
    user_id = current_user["user_id"]
    profile, preferences = matching_inputs(conn, user_id)
    if profile is None:
        return {"recommendations": []}

    jobs = {job["job_id"]: job for job in load_recommendation_jobs(conn, user_id)}
    return {
        "recommendations": [
            {"job": job_response(jobs[match["job_id"]]), "match": match}
            for match in current_matches(profile, jobs.values(), preferences)
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
    profile, preferences = matching_inputs(conn, user_id) if row["is_active"] else (None, None)
    if profile is not None:
        matches = current_matches(profile, [row], preferences)
        if matches:
            match = matches[0]
    elif row["match_user_id"] is not None:
        skills = matched_skills(conn, user_id, [job_id])
        match = match_response(row, skills[job_id])

    return {"job": job_response(row), "match": match}
