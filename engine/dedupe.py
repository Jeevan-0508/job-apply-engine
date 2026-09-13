"""
Deterministic cross-source deduplication.

Non-negotiable, stated in the spec and worth repeating in code: two
postings are never merged because their titles look similar. They are
merged only when they are the same posting by a hard identifier --
a shared link, or an exact match on normalized company + title +
location. Title-similarity scoring (fuzzy matching) is deliberately not
used anywhere in this module.

Each canonical job in the output carries a "matched_sources" list (which
connectors found it) and a "sources" alias for readability.
"""
import re

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")


def _normalize(text):
    text = (text or "").strip().lower()
    text = _PUNCT.sub("", text)
    text = _WS.sub(" ", text).strip()
    return text


def _normalize_link(link):
    """Normalize a link for identity comparison. Deliberately keeps the
    query string: some sources (e.g. Greenhouse's embedded-widget URLs)
    put the actual job id in a query param like ?gh_jid=..., so stripping
    it would make two different postings collide on the same bare path --
    exactly the false-merge this module exists to prevent. Only the
    fragment and a trailing slash, which are genuinely never
    identifying, are removed."""
    link = (link or "").strip().lower()
    link = link.split("#")[0]
    if link.endswith("/"):
        link = link[:-1]
    return link


def dedupe_key(job):
    """Hard identifier for a posting: normalized link if present, else
    normalized company|title|location. No fuzzy component, ever."""
    link = _normalize_link(job.get("link"))
    if link:
        return f"link:{link}"
    return "ctl:{}|{}|{}".format(
        _normalize(job.get("company")),
        _normalize(job.get("title")),
        _normalize(job.get("location")),
    )


def merge(jobs):
    """Merge a flat list of jobs (each with a 'source' field) into a
    deduplicated list. Jobs merge only on an exact dedupe_key match."""
    merged = {}
    order = []
    for job in jobs:
        key = dedupe_key(job)
        if key not in merged:
            canonical = dict(job)
            canonical["matched_sources"] = [job.get("source")] if job.get("source") else []
            merged[key] = canonical
            order.append(key)
        else:
            canonical = merged[key]
            src = job.get("source")
            if src and src not in canonical["matched_sources"]:
                canonical["matched_sources"].append(src)
            # Prefer a real link over a missing one, and fill any blank
            # field from a later duplicate -- never overwrite a value
            # that's already there.
            if not canonical.get("link") and job.get("link"):
                canonical["link"] = job["link"]
            for field in ("snippet", "posted"):
                if not canonical.get(field) and job.get(field):
                    canonical[field] = job[field]

    return [merged[k] for k in order]
