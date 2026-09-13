"""
Turns one job posting into a complete, ready-to-send application in a single
call: tailored CV, cover letter, interview prep, an ATS report and a zip,
written into one folder per application and recorded in the pipeline.

This is the point of the app. Everything else -- searching, scoring, tailoring
-- was already possible one manual step at a time; the cost was that each
application took a dozen interactions and produced files scattered across two
folders. Here the description is fetched, analysed, and every artefact is
generated and verified in one pass, so applying is one click and the result is
auditable afterwards.
"""
import json
import os
import re
import zipfile

from engine import tracker
from engine.ats_check import audit_pdf
from engine.integrity import check_integrity
from engine.cover_letter import (build_cover_letter_docx, build_cover_letter_pdf)
from engine.cv_builder import build_cv_docx, build_cv_pdf, tailor_profile
from engine.interview_prep import save_prep_notes_docx, save_prep_notes_txt
from engine.match import score_text
from engine.cv_redteam import red_team_cv


def safe_name(value, fallback="Unknown"):
    cleaned = re.sub(r"[^\w\s-]", "", value or "", flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned)
    return cleaned[:60] or fallback


def folder_for(job, base_dir="applications"):
    return os.path.join(base_dir,
                        f"{safe_name(job.get('company'), 'Company')}__{safe_name(job.get('title'), 'Role')}")


def build_package(job, jd_text, profile, base_dir="applications",
                  layout="international", fit_pages=1, language="en",
                  pipeline_path=tracker.STORE):
    """Generate every artefact for one application and record it.

    Returns a dict of paths plus the scores. Individual artefacts fail
    independently: a cover letter that cannot be built must not cost you the
    CV, so failures are collected and reported rather than raised.
    """
    out_dir = folder_for(job, base_dir)
    os.makedirs(out_dir, exist_ok=True)

    company = job.get("company") or "the company"
    role = job.get("title") or "the role"

    fit = score_text(jd_text, profile, title=role)
    tailored = tailor_profile(profile, fit["signal"])
    red_team = red_team_cv(tailored)

    files = {}
    errors = []

    def attempt(name, fn):
        try:
            files[name] = fn()
        except Exception as e:
            errors.append(f"{name}: {type(e).__name__}: {e}")

    attempt("cv_docx", lambda: build_cv_docx(
        tailored, os.path.join(out_dir, "CV.docx"), layout=layout))
    attempt("cv_pdf", lambda: build_cv_pdf(
        tailored, os.path.join(out_dir, "CV.pdf"), layout=layout, fit_pages=fit_pages))
    attempt("letter_docx", lambda: build_cover_letter_docx(
        profile, fit["signal"], company, role,
        os.path.join(out_dir, "CoverLetter.docx"), language=language))
    attempt("letter_pdf", lambda: build_cover_letter_pdf(
        profile, fit["signal"], company, role,
        os.path.join(out_dir, "CoverLetter.pdf"), language=language))
    attempt("prep_txt", lambda: save_prep_notes_txt(
        profile, fit["signal"], company, role, os.path.join(out_dir, "InterviewPrep.txt")))
    attempt("prep_docx", lambda: save_prep_notes_docx(
        profile, fit["signal"], company, role, os.path.join(out_dir, "InterviewPrep.docx")))

    report = audit_pdf(files["cv_pdf"], fit["signal"]) if files.get("cv_pdf") else None

    integrity = None
    if files.get("cv_pdf"):
        try:
            integrity = check_integrity(files["cv_pdf"], tailored, profile, jd_signal=fit["signal"])
        except Exception as e:
            errors.append(f"integrity: {type(e).__name__}: {e}")

    posting_path = os.path.join(out_dir, "posting.txt")
    with open(posting_path, "w", encoding="utf-8") as f:
        f.write(f"{role}\n{company}\n{job.get('location','')}\n{job.get('link','')}\n\n{jd_text}")
    files["posting"] = posting_path

    meta = {
        "job": job,
        "coverage": fit["coverage"],
        "relevance": fit["relevance"],
        "band": fit["band"],
        "verdict": fit["verdict"],
        "matched_skills": fit["matched"],
        "missing_skills": fit["missing"],
        "core_missing": fit["core_missing"],
        "ats_score": report["score"] if report else None,
        "integrity_score": integrity["score"] if integrity else None,
        "integrity_blocked": integrity["blocked"] if integrity else None,
        "integrity_unsupported": integrity["unsupported"] if integrity else [],
        "red_team_score": red_team["score"],
        "red_team_band": red_team["band"],
        "cv_layout": layout,
        "letter_language": language,
        "errors": errors,
    }
    meta_path = os.path.join(out_dir, "application.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    files["meta"] = meta_path

    if report:
        lines = [f"ATS check: {report['score']}/100",
                 f"{report['pages']} page(s), {report['words']} words extracted", ""]
        for name, check in report["checks"].items():
            lines.append(f"[{check['status'].upper():4}] {name.replace('_', ' ')}: {check['detail']}")
        ats_path = os.path.join(out_dir, "ATS_report.txt")
        with open(ats_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        files["ats_report"] = ats_path

    if integrity:
        lines = [f"CV Integrity: {integrity['score']}/100", ""]
        for name, check in integrity["checks"].items():
            icon = "PASS" if check["status"] == "pass" else "FAIL"
            lines.append(f"[{icon}] {name.replace('_', ' ')}: {check['detail']}")
        if integrity["unsupported"]:
            lines += ["", "Unsupported claims (blocks export):"]
            lines += [f"  - {u}" for u in integrity["unsupported"]]
        integrity_path = os.path.join(out_dir, "Integrity_report.txt")
        with open(integrity_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        files["integrity_report"] = integrity_path

    # A CV with an unsupported claim must not go out the door -- the zip is
    # the "ready to send" bundle, so it is the thing withheld. The CV/DOCX
    # themselves are kept on disk (never discarded) so the report is
    # reproducible and the candidate can see exactly what to fix.
    zip_path = os.path.join(out_dir, "application.zip")
    send = [files.get(k) for k in ("cv_pdf", "cv_docx", "letter_pdf", "letter_docx")]
    if integrity and integrity["blocked"]:
        errors.append("zip: withheld -- CV Integrity check found an unsupported claim, see Integrity_report.txt")
    else:
        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for path in filter(None, send):
                    zf.write(path, os.path.basename(path))
            files["zip"] = zip_path
        except Exception as e:
            errors.append(f"zip: {type(e).__name__}: {e}")

    tracker.upsert(job, path=pipeline_path, status="Package built", folder=out_dir,
                   coverage=fit["coverage"], relevance=fit["relevance"],
                   ats_score=report["score"] if report else None,
                   jd_chars=len(jd_text or ""))

    red_team_lines = [f"CV Red Team: {red_team['score']}/100 ({red_team['band']})",
                      f"{red_team['flagged_bullets']} of {red_team['total_bullets']} bullet(s) flagged", ""]
    for f in red_team["findings"]:
        where = f["where"]
        if f["bullet"]:
            snippet = f["bullet"][:80]
            red_team_lines.append(f"[{where}] {snippet!r}")
        else:
            red_team_lines.append(f"[{where}]")
        red_team_lines += [f"    - {i}" for i in f["issues"]]
    red_team_path = os.path.join(out_dir, "RedTeam_report.txt")
    with open(red_team_path, "w", encoding="utf-8") as f:
        f.write("\n".join(red_team_lines))
    files["red_team_report"] = red_team_path

    return {"folder": out_dir, "files": files, "fit": fit,
            "ats": report, "integrity": integrity, "red_team": red_team,
            "errors": errors, "meta": meta}
