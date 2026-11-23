"""Extract explicit applicant qualifications from normalized job descriptions."""

import re
from typing import Mapping

from app.job_matching import normalize_skill


_TECHNICAL = frozenset({
    "aws", "c#", "c++", "docker", "excel", "git", "java", "javascript",
    "linux", "postgresql", "python", "react", "react.js", "sql", "typescript",
    "ui development",
})
_SOFT = frozenset({
    "communication", "communication skills", "leadership", "problem solving",
    "problem-solving", "teamwork", "written communication", "verbal communication",
})
_EDUCATION = {
    "high school diploma": "high_school",
    "associate": "associate",
    "bachelor": "bachelor",
    "master": "master",
    "doctorate": "doctorate",
    "phd": "doctorate",
}
_EXPERIENCE = {"entry": "entry", "mid": "mid", "senior": "senior"}

_STATEMENT = re.compile(r"(?:[^.!?\n…]|\.(?=\w))+[.!?…]*")
_HEADING = re.compile(
    r"^(?:(required|preferred)(?:\s+(?:qualifications|skills))?"
    r"|(minimum qualifications)|(qualifications|requirements))\s*:\s*"
)
_PREFIX = re.compile(
    r"^(?:(?:applicants|candidates|you)\s+)?"
    r"(?:(must have|must know|should have|should know|need to have)\s+"
    r"|(proficiency in|experience (?:with|in)|knowledge of)\s+)"
)
_SUFFIX = re.compile(r"\s+(?:(?:is|are)\s+)?(required|preferred|desirable|a plus)$")
_NEGATION = re.compile(r"\b(?:no|not|never|without|waived|optional|unnecessary)\b|n['’]t\b")
_ALTERNATIVE = re.compile(r"\bor\b|/")
_LIST_SEPARATOR = re.compile(r"\s*(?:[,;]\s*(?:and\s+)?|\band\b)\s*")
_DEGREE = re.compile(r"(associate|bachelor|master)(?:['’]s)? degree")
_LEVEL = re.compile(r"(entry|mid|senior)(?:[- ]level)?(?: (?:work|professional))? experience")


def _qualification(statement, section_priority):
    """Return the candidate text and priority if it has a qualification cue."""
    heading = _HEADING.match(statement)
    if heading:
        section_priority = heading[1] or ("required" if heading[2] else "unspecified")
        statement = statement[heading.end():]

    suffix = _SUFFIX.search(statement)
    if suffix:
        statement = statement[:suffix.start()]
    prefix = _PREFIX.match(statement)
    if prefix:
        statement = statement[prefix.end():]
    if not (heading or suffix or prefix or section_priority):
        return None

    priority = section_priority or "unspecified"
    if prefix and prefix[1] in {"must have", "must know", "need to have"}:
        priority = "required"
    if suffix:
        suffix_priority = "required" if suffix[1] == "required" else "preferred"
        priority = suffix_priority if priority in {"unspecified", suffix_priority} else "unspecified"
    return statement, priority


def _minimum(targets, category, warnings):
    if not targets:
        return None
    # The scorer accepts one evidence span and minimum for each level category.
    if len({(target["minimum"], target["priority"]) for target in targets}) > 1:
        warnings.add(f"{category}_ambiguous")
        return None
    return targets[0]


def extract_requirements(job: Mapping) -> dict:
    """Read description only and return qualification targets and warning codes.

    Pass the returned dictionary to prepare_requirements with its warnings.
    The categorized skill lists retain the same targets as the combined skills list.
    """
    technical = []
    soft = []
    education = []
    experience = []
    warnings = set()
    description = job.get("description")
    if isinstance(description, str) and description.strip():
        if description.rstrip().endswith(("...", "…")):
            warnings.add("description_partial")
        section_priority = None
        for match in _STATEMENT.finditer(description):
            evidence = match[0].strip()
            statement = normalize_skill(evidence.rstrip(".!?…").lstrip("-•* "))
            heading = _HEADING.match(statement)
            if heading and not statement[heading.end():]:
                section_priority = heading[1] or ("required" if heading[2] else "unspecified")
                continue
            if statement.endswith(":"):
                section_priority = None
            if _NEGATION.search(statement) or evidence.endswith("?"):
                continue
            candidate = _qualification(statement, section_priority)
            if candidate is None:
                continue
            body, priority = candidate
            if _ALTERNATIVE.search(body):
                warnings.add("qualification_alternative")
                continue
            target = {"priority": priority, "evidence": evidence}
            for item in _LIST_SEPARATOR.split(body):
                item = re.sub(r"^(?:an?|the)\s+", "", item)
                degree = _DEGREE.fullmatch(item)
                level = _LEVEL.fullmatch(item)
                skill = re.sub(r"\s+experience$", "", item)
                if degree or item in {"high school diploma", "doctorate", "doctoral degree", "phd"}:
                    name = degree[1] if degree else item
                    minimum = _EDUCATION.get(name, "doctorate")
                    education.append({**target, "minimum": minimum})
                elif level:
                    experience.append({**target, "minimum": _EXPERIENCE[level[1]]})
                elif skill in _TECHNICAL:
                    technical.append({**target, "name": skill})
                elif skill in _SOFT:
                    soft.append({**target, "name": skill})
                elif re.fullmatch(r"(?:r|c|go|bi|ba|bs|ms|ma)(?: degree)?", item):
                    warnings.add("qualification_abbreviation_ambiguous")
                elif re.search(r"\byears?\b", item) and "experience" in item:
                    warnings.add("experience_level_unmapped")

    return {
        "technical_skills": technical,
        "soft_skills": soft,
        "skills": technical + soft,
        "education": _minimum(education, "education", warnings),
        "experience": _minimum(experience, "experience", warnings),
        "education_mentions": education,
        "experience_mentions": experience,
        "warnings": sorted(warnings),
    }
