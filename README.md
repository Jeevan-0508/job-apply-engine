# Job Apply Engine

A local-first job application tool for the German market. One click turns a
search into finished applications: it finds real postings, reads each full job
description, ranks them against your actual profile, and generates a tailored
CV, cover letter, interview prep pack and ATS report per job — then tracks what
you sent and what came back.

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

**Tab 1 — Find & Apply**
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

### One click, one finished application

**Search and rank** does the whole first pass: it searches, fetches the full
description for every result, scores each one against your profile, and sorts the
list best-fit first. Postings already in your pipeline are marked, so a repeat
search shows you what is new.

From there **⚡ Build application** on any posting — or **Build applications for
the top 3** — writes one folder per job containing everything needed to send it:

| File | |
|---|---|
| `CV.pdf` / `CV.docx` | tailored and reordered against that specific posting |
| `CoverLetter.pdf` / `.docx` | English, or a German Anschreiben |
| `InterviewPrep.txt` / `.docx` | question themes mapped to your matched skills |
| `ATS_report.txt` | the generated CV re-parsed and scored |
| `posting.txt` | the description as fetched, so you can reread it later |
| `application.json` | scores, matched and missing skills — an audit trail |
| `application.zip` | the four documents, ready to attach |

Each artefact is generated independently: a cover letter that fails to build must
not cost you the CV, so failures are collected and reported rather than raised.
The job is recorded in the pipeline as *Package built* in the same pass.

Descriptions come from the Arbeitsagentur job-details endpoint and LinkedIn's
public guest page (`engine/search/job_detail.py`). One that cannot be fetched
falls back to scoring the title alone — and says so, because a score based on
nothing is worse than an admitted gap.

### Two scores, deliberately not blended

Ranking reports two numbers (`engine/match.py`), because they answer different
questions and averaging them hides both:

- **Coverage** — of what this posting asks for, how much your profile can
  evidence. The *will my CV survive the keyword screen* number.
- **Relevance** — of what you can do, how much this posting asks for. The *is
  this the kind of work I actually do* number.

They are the same two sets measured in opposite directions. High coverage with
low relevance is a job you would pass the screen for and be bored by; the
reverse is your own work described in vocabulary your CV doesn't use.

Requirements the posting leans on hardest and your profile can't evidence are
named in the verdict, so a 55% tells you *which* thing is missing.

A posting with too little recognisable signal is labelled as such instead of
being ranked. Without that, a thin but precisely relevant posting scores 0 while
a keyword-stuffed generic one scores 50, and the ordering is worse than none.

### The demand report

Across every posting in a search, the app aggregates which skills the market
keeps asking for that your profile cannot evidence, ordered by how often they
cost you a match. A real run over eight German loss-prevention postings returned
*loss prevention missing in 8/8, German language 5/5, inventory shrinkage 3/3.*

That turns a low score from a verdict into a to-do list, and it is the most
useful output in the app: no scoring change can fix a profile that doesn't
mention the work you actually do.

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

Letters are available in English or as a German **Anschreiben** with the layout
German recruiters check for: sender and recipient blocks, a right-aligned
*Ort, TT.MM.JJJJ* line, a bold *Bewerbung als …* subject, *Sehr geehrte Damen
und Herren* and *Mit freundlichen Grüßen*. The German sentences are written, not
machine-translated — but only the frame is German. Your own profile text is
inserted exactly as you wrote it, so an English profile produces a mixed letter;
write German bullets in `config/profile.py` if you need a fully German one.

**The letter never claims a skill your profile does not evidence.** That is
enforced by a test, not merely intended: an earlier version fell back to the
job's own requirements when nothing matched, producing letters that opened *"my
experience in loss prevention, fraud investigation"* — naming precisely the
skills the applicant did not have. With no overlap it now names your own
strongest skills and drops the overlap claim entirely.

**Tab 4 — Pipeline**
Every job you shortlist or build a package for is recorded in
`data/pipeline.json` (gitignored, written atomically so an interrupted write
can't leave half a pipeline behind). The tab shows totals, how many are still
open, your response and interview rates, average coverage and average ATS score,
and which source actually converts — applying through the source that answers is
worth more than applying more.

Applications sent and gone quiet for ten days are flagged for chasing. Status and
notes are editable per row, and the whole pipeline exports to CSV.

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

`config/profile.py` is gitignored — it holds your real name, email and phone and
must never be committed. When hosting, leave it out of the repo and supply a
`PROFILE_JSON` secret instead; `python tools/make_secret.py` writes it in the
exact TOML the loader reads.

Then:

```
streamlit run app.py
```

## Project structure

```
app.py                          # 4-tab Streamlit UI, the entry point
conftest.py                     # puts the repo root on sys.path for pytest
config/
  profile.py                    # your structured profile — fill in once (gitignored)
engine/
  search/
    arbeitsagentur.py           # official public API
    linkedin_search.py          # public jobs-guest search
    job_detail.py               # fetches the full description for one posting
    deeplinks.py                # pre-filled searches for sites that block bots
    aggregator.py               # merges + normalizes the readable sources
  jd_analyzer.py                # JD -> weighted skill signal; profile match/gap logic
  skill_map.py                  # weighted skills + aliases (EN/DE) — extend for your field
  match.py                      # coverage/relevance scoring, verdicts, demand report
  ats_check.py                  # re-parses the produced PDF and scores it
  resume_parser.py              # PDF resume -> flat lines (fallback mode)
  tailor.py                     # ranks flat lines by JD relevance (fallback mode)
  cv_builder.py                 # tailored CV -> docx + pdf, both layouts
  cover_letter.py               # tailored cover letter -> docx + pdf, EN/DE
  interview_prep.py             # interview prep pack -> txt + docx
  package.py                    # one posting -> every artefact + zip, in one call
  tracker.py                    # application pipeline, metrics, CSV export
tools/
  make_secret.py                # profile.py -> the PROFILE_JSON hosting secret
tests/                          # pytest -- pip install -r requirements-dev.txt && pytest
resumes/                        # put your resume PDF here (gitignored)
applications/                   # generated output, one folder per job (gitignored)
data/                           # pipeline.json lives here (gitignored)
```

## Notes

- Nothing here calls out to an LLM or a cloud service — search hits public
  job APIs/pages directly, and CV/cover-letter/prep generation is template +
  scoring logic against your own `config/profile.py`, run entirely locally.
- LinkedIn's guest search endpoint is unauthenticated but automated access is
  against its Terms of Service; keep query volume to personal-use levels. It
  returns HTTP 429 if you page too fast, in which case the app keeps whatever
  it already fetched and tells you rather than failing the whole search.
- Search matches on title and metadata only, so a posting that mentions your
  skill only in the body won't surface. Once a posting *is* found its full
  description is fetched and scored — the limitation is discovery, not scoring.
- Fetching a description per result costs one request per job, so a search for
  50 postings makes 50 follow-up requests. Keep `limit` sane.

## License

All rights reserved — see [LICENSE](LICENSE).
