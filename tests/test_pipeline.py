"""
Regression tests for the one-click pipeline: scoring, the cover letter's honesty
guarantee, the application tracker and the packager.

Two of these exist because of defects that were invisible in the source and only
appeared in the output:

- the cover letter fell back to the job's own requirements when nothing matched,
  producing letters that opened "my experience in loss prevention, fraud
  investigation" -- naming precisely the skills the profile did not have;
- a thin but precisely relevant posting scored zero while a keyword-stuffed
  generic one scored fifty, so the ranking was actively misleading.

Anything that could reintroduce either must fail here.
"""
import csv
import io
import json
import zipfile
from datetime import date, datetime, timedelta

import pytest

from engine import tracker
from engine.cover_letter import (_top_skills, build_cover_letter_text,
                                 subject_line)
from engine.jd_analyzer import analyze_jd
from engine.match import LOW_SIGNAL, TITLE_BOOST, demand_report, score_job, score_text
from engine.package import build_package, folder_for, safe_name

from fixtures import JD, PROFILE

# a real posting whose every recognised skill is absent from the fixture profile
UNRELATED_JD = ("Cloud Security Engineer. Kubernetes, Terraform, penetration "
                "testing, CI/CD pipelines, Python, AWS, incident response.")


# --------------------------------------------------------------------- scoring

def test_score_reports_coverage_and_relevance_separately():
    fit = score_text(JD, PROFILE, title="Loss Prevention Specialist")
    assert 0 < fit["coverage"] <= 100
    assert 0 < fit["relevance"] <= 100
    # they measure the same two sets in opposite directions, so a blended single
    # number would hide whichever one is the problem
    assert fit["coverage"] != fit["relevance"] or fit["coverage"] == 100
    assert fit["band"] in {"strong", "good", "partial", "weak"}
    assert fit["matched"] and not set(fit["matched"]) & set(fit["missing"])


def test_title_boost_weights_the_role_above_the_body():
    body = "You will support loss prevention activities across the region."
    plain = score_text(body, PROFILE)
    boosted = score_text(body, PROFILE, title="Loss Prevention Manager")
    assert boosted["signal"]["loss prevention"] == plain["signal"]["loss prevention"] * TITLE_BOOST


def test_a_thin_posting_is_flagged_rather_than_ranked():
    fit = score_text("Good Excel skills required.", PROFILE)
    assert fit["total_weight"] < LOW_SIGNAL
    assert fit["low_signal"] is True
    assert fit["band"] == "low signal"
    assert "not a reliable measurement" in fit["verdict"]


def test_a_posting_with_no_known_skills_scores_nothing():
    for text in ("", None, "We are a friendly team in a modern office."):
        fit = score_text(text or "", PROFILE)
        assert fit["coverage"] == 0
        assert fit["low_signal"] is True


def test_missing_core_requirements_are_named_in_the_verdict():
    jd = ("Incident response lead. You will own incident response, Python "
          "automation, Kubernetes and Terraform, plus loss prevention reporting "
          "and inventory shrinkage analysis.")
    fit = score_text(jd, PROFILE)
    assert fit["total_weight"] >= LOW_SIGNAL, "fixture JD must carry enough signal to be ranked"
    assert "incident response" in fit["core_missing"]
    assert "incident response" in fit["verdict"]
    assert f"of {fit['core_total']} core requirement" in fit["verdict"]


def test_score_job_says_when_it_only_had_the_title():
    job = {"title": "Loss Prevention Specialist", "company": "Beispiel", "snippet": "Munich"}
    assert "title only" in score_job(job, PROFILE)["basis"]
    assert score_job(job, PROFILE, description=JD * 3)["basis"] == "full description"


def test_demand_report_ranks_skills_by_how_often_they_cost_a_match():
    scored = [
        {"signal": {"german language": 3, "sql": 2}, "missing": ["german language"]},
        {"signal": {"german language": 3, "cctv": 1}, "missing": ["german language", "cctv"]},
    ]
    rows = demand_report(scored)
    assert rows[0]["skill"] == "german language"
    assert rows[0]["postings_missing"] == 2
    assert rows[0]["postings_asking"] == 2
    assert rows[0]["share"] == 1.0
    assert demand_report([]) == []


