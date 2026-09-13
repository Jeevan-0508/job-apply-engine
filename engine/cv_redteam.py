"""
CV Red Team: reads a tailored CV the way a skeptical recruiter would, not
the way engine.integrity does.

engine.integrity answers "is every word on this CV true, traced back to
config/profile.py" -- and blocks export if not. This module never blocks
anything and never touches truth at all; it assumes integrity already
passed and asks a different question: even though every bullet here is
true, does it read as *persuasive*? A CV can be 100% honest and still be
weak -- unquantified, passive, generic filler dressed as achievement. That
is a craft problem, not a fabrication problem, so it is surfaced as
findings for the candidate to act on, never as a blocker.

Entirely rule-based (regex/keyword), same as the rest of this app -- no
LLM judgment call on "is this a good bullet", because that would be
unreviewable and inconsistent between two otherwise-identical runs.
"""
import re

_NUMBER_RE = re.compile(
    r"(\d[\d,.]*\s?%|\€\s?\d|\d[\d,.]*\s?\€|\bEUR\b|\$\s?\d|\d+x\b|\bx\d+\b|\d[\d,.]*\+?\b)"
)

_WEAK_OPENERS = {
    "helped", "worked", "responsible", "assisted", "involved", "participated",
    "supported", "tasked", "handled", "in charge",
}

_FILLER_PHRASES = [
    "team player", "results-driven", "detail-oriented", "self-starter",
    "hard worker", "go-getter", "think outside the box", "synergy",
    "highly motivated", "proven track record", "dynamic environment",
]

_MAX_BULLET_WORDS = 35


def _first_word(bullet):
    words = re.findall(r"[A-Za-z]+", bullet or "")
    return words[0].lower() if words else ""


def _check_bullet(bullet):
    issues = []
    if not _NUMBER_RE.search(bullet or ""):
        issues.append("no number/%/currency -- impact is not quantified")
    if _first_word(bullet) in _WEAK_OPENERS:
        issues.append(f"opens with a weak/passive verb ('{_first_word(bullet)}') -- lead with the action you owned")
    lower = (bullet or "").lower()
    hit_fillers = [p for p in _FILLER_PHRASES if p in lower]
    if hit_fillers:
        issues.append("generic filler phrase(s): " + ", ".join(hit_fillers))
    word_count = len(re.findall(r"\S+", bullet or ""))
    if word_count > _MAX_BULLET_WORDS:
        issues.append(f"{word_count} words -- likely too long for a single bullet, tighten it")
    return issues


def red_team_cv(tailored_profile):
    """Findings per bullet across every role, plus repeated-opening-verb
    detection across the whole CV (a craft smell: every bullet starting
    with 'Led' reads as templated, not a factual problem)."""
    findings = []
    opener_counts = {}

    for role in tailored_profile.get("experience", []) or []:
        where = f"{role.get('role', '')} @ {role.get('company', '')}".strip(" @")
        for bullet in role.get("bullets", []) or []:
            issues = _check_bullet(bullet)
            opener = _first_word(bullet)
            if opener:
                opener_counts[opener] = opener_counts.get(opener, 0) + 1
            if issues:
                findings.append({"where": where, "bullet": bullet, "issues": issues})

    repeated_openers = [w for w, count in opener_counts.items() if count >= 3]
    if repeated_openers:
        findings.append({
            "where": "whole CV",
            "bullet": None,
            "issues": [f"opening verb '{w}' repeated {opener_counts[w]}x across bullets -- reads as templated"
                       for w in repeated_openers],
        })

    total_bullets = sum(len(r.get("bullets", []) or []) for r in tailored_profile.get("experience", []) or [])
    flagged_bullets = sum(1 for f in findings if f["bullet"] is not None)
    clean_ratio = 1 - (flagged_bullets / total_bullets) if total_bullets else 1.0
    score = round(100 * clean_ratio)

    if score >= 85:
        band = "STRONG"
    elif score >= 60:
        band = "SOLID"
    elif score >= 35:
        band = "NEEDS WORK"
    else:
        band = "WEAK"

    return {
        "score": score,
        "band": band,
        "total_bullets": total_bullets,
        "flagged_bullets": flagged_bullets,
        "findings": findings,
    }
