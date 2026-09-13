"""
Application Strategy: one recommended next action for a posting, combining
Application Readiness (engine.readiness), Job Trust Signals
(engine.trust_signals) and Company Intelligence (engine.company_intel) --
the three things this app knows about a posting that a raw fit score alone
doesn't capture.

A hard rule, not a weighted vote: a WARNING-level trust signal always wins
over a high readiness score. A posting that looks fake or closed is not
"a great match you should apply to now" just because its coverage number
is high -- the recommendation is to verify first, full stop.
"""
VERIFY_FIRST, SKIP, APPLY_NOW, APPLY_WITH_TAILORED_LETTER, STRETCH = (
    "VERIFY FIRST", "SKIP", "APPLY NOW", "APPLY WITH TAILORED LETTER", "STRETCH APPLICATION",
)


def recommend_strategy(readiness, trust, company=None):
    """readiness: a dict from engine.readiness.compute_readiness.
    trust: a dict from engine.trust_signals.trust_signals.
    company: optional dict from engine.company_intel.company_profile.
    """
    reasons = []

    if trust and trust.get("level") == "WARNING":
        return {
            "action": VERIFY_FIRST,
            "reasons": [f["text"] for f in trust["flags"] if f["level"] == "WARNING"],
        }

    if company and company.get("flags"):
        reasons.extend(company["flags"])

    band = (readiness or {}).get("band")

    if band == "NOT READY":
        reasons = list((readiness or {}).get("notes") or []) + reasons
        return {"action": SKIP, "reasons": reasons or [f"readiness {readiness.get('score')}/100"]}

    if band == "READY":
        return {"action": APPLY_NOW, "reasons": reasons}

    if band == "CONDITIONAL":
        missing = (readiness or {}).get("missing_must_haves") or []
        if missing:
            reasons.append("address these directly in your cover letter: " + ", ".join(missing))
        else:
            reasons.append("a solid overlap -- tailor the letter to close the remaining gaps")
        return {"action": APPLY_WITH_TAILORED_LETTER, "reasons": reasons}

    # STRETCH or unknown band
    reasons.append("worth trying but treat as a long shot -- the overlap is thin")
    return {"action": STRETCH, "reasons": reasons}
