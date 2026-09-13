"""
Deterministic cross-source deduplication.

Non-negotiable, stated in the spec and worth repeating in code: two
postings are never merged because their titles look similar. They are
merged only on a hard identifier, checked in this priority order:

  1. The source's own official job id (Greenhouse/Lever assign a stable,
     globally-unique id to every posting -- more reliable than a URL,
     which can carry tracking noise or, on some boards, not vary per job
     at all in its path).
  2. A shared link, compared with its query string intact. Some ATSes
     (Greenhouse's embedded-widget links included) put the actual job id
     in a query parameter, not the path -- stripping query strings was a
     real bug here (see tests) that silently merged two different roles.
  3. An exact match on normalized company + title + location.

Title-similarity scoring (fuzzy matching) is deliberately not used
anywhere in this module -- that boundary belongs to nothing, on purpose.

Each canonical job in the output carries a "matched_sources" list (which
connectors found it) and a "sources" alias for readability.
"""
import re

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s]")

# Sources whose own id field is a stable, globally-unique identifier we can
# trust as a hard match on its own. Not every connector sets source_id, and
# a source not listed here is never trusted for this tier even if it
# happens to have a same-named field -- explicit allow-list, not a guess.
ID_TRUSTED_SOURCES = {"greenhouse", "lever"}


def normalize_text(text):
    text = (text or "").strip().lower()
    text = _PUNCT.sub("", text)
    text = _WS.sub(" ", text).strip()
    return text


def normalize_link(link):
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
    """Hard identifier for a posting, checked in priority order. No fuzzy
    component at any tier."""
    source = (job.get("source") or "").strip().lower()
    source_id = (job.get("source_id") or "").strip()
    if source_id and source in ID_TRUSTED_SOURCES:
        return f"id:{source}:{source_id}"

    link = normalize_link(job.get("link"))
    if link:
        return f"link:{link}"

    return "ctl:{}|{}|{}".format(
        normalize_text(job.get("company")),
        normalize_text(job.get("title")),
        normalize_text(job.get("location")),
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
