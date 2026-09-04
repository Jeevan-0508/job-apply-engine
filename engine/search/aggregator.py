"""
Runs the readable job sources for one query and merges results into one
normalized list: source, title, company, location, link, snippet, posted.

Each source fails independently -- one source breaking never blocks the rest,
and a source that returns nothing says so rather than silently contributing
zero rows.

Indeed, StepStone and Xing are not here: they cannot be read without a real
browser session. See engine/search/deeplinks.py.
"""
from engine.search import arbeitsagentur, linkedin_search

SOURCES = {
    "Arbeitsagentur": arbeitsagentur.search,
    "LinkedIn": linkedin_search.search,
}


def search_all(query, location="Germany", enabled_sources=None, limit_per_source=25):
    enabled_sources = enabled_sources or list(SOURCES.keys())
    all_jobs = []
    errors = []
    notes = []
    per_source = {}

    for name in enabled_sources:
        fn = SOURCES.get(name)
        if not fn:
            continue
        try:
            result = fn(query, location, limit_per_source)
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")
            per_source[name] = 0
            continue

        jobs = result.get("jobs", [])
        all_jobs.extend(jobs)
        per_source[name] = len(jobs)

        if result.get("error"):
            errors.append(result["error"])
        if result.get("note"):
            notes.append(result["note"])
        if not jobs and not result.get("error") and not result.get("note"):
            notes.append(f"{name} returned no matches for this query.")

    return {"jobs": all_jobs, "errors": errors, "notes": notes, "per_source": per_source}
