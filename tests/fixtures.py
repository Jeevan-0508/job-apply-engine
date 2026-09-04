"""Shared synthetic fixture data for the test suite.

Synthetic on purpose -- no real personal data belongs in the repository.
Both the CV/ATS tests and the pipeline tests score against this profile, so
it lives in one place and a change to it is visible in every assertion.
"""

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
