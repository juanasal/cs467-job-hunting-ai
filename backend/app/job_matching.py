"""Pure exact-match qualification baseline; no extraction or preference decisions."""

from dataclasses import dataclass
from fractions import Fraction
from typing import Mapping
import unicodedata


METHOD_VERSION = "exact-v1"
_WEIGHTS = {"required": Fraction(2), "preferred": Fraction(1),
            "unspecified": Fraction(1, 2)}
_LEVEL_CREDIT = {"required": Fraction(1), "preferred": Fraction(1, 2),
                 "unspecified": Fraction(1, 4)}
_EDUCATION = ("high_school", "associate", "bachelor", "master", "doctorate")
_EXPERIENCE = ("entry", "mid", "senior")


def normalize_skill(value: str) -> str:
    """Preserve punctuation while normalizing Unicode, case, and whitespace."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _id(value, field):
    if type(value) is not int or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


@dataclass(frozen=True)
class SkillTarget:
    name: str
    priority: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class LevelTarget:
    minimum: str
    priority: str
    evidence: tuple[str, ...]


@dataclass(frozen=True)
class PreparedRequirements:
    job_id: int
    description: str
    skills: tuple[SkillTarget, ...]
    education: LevelTarget | None
    experience: LevelTarget | None
    warnings: tuple[str, ...]


def _evidence(target, description):
    priority = target.get("priority")
    if priority not in _WEIGHTS:
        raise ValueError("priority must be required, preferred, or unspecified")
    evidence = _text(target.get("evidence"), "evidence")
    if evidence not in description:
        raise ValueError("evidence must be an exact span of the job description")
    return priority, evidence


def prepare_requirements(job: Mapping, requirements: Mapping, *, warnings=()):
    """Validate hand-authored/extracted requirements, deduplicate, and bind to job.

    This does not parse descriptions or determine whether a span is a qualification.
    Unknown/ambiguous minima must be None, with a caller-supplied warning.
    """
    job_id = _id(job.get("job_id"), "job_id")
    description = _text(job.get("description"), "description")
    skills = requirements.get("skills")
    if not isinstance(skills, list):
        raise ValueError("requirements.skills must be a list (empty when unknown)")
    grouped = {}
    for target in skills:
        name = normalize_skill(_text(target.get("name"), "target name"))
        priority, evidence = _evidence(target, description)
        if name not in grouped:
            grouped[name] = (priority, {evidence})
        else:
            old_priority, spans = grouped[name]
            spans.add(evidence)
            if _WEIGHTS[priority] > _WEIGHTS[old_priority]:
                grouped[name] = (priority, spans)

    def level(category, levels):
        target = requirements.get(category)
        if target is None:
            return None
        minimum = target.get("minimum")
        allowed = (*levels, "other") if category == "education" else levels
        if minimum not in allowed:
            raise ValueError(f"invalid {category} minimum; use None for ambiguity")
        priority, evidence = _evidence(target, description)
        return LevelTarget(minimum, priority, (evidence,))

    if isinstance(warnings, str):
        raise ValueError("warnings must be a sequence of strings")
    warning_text = tuple(sorted({_text(w, "warning") for w in warnings}))
    return PreparedRequirements(
        job_id, description,
        tuple(SkillTarget(name, priority, tuple(sorted(spans)))
              for name, (priority, spans) in sorted(grouped.items())),
        level("education", _EDUCATION), level("experience", _EXPERIENCE),
        warning_text,
    )


def _level_result(value, target, levels):
    if target is None or value not in levels or target.minimum not in levels:
        status, points = "insufficient evidence", Fraction(0)
    elif levels.index(value) < levels.index(target.minimum):
        status, points = "below minimum", Fraction(0)
    else:
        status, points = "minimum met", 10 * _LEVEL_CREDIT[target.priority]
    return points, {
        "profile_level": value,
        "minimum": target.minimum if target else None,
        "priority": target.priority if target else None,
        "evidence": list(target.evidence) if target else [],
        "status": status,
        "points": float(points),
    }


def score_job(profile: Mapping, job: Mapping, *, requirements: PreparedRequirements):
    """Score shared records using explicit prepared qualifications.

    Requires valid scoring fields; callers validate the rest of the shared records.
    Returns internal diagnostics plus applicable match-result fields, without time.
    No inclusion/exclusion decision is made here.
    """
    user_id = _id(profile.get("user_id"), "user_id")
    job_id = _id(job.get("job_id"), "job_id")
    description = _text(job.get("description"), "description")
    if (requirements.job_id, requirements.description) != (job_id, description):
        raise ValueError("requirements belong to a different job or description")
    skills = profile.get("skills")
    if not isinstance(skills, list) or not skills:
        raise ValueError("profile.skills must be a nonempty list")
    profile_skills = {}
    for skill in skills:
        profile_skills.setdefault(normalize_skill(_text(skill, "profile skill")), skill)
    education = profile.get("education_level")
    experience = profile.get("experience_level")
    if education not in (*_EDUCATION, "other"):
        raise ValueError("invalid or missing profile education_level")
    if experience not in _EXPERIENCE:
        raise ValueError("invalid or missing profile experience_level")

    targets = []
    matched_weight = total_weight = Fraction(0)
    matched = []
    for target in requirements.skills:
        weight = _WEIGHTS[target.priority]
        source = profile_skills.get(target.name)
        total_weight += weight
        if source is not None:
            matched_weight += weight
            matched.append(source)
        targets.append({"name": target.name, "priority": target.priority,
                        "weight": float(weight), "evidence": list(target.evidence),
                        "profile_skill": source, "credit": int(source is not None),
                        "status": "exact match" if source is not None else "unmatched"})
    skill_points = 80 * matched_weight / total_weight if total_weight else Fraction(0)
    education_points, education_result = _level_result(education, requirements.education, _EDUCATION)
    experience_points, experience_result = _level_result(experience, requirements.experience, _EXPERIENCE)
    raw = skill_points + education_points + experience_points
    rounded = (raw + Fraction(1, 2)).numerator // (raw + Fraction(1, 2)).denominator
    reasons = [f"Skills: {float(skill_points):g}/80 points."]
    if not targets:
        reasons.append("Skills: insufficient evidence; no evaluable targets.")
    for target in targets:
        reasons.append(f"{target['name']} ({target['priority']}): {target['status']}; "
                       f"evidence: {target['evidence']!r}.")
    for name, result in (("Education", education_result), ("Experience", experience_result)):
        reasons.append(f"{name}: {result['points']:g}/10 points; {result['status']}; "
                       f"profile={result['profile_level']}, minimum={result['minimum']}, "
                       f"priority={result['priority']}; evidence: {result['evidence']!r}.")
    reasons.extend(requirements.warnings)
    reasons.append("Qualification alignment only; preference compatibility has not been evaluated.")
    coverage = (80 if targets else 0) + sum(
        10 for result in (education_result, experience_result)
        if result["status"] != "insufficient evidence"
    )
    return {
        "user_id": user_id, "job_id": job_id, "match_score": rounded,
        "matched_skills": matched, "match_explanation": " ".join(reasons),
        "method_version": METHOD_VERSION,
        "qualification_fit": "good" if rounded >= 60 else "weak",
        "skill_targets": targets, "education": education_result,
        "experience": experience_result,
        "component_points": {"skills": float(skill_points), "education": float(education_points),
                             "experience": float(experience_points)},
        "raw_score": float(raw), "component_coverage": coverage / 100,
        "warnings": list(requirements.warnings),
    }
