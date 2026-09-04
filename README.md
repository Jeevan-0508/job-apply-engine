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

The skill map carries aliases as well as canonical names, including German
ones, so a posting that says "Diebstahlsermittlungen", "shrinkage" or "RCA"
scores against the same skill as its English long form. Your own profile is
read through that same vocabulary — without it, matching a CV to a JD is
string equality between two differently-phrased lists, which mostly fails.
Anything the JD asks for with no evidence anywhere in your profile is
reported as an honest gap rather than quietly ignored.

Two layouts are available, both single-column with no tables:

- **International (ATS-first)** — English headings, contact details only.
- **Deutsch (tabellarischer Lebenslauf)** — German headings, a Persönliche
  Daten block, MM/YYYY periods with *heute* for a current role, and a place,
  date and signature line.

A two-column CV is the classic German look, but parsers interleave the columns
into nonsense, so the tabular feel is carried by putting the period on the role
line instead. Periods given as a bare year are printed as given and flagged,
never guessed into months.

Target length is 1 or 2 pages. Content is never dropped to fit: the same CV is
re-rendered at a tighter density and re-measured, and if it still will not fit,
the longer version is kept.

### The ATS check

After generating, the app reads its own PDF back with a text parser and scores
what it finds — `engine/ats_check.py`. Nothing trusts the builder, because the
failure mode being guarded against is a CV that looks perfect on screen and
arrives damaged:

| Check | Why |
|---|---|
| Text extractable | A CV that parses as an image scores zero everywhere |
| No glyph corruption | See below |
| Required sections | Experience / education / skills headings, EN or DE |
| Contact email + phone | Many parsers reject a file with no email |
| Parseable date ranges | Without them an ATS cannot compute years of experience |
| Single column | Columns get interleaved into nonsense |
| No tables | Cell contents are often dropped or reordered |
| Page count and length | 1–2 pages, 350–900 words |
| Keyword coverage | Share of the JD's weighted skills appearing verbatim |

This caught a defect that had been shipping in every CV: bullets were rendered
in reportlab's built-in Helvetica, which has no Unicode map for U+2022, so
**every bullet extracted as `(cid:127)`** and corrupted the line it sat on.
Text is now set in Bitstream Vera, which ships with reportlab. The generated
CV went from 78/100 to 95/100 on the same input. `tests/test_cv_ats.py` fails
if anything reintroduces it.

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
  jd_analyzer.py                # JD -> weighted skill signal; profile match/gap logic
  skill_map.py                  # weighted skills + aliases (EN/DE) — extend for your field
  ats_check.py                  # re-parses the produced PDF and scores it
  resume_parser.py              # PDF resume -> flat lines (fallback mode)
  tailor.py                     # ranks flat lines by JD relevance (fallback mode)
  cv_builder.py                 # tailored CV -> docx + pdf, both layouts
  cover_letter.py               # tailored cover letter -> docx + pdf
  interview_prep.py             # interview prep pack -> txt + docx
tests/                          # pytest -- run: pip install -r requirements-dev.txt && pytest
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
