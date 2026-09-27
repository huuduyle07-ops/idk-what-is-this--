"""Static authority-boundary regressions for EVIDENCE.1.

These tests inspect syntax rather than invoking EVIDENCE.1.  The focused
verification tests own behaviour; this file proves that the implementation has
no machinery for reaching further than the payload it was handed, that the
deterministic gate is separable from the optional model transport, and that no
live product path has wired the report-only phase into the application.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_CONTRACT_SOURCE = _CORE_ROOT / "evidence_verification.py"
_ANALYZER_SOURCE = _CORE_ROOT / "evidence_analyzer.py"
_GATE_SOURCE = _CORE_ROOT / "evidence_promotion_gate.py"
_ADAPTER_SOURCE = _CORE_ROOT / "evidence_analyzer_adapter.py"

#: The pure decision path.  Nothing here may touch a file, a socket or a model.
_PURE_SOURCES = (_CONTRACT_SOURCE, _ANALYZER_SOURCE, _GATE_SOURCE)
#: Every EVIDENCE.1 module, including the optional model boundary.
_EVIDENCE_1_SOURCES = _PURE_SOURCES + (_ADAPTER_SOURCE,)

#: Downstream report-only phases that consume EVIDENCE.1 *records*.  A phase
#: that reads a frozen contract is not a live production path, and each is
#: proved unwired by its own boundary suite; the assertion that matters for them
#: is the narrower one at the end of this file — they bind to the contract
#: module and can never reach the analyzer or re-run the gate.
_DOWNSTREAM_CONTRACT_CONSUMERS = (
    _CORE_ROOT / "evidence_set_assessment.py",
    _CORE_ROOT / "claim_assessment.py",
)

_SKIPPED_PRODUCTION_PARTS = frozenset(
    {
        ".agent",
        ".agents",
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "tests",
        ".tmp",
        ".pytest_cache",
        "tmp_tests",
        "venv",
    }
)


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _qualified_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        owner = _qualified_name(node.value)
        return f"{owner}.{node.attr}" if owner else node.attr
    return None


def _imported_modules(tree: ast.AST) -> Iterable[tuple[str, int]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, node.lineno
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            yield module, node.lineno
            for alias in node.names:
                qualified = f"{module}.{alias.name}" if module else alias.name
                yield qualified, node.lineno


def _calls(tree: ast.AST) -> Iterable[tuple[ast.Call, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            yield node, _qualified_name(node.func) or "<dynamic call>"


def _source_trees(sources: tuple[Path, ...] = _EVIDENCE_1_SOURCES):
    for path in sources:
        yield path, _tree(path)


# ── Imports ───────────────────────────────────────────────────────────────────

def test_evidence_1_does_not_import_forbidden_authority_stacks() -> None:
    forbidden_roots = frozenset(
        {
            "aiohttp",
            "anthropic",
            "asyncpg",
            "boto3",
            "ftplib",
            "glob",
            "google.generativeai",
            "http",
            "httpx",
            "langchain",
            "litellm",
            "multiprocessing",
            "ollama",
            "openai",
            "os",
            "pathlib",
            "pathspec",
            "psycopg",
            "psycopg2",
            "pymongo",
            "redis",
            "requests",
            "shutil",
            "smtplib",
            "socket",
            "sqlalchemy",
            "sqlite3",
            "subprocess",
            "supabase",
            "tempfile",
            "transformers",
            "urllib",
            "websockets",
        }
    )
    forbidden_core_prefixes = (
        "agents.ollama_client",
        "core.context_selection",
        "core.direct_context_runtime",
        "core.direct_file_reader",
        "core.evidence_content_acquisition",
        "core.file_candidate_selector",
        "core.graph",
        "core.index",
        "core.model",
        "core.ollama_client",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
        "core.semantic_waiter_client",
        "core.validation_execution",
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            root = module.casefold()
            if any(
                root == prefix or root.startswith(f"{prefix}.")
                for prefix in forbidden_roots
            ) or any(
                root == prefix or root.startswith(f"{prefix}.")
                for prefix in forbidden_core_prefixes
            ):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name in {"__import__", "importlib.import_module"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_evidence_1_imports_acquire_3_contracts_but_not_its_read_runtime() -> None:
    """EVIDENCE.1 consumes what ACQUIRE.3 produced; it cannot re-run it."""
    contract_imports: list[str] = []
    runtime_imports: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.content_acquisition"):
                contract_imports.append(f"{path.name}:{line}")
            if module.startswith("core.evidence_content_acquisition"):
                runtime_imports.append(f"{path.name}:{line}")

    assert contract_imports, "EVIDENCE.1 must bind to the ACQUIRE.3 contracts"
    assert runtime_imports == [], runtime_imports

    for path, tree in _source_trees():
        for call, name in _calls(tree):
            assert name.rsplit(".", 1)[-1] != "acquire_selected_content", (
                f"{path.name}:{call.lineno}"
            )


# ── No filesystem, no traversal, no acquisition ───────────────────────────────

def test_evidence_1_performs_no_filesystem_access() -> None:
    filesystem_calls = frozenset(
        {
            "close",
            "fdopen",
            "fstat",
            "lstat",
            "makedirs",
            "mkdir",
            "open",
            "read",
            "read_bytes",
            "read_text",
            "remove",
            "rmdir",
            "stat",
            "unlink",
            "write",
            "write_bytes",
            "write_text",
        }
    )
    #: ``replace`` and ``rename`` are also ordinary string methods, so those two
    #: are matched by their exact dotted filesystem spelling instead.
    exact_filesystem_calls = frozenset(
        {
            "os.rename",
            "os.replace",
            "shutil.move",
            "shutil.rmtree",
            "Path.rename",
            "Path.replace",
        }
    )
    #: Bytes/str methods that share a name with a filesystem call and are safe.
    safe_receivers = frozenset({"self._content", "window", "content", "payload"})

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            owner = name.rsplit(".", 1)[0] if "." in name else ""
            if name in exact_filesystem_calls or (
                tail in filesystem_calls and owner not in safe_receivers
            ):
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_evidence_1_contains_no_repository_enumeration() -> None:
    traversal_names = frozenset(
        {"fwalk", "glob", "iglob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in traversal_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_evidence_1_contains_no_network_database_or_execution_calls() -> None:
    authority_call_names = frozenset(
        {
            "check_call",
            "check_output",
            "commit",
            "connect",
            "create_connection",
            "cursor",
            "eval",
            "exec",
            "executemany",
            "getaddrinfo",
            "popen",
            "post",
            "request",
            "rollback",
            "run",
            "socket",
            "spawn",
            "system",
            "urlopen",
        }
    )
    selector_call_names = frozenset(
        {
            "acquire_selected_content",
            "derive_candidate_eligibility",
            "execute_context_selection",
            "rank_candidates",
            "select_candidates",
        }
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if tail in authority_call_names or tail in selector_call_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


# ── The pure gate is separable from the model boundary ────────────────────────

def test_the_deterministic_gate_never_reaches_the_model_boundary() -> None:
    """A model may propose; the gate that decides must not know how to ask one."""
    violations: list[str] = []
    for path, tree in _source_trees(_PURE_SOURCES):
        for module, line in _imported_modules(tree):
            if module.startswith("core.evidence_analyzer_adapter"):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] == "complete":
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_the_model_adapter_opens_no_socket_and_owns_no_client() -> None:
    tree = _tree(_ADAPTER_SOURCE)
    for module, line in _imported_modules(tree):
        assert not module.startswith(
            ("requests", "httpx", "urllib", "socket", "aiohttp", "openai", "anthropic")
        ), f"{_ADAPTER_SOURCE.name}:{line}: {module}"
    #: The only transport is a caller-supplied protocol implementation.
    source = _ADAPTER_SOURCE.read_text(encoding="utf-8")
    assert "class EvidenceModelClient(Protocol)" in source
    assert "base_url" not in source
    assert "api_key" not in source


def test_importing_evidence_1_touches_nothing() -> None:
    """Import-time inertness: only definitions run when these modules load."""
    allowed_call_names = frozenset({"frozenset", "len", "tuple", "dataclass", "field"})
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom, ast.ClassDef,
                                 ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for call, name in _calls(node):
                if name.rsplit(".", 1)[-1] not in allowed_call_names:
                    violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


# ── No numeric confidence anywhere in the contract ────────────────────────────

def test_no_evidence_1_record_carries_a_numeric_confidence_field() -> None:
    banned = ("confidence", "probability", "support_score", "likelihood", "score")
    for path in _PURE_SOURCES:
        tree = _tree(path)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(
                    statement.target, ast.Name
                ):
                    field_name = statement.target.id.casefold()
                    assert not any(term in field_name for term in banned), (
                        f"{path.name}: {node.name}.{statement.target.id}"
                    )


def test_the_relation_vocabulary_stays_four_categorical_values() -> None:
    from core.evidence_verification import DIRECTIONAL_RELATIONS, RELATIONS

    assert RELATIONS == ("supports", "contradicts", "insufficient", "unrelated")
    assert DIRECTIONAL_RELATIONS == frozenset({"supports", "contradicts"})


# ── No field anywhere claims a proven proposition ─────────────────────────────

_PROVEN_TRUTH_TOKENS = (
    "claim_proven",
    "semantic_truth_verified",
    "proposition_verified_true",
    "proposition_proven",
    "deterministic_semantic_verification",
    "semantically_verified",
    "ground_truth",
)


def test_no_evidence_1_source_names_a_proven_semantic_truth() -> None:
    """The overclaim has no spelling anywhere in the phase, not even as a key.

    A serialized record is read by people and by later phases.  A field called
    ``claim_proven`` or ``semantic_truth_verified`` would be read as one whether
    it were set to true or to false, so neither exists at all.
    """
    violations: list[str] = []
    for path in _EVIDENCE_1_SOURCES:
        text = path.read_text(encoding="utf-8").casefold()
        for token in _PROVEN_TRUTH_TOKENS:
            if token in text:
                violations.append(f"{path.name}: {token}")

    assert violations == [], violations


def test_the_semantic_relation_dimension_has_a_ceiling_below_deterministic() -> None:
    """Structurally, not by convention: the record cannot be told otherwise."""
    import pytest

    from core.evidence_verification import (
        DETERMINISTIC_DIMENSIONS,
        DIMENSION_MAX_LEVEL,
        DIMENSION_SEMANTIC_RELATION,
        LEVEL_ANALYZER_ASSESSED,
        LEVEL_DETERMINISTICALLY_VERIFIED,
        VerificationLevels,
    )

    assert DIMENSION_SEMANTIC_RELATION not in DETERMINISTIC_DIMENSIONS
    assert DIMENSION_MAX_LEVEL[DIMENSION_SEMANTIC_RELATION] == LEVEL_ANALYZER_ASSESSED
    with pytest.raises(ValueError):
        VerificationLevels(semantic_relation=LEVEL_DETERMINISTICALLY_VERIFIED)


# ── Not wired into any live product path ──────────────────────────────────────

_EVIDENCE_1_MODULE_NAMES = frozenset(
    {
        "evidence_analyzer",
        "evidence_analyzer_adapter",
        "evidence_promotion_gate",
        "evidence_verification",
    }
)

_EVIDENCE_1_ENTRY_POINTS = frozenset(
    {
        "adjudicate",
        "verify_acquired_source",
        "verify_with_bounded_repair",
    }
)


def _production_python_files() -> Iterable[Path]:
    excluded = {
        path.resolve()
        for path in _EVIDENCE_1_SOURCES + _DOWNSTREAM_CONTRACT_CONSUMERS
    }
    for path in sorted(_REPOSITORY_ROOT.rglob("*.py")):
        relative = path.relative_to(_REPOSITORY_ROOT)
        if set(relative.parts) & _SKIPPED_PRODUCTION_PARTS or any(
            part.startswith(".tmp") or part.startswith("pytest-")
            for part in relative.parts
        ):
            continue
        if path.resolve() in excluded:
            continue
        yield path


def _is_evidence_1_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _EVIDENCE_1_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _EVIDENCE_1_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _EVIDENCE_1_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _EVIDENCE_1_MODULE_NAMES for alias in node.names
    )


def test_evidence_1_is_not_imported_or_called_by_a_live_production_path() -> None:
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_evidence_1_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _EVIDENCE_1_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _EVIDENCE_1_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _EVIDENCE_1_MODULE_NAMES
                        or argument.value
                        in {f"core.{item}" for item in _EVIDENCE_1_MODULE_NAMES}
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_downstream_consumers_bind_to_the_contract_and_cannot_reach_an_analyzer() -> None:
    """EVIDENCE.2 aggregates EVIDENCE.1's records; CLAIM.1 adjudicates the set
    EVIDENCE.2 described.  Neither can produce a record.

    Importing the gate would transitively import the analyzer, which would give
    a phase whose whole job is to *not* interpret content a way to interpret it.
    So the gate, the analyzer and the model adapter are all unreachable by
    import from every downstream consumer, and the entry points are unreachable
    by call.
    """
    forbidden_modules = (
        "core.evidence_promotion_gate",
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
    )
    violations: list[str] = []
    bound: list[str] = []
    for path in _DOWNSTREAM_CONTRACT_CONSUMERS:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.startswith("core.evidence_verification"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(forbidden_modules):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in _EVIDENCE_1_ENTRY_POINTS:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert bound, "a downstream consumer must bind to the EVIDENCE.1 contract"
    assert violations == [], violations
