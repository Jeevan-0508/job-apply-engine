"""
Company Intelligence: what this app's own record already knows about a
company, surfaced back before applying again.

Deliberately not a scraper -- there is no live "company info" API here, and
per the app's own anti-overengineering rule, bolting on a scrape of
Glassdoor/LinkedIn to fake that would be exactly the kind of unreviewable,
easily-broken integration this app has avoided everywhere else. What it
*does* have, honestly, is data/pipeline.json: every posting from this
company the candidate has already seen, applied to, or heard back from.
That is real, verifiable, and often more useful anyway -- "you've applied
here 3 times with no interview" is actionable in a way a star rating isn't.
"""
from collections import Counter

from engine import tracker

APPLIED_LIKE = {"Applied", "Interview", "Offer", "Rejected"}
REPEAT_NO_RESPONSE_THRESHOLD = 3


def _matches(company_name, entry):
    return (entry.get("company") or "").strip().lower() == (company_name or "").strip().lower()


def company_history(company, path=tracker.STORE):
    """Every pipeline entry recorded for this company, oldest first."""
    entries = tracker.load(path)
    return [e for e in entries if _matches(company, e)]


def company_profile(company, path=tracker.STORE):
    """Summary of everything this app's own record knows about a company.
    known=False (not "0 applications") when the company has never appeared
    at all -- an unknown company is a different fact from a known one with
    no history."""
    history = company_history(company, path)
    if not history:
        return {"company": company, "known": False, "postings_seen": 0,
                "applications_sent": 0, "outcomes": {}, "roles_seen": [], "flags": []}

    applied = [e for e in history if e.get("status") in APPLIED_LIKE]
    outcomes = dict(Counter(e.get("status") for e in applied))
    roles_seen = sorted({e.get("title") for e in history if e.get("title")})
    interviewed = any(e.get("status") in ("Interview", "Offer") for e in history)

    flags = []
    if interviewed:
        flags.append("you've reached interview stage here before")
    if len(applied) >= REPEAT_NO_RESPONSE_THRESHOLD and not interviewed:
        flags.append(f"applied {len(applied)}x here with no interview yet -- "
                     "worth asking whether this company converts for you at all")
    if any(e.get("status") == "Rejected" for e in history) and not interviewed:
        flags.append("a previous application here was rejected without an interview")

    return {
        "company": company,
        "known": True,
        "postings_seen": len(history),
        "applications_sent": len(applied),
        "outcomes": outcomes,
        "roles_seen": roles_seen,
        "flags": flags,
    }
