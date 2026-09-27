"""PATCH.BASIS.LIVE.1 — typed reasons to consider a repository change.

This module answers only the first of three separate questions:

``why``
    Is there a legitimate typed basis for considering a patch?

``where``
    Are the proposed targets backed by source this run actually acquired?

``may write``
    Did patch safety, runtime authorization and human approval permit mutation?

Only the first question is represented here.  In particular, a
``grounded_defect`` and an ``explicit_change_request`` are not write authority.

Failure relevance is deliberately bounded.  It reads only exact failure
locations already present in the validation receipt/output and resolves calls
only against the already-localized candidate set.  It performs no repository
search, graph walk, index operation, model call or network call.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Sequence


PATCH_BASIS_NONE = "none"
PATCH_BASIS_GROUNDED_DEFECT = "grounded_defect"
PATCH_BASIS_EXPLICIT_CHANGE_REQUEST = "explicit_change_request"
PATCH_BASIS_UNRESOLVED = "unresolved"

PATCH_BASES: tuple[str, ...] = (
    PATCH_BASIS_NONE,
    PATCH_BASIS_GROUNDED_DEFECT,
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_UNRESOLVED,
)
LEGITIMATE_PATCH_BASES: frozenset[str] = frozenset(
    {PATCH_BASIS_GROUNDED_DEFECT, PATCH_BASIS_EXPLICIT_CHANGE_REQUEST}
)

PATCH_BASIS_SOURCE_UNAVAILABLE = "unavailable"
PATCH_BASIS_SOURCE_EXECUTED_FAILURE = "executed_validation_failure"
PATCH_BASIS_SOURCE_BOUNDED_REPRODUCTION = "bounded_defect_reproduction"
PATCH_BASIS_SOURCE_EXPLICIT_REQUEST = "preserved_explicit_user_request"

FAILURE_BINDING_DIRECT_LOCATION = "direct_location"
FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE = "direct_executed_reference"
FAILURE_BINDING_EXPLICIT_CHANGE_REQUEST = "explicit_change_request"
FAILURE_BINDING_BOUNDED_REPRODUCTION = "bounded_reproduction"
FAILURE_BINDING_UNAVAILABLE = "unavailable"
FAILURE_BINDING_AMBIGUOUS = "ambiguous"

FAILURE_BINDING_KINDS: tuple[str, ...] = (
    FAILURE_BINDING_DIRECT_LOCATION,
    FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE,
    FAILURE_BINDING_EXPLICIT_CHANGE_REQUEST,
    FAILURE_BINDING_BOUNDED_REPRODUCTION,
    FAILURE_BINDING_UNAVAILABLE,
    FAILURE_BINDING_AMBIGUOUS,
)

_PYTHON_TRACEBACK_LOCATION = re.compile(
    r'File\s+["\'](?P<file>[^"\']+?\.py)["\']\s*,\s*line\s+(?P<line>\d+)',
    re.IGNORECASE,
)
_PYTEST_LOCATION = re.compile(
    r"(?m)^(?P<file>(?:[A-Za-z]:[\\/][^:\r\n]+|[^:\r\n]*?\.py))"
    r":(?P<line>\d+)(?::(?P<col>\d+))?(?=[:\s])"
)
_EXPLICIT_ACROSS_SCOPE = re.compile(
    r"\bacross\s+(?P<scope>[^.;\r\n]+)", re.IGNORECASE
)
_SCOPE_SPLIT = re.compile(r"\s*(?:/|,|\band\b|&)\s*", re.IGNORECASE)
_SCOPE_WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*")
_SCOPE_STOP_WORDS = frozenset(
    {"a", "an", "the", "all", "both", "support", "layer", "layers"}
)


def normalize_patch_basis(value: Any) -> str:
    """Return a supported categorical value, failing closed to ``none``."""

    normalized = str(value or "").strip().lower()
    return normalized if normalized in PATCH_BASES else PATCH_BASIS_NONE


def has_legitimate_patch_basis(value: Any) -> bool:
    return normalize_patch_basis(value) in LEGITIMATE_PATCH_BASES


def normalize_repo_relative_path(value: Any) -> str:
    text = str(value or "").strip().replace("\\", "/")
    while text.startswith("./"):
        text = text[2:]
    return text.lower()


@dataclass(frozen=True, slots=True)
class LocalizedCandidate:
    """One already-localized candidate; never discovered by this module."""

    file: str
    symbol: str
    rank: int

    @property
    def normalized_file(self) -> str:
        return normalize_repo_relative_path(self.file)

    @property
    def identity(self) -> str:
        return f"{self.normalized_file}::{self.symbol}"


@dataclass(frozen=True, slots=True)
class FailureLocation:
    file: str
    line: int | None
    col: int | None = None
    kind: str = ""
    symbol_hint: str = ""

    @property
    def normalized_file(self) -> str:
        return normalize_repo_relative_path(self.file)

    def as_dict(self) -> dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "col": self.col,
            "kind": self.kind or None,
        }


@dataclass(frozen=True, slots=True)
class FailureRelevanceBinding:
    """A bounded binding result; it does not assert sole mathematical cause."""

    kind: str = FAILURE_BINDING_UNAVAILABLE
    candidate_file: str = ""
    candidate_symbol: str = ""
    location: FailureLocation | None = None
    ambiguous_candidates: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.kind not in FAILURE_BINDING_KINDS:
            raise ValueError(f"unsupported failure binding kind: {self.kind!r}")

    @property
    def bound(self) -> bool:
        return self.kind in {
            FAILURE_BINDING_DIRECT_LOCATION,
            FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE,
        }

    @property
    def candidate_binding(self) -> dict[str, str] | None:
        if not self.bound:
            return None
        return {
            "file": self.candidate_file,
            "symbol": self.candidate_symbol,
            "relation": "executed_failure_bound",
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "failure_binding_kind": self.kind,
            "failure_binding_location": (
                self.location.as_dict() if self.location is not None else None
            ),
            "candidate_binding": self.candidate_binding,
            "ambiguous_candidates": list(self.ambiguous_candidates),
        }


def _safe_relative_file(repo: Path, raw: Any) -> tuple[str, Path] | None:
    text = str(raw or "").strip().strip('"\'')
    if not text:
        return None
    try:
        supplied = Path(text)
        resolved = supplied.resolve() if supplied.is_absolute() else (repo / supplied).resolve()
        relative = resolved.relative_to(repo).as_posix()
    except (OSError, ValueError):
        return None
    if not resolved.is_file():
        return None
    return relative, resolved


def _positive_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def known_failure_locations(
    repo_path: str | Path,
    preflight: Mapping[str, Any],
) -> tuple[FailureLocation, ...]:
    """Return bounded exact Python/file locations already named by validation.

    Typed locations remain authoritative.  The two output parsers cover the
    location forms emitted by Python tracebacks and pytest, which OPS.VALIDATE.1
    already captured but its cross-language diagnostics helper does not project.
    No path is guessed and no directory is enumerated.
    """

    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError):
        return ()
    if not repo.is_dir():
        return ()

    result: list[FailureLocation] = []
    seen: set[tuple[str, int | None, int | None, str]] = set()

    def add(raw_file: Any, raw_line: Any, raw_col: Any, kind: Any, hint: Any = "") -> None:
        if len(result) >= 16:
            return
        safe = _safe_relative_file(repo, raw_file)
        if safe is None:
            return
        relative, _ = safe
        line = _positive_int(raw_line)
        col = _positive_int(raw_col)
        kind_text = str(kind or "")[:64]
        key = (normalize_repo_relative_path(relative), line, col, kind_text)
        if key in seen:
            return
        seen.add(key)
        result.append(
            FailureLocation(
                file=relative,
                line=line,
                col=col,
                kind=kind_text,
                symbol_hint=str(hint or "")[:160],
            )
        )

    raw_locations = preflight.get("locations") or ()
    if isinstance(raw_locations, Sequence) and not isinstance(
        raw_locations, (str, bytes)
    ):
        for raw in raw_locations[:16]:
            if isinstance(raw, Mapping):
                add(
                    raw.get("file"),
                    raw.get("line"),
                    raw.get("col"),
                    raw.get("kind"),
                    raw.get("symbol_hint"),
                )

    output = str(preflight.get("output") or "")[:12000]
    for match in _PYTHON_TRACEBACK_LOCATION.finditer(output):
        add(match.group("file"), match.group("line"), None, "python_traceback")
    for match in _PYTEST_LOCATION.finditer(output):
        add(
            match.group("file"),
            match.group("line"),
            match.group("col"),
            "pytest_failure",
        )
    return tuple(result)


def _module_name_for_file(relative_file: str) -> str:
    normalized = normalize_repo_relative_path(relative_file)
    if normalized.endswith(".py"):
        normalized = normalized[:-3]
    if normalized.endswith("/__init__"):
        normalized = normalized[: -len("/__init__")]
    return normalized.replace("/", ".")


def _resolved_import_module(
    module: str | None,
    level: int,
    failing_file: str,
) -> str:
    base = str(module or "").strip(".")
    if level <= 0:
        return base
    package_parts = _module_name_for_file(failing_file).split(".")[:-1]
    keep = max(0, len(package_parts) - (level - 1))
    prefix = package_parts[:keep]
    if base:
        prefix.extend(base.split("."))
    return ".".join(part for part in prefix if part)


def _python_import_bindings(
    tree: ast.AST,
    failing_file: str,
) -> tuple[dict[str, tuple[str, str]], dict[str, str]]:
    direct: dict[str, tuple[str, str]] = {}
    modules: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = _resolved_import_module(node.module, node.level, failing_file)
            for alias in node.names:
                if alias.name == "*":
                    continue
                direct[alias.asname or alias.name] = (module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".", 1)[0]
                modules[local] = alias.name if alias.asname else local
    return direct, modules


def _attribute_parts(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Name):
        return (node.id,)
    if isinstance(node, ast.Attribute):
        return _attribute_parts(node.value) + (node.attr,)
    return ()


def _candidate_matches_module(
    candidate: LocalizedCandidate,
    module: str,
    symbol: str,
) -> bool:
    return (
        candidate.symbol == symbol
        and _module_name_for_file(candidate.file) == module.lower()
    )


def _calls_at_line(tree: ast.AST, line: int) -> tuple[ast.Call, ...]:
    containers: list[ast.AST] = []
    for node in ast.walk(tree):
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", start)
        if isinstance(node, ast.stmt) and start is not None and end is not None:
            if start <= line <= end:
                containers.append(node)
    if not containers:
        return ()
    containers.sort(
        key=lambda node: (
            int(getattr(node, "end_lineno", line)) - int(getattr(node, "lineno", line)),
            int(getattr(node, "col_offset", 0)),
        )
    )
    return tuple(
        child for child in ast.walk(containers[0]) if isinstance(child, ast.Call)
    )


def _call_candidate_matches(
    call: ast.Call,
    candidates: Sequence[LocalizedCandidate],
    failing_file: str,
    direct_imports: Mapping[str, tuple[str, str]],
    module_imports: Mapping[str, str],
) -> tuple[LocalizedCandidate, ...]:
    func = call.func
    matches: list[LocalizedCandidate] = []
    if isinstance(func, ast.Name):
        imported = direct_imports.get(func.id)
        if imported is not None:
            module, imported_symbol = imported
            matches = [
                candidate
                for candidate in candidates
                if _candidate_matches_module(candidate, module, imported_symbol)
            ]
        else:
            # The existing bounded candidate set is the resolver universe.  One
            # exact symbol match is deterministic; two are an explicit refusal.
            matches = [
                candidate for candidate in candidates if candidate.symbol == func.id
            ]
            same_file = [
                candidate
                for candidate in matches
                if candidate.normalized_file
                == normalize_repo_relative_path(failing_file)
            ]
            if same_file:
                matches = same_file
    elif isinstance(func, ast.Attribute):
        parts = _attribute_parts(func)
        if len(parts) >= 2 and parts[0] in module_imports:
            module = module_imports[parts[0]]
            if len(parts) > 2:
                module = ".".join((module, *parts[1:-1]))
            matches = [
                candidate
                for candidate in candidates
                if _candidate_matches_module(candidate, module, parts[-1])
            ]

    unique: dict[str, LocalizedCandidate] = {}
    for candidate in matches:
        unique[candidate.identity] = candidate
    return tuple(sorted(unique.values(), key=lambda item: (item.rank, item.identity)))


def _strong_direct_location(location: FailureLocation, candidate: LocalizedCandidate) -> bool:
    hint = location.symbol_hint.split(".")[-1]
    if hint and hint == candidate.symbol:
        return True
    kind = location.kind.lower()
    return "compiler" in kind or "syntax" in kind


def _output_names_candidate(preflight: Mapping[str, Any], candidate: LocalizedCandidate) -> bool:
    wanted = re.escape(candidate.normalized_file)
    normalized = str(preflight.get("output") or "").replace("\\", "/").lower()
    return bool(re.search(rf"(?<![a-z0-9_.-]){wanted}(?=[:\s\"'()])", normalized))


def bind_executed_failure_to_candidates(
    *,
    repo_path: str | Path,
    preflight: Mapping[str, Any],
    candidates: Iterable[LocalizedCandidate],
) -> FailureRelevanceBinding:
    """Bind one executed failure to one candidate without causal overclaim.

    Resolution order preserves strong direct compiler/symbol bindings, then
    prefers an actual call in an assertion/test expression over a generic
    same-file candidate, then falls back to the historical exact-path binding.
    Graph edges, lexical rank, score and execution-trace proximity are not
    inputs and therefore cannot establish a result.
    """

    ordered = tuple(
        sorted(
            {
                (candidate.normalized_file, candidate.symbol): candidate
                for candidate in candidates
                if candidate.normalized_file and candidate.symbol
            }.values(),
            key=lambda item: (item.rank, item.identity),
        )
    )
    if not ordered:
        return FailureRelevanceBinding()

    locations = known_failure_locations(repo_path, preflight)
    generic_direct: list[tuple[LocalizedCandidate, FailureLocation | None]] = []
    for candidate in ordered:
        candidate_locations = [
            location
            for location in locations
            if location.normalized_file == candidate.normalized_file
        ]
        for location in candidate_locations:
            if _strong_direct_location(location, candidate):
                return FailureRelevanceBinding(
                    kind=FAILURE_BINDING_DIRECT_LOCATION,
                    candidate_file=candidate.file,
                    candidate_symbol=candidate.symbol,
                    location=location,
                )
            generic_direct.append((candidate, location))
        if not candidate_locations and _output_names_candidate(preflight, candidate):
            generic_direct.append((candidate, None))

    resolved: dict[str, tuple[LocalizedCandidate, FailureLocation]] = {}
    ambiguous: set[str] = set()
    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError):
        repo = Path(".").resolve()

    for location in locations:
        if location.line is None or not location.normalized_file.endswith(".py"):
            continue
        safe = _safe_relative_file(repo, location.file)
        if safe is None:
            continue
        relative, path = safe
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError, ValueError):
            continue
        direct_imports, module_imports = _python_import_bindings(tree, relative)
        for call in _calls_at_line(tree, location.line):
            matches = _call_candidate_matches(
                call,
                ordered,
                relative,
                direct_imports,
                module_imports,
            )
            if len(matches) > 1:
                ambiguous.update(candidate.identity for candidate in matches)
                continue
            if len(matches) == 1:
                candidate = matches[0]
                resolved[candidate.identity] = (candidate, location)

    if ambiguous or len(resolved) > 1:
        ambiguous.update(resolved)
        return FailureRelevanceBinding(
            kind=FAILURE_BINDING_AMBIGUOUS,
            ambiguous_candidates=tuple(sorted(ambiguous)),
        )
    if len(resolved) == 1:
        candidate, location = next(iter(resolved.values()))
        return FailureRelevanceBinding(
            kind=FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE,
            candidate_file=candidate.file,
            candidate_symbol=candidate.symbol,
            location=location,
        )

    if generic_direct:
        generic_direct.sort(key=lambda item: (item[0].rank, item[0].identity))
        candidate, location = generic_direct[0]
        if location is None:
            location = FailureLocation(
                file=candidate.file,
                line=None,
                kind="validation_output_path",
            )
        return FailureRelevanceBinding(
            kind=FAILURE_BINDING_DIRECT_LOCATION,
            candidate_file=candidate.file,
            candidate_symbol=candidate.symbol,
            location=location,
        )
    return FailureRelevanceBinding()


def explicit_change_scope_tokens(route: Mapping[str, Any] | None) -> tuple[str, ...]:
    """Extract only an explicit ``across A/B/C`` scope from preserved receipt text.

    This does not reclassify intent.  WAITER.LIVE.1 already classified the
    request and preserved its obligations; this merely keeps a narrow literal
    multi-surface obligation from disappearing at the patch handoff.
    """

    if not isinstance(route, Mapping):
        return ()
    tokens: list[str] = []
    for obligation in route.get("obligations") or ():
        match = _EXPLICIT_ACROSS_SCOPE.search(str(obligation or ""))
        if match is None:
            continue
        parts = _SCOPE_SPLIT.split(match.group("scope"))
        for part in parts[:12]:
            words = [word.lower() for word in _SCOPE_WORD.findall(part)]
            words = [word for word in words if word not in _SCOPE_STOP_WORDS]
            if len(words) == 1 and words[0] not in tokens:
                tokens.append(words[0])
    return tuple(tokens) if len(tokens) >= 2 else ()


def target_matches_scope_token(target: str, token: str) -> bool:
    pieces = {
        piece
        for piece in re.findall(
            r"[a-z0-9]+", normalize_repo_relative_path(target).replace("_", "-")
        )
        if piece
    }
    variants = {token.lower(), token.lower().rstrip("s")}
    variants |= {variant + "s" for variant in tuple(variants) if variant}
    return bool(pieces & variants)


def explicit_change_targets_match_scope(
    route: Mapping[str, Any] | None,
    targets: Iterable[str],
) -> bool:
    tokens = explicit_change_scope_tokens(route)
    if not tokens:
        return True
    normalized_targets = tuple(target for target in targets if str(target or "").strip())
    return all(
        any(target_matches_scope_token(target, token) for target in normalized_targets)
        for token in tokens
    ) and all(
        any(target_matches_scope_token(target, token) for token in tokens)
        for target in normalized_targets
    )


__all__ = [
    "FAILURE_BINDING_AMBIGUOUS",
    "FAILURE_BINDING_DIRECT_EXECUTED_REFERENCE",
    "FAILURE_BINDING_DIRECT_LOCATION",
    "FAILURE_BINDING_EXPLICIT_CHANGE_REQUEST",
    "FAILURE_BINDING_BOUNDED_REPRODUCTION",
    "FAILURE_BINDING_KINDS",
    "FAILURE_BINDING_UNAVAILABLE",
    "LEGITIMATE_PATCH_BASES",
    "PATCH_BASES",
    "PATCH_BASIS_EXPLICIT_CHANGE_REQUEST",
    "PATCH_BASIS_GROUNDED_DEFECT",
    "PATCH_BASIS_NONE",
    "PATCH_BASIS_SOURCE_EXECUTED_FAILURE",
    "PATCH_BASIS_SOURCE_BOUNDED_REPRODUCTION",
    "PATCH_BASIS_SOURCE_EXPLICIT_REQUEST",
    "PATCH_BASIS_SOURCE_UNAVAILABLE",
    "PATCH_BASIS_UNRESOLVED",
    "FailureLocation",
    "FailureRelevanceBinding",
    "LocalizedCandidate",
    "bind_executed_failure_to_candidates",
    "explicit_change_scope_tokens",
    "explicit_change_targets_match_scope",
    "has_legitimate_patch_basis",
    "known_failure_locations",
    "normalize_patch_basis",
    "normalize_repo_relative_path",
]
