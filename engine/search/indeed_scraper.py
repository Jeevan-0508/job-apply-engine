"""
Indeed.de scraper -- no public API, best-effort HTML scraping.
Indeed fronts most traffic with Cloudflare bot checks; expect this to break
periodically and need selector fixes.
"""
import time
import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


def search(query, location="Germany", pages=1, limit=25):
    jobs = []
    error = None

    for page in range(pages):
        start = page * 10
        url = (
            f"https://de.indeed.com/jobs?q={query.replace(' ', '+')}"
            f"&l={location.replace(' ', '+')}&start={start}"
        )
        try:
            resp = requests.get(url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            error = f"Indeed: {e}"
            break

        soup = BeautifulSoup(resp.text, "html.parser")
        cards = soup.select("a.tapItem") or soup.select("div.job_seen_beacon")

        for card in cards:
            title = card.select_one("h2.jobTitle") or card.select_one("h2")
            company = card.select_one("span.companyName")
            location_el = card.select_one("div.companyLocation")
            href = card.get("href") if card.name == "a" else (card.select_one("a") or {}).get("href")

            if not (title and href):
                continue

            jobs.append({
                "source": "Indeed",
                "title": title.get_text(strip=True),
                "company": company.get_text(strip=True) if company else "",
                "location": location_el.get_text(strip=True) if location_el else "",
                "link": "https://de.indeed.com" + href if href.startswith("/") else href,
                "snippet": "",
                "posted": "",
            })

        if len(jobs) >= limit:
            break
        time.sleep(1.5)  # be polite

    return {"jobs": jobs[:limit], "error": error if not jobs else None}


def fetch_job_description(job_url):
    try:
        resp = requests.get(job_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")
        jd_div = soup.select_one("div#jobDescriptionText")
        return jd_div.get_text(separator=" ") if jd_div else ""
    except Exception:
        return ""
