"""AUTH.WEB.1: derived browser session and CSRF proofs.

WEB_AUTH_TOKEN stays the only configured secret. A browser presents it once,
in the POST body of /auth/login; the server verifies it and returns a derived
session cookie. The raw token never appears in a cookie, page, script or URL.

Cookie value ``v1.<session id>.<a|u>.<issued>.<mac>``: the MAC is HMAC-SHA256
under a per-process secret over those fields and, for an authenticated
session, a fingerprint of the WEB_AUTH_TOKEN it was minted under. Therefore:

- a server restart replaces the secret, so every earlier browser session and
  CSRF token is rejected (there is no durable session secret);
- rotating WEB_AUTH_TOKEN rejects authenticated sessions minted under the old
  value; anonymous sessions carry no authority and stay usable for CSRF;
- a session expires SESSION_TTL_SECONDS after it was issued.

CSRF token: HMAC-SHA256 of the session id under the same secret. It is
unguessable, bound to one session, sent separately from the cookie (the
X-CSRF-Token header, or a csrf_token form field for native forms) and verified
here, server-side.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import time
from collections.abc import Sequence
from dataclasses import dataclass

COOKIE_NAME = "cattus_ui_session"
CSRF_HEADER = "X-CSRF-Token"
CSRF_FORM_FIELD = "csrf_token"
LOGIN_TOKEN_FIELD = "web_auth_token"
SESSION_TTL_SECONDS = 12 * 60 * 60
CLOCK_SKEW_SECONDS = 60
MAX_COOKIE_LENGTH = 128

SESSION_VALID = "valid"
SESSION_MISSING = "missing"
SESSION_INVALID = "invalid"
SESSION_AMBIGUOUS = "ambiguous"
SESSION_EXPIRED = "expired"

CSRF_VALID = "csrf_valid"
CSRF_MISSING = "csrf_missing"
CSRF_AMBIGUOUS = "csrf_ambiguous"
CSRF_INVALID = "csrf_invalid"
BROWSER_SESSION_MISSING = "browser_session_missing"
BROWSER_SESSION_INVALID = "browser_session_invalid"

# Restart-invalidated by design: never persisted, logged or derived from config.
_PROCESS_SECRET = secrets.token_bytes(32)
_COOKIE_SHAPE = re.compile(r"v1\.([A-Za-z0-9_-]{43})\.([au])\.([0-9]{1,12})\.([A-Za-z0-9_-]{43})")
_CSRF_SHAPE = re.compile(r"[A-Za-z0-9_-]{43}")


@dataclass(frozen=True)
class BrowserSession:
    session_id: str
    authenticated: bool
    issued_at: int


@dataclass(frozen=True)
class SessionRead:
    status: str
    session: BrowserSession | None = None


@dataclass(frozen=True)
class CsrfDecision:
    allowed: bool
    code: str


def _mac(*parts: str) -> str:
    message = "\x00".join(parts).encode("utf-8", "surrogatepass")
    digest = hmac.new(_PROCESS_SECRET, message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _token_fingerprint(token: str) -> str:
    return _mac("cattus-web-auth-token", token)


def _session_mac(session_id: str, kind: str, issued: str, binding: str) -> str:
    return _mac("cattus-ui-session", "v1", session_id, kind, issued, binding)


def mint_session(
    *, authenticated: bool, configured_token: str, now: int | None = None
) -> tuple[BrowserSession, str]:
    """Create a new session id and its signed cookie value."""
    token = (configured_token or "").strip()
    if authenticated and not token:
        raise ValueError("an authenticated browser session requires WEB_AUTH_TOKEN")
    issued = str(int(time.time()) if now is None else int(now))
    session_id = secrets.token_urlsafe(32)
    kind = "a" if authenticated else "u"
    binding = _token_fingerprint(token) if authenticated else "-"
    cookie = f"v1.{session_id}.{kind}.{issued}.{_session_mac(session_id, kind, issued, binding)}"
    return BrowserSession(session_id, authenticated, int(issued)), cookie


def read_session(
    cookie_values: Sequence[object], *, configured_token: str, now: int | None = None
) -> SessionRead:
    """Verify the browser session cookie; every malformed or stale value fails closed."""
    values = list(cookie_values)
    if not values:
        return SessionRead(SESSION_MISSING)
    if len(values) != 1:
        return SessionRead(SESSION_AMBIGUOUS)
    value = values[0]
    if not isinstance(value, str) or len(value) > MAX_COOKIE_LENGTH:
        return SessionRead(SESSION_INVALID)
    shape = _COOKIE_SHAPE.fullmatch(value)
    if shape is None:
        return SessionRead(SESSION_INVALID)
    session_id, kind, issued_text, mac = shape.groups()
    token = (configured_token or "").strip()
    if kind == "a" and not token:
        return SessionRead(SESSION_INVALID)
    binding = _token_fingerprint(token) if kind == "a" else "-"
    if not hmac.compare_digest(mac, _session_mac(session_id, kind, issued_text, binding)):
        return SessionRead(SESSION_INVALID)
    issued = int(issued_text)
    current = int(time.time()) if now is None else int(now)
    if issued > current + CLOCK_SKEW_SECONDS:
        return SessionRead(SESSION_INVALID)
    if current - issued > SESSION_TTL_SECONDS:
        return SessionRead(SESSION_EXPIRED)
    return SessionRead(SESSION_VALID, BrowserSession(session_id, kind == "a", issued))


def csrf_token_for(session: BrowserSession) -> str:
    """The CSRF token of one session (deterministic; nothing is stored)."""
    return _mac("cattus-csrf", "v1", session.session_id)


def evaluate_csrf(session_read: SessionRead, submissions: Sequence[object]) -> CsrfDecision:
    """Require exactly one CSRF token, matching the valid session it was issued for."""
    if session_read.status == SESSION_MISSING:
        return CsrfDecision(False, BROWSER_SESSION_MISSING)
    if session_read.status != SESSION_VALID or session_read.session is None:
        return CsrfDecision(False, BROWSER_SESSION_INVALID)
    values = list(submissions)
    if not values:
        return CsrfDecision(False, CSRF_MISSING)
    if len(values) != 1:
        return CsrfDecision(False, CSRF_AMBIGUOUS)
    supplied = values[0]
    if not isinstance(supplied, str) or not _CSRF_SHAPE.fullmatch(supplied):
        return CsrfDecision(False, CSRF_INVALID)
    if not hmac.compare_digest(supplied, csrf_token_for(session_read.session)):
        return CsrfDecision(False, CSRF_INVALID)
    return CsrfDecision(True, CSRF_VALID)


def web_auth_token_matches(supplied: object, configured_token: str) -> bool:
    """Compare a presented token with WEB_AUTH_TOKEN; never raises on odd input."""
    token = (configured_token or "").strip()
    if not token or not isinstance(supplied, str) or not supplied:
        return False
    return hmac.compare_digest(_token_fingerprint(supplied), _token_fingerprint(token))