# ------------------------------------------------------------- letter honesty

def test_letter_never_claims_a_skill_the_profile_lacks():
    signal = analyze_jd(UNRELATED_JD)
    assert signal, "the unrelated JD must produce some signal for this test to mean anything"

    claimed, overlaps = _top_skills(PROFILE, signal)
    assert overlaps is False
    assert claimed, "with no overlap the letter must still name the profile's own strengths"
    assert set(claimed) <= set(PROFILE["skills"])

    for language in ("en", "de"):
        text = " ".join(build_cover_letter_text(
            PROFILE, signal, "Beispiel GmbH", "Cloud Security Engineer", language=language)).lower()
        for demanded in signal:
            assert demanded not in text, f"letter claims {demanded!r}, which the profile does not evidence"


def test_letter_claims_the_overlap_when_there_is_one():
    signal = analyze_jd(JD)
    claimed, overlaps = _top_skills(PROFILE, signal)
    assert overlaps is True
    assert claimed
    text = " ".join(build_cover_letter_text(PROFILE, signal, "Beispiel GmbH", "Loss Prevention Specialist"))
    assert "lines up closely" in text
    assert claimed[0] in text


def test_german_letter_uses_the_expected_salutation_and_close():
    paragraphs = build_cover_letter_text(
        PROFILE, analyze_jd(JD), "Beispiel GmbH", "Sicherheitsmanager", language="de")
    assert paragraphs[0] == "Sehr geehrte Damen und Herren,"
    assert "Mit freundlichen Gr\u00fc\u00dfen" in paragraphs
    assert paragraphs[-1] == PROFILE["name"]
    assert subject_line("Beispiel GmbH", "Sicherheitsmanager", language="de") == \
        "Bewerbung als Sicherheitsmanager"


# --------------------------------------------------------------------- tracker

JOB = {"title": "Loss Prevention Manager", "company": "Beispiel GmbH",
       "location": "Munich", "source": "Arbeitsagentur",
       "link": "https://example.com/jobs/1"}


@pytest.fixture()
def store(tmp_path):
    return str(tmp_path / "pipeline.json")


def test_upsert_is_idempotent_on_the_same_link(store):
    tracker.upsert(JOB, path=store)
    tracker.upsert(JOB, path=store)
    tracker.upsert({**JOB, "link": "HTTPS://EXAMPLE.COM/JOBS/1 "}, path=store)
    assert len(tracker.load(store)) == 1
    assert tracker.known_ids(store) == {"https://example.com/jobs/1"}


def test_upsert_preserves_fields_recorded_earlier(store):
    tracker.upsert(JOB, path=store, coverage=62, notes="referral via Anna")
    entry = tracker.upsert(JOB, path=store, ats_score=95, coverage=None)
    assert entry["coverage"] == 62, "None must not erase a recorded value"
    assert entry["notes"] == "referral via Anna"
    assert entry["ats_score"] == 95
    assert entry["status"] == "Shortlisted"


def test_marking_applied_records_the_date(store):
    entry = tracker.upsert(JOB, path=store)
    tracker.set_status(entry["id"], "Applied", path=store, notes="sent via portal")
    saved = tracker.load(store)[0]
    assert saved["status"] == "Applied"
    assert saved["applied_on"] == date.today().isoformat()
    assert saved["notes"] == "sent via portal"


def test_metrics_report_response_and_interview_rates():
    now = datetime.now().isoformat(timespec="seconds")
    entries = [
        {"status": "Shortlisted", "created": now, "source": "LinkedIn"},
        {"status": "Applied", "created": now, "source": "LinkedIn", "coverage": 40, "ats_score": 90},
        {"status": "Interview", "created": now, "source": "Arbeitsagentur", "coverage": 60, "ats_score": 96},
        {"status": "Offer", "created": now, "source": "Arbeitsagentur"},
        {"status": "Rejected", "created": now, "source": "LinkedIn"},
    ]
    m = tracker.metrics(entries)
    assert m["total"] == 5
    assert m["open"] == 3          # shortlisted + applied + interview
    assert m["applied"] == 4       # applied + interview + offer + rejected
    assert m["answered"] == 3
    assert m["interviews"] == 2
    assert m["response_rate"] == 0.75
    assert m["interview_rate"] == 0.5
    assert m["avg_coverage"] == 50
    assert m["avg_ats"] == 93
    assert m["added_this_week"] == 5
    assert m["by_source"]["Arbeitsagentur"] == {"total": 2, "applied": 2, "answered": 2}
    assert tracker.metrics([])["response_rate"] is None


