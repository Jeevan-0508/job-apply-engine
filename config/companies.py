"""
Company slugs for the Greenhouse and Lever connectors.

Neither API supports keyword search across all customers -- there is no
public "search every Greenhouse board" endpoint, only "list this one
company's postings". So these connectors only ever see the companies
listed here, then filter client-side by query/location.

Add a company by finding its board token:
  * Greenhouse: open the company's careers page, view source, look for
    boards.greenhouse.io/<slug> or boards-api.greenhouse.io/v1/boards/<slug>.
  * Lever: open the company's careers page, look for jobs.lever.co/<slug>.

Defaults below are real, verified-reachable public boards (checked live
against the actual API, not guessed) so the connectors return real data
out of the box. Edit freely -- add employers relevant to your own search.
"""

GREENHOUSE_SLUGS = [
    "stripe",
    "airbnb",
    "databricks",
    "coinbase",
]

LEVER_SLUGS = [
    "spotify",
    "palantir",
]
