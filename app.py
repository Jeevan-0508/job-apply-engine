"""
Job Apply Engine -- a local Streamlit app for running a job search end to end.

Tab 1: search German + LinkedIn jobs, fetch each full description, score the
       fit, and build a complete application package in one click.
Tab 2: paste a JD by hand -> tailored CV (docx + pdf) + an ATS report.
Tab 3: cover letter + interview prep for the same JD.
Tab 4: the pipeline -- every application, its status, and what has gone quiet.

Run: streamlit run app.py
"""
import os
import re
import tempfile

import streamlit as st

from config.loader import get_profile, profile_is_filled

PROFILE = get_profile()

from engine import tracker
from engine.ats_check import audit_pdf
from engine.cover_letter import build_cover_letter_docx, build_cover_letter_pdf
from engine.cv_builder import (build_cv_docx, build_cv_pdf, build_from_flat_lines,
                               missing_month_precision, tailor_profile)
from engine.interview_prep import save_prep_notes_docx, save_prep_notes_txt
from engine.jd_analyzer import analyze_jd
from engine.match import demand_report, score_job
from engine.package import build_package
from engine.resume_parser import extract_resume_sections
from engine.search.aggregator import search_all
from engine.search.deeplinks import build as build_deeplinks
from engine.search.job_detail import fetch_description
from engine.tailor import tailor_lines

st.set_page_config(page_title="Job Apply Engine", layout="wide")
st.title("\U0001F680 Job Apply Engine")

os.makedirs("data", exist_ok=True)
os.makedirs("applications", exist_ok=True)

BAND_ICON = {"strong": "\U0001F7E9", "good": "\U0001F7E8", "partial": "\U0001F7E7",
             "weak": "\U0001F7E5", "low signal": "\u2B1C", "unknown": "\u2B1C"}
ATS_ICON = {"pass": "\u2705", "warn": "\u26A0\uFE0F", "fail": "\u274C"}


def layout_controls(key_prefix):
    """CV format, target length and letter language -- shared by the tabs."""
    col1, col2, col3 = st.columns(3)
    with col1:
        layout_label = st.radio(
            "CV format", ["International (ATS-first)", "Deutsch (tabellarischer Lebenslauf)"],
            key=f"{key_prefix}_layout",
            help="The German layout adds a Persönliche Daten block, German section headings, "
                 "MM/YYYY periods and a place/date signature line. Both are single-column "
                 "with no tables, because parsers interleave columns into nonsense.",
        )
    layout = "german" if layout_label.startswith("Deutsch") else "international"
    with col2:
        fit_pages = st.selectbox(
            "Target length", [1, 2], index=1 if layout == "german" else 0,
            key=f"{key_prefix}_pages",
            format_func=lambda n: f"{n} page" + ("s" if n > 1 else ""),
            help="Content is never dropped to fit. The CV is re-rendered denser and "
                 "re-measured; the longer version is kept if it still will not fit.",
        )
    with col3:
        lang_label = st.radio(
            "Cover letter", ["English", "Deutsch (Anschreiben)"], key=f"{key_prefix}_lang",
            help="The German version uses the Anschreiben layout German recruiters look for. "
                 "Sentences drawn from your profile stay in the language you wrote them in.",
        )
    language = "de" if lang_label.startswith("Deutsch") else "en"
    return layout, fit_pages, language


def show_ats_report(report):
    st.markdown(f"**ATS check: {report['score']}/100**")
    st.caption(
        "Scored by reading the finished PDF back with a text parser, the way an applicant "
        f"tracking system does — not by inspecting the code that wrote it. "
        f"{report['pages']} page(s), {report['words']} words extracted."
    )
    st.progress(min(report["score"], 100) / 100)
    for name, check in report["checks"].items():
        st.markdown(f"{ATS_ICON.get(check['status'], '•')} **{name.replace('_', ' ')}** — {check['detail']}")


