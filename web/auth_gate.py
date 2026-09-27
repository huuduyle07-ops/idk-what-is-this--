from __future__ import annotations

from collections.abc import Collection, Sequence
from dataclasses import dataclass

from web.browser_session import (
    SESSION_MISSING,
    SessionRead,
    evaluate_csrf,
    web_auth_token_matches,
)
from web.request_origin import Origin, evaluate_origin


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
# Metadata a browser attaches by itself. User-Agent is not a signal, and a
# session cookie alone never selects the browser path: it is no credential.
_BROWSER_CONTEXT_HEADERS = ("Origin", "Sec-Fetch-Site", "Sec-Fetch-Mode", "Sec-Fetch-Dest", "Referer")
LOGIN_PATH = "/auth/login"

_REASONS = {
    "safe_method": "safe method",
    "origin_missing": "Browser mutation rejected: the request carries no Origin header.",
    "origin_null": "Browser mutation rejected: an opaque (privacy-masked) origin is never an allowed application origin.",
    "origin_malformed": "Browser mutation rejected: the Origin header is not a valid scheme://host[:port] origin.",
    "origin_ambiguous": "Browser mutation rejected: the request carries more than one Origin value.",
    "origin_not_allowed": (
        "Browser mutation rejected: this page's origin is not allowed for this server "
        "(scheme, host and port must match exactly; see WEB_ALLOWED_ORIGINS)."
    ),
    "browser_session_missing": "Browser mutation rejected: no browser session. Reload the page and retry.",
    "browser_session_invalid": (
        "Browser mutation rejected: the browser session is no longer valid (server restart, "
        "token change or expiry). Reload the page, sign in again if required, and retry."
    ),
    "csrf_missing": "Browser mutation rejected: the CSRF token is missing.",
    "csrf_ambiguous": "Browser mutation rejected: more than one CSRF token was supplied.",
    "csrf_invalid": "Browser mutation rejected: the CSRF token is invalid or stale. Reload the page and retry.",
    "auth_required": (
        "Authentication required: sign in with WEB_AUTH_TOKEN in the browser, "
        "or send it as a bearer token from an API client."
    ),
    "web_auth_token_mismatch": "Authentication failed: the supplied WEB_AUTH_TOKEN was not accepted.",
    "non_loopback_rejected": (
        "mutation from non-loopback address rejected; "
        "set WEB_AUTH_TOKEN to allow network-exposed mutations"
    ),
    "browser_context_required": (
        "Browser sign-in requires a same-origin browser request; "
        "API clients send WEB_AUTH_TOKEN as a bearer token instead."
    ),
    "browser_session_authenticated": "browser session authenticated",
    "token_authenticated": "token authenticated",
    "login_bootstrap": "sign-in request; the route verifies WEB_AUTH_TOKEN",
    "loopback_allowed": "loopback client allowed (no WEB_AUTH_TOKEN configured)",
}


@dataclass
class GateDecision:
    allowed: bool
    status_code: int
    reason: str
    code: str = ""


def _decision(allowed: bool, status_code: int, code: str) -> GateDecision:
    return GateDecision(allowed=allowed, status_code=status_code, reason=_REASONS[code], code=code)


def is_loopback_host(value: str) -> bool:
    """Return True if value is a loopback hostname or IP."""
    if not value:
        return False
    host = value.split(":")[0].strip().lower()
    if not host:
        host = value.strip().lower()
    return host in _LOOPBACK_HOSTS


def extract_web_auth_token(headers) -> str:
    """Return the bearer token from headers or empty string."""
    x_token = (headers.get("X-CATTUS-Web-Token") or "").strip()
    if x_token:
        return x_token
    auth = (headers.get("Authorization") or "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


def is_mutating_method(method: str) -> bool:
    return (method or "").upper() in _MUTATING_METHODS


def is_browser_request(headers) -> bool:
    """True when the request carries origin or Fetch Metadata a browser attaches."""
    return any(headers.get(name) is not None for name in _BROWSER_CONTEXT_HEADERS)


def _header_values(headers, name: str) -> list[str]:
    getlist = getattr(headers, "getlist", None)
    if getlist is not None:
        return list(getlist(name))
    value = headers.get(name)
    return [] if value is None else [value]


def _authenticate(
    token: str, provided: str, remote_addr: str, *, browser_authenticated: bool
) -> GateDecision:
    if token:
        if browser_authenticated:
            return _decision(True, 200, "browser_session_authenticated")
        if not provided:
            return _decision(False, 401, "auth_required")
        if not web_auth_token_matches(provided, token):
            return _decision(False, 403, "web_auth_token_mismatch")
        return _decision(True, 200, "token_authenticated")
    # No token configured: only loopback clients may mutate.
    if is_loopback_host(remote_addr):
        return _decision(True, 200, "loopback_allowed")
    return _decision(False, 403, "non_loopback_rejected")


def should_allow_mutation(
    method: str,
    remote_addr: str,
    headers,
    configured_token: str | None,
    *,
    path: str = "",
    allowed_origins: Collection[Origin] = frozenset(),
    browser_session: SessionRead | None = None,
    csrf_submissions: Sequence[str] = (),
) -> GateDecision:
    """Decide whether a request may reach a state-changing route.

    AUTH.WEB.1: a browser request (Origin or Fetch Metadata present) must pass
    three independent proofs, in this order: exact origin (scheme, host and
    effective port in ``allowed_origins``), a CSRF token bound to a valid
    browser session, then authentication -- an authenticated browser session
    or a valid WEB_AUTH_TOKEN header, or with no WEB_AUTH_TOKEN configured a
    loopback client. Neither proof substitutes for another.

    A request without browser metadata keeps the API contract: a valid
    WEB_AUTH_TOKEN header (X-CATTUS-Web-Token or Authorization: Bearer), or a
    loopback client when no token is configured. A session cookie
    authenticates nothing on that path, and /auth/login is browser-only.

    Args:
        method: HTTP method string (e.g. "POST").
        remote_addr: Client IP address string.
        headers: Mapping-like object with HTTP headers (e.g. flask.request.headers).
        configured_token: Value of WEB_AUTH_TOKEN env var, or None/empty if unset.
        path: Request path (only /auth/login is special).
        allowed_origins: Exact origins allowed to send browser mutations.
        browser_session: The verified browser session cookie read.
        csrf_submissions: CSRF token values carried by the request.

    Returns:
        GateDecision with allowed, status_code, reason and a stable code.
    """
    if not is_mutating_method(method):
        return _decision(True, 200, "safe_method")
    token = configured_token.strip() if configured_token else ""
    provided = extract_web_auth_token(headers)
    login = path == LOGIN_PATH

    if not is_browser_request(headers):
        if login:
            return _decision(False, 403, "browser_context_required")
        return _authenticate(token, provided, remote_addr, browser_authenticated=False)

    origin = evaluate_origin(_header_values(headers, "Origin"), allowed_origins)
    if not origin.allowed:
        return _decision(False, 403, origin.code)
    session = browser_session if browser_session is not None else SessionRead(SESSION_MISSING)
    csrf = evaluate_csrf(session, csrf_submissions)
    if not csrf.allowed:
        return _decision(False, 403, csrf.code)
    authenticated = session.session.authenticated
    if token and login and not provided and not authenticated:
        return _decision(True, 200, "login_bootstrap")
    return _authenticate(token, provided, remote_addr, browser_authenticated=authenticated)
