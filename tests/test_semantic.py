"""
Regression tests for JD//OS Slice A+B: semantic requirement matching and the
CV Truth Engine's evidence layer.

Two real bugs found during the forensics pass, both fixed here:

- profile_corpus() read role.get("title", ...) but the profile schema's key
  is "role" -- every job title in experience silently dropped out of the
  evidence corpus, so a skill proven only in a job title (not a bullet or the
  skills list) was reported as an honest-looking but wrong gap.
- "fraud detection" and "fraud prevention" were listed as ALIASES of "fraud
  investigation" -- three related but genuinely different skills were being
  silently treated as identical, exactly the false-equivalence the spec
  calls out by name ("Fraud investigation / Fraud detection / Fraud risk
  must NOT automatically become identical").
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from engine.jd_analyzer import (canonical_skills, canonical_skills_detailed,
                                 match_profile, profile_corpus, EXACT, ALIAS, SEMANTIC)
from engine.skill_map import SKILL_RELATED

from fixtures import PROFILE


def test_job_titles_feed_the_evidence_corpus():
    corpus = profile_corpus(PROFILE)
    for role in PROFILE["experience"]:
        assert role["role"] in corpus


def test_fraud_investigation_and_fraud_detection_are_distinct_skills():
    only_detection = canonical_skills("we need strong fraud detection experience")
    assert only_detection == {"fraud detection"}
    assert "fraud investigation" not in only_detection

    only_investigation = canonical_skills("led internal fraud investigations")
    assert only_investigation == {"fraud investigation"}
    assert "fraud detection" not in only_investigation


def test_semantic_hits_never_count_as_exact_or_alias():
    detailed = canonical_skills_detailed("we need strong fraud detection experience")
    assert detailed["fraud detection"] == EXACT
    assert detailed.get("fraud investigation") == SEMANTIC
    assert detailed.get("fraud prevention") == SEMANTIC


def test_semantic_relation_is_bidirectional_but_not_symmetric_with_exact():
    both = canonical_skills_detailed("fraud investigation and fraud detection")
    assert both["fraud investigation"] == EXACT
    assert both["fraud detection"] == EXACT
    # a third related skill mentioned nowhere is still only a semantic hint
    assert both.get("fraud prevention") == SEMANTIC


def test_match_profile_does_not_credit_a_semantic_relative():
    """A profile that only evidences fraud detection must not silently satisfy
    a JD asking for fraud investigation -- that is the conflation bug."""
    jd_signal = {"fraud investigation": 3}
    profile_skills = ["Fraud Detection"]
    matched, gaps = match_profile(profile_skills, jd_signal, extra_corpus="fraud detection systems")
    assert "fraud investigation" in gaps
    assert not matched


def test_every_related_skill_pair_is_a_real_canonical_skill():
    from engine.skill_map import SKILL_WEIGHTS
    for skill, related in SKILL_RELATED.items():
        assert skill in SKILL_WEIGHTS
        for r in related:
            assert r in SKILL_WEIGHTS, f"{r} referenced by SKILL_RELATED but not a canonical skill"


# ------------------------------------------------------------ evidence layer

from engine.evidence import build_evidence, skill_evidence_index, why_you_match, why_you_dont


def test_build_evidence_indexes_every_profile_section():
    records = build_evidence(PROFILE)
    categories = {r["category"] for r in records}
    assert {"SKILL", "EXPERIENCE", "CERTIFICATION", "EDUCATION", "LANGUAGE"} <= categories
    # every record must carry the exact text as written in the profile --
    # nothing paraphrased or summarized
    assert any(r["text"] == PROFILE["experience"][0]["bullets"][0] for r in records)


def test_why_you_match_cites_the_evidence_text_not_just_a_skill_name():
    jd_signal = {"loss prevention": 3, "sql": 2}
    rows = why_you_match(PROFILE, jd_signal)
    lp_row = next(r for r in rows if r["skill"] == "loss prevention")
    assert lp_row["evidence"]
    assert all("text" in h and "source" in h for h in lp_row["evidence"])


def test_why_you_dont_separates_real_gaps_from_semantic_near_misses():
    # PROFILE (fixtures.py) has no fraud-detection evidence at all, and no
    # fraud-investigation evidence either -- but does mention "fraud
    # patterns" in a bullet, which is not any canonical fraud skill.
    jd_signal = {"fraud investigation": 3, "gdpr": 3}
    rows = why_you_dont(PROFILE, jd_signal)
    skills_reported = {r["skill"] for r in rows}
    assert "fraud investigation" in skills_reported
    assert "gdpr" not in skills_reported  # PROFILE lists GDPR as a skill


# ------------------------------------------------------------ CV Truth Engine

import copy
import os

from engine.cv_builder import build_cv_pdf, tailor_profile
from engine.integrity import check_integrity
from engine.jd_analyzer import analyze_jd


def _build_tailored_pdf(tmp_path, profile=PROFILE, jd_text=JD if False else None):
    pass


def test_integrity_check_passes_a_real_generated_cv(tmp_path):
    jd_signal = analyze_jd(
        "Loss Prevention Specialist. Root cause analysis, inventory shrinkage, "
        "audit exceptions, Power BI dashboards, SQL, GDPR."
    )
    tailored = tailor_profile(PROFILE, jd_signal)
    pdf_path = os.path.join(str(tmp_path), "CV.pdf")
    build_cv_pdf(tailored, pdf_path, layout="international", fit_pages=2)

    report = check_integrity(pdf_path, tailored, PROFILE, jd_signal=jd_signal)
    assert report["blocked"] is False, report["unsupported"]
    assert report["score"] == 100
    assert all(c["status"] == "pass" for c in report["checks"].values())


def test_integrity_check_catches_a_bullet_not_in_the_original_profile(tmp_path):
    jd_signal = analyze_jd("Loss prevention and inventory shrinkage.")
    tailored = tailor_profile(PROFILE, jd_signal)
    # simulate a rendering/tailoring bug: a bullet appears that the stored
    # profile never actually said
    tailored = copy.deepcopy(tailored)
    tailored["experience"][0]["bullets"][0] = "Personally saved the company $50M through sheer willpower."
    pdf_path = os.path.join(str(tmp_path), "CV.pdf")
    build_cv_pdf(tailored, pdf_path, layout="international", fit_pages=2)

    report = check_integrity(pdf_path, tailored, PROFILE, jd_signal=jd_signal)
    assert report["blocked"] is True
    assert report["checks"]["bullets"]["status"] == "fail"
    assert any("not found verbatim" in u for u in report["unsupported"])


def test_integrity_check_catches_an_invented_skill(tmp_path):
    jd_signal = analyze_jd("Loss prevention.")
    tailored = copy.deepcopy(tailor_profile(PROFILE, jd_signal))
    tailored["skills"] = tailored["skills"] + ["SAP GRC"]  # never in PROFILE
    pdf_path = os.path.join(str(tmp_path), "CV.pdf")
    build_cv_pdf(tailored, pdf_path, layout="international", fit_pages=2)

    report = check_integrity(pdf_path, tailored, PROFILE, jd_signal=jd_signal)
    assert report["blocked"] is True
    assert report["checks"]["skills"]["status"] == "fail"
    assert any("SAP GRC" in u for u in report["unsupported"])
