"""
Audits a generated CV by reading the produced PDF back the way an applicant
tracking system does, and scores what it finds.

The point is that nothing here trusts the builder. The CV is parsed from the
finished file with pdfplumber, so a formatting choice that looks fine on
screen but destroys the extracted text -- the usual reason a CV is silently
rejected -- shows up as a failed check with the evidence attached.

Checks are weighted and produce a 0-100 score. Every check returns one of
"pass", "warn" or "fail" plus a human-readable detail string; nothing is
scored that cannot be pointed at in the file.
"""
import re

import pdfplumber

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE_RE = re.compile(r"(?:\+\d{1,3}[\s/-]?)?(?:\(?\d{2,5}\)?[\s/-]?){2,5}\d{2,}")
# an ATS needs a date range it can turn into a duration
DATE_RANGE_RE = re.compile(
    r"(?:(?:0[1-9]|1[0-2])[./]\d{4}|\d{4})\s*[\u2013\u2014-]\s*"
    r"(?:(?:0[1-9]|1[0-2])[./]\d{4}|\d{4}|present|heute|current|today|now)",
    re.I,
)
# a font subset with no usable ToUnicode map extracts like this
CID_RE = re.compile(r"\(cid:\d+\)")

SECTIONS = {
    "experience": ["experience", "work experience", "professional experience",
                   "employment", "berufserfahrung", "berufliche erfahrung", "praxiserfahrung"],
    "education": ["education", "ausbildung", "bildungsweg", "akademische ausbildung"],
    "skills": ["skills", "core skills", "competencies", "kenntnisse",
               "fähigkeiten", "kompetenzen", "it-kenntnisse"],
}
OPTIONAL_SECTIONS = {
    "summary": ["summary", "profile", "profil", "kurzprofil", "über mich"],
    "certifications": ["certifications", "certificates", "zertifikate",
                       "weiterbildungen", "qualifikationen"],
    "languages": ["languages", "sprachen", "sprachkenntnisse"],
}

WEIGHTS = {
    "text_extractable": 20,
    "no_glyph_corruption": 15,
    "required_sections": 12,
    "contact_email": 8,
    "contact_phone": 5,
    "date_ranges": 10,
    "single_column": 8,
    "no_tables": 5,
    "page_count": 5,
    "length": 4,
    "keyword_coverage": 8,
}


def _result(status, detail):
    return {"status": status, "detail": detail}


def _headings_found(text, groups):
    lines = [l.strip().lower().rstrip(":") for l in text.splitlines() if l.strip()]
    found = set()
    for key, names in groups.items():
        for line in lines:
            # a heading is a short standalone line, not a sentence mentioning the word
            if len(line) <= 40 and any(line == n or line.startswith(n) for n in names):
                found.add(key)
                break
    return found


def _column_count(page):
    """Detect a two-column layout from the horizontal spread of word starts.

    A single-column CV starts nearly every line at the left margin. A
    two-column one has a second cluster of line starts past the mid-point,
    which most parsers read by interleaving the columns into nonsense.
    """
    words = page.extract_words() or []
    if not words:
        return 1
    mid = page.width / 2
    by_line = {}
    for w in words:
        by_line.setdefault(round(w["top"] / 3), []).append(w["x0"])
    right_starts = sum(1 for xs in by_line.values() if min(xs) > mid)
    return 2 if right_starts >= max(4, 0.25 * len(by_line)) else 1


