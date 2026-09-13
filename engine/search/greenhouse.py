"""
Greenhouse public job board API -- no key required for boards published
with the standard embed (the same JSON the public careers page reads).

Docs: https://developers.greenhouse.io/job-board.html

Two things worth stating plainly:

1. There is no search-by-keyword across all Greenhouse customers -- that
   index does not exist publicly. This only ever returns jobs for the
   companies whose board token (slug) is listed in config/companies.py,
   filtered by query/location client-side.

2. A board's full job list is fetched once and cached (engine/cache.py,
   short TTL) rather than re-fetched per query. Role-alias expansion
   means one search can generate five query variants; without the cache
   that would mean five identical network round-trips per configured
   board for a source whose data doesn't change query to query anyway.
"""
import requests

from engine import cache
from engine.search import status as status_mod

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0"}
BOARD_CACHE_TTL = 600  # seconds


def _matches(job_title, location, query, location_query):
    q = (query or "").strip().lower()
    if q and q not in job_title.lower():
        return False
    lq = (location_query or "").strip().lower()
    if lq and lq not in (location or "").lower():
        return False
    return True


def _fetch_board(slug):
    """Raw jobs for one board, from cache if fetched recently in this process."""
    cache_key = f"greenhouse:{slug}"
    cached = cache.get(cache_key, BOARD_CACHE_TTL)
    if cached is not None:
        return cached

    url = BASE_URL.format(slug=slug)
    resp = requests.get(url, headers=HEADERS, params={"content": "true"}, timeout=15)
    resp.raise_for_status()
    jobs = []
    for item in resp.json().get("jobs", []):
        jobs.append({
            "source": "Greenhouse",
            "source_id": str(item.get("id", "")),
            "title": item.get("title") or "",
            "company": slug,
            "location": (item.get("location") or {}).get("name", ""),
            "link": item.get("absolute_url", ""),
            "snippet": "",
            "posted": item.get("updated_at", ""),
        })
    cache.set(cache_key, jobs)
    return jobs


def search(query, location="", limit=25, slugs=None):
    """Search across the configured Greenhouse boards for a matching title/location."""
    if slugs is None:
        from config.companies import GREENHOUSE_SLUGS as slugs

    if not slugs:
        return {"jobs": [], "error": None, "note": None, "total": 0, "status": status_mod.UNSUPPORTED}

    jobs = []
    problems = []
    for slug in slugs:
        try:
            board_jobs = _fetch_board(slug)
        except Exception as e:
            problems.append((slug, status_mod.classify_http_error(e), str(e)))
            continue

        for item in board_jobs:
            if not _matches(item["title"], item["location"], query, location):
                continue
            jobs.append(item)
            if len(jobs) >= limit:
                break

    jobs = jobs[:limit]

    if jobs:
        result_status = status_mod.SUCCESS
    elif problems and len(problems) == len(slugs):
        # every configured board failed -- that's a real problem, not "no matches"
        result_status = problems[0][1]
    elif problems:
        result_status = status_mod.PARTIAL
    else:
        result_status = status_mod.EMPTY

    note = None
    error = None
    if problems:
        detail = "; ".join(f"{slug}: {msg}" for slug, _, msg in problems)
        if result_status in status_mod.PROBLEM_STATUSES and result_status != status_mod.PARTIAL:
            error = f"Greenhouse: {detail}"
        else:
            note = f"Greenhouse: could not reach {len(problems)} of {len(slugs)} configured boards ({detail})."

    return {"jobs": jobs, "error": error, "note": note, "total": len(jobs), "status": result_status}
