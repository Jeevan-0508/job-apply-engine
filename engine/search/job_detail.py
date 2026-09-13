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

Every result also carries an honest description_status -- FULL/PARTIAL/
TITLE_ONLY/UNAVAILABLE -- because scoring a posting off its title alone and
scoring it off a real description answer different questions, and reporting
one as if it were the other is exactly the kind of false confidence this
project does not do. Fetches are cached (engine/cache.py, by job identity)
so re-scoring the same search results twice in one session doesn't refetch
every description again.
"""
import re

import requests
from bs4 import BeautifulSoup

from engine import cache
from engine.dedupe import normalize_link
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
CACHE_TTL = 3600  # seconds -- a session re-scoring the same jobs shouldn't refetch

FULL, PARTIAL, TITLE_ONLY, UNAVAILABLE = "FULL", "PARTIAL", "TITLE_ONLY", "UNAVAILABLE"
FULL_THRESHOLD = 600


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


def classify(text, has_link):
    """FULL/PARTIAL/TITLE_ONLY/UNAVAILABLE for one fetched description.

    FULL means a real match can be scored against it. PARTIAL is usable
    but thin. TITLE_ONLY means a link existed but nothing useful came
    back from it -- there was something to try. UNAVAILABLE means there
    was nothing to even attempt (no link at all).
    """
    length = len(text or "")
    if length >= FULL_THRESHOLD:
        return FULL
    if length >= MIN_USEFUL:
        return PARTIAL
    return TITLE_ONLY if has_link else UNAVAILABLE


def _cache_key(job):
    source = (job or {}).get("source", "")
    refnr = (job or {}).get("refnr")
    if source == "Arbeitsagentur" and refnr:
        return f"desc:arbeitsagentur:{refnr}"
    link = normalize_link((job or {}).get("link"))
    return f"desc:link:{link}" if link else None


def fetch_description(job):
    """Return description detail for one job dict from a search result.

    Never raises: a posting that cannot be read returns an empty string and
    the reason, because one unreadable posting must not abort a batch.

    Keys: text, source (which fetch path succeeded), error, status
    (FULL/PARTIAL/TITLE_ONLY/UNAVAILABLE), hash (content hash of text,
    stable across re-fetches of the unchanged description), cached (bool).
    """
    cache_key = _cache_key(job)
    if cache_key:
        cached = cache.get(cache_key, CACHE_TTL)
        if cached is not None:
            return {**cached, "cached": True}

    result = _fetch_uncached(job)
    if cache_key:
        cache.set(cache_key, result)
    return {**result, "cached": False}


def _fetch_uncached(job):
    source = (job or {}).get("source", "")
    link = (job or {}).get("link", "")
    has_link = bool(link) or bool((job or {}).get("refnr"))

    try:
        if source == "Arbeitsagentur" and job.get("refnr"):
            text = _clean(get_job_description(job["refnr"]))
            if len(text) >= MIN_USEFUL:
                return {"text": text, "source": "Arbeitsagentur detail API", "error": None,
                        "status": classify(text, has_link), "hash": cache.content_hash(text)}

        if not link:
            return {"text": "", "source": None, "error": "no link on this posting",
                    "status": classify("", has_link), "hash": cache.content_hash("")}

        if "linkedin.com" in link:
            text = _from_linkedin(link)
            if len(text) >= MIN_USEFUL:
                return {"text": text, "source": "LinkedIn guest page", "error": None,
                        "status": classify(text, has_link), "hash": cache.content_hash(text)}

        text = _from_generic(link)
        if len(text) >= MIN_USEFUL:
            return {"text": text, "source": "page text (best effort)", "error": None,
                    "status": classify(text, has_link), "hash": cache.content_hash(text)}

        return {"text": text, "source": None,
                "error": f"only {len(text)} characters readable at {link}",
                "status": classify(text, has_link), "hash": cache.content_hash(text)}
    except Exception as e:
        return {"text": "", "source": None, "error": f"{type(e).__name__}: {e}",
                "status": classify("", has_link), "hash": cache.content_hash("")}
