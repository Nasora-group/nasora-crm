"""Temporary protection against abusive login attempts.

Counters live in the existing Flask-Caching backend, so no database column or
migration is required. For multi-instance production deployments, configure a
shared cache backend (for example Redis) so limits are shared by all workers.
"""
import hashlib
import time

from flask import current_app, request

from app.extensions import cache

FAILED_LIMIT = 5
FAILED_WINDOW_SECONDS = 10 * 60
LOCKOUT_SECONDS = 15 * 60
IP_LIMIT = 20
IP_WINDOW_SECONDS = 10 * 60


def _digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:32]


def client_ip():
    """Return the direct peer address; do not trust arbitrary forwarded headers."""
    return request.remote_addr or "unknown"


def _key(prefix, value):
    return f"nasora:login:{prefix}:{_digest(value)}"


def _get_state(key):
    state = cache.get(key)
    return state if isinstance(state, dict) else None


def is_blocked(username):
    username_key = username.strip().lower()
    ip = client_ip()
    now = time.time()
    user_state = _get_state(_key("user", username_key))
    ip_state = _get_state(_key("ip", ip))
    return any(state and float(state.get("blocked_until", 0)) > now for state in (user_state, ip_state))


def record_failure(username):
    username_key = username.strip().lower()
    ip = client_ip()
    now = time.time()
    ttl = max(FAILED_WINDOW_SECONDS, LOCKOUT_SECONDS) + 5

    for prefix, value, limit, window in (
        ("user", username_key, FAILED_LIMIT, FAILED_WINDOW_SECONDS),
        ("ip", ip, IP_LIMIT, IP_WINDOW_SECONDS),
    ):
        key = _key(prefix, value)
        state = _get_state(key) or {"count": 0, "window_started": now, "blocked_until": 0}
        if now - float(state.get("window_started", now)) >= window:
            state = {"count": 0, "window_started": now, "blocked_until": 0}
        state["count"] = int(state.get("count", 0)) + 1
        if state["count"] >= limit:
            state["blocked_until"] = now + LOCKOUT_SECONDS
        cache.set(key, state, timeout=ttl)


def clear_failures(username):
    username_key = username.strip().lower()
    cache.delete(_key("user", username_key))
    cache.delete(_key("ip", client_ip()))


def retry_after(username):
    username_key = username.strip().lower()
    ip = client_ip()
    states = (_get_state(_key("user", username_key)), _get_state(_key("ip", ip)))
    remaining = [float(s.get("blocked_until", 0)) - time.time() for s in states if s]
    return max(0, int(max(remaining, default=0)))
