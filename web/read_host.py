"""AUTH.WEB.READ.1: trusted Host identity for every safe-method request.

DNS rebinding lets a page on an attacker's name (http://evil.example:5000)
resolve that name to this server and read the responses as same-origin data.
Those requests carry the attacker's name in the Host header and, for a
plain-HTTP name, neither Origin nor Fetch Metadata, so Host is the one field
that separates them from the real application. It is checked, never trusted:

- Trusted hosts are a projection of AUTH.WEB.1's allowed origins
  (``request_origin.allowed_origins_for``): the listening socket, or
  WEB_ALLOWED_ORIGINS when set. The Host, Origin, Referer and X-Forwarded-*
  headers never add a trusted host, and a wildcard bind (0.0.0.0, ::) without
  WEB_ALLOWED_ORIGINS trusts none.
- An origin (scheme, host, port) projects to ``host:port``, and also to the
  bare ``host`` when the port is its scheme's default, because clients omit a
  default port. localhost, 127.0.0.1 and ::1 stay distinct hosts, and the port
  is always compared.
- A missing, repeated or malformed Host is refused with 400 (RFC 9112 §3.2); a
  well-formed Host this server is not configured for, with 421 Misdirected
  Request (RFC 9110 §15.5.20).

``ReadHostBoundary`` wraps the Flask WSGI app, so it decides before routing,
redirects, sessions, before-request hooks, handlers and static files. It checks
GET, HEAD, OPTIONS and every other non-mutating method. POST, PUT, PATCH and
DELETE are left to AUTH.WEB.1's gate unchanged: a browser mutation already
needs an exact allowed Origin, which a rebound page never has.
"""
from __future__ import annotations

import json
import os
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass

from werkzeug.wrappers import Response

from web.auth_gate import is_mutating_method
from web.request_origin import ALLOWED_ORIGINS_ENV, DEFAULT_PORTS, Origin, allowed_origins_for, parse_origin

HOST_ALLOWED = "host_allowed"
HOST_MISSING = "host_missing"
HOST_MALFORMED = "host_malformed"
HOST_AMBIGUOUS = "host_ambiguous"
HOST_NOT_ALLOWED = "host_not_allowed"
MUTATION_GATE = "mutation_gate"
REJECTION_HEADER = "X-CATTUS-Request-Integrity"

_EXPLICIT_PORT = re.compile(r":[0-9]{1,5}\Z")
_REASONS = {
    HOST_MISSING: "Request rejected: it names no host.",
    HOST_MALFORMED: "Request rejected: the Host header is not a valid host[:port].",
    HOST_AMBIGUOUS: "Request rejected: the request carries more than one Host value.",
    HOST_NOT_ALLOWED: (
        "Request rejected: this server is not configured to serve the requested host and port. "
        "Open the app at its configured address; a deployment reached through another address "
        "lists that exact origin in WEB_ALLOWED_ORIGINS."
    ),
}


@dataclass(frozen=True)
class HostIdentity:
    """One Host header identity; ``port`` is None when the header omitted it."""

    host: str
    port: int | None

    def serialize(self) -> str:
        host = f"[{self.host}]" if ":" in self.host else self.host
        return host if self.port is None else f"{host}:{self.port}"


@dataclass(frozen=True)
class HostDecision:
    allowed: bool
    status_code: int
    code: str
    host: HostIdentity | None = None


def parse_host(value: object) -> HostIdentity | None:
    """Parse one Host header value strictly; anything else is None (fail closed).

    A Host is the authority of an http origin and is normalized by the same
    owner (``request_origin.parse_origin``): a lowercase DNS name, a canonical
    dotted-quad IPv4 address or a bracketed IPv6 literal, then an optional
    port. Userinfo, paths, whitespace, control and non-ASCII characters,
    number-like names, trailing dots and repeated values do not parse.
    """
    if not isinstance(value, str) or not value or "," in value:
        return None
    origin = parse_origin(f"http://{value}")
    if origin is None:
        return None
    return HostIdentity(origin.host, origin.port if _EXPLICIT_PORT.search(value) else None)


def trusted_hosts(origins: Collection[Origin]) -> frozenset[HostIdentity]:
    """The Host identities of the allowed origins; nothing else is ever trusted."""
    trusted: set[HostIdentity] = set()
    for origin in origins:
        trusted.add(HostIdentity(origin.host, origin.port))
        if origin.port == DEFAULT_PORTS[origin.scheme]:
            trusted.add(HostIdentity(origin.host, None))
    return frozenset(trusted)


def evaluate_host(value: object, trusted: Collection[HostIdentity]) -> HostDecision:
    """Decide one request's Host value against the trusted identities."""
    if value is None or value == "":
        return HostDecision(False, 400, HOST_MISSING)
    if isinstance(value, str) and "," in value:
        # WSGI servers join repeated header lines with a comma.
        return HostDecision(False, 400, HOST_AMBIGUOUS)
    identity = parse_host(value)
    if identity is None:
        return HostDecision(False, 400, HOST_MALFORMED)
    if identity not in trusted:
        return HostDecision(False, 421, HOST_NOT_ALLOWED, identity)
    return HostDecision(True, 200, HOST_ALLOWED, identity)


def should_allow_read_host(
    method: object, environ: Mapping[str, object], setting: str | None
) -> HostDecision:
    """Decide whether a request may reach the application under its Host.

    Mutating methods are left to AUTH.WEB.1's gate. Every other method needs a
    Host among the identities projected from ``environ``'s listening-socket
    fields (``wsgi.url_scheme``, ``SERVER_NAME``, ``SERVER_PORT``) or from
    ``setting``, the WEB_ALLOWED_ORIGINS value, which replaces that default.
    """
    if is_mutating_method(method if isinstance(method, str) else ""):
        return HostDecision(True, 200, MUTATION_GATE)
    trusted = trusted_hosts(allowed_origins_for(environ, setting))
    return evaluate_host(environ.get("HTTP_HOST"), trusted)


def read_host_rejection(decision: HostDecision, environ: Mapping[str, object]) -> Response:
    """A minimal refusal: no HTML, cookie, redirect, echoed host or trusted-host inventory."""
    reason = _REASONS[decision.code]
    if environ.get("HTTP_SEC_FETCH_MODE") == "navigate":
        response = Response(reason + "\n", status=decision.status_code, mimetype="text/plain")
    else:
        body = json.dumps({"ok": False, "success": False, "error": reason, "error_code": decision.code})
        response = Response(body, status=decision.status_code, mimetype="application/json")
    response.headers[REJECTION_HEADER] = decision.code
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    return response


class ReadHostBoundary:
    """WSGI middleware: the one trusted-Host choke point in front of the app."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        decision = should_allow_read_host(
            environ.get("REQUEST_METHOD"), environ, os.environ.get(ALLOWED_ORIGINS_ENV)
        )
        if decision.allowed:
            return self.wsgi_app(environ, start_response)
        return read_host_rejection(decision, environ)(environ, start_response)
