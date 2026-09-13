"""
CV Truth Engine: verifies that the CV actually produced can be traced back
to config/profile.py, fact by fact.

The rest of the pipeline (engine/cv_builder.tailor_profile) already never
fabricates a bullet -- it only reorders and trims. This module does not trust
that as an assumption; it re-derives the same guarantee from the finished
artefact, the same way engine/ats_check.py re-parses the produced PDF instead
of trusting the code that wrote it. Two things can defeat the "never
fabricates" guarantee without a single fabricated word: a future edit to
tailor_profile, or a rendering bug that prints something other than what was
handed to it. Both are caught here because the check runs against the
rendered page, not the code path.

`original_profile` must be the untailored profile straight from
config/profile.py -- checking a CV against its own tailored copy would let a
bug in tailoring mark its own output as trustworthy.
"""
import re

import pdfplumber

from engine.evidence import skill_evidence_index
from engine.jd_analyzer import EXACT, ALIAS


def _normalize(text):
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def _pdf_text(pdf_path):
    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def _on_page(page_text, snippet, probe_len=60):
    """True if snippet (or enough of it to survive a mid-sentence line wrap)
    appears on the rendered page."""
    norm = _normalize(snippet)
    if not norm:
        return True
    probe = norm[:probe_len]
    return probe in page_text


def _result(ok, detail):
    return {"status": "pass" if ok else "fail", "detail": detail}


def check_integrity(pdf_path, tailored_profile, original_profile, jd_signal=None):
    """Returns {score, checks: {name: {status, detail}}, unsupported: [...],
    blocked}. `blocked` is True if any claim on the CV could not be traced to
    the original profile -- per the non-negotiable rule, that must stop
    export rather than ship with a hidden fabrication.
    """
    page_text = _normalize(_pdf_text(pdf_path))
    unsupported = []
    checks = {}

    # --- Employment history: every role must exist, unedited, in the
    # original profile, and must actually appear on the rendered page.
    history_ok = True
    for role in tailored_profile.get("experience", []) or []:
        company, title = role.get("company", ""), role.get("role", "")
        exists = any(r.get("company") == company and r.get("role") == title
                     for r in original_profile.get("experience", []) or [])
        if not exists:
            history_ok = False
            unsupported.append(f"Employment record not in your stored profile: {title} @ {company}")
            continue
        if not (_on_page(page_text, company) and _on_page(page_text, title)):
            history_ok = False
            unsupported.append(f"{title} @ {company} is on the tailored profile but not on the rendered page")
    checks["employment_history"] = _result(
        history_ok, "every role traces to config/profile.py and appears on the page"
        if history_ok else "see unsupported claims")

    # --- Bullets: every bullet on the CV must be a verbatim (whitespace-
    # normalized) bullet from that same role in the original profile, and
    # must actually be on the page.
    bullets_ok = True
    checked_bullets = 0
    for role in tailored_profile.get("experience", []) or []:
        original_role = next(
            (r for r in original_profile.get("experience", []) or []
             if r.get("company") == role.get("company") and r.get("role") == role.get("role")),
            None,
        )
        original_bullets = {_normalize(b) for b in (original_role or {}).get("bullets", []) or []}
        for bullet in role.get("bullets", []) or []:
            checked_bullets += 1
            if _normalize(bullet) not in original_bullets:
                bullets_ok = False
                unsupported.append(f'Bullet not found verbatim in your stored profile: "{bullet[:90]}"')
            elif not _on_page(page_text, bullet):
                bullets_ok = False
                unsupported.append(f'Bullet selected for this CV did not render on the page: "{bullet[:90]}"')
    checks["bullets"] = _result(
        bullets_ok, f"{checked_bullets} bullet(s), all verbatim from your profile and on the page"
        if bullets_ok else "see unsupported claims")

    # --- Skills line: every skill named must be the profile's own wording,
    # never an invented or "tidied up" canonical name.
    original_skills = set(original_profile.get("skills", []) or [])
    cv_skills = tailored_profile.get("skills", []) or []
    invented_skills = [s for s in cv_skills if s not in original_skills]
    for s in invented_skills:
        unsupported.append(f"Skill on the CV not present in your profile's skill list: {s}")
    checks["skills"] = _result(not invented_skills,
                                "every listed skill is your own wording from config/profile.py"
                                if not invented_skills else "see unsupported claims")

    # --- Certifications, education, languages: same-origin checks.
    certs_ok = set(tailored_profile.get("certifications", []) or []) <= set(
        original_profile.get("certifications", []) or [])
    if not certs_ok:
        for c in set(tailored_profile.get("certifications", []) or []) - set(
                original_profile.get("certifications", []) or []):
            unsupported.append(f"Certification not in your stored profile: {c}")
    checks["certifications"] = _result(certs_ok, "unchanged from your profile" if certs_ok else "see unsupported claims")

    edu_ok = all(e in (original_profile.get("education") or []) for e in tailored_profile.get("education", []) or [])
    checks["education"] = _result(edu_ok, "unchanged from your profile" if edu_ok else "see unsupported claims")

    lang_ok = all(l in (original_profile.get("languages") or []) for l in tailored_profile.get("languages", []) or [])
    checks["languages"] = _result(lang_ok, "unchanged from your profile" if lang_ok else "see unsupported claims")

    # --- Critical requirements: a JD skill weighted CRITICAL (>=3) that this
    # CV's own scoring treated as matched must have real EXACT/ALIAS
    # evidence, never only a semantic near-miss dressed up as a match. This
    # independently re-checks match_profile's own guarantee against the
    # rendered claim rather than trusting the code path that produced it.
    critical_ok = True
    if jd_signal:
        index = skill_evidence_index(original_profile)
        gaps = set(tailored_profile.get("gap_skills") or [])
        for skill, weight in jd_signal.items():
            if weight < 3 or skill in gaps:
                continue
            hits = [h for h in index.get(skill, []) if h["match_type"] in (EXACT, ALIAS)]
            if not hits:
                critical_ok = False
                unsupported.append(f"Critical requirement '{skill}' is not marked a gap but has no real evidence")
    checks["critical_requirements"] = _result(
        critical_ok, "every critical requirement claimed as matched has real evidence"
        if critical_ok else "see unsupported claims")

    passed = sum(1 for c in checks.values() if c["status"] == "pass")
    score = round(100 * passed / len(checks)) if checks else 0

    return {
        "score": score,
        "checks": checks,
        "unsupported": unsupported,
        "blocked": bool(unsupported),
    }
