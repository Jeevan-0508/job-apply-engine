"""
LinkedIn public "jobs-guest" search -- no login required.
Personal-use only, keep volume low (LinkedIn ToS does not permit automated
scraping at scale). Same pattern used by community job-search tooling.
"""
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
HEADERS = {"User-Agent": "Mozilla/5.0"}


def search(query, location="Germany", limit=25):
    params = {"keywords": query, "location": location, "start": 0}
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"jobs": [], "error": f"LinkedIn: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("li")
    jobs = []

    for card in cards[:limit]:
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
