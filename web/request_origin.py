"""AUTH.WEB.1: exact browser-origin identity for state-changing requests.

An origin is one (scheme, host, effective port) tuple and is compared exactly.
Hostnames are never compared alone, and localhost, 127.0.0.1 and ::1 are
distinct hosts: loopback resolution does not make them the same origin.

Default allowlist: the single origin of the listening socket, read from the
PEP 3333 fields the bundled Werkzeug server fills from the bound socket
(``wsgi.url_scheme``, ``SERVER_NAME``, ``SERVER_PORT``) -- never from the
request's Host or Origin header. A wildcard bind (0.0.0.0, ::) names no origin
a browser can use, so it yields none.

``WEB_ALLOWED_ORIGINS`` replaces that default with an explicit list of complete
origins. Deployments whose browser origin differs from the socket (published
Docker ports, reverse proxies, TLS termination, local aliases such as
localhost for a 127.0.0.1 bind) and WSGI servers that derive SERVER_NAME from
the Host header must set it.
"""
from __future__ import annotations

import ipaddress
import re
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

ALLOWED_ORIGINS_ENV = "WEB_ALLOWED_ORIGINS"
MAX_CONFIGURED_ORIGINS = 16
MAX_ORIGIN_LENGTH = 300
MAX_REPORTED_ENTRY_LENGTH = 80
DEFAULT_PORTS = {"http": 80, "https": 443}

ORIGIN_ALLOWED = "origin_allowed"
ORIGIN_MISSING = "origin_missing"
ORIGIN_NULL = "origin_null"
ORIGIN_MALFORMED = "origin_malformed"
ORIGIN_AMBIGUOUS = "origin_ambiguous"
ORIGIN_NOT_ALLOWED = "origin_not_allowed"

_SHAPE = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*)://(?P<authority>[^/?#@\\]+)")
_BRACKETED = re.compile(r"\[(?P<host>[0-9A-Fa-f:.]+)\](?::(?P<port>[0-9]{1,5}))?")
_NAMED = re.compile(r"(?P<host>[^:\[\]]+)(?::(?P<port>[0-9]{1,5}))?")
_LABEL = re.compile(r"[a-z0-9_](?:[a-z0-9_-]{0,61}[a-z0-9_])?")
_NUMBER_LIKE_LABEL = re.compile(r"0x[0-9a-f]*|[0-9]+")
_DOTTED_DECIMAL = re.compile(r"[0-9.]+")
_reported_settings: set[str] = set()


@dataclass(frozen=True, order=True)
class Origin:
    """One browser origin; equality is the (scheme, host, port) tuple."""

    scheme: str
    host: str
    port: int

    def serialize(self) -> str:
        """ASCII serialization as a browser sends it (default port omitted)."""
        host = f"[{self.host}]" if ":" in self.host else self.host
        if self.port == DEFAULT_PORTS[self.scheme]:
            return f"{self.scheme}://{host}"
        return f"{self.scheme}://{host}:{self.port}"


@dataclass(frozen=True)
class OriginDecision:
    allowed: bool
    code: str
    origin: Origin | None = None


@dataclass(frozen=True)
class AllowedOriginsConfig:
    configured: bool
    origins: frozenset[Origin]
    invalid_entries: tuple[str, ...] = ()
    ignored_over_limit: int = 0


def _ipv6_text(address: ipaddress.IPv6Address) -> str:
    """WHATWG URL serialization: hex pieces, first longest zero run (2+) as '::'.

    Unlike ``str()``, this never prints an embedded dotted IPv4 form, so the
    result matches what a browser sends in its Origin header.
    """
    pieces = [int.from_bytes(address.packed[index:index + 2], "big") for index in range(0, 16, 2)]
    start, length, index = -1, 1, 0
    while index < 8:
        end = index
        while end < 8 and pieces[end] == 0:
            end += 1
        if end - index > length:
            start, length = index, end - index
        index = max(end, index + 1)
    if start < 0:
        return ":".join(format(piece, "x") for piece in pieces)
    head = ":".join(format(piece, "x") for piece in pieces[:start])
    tail = ":".join(format(piece, "x") for piece in pieces[start + length:])
    return f"{head}::{tail}"


def _normalized_host(raw: str, bracketed: bool) -> str | None:
    if bracketed:
        try:
            return _ipv6_text(ipaddress.IPv6Address(raw))
        except ValueError:
            return None
    host = raw.lower()
    if _DOTTED_DECIMAL.fullmatch(host):
        try:
            return str(ipaddress.IPv4Address(host))
        except ValueError:
            return None
    labels = host.split(".")
    if len(host) > 253 or not all(_LABEL.fullmatch(label) for label in labels):
        return None
    if _NUMBER_LIKE_LABEL.fullmatch(labels[-1]):
        # Browsers parse these as IPv4 and send the canonical dotted quad.
        return None
    return host


