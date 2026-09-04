"""
Fetches the full text of a job posting so the rest of the app never needs the
description pasted in by hand.

Copy-pasting a description was the single biggest cost per application: find
the posting, open it, select the right part of the page, paste it back. Both
readable sources expose the whole thing programmatically, so they are used.

Arbeitsagentur serves it from a documented detail endpoint keyed on the
reference number. LinkedIn renders the description into its public guest page,
so it is parsed out of the HTML. Anything else falls back to generic article
extraction, which is best-effort and says so.
"""
import re

import requests
from bs4 import BeautifulSoup

from engine.search.arbeitsagentur import get_job_description

BROWSER_HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
LINKEDIN_SELECTORS = [
    "div.show-more-less-html__markup",
    "div.description__text",
    "section.description",
]
MIN_USEFUL = 200


def _clean(text):
    text = re.sub(r"[ \t\xa0]+", " ", text or "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _from_linkedin(url):
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for selector in LINKEDIN_SELECTORS:
        el = soup.select_one(selector)
        if el:
            return _clean(el.get_text("\n", strip=True))
    return ""


def _from_generic(url):
    resp = requests.get(url, headers=BROWSER_HEADERS, timeout=20)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "header", "footer", "form"]):
        tag.decompose()
    main = soup.select_one("main") or soup.select_one("article") or soup.body
    return _clean(main.get_text("\n", strip=True)) if main else ""


def fetch_description(job):
    """Return {"text", "source", "error"} for one job dict from a search result.

    Never raises: a posting that cannot be read returns an empty string and the
    reason, because one unreadable posting must not abort a batch.
    """
    source = (job or {}).get("source", "")
    link = (job or {}).get("link", "")

    try:
        if source == "Arbeitsagentur" and job.get("refnr"):
            text = _clean(get_job_description(job["refnr"]))
            if len(text) >= MIN_USEFUL:
                return {"text": text, "source": "Arbeitsagentur detail API", "error": None}

        if not link:
            return {"text": "", "source": None, "error": "no link on this posting"}

        if "linkedin.com" in link:
            text = _from_linkedin(link)
            if len(text) >= MIN_USEFUL:
                return {"text": text, "source": "LinkedIn guest page", "error": None}

        text = _from_generic(link)
        if len(text) >= MIN_USEFUL:
            return {"text": text, "source": "page text (best effort)", "error": None}

        return {"text": text, "source": None,
                "error": f"only {len(text)} characters readable at {link}"}
    except Exception as e:
        return {"text": "", "source": None, "error": f"{type(e).__name__}: {e}"}
