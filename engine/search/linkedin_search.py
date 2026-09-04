"""
LinkedIn public "jobs-guest" search -- no login required.
Personal-use only, keep volume low (LinkedIn ToS does not permit automated
scraping at scale). Same pattern used by community job-search tooling.
"""
import time

import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def search(query, location="Germany", limit=25):
    """This endpoint returns 10 cards per call, so `limit` needs paging to mean anything."""
    jobs = []
    seen = set()
    start = 0
    while len(jobs) < limit and start < 100:
        if start:
            time.sleep(1.2)  # this endpoint 429s quickly when paged back to back
        page = _fetch_page(query, location, start)
        if page.get("error"):
            note = None
            if "429" in page["error"]:
                # Partial results are more useful than an empty list plus a stack trace.
                note = ("LinkedIn rate-limited the request (HTTP 429). Showing what came back; "
                        "wait a minute and search again, or rely on Arbeitsagentur.")
                page = None
            if page is not None:
                return {"jobs": jobs, "error": page["error"], "note": None, "total": len(jobs)}
            return {"jobs": jobs, "error": None, "note": note, "total": len(jobs)}
        new_cards = [j for j in page["jobs"] if j["link"] not in seen]
        if not new_cards:
            break
        for j in new_cards:
            seen.add(j["link"])
        jobs.extend(new_cards)
        start += 10
    return {"jobs": jobs[:limit], "error": None, "note": None, "total": len(jobs)}


def _fetch_page(query, location, start):
    params = {"keywords": query, "location": location, "start": start}
    resp = None
    for attempt in range(2):
        try:
            resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
            resp.raise_for_status()
            break
        except Exception as e:
            if attempt == 0 and "429" in str(e):
                time.sleep(3)
                continue
            return {"jobs": [], "error": f"LinkedIn: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li")
    jobs = []

    for card in cards:
        title_el = card.select_one("h3.base-search-card__title")
        company_el = card.select_one("h4.base-search-card__subtitle")
        location_el = card.select_one("span.job-search-card__location")
        link_el = card.select_one("a.base-card__full-link")

        if not (title_el and link_el):
            continue

        jobs.append({
            "source": "LinkedIn",
            "title": title_el.get_text(strip=True),
            "company": company_el.get_text(strip=True) if company_el else "",
            "location": location_el.get_text(strip=True) if location_el else "",
            "link": link_el.get("href", "").split("?")[0],
            "snippet": "",
            "posted": "",
        })

    return {"jobs": jobs, "error": None}
