"""
Job Apply Engine -- 3-tab local Streamlit app.
Tab 1: search German + LinkedIn jobs by query/location.
Tab 2: paste a JD + your resume -> tailored CV (docx + pdf).
Tab 3: cover letter + interview prep for the same JD.

Run: streamlit run app.py
"""
import os
import re
import tempfile
import streamlit as st

from config.loader import get_profile, profile_is_filled

PROFILE = get_profile()
from engine.search.aggregator import search_all
from engine.search.deeplinks import build as build_deeplinks
from engine.jd_analyzer import analyze_jd
from engine.resume_parser import extract_resume_sections
from engine.tailor import tailor_lines
from engine.cv_builder import tailor_profile, build_cv_docx, build_cv_pdf, build_from_flat_lines
from engine.cover_letter import build_cover_letter_docx, build_cover_letter_pdf
from engine.interview_prep import save_prep_notes_txt, save_prep_notes_docx

st.set_page_config(page_title="Job Apply Engine", layout="wide")
st.title("🚀 Job Apply Engine")

os.makedirs("data", exist_ok=True)
os.makedirs("applications", exist_ok=True)

tab1, tab2, tab3 = st.tabs(["🔎 Search Jobs", "📄 Tailor CV", "✉️ Cover Letter + Interview Prep"])

# ---------------------------------------------------------------------------
# TAB 1 -- Job search across Arbeitsagentur + LinkedIn, plus deep links
# ---------------------------------------------------------------------------
with tab1:
    st.subheader("Search German jobs across multiple sources")
    col1, col2 = st.columns(2)
    with col1:
        query = st.text_input("What (role/keywords)", value="Risk Manager")
    with col2:
        location = st.text_input(
            "Where (city or state -- English names work, e.g. Bavaria or Munich. Blank = all of Germany)",
            value="Bayern",
        )

    sources = st.multiselect(
        "Sources",
        ["Arbeitsagentur", "LinkedIn"],
        default=["Arbeitsagentur", "LinkedIn"],
        help="Arbeitsagentur is Germany's official public jobs API -- most stable. "
             "LinkedIn is fetched a page at a time and rate-limits if pushed.",
    )

    run_search = st.button("Search", type="primary")

    if run_search:
        with st.spinner("Searching..."):
            result = search_all(query, location, enabled_sources=sources)

        for e in result["errors"]:
            st.warning(e)
        for n in result["notes"]:
            st.info(n)

        jobs = result["jobs"]
        counts = " · ".join(f"{k} {v}" for k, v in result["per_source"].items())
        st.success(f"Found {len(jobs)} jobs" + (f" — {counts}" if counts else ""))
        st.session_state["last_search_results"] = jobs

    st.caption("Sites that can't be read automatically -- open them yourself:")
    link_cols = st.columns(4)
    for col, site in zip(link_cols, build_deeplinks(query, location)):
        with col:
            st.link_button(f"{site['name']} ↗", site["url"], use_container_width=True)
            st.caption(site["why"])

    jobs = st.session_state.get("last_search_results", [])
    for job in jobs:
        with st.container(border=True):
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f"**{job['title']}** — {job['company']}")
                st.caption(f"{job['source']} · {job['location']} · {job.get('posted','')}")
                if job.get("snippet"):
                    st.write(job["snippet"])
            with c2:
                if job.get("link"):
                    st.link_button("Open posting", job["link"])

