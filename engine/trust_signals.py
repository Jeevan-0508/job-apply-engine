"""
Job Trust Signals: an explicit, explainable checklist of reasons to
double-check a posting before investing time in it, as distinct from
engine.job_quality's single blended score. A checklist survives being
skimmed in a way a number doesn't -- "no direct link, company name
withheld" tells you exactly what to verify; "quality 41/100" does not.

Every signal here traces to a concrete, already-known fact about the
posting (its own fields, its freshness status, its corroboration count,
its description status) -- nothing is inferred from outside data.
"""
WARNING, INFO = "WARNING", "INFO"

_GENERIC_COMPANY_NAMES = {
    "confidential", "n/a", "na", "stealth", "stealth startup",
    "company name withheld", "undisclosed", "private",
}


def trust_signals(job, freshness_status=None, description_status=None):
    """{flags: [{level, text}], level: WARNING|INFO|OK}. `level` is the
    worst flag present, so a caller can gate on it without re-scanning
    the list."""
    flags = []

    company = (job.get("company") or "").strip()
    if not company or company.lower() in _GENERIC_COMPANY_NAMES:
        flags.append({"level": WARNING, "text": "company name is missing or generic -- verify the real employer before applying"})

    if not (job.get("link") or "").strip():
        flags.append({"level": WARNING, "text": "no direct application link"})

    if not (job.get("location") or "").strip():
        flags.append({"level": INFO, "text": "location not specified"})

    sources = job.get("matched_sources") or ([job.get("source")] if job.get("source") else [])
    sources = [s for s in sources if s]
    if len(sources) <= 1:
        flags.append({"level": INFO, "text": "seen on only one source, not corroborated elsewhere"})

    if freshness_status == "CLOSED":
        flags.append({"level": WARNING, "text": "confirmed closed"})
    elif freshness_status == "CLOSED_CANDIDATE":
        flags.append({"level": WARNING, "text": "flagged as a possible closed posting -- check the link before applying"})
    elif freshness_status == "STALE":
        flags.append({"level": WARNING, "text": "posting looks stale (30+ days old) -- confirm it's still open"})

    if description_status == "UNAVAILABLE":
        flags.append({"level": INFO, "text": "no description could be read at all -- everything about fit here is a guess"})

    if any(f["level"] == WARNING for f in flags):
        level = WARNING
    elif flags:
        level = INFO
    else:
        level = "OK"

    return {"flags": flags, "level": level}
