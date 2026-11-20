
# GenAI attribution:
# Developed with assistance from ChatGPT (OpenAI).
# Prompt: Implement the JH-018 search preferences API using
# FastAPI, Pydantic, and the project's existing MySQL helpers.
# Include authenticated GET/PUT endpoints, input validation,
# CSRF protection, transactional persistence, and change detection.
# Reviewed and adapted for the CS467 Job Hunting AI project.

"""API endpoints for managing user search preferences."""

from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator
from pymysql.err import IntegrityError

from app.authentication import (
    get_current_user,
    verify_csrf_and_origin,
)
from app.db import DbConnection, execute, fetch_all, fetch_one


router = APIRouter(prefix="/api/preferences", tags=["preferences"])

MAX_RESULT_COUNT = 4294967295
MAX_SALARY = Decimal("9999999999.99")


class SearchPreferencesData(BaseModel):
    """Search preference fields accepted by the API."""

    job_titles: list[str] = Field(default_factory=list)
    locations: list[str] = Field(default_factory=list)

    workplace_type: list[
        Literal["remote", "hybrid", "onsite"]
    ] = Field(default_factory=list)

    salary_min: Decimal | None = None
    salary_max: Decimal | None = None

    salary_currency: Literal["USD"] = "USD"

    result_count: int = Field(
        default=20,
        strict=True,
        gt=0,
        le=MAX_RESULT_COUNT,
    )

    @field_validator("job_titles", "locations")
    @classmethod
    def validate_text_lists(cls, values):
        """Trim text and reject empty or duplicate entries."""
        normalized = []
        seen = set()

        for value in values:
            if not isinstance(value, str):
                raise ValueError("Each entry must be a string.")

            value = value.strip()

            if not value:
                raise ValueError("Entries cannot be empty.")

            if len(value) > 255:
                raise ValueError(
                    "Entries cannot exceed 255 characters."
                )

            key = value.casefold()

            if key in seen:
                raise ValueError(
                    "Duplicate entries are not allowed."
                )

            seen.add(key)
            normalized.append(value)

        return normalized

    @field_validator("workplace_type")
    @classmethod
    def validate_workplace_types(cls, values):
        """Reject duplicate workplace types."""
        if len(values) != len(set(values)):
            raise ValueError(
                "Duplicate workplace types are not allowed."
            )

        return values

    @field_validator("salary_min", "salary_max")
    @classmethod
    def validate_salary(cls, value):
        """Validate MySQL DECIMAL(12,2) salary limits."""
        if value is None:
            return None

        if not value.is_finite():
            raise ValueError("Salary must be finite.")

        if value < 0:
            raise ValueError("Salary cannot be negative.")

        if value > MAX_SALARY:
            raise ValueError("Salary exceeds the allowed maximum.")

        if value.as_tuple().exponent < -2:
            raise ValueError(
                "Salary cannot have more than two decimal places."
            )

        return value

    @model_validator(mode="after")
    def validate_salary_range(self):
        """Minimum salary cannot exceed maximum salary."""
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError(
                "Minimum salary cannot exceed maximum salary."
            )

        return self


class SearchPreferencesResponse(SearchPreferencesData):
    """Search preferences returned to the authenticated user."""

    user_id: int


def load_preferences(conn, user_id):
    """Load preferences and their related lists from MySQL."""
    row = fetch_one(
        conn,
        """
        SELECT
            user_id,
            salary_min,
            salary_max,
            salary_currency,
            result_count
        FROM search_preferences
        WHERE user_id = %s
        """,
        (user_id,),
    )

    if row is None:
        return None

    titles = fetch_all(
        conn,
        """
        SELECT job_title
        FROM preference_job_titles
        WHERE user_id = %s
        ORDER BY job_title
        """,
        (user_id,),
    )

    locations = fetch_all(
        conn,
        """
        SELECT location
        FROM preference_locations
        WHERE user_id = %s
        ORDER BY location
        """,
        (user_id,),
    )

    workplace_types = fetch_all(
        conn,
        """
        SELECT workplace_type
        FROM preference_workplace_types
        WHERE user_id = %s
        ORDER BY workplace_type
        """,
        (user_id,),
    )

    return SearchPreferencesResponse(
        user_id=row["user_id"],
        job_titles=[
            item["job_title"] for item in titles
        ],
        locations=[
            item["location"] for item in locations
        ],
        workplace_type=[
            item["workplace_type"] for item in workplace_types
        ],
        salary_min=row["salary_min"],
        salary_max=row["salary_max"],
        salary_currency=row["salary_currency"],
        result_count=row["result_count"],
    )


