"""
The application pipeline: one JSON file recording every job this app has
touched, what was generated for it, and what happened next.

Job hunting fails on follow-through more than on volume. Without a record it is
impossible to answer "did I already apply to this?", "what is going stale?" or
"which source actually converts?" -- so the app keeps the record itself rather
than expecting a spreadsheet to be maintained alongside it.

Stored as plain JSON in data/, which is gitignored. No database, no service:
the file is readable, diffable and trivially backed up.
"""
import csv
import io as _io
import json
import os
from datetime import date, datetime, timedelta

STORE = os.path.join("data", "pipeline.json")

STATUSES = ["Shortlisted", "Package built", "Applied", "Interview",
            "Offer", "Rejected", "Withdrawn"]
OPEN_STATUSES = {"Shortlisted", "Package built", "Applied", "Interview"}
# a sent application with no movement after this long needs chasing
STALE_AFTER_DAYS = 10


def _now():
    return datetime.now().isoformat(timespec="seconds")


def job_id(job):
    """Stable id for a posting. The link is the only reliable unique field."""
    link = (job.get("link") or "").strip().lower()
    if link:
        return link
    return f"{(job.get('company') or '').lower()}|{(job.get('title') or '').lower()}"


def load(path=STORE):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(entries, path=STORE):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)  # never leave a half-written pipeline behind
    return path


def upsert(job, path=STORE, **fields):
    """Add or update one posting, preserving anything already recorded."""
    entries = load(path)
    jid = job_id(job)
    existing = next((e for e in entries if e.get("id") == jid), None)

    if existing is None:
        existing = {
            "id": jid,
            "title": job.get("title", ""),
            "company": job.get("company", ""),
            "location": job.get("location", ""),
            "source": job.get("source", ""),
            "link": job.get("link", ""),
            "status": "Shortlisted",
            "created": _now(),
            "notes": "",
        }
        entries.append(existing)

    existing.update({k: v for k, v in fields.items() if v is not None})
    existing["updated"] = _now()
    save(entries, path)
    return existing


def set_status(jid, status, path=STORE, notes=None):
    entries = load(path)
    for entry in entries:
        if entry.get("id") == jid:
            entry["status"] = status
            if notes is not None:
                entry["notes"] = notes
            entry["updated"] = _now()
            if status == "Applied" and not entry.get("applied_on"):
                entry["applied_on"] = date.today().isoformat()
            break
    save(entries, path)
    return entries


def known_ids(path=STORE):
    """Ids already in the pipeline, so a search can mark what is new."""
    return {e.get("id") for e in load(path)}


def days_since(value):
    if not value:
        return None
    try:
        stamp = datetime.fromisoformat(value)
    except ValueError:
        return None
    return (datetime.now() - stamp).days


def stale(entries):
    """Applications sent and gone quiet, oldest first."""
    out = []
    for entry in entries:
        if entry.get("status") != "Applied":
            continue
        age = days_since(entry.get("applied_on") or entry.get("updated"))
        if age is not None and age >= STALE_AFTER_DAYS:
            out.append({**entry, "days_quiet": age})
    return sorted(out, key=lambda e: -e["days_quiet"])


def metrics(entries):
    """Headline numbers for the pipeline, and the response rate by source."""
    by_status = {s: 0 for s in STATUSES}
    for entry in entries:
        by_status[entry.get("status", "Shortlisted")] = by_status.get(entry.get("status", "Shortlisted"), 0) + 1

    applied = sum(by_status.get(s, 0) for s in ("Applied", "Interview", "Offer", "Rejected"))
    answered = sum(by_status.get(s, 0) for s in ("Interview", "Offer", "Rejected"))
    interviews = by_status.get("Interview", 0) + by_status.get("Offer", 0)

    scores = [e["coverage"] for e in entries if isinstance(e.get("coverage"), (int, float))]
    ats = [e["ats_score"] for e in entries if isinstance(e.get("ats_score"), (int, float))]

    week_ago = datetime.now() - timedelta(days=7)
    this_week = 0
    for entry in entries:
        try:
            if datetime.fromisoformat(entry.get("created", "")) >= week_ago:
                this_week += 1
        except ValueError:
            continue

    by_source = {}
    for entry in entries:
        src = entry.get("source") or "unknown"
        bucket = by_source.setdefault(src, {"total": 0, "applied": 0, "answered": 0})
        bucket["total"] += 1
        if entry.get("status") in ("Applied", "Interview", "Offer", "Rejected"):
            bucket["applied"] += 1
        if entry.get("status") in ("Interview", "Offer", "Rejected"):
            bucket["answered"] += 1

    return {
        "total": len(entries),
        "by_status": by_status,
        "open": sum(by_status.get(s, 0) for s in OPEN_STATUSES),
        "applied": applied,
        "answered": answered,
        "interviews": interviews,
        "response_rate": (answered / applied) if applied else None,
        "interview_rate": (interviews / applied) if applied else None,
        "avg_coverage": (sum(scores) / len(scores)) if scores else None,
        "avg_ats": (sum(ats) / len(ats)) if ats else None,
        "added_this_week": this_week,
        "stale": stale(entries),
        "by_source": by_source,
    }


CSV_FIELDS = ["company", "title", "location", "source", "status", "coverage",
              "relevance", "ats_score", "created", "applied_on", "updated",
              "link", "folder", "notes"]


def to_csv(entries):
    buffer = _io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for entry in sorted(entries, key=lambda e: e.get("created", ""), reverse=True):
        writer.writerow(entry)
    return buffer.getvalue()
