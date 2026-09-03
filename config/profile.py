"""
Real profile data -- local only, never pushed (see .gitignore).
Source: Jeevan_Resume. Main.pdf (Downloads), read 2026-09-04.

TO CONFIRM:
- visa: set to "in hand" per prior conversation, PDF said "sponsorship
  required" -- update why_germany below if that's changed back.
- german level: PDF says A2 (B2-progressing); an earlier German CV used B2.
  Using A2/B2-progressing here since this resume is the source of truth --
  correct if that's out of date.
"""

PROFILE = {
    "name": "Jeevan Siddhabhaktula",
    "title": "Risk Manager — Amazon | Risk Management, Supply Chain, Fraud Detection, Operational Excellence",
    "email": "jeevansiddhabhaktula@gmail.com",
    "phone": "+91-9398423434",
    "location": "Hyderabad, India",
    "linkedin": "linkedin.com/in/jeevansiddhabhaktula",
    "github": "github.com/Jeevan-0508",

    "summary": (
        "Risk Manager (Amazon) specializing in fraud detection, predictive analytics, "
        "and supply-chain risk controls across EU & NA. Lean Six Sigma Black Belt with "
        ">$15M model-based prevention impact. Proven ability to reduce false positives "
        "by 40%, automate reporting workflows, and build forecasting models that "
        "strengthen operational governance."
    ),

    "skills": [
        "Operational Risk Management", "Risk Governance", "GDPR", "GRC",
        "Audit Frameworks", "SQL", "Power BI", "Excel (VBA, Pivot)",
        "Forecasting Models", "Data Analysis", "SOP Design", "RCA",
        "Dashboard Automation", "Stakeholder Management", "Program Management",
    ],

    "experience": [
        {
            "company": "Amazon",
            "role": "Risk Manager",
            "location": "Hyderabad, India",
            "start": "2022",
            "end": "Present",
            "bullets": [
                "Delivered >$15M model-based prevention impact through high-risk pattern analysis and control reinforcement.",
                "Reduced NA/EU audit false positives by ~40% via audit-logic redesign and exclusion rule optimization.",
                "Investigated complex risk anomalies using behavioral deviation and pattern-analysis models; closed recurring vulnerabilities via multi-layer validation.",
                "Developed forecasting engine (~95% accuracy) to predict and plan for peak-risk periods.",
                "Automated WBR/MBR/QBR reporting workflows, reducing manual effort by ~90% (~10-12 hours/week).",
                "Created RCMT Wiki, SOPs, PKTs, and standardized audit templates adopted across 20+ associates.",
            ],
        },
        {
            "company": "Amazon",
            "role": "Data Analyst (Risk)",
            "location": "Hyderabad, India",
            "start": "2021",
            "end": "2022",
            "bullets": [
                "Analyzed 80K+ monthly audit events to identify multi-layer risk trends, reducing escalation frequency by ~18%.",
                "Designed risk-scoring models improving prioritization accuracy by 30% and reducing false positives by 25%.",
                "Enhanced data pipelines, improving quality by ~20% and processing speed by ~35%.",
                "Automated weekly reporting using SQL+Excel, reducing manual effort by ~70% and speeding decision cycles.",
            ],
        },
    ],

    "education": [
        {"degree": "B.Tech — Electronics & Communications Engineering", "institution": "Andhra University, India", "year": "2021"},
    ],

    "certifications": [
        "Lean Six Sigma Black Belt — Kennesaw University",
        "AWS Certified Solutions Architect",
        "Lean Six Sigma Green Belt",
        "ISO 9001: Internal Auditor",
        "ISO 28000: Supply Chain Security",
        "Power BI / Data Analytics Certification",
        "Cybersecurity Foundations — University of London",
        "Risk Management Certificate — Jack Welch University",
    ],

    "languages": [
        {"name": "English", "level": "Fluent"},
        {"name": "Telugu", "level": "Native"},
        {"name": "Hindi", "level": "Fluent"},
        {"name": "German", "level": "A2 (B2-progressing)"},
    ],

    "why_germany": (
        "I'm targeting Risk/LP Specialist roles in Germany, with a valid German work visa "
        "already in hand. My background is hands-on risk operations at Amazon scale -- fraud "
        "detection, audit design, and forecasting that's driven >$15M in measurable prevention "
        "impact -- and I'm looking to bring that operational rigor to a market where I can also "
        "grow into German fluency long-term."
    ),

    "star_examples": [
        {
            "title": "Risk Forecasting & MO Prediction (LSSBB)",
            "situation": "Amazon's risk operations team lacked a way to proactively staff for high-risk periods, relying on reactive escalations after incidents already occurred.",
            "task": "I needed to build a forecasting model that could predict risk-heavy periods ahead of time using historical audit data.",
            "action": "Developed a forecasting engine using 12+ months of audit data, reaching ~95% prediction accuracy, and used it to drive proactive staffing decisions.",
            "result": "Enabled proactive staffing, fewer reactive escalations, and contributed to >$15M in prevention impact.",
            "skills_tags": ["risk management", "forecasting", "data analysis", "risk governance"],
        },
        {
            "title": "WBR/MBR Dashboard Automation (EU + NA)",
            "situation": "Weekly/monthly risk reporting across EU and NA regions was manual, slow, and gave leadership inconsistent visibility.",
            "task": "I needed to unify multi-region reporting into one automated, real-time view.",
            "action": "Built BI dashboards that automated the WBR/MBR reporting pipeline across both regions.",
            "result": "Cut reporting time by 90% and materially improved leadership visibility into risk trends.",
            "skills_tags": ["power bi", "dashboard automation", "program management", "stakeholder management"],
        },
        {
            "title": "Risk Signal Detection Framework (RSD)",
            "situation": "Existing audit processes were missing early warning signs of emerging risk patterns until they became active incidents.",
            "task": "I set out to build a system that tracked anomalies and behavioral patterns before they escalated.",
            "action": "Built an anomaly-tracking and behavioral-mapping system layered on top of existing audit data.",
            "result": "+28% early-warning detection, -15% missed high-risk signals.",
            "skills_tags": ["risk management", "data analysis", "audit frameworks", "rca"],
        },
        {
            "title": "Audit False-Positive Reduction (NA/EU)",
            "situation": "NA/EU audit processes were flagging a high rate of false positives, consuming investigator time on non-issues.",
            "task": "I needed to redesign the audit logic to cut noise without missing real risk.",
            "action": "Redesigned audit logic and optimized exclusion rules based on root-cause pattern analysis.",
            "result": "Reduced false positives by ~40%, freeing up investigation capacity for genuine risk cases.",
            "skills_tags": ["audit frameworks", "rca", "risk governance", "grc"],
        },
    ],
}


def is_filled():
    """True once the placeholders have been replaced with real data."""
    return PROFILE["name"] != "[FILL IN]" and PROFILE["email"] != "[FILL IN]"
