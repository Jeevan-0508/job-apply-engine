import re

from engine.skill_map import SKILL_ALIASES, SKILL_WEIGHTS


def _phrases(skill):
    """Canonical name plus its aliases, longest first so the specific wins."""
    return sorted({skill, *SKILL_ALIASES.get(skill, [])}, key=len, reverse=True)


def analyze_jd(jd_text):
    """Map a job description onto the weighted skill vocabulary.

    Returns {canonical_skill: weight} sorted by weight. Aliases are folded into
    their canonical name, so downstream code only ever sees canonical keys and
    a JD written in German scores the same as its English equivalent.
    """
    jd_text = (jd_text or "").lower()
    signal = {}

    for skill, weight in SKILL_WEIGHTS.items():
        for phrase in _phrases(skill):
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", jd_text):
                signal[skill] = weight
                break

    return dict(sorted(signal.items(), key=lambda x: (-x[1], x[0])))


def canonical_skills(text):
    """Canonical vocabulary names present in one free-text string.

    Used to read a profile's own wording -- "Audit Frameworks", "RCA",
    "Excel (VBA, Pivot)" -- in the same vocabulary a JD is scored in. Without
    this, matching a profile against a JD is string equality between two
    differently-phrased lists, which mostly fails.
    """
    text = (text or "").lower()
    hits = set()
    for skill in SKILL_WEIGHTS:
        for phrase in _phrases(skill):
            if re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text):
                hits.add(skill)
                break
    return hits


def match_profile(profile_skills, jd_signal, extra_corpus=""):
    """Split a JD's demands into what the profile evidences and what it doesn't.

    Returns (matched, gaps): matched keeps the profile's own wording for
    display; gaps are canonical JD skills with no evidence anywhere in the
    profile, including free-text summary and bullets, so a skill proven in
    experience is not reported as missing just because it is absent from the
    skills list.
    """
    wanted = set(jd_signal)
    scored, covered = [], set()

    for skill in profile_skills or []:
        hit = canonical_skills(skill) & wanted
        if hit:
            scored.append((max(jd_signal[h] for h in hit), skill))
            covered |= hit

    # strongest JD signal first, so a cover letter leads on what the JD wants most
    matched = [s for _, s in sorted(scored, key=lambda x: -x[0])]

    covered |= canonical_skills(extra_corpus) & wanted
    gaps = [s for s in jd_signal if s not in covered]
    return matched, gaps


def profile_corpus(profile):
    """All free text in a profile that can evidence a skill."""
    parts = [profile.get("summary", ""), profile.get("title", "")]
    for role in profile.get("experience", []) or []:
        parts += [role.get("title", ""), role.get("company", "")]
        parts += role.get("bullets", []) or []
    for ex in profile.get("star_examples", []) or []:
        parts += [ex.get(k, "") for k in ("title", "situation", "task", "action", "result")]
        parts += ex.get("skills_tags", []) or []
    parts += profile.get("certifications", []) or []
    return " \n ".join(p for p in parts if isinstance(p, str))
