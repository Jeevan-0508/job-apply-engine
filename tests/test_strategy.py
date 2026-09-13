"""Tests for engine.strategy -- one recommended action, trust gates everything."""
from engine.strategy import recommend_strategy, VERIFY_FIRST, SKIP, APPLY_NOW, APPLY_WITH_TAILORED_LETTER, STRETCH


def readiness(band="READY", score=90, missing_must_haves=None, notes=None):
    return {"band": band, "score": score, "missing_must_haves": missing_must_haves or [], "notes": notes or []}


def trust(level="OK", flags=None):
    return {"level": level, "flags": flags or []}


class TestTrustGatesEverything:
    def test_warning_trust_always_wins_over_high_readiness(self):
        result = recommend_strategy(
            readiness(band="READY", score=99),
            trust(level="WARNING", flags=[{"level": "WARNING", "text": "no direct application link"}]),
        )
        assert result["action"] == VERIFY_FIRST
        assert "no direct application link" in result["reasons"]

    def test_ok_trust_does_not_block_apply_now(self):
        result = recommend_strategy(readiness(band="READY"), trust(level="OK"))
        assert result["action"] == APPLY_NOW

    def test_info_only_trust_does_not_block_apply_now(self):
        result = recommend_strategy(readiness(band="READY"), trust(level="INFO", flags=[{"level": "INFO", "text": "x"}]))
        assert result["action"] == APPLY_NOW


class TestReadinessBands:
    def test_not_ready_recommends_skip(self):
        result = recommend_strategy(readiness(band="NOT READY", score=10), trust())
        assert result["action"] == SKIP

    def test_conditional_recommends_tailored_letter(self):
        result = recommend_strategy(readiness(band="CONDITIONAL", missing_must_haves=["sql"]), trust())
        assert result["action"] == APPLY_WITH_TAILORED_LETTER
        assert any("sql" in r for r in result["reasons"])

    def test_stretch_recommends_stretch_application(self):
        result = recommend_strategy(readiness(band="STRETCH"), trust())
        assert result["action"] == STRETCH


class TestCompanyIntelligenceIntegration:
    def test_company_flags_surfaced_as_reasons(self):
        company = {"known": True, "flags": ["applied 3x here with no interview yet -- worth asking whether this company converts for you at all"]}
        result = recommend_strategy(readiness(band="READY"), trust(), company=company)
        assert any("no interview" in r for r in result["reasons"])

    def test_no_company_data_does_not_error(self):
        result = recommend_strategy(readiness(band="READY"), trust(), company=None)
        assert result["action"] == APPLY_NOW
