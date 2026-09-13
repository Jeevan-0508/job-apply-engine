"""Tests for engine.jd_analyzer.analyze_severity -- must-have vs nice-to-have."""
from engine.jd_analyzer import analyze_severity, MUST, PREFERRED, STANDARD


class TestSeverityDetection:
    def test_must_have_language_english(self):
        jd = "Excel skills are required for this role."
        assert analyze_severity(jd).get("excel") == MUST

    def test_must_have_language_german(self):
        jd = "Erfahrung mit SQL ist erforderlich."
        assert analyze_severity(jd).get("sql") == MUST

    def test_preferred_language_english(self):
        jd = "Python experience is nice to have."
        assert analyze_severity(jd).get("python") == PREFERRED

    def test_preferred_language_german(self):
        jd = "GDPR-Kenntnisse sind von Vorteil."
        assert analyze_severity(jd).get("gdpr") == PREFERRED

    def test_no_severity_language_is_standard(self):
        jd = "The team also uses Tableau for reporting."
        assert analyze_severity(jd).get("tableau") == STANDARD

    def test_never_guesses_must_without_language(self):
        jd = "Tableau. Tableau is used daily."
        assert analyze_severity(jd).get("tableau") != MUST

    def test_strongest_tag_wins_across_sentences(self):
        jd = "Excel is required. Elsewhere, Excel is also nice to have for reporting."
        assert analyze_severity(jd)["excel"] == MUST

    def test_unrelated_sentence_does_not_bleed_severity(self):
        jd = "Excel is required for the core role. SQL is used by the data team."
        result = analyze_severity(jd)
        assert result.get("excel") == MUST
        assert result.get("sql") == STANDARD

    def test_empty_text_returns_empty(self):
        assert analyze_severity("") == {}

    def test_none_text_returns_empty(self):
        assert analyze_severity(None) == {}