def audit_pdf(pdf_path, jd_signal=None):
    """Parse a finished CV PDF and score how an ATS is likely to read it."""
    checks = {}
    pages_text = []
    n_pages = 0
    tables = 0
    columns = 1
    fonts = set()

    try:
        with pdfplumber.open(pdf_path) as pdf:
            n_pages = len(pdf.pages)
            for page in pdf.pages:
                pages_text.append(page.extract_text() or "")
                tables += len(page.find_tables() or [])
                columns = max(columns, _column_count(page))
                for ch in page.chars:
                    if ch.get("fontname"):
                        fonts.add(ch["fontname"])
    except Exception as e:
        return {
            "score": 0,
            "checks": {"text_extractable": _result("fail", f"PDF could not be opened: {e}")},
            "text": "",
            "pages": 0,
            "fonts": [],
        }

    text = "\n".join(pages_text)
    words = text.split()

    if len(words) >= 80:
        checks["text_extractable"] = _result("pass", f"{len(words)} words of real text extracted")
    elif words:
        checks["text_extractable"] = _result(
            "fail", f"only {len(words)} words extracted -- most of the CV is unreadable to a parser")
    else:
        checks["text_extractable"] = _result(
            "fail", "no text extracted at all -- the CV is effectively an image")

    cids = CID_RE.findall(text)
    if cids:
        checks["no_glyph_corruption"] = _result(
            "fail", f"{len(cids)} character(s) extract as {cids[0]} instead of a real glyph -- "
                    "a font without a Unicode map corrupts every line it appears on")
    elif "\x00" in text:
        checks["no_glyph_corruption"] = _result("fail", "null characters in the extracted text")
    else:
        checks["no_glyph_corruption"] = _result("pass", "all characters extract as real text")

    found = _headings_found(text, SECTIONS)
    missing = [k for k in SECTIONS if k not in found]
    if not missing:
        checks["required_sections"] = _result("pass", "experience, education and skills headings all found")
    elif len(missing) == 1:
        checks["required_sections"] = _result("warn", f"no recognisable heading for: {missing[0]}")
    else:
        checks["required_sections"] = _result("fail", f"no recognisable heading for: {', '.join(missing)}")

    extras = _headings_found(text, OPTIONAL_SECTIONS)

    emails = EMAIL_RE.findall(text)
    checks["contact_email"] = (
        _result("pass", f"email found: {emails[0]}") if emails
        else _result("fail", "no email address found -- many parsers reject the file outright"))

    head = "\n".join(pages_text[:1])[:600]
    phones = PHONE_RE.findall(head) or PHONE_RE.findall(text)
    checks["contact_phone"] = (
        _result("pass", "phone number found in the header") if phones
        else _result("warn", "no phone number found near the top of page 1"))

    ranges = DATE_RANGE_RE.findall(text)
    if len(ranges) >= 2:
        checks["date_ranges"] = _result("pass", f"{len(ranges)} parseable date ranges")
    elif ranges:
        checks["date_ranges"] = _result("warn", "only one parseable date range -- roles may merge into one entry")
    else:
        checks["date_ranges"] = _result(
            "fail", "no parseable date ranges -- an ATS cannot compute years of experience")

    checks["single_column"] = (
        _result("pass", "single-column layout") if columns == 1
        else _result("fail", "two-column layout detected -- columns are usually interleaved into nonsense"))

    checks["no_tables"] = (
        _result("pass", "no table structures") if tables == 0
        else _result("warn", f"{tables} table structure(s) -- cell contents are often dropped or reordered"))

    if n_pages <= 2:
        checks["page_count"] = _result("pass", f"{n_pages} page(s)")
    elif n_pages == 3:
        checks["page_count"] = _result("warn", "3 pages -- German recruiters expect one or two")
    else:
        checks["page_count"] = _result("fail", f"{n_pages} pages -- far beyond what is read")

    if 350 <= len(words) <= 900:
        checks["length"] = _result("pass", f"{len(words)} words")
    elif len(words) < 350:
        checks["length"] = _result("warn", f"{len(words)} words -- thin, likely to lose on keyword coverage")
    else:
        checks["length"] = _result("warn", f"{len(words)} words -- long enough to bury the relevant parts")

    if jd_signal:
        low = text.lower()
        hit = [s for s in jd_signal if s in low]
        total_w = sum(jd_signal.values()) or 1
        cover = sum(jd_signal[s] for s in hit) / total_w
        missed = [s for s in jd_signal if s not in low]
        detail = f"{len(hit)}/{len(jd_signal)} of the JD's skills appear verbatim ({cover:.0%} by weight)"
        if missed[:6]:
            detail += " -- absent: " + ", ".join(missed[:6])
        status = "pass" if cover >= 0.5 else "warn" if cover >= 0.25 else "fail"
        checks["keyword_coverage"] = _result(status, detail)
        checks["keyword_coverage"]["ratio"] = cover
    else:
        checks["keyword_coverage"] = _result("warn", "no job description supplied, so keyword coverage is unscored")

    earned = 0
    possible = 0
    for name, weight in WEIGHTS.items():
        check = checks.get(name)
        if not check:
            continue
        possible += weight
        if name == "keyword_coverage" and "ratio" in check:
            earned += weight * check["ratio"]
        elif check["status"] == "pass":
            earned += weight
        elif check["status"] == "warn":
            earned += weight * 0.5

    return {
        "score": round(100 * earned / possible) if possible else 0,
        "checks": checks,
        "sections_found": sorted(found | extras),
        "text": text,
        "pages": n_pages,
        "words": len(words),
        "fonts": sorted(fonts),
    }
