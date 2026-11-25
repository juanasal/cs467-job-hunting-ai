from math import floor

import pytest

from app.job_matching import prepare_requirements
from app.job_requirements import extract_requirements
from app.match_evaluation import evaluate_match, recommend_jobs
from app.search_preferences import SearchPreferencesData, SearchPreferencesResponse, preferences_changed


STRICT = {"strict_location": True, "strict_workplace": True, "strict_salary": True}


@pytest.fixture
def recommendation_inputs():
    profile = {
        "user_id": 1,
        "skills": ["Python", "PostgreSQL"],
        "education_level": "bachelor",
        "experience_level": "mid",
    }
    preferences = SearchPreferencesResponse(
        user_id=1, job_titles=["Software Engineer"], locations=["Portland, OR"],
        workplace_type=["hybrid"], salary_min=80000,
    )
    return profile, preferences


def test_recommendations_sort_by_final_score_then_job_id_and_apply_limit(recommendation_inputs):
    profile, preferences = recommendation_inputs
    jobs = [
        {"job_id": 1, "description": "Required: Docker."},
        {"job_id": 4, "description": "Required: Python."},
        {"job_id": 3, "description": "Required: PostgreSQL."},
        {"job_id": 2, "description": "Required: SQL."},
        {"job_id": 5, "description": "Required: Python. Bachelor degree required.",
         "workplace_type": "onsite"},
    ]
    results = recommend_jobs(profile, jobs, preferences)
    assert [(row["job_id"], row["match_score"]) for row in results] == [
        (5, 90), (3, 80), (4, 80), (2, 60), (1, 0),
    ]
    assert recommend_jobs(profile, jobs, preferences) == results
    assert recommend_jobs(profile, reversed(jobs), preferences) == results
    assert recommend_jobs(profile, jobs, preferences.model_copy(update={"result_count": 2})) == results[:2]
    strict = preferences.model_copy(update={"strict_workplace": True, "result_count": 1})
    assert recommend_jobs(profile, jobs, strict) == results[1:2]


def test_recommendation_explanation_reflects_scoring_evidence(recommendation_inputs):
    profile, preferences = recommendation_inputs
    job = {
        "job_id": 1,
        "description": "Required: Python, SQL and Docker. Bachelor degree required. "
                       "Senior experience required. Additional qualifications…",
        "location": "Portland, OR",
        "workplace_type": "onsite",
    }
    assert recommend_jobs(profile, [job], preferences) == [{
        "user_id": 1,
        "job_id": 1,
        "match_score": 57,
        "matched_skills": ["PostgreSQL", "Python"],
        "match_explanation": (
            "Direct skill matches include Python. "
            "Related skill matches include PostgreSQL for sql (partial credit). "
            "No matching profile skill was found for docker (required priority). "
            "Your recorded education meets the job's stated level. "
            "Your recorded experience is below the job's stated level. "
            "Location matches your preference. "
            "Workplace type differs from your preference. "
            "Salary could not be verified against your preference. "
            "The job description appears incomplete."
        ),
    }]


def test_recommendations_handle_incomplete_candidates_and_profiles(recommendation_inputs):
    profile, preferences = recommendation_inputs
    job = {"job_id": 3, "description": "Join our team."}
    jobs = [{"job_id": 1}, {"job_id": 2, "description": " "},
            {"description": "Required: Python."}, job]
    assert recommend_jobs(profile, [], preferences) == []
    assert recommend_jobs(profile, jobs[:-1], preferences) == []
    assert recommend_jobs(None, jobs, preferences) == []
    assert recommend_jobs(profile, jobs, None) == []
    for field in ("skills", "education_level", "experience_level"):
        incomplete = {key: value for key, value in profile.items() if key != field}
        assert recommend_jobs(incomplete, jobs, preferences) == []

    result, = recommend_jobs(profile, jobs, preferences)
    assert result["job_id"] == 3
    assert result["match_score"] == 0
    assert result["matched_skills"] == []
    assert result["match_explanation"] == (
        "Job skill requirements could not be determined from the posting. "
        "Education fit could not be determined from the available information. "
        "Experience fit could not be determined from the available information. "
        "Location could not be verified against your preference. "
        "Workplace type could not be verified against your preference. "
        "Salary could not be verified against your preference."
    )


@pytest.fixture
def match():
    def evaluate(*, job_fields=None, profile_fields=None, preference_fields=None,
                 strict=STRICT):
        profile = {
            "user_id": 1,
            "skills": ["Python", "SQL"],
            "education_level": "bachelor",
            "experience_level": "mid",
            **(profile_fields or {}),
        }
        job = {
            "job_id": 1,
            "description": "Required: Python and SQL. Bachelor degree required. Mid experience required.",
            "location": "Portland, OR",
            "workplace_type": "hybrid",
            "salary_min": 80000,
            "salary_max": 100000,
            "salary_currency": "USD",
            "salary_is_predicted": False,
            **(job_fields or {}),
        }
        preferences = SearchPreferencesResponse(**{
            "user_id": 1,
            "job_titles": ["Software Engineer"],
            "locations": [" PORTLAND,  OR "],
            "workplace_type": ["hybrid"],
            "salary_min": 80000,
            **(strict or {}),
            **(preference_fields or {}),
        })
        extracted = extract_requirements(job)
        prepared = prepare_requirements(job, extracted, warnings=extracted["warnings"])
        return evaluate_match(profile, job, preferences, requirements=prepared)

    return evaluate


