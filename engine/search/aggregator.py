"""
Runs all four job sources for one query and merges results into one
normalized list: source, title, company, location, link, snippet, posted.
Each source fails independently -- one source breaking never blocks the rest.
"""
from engine.search import arbeitsagentur, linkedin_search, indeed_scraper, stepstone_scraper

SOURCES = {
    "Arbeitsagentur": arbeitsagentur.search,
    "LinkedIn": linkedin_search.search,
    "Indeed": indeed_scraper.search,
    "StepStone": stepstone_scraper.search,
}


def search_all(query, location="Germany", enabled_sources=None, limit_per_source=20):
    enabled_sources = enabled_sources or list(SOURCES.keys())
    all_jobs = []
    errors = []

    for name in enabled_sources:
        fn = SOURCES.get(name)
        if not fn:
            continue
        try:
            result = fn(query, location, limit_per_source) if name != "Arbeitsagentur" else fn(query, location, size=limit_per_source)
        except TypeError:
            # arbeitsagentur.search has a slightly different signature (location, radius_km, size)
            result = fn(query, location)
        except Exception as e:
            errors.append(f"{name}: {e}")
            continue

        all_jobs.extend(result.get("jobs", []))
        if result.get("error"):
            errors.append(result["error"])

    return {"jobs": all_jobs, "errors": errors}