def test_stale_only_flags_sent_applications_gone_quiet():
    old = (date.today() - timedelta(days=tracker.STALE_AFTER_DAYS + 4)).isoformat()
    recent = date.today().isoformat()
    entries = [
        {"id": "a", "status": "Applied", "applied_on": old},
        {"id": "b", "status": "Applied", "applied_on": recent},
        {"id": "c", "status": "Shortlisted", "updated": old},
    ]
    flagged = tracker.stale(entries)
    assert [e["id"] for e in flagged] == ["a"]
    assert flagged[0]["days_quiet"] >= tracker.STALE_AFTER_DAYS


def test_csv_export_round_trips_through_a_reader(store):
    tracker.upsert(JOB, path=store, coverage=62, folder="applications/Beispiel")
    rows = list(csv.DictReader(io.StringIO(tracker.to_csv(tracker.load(store)))))
    assert len(rows) == 1
    assert rows[0]["company"] == "Beispiel GmbH"
    assert rows[0]["coverage"] == "62"
    assert set(rows[0]) == set(tracker.CSV_FIELDS)


def test_a_corrupt_store_reads_as_empty_rather_than_crashing(tmp_path):
    broken = tmp_path / "pipeline.json"
    broken.write_text("{ this is not json", encoding="utf-8")
    assert tracker.load(str(broken)) == []
    assert tracker.load(str(tmp_path / "absent.json")) == []


# --------------------------------------------------------------------- package

def test_safe_name_survives_a_hostile_job_title():
    assert safe_name("Security / Investigator (m/w/d)*") == "Security_Investigator_mwd"
    assert safe_name("") == "Unknown"
    assert len(safe_name("x" * 200)) == 60
    assert folder_for({"company": None, "title": None}) == \
        "applications" + __import__("os").sep + "Company__Role"


def test_build_package_writes_every_artefact_for_one_job(tmp_path):
    result = build_package(JOB, JD, PROFILE, base_dir=str(tmp_path / "applications"),
                           pipeline_path=str(tmp_path / "pipeline.json"))

    assert result["errors"] == [], result["errors"]
    for key in ("cv_pdf", "cv_docx", "letter_pdf", "letter_docx", "prep_txt",
                "prep_docx", "posting", "meta", "ats_report", "zip"):
        path = result["files"][key]
        assert __import__("os").path.getsize(path) > 0, f"{key} is empty"

    meta = json.loads(open(result["files"]["meta"], encoding="utf-8").read())
    assert meta["coverage"] == result["fit"]["coverage"]
    assert meta["ats_score"] == result["ats"]["score"]
    assert meta["errors"] == []

    with zipfile.ZipFile(result["files"]["zip"]) as zf:
        assert sorted(zf.namelist()) == ["CV.docx", "CV.pdf", "CoverLetter.docx", "CoverLetter.pdf"]

    entry = tracker.load(str(tmp_path / "pipeline.json"))[0]
    assert entry["status"] == "Package built"
    assert entry["folder"] == result["folder"]
    assert entry["ats_score"] == result["ats"]["score"]


def test_a_packaged_cv_still_passes_the_ats_audit(tmp_path):
    """The whole point of packaging is that the output is machine-readable."""
    result = build_package(JOB, JD, PROFILE, base_dir=str(tmp_path / "applications"),
                           pipeline_path=str(tmp_path / "pipeline.json"))
    report = result["ats"]
    assert report["score"] >= 85, report["checks"]
    assert report["checks"]["no_glyph_corruption"]["status"] == "pass"
