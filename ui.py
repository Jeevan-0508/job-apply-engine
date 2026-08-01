import streamlit as st
import subprocess
import sys
import os

st.set_page_config(
    page_title="Job Apply Engine",
    layout="centered"
)

st.title("🚀 Job Apply Engine")
st.write("Select a region to run the job application pipeline.")

st.divider()

# Helper to run main.py
def run_engine(region):
    with st.spinner(f"Running job engine for {region.capitalize()}..."):
        result = subprocess.run(
            [sys.executable, "main.py", region],
            capture_output=True,
            text=True
        )

    if result.returncode == 0:
        st.success(f"{region.capitalize()} job run completed successfully.")
        st.text(result.stdout)
    else:
        st.error("Error occurred while running engine.")
        st.text(result.stderr)

# Buttons
col1, col2 = st.columns(2)

with col1:
    if st.button("🇩🇪 Germany Jobs", use_container_width=True):
        run_engine("germany")

with col2:
    if st.button("🇮🇳 India Jobs", use_container_width=True):
        run_engine("india")

st.divider()

st.caption("This runs your local job application engine safely.")