def offer_downloads(files, key):
    labels = [("cv_pdf", "CV .pdf"), ("cv_docx", "CV .docx"),
              ("letter_pdf", "Letter .pdf"), ("letter_docx", "Letter .docx"),
              ("prep_docx", "Prep .docx"), ("zip", "Everything .zip")]
    available = [(k, label) for k, label in labels if files.get(k)]
    for col, (fkey, label) in zip(st.columns(len(available)), available):
        with col:
            with open(files[fkey], "rb") as fh:
                st.download_button(label, fh, file_name=os.path.basename(files[fkey]),
                                   key=f"{key}_{fkey}", width='stretch')


tab1, tab2, tab3, tab4 = st.tabs([
    "\U0001F50E Find & Apply", "\U0001F4C4 Tailor CV",
    "\u2709\uFE0F Cover Letter + Prep", "\U0001F4CA Pipeline",
])

# ---------------------------------------------------------------------------
# TAB 1 -- search, score and build a full application in one click
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Search, rank by fit, and build the whole application")

    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("What (role/keywords)", value="Risk Manager")
    with col2:
        location = st.text_input(
            "Where (city or state — English names work, e.g. Bavaria or Munich. Blank = all of Germany)",
            value="Bayern",
        )

    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        sources = st.multiselect(
            "Sources", ["Arbeitsagentur", "LinkedIn"], default=["Arbeitsagentur", "LinkedIn"],
            help="Arbeitsagentur is Germany's official public jobs API — most stable. "
                 "LinkedIn is fetched a page at a time and rate-limits if pushed.",
        )
    with col2:
        per_source = st.number_input("Results per source", 5, 50, 15, step=5)
    with col3:
        deep = st.checkbox(
            "Fetch full descriptions", value=True,
            help="Reads each posting's full text so the fit score means something. "
                 "One request per job, so it is slower.",
        )

    if st.button("Search and rank", type="primary"):
        with st.spinner("Searching..."):
            result = search_all(query, location, enabled_sources=sources,
                                limit_per_source=int(per_source))
        for message in result["errors"]:
            st.warning(message)
        for message in result["notes"]:
            st.info(message)

        jobs = result["jobs"]
        known = tracker.known_ids()
        scored = []
        progress = st.progress(0.0, text="Scoring...")
        for index, job in enumerate(jobs, start=1):
            description = ""
            detail_error = None
            if deep:
                detail = fetch_description(job)
                description = detail["text"]
                detail_error = detail["error"]
            fit = score_job(job, PROFILE, description)
            scored.append({"job": job, "fit": fit, "description": description,
                           "detail_error": detail_error,
                           "seen_before": tracker.job_id(job) in known})
            progress.progress(index / max(len(jobs), 1),
                              text=f"Scoring {index}/{len(jobs)}: {job.get('title','')[:50]}")
        progress.empty()

        scored.sort(key=lambda row: (-row["fit"]["relevance"], -row["fit"]["coverage"]))
        st.session_state["scored"] = scored
        counts = " · ".join(f"{k} {v}" for k, v in result["per_source"].items())
        st.success(f"{len(jobs)} jobs" + (f" — {counts}" if counts else ""))

    scored = st.session_state.get("scored", [])

    if scored:
        layout, fit_pages, language = layout_controls("t1")

        fresh = [row for row in scored if not row["seen_before"]]
        st.caption(f"{len(fresh)} new since your last run · {len(scored) - len(fresh)} already in your pipeline")

        top = [row for row in scored if not row["seen_before"]][:3]
        if top and st.button(f"\u26A1 Build applications for the top {len(top)}", type="primary"):
            for row in top:
                if not row["description"]:
                    st.warning(f"Skipped {row['job'].get('title','')} — no description could be read.")
                    continue
                with st.spinner(f"Building {row['job'].get('company','')}..."):
                    outcome = build_package(row["job"], row["description"], PROFILE,
                                            layout=layout, fit_pages=fit_pages, language=language)
                st.success(f"{row['job'].get('company','')} — {outcome['folder']} "
                           f"(ATS {outcome['ats']['score'] if outcome['ats'] else 'n/a'}/100)")
            st.rerun()

        for index, row in enumerate(scored):
            job, fit = row["job"], row["fit"]
            icon = BAND_ICON.get(fit["band"], "\u2B1C")
            flag = "" if not row["seen_before"] else " · in pipeline"
            with st.expander(
                f"{icon} {fit['relevance']}% relevant · {fit['coverage']}% covered — "
                f"{job.get('title','')} · {job.get('company','')}{flag}"
            ):
                st.caption(f"{job.get('source','')} · {job.get('location','')} · "
                           f"{job.get('posted','')} · scored on {fit['basis']}")
                st.write(fit["verdict"])
                if fit["missing"]:
                    st.caption("Asked for, not evidenced in your profile: " + ", ".join(fit["missing"]))
                if row["detail_error"]:
                    st.caption(f"Description unavailable: {row['detail_error']}")

                buttons = st.columns(3)
                with buttons[0]:
                    if job.get("link"):
                        st.link_button("Open posting", job["link"], width='stretch')
                with buttons[1]:
                    if st.button("Shortlist", key=f"save_{index}", width='stretch'):
                        tracker.upsert(job, coverage=fit["coverage"], relevance=fit["relevance"])
                        st.toast(f"Shortlisted {job.get('company','')}")
                with buttons[2]:
                    disabled = not row["description"]
                    if st.button("\u26A1 Build application", key=f"build_{index}",
                                 type="primary", disabled=disabled, width='stretch'):
                        with st.spinner("Building CV, letter, prep pack and ATS report..."):
                            outcome = build_package(job, row["description"], PROFILE,
                                                    layout=layout, fit_pages=fit_pages,
                                                    language=language)
                        st.success(f"Written to {outcome['folder']}")
                        for message in outcome["errors"]:
                            st.warning(message)
                        offer_downloads(outcome["files"], f"dl_{index}")
                        if outcome["ats"]:
                            show_ats_report(outcome["ats"])

                if row["description"]:
                    with st.popover("Read the description"):
                        st.text(row["description"][:6000])

        rows = demand_report([row["fit"] for row in scored])
        if rows:
            with st.expander("\U0001F4C9 What this search keeps asking for that your profile cannot evidence"):
                st.caption(
                    "Aggregated across every posting scored above. This is the shortest path to a "
                    "higher score on every future application: these are the words the market uses "
                    "and your profile does not."
                )
                for entry in rows[:15]:
                    st.markdown(
                        f"**{entry['skill']}** — missing in {entry['postings_missing']} of "
                        f"{entry['postings_asking']} postings that ask for it"
                    )

    st.divider()
    st.caption("Sites that can't be read automatically — open them yourself:")
    for col, site in zip(st.columns(4), build_deeplinks(query, location)):
        with col:
            st.link_button(f"{site['name']} \u2197", site["url"], width='stretch')
            st.caption(site["why"])

