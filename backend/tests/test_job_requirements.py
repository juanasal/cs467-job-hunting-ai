import pytest

from app.job_matching import prepare_requirements, score_job
from app.job_requirements import extract_requirements


def target(field, value, priority, evidence):
    return {field: value, "priority": priority, "evidence": evidence}


def test_all_qualification_types_feed_exact_scorer():
    job = {
        "job_id": 1001,
        "description": (
            "Required: Python; SQL. Preferred: written communication. "
            "Bachelor’s degree required. Mid-level experience required."
        ),
    }
    result = extract_requirements(job)
    assert result["technical_skills"] == [
        target("name", name, "required", "Required: Python; SQL.")
        for name in ("python", "sql")
    ]
    assert result["soft_skills"] == [
        target("name", "written communication", "preferred", "Preferred: written communication.")
    ]
    assert result["education"] == target(
        "minimum", "bachelor", "required", "Bachelor’s degree required."
    )
    assert result["experience"] == target(
        "minimum", "mid", "required", "Mid-level experience required."
    )
    prepared = prepare_requirements(job, result, warnings=result["warnings"])
    profile = {
        "user_id": 1, "skills": ["Python", "SQL", "Written Communication"],
        "education_level": "bachelor", "experience_level": "mid",
    }
    assert score_job(profile, job, requirements=prepared)["match_score"] == 100


def test_required_preferred_and_unspecified_stay_local():
    result = extract_requirements({
        "description": "Python required. AWS preferred. Applicants should have Docker experience."
    })
    assert result["skills"] == [
        target("name", "python", "required", "Python required."),
        target("name", "aws", "preferred", "AWS preferred."),
        target("name", "docker", "unspecified", "Applicants should have Docker experience."),
    ]


def test_negation_and_ambiguous_abbreviation():
    result = extract_requirements({
        "description": "No degree required. Python is not required. R required. SQL preferred."
    })
    assert result["education_mentions"] == []
    assert result["education"] is None
    assert result["skills"] == [target("name", "sql", "preferred", "SQL preferred.")]
    assert result["warnings"] == ["qualification_abbreviation_ambiguous"]


@pytest.mark.parametrize("job", [{}, {"description": None}, {"description": " \n\t"}])
def test_missing_and_blank_descriptions(job):
    assert extract_requirements({**job, "title": "Python developer"}) == {
        "technical_skills": [], "soft_skills": [], "skills": [],
        "education": None, "experience": None, "education_mentions": [],
        "experience_mentions": [], "warnings": [],
    }


def test_shortened_description_stops_at_visible_qualifications():
    result = extract_requirements({
        "description": "Required: Python. Additional qualifications include a bachelor’s…"
    })
    assert result["skills"] == [target("name", "python", "required", "Required: Python.")]
    assert result["education"] is None
    assert result["experience"] is None
    assert result["warnings"] == ["description_partial"]


def test_alternatives_years_and_conflicting_levels_stay_unevaluable():
    result = extract_requirements({
        "description": (
            "Bachelor degree or equivalent experience required. "
            "5 years of experience required. Mid experience required. Senior experience preferred."
        )
    })
    assert result["education"] is None
    assert result["experience"] is None
    assert result["experience_mentions"] == [
        target("minimum", "mid", "required", "Mid experience required."),
        target("minimum", "senior", "preferred", "Senior experience preferred."),
    ]
    assert result["warnings"] == [
        "experience_ambiguous", "experience_level_unmapped", "qualification_alternative",
    ]


def test_multiline_heading_and_literal_skill_boundaries():
    result = extract_requirements({
        "description": "Required skills:\n- C++\n- React.js\nResponsibilities:\n- Java"
    })
    assert result["skills"] == [
        target("name", "c++", "required", "- C++"),
        target("name", "react.js", "required", "- React.js"),
    ]


@pytest.mark.parametrize("heading", ["", "Required skills:\n"])
def test_semicolon_separates_explicit_priorities(heading):
    result = extract_requirements({"description": heading + "Python required; AWS preferred."})
    assert result["skills"] == [
        target("name", "python", "required", "Python required"),
        target("name", "aws", "preferred", "AWS preferred."),
    ]


def test_unpunctuated_employer_heading_ends_qualification_section():
    result = extract_requirements({
        "description": "Required skills:\n- Python\nOur tech stack\n- Java"
    })
    assert result["skills"] == [target("name", "python", "required", "- Python")]
