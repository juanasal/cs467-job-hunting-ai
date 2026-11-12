
"""API endpoints for viewing and editing the signed-in user's profile."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from app.authentication import get_current_user, verify_csrf_and_origin
from app.db import DbConnection, execute, fetch_all, fetch_one


router = APIRouter(prefix="/api/profile", tags=["Profile"])


EducationLevel = Literal[
    "high_school",
    "associate",
    "bachelor",
    "master",
    "doctorate",
    "other",
]

ExperienceLevel = Literal["entry", "mid", "senior"]


class ProfileData(BaseModel):
    """Profile fields defined in the shared data contract."""

    model_config = ConfigDict(extra="forbid")

    skills: list[str] = Field(min_length=1)
    education_level: EducationLevel
    experience_level: ExperienceLevel


class ProfileResponse(ProfileData):
    user_id: int


@router.get("", response_model=ProfileResponse)
def get_profile(
    conn: DbConnection,
    current_user: dict = Depends(get_current_user),
):
    """Return the signed-in user's saved profile."""

    user_id = current_user["user_id"]

    profile = fetch_one(
        conn,
        """
        SELECT education_level, experience_level
        FROM user_profiles
        WHERE user_id = %s
        """,
        (user_id,),
    )

    if profile is None:
        raise HTTPException(
            status_code=404,
            detail="Profile not found.",
        )

    skills = fetch_all(
        conn,
        """
        SELECT skill
        FROM user_skills
        WHERE user_id = %s
        ORDER BY skill
        """,
        (user_id,),
    )

    return {
        "user_id": user_id,
        "skills": [row["skill"] for row in skills],
        "education_level": profile["education_level"],
        "experience_level": profile["experience_level"],
    }


@router.put(
    "",
    response_model=ProfileResponse,
    dependencies=[Depends(verify_csrf_and_origin)],
)
def update_profile(
    profile: ProfileData,
    conn: DbConnection,
    current_user: dict = Depends(get_current_user),
):
    """Create or update the signed-in user's profile."""

    user_id = current_user["user_id"]

    # Normalize skills and reject invalid or duplicate values.
    normalized_skills = []
    seen = set()

    for skill in profile.skills:
        skill = " ".join(skill.split())

        if not skill or len(skill) > 100:
            raise HTTPException(
                status_code=422,
                detail="Each skill must contain 1 to 100 characters.",
            )

        key = skill.casefold()

        if key in seen:
            raise HTTPException(
                status_code=422,
                detail="Duplicate skills are not allowed.",
            )

        seen.add(key)
        normalized_skills.append(skill)

    # Check whether the saved profile has changed.
    existing_profile = fetch_one(
        conn,
        """
        SELECT education_level, experience_level
        FROM user_profiles
        WHERE user_id = %s
        """,
        (user_id,),
    )

    existing_skills = fetch_all(
        conn,
        """
        SELECT skill
        FROM user_skills
        WHERE user_id = %s
        """,
        (user_id,),
    )

    profile_changed = (
        existing_profile is None
        or existing_profile["education_level"] != profile.education_level
        or existing_profile["experience_level"] != profile.experience_level
        or {row["skill"].casefold() for row in existing_skills}
        != {skill.casefold() for skill in normalized_skills}
    )

    # Create or update education and experience.
    execute(
        conn,
        """
        INSERT INTO user_profiles
            (user_id, education_level, experience_level)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE
            education_level = VALUES(education_level),
            experience_level = VALUES(experience_level)
        """,
        (
            user_id,
            profile.education_level,
            profile.experience_level,
        ),
    )

    # Replace the existing skills.
    execute(
        conn,
        "DELETE FROM user_skills WHERE user_id = %s",
        (user_id,),
    )

    for skill in normalized_skills:
        execute(
            conn,
            """
            INSERT INTO user_skills (user_id, skill)
            VALUES (%s, %s)
            """,
            (user_id, skill),
        )

    # Mark recommendations for recalculation only when
    # matching profile inputs have changed.
    if profile_changed:
        execute(
            conn,
            """
            UPDATE match_results
            SET needs_recalculation = TRUE
            WHERE user_id = %s
            """,
            (user_id,),
        )

    return {
        "user_id": user_id,
        "skills": sorted(normalized_skills, key=str.casefold),
        "education_level": profile.education_level,
        "experience_level": profile.experience_level,
    }
