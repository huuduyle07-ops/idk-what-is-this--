from __future__ import annotations

import hmac
from dataclasses import dataclass
from urllib.parse import urlparse


_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


@dataclass
class GateDecision:
    allowed: bool
    status_code: int
    reason: str


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


def origin_matches_request(origin: str, host: str) -> bool:
    """Return True when origin host equals request host (allows same-origin)."""
    if not origin or not host:
        return True
    try:
        origin_host = urlparse(origin).hostname or ""
    except Exception:
        return False
    request_host = host.split(":")[0].strip().lower()
    if not request_host:
        request_host = host.strip().lower()
    origin_host = origin_host.strip().lower()
    if not origin_host:
        return True
    if origin_host == request_host:
        return True
    if origin_host in _LOOPBACK_HOSTS and request_host in _LOOPBACK_HOSTS:
        return True
    return False


def should_allow_mutation(
    method: str,
    remote_addr: str,
    headers,
    host: str,
    configured_token: str | None,
) -> GateDecision:
    """Decide whether a request should be allowed through the mutation gate.

    Args:
        method: HTTP method string (e.g. "POST").
        remote_addr: Client IP address string.
        headers: Mapping-like object with HTTP headers (e.g. flask.request.headers).
        host: Request Host header value (e.g. "localhost:5000").
        configured_token: Value of WEB_AUTH_TOKEN env var, or None/empty if unset.

    Returns:
        GateDecision with allowed, status_code, reason.
    """
    if method.upper() not in _MUTATING_METHODS:
        return GateDecision(allowed=True, status_code=200, reason="safe method")

    # CSRF / Origin check — runs before auth so cross-origin is always rejected.
    origin = (headers.get("Origin") or "").strip()
    referer = (headers.get("Referer") or "").strip()
    check_origin = origin or referer
    if check_origin and not origin_matches_request(check_origin, host):
        return GateDecision(
            allowed=False,
            status_code=403,
            reason=f"cross-origin mutation rejected: origin={check_origin!r} host={host!r}",
        )

    token = configured_token.strip() if configured_token else ""

    if token:
        # Token is configured — require a matching bearer on all mutating requests.
        provided = extract_web_auth_token(headers)
        if not provided:
            return GateDecision(
                allowed=False,
                status_code=401,
                reason="mutation requires WEB_AUTH_TOKEN; no token provided",
            )
        if not hmac.compare_digest(provided, token):
            return GateDecision(
                allowed=False,
                status_code=403,
                reason="mutation token mismatch",
            )
        return GateDecision(allowed=True, status_code=200, reason="token authenticated")
    else:
        # No token configured — allow only loopback clients.
        if is_loopback_host(remote_addr):
            return GateDecision(
                allowed=True,
                status_code=200,
                reason="loopback client allowed (no WEB_AUTH_TOKEN configured)",
            )
        return GateDecision(
            allowed=False,
            status_code=403,
            reason=(
                "mutation from non-loopback address rejected; "
                "set WEB_AUTH_TOKEN to allow network-exposed mutations"
            ),
        )