def parse_origin(value: object) -> Origin | None:
    """Parse one serialized origin strictly; anything else is None (fail closed).

    Scheme and host are case-insensitive, IPv6 literals are bracketed and
    compressed, and an absent port is the scheme's default. Paths, queries,
    fragments, userinfo, wildcards, empty or zero ports, whitespace, non-ASCII
    text, trailing dots and non-canonical IPv4 spellings are rejected.
    """
    if not isinstance(value, str) or not 0 < len(value) <= MAX_ORIGIN_LENGTH:
        return None
    if not all("\x21" <= character <= "\x7e" for character in value):
        return None
    shape = _SHAPE.fullmatch(value)
    if shape is None:
        return None
    scheme = shape.group("scheme").lower()
    if scheme not in DEFAULT_PORTS:
        return None
    authority = shape.group("authority")
    bracketed = authority.startswith("[")
    parts = (_BRACKETED if bracketed else _NAMED).fullmatch(authority)
    if parts is None:
        return None
    host = _normalized_host(parts.group("host"), bracketed)
    if host is None:
        return None
    port = DEFAULT_PORTS[scheme] if parts.group("port") is None else int(parts.group("port"))
    if not 0 < port <= 65535:
        return None
    return Origin(scheme, host, port)


def evaluate_origin(values: Sequence[str], allowed: Collection[Origin]) -> OriginDecision:
    """Decide one request's Origin header value(s) against the exact allowlist."""
    values = tuple(values)
    if not values:
        return OriginDecision(False, ORIGIN_MISSING)
    if len(values) != 1:
        return OriginDecision(False, ORIGIN_AMBIGUOUS)
    raw = values[0]
    if raw == "null":
        return OriginDecision(False, ORIGIN_NULL)
    if isinstance(raw, str) and "," in raw:
        # WSGI servers join repeated headers with a comma.
        return OriginDecision(False, ORIGIN_AMBIGUOUS)
    origin = parse_origin(raw)
    if origin is None:
        return OriginDecision(False, ORIGIN_MALFORMED)
    if origin not in allowed:
        return OriginDecision(False, ORIGIN_NOT_ALLOWED, origin)
    return OriginDecision(True, ORIGIN_ALLOWED, origin)


def listening_origin(scheme: object, server_name: object, server_port: object) -> Origin | None:
    """The origin of the listening socket, or None when it names no browser origin."""
    if not all(isinstance(item, str) for item in (scheme, server_name, server_port)):
        return None
    name = server_name[1:-1] if server_name.startswith("[") and server_name.endswith("]") else server_name
    try:
        if ipaddress.ip_address(name).is_unspecified:
            return None
    except ValueError:
        pass
    host = f"[{name}]" if ":" in name else name
    return parse_origin(f"{scheme}://{host}:{server_port}") if server_port.isdigit() else None


def parse_allowed_origins_setting(raw: str | None) -> AllowedOriginsConfig:
    """Parse WEB_ALLOWED_ORIGINS: comma-separated complete origins, at most 16.

    Entries are trimmed and normalized like browser Origin headers; empty
    entries are skipped. An invalid entry is dropped and reported, never
    widened into a pattern, and never replaced by the default. Non-empty
    entries after the sixteenth are ignored and counted. A setting without any
    non-empty entry counts as not configured.
    """
    entries = [entry.strip() for entry in (raw or "").split(",")]
    entries = [entry for entry in entries if entry]
    if not entries:
        return AllowedOriginsConfig(configured=False, origins=frozenset())
    kept = entries[:MAX_CONFIGURED_ORIGINS]
    origins: set[Origin] = set()
    invalid: list[str] = []
    for entry in kept:
        origin = parse_origin(entry)
        if origin is None:
            invalid.append(entry[:MAX_REPORTED_ENTRY_LENGTH])
        else:
            origins.add(origin)
    return AllowedOriginsConfig(True, frozenset(origins), tuple(invalid), len(entries) - len(kept))


def allowed_origins_for(environ: Mapping[str, object], setting: str | None) -> frozenset[Origin]:
    """Exact origins allowed to send browser mutations to this server."""
    config = parse_allowed_origins_setting(setting)
    if config.configured:
        _report_setting_problems(setting or "", config)
        return config.origins
    origin = listening_origin(
        environ.get("wsgi.url_scheme"), environ.get("SERVER_NAME"), environ.get("SERVER_PORT")
    )
    return frozenset() if origin is None else frozenset({origin})


def _report_setting_problems(setting: str, config: AllowedOriginsConfig) -> None:
    if not (config.invalid_entries or config.ignored_over_limit) or setting in _reported_settings:
        return
    _reported_settings.add(setting)
    print(
        f"⚠️ {ALLOWED_ORIGINS_ENV}: ignored {len(config.invalid_entries)} invalid origin "
        f"entries {ascii(list(config.invalid_entries))} and {config.ignored_over_limit} "
        f"entries beyond the limit of {MAX_CONFIGURED_ORIGINS}."
    )
