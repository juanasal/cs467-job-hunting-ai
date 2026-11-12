"""API endpoints for saving, dismissing, and marking jobs as applied.

Each user has at most one current tracking status per job (the job_tracking
primary key is user_id + job_id). The user always comes from the session
cookie, never from the request, so users can only change their own tracking.

"applied" only records what the user says they did. The app does not submit
job applications.
"""

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from pydantic import BaseModel, ConfigDict

from app.authentication import get_current_user, verify_csrf_and_origin
from app.db import DbConnection, execute, fetch_all, fetch_one


router = APIRouter(prefix="/api/tracking", tags=["Job tracking"])

TrackingStatus = Literal["saved", "dismissed", "applied"]


class TrackingUpdate(BaseModel):
    # Reject extra fields such as user_id; the session decides the user.
    model_config = ConfigDict(extra="forbid")

    status: TrackingStatus


def to_response(row):
    """Return a job_tracking row in the data contract format."""
    return {
        "user_id": row["user_id"],
        "job_id": row["job_id"],
        "status": row["status"],
        "updated_at": row["updated_at"].strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


@router.get("")
def list_tracking(
    conn: DbConnection,
    status: TrackingStatus | None = None,
    current_user: dict = Depends(get_current_user),
):
    """Return the signed-in user's tracked jobs, optionally for one status."""
    sql = """
        SELECT user_id, job_id, status, updated_at
        FROM job_tracking
        WHERE user_id = %s
    """
    params = [current_user["user_id"]]

    if status is not None:
        sql += " AND status = %s"
        params.append(status)

    sql += " ORDER BY updated_at DESC, job_id"

    rows = fetch_all(conn, sql, tuple(params))
    return {"tracking": [to_response(row) for row in rows]}


@router.put("/{job_id}", dependencies=[Depends(verify_csrf_and_origin)])
def set_tracking(
    body: TrackingUpdate,
    conn: DbConnection,
    job_id: int = Path(gt=0),
    current_user: dict = Depends(get_current_user),
):
    """Save, dismiss, or mark a job applied, or change the current status.

    Repeating the same status keeps the single existing row unchanged.
    """
    user_id = current_user["user_id"]

    job = fetch_one(conn, "SELECT job_id FROM jobs WHERE job_id = %s", (job_id,))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # The primary key on (user_id, job_id) turns a repeat into an update.
    # updated_at is assigned first so it compares against the old status and
    # only moves when the status actually changes.
    execute(
        conn,
        """
        INSERT INTO job_tracking (user_id, job_id, status, updated_at)
        VALUES (%s, %s, %s, %s)
        ON DUPLICATE KEY UPDATE
            updated_at = IF(status = VALUES(status), updated_at, VALUES(updated_at)),
            status = VALUES(status)
        """,
        (user_id, job_id, body.status, now),
    )

    row = fetch_one(
        conn,
        """
        SELECT user_id, job_id, status, updated_at
        FROM job_tracking
        WHERE user_id = %s AND job_id = %s
        """,
        (user_id, job_id),
    )
    return to_response(row)


@router.delete(
    "/{job_id}",
    status_code=204,
    dependencies=[Depends(verify_csrf_and_origin)],
)
def clear_tracking(
    conn: DbConnection,
    job_id: int = Path(gt=0),
    current_user: dict = Depends(get_current_user),
):
    """Undo tracking so the job is untracked again (and back in the feed)."""
    deleted = execute(
        conn,
        "DELETE FROM job_tracking WHERE user_id = %s AND job_id = %s",
        (current_user["user_id"], job_id),
    )

    if deleted == 0:
        raise HTTPException(status_code=404, detail="Tracking record not found.")

    return Response(status_code=204)
