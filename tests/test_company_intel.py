"""Tests for engine.company_intel -- internal-history-only company summary."""
import pytest

from engine import company_intel as ci
from engine import tracker


def job(company="Acme", title="Risk Manager", link="https://example.com/1"):
    return {"company": company, "title": title, "location": "Berlin", "link": link, "source": "Greenhouse"}


@pytest.fixture
def store(tmp_path):
    return str(tmp_path / "pipeline.json")


class TestUnknownCompany:
    def test_never_seen_company_is_not_known(self, store):
        profile = ci.company_profile("Nobody Corp", path=store)
        assert profile["known"] is False
        assert profile["postings_seen"] == 0

    def test_known_false_distinct_from_zero_applications(self, store):
        tracker.upsert(job(), path=store)
        tracker.set_status(tracker.job_id(job()), "Shortlisted", path=store)
        profile = ci.company_profile("Acme", path=store)
        assert profile["known"] is True
        assert profile["applications_sent"] == 0


class TestHistoryAndOutcomes:
    def test_counts_only_applied_like_statuses_as_applications(self, store):
        tracker.upsert(job(link="https://example.com/1"), path=store)
        tracker.upsert(job(link="https://example.com/2"), path=store)
        tracker.set_status(tracker.job_id(job(link="https://example.com/2")), "Applied", path=store)
        profile = ci.company_profile("Acme", path=store)
        assert profile["postings_seen"] == 2
        assert profile["applications_sent"] == 1

    def test_case_insensitive_company_match(self, store):
        tracker.upsert(job(company="Acme"), path=store)
        profile = ci.company_profile("acme", path=store)
        assert profile["known"] is True

    def test_roles_seen_lists_distinct_titles(self, store):
        tracker.upsert(job(title="Risk Manager", link="https://example.com/1"), path=store)
        tracker.upsert(job(title="Fraud Analyst", link="https://example.com/2"), path=store)
        profile = ci.company_profile("Acme", path=store)
        assert set(profile["roles_seen"]) == {"Risk Manager", "Fraud Analyst"}


class TestFlags:
    def test_flags_repeat_applications_with_no_interview(self, store):
        for i in range(3):
            j = job(link=f"https://example.com/{i}")
            tracker.upsert(j, path=store)
            tracker.set_status(tracker.job_id(j), "Applied", path=store)
        profile = ci.company_profile("Acme", path=store)
        assert any("no interview" in f for f in profile["flags"])

    def test_flags_interview_reached_positively(self, store):
        j = job()
        tracker.upsert(j, path=store)
        tracker.set_status(tracker.job_id(j), "Interview", path=store)
        profile = ci.company_profile("Acme", path=store)
        assert any("interview stage" in f for f in profile["flags"])

    def test_no_flags_for_single_shortlisted_entry(self, store):
        tracker.upsert(job(), path=store)
        profile = ci.company_profile("Acme", path=store)
        assert profile["flags"] == []
