"""Pure credential redaction for runtime error boundaries."""
from __future__ import annotations

from collections.abc import Iterable
import re
from urllib.parse import (
    parse_qsl,
    unquote,
    urlencode,
    urlsplit,
    urlunsplit,
)


REDACTED_DATABASE_URL = "[REDACTED_DATABASE_URL]"
_DATABASE_URL_RE = re.compile(
    r"(?i)\b(?:postgres|postgresql)"
    r"(?:\+[a-z0-9_.-]+)?://[^\s<>]+"
)
_SENSITIVE_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(?P<key>password|passwd|pwd|token|access_token|"
    r"refresh_token|api_key|apikey|secret)\b"
    r"(?P<key_quote>[\"']?)(?P<separator>\s*[:=]\s*)"
    r"(?P<value>"
    r"\"(?:\\.|[^\"\\])*\""
    r"|'(?:\\.|[^'\\])*'"
    r"|[^\s,;}\]]+"
    r")"
)


def _redact_database_url(raw_url: str) -> str:
    try:
        parsed = urlsplit(raw_url)
        scheme = parsed.scheme
        if scheme.casefold().split("+", 1)[0] not in {
            "postgres",
            "postgresql",
        }:
            return REDACTED_DATABASE_URL

        hostname = parsed.hostname
        if not hostname:
            return REDACTED_DATABASE_URL
        host = (
            f"[{hostname}]"
            if ":" in hostname and not hostname.startswith("[")
            else hostname
        )
        port = parsed.port
        host_port = f"{host}:{port}" if port is not None else host
        netloc = (
            f"***:***@{host_port}"
            if "@" in parsed.netloc
            else host_port
        )
        query_items = parse_qsl(
            parsed.query,
            keep_blank_values=True,
            strict_parsing=False,
        )
        redacted_query = urlencode(
            [(key, "***") for key, _value in query_items],
            doseq=True,
        )
        fragment = "***" if parsed.fragment else ""
        return urlunsplit(
            (
                scheme,
                netloc,
                parsed.path,
                redacted_query,
                fragment,
            )
        )
    except (TypeError, ValueError, UnicodeError):
        return REDACTED_DATABASE_URL


def _redact_urls(text: str) -> str:
    return _DATABASE_URL_RE.sub(
        lambda match: _redact_database_url(match.group(0)),
        text,
    )


def _database_url_secret_components(
    raw_secret: str,
) -> tuple[str, ...]:
    """Extract configured URL credential values, never host/path context."""
    try:
        parsed = urlsplit(raw_secret)
        if parsed.scheme.casefold().split("+", 1)[0] not in {
            "postgres",
            "postgresql",
        }:
            return ()
        if not parsed.hostname:
            return ()
        candidates = [
            parsed.username,
            parsed.password,
            parsed.fragment,
        ]
        candidates.extend(
            value
            for _key, value in parse_qsl(
                parsed.query,
                keep_blank_values=True,
                strict_parsing=False,
            )
        )
        components = {
            form
            for candidate in candidates
            if candidate
            for form in (
                str(candidate),
                unquote(str(candidate)),
            )
            if form
        }
        return tuple(
            sorted(
                components,
                key=lambda item: (-len(item), item),
            )
        )
    except (TypeError, ValueError, UnicodeError):
        return ()


def _redact_exact_component(
    text: str,
    component: str,
) -> str:
    """Mask one detached credential token without matching substrings."""
    pattern = re.compile(
        rf"(?<!\w){re.escape(component)}(?!\w)"
    )
    return pattern.sub("[REDACTED]", text)


def _redact_assignment(match: re.Match[str]) -> str:
    value = match.group("value")
    quote = (
        value[0]
        if len(value) >= 2
        and value[0] in {"'", '"'}
        and value[-1] == value[0]
        else ""
    )
    redacted_value = (
        f"{quote}[REDACTED]{quote}"
        if quote
        else "[REDACTED]"
    )
    return (
        f"{match.group('key')}"
        f"{match.group('key_quote')}"
        f"{match.group('separator')}"
        f"{redacted_value}"
    )


def redact_credentials(
    value: object,
    *,
    known_secrets: Iterable[object] = (),
) -> str:
    """Return safe text without mutating ``value`` or ``known_secrets``.

    PostgreSQL userinfo is masked and every URL query value is redacted. Exact
    configured secrets are replaced first, which also protects non-URI libpq
    DSNs. Malformed database URLs fail closed.
    """
    text = str(value)
    secret_values = (
        (known_secrets,)
        if isinstance(known_secrets, (str, bytes))
        else known_secrets
    )
    secrets_list = []
    for secret in secret_values:
        if secret is None:
            continue
        rendered = str(secret)
        if rendered:
            secrets_list.append(rendered)
    secrets = tuple(secrets_list)
    components = {
        component
        for secret in secrets
        for component in _database_url_secret_components(secret)
    }

    for secret in sorted(
        set(secrets),
        key=lambda item: (-len(item), item),
    ):
        # Exact configured values fail closed. In particular, do not retain a
        # partially parsed malformed URL whose credential suffix may survive.
        text = text.replace(secret, REDACTED_DATABASE_URL)

    text = _redact_urls(text)
    for component in sorted(
        components,
        key=lambda item: (-len(item), item),
    ):
        text = _redact_exact_component(text, component)
    return _SENSITIVE_ASSIGNMENT_RE.sub(
        _redact_assignment,
        text,
    )
