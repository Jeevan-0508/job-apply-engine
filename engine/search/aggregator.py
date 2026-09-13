"""
Runs the readable job sources for one query and merges results into one
normalized, deduplicated list: source, title, company, location, link,
snippet, posted, matched_sources.

Each source fails independently -- one source breaking never blocks the
rest, and a source that returns nothing says so via a status (see
engine/search/status.py) rather than being silently indistinguishable
from a broken connector.

Role-alias expansion (engine/search/role_aliases.py) additionally runs
each configured alias of the query through the same sources, filters
alias-only hits by relevance, and folds them into the same merge --
still subject to the same deterministic dedupe (engine/dedupe.py), never
a title-similarity merge.

Full observability per source (requests made, jobs fetched before
filtering, jobs rejected by the relevance filter, and duplicates removed
during the cross-source merge) is returned in "observability", so a
search can be audited afterwards rather than just trusted.

Indeed, StepStone and Xing are not here: they cannot be read without a real
browser session. See engine/search/deeplinks.py.
"""
from engine.dedupe import merge as dedupe_merge
from engine.search import arbeitsagentur, greenhouse, lever, linkedin_search, role_aliases, status

SOURCES = {
    "Arbeitsagentur": arbeitsagentur.search,
    "LinkedIn": linkedin_search.search,
    "Greenhouse": greenhouse.search,
    "Lever": lever.search,
}


def _run_source(name, fn, query, location, limit_per_source):
    """Run one source for one query string. Returns (jobs, problem_or_none, note_or_none, source_status)."""
    try:
        result = fn(query, location, limit_per_source)
    except Exception as e:
        return [], f"{name}: {type(e).__name__}: {e}", None, status.ERROR

    jobs = result.get("jobs", [])
    result_status = result.get("status")
    if result_status not in status.ALL:
        # Older/unknown connector shape -- infer rather than lose the signal.
        result_status = status.SUCCESS if jobs else status.EMPTY

    return jobs, result.get("error"), result.get("note"), result_status


def search_all(query, location="Germany", enabled_sources=None, limit_per_source=25, expand_roles=True):
    enabled_sources = enabled_sources or list(SOURCES.keys())
    all_jobs = []
    errors = []
    notes = []
    per_source = {}
    source_status = {}
    observability = {}

    queries = [query]
    if expand_roles:
        queries += role_aliases.expand(query)

    for name in enabled_sources:
        fn = SOURCES.get(name)
        if not fn:
            continue

        source_jobs = []
        statuses_for_source = []
        fetched = 0
        rejected = 0

        for i, q in enumerate(queries):
            jobs, error, note, s = _run_source(name, fn, q, location, limit_per_source)
            statuses_for_source.append(s)
            fetched += len(jobs)
            if i > 0:
                # alias-expanded query: keep only results still relevant to the original ask
                before = len(jobs)
                jobs = [j for j in jobs if role_aliases.is_relevant(query, j.get("title"))]
                rejected += before - len(jobs)
            source_jobs.extend(jobs)
            if error:
                errors.append(error)
            if note:
                notes.append(note)

        all_jobs.extend(source_jobs)
        per_source[name] = len(source_jobs)

        # Roll up this source's per-query statuses: a real problem on the
        # primary query always wins; otherwise SUCCESS beats EMPTY.
        primary_status = statuses_for_source[0]
        if primary_status in status.PROBLEM_STATUSES:
            source_status[name] = primary_status
        elif any(st == status.SUCCESS for st in statuses_for_source):
            source_status[name] = status.SUCCESS
        else:
            source_status[name] = primary_status

        if not source_jobs and primary_status not in status.PROBLEM_STATUSES and not any(
            n for n in notes if n and name in n
        ):
            notes.append(f"{name} returned no matches for this query.")

        observability[name] = {
            "status": source_status[name],
            "requests": len(queries),
            "fetched": fetched,
            "rejected": rejected,
            "kept_before_dedupe": len(source_jobs),
        }

    deduped = dedupe_merge(all_jobs)
    duplicates_removed = len(all_jobs) - len(deduped)
    for name in observability:
        observability[name]["final_canonical_contribution"] = sum(
            1 for j in deduped if name in (j.get("matched_sources") or [])
        )

    return {
        "jobs": deduped,
        "errors": errors,
        "notes": notes,
        "per_source": per_source,
        "source_status": source_status,
        "observability": observability,
        "duplicates_removed": duplicates_removed,
        "final_canonical": len(deduped),
    }
