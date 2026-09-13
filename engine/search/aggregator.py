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

    queries = [query]
    if expand_roles:
        queries += role_aliases.expand(query)

    for name in enabled_sources:
        fn = SOURCES.get(name)
        if not fn:
            continue

        source_jobs = []
        statuses_for_source = []
        for i, q in enumerate(queries):
            jobs, error, note, s = _run_source(name, fn, q, location, limit_per_source)
            statuses_for_source.append(s)
            if i > 0:
                # alias-expanded query: keep only results still relevant to the original ask
                jobs = [j for j in jobs if role_aliases.is_relevant(query, j.get("title"))]
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
        elif any(s == status.SUCCESS for s in statuses_for_source):
            source_status[name] = status.SUCCESS
        else:
            source_status[name] = primary_status

        if not source_jobs and primary_status not in status.PROBLEM_STATUSES and not any(
            n for n in notes if n and name in n
        ):
            notes.append(f"{name} returned no matches for this query.")

    deduped = dedupe_merge(all_jobs)

    return {
        "jobs": deduped,
        "errors": errors,
        "notes": notes,
        "per_source": per_source,
        "source_status": source_status,
    }
