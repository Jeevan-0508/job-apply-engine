"""
Bundesagentur fuer Arbeit (Germany's official public job search API).
No API key registration needed -- this is the well-known public client_id
published by the agency's own community docs (bundesAPI/jobsuche-api).
Docs: https://jobsuche.api.bund.dev/
"""
import urllib.parse
import requests

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "Mozilla/5.0",
}


def search(query, location="", radius_km=50, size=25):
    """Search German jobs. `location` can be a city, state (e.g. 'Bayern'/'Bavaria') or blank for nationwide."""
    params = {
        "was": query,
        "wo": location,
        "umkreis": radius_km,
        "size": size,
        "page": 1,
        "angebotsart": "1",  # 1 = regular employment
        "pav": "false",
    }
    try:
        resp = requests.get(BASE_URL, headers=HEADERS, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        return {"jobs": [], "error": f"Arbeitsagentur: {e}"}

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

    return {"jobs": jobs, "error": None}


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
