"""
CV versioning: every time build_package() runs for a job, this records a
version entry -- score snapshot + matched/missing skills -- keyed by the
same stable job id tracker.py uses. Answers "did the last rebuild actually
improve this application" without the candidate having to remember what
the previous ATS/Integrity/Red Team scores were.

Stored as data/cv_versions.json (gitignored, same atomic-write pattern as
tracker.py/freshness.py). Append-only: nothing here is ever edited or
deleted, so a version history stays a real history even if a later build
is worse than an earlier one.
"""
import json
import os
from datetime import datetime

from engine.tracker import job_id

STORE = os.path.join("data", "cv_versions.json")


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


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


def record_version(job, meta, path=STORE):
    """Append one version snapshot for this job. `meta` is the dict
    build_package() already produces -- only the fields relevant to
    tracking improvement over time are kept, not the whole thing."""
    entries = load(path)
    jid = job_id(job)
    history = entries.setdefault(jid, [])
    snapshot = {
        "recorded_at": _now_iso(),
        "coverage": meta.get("coverage"),
        "relevance": meta.get("relevance"),
        "ats_score": meta.get("ats_score"),
        "integrity_score": meta.get("integrity_score"),
        "integrity_blocked": meta.get("integrity_blocked"),
        "red_team_score": meta.get("red_team_score"),
        "matched_skills": list(meta.get("matched_skills") or []),
        "missing_skills": list(meta.get("missing_skills") or []),
    }
    history.append(snapshot)
    save(entries, path)
    return history


def get_history(job, path=STORE):
    return load(path).get(job_id(job), [])


def diff_last_two(job, path=STORE):
    """Score deltas and skill-set changes between the two most recent
    versions for this job. None if there is no prior version to compare
    against -- a first build has nothing to diff, and that is reported
    as such rather than as all-zero deltas."""
    history = get_history(job, path)
    if len(history) < 2:
        return None
    prev, curr = history[-2], history[-1]

    def delta(field):
        a, b = prev.get(field), curr.get(field)
        if a is None or b is None:
            return None
        return b - a

    gained = sorted(set(curr.get("matched_skills") or []) - set(prev.get("matched_skills") or []))
    lost = sorted(set(prev.get("matched_skills") or []) - set(curr.get("matched_skills") or []))

    return {
        "previous_recorded_at": prev["recorded_at"],
        "current_recorded_at": curr["recorded_at"],
        "coverage_delta": delta("coverage"),
        "relevance_delta": delta("relevance"),
        "ats_delta": delta("ats_score"),
        "integrity_delta": delta("integrity_score"),
        "red_team_delta": delta("red_team_score"),
        "skills_gained": gained,
        "skills_lost": lost,
        "version_count": len(history),
    }