# ---------------------------------------------------------------------------
# TAB 2 -- tailor a CV against a pasted JD
# ---------------------------------------------------------------------------
with tab2:
    st.subheader("Tailor your CV to a job description")

    if not profile_is_filled(PROFILE):
        st.info(
            "config/profile.py isn't filled in yet, so this runs in basic mode: "
            "it'll reorder bullets extracted from your uploaded resume PDF, but can't "
            "build a full structured CV. Fill in config/profile.py for the full version."
        )

    company = st.text_input("Company", key="cv_company")
    role = st.text_input("Role title", key="cv_role")
    layout, fit_pages, _ = layout_controls("t2")
    jd_text = st.text_area("Paste the job description", height=220, key="cv_jd")
    resume_pdf = st.file_uploader("Upload your resume (PDF) — used if profile.py isn't filled in",
                                  type=["pdf"])

    if st.button("Tailor CV", type="primary"):
        if not jd_text.strip():
            st.error("Paste a job description first.")
        else:
            jd_signal = analyze_jd(jd_text)
            safe = re.sub(r"[^a-zA-Z0-9_\- ]", "", company or "Company").replace(" ", "_")
            out_dir = f"applications/{safe}"
            os.makedirs(out_dir, exist_ok=True)

            if profile_is_filled(PROFILE):
                tailored = tailor_profile(PROFILE, jd_signal)
                docx_path = build_cv_docx(tailored, f"{out_dir}/CV_tailored.docx", layout=layout)
                pdf_path = build_cv_pdf(tailored, f"{out_dir}/CV_tailored.pdf",
                                        layout=layout, fit_pages=fit_pages)
                if tailored.get("gap_skills"):
                    st.warning("JD asks for skills not in your profile: "
                               + ", ".join(tailored["gap_skills"]))
                if layout == "german":
                    vague = missing_month_precision(PROFILE)
                    if vague:
                        st.info("German CVs are expected to give periods as MM/YYYY. These are "
                                "years only, so they're printed as-is rather than guessed: "
                                + "; ".join(vague))
            elif resume_pdf is not None:
                tmp_path = os.path.join(tempfile.gettempdir(), resume_pdf.name)
                with open(tmp_path, "wb") as fh:
                    fh.write(resume_pdf.getbuffer())
                resume = extract_resume_sections(tmp_path)
                tailored_lines = tailor_lines(resume["experience"], jd_signal)[:8]
                docx_path, pdf_path = build_from_flat_lines(
                    tailored_lines, f"{out_dir}/CV_tailored.docx", f"{out_dir}/CV_tailored.pdf")
            else:
                st.error("Fill config/profile.py or upload a resume PDF.")
                docx_path = pdf_path = None

            if docx_path:
                st.success("Tailored CV ready.")
                offer_downloads({"cv_docx": docx_path, "cv_pdf": pdf_path}, "t2")
                with st.expander("Matched skills for this JD"):
                    st.write(", ".join(jd_signal.keys()) or "No skill_map.py matches found in this JD.")
                st.divider()
                show_ats_report(audit_pdf(pdf_path, jd_signal))
                st.session_state["last_jd_signal"] = jd_signal
                st.session_state["last_company"] = company
                st.session_state["last_role"] = role

