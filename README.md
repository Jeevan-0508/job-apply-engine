# Job Apply Engine

A local-first job application tool for the German market: search real job
postings across four sources, tailor your CV per posting, and generate a
cover letter + interview prep pack — all from one Streamlit app.

**Live app:** https://job-apply-engine-6a5fsqqd765xpj3pgf6sn8.streamlit.app/

> Note: the hosted version above runs on Streamlit Community Cloud, so
> anything you paste or upload there is processed on their servers, not
> just yours. For actual personal/resume data, run it locally instead (see
> below) so nothing leaves your machine.

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
| LinkedIn | public jobs-guest search, no login | Paged 10 at a time with a delay and one retry; rate-limits if pushed |

Results are normalized into one list (title, company, location, link,
source) regardless of where they came from. Each source reports its own
count, and a source that returns nothing says so instead of silently
contributing zero rows.

Location accepts English names — "Bavaria", "Munich" and "Cologne" are
mapped to Bayern, München and Köln, because the German API only accepts
German place names. Leaving it blank searches all of Germany.

**Indeed, StepStone and Xing are deep links, not integrations.** Indeed and
StepStone answer a plain HTTPS request with HTTP 403 — verified with a full
browser header set, not just a bare User-Agent — and Xing renders its results
client-side, so there is nothing in the HTML to parse. Getting in would need
headless-browser automation or a paid scraping API, both disproportionate
here. They appear as one-click pre-filled search buttons with the reason
shown underneath. A scraper that silently returns zero is worse than a link
that works.

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
    deeplinks.py                # pre-filled searches for sites that block bots
    aggregator.py               # merges + normalizes the readable sources
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
- LinkedIn's guest search endpoint is unauthenticated but automated access is
  against its Terms of Service; keep query volume to personal-use levels. It
  returns HTTP 429 if you page too fast, in which case the app keeps whatever
  it already fetched and tells you rather than failing the whole search.
- There is no full-text search of job descriptions — both sources match on
  title and metadata only, so a posting that mentions your skill in the body
  but not the title won't surface.

## License

All rights reserved — see [LICENSE](LICENSE).
