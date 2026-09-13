"""
Lever public postings API -- no key required.

Docs: https://github.com/lever/postings-api

Same shape as Greenhouse: no cross-company keyword search exists publicly,
so this filters the known companies' (config/companies.py) postings by
query/location client-side.
"""
import requests

from engine.search import status as status_mod
from engine.search.greenhouse import _matches

BASE_URL = "https://api.lever.co/v0/postings/{slug}"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def search(query, location="", limit=25, slugs=None):
    if slugs is None:
        from config.companies import LEVER_SLUGS as slugs

    if not slugs:
        return {"jobs": [], "error": None, "note": None, "total": 0, "status": status_mod.UNSUPPORTED}

    jobs = []
    problems = []
    for slug in slugs:
        url = BASE_URL.format(slug=slug)
        try:
            resp = requests.get(url, headers=HEADERS, params={"mode": "json"}, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            problems.append((slug, status_mod.classify_http_error(e), str(e)))
            continue

        for item in data:
            title = item.get("text") or ""
            loc = (item.get("categories") or {}).get("location", "")
            if not _matches(title, loc, query, location):
                continue
            jobs.append({
                "source": "Lever",
                "title": title,
                "company": slug,
                "location": loc,
                "link": item.get("hostedUrl", ""),
                "snippet": "",
                "posted": item.get("createdAt", ""),
            })
            if len(jobs) >= limit:
                break

    jobs = jobs[:limit]

    if jobs:
        result_status = status_mod.SUCCESS
    elif problems and len(problems) == len(slugs):
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
            error = f"Lever: {detail}"
        else:
            note = f"Lever: could not reach {len(problems)} of {len(slugs)} configured boards ({detail})."

    return {"jobs": jobs, "error": error, "note": note, "total": len(jobs), "status": result_status}
