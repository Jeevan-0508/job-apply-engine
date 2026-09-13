"""Tests for engine.freshness -- posting age/liveness tracking."""
from datetime import datetime, timedelta

import pytest

from engine import freshness as fr


def job(link="https://example.com/jobs/1", posted=None, company="Acme", title="Risk Manager", location="Berlin"):
    j = {"link": link, "company": company, "title": title, "location": location}
    if posted is not None:
        j["posted"] = posted
    return j


def iso_days_ago(n):
    return (datetime.now() - timedelta(days=n)).isoformat(timespec="seconds")


@pytest.fixture
def store(tmp_path):
    return str(tmp_path / "sightings.json")


class TestDateParsing:
    def test_iso_date(self):
        assert fr._parse_date("2026-08-01") is not None

    def test_iso_datetime_with_z(self):
        d = fr._parse_date("2026-08-01T10:00:00Z")
        assert d is not None and d.year == 2026

    def test_epoch_seconds(self):
        d = fr._parse_date(1735689600)
        assert d is not None

    def test_epoch_ms(self):
        d = fr._parse_date(1735689600000)
        assert d is not None

    def test_epoch_ms_as_string(self):
        d = fr._parse_date("1735689600000")
        assert d is not None

    def test_dotted_date(self):
        d = fr._parse_date("01.08.2026")
        assert d is not None and d.month == 8

    def test_unparseable_returns_none(self):
        assert fr._parse_date("not a date") is None

    def test_none_returns_none(self):
        assert fr._parse_date(None) is None

    def test_empty_string_returns_none(self):
        assert fr._parse_date("") is None


class TestScoreMonotonic:
    def test_score_decreases_with_age(self):
        scores = [fr._score_for_age(d) for d in (0, 3, 14, 30, 90, 200)]
        assert scores == sorted(scores, reverse=True)

    def test_score_floor_beyond_90_days(self):
        assert fr._score_for_age(90) == fr._score_for_age(500)

    def test_score_at_zero_is_100(self):
        assert fr._score_for_age(0) == 100


class TestStatusThresholds:
    @pytest.mark.parametrize("age,expected", [
        (0, fr.FRESH), (3, fr.FRESH),
        (4, fr.AGING), (14, fr.AGING),
        (15, fr.OLD), (30, fr.OLD),
        (31, fr.STALE), (365, fr.STALE),
    ])
    def test_thresholds(self, age, expected):
        assert fr._status_for_age(age) == expected


class TestRecordSighting:
    def test_creates_entry_on_first_sighting(self, store):
        entry = fr.record_sighting(job(), path=store)
        assert entry["first_seen_at"] is not None
        assert entry["last_seen_at"] == entry["first_seen_at"]

    def test_preserves_first_seen_across_repeats(self, store):
        e1 = fr.record_sighting(job(), path=store)
        first = e1["first_seen_at"]
        e2 = fr.record_sighting(job(), path=store)
        assert e2["first_seen_at"] == first

    def test_updates_last_seen_on_resighting(self, store, monkeypatch):
        fr.record_sighting(job(), path=store)
        entries = fr.load(store)
        jid = list(entries)[0]
        entries[jid]["last_seen_at"] = "2000-01-01T00:00:00"
        fr.save(entries, store)
        e2 = fr.record_sighting(job(), path=store)
        assert e2["last_seen_at"] != "2000-01-01T00:00:00"

    def test_captures_posted_date_once(self, store):
        e1 = fr.record_sighting(job(posted="2026-08-01"), path=store)
        assert e1["posted_at"] is not None
        e2 = fr.record_sighting(job(posted="2026-09-01"), path=store)
        # posted_at set once, not overwritten by a later differing value
        assert e2["posted_at"] == e1["posted_at"]

    def test_resighting_clears_closed_candidate(self, store):
        j = job()
        fr.mark_closed_candidate(j, reason="link 404", path=store)
        entry = fr.get_entry(j, path=store)
        assert entry["status_override"] == fr.CLOSED_CANDIDATE
        fr.record_sighting(j, path=store)
        entry2 = fr.get_entry(j, path=store)
        assert entry2["status_override"] is None

    def test_different_jobs_get_different_ids(self, store):
        fr.record_sighting(job(link="https://example.com/a"), path=store)
        fr.record_sighting(job(link="https://example.com/b"), path=store)
        assert len(fr.load(store)) == 2


