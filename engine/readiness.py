"""
Application Readiness Score: not "does this posting fit you" (that's
engine.match's coverage/relevance) but "are you actually ready to apply to
this specific one right now" -- the one number this app is missing that a
candidate scanning fifty scored postings would otherwise have to reconstruct
in their head from four different numbers on four different tabs.

Deliberately composed from scores that already exist elsewhere rather than
recomputing anything: a fit result from engine.match.score_job/score_text,
an optional severity map from engine.jd_analyzer.analyze_severity, and an
optional listing-quality score from engine.job_quality.score_job_quality.
Each is optional because not every caller has fetched a full description
yet -- readiness degrades honestly (documented in `notes`) rather than
guessing at inputs it was not given.
"""

# Weights sum to 100 when every input is available. Coverage carries the
# most weight because it is the input that exists for every job regardless
# of how much extra analysis was run; must-have coverage is next because a
# single missing hard requirement matters more than a few extra points of
# general overlap.
W_COVERAGE = 35
W_MUST_HAVE = 30
W_RELEVANCE = 15
W_QUALITY = 20

READY, CONDITIONAL, STRETCH, NOT_READY = "READY", "CONDITIONAL", "STRETCH", "NOT READY"


def _must_have_coverage(fit, severity):
    """Fraction of MUST-severity skills the fit already evidenced as
    matched (i.e. not in fit['missing']). None if there are no MUST-tagged
    skills to measure at all -- that's a "not applicable", not a zero."""
    if not severity:
        return None, []
    must_skills = [s for s, tag in severity.items() if tag == "MUST"]
    if not must_skills:
        return None, []
    signal = fit.get("signal") or {}
    missing = set(fit.get("missing") or [])
    relevant_musts = [s for s in must_skills if s in signal]
    if not relevant_musts:
        return None, []
    missing_musts = [s for s in relevant_musts if s in missing]
    covered = len(relevant_musts) - len(missing_musts)
    return covered / len(relevant_musts), missing_musts


def compute_readiness(fit, severity=None, quality_score=None):
    """Composite readiness/100 + band + factor breakdown + notes.

    fit: a result dict from engine.match.score_text/score_job (needs at
         least 'coverage', 'relevance', 'signal', 'missing').
    severity: optional {skill: MUST/PREFERRED/STANDARD} from
         engine.jd_analyzer.analyze_severity.
    quality_score: optional 0-100 from engine.job_quality.score_job_quality.
    """
    notes = []

    coverage_factor = max(0, min(100, fit.get("coverage", 0))) / 100
    relevance_factor = max(0, min(100, fit.get("relevance", 0))) / 100

    must_ratio, missing_musts = _must_have_coverage(fit, severity or {})
    if must_ratio is None:
        must_factor = 0.5  # no MUST-tagged skill detected -- neutral, not penalized
        notes.append("no must-have requirements detected in this posting's language")
    else:
        must_factor = must_ratio
        if missing_musts:
            notes.append("missing a must-have requirement: " + ", ".join(missing_musts))

    if quality_score is None:
        quality_factor = 0.5
        notes.append("listing quality not evaluated")
    else:
        quality_factor = max(0, min(100, quality_score)) / 100

    points = {
        "coverage": round(coverage_factor * W_COVERAGE, 1),
        "must_have_coverage": round(must_factor * W_MUST_HAVE, 1),
        "relevance": round(relevance_factor * W_RELEVANCE, 1),
        "listing_quality": round(quality_factor * W_QUALITY, 1),
    }
    total = round(sum(points.values()))

    if fit.get("low_signal"):
        notes.append("posting had too little detectable signal for a reliable score")

    # A missing must-have caps the band regardless of the numeric total --
    # a stated hard requirement you cannot evidence is exactly the case
    # this score exists to surface loudly, not average away.
    if missing_musts:
        band = NOT_READY if total < 40 else CONDITIONAL
    elif total >= 80:
        band = READY
    elif total >= 55:
        band = CONDITIONAL
    elif total >= 30:
        band = STRETCH
    else:
        band = NOT_READY

    return {
        "score": total,
        "band": band,
        "factors": points,
        "missing_must_haves": missing_musts,
        "notes": notes,
    }
