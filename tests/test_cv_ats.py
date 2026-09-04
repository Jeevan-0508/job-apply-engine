"""
Regression tests for CV generation and the ATS audit.

These exist because of a real defect: bullets were rendered in reportlab's
built-in Helvetica, which has no Unicode map for U+2022, so every bullet in
every generated PDF extracted as "(cid:127)" and corrupted the line it sat on.
The CV looked perfect on screen and was damaged in every parser that read it.
Anything that could reintroduce that must fail here.

The profile it scores against lives in tests/fixtures.py and is synthetic on
purpose -- no real personal data belongs in the repository.
"""
import pytest

from engine.ats_check import audit_pdf
from engine.cv_builder import (LABELS, build_cv_docx, build_cv_pdf, period,
                               missing_month_precision, register_fonts,
                               tailor_profile)
from engine.jd_analyzer import analyze_jd, canonical_skills, match_profile

from fixtures import JD, PROFILE


@pytest.fixture(scope="module")
def signal():
    return analyze_jd(JD)


@pytest.fixture(scope="module")
def tailored(signal):
    return tailor_profile(PROFILE, signal)


def test_jd_analyzer_reads_the_loss_prevention_vocabulary(signal):
    for expected in ["loss prevention", "theft investigation", "inventory shrinkage",
                     "root cause analysis", "guard force", "cctv", "access control",
                     "six sigma", "excel", "sql", "gdpr"]:
        assert expected in signal, f"{expected} not detected in the JD"


def test_german_phrasing_scores_the_same_as_english():
    de = analyze_jd("Werkschutz, Diebstahlsermittlungen, Inventurdifferenzen, DSGVO, Datenanalyse")
    assert {"physical security", "theft investigation", "inventory shrinkage",
            "gdpr", "data analysis"} <= set(de)


def test_analyzer_tolerates_empty_input():
    assert analyze_jd("") == {}
    assert analyze_jd(None) == {}


def test_word_boundaries_prevent_false_positives():
    assert "audit" not in analyze_jd("a large auditorium with seating")


def test_profile_wording_is_read_through_the_same_vocabulary():
    """String equality used to drop these -- the original bug in match_profile."""
    assert "audit" in canonical_skills("Audit Frameworks")
    assert "root cause analysis" in canonical_skills("RCA")
    assert "excel" in canonical_skills("Excel (VBA, Pivot)")


def test_matched_skills_are_ordered_by_jd_weight(signal):
    matched, _ = match_profile(PROFILE["skills"], signal)
    assert matched, "no profile skills matched a JD full of their synonyms"
    weights = []
    for skill in matched:
        hits = canonical_skills(skill) & set(signal)
        weights.append(max(signal[h] for h in hits))
    assert weights == sorted(weights, reverse=True)


def test_gaps_exclude_skills_evidenced_elsewhere_in_the_profile(signal):
    from engine.jd_analyzer import profile_corpus
    _, gaps_shallow = match_profile(["SQL"], signal)
    _, gaps_deep = match_profile(["SQL"], signal, profile_corpus(PROFILE))
    assert "theft investigation" in gaps_shallow
    assert "theft investigation" not in gaps_deep, "a skill proven in bullets was reported missing"


def test_periods_localise_without_inventing_precision():
    role = {"start": "03/2021", "end": "Present"}
    assert period(role, LABELS["international"]) == "03/2021 \u2013 Present"
    assert period(role, LABELS["german"]) == "03/2021 \u2013 heute"
    assert period({"start": "2021", "end": "2022"}, LABELS["german"]) == "2021 \u2013 2022"


def test_year_only_periods_are_reported_not_guessed():
    vague = missing_month_precision({"experience": [{"role": "R", "company": "C",
                                                     "start": "2021", "end": "2022"}]})
    assert len(vague) == 2
    assert not missing_month_precision({"experience": [{"start": "03/2021", "end": "Present"}]})


