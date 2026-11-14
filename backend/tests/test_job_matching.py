"""Fixed, hand-calculated expectations for exact-v1 (JH-033 examples)."""
from copy import deepcopy

import pytest

from app.job_matching import prepare_requirements, score_job


@pytest.fixture
def profile():
    return {"user_id": 1, "skills": ["Python", "SQL"],
            "education_level": "bachelor", "experience_level": "mid"}


@pytest.fixture
def job():
    return {"job_id": 1001, "external_job_id": "fictional-001", "source": "fictional",
            "title": "Software Engineer", "company": "Fictional Example", "location": None,
            "workplace_type": "unknown", "salary_min": None, "salary_max": None,
            "salary_currency": None, "salary_is_predicted": None,
            "description": "Required: Python; SQL. Bachelor degree required. Mid experience required.",
            "job_url": "https://example.com/jobs/001", "date_posted": "2026-11-01",
            "retrieved_at": "2026-11-10T18:00:00Z", "first_seen_at": "2026-11-10T18:00:00Z"}


def skill(name, priority="required", evidence=None):
    return {"name": name, "priority": priority, "evidence": evidence or name}


def level(minimum, priority="required", evidence=None):
    return {"minimum": minimum, "priority": priority, "evidence": evidence or minimum}


def evaluate(profile, job, skills=None, education=None, experience=None, warnings=()):
    prepared = prepare_requirements(job, {"skills": skills or [], "education": education,
                                         "experience": experience}, warnings=warnings)
    return score_job(profile, job, requirements=prepared)


def default_requirements(job):
    return prepare_requirements(job, {
        "skills": [skill("Python"), skill("SQL")],
        "education": level("bachelor", evidence="Bachelor degree required."),
        "experience": level("mid", evidence="Mid experience required."),
    })


def test_match_001_strong_repeatable_and_nonmutating(profile, job):
    profile["skills"] = [" python ", "SQL", "PYTHON"]
    original = deepcopy((profile, job))
    requirements = default_requirements(job)
    result = score_job(profile, job, requirements=requirements)
    assert result["match_score"] == 100
    assert result["component_points"] == {"skills": 80, "education": 10, "experience": 10}
    assert result["matched_skills"] == [" python ", "SQL"]
    assert result["component_coverage"] == 1
    assert result["method_version"] == "exact-v1"
    assert result["user_id"] == 1 and result["job_id"] == 1001
    assert "created_at" not in result and "included" not in result
    assert "exact match" in result["match_explanation"]
    for _ in range(3):
        assert score_job(profile, job, requirements=requirements) == result
    assert (profile, job) == original


def test_match_002_unrelated(profile, job):
    profile.update(skills=["Excel"], education_level="high_school", experience_level="entry")
    result = score_job(profile, job, requirements=default_requirements(job))
    assert result["match_score"] == 0
    assert result["matched_skills"] == []
    assert all(t["status"] == "unmatched" for t in result["skill_targets"])
    assert result["education"]["status"] == "below minimum"
    assert result["experience"]["status"] == "below minimum"


def test_missing_requirements_and_other_education(profile, job):
    result = evaluate(profile, job)
    assert result["match_score"] == 0
    assert result["component_coverage"] == 0
    assert result["match_explanation"].count("insufficient evidence") == 3
    profile["education_level"] = "other"
    result = score_job(profile, job, requirements=default_requirements(job))
    assert result["match_score"] == 90
    assert result["education"]["status"] == "insufficient evidence"
    assert result["component_coverage"] == .9


def test_match_013_partial_description(profile, job):
    job["description"] = "Required: Python. Additional qualifications…"
    result = evaluate(profile, job, [skill("Python")], warnings=["description_partial"])
    assert result["match_score"] == 80
    assert result["warnings"] == ["description_partial"]
    assert "description_partial" in result["match_explanation"]
    assert result["education"]["minimum"] is None


@pytest.mark.parametrize("priority,expected", [("required", 53), ("preferred", 40),
                                               ("unspecified", 27)])
def test_relative_skill_priority(profile, job, priority, expected):
    profile["skills"] = ["Python"]
    result = evaluate(profile, job, [skill("Python", priority), skill("SQL", "preferred")])
    # 80 * (2, 1, or .5) / (3, 2, or 1.5), rounded once.
    assert result["match_score"] == expected


@pytest.mark.parametrize("priority", ["required", "preferred", "unspecified"])
def test_sole_target_weight_cancels(profile, job, priority):
    assert evaluate(profile, job, [skill("Python", priority)])["match_score"] == 80


def test_duplicates_highest_priority_all_evidence_and_sorted_output(profile, job):
    job["description"] = "Python required. PYTHON preferred. SQL required."
    targets = [skill(" SQL ", evidence="SQL required."),
               skill("Python", "preferred", "PYTHON preferred."),
               skill(" PYTHON ", "required", "Python required."),
               skill("Python", "required", "Python required.")]
    profile["skills"] = ["python", "PYTHON"]
    result = evaluate(profile, job, targets)
    assert result["match_score"] == 40  # two unique equally required targets
    assert result["skill_targets"][0]["priority"] == "required"
    assert result["skill_targets"][0]["evidence"] == ["PYTHON preferred.", "Python required."]
    assert result["matched_skills"] == ["python"]
    assert evaluate(profile, job, list(reversed(targets))) == result


