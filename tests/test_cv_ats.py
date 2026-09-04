"""
Regression tests for CV generation and the ATS audit.

These exist because of a real defect: bullets were rendered in reportlab's
built-in Helvetica, which has no Unicode map for U+2022, so every bullet in
every generated PDF extracted as "(cid:127)" and corrupted the line it sat on.
The CV looked perfect on screen and was damaged in every parser that read it.
Anything that could reintroduce that must fail here.

The fixture is synthetic on purpose -- no real personal data in the repo.
"""
import pytest

from engine.ats_check import audit_pdf
from engine.cv_builder import (LABELS, build_cv_docx, build_cv_pdf, period,
                               missing_month_precision, register_fonts,
                               tailor_profile)
from engine.jd_analyzer import analyze_jd, canonical_skills, match_profile

PROFILE = {
    "name": "Alex Muster",
    "title": "Risk Manager | Loss Prevention | Supply Chain Security",
    "email": "alex.muster@example.com",
    "phone": "+49 151 23456789",
    "location": "Munich, Germany",
    "linkedin": "linkedin.com/in/example",
    "summary": (
        "Risk manager with eight years in supply chain security and loss prevention "
        "across European distribution networks. Led theft investigations, rebuilt "
        "audit controls and cut shrinkage through data-driven root cause analysis. "
        "Certified Lean Six Sigma Black Belt with a record of measurable reduction "
        "in inventory loss and false positive escalations."
    ),
    "skills": [
        "Loss Prevention", "Physical Security", "Theft Investigation",
        "Audit Frameworks", "SQL", "Power BI", "Excel (VBA, Pivot)",
        "RCA", "Stakeholder Management", "GDPR",
    ],
    "experience": [
        {
            "company": "Beispiel Logistik GmbH",
            "role": "Loss Prevention Manager",
            "location": "Munich, Germany",
            "start": "03/2021",
            "end": "Present",
            "bullets": [
                "Led theft investigations across six distribution centres, recovering EUR 1.2M in losses.",
                "Cut inventory shrinkage by 34% through root cause analysis of audit exceptions.",
                "Rebuilt the guard force vendor programme, reducing cost per site by 18%.",
                "Built Power BI dashboards giving regional managers weekly shrinkage visibility.",
                "Reduced false positive escalations by 40% by redesigning audit thresholds.",
                "Wrote the standard operating procedures adopted across the German network.",
            ],
        },
        {
            "company": "Muster Handel AG",
            "role": "Risk Analyst",
            "location": "Cologne, Germany",
            "start": "09/2017",
            "end": "02/2021",
            "bullets": [
                "Analysed 90K monthly audit events to surface repeat fraud patterns.",
                "Designed a risk scoring model improving case prioritisation accuracy by 30%.",
                "Automated weekly reporting in SQL and Excel, saving twelve hours a week.",
            ],
        },
    ],
    "education": [
        {"degree": "B.Sc. Business Administration", "institution": "Universität Köln", "year": "2017"},
    ],
    "certifications": [
        "Lean Six Sigma Black Belt",
        "ISO 28000: Supply Chain Security",
        "Certified Fraud Examiner",
    ],
    "languages": [
        {"name": "German", "level": "C1"},
        {"name": "English", "level": "Fluent"},
    ],
    "star_examples": [],
}

JD = """
Loss Prevention Specialist (m/f/d) Munich. You will lead internal and external
theft investigations, conduct root cause analysis on inventory shrinkage, manage
third-party guard force vendors and deliver data-driven risk assessments.
Requires strong data analysis (Excel, SQL), dashboards, incident management,
GDPR awareness, CCTV and access control experience, and Six Sigma.
"""


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
