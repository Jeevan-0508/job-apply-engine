"""
Canonical per-source status for one search() call.

The rule that matters here: a source that failed, was blocked, or got
rate-limited must never be reported the same way as a source that
genuinely has zero matching postings. Collapsing those into one "EMPTY"
bucket hides real problems (a broken connector looks like "no jobs today")
and is exactly the kind of silently-discarded uncertainty this project
does not do.

Every connector's search() returns a dict that now includes a "status"
key using one of the constants below, in addition to the existing
jobs/error/note/total keys (additive -- old consumers that ignore
"status" keep working).
"""

SUCCESS = "SUCCESS"            # request worked, one or more jobs returned
PARTIAL = "PARTIAL"            # request worked, some jobs returned, but paging/fetch was cut short
EMPTY = "EMPTY"                # request worked, zero jobs -- genuinely no matches
BLOCKED = "BLOCKED"            # request was refused/blocked (e.g. 403, captcha wall)
RATE_LIMITED = "RATE_LIMITED"  # request was throttled (e.g. 429)
ERROR = "ERROR"                # request failed for any other reason (network, timeout, bad response)
UNSUPPORTED = "UNSUPPORTED"    # this source cannot serve this query/location at all

ALL = {SUCCESS, PARTIAL, EMPTY, BLOCKED, RATE_LIMITED, ERROR, UNSUPPORTED}

# Statuses that mean "something is wrong", never to be reported as EMPTY.
PROBLEM_STATUSES = {BLOCKED, RATE_LIMITED, ERROR, UNSUPPORTED}


def classify_http_error(exc):
    """Map an exception (typically requests.RequestException) to a status.

    Looks at the string form of the exception for status codes, since
    connectors here catch broadly and don't always have a real response
    object at hand.
    """
    text = str(exc)
    if "429" in text:
        return RATE_LIMITED
    if "403" in text or "401" in text:
        return BLOCKED
    return ERROR


def label(status):
    """Short human-readable label for UI display."""
    return {
        SUCCESS: "OK",
        PARTIAL: "Partial results",
        EMPTY: "No matches",
        BLOCKED: "Blocked",
        RATE_LIMITED: "Rate-limited",
        ERROR: "Error",
        UNSUPPORTED: "Not supported",
    }.get(status, status)
