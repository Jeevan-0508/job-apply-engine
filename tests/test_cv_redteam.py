"""Tests for engine.cv_redteam -- persuasiveness pass, distinct from truth-checking."""
from engine.cv_redteam import red_team_cv


def profile(bullets_by_role):
    return {"experience": [{"role": "Risk Manager", "company": "Acme", "bullets": bullets}
                            for bullets in bullets_by_role]}


class TestNeverJudgesTruth:
    def test_no_profile_param_for_verification(self):
        import inspect
        sig = inspect.signature(red_team_cv)
        assert "original_profile" not in sig.parameters
        assert "profile" not in sig.parameters or list(sig.parameters) == ["tailored_profile"]


class TestQuantification:
    def test_flags_bullet_with_no_number(self):
        result = red_team_cv(profile([["Managed a team and improved processes across the department."]]))
        assert result["flagged_bullets"] == 1
        assert any("not quantified" in i for f in result["findings"] for i in f["issues"])

    def test_does_not_flag_bullet_with_percentage(self):
        result = red_team_cv(profile([["Cut fraud false positives by 40% across EU and NA audits."]]))
        quant_issues = [i for f in result["findings"] for i in f["issues"] if "quantified" in i]
        assert not quant_issues

    def test_does_not_flag_bullet_with_currency(self):
        result = red_team_cv(profile([["Drove $15M in model-based prevention impact."]]))
        quant_issues = [i for f in result["findings"] for i in f["issues"] if "quantified" in i]
        assert not quant_issues


class TestWeakOpeners:
    def test_flags_weak_opener(self):
        result = red_team_cv(profile([["Helped the team reduce fraud by 20%."]]))
        assert any("weak/passive verb" in i for f in result["findings"] for i in f["issues"])

    def test_strong_opener_not_flagged(self):
        result = red_team_cv(profile([["Cut fraud losses by 20% through a new detection model."]]))
        assert not any("weak/passive verb" in i for f in result["findings"] for i in f["issues"])


class TestFillerPhrases:
    def test_flags_filler_phrase(self):
        result = red_team_cv(profile([["Results-driven team player who delivered 30% growth."]]))
        assert any("filler" in i for f in result["findings"] for i in f["issues"])


class TestLength:
    def test_flags_overly_long_bullet(self):
        long_bullet = "Led " + " ".join(["word"] * 40) + " achieving 20% improvement."
        result = red_team_cv(profile([[long_bullet]]))
        assert any("too long" in i for f in result["findings"] for i in f["issues"])

    def test_short_bullet_not_flagged_for_length(self):
        result = red_team_cv(profile([["Cut losses by 20%."]]))
        assert not any("too long" in i for f in result["findings"] for i in f["issues"])


class TestRepeatedOpeners:
    def test_flags_repeated_opening_verb_across_cv(self):
        bullets = ["Led fraud reviews across 5 markets, cutting losses 10%.",
                   "Led a team of 4 analysts to build a 90% accurate model.",
                   "Led SOP rollout adopted by 20+ associates."]
        result = red_team_cv(profile([bullets]))
        whole_cv_findings = [f for f in result["findings"] if f["where"] == "whole CV"]
        assert whole_cv_findings
        assert any("repeated" in i for i in whole_cv_findings[0]["issues"])


class TestScoringAndBands:
    def test_all_clean_bullets_score_high(self):
        bullets = ["Cut fraud false positives by 40% across EU audits.",
                   "Built a forecasting engine reaching 95% accuracy.",
                   "Automated 90% of reporting, saving 10 hours weekly."]
        result = red_team_cv(profile([bullets]))
        assert result["score"] >= 85
        assert result["band"] == "STRONG"

    def test_all_weak_bullets_score_low(self):
        bullets = ["Helped with team player results-driven initiatives.",
                   "Assisted the team with various tasks and duties.",
                   "Responsible for handling day to day operations."]
        result = red_team_cv(profile([bullets]))
        assert result["band"] in ("NEEDS WORK", "WEAK")

    def test_no_bullets_at_all_scores_perfect(self):
        result = red_team_cv({"experience": []})
        assert result["score"] == 100
        assert result["total_bullets"] == 0
