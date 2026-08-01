import re
from engine.skill_map import SKILL_WEIGHTS

def analyze_jd(jd_text):
    jd_text = jd_text.lower()
    signal = {}

    for skill, weight in SKILL_WEIGHTS.items():
        if re.search(rf"\b{re.escape(skill)}\b", jd_text):
            signal[skill] = weight

    return dict(sorted(signal.items(), key=lambda x: x[1], reverse=True))
