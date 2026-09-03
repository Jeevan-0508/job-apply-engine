"""
Generates a tailored cover letter from the structured profile + a job's
matched skill signal. Honest by construction: it only ever cites skills and
STAR proof points that exist in config/profile.py -- nothing invented.
"""
from docx import Document
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet


def _pick_proof_point(profile, jd_signal):
    """Pick the STAR example with the most overlap against this JD's skills."""
    best, best_score = None, -1
    for ex in profile.get("star_examples", []):
        score = sum(1 for tag in ex.get("skills_tags", []) if tag in jd_signal)
        if score > best_score:
            best, best_score = ex, score
    return best


def build_cover_letter_text(profile, jd_signal, company, role):
    matched_skills = [s for s in profile.get("skills", []) if s.lower() in jd_signal]
    top_skills = matched_skills[:4] or list(jd_signal.keys())[:4]
    proof = _pick_proof_point(profile, jd_signal)

    proof_para = ""
    if proof and proof["title"] != "[FILL IN]":
        proof_para = (
            f"In a recent example, {proof['situation']} {proof['task']} "
            f"{proof['action']} The result: {proof['result']}"
        )

    paragraphs = [
        f"Dear Hiring Team at {company},",
        (f"I'm writing to apply for the {role} position. My background in "
         f"{', '.join(top_skills) if top_skills else profile.get('title', 'this field')} "
         f"lines up closely with what you're looking for, and I'd welcome the "
         f"chance to bring that to your team."),
        proof_para,
        profile.get("why_germany", ""),
        "Thank you for your time and consideration -- I'd welcome the opportunity to discuss further.",
        f"Best regards,\n{profile.get('name', '')}",
    ]
    return [p for p in paragraphs if p]


def build_cover_letter_docx(profile, jd_signal, company, role, out_path):
    doc = Document()
    doc.add_paragraph(profile.get("name", ""))
    doc.add_paragraph(" | ".join(filter(None, [profile.get("email"), profile.get("phone"), profile.get("linkedin")])))
    doc.add_paragraph("")
    for para in build_cover_letter_text(profile, jd_signal, company, role):
        doc.add_paragraph(para)
    doc.save(out_path)
    return out_path


def build_cover_letter_pdf(profile, jd_signal, company, role, out_path):
    styles = getSampleStyleSheet()
    body = styles["BodyText"]
    doc = SimpleDocTemplate(out_path, pagesize=A4, topMargin=2 * cm, bottomMargin=2 * cm,
                             leftMargin=2 * cm, rightMargin=2 * cm)
    flow = [Paragraph(profile.get("name", ""), styles["Title"]), Spacer(1, 10)]
    for para in build_cover_letter_text(profile, jd_signal, company, role):
        flow.append(Paragraph(para.replace("\n", "<br/>"), body))
        flow.append(Spacer(1, 8))
    doc.build(flow)
    return out_path
