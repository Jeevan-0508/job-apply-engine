"""
Profile loader -- makes the same PROFILE dict work both locally and on
Streamlit Cloud, without ever putting real PII into git.

Local run:    reads config/profile.py (gitignored, real data).
Hosted app:   reads a single PROFILE_JSON secret pasted into
              Streamlit Cloud -> App settings -> Secrets. Never touches git.
"""
import json

try:
    import streamlit as st
    _secrets_available = True
except Exception:
    _secrets_available = False


def get_profile():
    if _secrets_available:
        try:
            raw = st.secrets["PROFILE_JSON"]
            return json.loads(raw)
        except Exception:
            pass
    from config.profile import PROFILE
    return PROFILE


def profile_is_filled(profile):
    return profile.get("name", "[FILL IN]") != "[FILL IN]" and profile.get("email", "[FILL IN]") != "[FILL IN]"
