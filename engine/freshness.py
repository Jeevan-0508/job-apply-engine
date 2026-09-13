"""
Tracks how current one posting is, across repeat searches over time.

Stored as data/job_sightings.json (gitignored, same atomic-write pattern
as engine/tracker.py) keyed by the same stable job identity tracker.py
uses, so "the same posting" means the same thing everywhere in this app.

Every entry carries:
  first_seen_at   -- when this app first saw the posting, ever
  last_seen_at    -- the most recent search that returned it
  last_verified_at -- the most recent time a source confirmed it live
                       (identical to last_seen_at here, since a search
                       result IS a live confirmation from the source)
  posted_at       -- the source's own publish date, when parseable
  closed_at       -- set only once CLOSED is confirmed

Freshness Score/100 and status (FRESH/AGING/OLD/STALE/CLOSED/
CLOSED_CANDIDATE/UNKNOWN) are derived from posted_at when available,
falling back to first_seen_at (flagged as an estimate, never presented
with the same confidence as a real posted date).

What this deliberately does NOT do: infer that a posting has closed just
because one particular search no longer returns it. Absence from one
query/location combination is not evidence of closure -- the query
changed, the ranking changed, anything. CLOSED_CANDIDATE and CLOSED exist
as states a caller can set explicitly (mark_closed_candidate /
confirm_closed) once it has done a real, targeted check (e.g. the
posting's own link now 404s) -- that check is deliberately not wired to
run automatically on every search, which would multiply requests for a
guess. A job is never claimed active without evidence, and it is never
silently deleted either.
"""
import json
import os
import re
from datetime import datetime

from engine.tracker import job_id

STORE = os.path.join("data", "job_sightings.json")

FRESH, AGING, OLD, STALE, CLOSED, CLOSED_CANDIDATE, UNKNOWN = (
    "FRESH", "AGING", "OLD", "STALE", "CLOSED", "CLOSED_CANDIDATE", "UNKNOWN",
)

# (age_days, score) breakpoints, piecewise-linear between them. A
# suggested interpretation, not a hard law -- see module docstring for
# why a stale-looking date doesn't always mean a stale posting.
_SCORE_POINTS = [(0, 100), (3, 91), (14, 60), (30, 30), (90, 5)]


def _now():
    return datetime.now()


def _now_iso():
    return _now().isoformat(timespec="seconds")


def _parse_date(value):
    """Best-effort parse of a source's own date field into a datetime.
    Handles ISO dates/datetimes (with or without a trailing Z) and epoch
    timestamps in seconds or milliseconds (Lever uses epoch-ms). Returns
    None rather than guessing when the format isn't recognized."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        try:
            ts = value / 1000 if value > 1e12 else value
            return datetime.fromtimestamp(ts)
        except (ValueError, OSError, OverflowError):
            return None
    text = str(value).strip()
    if re.fullmatch(r"\d{10,13}", text):
        return _parse_date(int(text))
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        pass
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def load(path=STORE):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save(entries, path=STORE):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return path


def record_sighting(job, path=STORE):
    """Record that a live search just returned this posting. Creates the
    entry on first sighting, otherwise refreshes last_seen_at/
    last_verified_at -- and un-flags CLOSED_CANDIDATE, because reappearing
    in a live result is itself evidence the posting is still up."""
    entries = load(path)
    jid = job_id(job)
    now = _now_iso()

    entry = entries.get(jid)
    if entry is None:
        entry = {
            "id": jid,
            "first_seen_at": now,
            "posted_at": None,
            "closed_at": None,
            "status_override": None,
        }
        entries[jid] = entry

    entry["last_seen_at"] = now
    entry["last_verified_at"] = now
    if entry.get("status_override") == CLOSED_CANDIDATE:
        entry["status_override"] = None

    if not entry.get("posted_at"):
        parsed = _parse_date((job or {}).get("posted"))
        if parsed:
            entry["posted_at"] = parsed.isoformat()

    save(entries, path)
    return entry


def get_entry(job, path=STORE):
    return load(path).get(job_id(job))


def _score_for_age(age_days):
    age_days = max(0, age_days)
    points = _SCORE_POINTS
    if age_days <= points[0][0]:
        return points[0][1]
    for (a0, s0), (a1, s1) in zip(points, points[1:]):
        if age_days <= a1:
            frac = (age_days - a0) / (a1 - a0)
            return round(s0 + frac * (s1 - s0))
    return points[-1][1]


def _status_for_age(age_days):
    if age_days <= 3:
        return FRESH
    if age_days <= 14:
        return AGING
    if age_days <= 30:
        return OLD
    return STALE


def compute_freshness(entry):
    """Score/100 and status for one sightings entry. Never fabricates
    activity: with no entry and no parseable date at all, returns
    UNKNOWN with score None rather than guessing."""
    if not entry:
        return {"score": None, "status": UNKNOWN, "age_days": None, "date_source": None}

    if entry.get("status_override") == CLOSED:
        return {"score": 0, "status": CLOSED, "age_days": None, "date_source": "confirmed"}

    reference = entry.get("posted_at")
    date_source = "posted_at"
    if not reference:
        reference = entry.get("first_seen_at")
        date_source = "first_seen_at (estimated -- no posting date available)"

    parsed = _parse_date(reference)
    if not parsed:
        return {"score": None, "status": UNKNOWN, "age_days": None, "date_source": None}

    age_days = (_now() - parsed).days
    status_value = entry.get("status_override") or _status_for_age(age_days)
    if status_value == CLOSED_CANDIDATE:
        score = max(0, _score_for_age(age_days) - 20)  # visibly lower, but not zeroed -- unconfirmed
    else:
        score = _score_for_age(age_days)

    return {"score": score, "status": status_value, "age_days": age_days, "date_source": date_source}


def freshness_for_job(job, path=STORE, record=True):
    """Convenience entrypoint: record this sighting (unless the caller is
    just inspecting, not searching) and return its freshness."""
    entry = record_sighting(job, path) if record else get_entry(job, path)
    return compute_freshness(entry)


def mark_closed_candidate(job, reason="", path=STORE):
    """Flag a posting as possibly closed, from a real targeted check (e.g.
    its link returned 404) -- never from mere absence in a search result.
    Stays a *candidate*, not CLOSED, until confirm_closed() is called."""
    entries = load(path)
    jid = job_id(job)
    entry = entries.get(jid) or {"id": jid, "first_seen_at": _now_iso(), "posted_at": None, "closed_at": None}
    entry["status_override"] = CLOSED_CANDIDATE
    entry["closed_candidate_reason"] = reason
    entries[jid] = entry
    save(entries, path)
    return entry


def confirm_closed(job, path=STORE):
    """Transition a posting to CLOSED. Only ever called explicitly, never
    inferred automatically -- see module docstring."""
    entries = load(path)
    jid = job_id(job)
    entry = entries.get(jid) or {"id": jid, "first_seen_at": _now_iso(), "posted_at": None}
    entry["status_override"] = CLOSED
    entry["closed_at"] = _now_iso()
    entries[jid] = entry
    save(entries, path)
    return entry
