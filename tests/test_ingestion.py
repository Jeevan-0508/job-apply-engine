"""
Tests for Job Ingestion 2.0: the status enum, source connectors' status
reporting, and (once added) Greenhouse/Lever, role aliasing and dedup.
"""
import requests

from engine.search import status as status_mod
from engine.search import arbeitsagentur, linkedin_search


class FakeResponse:
    def __init__(self, json_data=None, status_code=200, text=""):
        self._json = json_data or {}
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code} error")

    def json(self):
        return self._json


def test_status_constants_are_distinct():
    assert len(status_mod.ALL) == 7
    assert status_mod.EMPTY not in status_mod.PROBLEM_STATUSES
    assert status_mod.BLOCKED in status_mod.PROBLEM_STATUSES
    assert status_mod.ERROR in status_mod.PROBLEM_STATUSES
    assert status_mod.RATE_LIMITED in status_mod.PROBLEM_STATUSES


def test_classify_http_error_maps_429_to_rate_limited():
    assert status_mod.classify_http_error(Exception("429 Client Error")) == status_mod.RATE_LIMITED


def test_classify_http_error_maps_403_to_blocked():
    assert status_mod.classify_http_error(Exception("403 Forbidden")) == status_mod.BLOCKED


def test_classify_http_error_maps_other_to_error():
    assert status_mod.classify_http_error(Exception("Connection timed out")) == status_mod.ERROR


def test_arbeitsagentur_success_status(monkeypatch):
    data = {
        "ergebnisliste": [{
            "stellenangebotsTitel": "Risk Manager",
            "firma": "Acme GmbH",
            "referenznummer": "abc123",
            "stellenlokationen": [{"adresse": {"ort": "München", "region": "Bayern"}}],
        }],
        "maxErgebnisse": 1,
    }
    monkeypatch.setattr(arbeitsagentur.requests, "get", lambda *a, **k: FakeResponse(data))
    result = arbeitsagentur.search("Risk Manager", "Munich")
    assert result["status"] == status_mod.SUCCESS
    assert len(result["jobs"]) == 1


def test_arbeitsagentur_empty_is_not_a_problem_status(monkeypatch):
    monkeypatch.setattr(arbeitsagentur.requests, "get", lambda *a, **k: FakeResponse({"ergebnisliste": []}))
    result = arbeitsagentur.search("Risk Manager", "Munich")
    assert result["status"] == status_mod.EMPTY
    assert result["status"] not in status_mod.PROBLEM_STATUSES


