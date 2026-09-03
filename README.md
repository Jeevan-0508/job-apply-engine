# Job Apply Engine

A local-first job application tool for the German market: search real job
postings across four sources, tailor your CV per posting, and generate a
cover letter + interview prep pack — all from one Streamlit app, no cloud,
no data leaving your machine.

Built for risk/GRC/compliance roles targeting Germany, but the search terms
and skill map are easy to repoint at any field.

```
streamlit run app.py
```

## What it does

**Tab 1 — Search Jobs**
Type a role and a location (e.g. "Risk Manager" / "Bayern") and it searches:

| Source | How | Durability |
|---|---|---|
| [Bundesagentur für Arbeit](https://jobsuche.api.bund.dev/) | Germany's official public jobs API | Stable — no scraping |
| LinkedIn | public jobs-guest search, no login | Fairly stable, keep volume low (personal use) |
| Indeed.de | HTML scraping | Breaks periodically, needs selector fixes |
| StepStone.de | HTML scraping | Least stable — no public API |

Results are normalized into one list (title, company, location, link,
source) regardless of where they came from.

There's also an **"Open in Xing ↗"** button next to Search — Xing's job
search is a JS-only app with no server-rendered results, so it can't be
scraped the lightweight way the other four are (the only ways in are
headless-browser automation or paid third-party scraping APIs, both
disproportionate for this tool). The button just opens a pre-filled Xing
search in a new tab instead of pretending to integrate.

**Tab 2 — Tailor CV**
Paste a job description, and it scores + reorders your CV against that
specific posting using a weighted skill map (`engine/skill_map.py`), then
generates a real tailored CV as both `.docx` and `.pdf`.

**Tab 3 — Cover Letter + Interview Prep**
For the same job: a cover letter drawing on your actual STAR examples (never
invented experience), and an interview prep pack with likely question themes
mapped to your matched skills — plus an honest list of skills the JD wants
that your profile doesn't show, so you can prepare an answer instead of
being surprised.

## Setup

```
git clone https://github.com/Jeevan-0508/job-apply-engine.git
cd job-apply-engine
python -m venv venv
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

Fill in `config/profile.py` once — your experience, skills, education, and
a few STAR examples. This is what makes the tailoring actually good: without
it, Tab 2 falls back to a basic mode that just reorders bullets extracted
from an uploaded resume PDF, and Tabs 2/3 lose the structured detail that
makes a tailored CV/cover letter/prep pack worth generating.

Then:

```
streamlit run app.py
```

## Project structure

```
app.py                          # 3-tab Streamlit UI, the entry point
config/
  profile.py                    # your structured profile — fill in once
engine/
  search/
    arbeitsagentur.py           # official public API
    linkedin_search.py          # public jobs-guest search
    indeed_scraper.py           # scraping, may break
    stepstone_scraper.py        # scraping, may break
    aggregator.py                # merges + normalizes all four
  jd_analyzer.py                # extracts weighted skill signal from a JD
  skill_map.py                  # weighted skill dictionary — extend for your field
  resume_parser.py              # PDF resume -> flat lines (fallback mode)
  tailor.py                     # ranks flat lines by JD relevance (fallback mode)
  cv_builder.py                 # tailored CV -> docx + pdf
  cover_letter.py               # tailored cover letter -> docx + pdf
  interview_prep.py             # interview prep pack -> txt + docx
resumes/                        # put your resume PDF here (gitignored)
applications/                   # generated output per company (gitignored)
```

## Notes

- Nothing here calls out to an LLM or a cloud service — search hits public
  job APIs/pages directly, and CV/cover-letter/prep generation is template +
  scoring logic against your own `config/profile.py`, run entirely locally.
- The Indeed and StepStone integrations are HTML scrapes against sites with
  no public API. They'll break when those sites change markup — that's
  expected, not a bug in the rest of the app.
- LinkedIn's guest search endpoint is unauthenticated but automated access is
  against its Terms of Service; keep query volume to personal-use levels.

## License

All rights reserved — see [LICENSE](LICENSE).
