"""
Role-alias expansion for search queries.

A search for "Risk Manager" misses postings titled "Risk & Compliance
Manager" or "Enterprise Risk Lead" purely because the words don't match.
This module expands one query into a small set of alias queries so a
search can run all of them and merge results -- but keeps the set
deliberately short and scored, so a query for "Risk Manager" doesn't
quietly balloon into "Manager" and pull in every unrelated role.

Non-negotiable: this only ever adds candidate query strings for the
caller to search separately. It never rewrites or merges postings by
title-similarity -- that boundary belongs to engine/dedupe.py, which
requires an exact normalized match or a shared link, never a fuzzy score.
"""

# canonical role (lowercase) -> alias query strings to search alongside it.
ROLE_ALIASES = {
    "risk manager": [
        "Risk Management",
        "Enterprise Risk Manager",
        "Operational Risk Manager",
        "Risk & Compliance Manager",
    ],
    "risk analyst": [
        "Risk Management Analyst",
        "Operational Risk Analyst",
    ],
    "fraud investigator": [
        "Fraud Analyst",
        "Fraud Prevention Specialist",
        "Investigations Specialist",
    ],
    "fraud analyst": [
        "Fraud Investigator",
        "Fraud Prevention Analyst",
    ],
    "compliance manager": [
        "Compliance Officer",
        "Risk & Compliance Manager",
        "Regulatory Compliance Manager",
    ],
    "loss prevention manager": [
        "Loss Prevention Specialist",
        "Asset Protection Manager",
    ],
    "supply chain security manager": [
        "Supply Chain Risk Manager",
        "Logistics Security Manager",
    ],
}

# Minimum fraction of the canonical query's significant words that must
# appear (as whole words, case-insensitive) in a candidate job title for
# an alias-expanded search to be considered relevant enough to keep -- this
# is the relevance threshold that stops expansion from over-broadening.
RELEVANCE_THRESHOLD = 0.34

_STOPWORDS = {"the", "a", "an", "of", "and", "&", "for", "to", "in"}


def _significant_words(text):
    return [w for w in text.lower().replace("&", " ").split() if w and w not in _STOPWORDS]


def expand(query):
    """Return the list of alias query strings for a canonical role query (not including the original)."""
    key = (query or "").strip().lower()
    return list(ROLE_ALIASES.get(key, []))


def is_relevant(original_query, job_title):
    """Whether a job title found via an alias-expanded query is still relevant
    enough to the original query to keep, per RELEVANCE_THRESHOLD."""
    orig_words = set(_significant_words(original_query))
    if not orig_words:
        return True
    title_words = set(_significant_words(job_title or ""))
    overlap = orig_words & title_words
    return (len(overlap) / len(orig_words)) >= RELEVANCE_THRESHOLD
