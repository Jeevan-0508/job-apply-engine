"""
Bundesagentur fuer Arbeit (Germany's official public job search API).
No API key registration needed -- this is the well-known public client_id
published by the agency's own community docs (bundesAPI/jobsuche-api).
Docs: https://jobsuche.api.bund.dev/

Two things about this API that are easy to get wrong, both verified against
the live service:
  * `wo` only understands German place names. "Bavaria" returns an empty list
    with HTTP 200, which is indistinguishable from "no such jobs".
  * `wo=""` is a 400, not a nationwide search. Nationwide means omitting
    `wo` and `umkreis` from the query entirely.
"""
import urllib.parse
import requests

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "Mozilla/5.0",
}

# English place names the API rejects, mapped to the German ones it accepts.
DE_NAMES = {
    "bavaria": "Bayern",
    "munich": "München",
    "cologne": "Köln",
    "nuremberg": "Nürnberg",
    "nuernberg": "Nürnberg",
    "hesse": "Hessen",
    "saxony": "Sachsen",
    "lower saxony": "Niedersachsen",
    "saxony-anhalt": "Sachsen-Anhalt",
    "north rhine-westphalia": "Nordrhein-Westfalen",
    "rhineland-palatinate": "Rheinland-Pfalz",
    "thuringia": "Thüringen",
    "westphalia": "Nordrhein-Westfalen",
    "brunswick": "Braunschweig",
    "hanover": "Hannover",
    "frankfurt am main": "Frankfurt am Main",
}

# Values that mean "anywhere in Germany" rather than a place.
NATIONWIDE = {"", "germany", "deutschland", "de", "all", "anywhere", "nationwide", "remote"}


def normalize_location(location):
    """Return (api_value, note). api_value of None means search nationwide."""
    raw = (location or "").strip()
    key = raw.lower()
    if key in NATIONWIDE:
        return None, None
    if key in DE_NAMES:
        return DE_NAMES[key], f'Searched "{DE_NAMES[key]}" -- the German jobs API only accepts German place names.'
    return raw, None


def search(query, location="", limit=25, radius_km=50):
    api_loc, note = normalize_location(location)

    params = {
        "was": query,
        "size": limit,
        "page": 1,
        "angebotsart": "1",  # 1 = regular employment
        "pav": "false",
    }
    # Sending wo="" is a 400. Omit both keys for a nationwide search.
    if api_loc:
        params["wo"] = api_loc
        params["umkreis"] = radius_km

    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"jobs": [], "error": f"Arbeitsagentur: {e}", "note": note, "total": 0}

    jobs = []
    for item in data.get("ergebnisliste", []):
        loc = ""
        lokationen = item.get("stellenlokationen") or []
        if lokationen:
            adresse = lokationen[0].get("adresse", {})
            loc = ", ".join(filter(None, [adresse.get("ort"), adresse.get("region")]))

        refnr = item.get("referenznummer", "")
        jobs.append({
            "source": "Arbeitsagentur",
            "title": item.get("stellenangebotsTitel") or item.get("hauptberuf") or "",
            "company": item.get("firma", ""),
            "location": loc,
            "link": f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{urllib.parse.quote(refnr)}" if refnr else "",
            "snippet": item.get("hauptberuf", ""),
            "posted": (item.get("veroeffentlichungszeitraum") or {}).get("von", ""),
            "refnr": refnr,
        })

    if not jobs and api_loc and not note:
        note = (f'Arbeitsagentur returned nothing for "{api_loc}". It only accepts German '
                f'place names -- try the German spelling, or clear the field to search all of Germany.')

    return {"jobs": jobs, "error": None, "note": note, "total": data.get("maxErgebnisse") or len(jobs)}


def get_job_description(refnr):
    """Fetch full job description text via job details endpoint."""
    import base64
    encoded = base64.b64encode(refnr.encode()).decode()
    url = f"https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobdetails/{encoded}"
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("stellenbeschreibung") or data.get("stellenangebotsBeschreibung") or ""
    except Exception:
        return ""
