"""
Greenhouse public job board API -- no key required for boards published
with the standard embed (the same JSON the public careers page reads).

Docs: https://developers.greenhouse.io/job-board.html

One thing worth stating plainly: this only returns jobs for companies
whose Greenhouse "board token" (slug) we already know, from
config/companies.py. There is no search-by-keyword across all Greenhouse
customers -- that index does not exist publicly. So this connector filters
the known companies' postings by query/location client-side.
"""
import requests

from engine.search import status as status_mod

BASE_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def _matches(job_title, location, query, location_query):
    q = (query or "").strip().lower()
    if q and q not in job_title.lower():
        return False
    lq = (location_query or "").strip().lower()
    if lq and lq not in (location or "").lower():
        return False
    return True


def search(query, location="", limit=25, slugs=None):
    """Search across the configured Greenhouse boards for a matching title/location."""
    if slugs is None:
        from config.companies import GREENHOUSE_SLUGS as slugs

    if not slugs:
        return {"jobs": [], "error": None, "note": None, "total": 0, "status": status_mod.UNSUPPORTED}

    jobs = []
    problems = []
    for slug in slugs:
        url = BASE_URL.format(slug=slug)
        try:
            resp = requests.get(url, headers=HEADERS, params={"content": "true"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            problems.append((slug, status_mod.classify_http_error(e), str(e)))
            continue

        for item in data.get("jobs", []):
            title = item.get("title") or ""
            loc = (item.get("location") or {}).get("name", "")
            if not _matches(title, loc, query, location):
                continue
            jobs.append({
                "source": "Greenhouse",
                "title": title,
                "company": slug,
                "location": loc,
                "link": item.get("absolute_url", ""),
                "snippet": "",
                "posted": item.get("updated_at", ""),
            })
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
