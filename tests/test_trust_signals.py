"""Tests for engine.trust_signals -- explainable red/green flag checklist."""
from engine.trust_signals import trust_signals, WARNING, INFO


def job(company="Acme", link="https://example.com/1", location="Berlin",
        source="Greenhouse", matched_sources=None):
    j = {"company": company, "link": link, "location": location, "source": source}
    if matched_sources is not None:
        j["matched_sources"] = matched_sources
    return j


class TestCleanPosting:
    def test_fully_specified_multi_source_posting_is_ok_or_info_only(self):
        result = trust_signals(job(matched_sources=["Greenhouse", "Lever"]))
        assert result["level"] in ("OK", "INFO")
        assert not any(f["level"] == WARNING for f in result["flags"])


class TestCompanyName:
    def test_missing_company_is_warning(self):
        result = trust_signals(job(company=""))
        assert result["level"] == WARNING

    def test_generic_placeholder_company_is_warning(self):
        result = trust_signals(job(company="Confidential"))
        assert result["level"] == WARNING

    def test_real_company_name_not_flagged(self):
        result = trust_signals(job(company="Acme GmbH"))
        assert not any("company name" in f["text"] for f in result["flags"])


class TestLinkAndLocation:
    def test_missing_link_is_warning(self):
        result = trust_signals(job(link=""))
        assert result["level"] == WARNING

    def test_missing_location_is_info_not_warning(self):
        result = trust_signals(job(location=""))
        assert any(f["text"] == "location not specified" for f in result["flags"])
        assert not any(f["level"] == WARNING and "location" in f["text"] for f in result["flags"])


class TestCorroboration:
    def test_single_source_flagged_as_info(self):
        result = trust_signals(job(matched_sources=["Greenhouse"]))
        assert any("only one source" in f["text"] for f in result["flags"])

    def test_multi_source_not_flagged(self):
        result = trust_signals(job(matched_sources=["Greenhouse", "Lever"]))
        assert not any("only one source" in f["text"] for f in result["flags"])


class TestFreshnessIntegration:
    def test_closed_is_warning(self):
        result = trust_signals(job(), freshness_status="CLOSED")
        assert result["level"] == WARNING

    def test_closed_candidate_is_warning(self):
        result = trust_signals(job(), freshness_status="CLOSED_CANDIDATE")
        assert result["level"] == WARNING

    def test_stale_is_warning(self):
        result = trust_signals(job(), freshness_status="STALE")
        assert result["level"] == WARNING

    def test_fresh_not_flagged(self):
        result = trust_signals(job(matched_sources=["Greenhouse", "Lever"]), freshness_status="FRESH")
        assert not any("stale" in f["text"] or "closed" in f["text"] for f in result["flags"])


class TestDescriptionStatus:
    def test_unavailable_description_flagged_info(self):
        result = trust_signals(job(), description_status="UNAVAILABLE")
        assert any("could be read" in f["text"] for f in result["flags"])