def preferences_changed(existing, incoming):
    """Check whether any meaningful preference value changed."""
    if existing is None:
        return True

    scalar_fields = (
        "salary_min",
        "salary_max",
        "salary_currency",
        "result_count",
    )

    for field in scalar_fields:
        if getattr(existing, field) != getattr(incoming, field):
            return True

    for field in (
        "job_titles",
        "locations",
        "workplace_type",
    ):
        old_values = {
            value.casefold()
            for value in getattr(existing, field)
        }

        new_values = {
            value.casefold()
            for value in getattr(incoming, field)
        }

        if old_values != new_values:
            return True

    return False


@router.get("", response_model=SearchPreferencesResponse)
def get_preferences(
    conn: DbConnection,
    current_user=Depends(get_current_user),
):
    """Return preferences belonging to the logged-in user."""
    user_id = current_user["user_id"]

    preferences = load_preferences(conn, user_id)

    if preferences is None:
        raise HTTPException(
            status_code=404,
            detail="Search preferences not found.",
        )

    return preferences


@router.put(
    "",
    response_model=SearchPreferencesResponse,
    dependencies=[Depends(verify_csrf_and_origin)],
)
def update_preferences(
    preferences: SearchPreferencesData,
    conn: DbConnection,
    current_user=Depends(get_current_user),
):
    """Create or replace the logged-in user's preferences."""
    user_id = current_user["user_id"]

    existing = load_preferences(conn, user_id)
    changed = preferences_changed(existing, preferences)

    try:
        execute(
            conn,
            """
            INSERT INTO search_preferences (
                user_id,
                salary_min,
                salary_max,
                salary_currency,
                result_count
            )
            VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                salary_min = VALUES(salary_min),
                salary_max = VALUES(salary_max),
                salary_currency = VALUES(salary_currency),
                result_count = VALUES(result_count)
            """,
            (
                user_id,
                preferences.salary_min,
                preferences.salary_max,
                preferences.salary_currency,
                preferences.result_count,
            ),
        )

        execute(
            conn,
            """
            DELETE FROM preference_job_titles
            WHERE user_id = %s
            """,
            (user_id,),
        )

        for title in preferences.job_titles:
            execute(
                conn,
                """
                INSERT INTO preference_job_titles (
                    user_id,
                    job_title
                )
                VALUES (%s, %s)
                """,
                (user_id, title),
            )

        execute(
            conn,
            """
            DELETE FROM preference_locations
            WHERE user_id = %s
            """,
            (user_id,),
        )

        for location in preferences.locations:
            execute(
                conn,
                """
                INSERT INTO preference_locations (
                    user_id,
                    location
                )
                VALUES (%s, %s)
                """,
                (user_id, location),
            )

        execute(
            conn,
            """
            DELETE FROM preference_workplace_types
            WHERE user_id = %s
            """,
            (user_id,),
        )

        for workplace_type in preferences.workplace_type:
            execute(
                conn,
                """
                INSERT INTO preference_workplace_types (
                    user_id,
                    workplace_type
                )
                VALUES (%s, %s)
                """,
                (user_id, workplace_type),
            )


        # GenAI attribution:
        # Developed with assistance from ChatGPT (OpenAI).
        # Prompt: Mark existing match results for recalculation
        # when a user's search preferences actually change.
        # Follow the existing JH-017 profile API pattern.
        # Reviewed and adapted for the CS467 project.

        # Mark existing matches for recalculation only when
        # the user's search preferences have changed.
        if changed:
            execute(
                conn,
                """
                UPDATE match_results
                SET needs_recalculation = TRUE
                WHERE user_id = %s
                """,
                (user_id,),
            )


    except IntegrityError as exc:
        if exc.args and exc.args[0] == 1062:
            raise HTTPException(
                status_code=422,
                detail="Duplicate preference value.",
            ) from exc

        raise

    saved = load_preferences(conn, user_id)

    if saved is None:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve saved preferences.",
        )

    return saved