# ---------------------------------------------------------------------------
# TAB 2 -- Tailor CV from a pasted JD
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
    jd_text = st.text_area("Paste the job description", height=220, key="cv_jd")
    resume_pdf = st.file_uploader("Upload your resume (PDF) -- used if profile.py isn't filled in", type=["pdf"])

    if st.button("Tailor CV", type="primary"):
        if not jd_text.strip():
            st.error("Paste a job description first.")
        else:
            jd_signal = analyze_jd(jd_text)
            safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", company or "Company").replace(" ", "_")
            out_dir = f"applications/{safe_name}"
            os.makedirs(out_dir, exist_ok=True)

            if profile_is_filled(PROFILE):
                tailored = tailor_profile(PROFILE, jd_signal)
                docx_path = build_cv_docx(tailored, f"{out_dir}/CV_tailored.docx")
                pdf_path = build_cv_pdf(tailored, f"{out_dir}/CV_tailored.pdf")
                if tailored.get("gap_skills"):
                    st.warning(f"JD asks for skills not in your profile: {', '.join(tailored['gap_skills'])}")
            elif resume_pdf is not None:
                tmp_path = os.path.join(tempfile.gettempdir(), resume_pdf.name)
                with open(tmp_path, "wb") as f:
                    f.write(resume_pdf.getbuffer())
                resume = extract_resume_sections(tmp_path)
                tailored_lines = tailor_lines(resume["experience"], jd_signal)[:8]
                docx_path, pdf_path = build_from_flat_lines(
                    tailored_lines, f"{out_dir}/CV_tailored.docx", f"{out_dir}/CV_tailored.pdf"
                )
            else:
                st.error("Fill config/profile.py or upload a resume PDF.")
                docx_path = pdf_path = None

            if docx_path:
                st.success("Tailored CV ready.")
                c1, c2 = st.columns(2)
                with c1:
                    with open(docx_path, "rb") as f:
                        st.download_button("Download .docx", f, file_name="CV_tailored.docx")
                with c2:
                    with open(pdf_path, "rb") as f:
                        st.download_button("Download .pdf", f, file_name="CV_tailored.pdf")

                with st.expander("Matched skills for this JD"):
                    st.write(", ".join(jd_signal.keys()) or "No skill_map.py matches found in this JD.")
                st.session_state["last_jd_signal"] = jd_signal
                st.session_state["last_company"] = company
                st.session_state["last_role"] = role

# ---------------------------------------------------------------------------
# TAB 3 -- Cover letter + interview prep
# ---------------------------------------------------------------------------
with tab3:
    st.subheader("Cover letter + interview prep for the same application")

    if not profile_is_filled(PROFILE):
        st.info("Fill in config/profile.py (especially why_germany and star_examples) for a real cover letter and prep pack.")

    company3 = st.text_input("Company", value=st.session_state.get("last_company", ""), key="cl_company")
    role3 = st.text_input("Role title", value=st.session_state.get("last_role", ""), key="cl_role")
    jd_signal = st.session_state.get("last_jd_signal")

    if jd_signal is None:
        st.warning("Tailor a CV in Tab 2 first (or paste a JD below) so there's a skill signal to work from.")
        jd_text3 = st.text_area("Or paste a JD here directly", height=150, key="cl_jd")
        if jd_text3.strip():
            jd_signal = analyze_jd(jd_text3)

    if st.button("Generate cover letter + interview prep", type="primary") and jd_signal is not None:
        safe_name = re.sub(r"[^a-zA-Z0-9_\- ]", "", company3 or "Company").replace(" ", "_")
        out_dir = f"applications/{safe_name}"
        os.makedirs(out_dir, exist_ok=True)

        cl_docx = build_cover_letter_docx(PROFILE, jd_signal, company3, role3, f"{out_dir}/CoverLetter.docx")
        cl_pdf = build_cover_letter_pdf(PROFILE, jd_signal, company3, role3, f"{out_dir}/CoverLetter.pdf")
        prep_txt = save_prep_notes_txt(PROFILE, jd_signal, company3, role3, f"{out_dir}/InterviewPrep.txt")
        prep_docx = save_prep_notes_docx(PROFILE, jd_signal, company3, role3, f"{out_dir}/InterviewPrep.docx")

        st.success("Cover letter and interview prep ready.")
        c1, c2, c3 = st.columns(3)
        with c1:
            with open(cl_docx, "rb") as f:
                st.download_button("Cover letter .docx", f, file_name="CoverLetter.docx")
        with c2:
            with open(cl_pdf, "rb") as f:
                st.download_button("Cover letter .pdf", f, file_name="CoverLetter.pdf")
        with c3:
            with open(prep_docx, "rb") as f:
                st.download_button("Interview prep .docx", f, file_name="InterviewPrep.docx")

        with open(prep_txt, encoding="utf-8") as f:
            st.text_area("Interview prep preview", f.read(), height=300)