@pytest.mark.parametrize(("job_fields", "category"), [
    ({"location": "Seattle, WA"}, "location"),
    ({"workplace_type": "onsite"}, "workplace"),
    ({"salary_min": None, "salary_max": 79999}, "salary"),
])
def test_strict_violation_excludes_and_soft_violation_preserves_fit(match, job_fields, category):
    result = match(job_fields=job_fields)
    assert result["eligible"] is False
    assert result["preference_statuses"][category] == "incompatible"
    assert result["exclusion_reasons"] == [category]
    assert result["qualification"] is None

    result = match(job_fields=job_fields, strict=None)
    assert result["eligible"] is True
    assert result["preference_statuses"][category] == "incompatible"
    assert result["qualification"]["match_score"] == 100


@pytest.mark.parametrize("job_fields", [
    {"salary_min": None, "salary_max": None},
    {"salary_min": 60000, "salary_max": 70000, "salary_currency": None},
    {"salary_min": 60000, "salary_max": 70000, "salary_currency": "EUR"},
    {"salary_min": 60000, "salary_max": 70000, "salary_is_predicted": True},
    {"salary_min": 60000, "salary_max": 70000, "salary_is_predicted": None},
    {"salary_min": None},
])
def test_incomparable_or_insufficient_salary_is_unverified(match, job_fields):
    result = match(job_fields=job_fields)
    assert result["eligible"] is True
    assert result["preference_statuses"]["salary"] == "unverified"


def test_salary_boundary_and_one_sided_maximum(match):
    boundary = match(job_fields={
        "salary_min": 70000, "salary_max": 80000, "salary_is_predicted": 0,
    })
    assert boundary["preference_statuses"]["salary"] == "compatible"
    above_max = match(job_fields={"salary_min": 96000, "salary_max": None},
                      preference_fields={"salary_max": 95000})
    assert above_max["exclusion_reasons"] == ["salary"]


@pytest.mark.parametrize("job_fields", [
    {"salary_min": -1},
    {"salary_min": 120000},
])
def test_invalid_salary_bounds_are_rejected(match, job_fields):
    with pytest.raises(ValueError, match="salary_min"):
        match(job_fields=job_fields)


@pytest.mark.parametrize("flag", sorted(STRICT))
def test_changing_a_strictness_flag_invalidates_matches(flag):
    existing = SearchPreferencesResponse(user_id=1)
    assert getattr(existing, flag) is False
    assert not preferences_changed(existing, SearchPreferencesData())
    assert preferences_changed(existing, SearchPreferencesData(**{flag: True}))


def test_unknown_workplace_leaves_location_and_workplace_unverified(match):
    result = match(job_fields={"workplace_type": "unknown"})
    assert result["eligible"] is True
    assert result["preference_statuses"] == {
        "location": "unverified", "workplace": "unverified", "salary": "compatible",
    }


def test_empty_locations_are_unconstrained_even_when_strict(match):
    result = match(job_fields={"location": "Seattle, WA"},
                   preference_fields={"locations": []})
    assert result["eligible"] is True
    assert result["preference_statuses"]["location"] == "not_constrained"
    assert result["exclusion_reasons"] == []
    assert result["qualification"]["match_score"] == 100


def test_remote_requires_explicit_worker_location_evidence(match):
    remote = {"workplace_type": "remote", "location": "Seattle, WA"}
    preferences = {"workplace_type": ["remote"]}
    result = match(job_fields=remote, preference_fields=preferences)
    assert result["eligible"] is True
    assert result["preference_statuses"]["location"] == "unverified"

    evidence = "Workers must reside in Seattle, WA."
    result = match(job_fields={**remote, "description": f"Required: Python. {evidence}"},
                   preference_fields=preferences)
    assert result["exclusion_reasons"] == ["location"]
    assert result["location_evidence"] == [evidence]


@pytest.mark.parametrize("profile_fields", [
    {"skills": []},
    {"education_level": None},
    {"experience_level": None},
])
def test_incomplete_profile_is_rejected_even_for_strict_mismatch(match, profile_fields):
    with pytest.raises(ValueError, match="skills|education_level|experience_level"):
        match(profile_fields=profile_fields, job_fields={"workplace_type": "onsite"})


@pytest.mark.parametrize(("profile_fields", "description", "expected_points", "score"), [
    ({"skills": ["Excel"], "education_level": "other", "experience_level": "entry"},
     "Required: Python. Bachelor degree required. Mid experience required.", (0, 0, 0), 0),
    ({"skills": ["React"], "education_level": "other"},
     "Required: UI development. Bachelor degree required.", (60, 0, 0), 60),
    ({"skills": ["Python"]},
     "Required: Python. Preferred: SQL. Bachelor degree required. Mid experience required.",
     (160 / 3, 10, 10), 73),
    ({}, "Required: Python and SQL. Bachelor degree required. Mid experience required.",
     (80, 10, 10), 100),
])
def test_fit_bounds_and_component_points(match, profile_fields, description, expected_points, score):
    result = match(profile_fields=profile_fields, job_fields={"description": description})
    qualification = result["qualification"]
    points = qualification["component_points"]
    assert (points["skills"], points["education"], points["experience"]) == pytest.approx(expected_points)
    assert sum(points.values()) == pytest.approx(qualification["raw_score"])
    assert floor(sum(points.values()) + 0.5) == qualification["match_score"] == score
    assert 0 <= qualification["match_score"] <= 100