def test_arbeitsagentur_network_error_is_a_problem_status(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("connection refused")
    monkeypatch.setattr(arbeitsagentur.requests, "get", boom)
    result = arbeitsagentur.search("Risk Manager", "Munich")
    assert result["status"] in status_mod.PROBLEM_STATUSES
    assert result["jobs"] == []


def test_linkedin_success_status(monkeypatch):
    card_html = (
        '<li><h3 class="base-search-card__title">Risk Manager</h3>'
        '<h4 class="base-search-card__subtitle">Acme</h4>'
        '<span class="job-search-card__location">Berlin</span>'
        '<a class="base-card__full-link" href="https://linkedin.com/jobs/view/1">x</a></li>'
    )
    monkeypatch.setattr(linkedin_search.requests, "get", lambda *a, **k: FakeResponse(text=card_html))
    result = linkedin_search.search("Risk Manager", "Berlin", limit=5)
    assert result["status"] == status_mod.SUCCESS
    assert len(result["jobs"]) == 1


def test_linkedin_empty_status(monkeypatch):
    monkeypatch.setattr(linkedin_search.requests, "get", lambda *a, **k: FakeResponse(text="<html></html>"))
    result = linkedin_search.search("Risk Manager", "Berlin", limit=5)
    assert result["status"] == status_mod.EMPTY


def test_linkedin_rate_limited_with_no_jobs_yet(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.HTTPError("429 Too Many Requests")
    monkeypatch.setattr(linkedin_search.requests, "get", boom)
    monkeypatch.setattr(linkedin_search.time, "sleep", lambda *a, **k: None)
    result = linkedin_search.search("Risk Manager", "Berlin", limit=5)
    assert result["status"] == status_mod.RATE_LIMITED
    assert result["jobs"] == []


from engine.search import greenhouse, lever


def test_greenhouse_filters_by_query_and_location(monkeypatch):
    data = {
        "jobs": [
            {"title": "Risk Manager", "location": {"name": "Berlin, Germany"},
             "absolute_url": "https://job.co/1", "updated_at": "2026-09-01"},
            {"title": "Software Engineer", "location": {"name": "Berlin, Germany"},
             "absolute_url": "https://job.co/2", "updated_at": "2026-09-01"},
        ]
    }
    monkeypatch.setattr(greenhouse.requests, "get", lambda *a, **k: FakeResponse(data))
    result = greenhouse.search("Risk Manager", "Berlin", slugs=["acme"])
    assert result["status"] == status_mod.SUCCESS
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["title"] == "Risk Manager"
    assert result["jobs"][0]["source"] == "Greenhouse"


def test_greenhouse_no_slugs_configured_is_unsupported():
    result = greenhouse.search("Risk Manager", "Berlin", slugs=[])
    assert result["status"] == status_mod.UNSUPPORTED
    assert result["jobs"] == []


def test_greenhouse_all_boards_unreachable_is_a_problem_status(monkeypatch):
    def boom(*a, **k):
        raise requests.exceptions.ConnectionError("nope")
    monkeypatch.setattr(greenhouse.requests, "get", boom)
    result = greenhouse.search("Risk Manager", "Berlin", slugs=["acme"])
    assert result["status"] in status_mod.PROBLEM_STATUSES
    assert result["error"] is not None


def test_greenhouse_empty_when_no_matches(monkeypatch):
    monkeypatch.setattr(greenhouse.requests, "get", lambda *a, **k: FakeResponse({"jobs": []}))
    result = greenhouse.search("Risk Manager", "Berlin", slugs=["acme"])
    assert result["status"] == status_mod.EMPTY


def test_lever_filters_by_query_and_location(monkeypatch):
    data = [
        {"text": "Fraud Investigator", "categories": {"location": "Munich, Germany"},
         "hostedUrl": "https://job.co/a", "createdAt": 1},
        {"text": "Sales Rep", "categories": {"location": "Munich, Germany"},
         "hostedUrl": "https://job.co/b", "createdAt": 1},
    ]
    monkeypatch.setattr(lever.requests, "get", lambda *a, **k: FakeResponse(data))
    result = lever.search("Fraud", "Munich", slugs=["acme"])
    assert result["status"] == status_mod.SUCCESS
    assert len(result["jobs"]) == 1
    assert result["jobs"][0]["source"] == "Lever"


def test_lever_no_slugs_configured_is_unsupported():
    result = lever.search("Risk", "Berlin", slugs=[])
    assert result["status"] == status_mod.UNSUPPORTED


def test_config_companies_slugs_are_nonempty_lists():
    from config.companies import GREENHOUSE_SLUGS, LEVER_SLUGS
    assert isinstance(GREENHOUSE_SLUGS, list) and len(GREENHOUSE_SLUGS) > 0
    assert isinstance(LEVER_SLUGS, list) and len(LEVER_SLUGS) > 0


from engine import dedupe
from engine.search import aggregator, role_aliases


def _fake_source(jobs_by_query, result_status=status_mod.SUCCESS):
    def fn(query, location, limit):
        jobs = jobs_by_query.get(query, [])
        return {"jobs": jobs, "error": None, "note": None, "total": len(jobs), "status": result_status if jobs else status_mod.EMPTY}
    return fn


def test_dedupe_merges_on_shared_link_only():
    jobs = [
        {"source": "Arbeitsagentur", "title": "Risk Manager", "company": "Acme",
         "location": "Berlin", "link": "https://x.co/1"},
        {"source": "LinkedIn", "title": "Senior Risk Manager (2026)", "company": "ACME GmbH",
         "location": "Berlin, DE", "link": "https://x.co/1?ref=abc"},
    ]
    merged = dedupe.merge(jobs)
    assert len(merged) == 1
    assert set(merged[0]["matched_sources"]) == {"Arbeitsagentur", "LinkedIn"}


def test_dedupe_merges_on_exact_normalized_company_title_location_without_link():
    jobs = [
        {"source": "Greenhouse", "title": "Risk Manager", "company": "Acme", "location": "Berlin"},
        {"source": "Lever", "title": "risk manager", "company": "ACME", "location": "berlin"},
    ]
    merged = dedupe.merge(jobs)
    assert len(merged) == 1


def test_dedupe_never_merges_on_title_similarity_alone():
    jobs = [
        {"source": "Greenhouse", "title": "Risk Manager", "company": "Acme", "location": "Berlin"},
        {"source": "Lever", "title": "Risk Management Lead", "company": "Acme", "location": "Berlin"},
    ]
    merged = dedupe.merge(jobs)
    assert len(merged) == 2


def test_dedupe_different_companies_same_title_stay_separate():
    jobs = [
        {"source": "Greenhouse", "title": "Risk Manager", "company": "Acme", "location": "Berlin"},
        {"source": "Lever", "title": "Risk Manager", "company": "Globex", "location": "Berlin"},
    ]
    merged = dedupe.merge(jobs)
    assert len(merged) == 2


def test_role_alias_expand_returns_configured_aliases():
    aliases = role_aliases.expand("Risk Manager")
    assert "Enterprise Risk Manager" in aliases


def test_role_alias_expand_unknown_role_returns_empty():
    assert role_aliases.expand("Underwater Basket Weaver") == []


def test_role_alias_relevance_keeps_overlapping_titles():
    assert role_aliases.is_relevant("Risk Manager", "Enterprise Risk Lead") is True


def test_role_alias_relevance_rejects_unrelated_titles():
    assert role_aliases.is_relevant("Risk Manager", "Compliance Officer") is False


def test_aggregator_expands_roles_and_filters_by_relevance(monkeypatch):
    monkeypatch.setattr(aggregator, "SOURCES", {
        "Arbeitsagentur": _fake_source({
            "Risk Manager": [{"source": "Arbeitsagentur", "title": "Risk Manager", "company": "Acme", "location": "Berlin"}],
            "Enterprise Risk Manager": [{"source": "Arbeitsagentur", "title": "Enterprise Risk Manager", "company": "Beta", "location": "Berlin"}],
            "Operational Risk Manager": [{"source": "Arbeitsagentur", "title": "Software Engineer", "company": "Gamma", "location": "Berlin"}],
            "Risk & Compliance Manager": [],
        }),
    })
    result = aggregator.search_all("Risk Manager", "Berlin", enabled_sources=["Arbeitsagentur"])
    titles = [j["title"] for j in result["jobs"]]
    assert "Risk Manager" in titles
    assert "Enterprise Risk Manager" in titles
    assert "Software Engineer" not in titles  # alias hit, but irrelevant to the original query


def test_aggregator_deduplicates_across_sources(monkeypatch):
    shared = {"source": "Arbeitsagentur", "title": "Risk Manager", "company": "Acme",
              "location": "Berlin", "link": "https://x.co/1"}
    shared_other_source = dict(shared, source="LinkedIn")
    monkeypatch.setattr(aggregator, "SOURCES", {
        "Arbeitsagentur": lambda q, l, n: {"jobs": [shared], "error": None, "note": None, "total": 1, "status": status_mod.SUCCESS},
        "LinkedIn": lambda q, l, n: {"jobs": [shared_other_source], "error": None, "note": None, "total": 1, "status": status_mod.SUCCESS},
    })
    result = aggregator.search_all("Risk Manager", "Berlin",
                                    enabled_sources=["Arbeitsagentur", "LinkedIn"], expand_roles=False)
    assert len(result["jobs"]) == 1
    assert set(result["jobs"][0]["matched_sources"]) == {"Arbeitsagentur", "LinkedIn"}


def test_aggregator_reports_problem_status_distinct_from_empty(monkeypatch):
    monkeypatch.setattr(aggregator, "SOURCES", {
        "Arbeitsagentur": lambda q, l, n: {"jobs": [], "error": "boom", "note": None, "total": 0, "status": status_mod.BLOCKED},
        "LinkedIn": lambda q, l, n: {"jobs": [], "error": None, "note": None, "total": 0, "status": status_mod.EMPTY},
    })
    result = aggregator.search_all("Risk Manager", "Berlin",
                                    enabled_sources=["Arbeitsagentur", "LinkedIn"], expand_roles=False)
    assert result["source_status"]["Arbeitsagentur"] == status_mod.BLOCKED
    assert result["source_status"]["LinkedIn"] == status_mod.EMPTY