class TestComputeFreshness:
    def test_no_entry_is_unknown(self):
        result = fr.compute_freshness(None)
        assert result["status"] == fr.UNKNOWN
        assert result["score"] is None

    def test_unparseable_dates_are_unknown(self):
        entry = {"posted_at": "garbage", "first_seen_at": "garbage", "status_override": None}
        result = fr.compute_freshness(entry)
        assert result["status"] == fr.UNKNOWN
        assert result["score"] is None

    def test_uses_posted_at_when_available(self):
        entry = {"posted_at": iso_days_ago(1), "first_seen_at": iso_days_ago(50), "status_override": None}
        result = fr.compute_freshness(entry)
        assert result["date_source"] == "posted_at"
        assert result["status"] == fr.FRESH

    def test_falls_back_to_first_seen_and_flags_estimate(self):
        entry = {"posted_at": None, "first_seen_at": iso_days_ago(20), "status_override": None}
        result = fr.compute_freshness(entry)
        assert "estimated" in result["date_source"]
        assert result["status"] == fr.OLD

    def test_closed_short_circuits_to_zero(self):
        entry = {"posted_at": iso_days_ago(1), "first_seen_at": iso_days_ago(1), "status_override": fr.CLOSED}
        result = fr.compute_freshness(entry)
        assert result["status"] == fr.CLOSED
        assert result["score"] == 0

    def test_closed_candidate_lowers_but_does_not_zero_score(self):
        base_entry = {"posted_at": iso_days_ago(1), "first_seen_at": iso_days_ago(1), "status_override": None}
        candidate_entry = dict(base_entry, status_override=fr.CLOSED_CANDIDATE)
        base_score = fr.compute_freshness(base_entry)["score"]
        cand_score = fr.compute_freshness(candidate_entry)["score"]
        assert 0 < cand_score < base_score

    def test_closed_candidate_status_reported(self):
        entry = {"posted_at": iso_days_ago(1), "first_seen_at": iso_days_ago(1), "status_override": fr.CLOSED_CANDIDATE}
        result = fr.compute_freshness(entry)
        assert result["status"] == fr.CLOSED_CANDIDATE


class TestFreshnessForJob:
    def test_records_and_computes_in_one_call(self, store):
        result = fr.freshness_for_job(job(posted="2026-08-01"), path=store)
        assert result["status"] in (fr.FRESH, fr.AGING, fr.OLD, fr.STALE)
        assert fr.get_entry(job(), path=store) is not None

    def test_record_false_does_not_create_entry(self, store):
        result = fr.freshness_for_job(job(), path=store, record=False)
        assert result["status"] == fr.UNKNOWN
        assert fr.get_entry(job(), path=store) is None


class TestClosedTransitions:
    def test_mark_closed_candidate_then_confirm(self, store):
        j = job()
        fr.mark_closed_candidate(j, reason="404 on link check", path=store)
        entry = fr.get_entry(j, path=store)
        assert entry["status_override"] == fr.CLOSED_CANDIDATE
        assert entry["closed_candidate_reason"] == "404 on link check"
        fr.confirm_closed(j, path=store)
        entry2 = fr.get_entry(j, path=store)
        assert entry2["status_override"] == fr.CLOSED
        assert entry2["closed_at"] is not None

    def test_mark_closed_candidate_on_unseen_job_creates_entry(self, store):
        j = job()
        assert fr.get_entry(j, path=store) is None
        fr.mark_closed_candidate(j, path=store)
        assert fr.get_entry(j, path=store) is not None
