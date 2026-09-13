"""
A small in-memory, TTL-based cache shared by anything that fetches the same
thing repeatedly within a session: a Greenhouse/Lever board's full job list,
or one posting's full description.

Deliberately not a database and not disk-persisted -- this is a Streamlit
app, one process per session, and the problem being solved is "don't hit
the network twice for the same thing in the same run", not "remember
forever". Persisting past a restart would need a real invalidation story
(a posting can close or change) that isn't worth building for what this
actually needs.
"""
import hashlib
import time

_STORE = {}


def get(key, ttl):
    entry = _STORE.get(key)
    if not entry:
        return None
    value, stored_at = entry
    if time.time() - stored_at > ttl:
        del _STORE[key]
        return None
    return value


def set(key, value):
    _STORE[key] = (value, time.time())


def clear():
    _STORE.clear()


def content_hash(text):
    """Stable short hash of a text blob, used to detect whether a
    description actually changed rather than just being re-fetched."""
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
