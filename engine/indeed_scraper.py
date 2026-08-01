import requests
from bs4 import BeautifulSoup
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

def search_indeed(query, location="Germany", pages=1):
    jobs = []

    for page in range(pages):
        start = page * 10
        url = (
            f"https://de.indeed.com/jobs?q={query.replace(' ', '+')}"
            f"&l={location.replace(' ', '+')}&start={start}"
        )

        resp = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")

        cards = soup.select("a.tapItem")

        for card in cards:
            title = card.select_one("h2.jobTitle")
            company = card.select_one("span.companyName")
            link = card.get("href")

            if not (title and company and link):
                continue

            jobs.append({
                "title": title.text.strip(),
                "company": company.text.strip(),
                "link": "https://de.indeed.com" + link
            })

        time.sleep(2)  # be polite

    return jobs


def fetch_job_description(job_url):
    resp = requests.get(job_url, headers=HEADERS, timeout=10)
    soup = BeautifulSoup(resp.text, "html.parser")

    jd_div = soup.select_one("div#jobDescriptionText")
    return jd_div.get_text(separator=" ") if jd_div else ""
