"""
Weighted vocabulary used to score a job description against your profile.

Keys are canonical skill names; ALIASES lists the other ways a JD may phrase
the same thing, including the German terms that appear in German postings.
Matching is exact-phrase (word-boundary), so aliases are how coverage is
gained -- a JD that says "Diebstahlsermittlungen" or "shrinkage" is talking
about theft investigation and should score as such.

Weights: 3 = core to the target roles, 2 = strong supporting, 1 = generic.
Extend this for your own field; everything downstream reads only this file.
"""

SKILL_WEIGHTS = {
    # Loss prevention / physical security
    "loss prevention": 3,
    "physical security": 3,
    "theft investigation": 3,
    "fraud investigation": 3,
    "supply chain security": 3,
    "cargo theft": 3,
    "inventory shrinkage": 3,
    "cctv": 2,
    "access control": 2,
    "guard force": 2,
    "case management": 2,
    "incident management": 2,
    "law enforcement": 2,

    # Risk / governance / compliance
    "risk governance": 3,
    "risk management": 3,
    "risk assessment": 3,
    "internal controls": 3,
    "iso 27001": 3,
    "iso 31000": 3,
    "pci dss": 3,
    "sox itgc": 3,
    "gdpr": 3,
    "grc": 3,
    "audit": 3,
    "incident response": 3,
    "data security": 3,
    "anti money laundering": 2,
    "sanctions screening": 2,
    "due diligence": 2,

    # Analytics / tooling
    "sql": 2,
    "python": 2,
    "power bi": 2,
    "tableau": 2,
    "excel": 2,
    "data analysis": 2,
    "dashboards": 2,
    "forecasting": 2,
    "risk scoring": 2,
    "machine learning": 2,
    "root cause analysis": 2,

    # Ways of working
    "program management": 2,
    "project management": 2,
    "six sigma": 2,
    "vendor management": 2,
    "stakeholder management": 1,
    "process optimization": 1,
    "standard operating procedures": 1,
    "german language": 1,
}

# canonical -> extra phrases that mean the same thing
SKILL_ALIASES = {
    "loss prevention": ["asset protection", "lp specialist", "verlustprävention"],
    "physical security": ["site security", "premises security", "werkschutz", "objektschutz"],
    "theft investigation": [
        "theft investigations", "internal theft", "pilferage", "shrinkage investigation",
        "diebstahl", "diebstahlsermittlungen",
    ],
    "fraud investigation": [
        "fraud investigations", "fraud detection", "fraud prevention", "investigations",
        "betrug", "betrugsprävention", "ermittlungen",
    ],
    "supply chain security": ["transportation security", "logistics security", "freight security", "ttsi", "tapa"],
    "cargo theft": ["freight theft", "load theft", "trailer theft", "ladungsdiebstahl"],
    "inventory shrinkage": ["shrink", "shrinkage", "inventory loss", "stock loss", "inventurdifferenzen"],
    "cctv": ["video surveillance", "camera systems", "videosüberwachung"],
    "access control": ["badge access", "zutrittskontrolle"],
    "guard force": ["security guards", "guarding vendor", "third-party guard", "sicherheitsdienst"],
    "case management": ["case documentation", "case files", "investigation reports"],
    "incident management": ["incident reporting", "incident handling", "vorfallmanagement"],
    "law enforcement": ["police liaison", "polizei", "prosecution"],

    "risk governance": ["governance framework", "risk framework"],
    "risk management": ["operational risk", "enterprise risk", "risikomanagement"],
    "risk assessment": ["risk assessments", "threat assessment", "risk analysis", "risikobewertung"],
    "internal controls": ["control framework", "control testing", "kontrollen"],
    "gdpr": ["data privacy", "data protection", "dsgvo", "datenschutz"],
    "grc": ["governance risk and compliance", "compliance management"],
    "audit": ["audits", "auditing", "audit programme", "audit program", "audit controls", "revision"],
    "incident response": ["crisis management", "business continuity", "notfallmanagement"],
    "anti money laundering": ["aml", "money laundering", "geldwäsche"],
    "sanctions screening": ["sanctions", "embargo screening"],
    "due diligence": ["kyc", "know your customer", "background checks", "vendor screening"],

    "sql": ["queries", "relational database"],
    "python": ["pandas", "scripting"],
    "power bi": ["powerbi"],
    "excel": ["spreadsheets", "pivot tables", "vlookup"],
    "data analysis": ["data-driven", "data driven", "analytics", "quantitative analysis", "datenanalyse"],
    "dashboards": ["dashboard", "reporting", "kpi reporting", "metrics reporting", "visualisation", "visualization"],
    "forecasting": ["forecast", "predictive", "trend analysis"],
    "risk scoring": ["scoring model", "risk model", "risk engine"],
    "machine learning": ["ml models", "predictive model", "anomaly detection"],
    "root cause analysis": ["rca", "5 whys", "corrective action", "ursachenanalyse"],

    "program management": ["programme management", "program manager"],
    "project management": ["project manager", "projektmanagement"],
    "six sigma": ["lean", "kaizen", "process improvement", "continuous improvement"],
    "vendor management": ["supplier management", "third-party management", "contract management"],
    "stakeholder management": [
        "stakeholders", "influence without authority", "cross-functional",
        "senior leadership", "stakeholder-management",
    ],
    "process optimization": ["process improvement", "process design", "prozessoptimierung"],
    "standard operating procedures": ["sop", "sops", "work instructions", "arbeitsanweisungen"],
    "german language": ["german is a plus", "german is a strong plus", "fluent german", "deutschkenntnisse"],
}
