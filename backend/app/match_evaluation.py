"""Evaluate saved search preferences and qualification fit for one job."""

from decimal import Decimal, InvalidOperation
import re

from app.job_matching import normalize_skill, score_job


_WORKPLACES = {"remote", "hybrid", "onsite"}
_CITY_STATE = re.compile(r"[^,\d]+, [a-z]{2}")
_RESIDENCE = re.compile(
    r"(?:^|(?<=[.!?\n]))\s*(Workers must reside in ([^.!?\n]+)\.)",
    re.IGNORECASE,
)


def _location(job, locations):
    if not locations:
        return "not_constrained", []

    restrictions = _RESIDENCE.findall(job["description"])
    evidence = [sentence for sentence, _ in restrictions]
    preferred = {normalize_skill(location) for location in locations}
    posting = normalize_skill(job.get("location") or "")
    if len(restrictions) == 1:
        city = normalize_skill(restrictions[0][1])
        if job.get("workplace_type") in {"hybrid", "onsite"} and posting and city != posting:
            return "unverified", evidence
    elif restrictions or job.get("workplace_type") not in {"hybrid", "onsite"}:
        return "unverified", evidence
    else:
        city = posting

    if not _CITY_STATE.fullmatch(city):
        return "unverified", evidence
    if city in preferred:
        return "compatible", evidence
    if all(_CITY_STATE.fullmatch(location) for location in preferred):
        return "incompatible", evidence
    return "unverified", evidence


def _salary_bounds(record):
    bounds = []
    for field in ("salary_min", "salary_max"):
        value = record.get(field)
        if value is not None:
            try:
                value = Decimal(str(value))
            except InvalidOperation as exc:
                raise ValueError(f"{field} must be numeric") from exc
            if not value.is_finite() or value < 0:
                raise ValueError(f"{field} must be finite and nonnegative")
        bounds.append(value)
    minimum, maximum = bounds
    if minimum is not None and maximum is not None and minimum > maximum:
        raise ValueError("salary_min cannot exceed salary_max")
    return minimum, maximum


def _salary(job, preferences):
    user_min, user_max = preferences.salary_min, preferences.salary_max
    job_min, job_max = _salary_bounds(job)
    if user_min is None and user_max is None:
        return "not_constrained"
    if (
        job.get("salary_is_predicted") not in (False, 0)
        or job.get("salary_currency") != preferences.salary_currency
    ):
        return "unverified"
    if (job_max is not None and user_min is not None and job_max < user_min) or (
        job_min is not None and user_max is not None and job_min > user_max
    ):
        return "incompatible"
    if job_min is not None and job_max is not None:
        return "compatible"
    if user_max is None and job_min is not None and job_min >= user_min:
        return "compatible"
    if user_min is None and job_max is not None and job_max <= user_max:
        return "compatible"
    return "unverified"


def evaluate_match(profile, job, preferences, *, requirements):
    """Combine prepared qualifications and a validated JH-018 preference record.

    Job salary fields must satisfy the shared annual-salary contract.
    Results are internal. Raw component points sum to raw_score, which the
    qualification scorer rounds half up to obtain match_score.
    """
    qualification = score_job(profile, job, requirements=requirements)
    if qualification["user_id"] != preferences.user_id:
        raise ValueError("profile and preferences must belong to the same user")
    if not preferences.job_titles:
        raise ValueError("job titles must be nonempty for matching")

    location, location_evidence = _location(job, preferences.locations)
    workplace = job.get("workplace_type")
    if not preferences.workplace_type:
        workplace_status = "not_constrained"
    elif workplace not in _WORKPLACES:
        workplace_status = "unverified"
    else:
        workplace_status = "compatible" if workplace in preferences.workplace_type else "incompatible"

    statuses = {
        "location": location,
        "workplace": workplace_status,
        "salary": _salary(job, preferences),
    }
    exclusions = [
        category for category, status in statuses.items()
        if status == "incompatible" and getattr(preferences, f"strict_{category}")
    ]
    return {
        "user_id": qualification["user_id"],
        "job_id": qualification["job_id"],
        "eligible": not exclusions,
        "preference_statuses": statuses,
        "location_evidence": location_evidence,
        "exclusion_reasons": exclusions,
        "qualification": None if exclusions else qualification,
    }
