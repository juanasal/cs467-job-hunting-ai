"""Evaluate job fit and rank recommendations using saved search preferences."""

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
import re

from app.job_matching import normalize_skill, prepare_requirements, score_job
from app.job_requirements import extract_requirements


_WORKPLACES = {"remote", "hybrid", "onsite"}
_CITY_STATE = re.compile(r"[^,\d]+, [a-z]{2}")
_RESIDENCE = re.compile(
    r"(?:^|(?<=[.!?\n]))\s*(Workers must reside in ([^.!?\n]+)\.)",
    re.IGNORECASE,
)
_WARNING_TEXT = {
    "description_partial": "The job description appears incomplete.",
    "education_ambiguous": "The posting lists conflicting education requirements.",
    "experience_ambiguous": "The posting lists conflicting experience requirements.",
    "experience_level_unmapped": "A years-of-experience requirement could not be compared with the profile's experience level.",
    "qualification_abbreviation_ambiguous": "An ambiguous qualification abbreviation could not be evaluated.",
    "qualification_alternative": "A qualification with alternatives could not be evaluated.",
}
_PREFERENCE_TEXT = {
    "compatible": "matches your preference",
    "incompatible": "differs from your preference",
    "unverified": "could not be verified against your preference",
}


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


def _recommendation_explanation(qualification, preference_statuses):
    direct, related, unmatched = [], [], []
    for target in qualification["skill_targets"]:
        name = target["name"]
        source = target["profile_skill"]
        if target["status"] == "exact match":
            direct.append(source)
        elif target["status"] == "related match":
            related.append(f"{source} for {name} (partial credit)")
        else:
            unmatched.append(f"{name} ({target['priority']} priority)")

    reasons = []
    if direct:
        reasons.append(f"Direct skill matches include {', '.join(direct)}.")
    if related:
        reasons.append(f"Related skill matches include {', '.join(related)}.")
    if unmatched:
        reasons.append(f"No matching profile skill was found for {', '.join(unmatched)}.")
    if not qualification["skill_targets"]:
        reasons.append("Job skill requirements could not be determined from the posting.")

    for category in ("education", "experience"):
        result = qualification[category]
        label = category.capitalize()
        if result["status"] == "minimum met":
            reasons.append(f"Your recorded {category} meets the job's stated level.")
        elif result["status"] == "below minimum":
            reasons.append(f"Your recorded {category} is below the job's stated level.")
        else:
            reasons.append(f"{label} fit could not be determined from the available information.")

    for category, status in preference_statuses.items():
        if status in _PREFERENCE_TEXT:
            label = "Workplace type" if category == "workplace" else category.capitalize()
            reasons.append(f"{label} {_PREFERENCE_TEXT[status]}.")
    reasons.extend(_WARNING_TEXT[warning] for warning in qualification["warnings"])
    return " ".join(reasons)


def recommend_jobs(profile, jobs, preferences):
    """Return contract-shaped recommendations for eligible persisted candidates.

    Unscorable records are skipped under the existing validation rules. Callers
    supply unique job IDs and add created_at if they persist the results.
    """
    if not isinstance(profile, Mapping) or preferences is None:
        return []
    if profile.get("user_id") != preferences.user_id or not preferences.job_titles:
        return []

    eligible = []
    for job in jobs:
        if not isinstance(job, Mapping):
            continue
        try:
            extracted = extract_requirements(job)
            prepared = prepare_requirements(job, extracted, warnings=extracted["warnings"])
            result = evaluate_match(profile, job, preferences, requirements=prepared)
        except ValueError:
            # Required matching data is invalid. There is no score to rank.
            continue
        if result["eligible"]:
            eligible.append(result)

    eligible.sort(key=lambda result: (-result["qualification"]["match_score"], result["job_id"]))
    recommendations = []
    for result in eligible[:preferences.result_count]:
        qualification = result["qualification"]
        recommendations.append({
            "user_id": result["user_id"],
            "job_id": result["job_id"],
            "match_score": qualification["match_score"],
            "matched_skills": qualification["matched_skills"],
            "match_explanation": _recommendation_explanation(
                qualification, result["preference_statuses"]
            ),
        })
    return recommendations
