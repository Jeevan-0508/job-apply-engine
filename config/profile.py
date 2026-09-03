"""
Your structured profile -- fill this in ONCE. Everything downstream (tailored
CV, cover letters, interview prep) reads from here instead of re-parsing a
PDF every run, which is what makes tailoring actually work well.

Leave a field as "[FILL IN]" and the app will fall back to basic PDF-only
mode for that piece (still works, just less precise). Nothing here is ever
sent anywhere -- it only runs locally on your machine.
"""

PROFILE = {
    "name": "[FILL IN]",
    "title": "[FILL IN]",              # e.g. "Risk Manager | GRC | LP Specialist"
    "email": "[FILL IN]",
    "phone": "[FILL IN]",
    "location": "[FILL IN]",
    "linkedin": "[FILL IN]",
    "github": "[FILL IN]",

    "summary": "[FILL IN] -- 2-3 sentence professional summary.",

    "skills": [
        # flat list, most important first -- feeds the "Core Skills" line on the tailored CV
        "[FILL IN]",
    ],

    "experience": [
        {
            "company": "[FILL IN]",
            "role": "[FILL IN]",
            "location": "[FILL IN]",
            "start": "[FILL IN]",       # e.g. "Jan 2022"
            "end": "[FILL IN]",         # e.g. "Present"
            "bullets": [
                "[FILL IN] -- write outcomes with numbers where you can, not just duties.",
            ],
        },
    ],

    "education": [
        {"degree": "[FILL IN]", "institution": "[FILL IN]", "year": "[FILL IN]"},
    ],

    "certifications": [
        "[FILL IN]",
    ],

    "languages": [
        {"name": "English", "level": "[FILL IN]"},
        {"name": "German", "level": "[FILL IN]"},
    ],

    "why_germany": "[FILL IN] -- short paragraph the cover letter can draw on: "
                   "why Germany, why this kind of role, what you bring.",

    # STAR examples feed both the cover letter's proof points and interview prep.
    # Add as many as you have -- more, tagged with more skills, = better matches.
    "star_examples": [
        {
            "title": "[FILL IN] -- short label, e.g. 'Caught a $100K+ carrier fraud pattern'",
            "situation": "[FILL IN]",
            "task": "[FILL IN]",
            "action": "[FILL IN]",
            "result": "[FILL IN]",
            "skills_tags": ["[FILL IN]"],   # lowercase, should overlap with skill_map.py terms
        },
    ],
}


def is_filled():
    """True once the placeholders have been replaced with real data."""
    return PROFILE["name"] != "[FILL IN]" and PROFILE["email"] != "[FILL IN]"
