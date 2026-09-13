"""
Structured candidate evidence -- the CV Truth Engine's source of truth.

Every skill claim the app displays or writes onto a CV must trace back to one
of these records. Built by reading config/profile.py once; nothing here is
invented, only indexed, so downstream code can answer "why does this posting
say I match?" with the exact sentence that proves it, not just a skill name.
"""
from engine.jd_analyzer import canonical_skills_detailed, EXACT, ALIAS, SEMANTIC

SKILL, EXPERIENCE, STAR, CERTIFICATION, EDUCATION, LANGUAGE = (
    "SKILL", "EXPERIENCE", "STAR", "CERTIFICATION", "EDUCATION", "LANGUAGE",
)


def build_evidence(profile):
    """Flat list of {text, category, source} records -- one per fact the
    profile actually states. `source` is a human-readable pointer back to
    where in the profile the text lives, e.g. "Loss Prevention Manager @
    Beispiel Logistik GmbH"."""
    records = []

    for skill in profile.get("skills", []) or []:
        records.append({"text": skill, "category": SKILL, "source": "Skills"})

    for role in profile.get("experience", []) or []:
        where = f"{role.get('role', '')} @ {role.get('company', '')}".strip(" @")
        if role.get("role"):
            records.append({"text": role["role"], "category": EXPERIENCE, "source": where})
        for bullet in role.get("bullets", []) or []:
            records.append({"text": bullet, "category": EXPERIENCE, "source": where})

    for ex in profile.get("star_examples", []) or []:
        text = " ".join(filter(None, [ex.get("situation"), ex.get("task"),
                                       ex.get("action"), ex.get("result")]))
        if text:
            records.append({"text": text, "category": STAR, "source": ex.get("title") or "STAR example"})

    for cert in profile.get("certifications", []) or []:
        records.append({"text": cert, "category": CERTIFICATION, "source": "Certifications"})

    for edu in profile.get("education", []) or []:
        text = ", ".join(filter(None, [edu.get("degree"), edu.get("institution"), edu.get("year")]))
        if text:
            records.append({"text": text, "category": EDUCATION, "source": "Education"})

    for lang in profile.get("languages", []) or []:
        text = f"{lang.get('name', '')} {lang.get('level', '')}".strip()
        if text:
            records.append({"text": text, "category": LANGUAGE, "source": "Languages"})

    return [r for r in records if r["text"]]


def skill_evidence_index(profile):
    """canonical_skill -> list of evidence records that mention it, each
    tagged with match_type (EXACT/ALIAS/SEMANTIC). Built once per profile."""
    index = {}
    for record in build_evidence(profile):
        for skill, match_type in canonical_skills_detailed(record["text"]).items():
            index.setdefault(skill, []).append({**record, "match_type": match_type})
    return index


def why_you_match(profile, jd_signal, index=None):
    """JD-requested skills with real (EXACT/ALIAS) evidence, each with the
    evidence text that proves it. Sorted by JD weight, strongest first."""
    index = index if index is not None else skill_evidence_index(profile)
    rows = []
    for skill, weight in jd_signal.items():
        hits = [h for h in index.get(skill, []) if h["match_type"] in (EXACT, ALIAS)]
        if hits:
            rows.append({"skill": skill, "weight": weight, "evidence": hits})
    return sorted(rows, key=lambda r: -r["weight"])


def why_you_dont(profile, jd_signal, index=None):
    """JD-requested skills with no real evidence. Each gap also carries any
    SEMANTIC near-misses found, so a genuine hole ("nothing about GDPR
    anywhere") reads differently from a near-miss ("you have fraud detection,
    this posting wants fraud investigation -- speak to the overlap")."""
    index = index if index is not None else skill_evidence_index(profile)
    rows = []
    for skill, weight in jd_signal.items():
        hits = [h for h in index.get(skill, []) if h["match_type"] in (EXACT, ALIAS)]
        if hits:
            continue
        related = [h for h in index.get(skill, []) if h["match_type"] == SEMANTIC]
        rows.append({"skill": skill, "weight": weight, "related_evidence": related})
    return sorted(rows, key=lambda r: -r["weight"])
