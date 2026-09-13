"""
Job Quality Score: how trustworthy and complete a posting is as a piece
of information, entirely separate from how well it matches a candidate.

A perfect-fit posting that is a bare title with no link and no company
name is not a "good job" in the sense this score means -- it is a low-
information listing that happens to mention the right words. Candidate
fit lives in engine/match.py and never touches this file; this score
never touches candidate fit. Mixing the two would let a high match score
paper over a listing nobody could actually act on, or vice versa.

Inputs are all things the app already has by the time it has fetched a
job: the raw job dict from a search/aggregator source, the description
text and its status (FULL/PARTIAL/TITLE_ONLY/UNAVAILABLE, from
engine.search.job_detail.classify), and optionally a freshness result
from engine.freshness. None of these are refetched here -- this module
only scores what it is handed.
"""
import re

from engine.dedupe import ID_TRUSTED_SOURCES

# Weights sum to 100. Chosen so no single missing signal (e.g. no salary,
# which most German postings omit anyway) can sink an otherwise-solid
# listing, but a genuinely thin posting (no link, no description, single
# unverified source) scores low across the board.
W_SOURCE = 15
W_DESCRIPTION = 25
W_FIELDS = 15
W_CORROBORATION = 10
W_FRESHNESS = 15
W_REQUIREMENTS = 10
W_SALARY = 10

_SALARY_RE = re.compile(
    r"(\u20ac\s?\d[\d.,]*|\d[\d.,]*\s?\u20ac|EUR\s?\d[\d.,]*|\d[\d.,]*\s?EUR|"
    r"\bgehalt\b|\bsalary\b|\bcompensation\b|\bvergütung\b)",
    re.IGNORECASE,
)
_REQUIREMENTS_RE = re.compile(
    r"(\brequirements?\b|\bqualifications?\b|\bmust have\b|\byou bring\b|"
    r"\banforderungen\b|\bvoraussetzungen\b|\bihr profil\b|\bwas du mitbringst\b)",
    re.IGNORECASE,
)

_DESCRIPTION_POINTS = {"FULL": 1.0, "PARTIAL": 0.55, "TITLE_ONLY": 0.15, "UNAVAILABLE": 0.0}


def _source_reliability(job):
    """1.0 for an ATS-native source we can identify a stable id from
    (Greenhouse/Lever), 0.8 for a named official source (e.g. the
    Bundesagentur für Arbeit feed), 0.5 for anything else named, 0.2 if
    the posting does not even say where it came from."""
    source = (job.get("source") or "").strip()
    key = source.lower()
    if key in ID_TRUSTED_SOURCES:
        return 1.0
    if "arbeitsagentur" in key or "bundesagentur" in key:
        return 0.8
    if source:
        return 0.5
    return 0.2


def _field_completeness(job):
    fields = ["company", "title", "location", "link", "posted"]
    present = sum(1 for f in fields if (job.get(f) or "").strip())
    return present / len(fields)


def _corroboration(job):
    """More than one source independently returning the same canonical
    job (matched_sources, set by dedupe) is itself weak evidence the
    posting is real and current -- not proof, just a mild positive."""
    sources = job.get("matched_sources") or ([job.get("source")] if job.get("source") else [])
    sources = [s for s in sources if s]
    if len(sources) >= 2:
        return 1.0
    if len(sources) == 1:
        return 0.6
    return 0.0


def _description_completeness(description_status):
    return _DESCRIPTION_POINTS.get(description_status, 0.0)


def _has_requirements(description):
    return bool(description) and bool(_REQUIREMENTS_RE.search(description))


def _has_salary(description):
    return bool(description) and bool(_SALARY_RE.search(description))


def score_job_quality(job, description=None, description_status=None, freshness_score=None):
    """Job Quality Score/100 for one posting, plus the factor breakdown
    that produced it -- always shown alongside the number so the score
    is never a black box."""
    description = description or ""

    source_factor = _source_reliability(job)
    field_factor = _field_completeness(job)
    corroboration_factor = _corroboration(job)
    description_factor = _description_completeness(description_status)
    requirements_present = _has_requirements(description)
    salary_present = _has_salary(description)

    if freshness_score is None:
        freshness_factor = 0.5  # unknown freshness is neither rewarded nor punished
        freshness_known = False
    else:
        freshness_factor = max(0.0, min(1.0, freshness_score / 100))
        freshness_known = True

    points = {
        "source_reliability": round(source_factor * W_SOURCE, 1),
        "description_completeness": round(description_factor * W_DESCRIPTION, 1),
        "field_completeness": round(field_factor * W_FIELDS, 1),
        "corroboration": round(corroboration_factor * W_CORROBORATION, 1),
        "freshness": round(freshness_factor * W_FRESHNESS, 1),
        "requirements_disclosed": W_REQUIREMENTS if requirements_present else 0,
        "salary_disclosed": W_SALARY if salary_present else 0,
    }
    total = round(sum(points.values()))

    if total >= 80:
        band = "HIGH"
    elif total >= 55:
        band = "MEDIUM"
    elif total >= 30:
        band = "LOW"
    else:
        band = "VERY LOW"

    notes = []
    if source_factor < 0.5:
        notes.append("source not identified")
    if field_factor < 1.0:
        notes.append("missing basic fields (company/location/link/posted)")
    if description_factor == 0.0:
        notes.append("no description could be read")
    if not freshness_known:
        notes.append("freshness not evaluated")
    if not requirements_present:
        notes.append("no clear requirements section found")
    if not salary_present:
        notes.append("no salary/compensation figure disclosed")

    return {
        "score": total,
        "band": band,
        "factors": points,
        "notes": notes,
    }
