"""
Builds a real tailored CV (not just a bullet dump) from the structured
profile in config/profile.py, reordered per-role against a specific JD's
weighted skill signal. Outputs both .docx and .pdf.

Falls back to a flat "top matched lines" mode if the profile hasn't been
filled in yet -- see build_from_flat_lines().
"""
from docx import Document
from docx.shared import Pt, RGBColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def _score_bullet(bullet, jd_signal):
    b = bullet.lower()
    return sum(weight for skill, weight in jd_signal.items() if skill in b)


def tailor_profile(profile, jd_signal, top_n_per_role=6):
    """Reorders bullets within each role by JD relevance. Never drops roles
    or fabricates content -- only reorders and trims to top_n per role."""
    tailored_experience = []
    for role in profile["experience"]:
        scored = sorted(
            role["bullets"],
            key=lambda b: _score_bullet(b, jd_signal),
            reverse=True,
        )
        tailored_experience.append({**role, "bullets": scored[:top_n_per_role]})

    matched_skills = [s for s in profile["skills"] if s.lower() in jd_signal]
    other_skills = [s for s in profile["skills"] if s.lower() not in jd_signal]
    gap_skills = [s for s in jd_signal if s not in [x.lower() for x in profile["skills"]]]

    return {
        **profile,
        "experience": tailored_experience,
        "skills": matched_skills + other_skills,  # matched ones surface first, nothing removed
        "gap_skills": gap_skills,  # shown in the app, never stuffed into the CV
    }


def build_cv_docx(tailored, out_path):
    doc = Document()

    name = doc.add_heading(tailored["name"], level=0)
    name.runs[0].font.color.rgb = RGBColor(0x1A, 0x1A, 0x1A)

    contact = doc.add_paragraph()
    contact.add_run(
        " | ".join(filter(None, [tailored.get("title"), tailored.get("email"),
                                  tailored.get("phone"), tailored.get("location"),
                                  tailored.get("linkedin")]))
    ).font.size = Pt(10)

    doc.add_heading("Summary", level=1)
    doc.add_paragraph(tailored.get("summary", ""))

    doc.add_heading("Core Skills", level=1)
    doc.add_paragraph(", ".join(tailored.get("skills", [])))

    doc.add_heading("Experience", level=1)
    for role in tailored.get("experience", []):
        p = doc.add_paragraph()
        p.add_run(f"{role['role']} — {role['company']}").bold = True
        p.add_run(f"  ({role.get('start','')} – {role.get('end','')}, {role.get('location','')})").italic = True
        for bullet in role.get("bullets", []):
            doc.add_paragraph(bullet, style="List Bullet")

    if tailored.get("education"):
        doc.add_heading("Education", level=1)
        for ed in tailored["education"]:
            doc.add_paragraph(f"{ed['degree']} — {ed['institution']} ({ed['year']})")

    if tailored.get("certifications"):
        doc.add_heading("Certifications", level=1)
        for c in tailored["certifications"]:
            doc.add_paragraph(c, style="List Bullet")

    if tailored.get("languages"):
        doc.add_heading("Languages", level=1)
        doc.add_paragraph(", ".join(f"{l['name']} ({l['level']})" for l in tailored["languages"]))

    doc.save(out_path)
    return out_path


def build_cv_pdf(tailored, out_path):
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], spaceAfter=6)
    body = styles["BodyText"]
    bullet_style = ParagraphStyle("Bullet", parent=body, leftIndent=14, bulletIndent=4)

    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.8 * cm, rightMargin=1.8 * cm)
    flow = [
        Paragraph(tailored["name"], styles["Title"]),
        Paragraph(" | ".join(filter(None, [tailored.get("title"), tailored.get("email"),
                                            tailored.get("phone"), tailored.get("location")])), body),
        Spacer(1, 10),
        Paragraph("Summary", h1),
        Paragraph(tailored.get("summary", ""), body),
        Paragraph("Core Skills", h1),
        Paragraph(", ".join(tailored.get("skills", [])), body),
        Paragraph("Experience", h1),
    ]
    for role in tailored.get("experience", []):
        flow.append(Paragraph(f"<b>{role['role']} — {role['company']}</b> "
                               f"<i>({role.get('start','')} – {role.get('end','')}, {role.get('location','')})</i>", body))
        for bullet in role.get("bullets", []):
            flow.append(Paragraph(f"• {bullet}", bullet_style))
        flow.append(Spacer(1, 6))

    if tailored.get("education"):
        flow.append(Paragraph("Education", h1))
        for ed in tailored["education"]:
            flow.append(Paragraph(f"{ed['degree']} — {ed['institution']} ({ed['year']})", body))

    if tailored.get("certifications"):
        flow.append(Paragraph("Certifications", h1))
        for c in tailored["certifications"]:
            flow.append(Paragraph(f"• {c}", bullet_style))

    if tailored.get("languages"):
        flow.append(Paragraph("Languages", h1))
        flow.append(Paragraph(", ".join(f"{l['name']} ({l['level']})" for l in tailored["languages"]), body))

    doc.build(flow)
    return out_path


def build_from_flat_lines(lines, out_path_docx, out_path_pdf, header="TAILORED RESUME - DRAFT"):
    """Fallback mode for when config/profile.py is still unfilled: takes the
    flat JD-ranked lines from engine/tailor.py and produces simple docx+pdf."""
    doc = Document()
    doc.add_heading(header, level=1)
    for line in lines:
        doc.add_paragraph(line, style="List Bullet")
    doc.save(out_path_docx)

    styles = getSampleStyleSheet()
    pdf = SimpleDocTemplate(out_path_pdf, pagesize=A4)
    flow = [Paragraph(header, styles["Heading1"])]
    for line in lines:
        flow.append(Paragraph(f"• {line}", styles["BodyText"]))
    pdf.build(flow)

    return out_path_docx, out_path_pdf