# ---------------------------------------------------------------------------
# TAB 3 -- cover letter + interview prep
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Cover letter + interview prep for the same application")

    if not profile_is_filled(PROFILE):
        st.info("Fill in config/profile.py (especially why_germany and star_examples) "
                "for a real cover letter and prep pack.")

    # Seed from Tab 2 before the widgets exist -- a text_input's `value=` is only
    # applied on first render, so tailoring a CV afterwards would never reach these
    # and the cover letter would land in applications/Company instead.
    for source, widget in (("last_company", "cl_company"), ("last_role", "cl_role")):
        if not st.session_state.get(widget) and st.session_state.get(source):
            st.session_state[widget] = st.session_state[source]

    company3 = st.text_input("Company", key="cl_company")
    role3 = st.text_input("Role title", key="cl_role")
    letter_lang = st.radio("Language", ["English", "Deutsch (Anschreiben)"],
                           horizontal=True, key="t3_lang")
    language3 = "de" if letter_lang.startswith("Deutsch") else "en"
    jd_signal = st.session_state.get("last_jd_signal")

    if jd_signal is None:
        st.warning("Tailor a CV in Tab 2 first (or paste a JD below) so there's a skill signal "
                   "to work from.")
        jd_text3 = st.text_area("Or paste a JD here directly", height=150, key="cl_jd")
        if jd_text3.strip():
            jd_signal = analyze_jd(jd_text3)

    if st.button("Generate cover letter + interview prep", type="primary") and jd_signal is not None:
        safe = re.sub(r"[^a-zA-Z0-9_\- ]", "", company3 or "Company").replace(" ", "_")
        out_dir = f"applications/{safe}"
        os.makedirs(out_dir, exist_ok=True)

        letter_docx = build_cover_letter_docx(PROFILE, jd_signal, company3, role3,
                                              f"{out_dir}/CoverLetter.docx", language=language3)
        letter_pdf = build_cover_letter_pdf(PROFILE, jd_signal, company3, role3,
                                            f"{out_dir}/CoverLetter.pdf", language=language3)
        prep_txt = save_prep_notes_txt(PROFILE, jd_signal, company3, role3,
                                       f"{out_dir}/InterviewPrep.txt")
        prep_docx = save_prep_notes_docx(PROFILE, jd_signal, company3, role3,
                                         f"{out_dir}/InterviewPrep.docx")

        st.success("Cover letter and interview prep ready.")
        if language3 == "de":
            st.info("The Anschreiben layout and wording are German. Sentences taken from your "
                    "profile — the STAR example and the motivation paragraph — are inserted as "
                    "written, so have those checked by a native speaker before sending.")
        offer_downloads({"letter_docx": letter_docx, "letter_pdf": letter_pdf,
                         "prep_docx": prep_docx}, "t3")
        with open(prep_txt, encoding="utf-8") as fh:
            st.text_area("Interview prep preview", fh.read(), height=300)

