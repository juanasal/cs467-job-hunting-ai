from math import floor

import pytest

from app.job_matching import prepare_requirements
from app.job_requirements import extract_requirements
from app.match_evaluation import evaluate_match
from app.search_preferences import SearchPreferencesData, SearchPreferencesResponse, preferences_changed


STRICT = {"strict_location": True, "strict_workplace": True, "strict_salary": True}


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
