"""Tests for engine.job_quality -- posting quality, independent of candidate fit."""
from engine.job_quality import score_job_quality


def job(source="Greenhouse", source_id="1", company="Acme", title="Risk Manager",
         location="Berlin", link="https://example.com/1", posted="2026-08-01",
         matched_sources=None):
    j = {"source": source, "source_id": source_id, "company": company, "title": title,
         "location": location, "link": link, "posted": posted}
    if matched_sources is not None:
        j["matched_sources"] = matched_sources
    return j


FULL_DESC = (
    "We are hiring a Risk Manager. Requirements: 5 years experience in fraud. "
    "Salary: EUR 70,000 - 85,000 per year. You bring strong analytical skills."
)


class TestScoreShape:
    def test_returns_score_band_factors_notes(self):
        result = score_job_quality(job(), description=FULL_DESC, description_status="FULL", freshness_score=95)
        assert set(["score", "band", "factors", "notes"]) <= set(result)
        assert 0 <= result["score"] <= 100

    def test_never_equals_candidate_match_semantics(self):
        # sanity: this module has no notion of a candidate profile at all
        import inspect
        sig = inspect.signature(score_job_quality)
        assert "profile" not in sig.parameters


class TestSourceReliability:
    def test_ats_native_source_scores_higher_than_unnamed(self):
        good = score_job_quality(job(source="Greenhouse"), description_status="FULL")
        bad = score_job_quality(job(source=""), description_status="FULL")
        assert good["factors"]["source_reliability"] > bad["factors"]["source_reliability"]

    def test_arbeitsagentur_treated_as_reasonably_reliable(self):
        result = score_job_quality(job(source="Arbeitsagentur"), description_status="FULL")
        assert result["factors"]["source_reliability"] > 0


class TestDescriptionCompleteness:
    def test_full_beats_partial_beats_title_only_beats_unavailable(self):
        scores = [
            score_job_quality(job(), description_status=s)["factors"]["description_completeness"]
            for s in ("FULL", "PARTIAL", "TITLE_ONLY", "UNAVAILABLE")
        ]
        assert scores == sorted(scores, reverse=True)
        assert scores[-1] == 0.0

    def test_unknown_status_treated_as_zero_not_guessed(self):
        result = score_job_quality(job(), description_status=None)
        assert result["factors"]["description_completeness"] == 0.0


class TestFieldCompleteness:
    def test_missing_fields_lower_score(self):
        full = score_job_quality(job())
        thin = score_job_quality(job(company="", location="", link="", posted=""))
        assert full["factors"]["field_completeness"] > thin["factors"]["field_completeness"]
        assert "missing basic fields" in " ".join(thin["notes"])


class TestCorroboration:
    def test_multi_source_scores_higher_than_single(self):
        multi = score_job_quality(job(matched_sources=["Greenhouse", "Lever"]))
        single = score_job_quality(job(matched_sources=["Greenhouse"]))
        assert multi["factors"]["corroboration"] > single["factors"]["corroboration"]

    def test_no_source_at_all_scores_zero_corroboration(self):
        j = job(source="")
        j.pop("matched_sources", None)
        result = score_job_quality(j)
        assert result["factors"]["corroboration"] == 0.0


class TestFreshnessIntegration:
    def test_high_freshness_score_raises_total(self):
        fresh = score_job_quality(job(), description_status="FULL", freshness_score=100)
        stale = score_job_quality(job(), description_status="FULL", freshness_score=5)
        assert fresh["score"] > stale["score"]

    def test_unknown_freshness_is_neutral_and_noted(self):
        result = score_job_quality(job(), description_status="FULL", freshness_score=None)
        assert "freshness not evaluated" in result["notes"]


class TestRequirementsAndSalaryDetection:
    def test_detects_requirements_section(self):
        result = score_job_quality(job(), description=FULL_DESC, description_status="FULL")
        assert result["factors"]["requirements_disclosed"] > 0
        assert "no clear requirements section found" not in result["notes"]

    def test_detects_salary_figure(self):
        result = score_job_quality(job(), description=FULL_DESC, description_status="FULL")
        assert result["factors"]["salary_disclosed"] > 0

    def test_no_salary_mentioned_is_flagged_not_guessed(self):
        result = score_job_quality(job(), description="Great team, apply now.", description_status="FULL")
        assert result["factors"]["salary_disclosed"] == 0
        assert "no salary" in " ".join(result["notes"])

    def test_german_requirements_keywords_detected(self):
        text = "Ihr Profil: mehrere Jahre Erfahrung im Risikomanagement."
        result = score_job_quality(job(), description=text, description_status="FULL")
        assert result["factors"]["requirements_disclosed"] > 0


class TestBands:
    def test_thin_listing_lands_in_low_or_very_low_band(self):
        thin_job = job(source="", company="", location="", link="", posted="")
        thin_job.pop("matched_sources", None)
        result = score_job_quality(thin_job, description_status="UNAVAILABLE", freshness_score=None)
        assert result["band"] in ("LOW", "VERY LOW")

    def test_strong_listing_lands_in_high_band(self):
        result = score_job_quality(
            job(matched_sources=["Greenhouse", "Lever"]),
            description=FULL_DESC, description_status="FULL", freshness_score=95,
        )
        assert result["band"] == "HIGH"
