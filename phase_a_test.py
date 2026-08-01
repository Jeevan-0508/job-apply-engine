from engine.resume_parser import extract_resume_sections
from engine.jd_analyzer import analyze_jd
from engine.tailor import tailor_lines

RESUME = "resumes/Jeevan_Resume.pdf"

JD = """
Risk Manager role requiring ISO 27001, GDPR,
risk governance frameworks, SQL reporting,
audit controls and stakeholder management.
"""

resume = extract_resume_sections(RESUME)
jd_signal = analyze_jd(JD)

tailored = tailor_lines(resume["experience"], jd_signal)

print("\nJD SIGNALS:")
for k, v in jd_signal.items():
    print("-", k, "(weight", v, ")")

print("\nTOP TAILORED LINES:")
for line in tailored[:10]:
    print("-", line)
