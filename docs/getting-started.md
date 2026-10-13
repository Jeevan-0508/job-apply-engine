# Getting started

Job Apply Engine is a local-first Streamlit workflow for German-market job applications. It searches supported sources, ranks a posting against the configured profile, drafts application material and keeps the process trackable.

## Try it safely

The [hosted demo](https://job-apply-engine-6a5fsqqd765xpj3pgf6sn8.streamlit.app/) is useful for exploring the workflow, but uploads and pasted content are processed by Streamlit Community Cloud. Use a local run for real personal or resume data.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run the repository's test suite from the same environment before changing the search or document-generation flow.

## Honest boundaries

Indeed, StepStone and Xing are presented as deep links rather than claimed integrations. Generated CVs, letters, interview notes and ATS findings are drafts for review, not automatic submissions or guarantees of employment.
