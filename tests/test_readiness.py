"""Tests for engine.readiness -- Application Readiness composite score."""
from engine.readiness import compute_readiness, READY, CONDITIONAL, STRETCH, NOT_READY
from engine.jd_analyzer import MUST, PREFERRED, STANDARD


def fit(coverage=80, relevance=80, signal=None, missing=None, low_signal=False):
    return {
        "coverage": coverage, "relevance": relevance,
        "signal": signal or {"excel": 3, "sql": 2, "gdpr": 2},
        "missing": missing or [],
        "low_signal": low_signal,
    }


class TestBasicShape:
    def test_returns_score_band_factors_notes(self):
        result = compute_readiness(fit())
        assert set(["score", "band", "factors", "missing_must_haves", "notes"]) <= set(result)
        assert 0 <= result["score"] <= 100


class TestCoverageAndRelevance:
    def test_higher_coverage_raises_score(self):
        low = compute_readiness(fit(coverage=20))
        high = compute_readiness(fit(coverage=90))
        assert high["score"] > low["score"]

    def test_higher_relevance_raises_score(self):
        low = compute_readiness(fit(relevance=20))
        high = compute_readiness(fit(relevance=90))
        assert high["score"] > low["score"]


class TestMustHaveCoverage:
    def test_missing_must_have_is_flagged(self):
        severity = {"excel": MUST, "sql": STANDARD, "gdpr": STANDARD}
        result = compute_readiness(fit(missing=["excel"]), severity=severity)
        assert "excel" in result["missing_must_haves"]
        assert any("excel" in n for n in result["notes"])

    def test_missing_must_have_caps_band_below_ready(self):
        severity = {"excel": MUST, "sql": STANDARD, "gdpr": STANDARD}
        result = compute_readiness(fit(coverage=95, relevance=95, missing=["excel"]),
                                    severity=severity, quality_score=95)
        assert result["band"] != READY

    def test_all_must_haves_covered_allows_ready(self):
        severity = {"excel": MUST, "sql": STANDARD, "gdpr": STANDARD}
        result = compute_readiness(fit(coverage=95, relevance=95, missing=[]),
                                    severity=severity, quality_score=95)
        assert result["band"] == READY

    def test_no_must_haves_detected_is_neutral_not_penalized(self):
        result = compute_readiness(fit(), severity={"sql": STANDARD})
        assert result["factors"]["must_have_coverage"] == compute_readiness(fit(), severity=None)["factors"]["must_have_coverage"]
        assert "no must-have requirements detected" in " ".join(result["notes"])

    def test_must_have_not_in_signal_is_ignored_not_counted_missing(self):
        # a MUST-tagged skill from severity that this posting's signal never
        # actually asked for (e.g. from a stray sentence) should not be
        # treated as a missing requirement of THIS scoring
        severity = {"docker": MUST}
        result = compute_readiness(fit(), severity=severity)
        assert result["missing_must_haves"] == []


class TestListingQualityInput:
    def test_higher_quality_raises_score(self):
        low = compute_readiness(fit(), quality_score=10)
        high = compute_readiness(fit(), quality_score=95)
        assert high["score"] > low["score"]

    def test_missing_quality_is_neutral_and_noted(self):
        result = compute_readiness(fit(), quality_score=None)
        assert "listing quality not evaluated" in result["notes"]


class TestBands:
    def test_strong_fit_full_inputs_is_ready(self):
        severity = {"excel": MUST, "sql": PREFERRED, "gdpr": STANDARD}
        result = compute_readiness(fit(coverage=95, relevance=95, missing=[]),
                                    severity=severity, quality_score=90)
        assert result["band"] == READY

    def test_weak_fit_is_not_ready(self):
        result = compute_readiness(fit(coverage=5, relevance=5, missing=["excel", "sql", "gdpr"]),
                                    quality_score=5)
        assert result["band"] == NOT_READY

    def test_low_signal_is_noted(self):
        result = compute_readiness(fit(low_signal=True))
        assert any("too little detectable signal" in n for n in result["notes"])
