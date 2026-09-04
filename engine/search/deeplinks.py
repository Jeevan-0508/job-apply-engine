"""
Sites that cannot be read programmatically, exposed as one-click searches instead.

Indeed and StepStone both answer a plain HTTPS request with HTTP 403 -- verified
with a full browser header set, not just a bare User-Agent. They sit behind
bot protection that needs a real browser session, so scraping them produced a
silent zero every time and made the app look broken. Xing renders its job
search client-side, so there is nothing in the HTML to parse either.

A link the user can click is honest and always works. A scraper that returns
nothing is neither.
"""
from urllib.parse import quote_plus, urlencode


def build(query, location=""):
    q = query or ""
    loc = location or ""
    return [
        {
            "name": "Indeed",
            "url": f"https://de.indeed.com/jobs?{urlencode({'q': q, 'l': loc})}",
            "why": "blocks automated requests (403)",
        },
        {
            "name": "StepStone",
            "url": f"https://www.stepstone.de/jobs/{quote_plus(q.replace(' ', '-'))}"
                   + (f"/in-{quote_plus(loc.replace(' ', '-'))}" if loc else ""),
            "why": "blocks automated requests (403)",
        },
        {
            "name": "Xing",
            "url": "https://www.xing.com/jobs/search?" + urlencode({"keywords": q, "location": loc}),
            "why": "renders results in the browser only",
        },
        {
            "name": "LinkedIn",
            "url": "https://www.linkedin.com/jobs/search?" + urlencode({"keywords": q, "location": loc or "Germany"}),
            "why": "full results, no rate limit",
        },
    ]