def test_unicode_whitespace_case_and_punctuation(profile, job):
    profile["skills"] = [" ＰＹＴＨＯＮ ", "DATA\t Science", "C", "React.js", "Java", "PostgreSQL"]
    job["description"] = "python data science C++ C# React JavaScript SQL C"
    targets = [skill(s) for s in ["python", "data science", "C++", "C#", "React", "JavaScript", "SQL", "C"]]
    result = evaluate(profile, job, targets)
    assert result["match_score"] == 30  # exactly 3 of 8; no aliases/substrings/related credit
    assert result["matched_skills"] == ["C", "DATA\t Science", " ＰＹＴＨＯＮ "]


@pytest.mark.parametrize("category,profile_field,minimum,values", [
    ("education", "education_level", "bachelor", [("associate", 0), ("bachelor", 10), ("doctorate", 10), ("other", 0)]),
    ("experience", "experience_level", "mid", [("entry", 0), ("mid", 10), ("senior", 10)]),
])
def test_level_minimum_comparisons(profile, job, category, profile_field, minimum, values):
    job["description"] = minimum
    for value, expected in values:
        profile[profile_field] = value
        assert evaluate(profile, job, **{category: level(minimum)})["match_score"] == expected


@pytest.mark.parametrize("priority,expected", [("required", 20), ("preferred", 10), ("unspecified", 5)])
def test_level_priorities(profile, job, priority, expected):
    result = evaluate(profile, job, education=level("bachelor", priority, "Bachelor"),
                      experience=level("mid", priority, "Mid"))
    assert result["match_score"] == expected


def test_round_half_up_once_and_match_016(profile, job):
    # 80*2/3 + 10 + 10 = 73 1/3 (MATCH-016 baseline arithmetic).
    result = evaluate(profile, job, [skill("Python"), skill("SQL", "preferred")],
                      level("bachelor", evidence="Bachelor"), level("mid", evidence="Mid"))
    assert result["match_score"] == 100  # both skills present
    profile["skills"] = ["Python"]
    result = evaluate(profile, job, [skill("Python"), skill("SQL", "preferred")],
                      level("bachelor", evidence="Bachelor"), level("mid", evidence="Mid"))
    assert result["match_score"] == 73
    # .5 must round up, unlike Python's bankers rounding.
    result = evaluate(profile, job, education=level("bachelor", "unspecified", "Bachelor"))
    assert result["raw_score"] == 2.5 and result["match_score"] == 3
    # Two 2.5 components sum to 5, not individually rounded 3+3.
    result = evaluate(profile, job, education=level("bachelor", "unspecified", "Bachelor"),
                      experience=level("mid", "unspecified", "Mid"))
    assert result["match_score"] == 5


@pytest.mark.parametrize("change", [{"job_id": 999}, {"description": "Another description"}])
def test_requirements_bound_to_actual_job(profile, job, change):
    requirements = default_requirements(job)
    with pytest.raises(ValueError, match="different job or description"):
        score_job(profile, {**job, **change}, requirements=requirements)


@pytest.mark.parametrize("patch", [{"skills": []}, {"skills": [""]}, {"user_id": True},
                                    {"education_level": None}, {"experience_level": "expert"}])
def test_invalid_profile_rejected(profile, job, patch):
    with pytest.raises(ValueError):
        score_job({**profile, **patch}, job, requirements=default_requirements(job))


@pytest.mark.parametrize("target", [skill("Python", "mandatory"), skill("Python", evidence="invented"),
                                    skill(" ", evidence="Python")])
def test_invalid_targets_rejected(job, target):
    with pytest.raises(ValueError):
        prepare_requirements(job, {"skills": [target]})


def test_missing_description_rejected(job):
    del job["description"]
    with pytest.raises(ValueError, match="description"):
        prepare_requirements(job, {"skills": []})


def test_match_030_031_sparse_description_bias(profile, job):
    profile["skills"] = ["Python", "SQL", "Git", "Linux"]
    job["description"] = "Required: Python SQL Git Linux Docker. Bachelor degree. Mid experience."
    levels = {"education": level("bachelor", evidence="Bachelor degree"),
              "experience": level("mid", evidence="Mid experience")}
    sparse = evaluate(profile, job, [skill("Python")], **levels)
    fuller = evaluate(profile, job, [skill(n) for n in ["Python", "SQL", "Git", "Linux", "Docker"]], **levels)
    assert sparse["match_score"] == 100
    assert fuller["match_score"] == 84
    assert sparse["component_coverage"] == fuller["component_coverage"] == 1


def test_ambiguous_requirement_warning_is_preserved(profile, job):
    job["description"] = "Degree or equivalent experience."
    result = evaluate(profile, job, warnings=["education ambiguous", "education ambiguous"])
    assert result["match_score"] == 0
    assert result["warnings"] == ["education ambiguous"]
    assert result["education"]["status"] == "insufficient evidence"


@pytest.mark.parametrize("category,minimum", [("education", "PhD"), ("experience", "5 years")])
def test_unmapped_minima_rejected(job, category, minimum):
    job["description"] = minimum
    with pytest.raises(ValueError, match="minimum"):
        prepare_requirements(job, {"skills": [], category: level(minimum)})