# ---------------------------------------------------------------------------
# TAB 4 -- the pipeline
# ---------------------------------------------------------------------------
with tab4:
    st.subheader("Your pipeline")
    entries = tracker.load()

    if not entries:
        st.info("Nothing here yet. Shortlist or build an application in the first tab and it "
                "will appear, with everything generated for it recorded alongside.")
    else:
        stats = tracker.metrics(entries)
        row = st.columns(5)
        row[0].metric("Total", stats["total"], f"+{stats['added_this_week']} this week")
        row[1].metric("Open", stats["open"])
        row[2].metric("Applied", stats["applied"])
        row[3].metric("Response rate",
                      f"{stats['response_rate']:.0%}" if stats["response_rate"] is not None else "—")
        row[4].metric("Avg ATS",
                      f"{stats['avg_ats']:.0f}/100" if stats["avg_ats"] is not None else "—")

        if stats["stale"]:
            st.warning(f"{len(stats['stale'])} application(s) sent and gone quiet for "
                       f"{tracker.STALE_AFTER_DAYS}+ days:")
            for entry in stats["stale"]:
                st.markdown(f"- **{entry['company']}** — {entry['title']} "
                            f"({entry['days_quiet']} days) — worth a follow-up")

        st.dataframe(
            [{"Company": e.get("company"), "Role": e.get("title"),
              "Status": e.get("status"), "Relevance": e.get("relevance"),
              "Coverage": e.get("coverage"), "ATS": e.get("ats_score"),
              "Source": e.get("source"), "Added": (e.get("created") or "")[:10]}
             for e in sorted(entries, key=lambda e: e.get("created", ""), reverse=True)],
            width='stretch', hide_index=True,
        )

        st.download_button("Export pipeline as CSV", tracker.to_csv(entries),
                           file_name="pipeline.csv", mime="text/csv")

        st.divider()
        st.caption("Update a status as things move:")
        for index, entry in enumerate(sorted(entries, key=lambda e: e.get("updated", ""), reverse=True)):
            with st.expander(f"{entry.get('status')} — {entry.get('company')} · {entry.get('title')}"):
                if entry.get("link"):
                    st.link_button("Open posting", entry["link"])
                if entry.get("folder") and os.path.isdir(entry["folder"]):
                    st.caption(f"Files: {entry['folder']}")
                    zip_path = os.path.join(entry["folder"], "application.zip")
                    if os.path.exists(zip_path):
                        with open(zip_path, "rb") as fh:
                            st.download_button("Download package", fh, file_name="application.zip",
                                               key=f"pipe_zip_{index}")
                status = st.selectbox("Status", tracker.STATUSES,
                                      index=tracker.STATUSES.index(entry.get("status", "Shortlisted"))
                                      if entry.get("status") in tracker.STATUSES else 0,
                                      key=f"status_{index}")
                notes = st.text_area("Notes", value=entry.get("notes", ""), key=f"notes_{index}",
                                     height=80)
                if st.button("Save", key=f"save_pipe_{index}"):
                    tracker.set_status(entry["id"], status, notes=notes)
                    st.toast("Updated")
                    st.rerun()

        by_source = stats["by_source"]
        if len(by_source) > 1:
            with st.expander("Which source actually converts"):
                for name, bucket in sorted(by_source.items(), key=lambda kv: -kv[1]["total"]):
                    rate = (bucket["answered"] / bucket["applied"]) if bucket["applied"] else None
                    st.markdown(f"**{name}** — {bucket['total']} tracked, {bucket['applied']} applied, "
                                f"{bucket['answered']} answered"
                                + (f" ({rate:.0%})" if rate is not None else ""))
