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
