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
