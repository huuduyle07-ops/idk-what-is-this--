"""Static authority-boundary regressions for EVIDENCE.2.

These tests inspect syntax rather than invoking EVIDENCE.2.  The focused set
tests own behaviour; this file proves that the implementation has no machinery
for reaching past the records it was handed — no filesystem, no acquisition, no
analyzer, no model, no network — and that no live product path has wired the
report-only phase into the application.

The most important of these is negative in an unusual way: EVIDENCE.2 must not
be able to *interpret* anything.  Importing the EVIDENCE.1 promotion gate would
transitively import an analyzer, which would hand a phase whose entire job is to
group already-decided relations a way to decide them again.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_SET_SOURCE = _CORE_ROOT / "evidence_set_assessment.py"

_EVIDENCE_2_SOURCES = (_SET_SOURCE,)

#: Downstream report-only phases that consume EVIDENCE.2 *assessments*.  A phase
#: that reads a frozen contract is not a live production path, and each is
#: proved unwired by its own boundary suite; the assertion that matters for them
#: is the narrower one at the end of this file — they bind to the contract
#: module, never re-run the aggregator, and can never reach an analyzer.
_DOWNSTREAM_CONTRACT_CONSUMERS = (
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


def _source_trees(sources: tuple[Path, ...] = _EVIDENCE_2_SOURCES):
    for path in sources:
        yield path, _tree(path)


# ── Imports ───────────────────────────────────────────────────────────────────

def test_evidence_2_does_not_import_forbidden_authority_stacks() -> None:
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
        "core.bounded_lexical_search",
        "core.context_search_runtime",
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


def test_evidence_2_cannot_reach_an_analyzer_or_re_run_the_gate() -> None:
    """A phase that groups decided relations must not be able to decide any."""
    forbidden = (
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
        "core.evidence_promotion_gate",
    )
    entry_points = frozenset(
        {"adjudicate", "analyze", "verify_acquired_source", "verify_with_bounded_repair"}
    )

    violations: list[str] = []
    bound: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.evidence_verification"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(forbidden):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in entry_points:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert bound, "EVIDENCE.2 must bind to the EVIDENCE.1 contract"
    assert violations == [], violations


def test_evidence_2_needs_no_acquired_bytes() -> None:
    """Hashes and records are enough; the payload contract is never imported."""
    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.content_acquisition"):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if tail in {"acquire_selected_content", "bounded_payload_view"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations
    source = _SET_SOURCE.read_text(encoding="utf-8")
    assert "AcquiredSourcePayload" not in source
    assert "BoundedPayloadView" not in source


# ── No filesystem, no traversal, no acquisition ───────────────────────────────

def test_evidence_2_performs_no_filesystem_access() -> None:
    filesystem_calls = frozenset(
        {
            "close",
            "fdopen",
            "fstat",
            "lstat",
            "makedirs",
            "mkdir",
            "open",
            "read_bytes",
            "read_text",
            "remove",
            "rmdir",
            "stat",
            "unlink",
            "write_bytes",
            "write_text",
        }
    )
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

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if name in exact_filesystem_calls or tail in filesystem_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_evidence_2_contains_no_repository_enumeration() -> None:
    traversal_names = frozenset(
        {"fwalk", "glob", "iglob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in traversal_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_evidence_2_contains_no_network_database_or_execution_calls() -> None:
    authority_call_names = frozenset(
        {
            "check_call",
            "check_output",
            "commit",
            "complete",
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


def test_importing_evidence_2_touches_nothing() -> None:
    """Import-time inertness: only definitions run when the module loads."""
    allowed_call_names = frozenset({"frozenset", "len", "tuple", "dataclass", "field"})
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in tree.body:
            if isinstance(
                node,
                (ast.Import, ast.ImportFrom, ast.ClassDef, ast.FunctionDef,
                 ast.AsyncFunctionDef),
            ):
                continue
            for call, name in _calls(node):
                if name.rsplit(".", 1)[-1] not in allowed_call_names:
                    violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


# ── No number is ever an evidence weight ──────────────────────────────────────

def test_no_evidence_2_record_carries_a_numeric_confidence_field() -> None:
    banned = (
        "confidence",
        "probability",
        "support_score",
        "likelihood",
        "score",
        "weight",
        "rank",
    )
    for path in _EVIDENCE_2_SOURCES:
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


def test_no_evidence_2_field_or_function_names_a_vote() -> None:
    """Counting is not weighing, and there is nowhere to write the arithmetic."""
    banned_fragments = (
        "majority",
        "vote",
        "winner",
        "winning",
        "outweigh",
        "tally",
        "average",
        "mean_",
        "aggregate_confidence",
    )
    violations: list[str] = []
    for path in _EVIDENCE_2_SOURCES:
        tree = _tree(path)
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                names.append(node.name)
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names.append(node.target.id)
            for name in names:
                folded = name.casefold()
                for fragment in banned_fragments:
                    if fragment in folded:
                        violations.append(f"{path.name}: {name}")

    #: The honest denials — ``no_majority_computed``, ``majority_vote_computed``
    #: — are guardrail *keys* and reason-code string values, not class fields or
    #: callables, so they are outside this scan by construction.
    assert violations == [], violations


def test_the_relation_vocabulary_is_consumed_and_never_extended() -> None:
    from core.evidence_set_assessment import (
        ADDRESSING_RELATIONS,
        CONFLICT_STATUSES,
        INDEPENDENCE_STATES,
    )
    from core.evidence_verification import RELATIONS

    assert ADDRESSING_RELATIONS < set(RELATIONS)
    assert len(CONFLICT_STATUSES) == 5
    assert len(INDEPENDENCE_STATES) == 3


def test_claim_decision_authority_is_a_property_and_not_a_settable_field() -> None:
    """No construction path can flip it, because there is no field to flip."""
    import dataclasses

    from core.evidence_set_assessment import EvidenceSetAssessment

    field_names = {item.name for item in dataclasses.fields(EvidenceSetAssessment)}
    assert "claim_decision_authority" not in field_names
    assert "final_claim_authority" not in field_names
    assert isinstance(
        EvidenceSetAssessment.claim_decision_authority, property
    )
    assert isinstance(EvidenceSetAssessment.final_claim_authority, property)


# ── Not wired into any live product path ──────────────────────────────────────

_EVIDENCE_2_MODULE_NAMES = frozenset({"evidence_set_assessment"})

_EVIDENCE_2_ENTRY_POINTS = frozenset({"assess_evidence_set"})


def _production_python_files() -> Iterable[Path]:
    excluded = {
        path.resolve()
        for path in _EVIDENCE_2_SOURCES + _DOWNSTREAM_CONTRACT_CONSUMERS
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


def _is_evidence_2_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _EVIDENCE_2_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _EVIDENCE_2_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _EVIDENCE_2_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _EVIDENCE_2_MODULE_NAMES for alias in node.names
    )


def test_evidence_2_is_not_imported_or_called_by_a_live_production_path() -> None:
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_evidence_2_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _EVIDENCE_2_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _EVIDENCE_2_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _EVIDENCE_2_MODULE_NAMES
                        or argument.value
                        in {f"core.{item}" for item in _EVIDENCE_2_MODULE_NAMES}
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_downstream_consumers_bind_to_the_set_contract_and_re_run_nothing() -> None:
    """CLAIM.1 adjudicates the set EVIDENCE.2 described; it cannot describe one.

    Re-running the aggregator would let a phase whose job is to apply set-level
    policy re-derive the set it was handed, and importing the promotion gate
    would transitively import an analyzer.  So ``assess_evidence_set``, the
    gate, the analyzer and the model adapter are all unreachable from every
    downstream consumer.
    """
    forbidden_modules = (
        "core.evidence_promotion_gate",
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
        "core.content_acquisition",
    )
    forbidden_calls = frozenset(
        {
            "adjudicate",
            "analyze",
            "assess_evidence_set",
            "verify_acquired_source",
            "verify_with_bounded_repair",
        }
    )
    violations: list[str] = []
    bound: list[str] = []
    for path in _DOWNSTREAM_CONTRACT_CONSUMERS:
        tree = _tree(path)
        for module, line in _imported_modules(tree):
            if module.startswith("core.evidence_set_assessment"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(forbidden_modules):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert bound, "a downstream consumer must bind to the EVIDENCE.2 contract"
    assert violations == [], violations
