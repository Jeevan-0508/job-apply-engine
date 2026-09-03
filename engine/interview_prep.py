"""
Builds an interview prep pack for a specific application: likely question
themes from the JD's weighted skills, matching STAR examples from the
profile, and a plain research checklist. Gaps are shown honestly, never
papered over with invented experience.
"""
from docx import Document


QUESTION_TEMPLATES = {
    3: "Tell me about a time you handled {skill} directly -- what was the situation and what did you do?",
    2: "How have you applied {skill} in a previous role?",
    1: "Where does {skill} show up in your day-to-day work?",
}


def _questions_for_skill(skill, weight):
    template = QUESTION_TEMPLATES.get(weight, QUESTION_TEMPLATES[1])
    return template.format(skill=skill)


def build_prep_notes(profile, jd_signal, company, role):
    matched_skills = [s for s in profile.get("skills", []) if s.lower() in jd_signal]
    gap_skills = [s for s in jd_signal if s not in [x.lower() for x in profile.get("skills", [])]]

    star_by_skill = {}
    for ex in profile.get("star_examples", []):
        for tag in ex.get("skills_tags", []):
            star_by_skill.setdefault(tag, ex)

    lines = [
        f"INTERVIEW PREP -- {role} at {company}",
        "=" * 60,
        "",
        "LIKELY QUESTION THEMES (from JD's weighted skills):",
    ]
    for skill, weight in sorted(jd_signal.items(), key=lambda x: -x[1]):
        lines.append(f"- {_questions_for_skill(skill, weight)}")
        star = star_by_skill.get(skill)
        if star and star["title"] != "[FILL IN]":
            lines.append(f"  -> Use STAR example: \"{star['title']}\"")
        else:
            lines.append("  -> No STAR example tagged for this yet -- add one to config/profile.py")
    lines.append("")

    lines.append("SKILLS YOU MATCH ON:")
    if matched_skills:
        lines.extend(f"- {s}" for s in matched_skills)
    else:
        lines.append("- (none detected -- check profile skills list)")
    lines.append("")

    if gap_skills:
        lines.append("HONEST GAPS -- the JD wants these and your profile doesn't show them.")
        lines.append("Don't invent experience; decide how you'll address these if asked:")
        lines.extend(f"- {s}" for s in gap_skills)
        lines.append("")

    lines.append("BEFORE THE INTERVIEW:")
    lines.append(f"- Research {company}: recent news, org structure, who you're meeting")
    lines.append("- Re-read the exact JD and the CV/cover letter you submitted for this application")
    lines.append("- Prepare 2-3 questions to ask them (about the role, the team, how success is measured)")

    return "\n".join(lines)


def save_prep_notes_txt(profile, jd_signal, company, role, out_path):
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(build_prep_notes(profile, jd_signal, company, role))
    return out_path


def save_prep_notes_docx(profile, jd_signal, company, role, out_path):
    doc = Document()
    for line in build_prep_notes(profile, jd_signal, company, role).split("\n"):
        doc.add_paragraph(line)
    doc.save(out_path)
    return out_path
