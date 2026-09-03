"""
StepStone.de scraper -- no public API, so this is best-effort HTML scraping.
StepStone actively changes markup and fronts pages with anti-bot checks, so
treat this source as the least durable of the four. If it silently returns
zero results, StepStone's markup has likely shifted -- check the selectors
below against a fresh page view before assuming your query is bad.
"""
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def search(query, location="Germany", limit=25):
    url = (
        f"https://www.stepstone.de/jobs/{query.replace(' ', '-')}/in-{location.replace(' ', '-')}"
    )
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        return {"jobs": [], "error": f"StepStone: {e}"}

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select("article[data-testid='job-item']") or soup.select("article")
    jobs = []

    for card in cards[:limit]:
        title_el = card.select_one("[data-at='job-item-title']") or card.select_one("h2")
        company_el = card.select_one("[data-at='job-item-company-name']")
        location_el = card.select_one("[data-at='job-item-location']")
        link_el = card.select_one("a")

        if not (title_el and link_el):
            continue

        href = link_el.get("href", "")
        if href and not href.startswith("http"):
            href = "https://www.stepstone.de" + href

        jobs.append({
            "source": "StepStone",
            "title": title_el.get_text(strip=True),
            "company": company_el.get_text(strip=True) if company_el else "",
            "location": location_el.get_text(strip=True) if location_el else "",
            "link": href,
            "snippet": "",
            "posted": "",
        })

    return {"jobs": jobs, "error": None if jobs else "StepStone: 0 results -- markup may have changed"}