def test_unicode_font_is_available():
    fonts = register_fonts()
    assert fonts["regular"] != "Helvetica", (
        "fell back to Helvetica, which cannot embed a Unicode bullet")


@pytest.mark.parametrize("layout", ["international", "german"])
def test_generated_pdf_has_no_corrupted_glyphs(tmp_path, tailored, signal, layout):
    out = tmp_path / f"cv_{layout}.pdf"
    build_cv_pdf(tailored, str(out), layout=layout, fit_pages=1)
    report = audit_pdf(str(out), signal)

    assert report["checks"]["no_glyph_corruption"]["status"] == "pass", \
        report["checks"]["no_glyph_corruption"]["detail"]
    assert "(cid:" not in report["text"]
    assert "\u2022" in report["text"], "bullets vanished from the extracted text"


@pytest.mark.parametrize("layout", ["international", "german"])
def test_generated_pdf_passes_the_structural_ats_checks(tmp_path, tailored, signal, layout):
    out = tmp_path / f"cv_{layout}.pdf"
    build_cv_pdf(tailored, str(out), layout=layout, fit_pages=2)
    report = audit_pdf(str(out), signal)

    for name in ["text_extractable", "required_sections", "contact_email",
                 "date_ranges", "single_column", "no_tables", "page_count"]:
        assert report["checks"][name]["status"] == "pass", \
            f"{name}: {report['checks'][name]['detail']}"
    assert report["score"] >= 90, f"score dropped to {report['score']}"


def test_bullets_stay_attached_to_their_text(tmp_path, tailored, signal):
    """A bullet drawn as a separate text run becomes an orphan line in some
    parsers, which is why it is part of the paragraph text instead."""
    out = tmp_path / "cv.pdf"
    build_cv_pdf(tailored, str(out), fit_pages=2)
    text = audit_pdf(str(out), signal)["text"]
    for line in text.splitlines():
        assert line.strip() != "\u2022", "found a bullet on a line of its own"


def test_autofit_reaches_one_page(tmp_path, tailored):
    out = tmp_path / "cv.pdf"
    build_cv_pdf(tailored, str(out), layout="international", fit_pages=1)
    import pdfplumber
    with pdfplumber.open(str(out)) as pdf:
        assert len(pdf.pages) == 1


def test_german_layout_uses_german_headings_and_signature(tmp_path, tailored, signal):
    out = tmp_path / "cv.pdf"
    build_cv_pdf(tailored, str(out), layout="german", fit_pages=2)
    text = audit_pdf(str(out), signal)["text"]
    for heading in ["Lebenslauf", "Pers\u00f6nliche Daten", "Berufserfahrung",
                    "Ausbildung", "Kenntnisse", "Sprachen"]:
        assert heading in text, f"missing German heading: {heading}"
    assert "heute" in text, "a current role should read 'heute' in a German CV"
    assert PROFILE["name"] in text.split("Sprachen")[-1], "no signature block"


def test_german_umlauts_survive_extraction(tmp_path, tailored, signal):
    out = tmp_path / "cv.pdf"
    build_cv_pdf(tailored, str(out), layout="german", fit_pages=2)
    text = audit_pdf(str(out), signal)["text"]
    assert "Universit\u00e4t K\u00f6ln" in text


def test_docx_is_written_for_both_layouts(tmp_path, tailored):
    from docx import Document
    for layout in ("international", "german"):
        out = tmp_path / f"cv_{layout}.docx"
        build_cv_docx(tailored, str(out), layout=layout)
        paragraphs = [p.text for p in Document(str(out)).paragraphs]
        assert PROFILE["name"] in paragraphs
        assert any("Loss Prevention Manager" in p for p in paragraphs)


def test_audit_reports_zero_for_a_file_it_cannot_read(tmp_path):
    broken = tmp_path / "broken.pdf"
    broken.write_bytes(b"not a pdf at all")
    report = audit_pdf(str(broken))
    assert report["score"] == 0
    assert report["checks"]["text_extractable"]["status"] == "fail"
