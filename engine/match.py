"""
Scores how well one posting fits the profile, and explains the number.

A search that returns fifty postings in no particular order is still fifty
postings to read. Ranking them turns that into a shortlist.

Two numbers are reported rather than one blended score, because they answer
different questions and blending them hides both:

- coverage: of what this posting asks for, how much can the profile evidence?
  This is the "will my CV survive the keyword screen" number.
- relevance: of what the profile can do, how much does this posting ask for?
  This is the "is this the kind of work I actually do" number.

They are the same two sets measured in opposite directions. A single ratio of
demand met also has a pathology worth avoiding: a posting listing four skills
becomes all-or-nothing, so a thin, precisely relevant posting can score zero
while a keyword-stuffed generic one scores fifty. Postings with little
detectable signal are therefore labelled as such instead of being ranked as if
the number meant something.

A low score is usually missing vocabulary rather than a bad match, and that is
worth knowing before applying rather than after being filtered out.
"""
from collections import Counter

from engine.jd_analyzer import (analyze_jd, canonical_skills, match_profile,
                                profile_corpus)

# below this many weighted points the ratio is not a measurement
LOW_SIGNAL = 6
TITLE_BOOST = 2

BANDS = [
    (75, "strong", "Most of what this posting asks for is evidenced in your profile."),
    (50, "good", "A solid overlap, with gaps worth addressing in the letter."),
    (30, "partial", "About a third of the demand is evidenced -- a stretch application."),
    (0, "weak", "Little of what this posting asks for appears in your profile."),
]


def _band(score):
    return next((b, v) for threshold, b, v in BANDS if score >= threshold)


def score_text(jd_text, profile, title=""):
    """Score a job description, counting the title more heavily than the body.

    The title carries the role. A description mentioning Excel twice should not
    outrank one whose title is the job being looked for.
    """
    signal = analyze_jd(jd_text)
    if title:
        for skill in analyze_jd(title):
            signal[skill] = signal.get(skill, 0) * TITLE_BOOST or TITLE_BOOST
        signal = dict(sorted(signal.items(), key=lambda x: (-x[1], x[0])))

    profile_vocab = set()
    for skill in profile.get("skills", []) or []:
        profile_vocab |= canonical_skills(skill)
    profile_vocab |= canonical_skills(profile_corpus(profile))

    if not signal:
        return {
            "coverage": 0, "relevance": 0, "band": "unknown", "low_signal": True,
            "verdict": "No known skills detected in this posting -- nothing to score against.",
            "signal": {}, "matched": [], "missing": [], "total_weight": 0,
            "core_missing": [], "core_total": 0,
        }

    matched, missing = match_profile(profile.get("skills", []), signal, profile_corpus(profile))
    total = sum(signal.values())
    covered = total - sum(signal[s] for s in missing)
    coverage = round(100 * covered / total) if total else 0

    asked = set(signal)
    relevance = round(100 * len(asked & profile_vocab) / len(asked)) if asked else 0

    core = [s for s, w in signal.items() if w >= 3]
    core_missing = [s for s in core if s in missing]

    band, verdict = _band(coverage)
    low_signal = total < LOW_SIGNAL
    if low_signal:
        band = "low signal"
        verdict = (f"Only {len(signal)} recognisable skill(s) in this posting, so the "
                   "percentages are not a reliable measurement -- read it yourself.")
    elif core_missing:
        verdict += (f" Missing {len(core_missing)} of {len(core)} core requirement(s): "
                    + ", ".join(core_missing) + ".")

    return {
        "coverage": coverage,
        "relevance": relevance,
        "band": band,
        "low_signal": low_signal,
        "verdict": verdict,
        "signal": signal,
        "matched": matched,
        "missing": missing,
        "total_weight": total,
        "core_missing": core_missing,
        "core_total": len(core),
    }


def score_job(job, profile, description=None):
    """Score a search result, using the full description when one is available."""
    title = (job or {}).get("title", "")
    if description and len(description) >= 200:
        result = score_text(description, profile, title=title)
        result["basis"] = "full description"
        return result

    fallback = " ".join(filter(None, [job.get("snippet"), job.get("company")]))
    result = score_text(fallback, profile, title=title)
    result["basis"] = "title only -- fetch the description for a real score"
    return result


def demand_report(scored):
    """Which skills the market keeps asking for that the profile cannot evidence.

    Aggregated across every posting scored in a session. This is the most
    actionable output in the app: it turns a low score from a verdict into a
    list of things to add to the profile, ordered by how often they cost a
    match.
    """
    missing = Counter()
    asked = Counter()
    for result in scored:
        for skill in result.get("signal", {}):
            asked[skill] += 1
        for skill in result.get("missing", []):
            missing[skill] += 1

    rows = []
    for skill, count in missing.most_common():
        rows.append({
            "skill": skill,
            "postings_missing": count,
            "postings_asking": asked[skill],
            "share": count / len(scored) if scored else 0,
        })
    return rows
