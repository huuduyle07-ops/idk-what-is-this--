"""Pure file-capability classification for direct-context planning.

The helpers in this module classify already-supplied repository inventory
metadata.  They never enumerate a repository, inspect file contents, resolve a
symlink, or grant read/write authority.  Callers that adapt a canonical
``RepositoryInventory`` must supply any metadata (size, binary detection,
generated status, and symlink validation) established by an earlier trusted
boundary.

Canonical parser support and direct textual usefulness are deliberately
independent.  ``SUPPORTED_EXTENSIONS`` continues to describe canonical parser
and index support only; a safe unsupported text file can be classified as
``direct_context_only`` without changing indexing behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Iterable, Iterator, Mapping

from core.repo_ignore import (
    ANY_DEPTH_HARD_EXCLUDES,
    ROOT_ONLY_HARD_EXCLUDES,
)
from core.repository_path_policy import is_safe_repository_relative_path
from core.security import BLACKLIST
from core.source_file_policy import SUPPORTED_EXTENSIONS


READABILITY_STATES = (
    "readable_text",
    "readable_limited",
    "opaque_binary",
    "unreadable",
    "sensitive",
)

PARSER_SUPPORT_STATES = (
    "supported",
    "partial",
    "unsupported",
    "not_applicable",
)

INDEXABILITY_STATES = (
    "canonical_indexable",
    "direct_context_only",
    "not_indexable",
)

EDITABILITY_STATES = (
    "editable",
    "editable_with_review",
    "read_only",
    "generated_do_not_edit",
    "sensitive_requires_approval",
    "outside_scope",
    "opaque",
    "forbidden",
)

READ_POLICY_STATES = (
    "auto_read_allowed",
    "explicit_human_approval_required",
    "hard_no_auto_read",
)

UNDERSTANDING_CONFIDENCE_STATES = (
    "parsed",
    "partial",
    "raw_text_only",
    "unknown",
)


# Extensions that are commonly text even though the canonical parser/index
# allow-list does not necessarily support them.  This does not alter
# SUPPORTED_EXTENSIONS and conveys no AST or dependency claim.
SAFE_TEXT_EXTENSIONS = frozenset(
    {
        ".adoc",
        ".cfg",
        ".conf",
        ".csv",
        ".editorconfig",
        ".ex",
        ".exs",
        ".gql",
        ".graphql",
        ".ini",
        ".lock",
        ".php",
        ".proto",
        ".properties",
        ".ps1",
        ".rb",
        ".r",
        ".rst",
        ".scala",
        ".sh",
        ".sql",
        ".svelte",
        ".swift",
        ".tex",
        ".toml",
        ".vue",
        ".xml",
        ".yaml",
        ".yml",
        ".zsh",
    }
)

SAFE_TEXT_FILENAMES = frozenset(
    {
        "dockerfile",
        "gemfile",
        "makefile",
        "procfile",
        "rakefile",
    }
)

LIMITED_DOCUMENT_EXTENSIONS = frozenset({".pdf", ".docx"})

OPAQUE_BINARY_EXTENSIONS = frozenset(
    {
        ".7z",
        ".a",
        ".avi",
        ".bin",
        ".bmp",
        ".class",
        ".dll",
        ".dylib",
        ".exe",
        ".gif",
        ".gz",
        ".ico",
        ".jar",
        ".jpeg",
        ".jpg",
        ".mov",
        ".mp3",
        ".mp4",
        ".o",
        ".obj",
        ".png",
        ".pyc",
        ".so",
        ".tar",
        ".tiff",
        ".wav",
        ".webp",
        ".woff",
        ".woff2",
        ".zip",
    }
)

PRIVATE_KEY_EXTENSIONS = frozenset(
    {".key", ".pem", ".p12", ".pfx", ".jks", ".keystore"}
)

PRIVATE_KEY_NAMES = frozenset(
    {
        "id_dsa",
        "id_ecdsa",
        "id_ed25519",
        "id_rsa",
        "openssh_key",
        "private_key",
    }
)

CREDENTIAL_STORE_NAMES = frozenset(
    {
        "cookies",
        "cookies.sqlite",
        "credentials.db",
        "credentials.json",
        "keychain.db",
        "keyring.db",
        "login data",
        "logins.json",
        "passwords.csv",
        "session.db",
        "session.json",
        "sessions.sqlite",
        "sessions.json",
        "web data",
    }
)

DATABASE_BINARY_EXTENSIONS = frozenset(
    {".bak", ".db", ".dump", ".dmp", ".sqlite", ".sqlite3"}
)

_GENERATED_PARTS = frozenset({"generated", "vendor"})
_GENERATED_NAME_MARKERS = (".generated.", ".min.", "_generated.")
AST_PARSED_EXTENSIONS = frozenset(
    {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".css",
        ".cxx",
        ".go",
        ".h",
        ".hpp",
        ".htm",
        ".html",
        ".hxx",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".kts",
        ".mjs",
        ".cjs",
        ".py",
        ".rs",
        ".sass",
        ".scss",
        ".ts",
        ".tsx",
    }
)


class _RecordMapping(Mapping[str, Any]):
    """Small immutable-record mapping facade used by public result objects."""

    def as_dict(self) -> dict[str, Any]:  # pragma: no cover - abstract helper
        raise NotImplementedError

    def __getitem__(self, key: str) -> Any:
        return self.as_dict()[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self.as_dict())

    def __len__(self) -> int:
        return len(self.as_dict())


@dataclass(frozen=True, slots=True)
class FileCapability(_RecordMapping):
    """Independent, immutable capability states for one inventory member."""

    path: str
    size_bytes: int | None
    readability: str
    parser_support: str
    indexability: str
    direct_read_allowed: bool
    read_policy: str
    editability: str
    understanding_confidence: str
    repository_contained: bool
    symlink_escape: bool
    generated: bool
    vendor: bool
    authoritative_source: str | None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.readability not in READABILITY_STATES:
            raise ValueError(f"unknown readability state: {self.readability}")
        if self.parser_support not in PARSER_SUPPORT_STATES:
            raise ValueError(f"unknown parser-support state: {self.parser_support}")
        if self.indexability not in INDEXABILITY_STATES:
            raise ValueError(f"unknown indexability state: {self.indexability}")
        if self.editability not in EDITABILITY_STATES:
            raise ValueError(f"unknown editability state: {self.editability}")
        if self.read_policy not in READ_POLICY_STATES:
            raise ValueError(f"unknown read-policy state: {self.read_policy}")
        if self.understanding_confidence not in UNDERSTANDING_CONFIDENCE_STATES:
            raise ValueError(
                "unknown understanding-confidence state: "
                f"{self.understanding_confidence}"
            )
        if self.size_bytes is not None and self.size_bytes < 0:
            raise ValueError("size_bytes must be non-negative or None")
        if tuple(sorted(set(self.reasons))) != self.reasons:
            raise ValueError("capability reasons must be unique and deterministic")
        if self.direct_read_allowed and (
            self.read_policy != "auto_read_allowed"
            or self.readability not in {"readable_text", "readable_limited"}
            or not self.repository_contained
            or self.symlink_escape
            or self.editability
            in {
                "sensitive_requires_approval",
                "outside_scope",
                "opaque",
                "forbidden",
            }
        ):
            raise ValueError("direct-read authority conflicts with capability gates")
        if self.editability in {"outside_scope", "opaque", "forbidden"} and (
            self.read_policy != "hard_no_auto_read" or self.direct_read_allowed
        ):
            raise ValueError("hard editability gate must disable automatic reads")
        if self.editability == "sensitive_requires_approval" and (
            self.read_policy != "explicit_human_approval_required"
            or self.direct_read_allowed
        ):
            raise ValueError("sensitive editability must require human approval")
        if self.readability == "sensitive" and (
            self.read_policy != "explicit_human_approval_required"
            or self.editability != "sensitive_requires_approval"
            or self.direct_read_allowed
        ):
            raise ValueError("sensitive readability must require human approval")

    @property
    def requires_human_approval(self) -> bool:
        return self.read_policy == "explicit_human_approval_required"

    @property
    def hard_excluded(self) -> bool:
        return self.read_policy == "hard_no_auto_read"

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size_bytes": self.size_bytes,
            "readability": self.readability,
            "parser_support": self.parser_support,
            "indexability": self.indexability,
            "direct_read_allowed": self.direct_read_allowed,
            "read_policy": self.read_policy,
            "editability": self.editability,
            "understanding_confidence": self.understanding_confidence,
            "repository_contained": self.repository_contained,
            "symlink_escape": self.symlink_escape,
            "generated": self.generated,
            "vendor": self.vendor,
            "authoritative_source": self.authoritative_source,
            "reasons": list(self.reasons),
        }


def normalize_repository_relative_path(value: str | PurePosixPath) -> str | None:
    """Return one portable repository-relative spelling, or ``None``.

    This is input-shape validation, not a filesystem containment check.  A
    trusted inventory boundary must separately assert ``repository_contained``
    and ``symlink_escape`` metadata.
    """

    rendered = str(value)
    return rendered if is_safe_repository_relative_path(rendered) else None


def _mapping_value(
    raw: str | PurePosixPath | Mapping[str, Any],
    key: str,
    explicit: Any,
    default: Any,
) -> Any:
    if explicit is not None:
        return explicit
    if isinstance(raw, Mapping) and key in raw:
        return raw[key]
    return default


def _raw_path(raw: str | PurePosixPath | Mapping[str, Any]) -> str:
    if isinstance(raw, Mapping):
        value = raw.get("path", raw.get("relative_path", ""))
    else:
        value = raw
    if hasattr(value, "as_posix"):
        return value.as_posix()
    return str(value)


def _is_hard_excluded_path(path: str) -> bool:
    parts = tuple(part.casefold() for part in PurePosixPath(path).parts)
    any_depth = {name.casefold() for name in ANY_DEPTH_HARD_EXCLUDES}
    root_only = {name.casefold() for name in ROOT_ONLY_HARD_EXCLUDES}
    return any(part in any_depth for part in parts) or (
        bool(parts) and parts[0] in root_only
    )


def _sensitive_policy(path: str) -> tuple[str | None, str | None]:
    """Return ``(read_policy, reason)`` for path-only sensitive classes."""

    pure = PurePosixPath(path)
    name = pure.name.casefold()
    suffix = pure.suffix.casefold()
    parts = {part.casefold() for part in pure.parts}

    if name in {".env.example", ".env.sample", ".env.template"}:
        return None, None
    if name == ".env" or name.startswith(".env."):
        return (
            "explicit_human_approval_required",
            "environment file requires explicit human approval",
        )
    if parts & {".aws", ".gnupg", ".ssh", "credential-store", "credentials", "secrets"}:
        return "hard_no_auto_read", "credential or secret store is forbidden"
    if suffix in PRIVATE_KEY_EXTENSIONS or name in PRIVATE_KEY_NAMES:
        return "hard_no_auto_read", "private key material is forbidden"
    if name in CREDENTIAL_STORE_NAMES:
        return "hard_no_auto_read", "credential or browser store is forbidden"
    if suffix in DATABASE_BINARY_EXTENSIONS:
        return (
            "hard_no_auto_read",
            "binary database or dump requires an explicit safe adapter",
        )
    if parts & {
        "browser",
        "browser-data",
        "browser-profile",
        "browser-profiles",
        "session-data",
    }:
        return "hard_no_auto_read", "browser or session data is forbidden"
    canonical_blacklist = {item.casefold() for item in BLACKLIST}
    if name in canonical_blacklist:
        return "hard_no_auto_read", "existing security policy forbids this file"
    if any(
        marker in name
        for marker in ("secret", "credential", "password", "token", "auth_key")
    ):
        return "hard_no_auto_read", "existing credential-name policy forbids this file"
    if (
        name.startswith(".")
        and name not in {".github"}
        and suffix not in {".py", ".md", ".txt", ".json"}
    ):
        return "hard_no_auto_read", "existing dotfile security policy forbids this file"
    return None, None


def classify_repository_path_read_policy(path: str) -> tuple[str, str | None]:
    """Classify a supplied relative path/prefix without reading the filesystem."""

    normalized = normalize_repository_relative_path(path.rstrip("/"))
    if normalized is None:
        return "hard_no_auto_read", "path is not a safe repository-relative path"
    policy, reason = _sensitive_policy(normalized)
    return policy or "auto_read_allowed", reason


def classify_file_capability(
    path: str | PurePosixPath | Mapping[str, Any],
    *,
    size_bytes: int | None = None,
    readability: str | None = None,
    parser_support: str | None = None,
    is_binary: bool | None = None,
    is_readable: bool | None = None,
    text_hint: bool | None = None,
    repository_contained: bool | None = None,
    symlink_escape: bool | None = None,
    generated: bool | None = None,
    vendor: bool | None = None,
    policy_forbidden: bool | None = None,
    sensitive_policy: str | None = None,
    editability: str | None = None,
    authoritative_source: str | None = None,
    supported_extensions: Iterable[str] | None = None,
) -> FileCapability:
    """Classify supplied file metadata without touching the filesystem.

    ``path`` may be a relative path or a mapping with matching keyword fields.
    Explicit keyword arguments take precedence over mapping values.  Unknown
    file sizes remain unknown; this helper never calls ``stat``.
    """

    raw_path = _raw_path(path)
    normalized = normalize_repository_relative_path(raw_path)
    rendered = normalized if normalized is not None else "<invalid-relative-path>"

    mapped_size = _mapping_value(path, "size_bytes", size_bytes, None)
    if mapped_size is not None:
        if isinstance(mapped_size, bool) or not isinstance(mapped_size, int):
            raise TypeError("size_bytes must be an integer or None")
        if mapped_size < 0:
            raise ValueError("size_bytes must be non-negative or None")

    contained = bool(
        _mapping_value(path, "repository_contained", repository_contained, True)
    )
    escaped = bool(_mapping_value(path, "symlink_escape", symlink_escape, False))
    forbidden_by_policy = bool(
        _mapping_value(path, "policy_forbidden", policy_forbidden, False)
    )

    pure = PurePosixPath(rendered)
    suffix = pure.suffix.casefold()
    name = pure.name.casefold()
    canonical_supported = frozenset(
        str(extension).casefold() for extension in SUPPORTED_EXTENSIONS
    )
    if supported_extensions is not None:
        supplied_supported = frozenset(
            str(extension).casefold() for extension in supported_extensions
        )
        if supplied_supported != canonical_supported:
            raise ValueError(
                "supported_extensions must match canonical SUPPORTED_EXTENSIONS exactly"
            )
    supported = canonical_supported

    generated_from_path = (
        any(part.casefold() in _GENERATED_PARTS for part in pure.parts)
        or any(marker in name for marker in _GENERATED_NAME_MARKERS)
    )
    generated_value = generated_from_path or bool(
        _mapping_value(path, "generated", generated, False)
    )
    vendor_from_path = any(
        part.casefold() in {"vendor", "third_party"} for part in pure.parts
    )
    vendor_value = vendor_from_path or bool(
        _mapping_value(path, "vendor", vendor, False)
    )

    reasons: set[str] = set()
    hard_boundary = False
    if normalized is None or not contained:
        hard_boundary = True
        contained = False
        reasons.add("path is not a normalized repository-contained relative path")
    if escaped:
        hard_boundary = True
        reasons.add("symlink target escapes the repository root")
    if normalized is not None and _is_hard_excluded_path(normalized):
        hard_boundary = True
        reasons.add("path matches a non-overridable repository exclusion")
    if forbidden_by_policy:
        hard_boundary = True
        reasons.add("repository policy explicitly forbids the file")

    requested_sensitive = _mapping_value(
        path, "sensitive_policy", sensitive_policy, None
    )
    if (
        requested_sensitive is None
        and isinstance(path, Mapping)
        and "read_policy" in path
    ):
        requested_sensitive = path["read_policy"]
    detected_policy, detected_reason = _sensitive_policy(rendered)
    if requested_sensitive is not None and str(requested_sensitive) not in READ_POLICY_STATES:
        raise ValueError(f"unknown sensitive/read policy: {requested_sensitive}")
    policy_rank = {
        "": 0,
        "auto_read_allowed": 0,
        "explicit_human_approval_required": 1,
        "hard_no_auto_read": 2,
    }
    policy_options = (str(requested_sensitive or ""), str(detected_policy or ""))
    read_policy = max(policy_options, key=lambda item: policy_rank[item])
    if detected_reason:
        reasons.add(detected_reason)
    if hard_boundary:
        read_policy = "hard_no_auto_read"

    extension_is_binary = (
        suffix in OPAQUE_BINARY_EXTENSIONS
        or suffix in DATABASE_BINARY_EXTENSIONS
        or suffix in PRIVATE_KEY_EXTENSIONS
    )
    binary_value = bool(
        _mapping_value(
            path,
            "is_binary",
            is_binary,
            extension_is_binary,
        )
    )
    readable_value = bool(
        _mapping_value(path, "is_readable", is_readable, True)
    )
    text_value = bool(
        _mapping_value(
            path,
            "text_hint",
            text_hint,
            suffix in supported
            or suffix in SAFE_TEXT_EXTENSIONS
            or name in SAFE_TEXT_FILENAMES
            or name.startswith(".env."),
        )
    )

    requested_readability = _mapping_value(
        path, "readability", readability, None
    )
    if (
        requested_readability is not None
        and str(requested_readability) not in READABILITY_STATES
    ):
        raise ValueError(f"unknown readability state: {requested_readability}")
    if read_policy == "explicit_human_approval_required":
        resolved_readability = "sensitive"
    elif not readable_value:
        resolved_readability = "unreadable"
    elif extension_is_binary and suffix not in LIMITED_DOCUMENT_EXTENSIONS:
        resolved_readability = "opaque_binary"
        if requested_readability not in {None, "opaque_binary"}:
            reasons.add("conflicting text-readability hint failed closed")
    elif binary_value and suffix not in LIMITED_DOCUMENT_EXTENSIONS:
        resolved_readability = "opaque_binary"
        if requested_readability not in {None, "opaque_binary"}:
            reasons.add("conflicting text-readability hint failed closed")
    elif requested_readability is not None:
        resolved_readability = str(requested_readability)
    elif suffix in LIMITED_DOCUMENT_EXTENSIONS:
        resolved_readability = "readable_limited"
    elif text_value:
        resolved_readability = "readable_text"
    else:
        resolved_readability = "opaque_binary"

    if resolved_readability == "sensitive":
        if read_policy != "hard_no_auto_read":
            read_policy = "explicit_human_approval_required"
        reasons.add("sensitive readability requires explicit human approval")
    elif resolved_readability in {"opaque_binary", "unreadable"}:
        read_policy = "hard_no_auto_read"
        reasons.add(
            "file is opaque binary" if resolved_readability == "opaque_binary" else "file is unreadable"
        )
    elif not read_policy:
        read_policy = "auto_read_allowed"

    requested_editability = _mapping_value(path, "editability", editability, None)
    if (
        requested_editability is not None
        and str(requested_editability) not in EDITABILITY_STATES
    ):
        raise ValueError(f"unknown editability state: {requested_editability}")
    requested_editability_text = (
        str(requested_editability) if requested_editability is not None else None
    )
    if requested_editability_text in {"outside_scope", "forbidden"}:
        read_policy = "hard_no_auto_read"
        reasons.add("caller-supplied editability state forbids automatic reading")
    elif requested_editability_text == "opaque":
        read_policy = "hard_no_auto_read"
        resolved_readability = "opaque_binary"
        reasons.add("caller-supplied editability state marks the file opaque")
    elif requested_editability_text == "sensitive_requires_approval":
        if read_policy != "hard_no_auto_read":
            read_policy = "explicit_human_approval_required"
            resolved_readability = "sensitive"
        reasons.add("caller-supplied editability state requires human approval")

    if suffix in AST_PARSED_EXTENSIONS:
        detected_parser = "supported"
    elif suffix in supported:
        detected_parser = "partial"
    elif resolved_readability in {"readable_text", "readable_limited"}:
        detected_parser = "unsupported"
    else:
        detected_parser = "not_applicable"

    requested_parser = _mapping_value(path, "parser_support", parser_support, None)
    if requested_parser is None:
        resolved_parser = detected_parser
    else:
        requested_parser_text = str(requested_parser)
        if requested_parser_text not in PARSER_SUPPORT_STATES:
            raise ValueError(f"unknown parser-support state: {requested_parser_text}")
        parser_rank = {
            "not_applicable": 0,
            "unsupported": 1,
            "partial": 2,
            "supported": 3,
        }
        resolved_parser = min(
            (detected_parser, requested_parser_text),
            key=lambda value: parser_rank[value],
        )
        if resolved_parser != requested_parser_text:
            reasons.add(
                "parser-support hint exceeded canonical parser metadata and was reduced"
            )

    direct_read_allowed = (
        read_policy == "auto_read_allowed"
        and resolved_readability in {"readable_text", "readable_limited"}
        and contained
        and not escaped
    )

    if (
        suffix in supported
        and resolved_readability in {"readable_text", "readable_limited"}
        and read_policy == "auto_read_allowed"
    ):
        indexability = "canonical_indexable"
    elif direct_read_allowed:
        indexability = "direct_context_only"
        if resolved_parser == "unsupported":
            reasons.add(
                "safe text is usable as raw direct context without parser guarantees"
            )
    else:
        indexability = "not_indexable"
    if direct_read_allowed and resolved_parser == "partial":
        reasons.add(
            "safe text is usable as raw direct context without complete parser guarantees"
        )

    if hard_boundary:
        resolved_editability = "outside_scope" if not contained else "forbidden"
    elif read_policy == "hard_no_auto_read" and detected_policy == "hard_no_auto_read":
        resolved_editability = "forbidden"
    elif requested_editability_text in {
        "outside_scope",
        "opaque",
        "forbidden",
    }:
        resolved_editability = requested_editability_text
    elif (
        requested_editability_text == "sensitive_requires_approval"
        and read_policy != "hard_no_auto_read"
    ):
        resolved_editability = requested_editability_text
    elif read_policy == "hard_no_auto_read":
        resolved_editability = (
            "opaque"
            if resolved_readability in {"opaque_binary", "unreadable"}
            else "forbidden"
        )
    elif read_policy == "explicit_human_approval_required":
        resolved_editability = "sensitive_requires_approval"
    elif generated_value or vendor_value:
        resolved_editability = "generated_do_not_edit"
    elif requested_editability_text is not None:
        resolved_editability = requested_editability_text
    elif resolved_parser in {"unsupported", "partial"} or name in {
        ".env.example",
        ".env.sample",
        ".env.template",
    }:
        resolved_editability = "editable_with_review"
    else:
        resolved_editability = "editable"

    if resolved_parser == "supported":
        confidence = "parsed"
    elif resolved_parser == "partial":
        confidence = "partial"
    elif resolved_parser == "unsupported" and direct_read_allowed:
        confidence = "raw_text_only"
    else:
        confidence = "unknown"

    source_value = _mapping_value(
        path, "authoritative_source", authoritative_source, None
    )
    source_normalized = (
        normalize_repository_relative_path(str(source_value))
        if source_value
        else None
    )
    if source_value and source_normalized is None:
        reasons.add("authoritative source hint was not a safe relative path")

    return FileCapability(
        path=rendered,
        size_bytes=mapped_size,
        readability=resolved_readability,
        parser_support=resolved_parser,
        indexability=indexability,
        direct_read_allowed=direct_read_allowed,
        read_policy=read_policy,
        editability=resolved_editability,
        understanding_confidence=confidence,
        repository_contained=contained,
        symlink_escape=escaped,
        generated=generated_value,
        vendor=vendor_value,
        authoritative_source=source_normalized,
        reasons=tuple(sorted(reasons)),
    )


def classify_file_capabilities(
    records: Iterable[str | PurePosixPath | Mapping[str, Any]],
    *,
    supported_extensions: Iterable[str] | None = None,
) -> tuple[FileCapability, ...]:
    """Classify an already-supplied inventory with strict deterministic order."""

    materialized = tuple(
        classify_file_capability(
            record,
            supported_extensions=supported_extensions,
        )
        for record in records
    )
    paths = [item.path.casefold() for item in materialized]
    if len(paths) != len(set(paths)):
        raise ValueError("inventory contains duplicate canonical paths")
    expected = tuple(sorted(materialized, key=lambda item: item.path))
    if materialized != expected:
        raise ValueError("inventory records must use deterministic path ordering")
    return materialized


def capability_from_repository_entry(
    entry: Any,
    **metadata: Any,
) -> FileCapability:
    """Adapt one existing inventory entry without reading metadata or contents."""

    relative = getattr(entry, "relative_path", None)
    if relative is None:
        raise TypeError("entry must expose relative_path")
    rendered = relative.as_posix() if hasattr(relative, "as_posix") else str(relative)
    return classify_file_capability(rendered, **metadata)
