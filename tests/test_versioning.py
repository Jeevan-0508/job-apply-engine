"""Tests for engine.versioning -- append-only CV version history per job."""
import pytest

from engine import versioning as v


def job(link="https://example.com/1"):
    return {"link": link, "company": "Acme", "title": "Risk Manager", "location": "Berlin"}


def meta(coverage=50, relevance=50, ats_score=60, integrity_score=100,
         integrity_blocked=False, red_team_score=70, matched_skills=None, missing_skills=None):
    return {
        "coverage": coverage, "relevance": relevance, "ats_score": ats_score,
        "integrity_score": integrity_score, "integrity_blocked": integrity_blocked,
        "red_team_score": red_team_score,
        "matched_skills": matched_skills or ["excel"],
        "missing_skills": missing_skills or ["sql"],
    }


@pytest.fixture
def store(tmp_path):
    return str(tmp_path / "versions.json")


class TestRecordAndHistory:
    def test_first_version_creates_history_of_one(self, store):
        v.record_version(job(), meta(), path=store)
        assert len(v.get_history(job(), path=store)) == 1

    def test_second_version_appends_not_overwrites(self, store):
        v.record_version(job(), meta(coverage=40), path=store)
        v.record_version(job(), meta(coverage=60), path=store)
        history = v.get_history(job(), path=store)
        assert len(history) == 2
        assert history[0]["coverage"] == 40
        assert history[1]["coverage"] == 60

    def test_no_history_for_unseen_job_is_empty_list(self, store):
        assert v.get_history(job(), path=store) == []

    def test_different_jobs_get_separate_histories(self, store):
        v.record_version(job("https://example.com/a"), meta(), path=store)
        v.record_version(job("https://example.com/b"), meta(), path=store)
        assert len(v.get_history(job("https://example.com/a"), path=store)) == 1
        assert len(v.get_history(job("https://example.com/b"), path=store)) == 1


class TestDiffLastTwo:
    def test_no_diff_with_fewer_than_two_versions(self, store):
        v.record_version(job(), meta(), path=store)
        assert v.diff_last_two(job(), path=store) is None

    def test_no_diff_with_zero_versions(self, store):
        assert v.diff_last_two(job(), path=store) is None

    def test_score_deltas_computed(self, store):
        v.record_version(job(), meta(coverage=40, ats_score=50, red_team_score=60), path=store)
        v.record_version(job(), meta(coverage=70, ats_score=55, red_team_score=80), path=store)
        diff = v.diff_last_two(job(), path=store)
        assert diff["coverage_delta"] == 30
        assert diff["ats_delta"] == 5
        assert diff["red_team_delta"] == 20

    def test_negative_delta_when_score_drops(self, store):
        v.record_version(job(), meta(coverage=80), path=store)
        v.record_version(job(), meta(coverage=50), path=store)
        diff = v.diff_last_two(job(), path=store)
        assert diff["coverage_delta"] == -30

    def test_skills_gained_and_lost(self, store):
        v.record_version(job(), meta(matched_skills=["excel", "sql"]), path=store)
        v.record_version(job(), meta(matched_skills=["excel", "gdpr"]), path=store)
        diff = v.diff_last_two(job(), path=store)
        assert diff["skills_gained"] == ["gdpr"]
        assert diff["skills_lost"] == ["sql"]

    def test_version_count_reported(self, store):
        v.record_version(job(), meta(), path=store)
        v.record_version(job(), meta(), path=store)
        v.record_version(job(), meta(), path=store)
        diff = v.diff_last_two(job(), path=store)
        assert diff["version_count"] == 3

    def test_missing_score_field_gives_none_delta_not_guessed(self, store):
        m1 = meta()
        m1["ats_score"] = None
        v.record_version(job(), m1, path=store)
        v.record_version(job(), meta(ats_score=90), path=store)
        diff = v.diff_last_two(job(), path=store)
        assert diff["ats_delta"] is None
