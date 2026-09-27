"""Static authority-boundary regressions for CLAIM.1.

These tests inspect syntax rather than invoking CLAIM.1.  The focused suite owns
behaviour; this file proves that the implementation has no machinery for
reaching past the one evidence set it was handed — no filesystem, no
acquisition, no analyzer, no model, no network — and that no live product path
has wired the report-only phase into the application.

Two of them are negative in an unusual way.

CLAIM.1 must not be able to *weigh* anything.  A phase that adjudicates
categorical set conditions has no business comparing one count against another,
so the arithmetic that would let five supports beat one contradiction is proved
absent rather than merely unused: no ``sum``, no ``max``, no ``min``, no
``Counter``, and no comparison with a length on both sides.

CLAIM.1 must not be able to *synthesize*.  Combining several proposition
assessments into a task answer is SYNTHESIS.1's job.  There is no code path here
that accepts more than one proposition, and none that renders prose.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_CLAIM_SOURCE = _CORE_ROOT / "claim_assessment.py"

_CLAIM_1_SOURCES = (_CLAIM_SOURCE,)

#: The report-only downstream phases allowed to consume a frozen
#: ClaimAssessment: SYNTHESIS.1, which composes several of them into a task
#: answer skeleton, and CHECK.2, which reconciles them against explicit
#: post-run goal and preservation obligations.  Both are excluded from the
#: "live wiring" scan only so long as the narrower assertion at the end of this
#: file proves that each reads the contract and cannot re-run CLAIM.1 or reach
#: any upstream runtime.
_DOWNSTREAM_CONTRACT_CONSUMERS = (
    _CORE_ROOT / "structured_synthesis.py",
    _CORE_ROOT / "goal_fidelity_review.py",
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


def _source_trees(sources: tuple[Path, ...] = _CLAIM_1_SOURCES):
    for path in sources:
        yield path, _tree(path)


# ── Imports ───────────────────────────────────────────────────────────────────

def test_claim_1_does_not_import_forbidden_authority_stacks() -> None:
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
            "random",
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
            "time",
            "transformers",
            "urllib",
            "uuid",
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


def test_claim_1_cannot_reach_an_analyzer_or_re_run_any_upstream_gate() -> None:
    """A phase that adjudicates decided relations must not be able to decide any."""
    forbidden = (
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
        "core.evidence_promotion_gate",
    )
    entry_points = frozenset(
        {
            "adjudicate",
            "analyze",
            "assess_evidence_set",
            "verify_acquired_source",
            "verify_with_bounded_repair",
        }
    )

    violations: list[str] = []
    bound_to_set: list[str] = []
    bound_to_record: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.evidence_set_assessment"):
                bound_to_set.append(f"{path.name}:{line}")
            if module.startswith("core.evidence_verification"):
                bound_to_record.append(f"{path.name}:{line}")
            if module.startswith(forbidden):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            # ``_adjudicate`` is CLAIM.1's own private rule table; the banned
            # name is EVIDENCE.1's public relation adjudicator.
            tail = name.rsplit(".", 1)[-1]
            if tail in entry_points:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert bound_to_set, "CLAIM.1 must bind to the EVIDENCE.2 contract"
    assert bound_to_record, "CLAIM.1 must bind to the EVIDENCE.1 contract"
    assert violations == [], violations


def test_claim_1_needs_no_acquired_bytes_and_no_evidence_records() -> None:
    """Fingerprints and one set assessment are enough."""
    violations: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.content_acquisition") or module.startswith(
                "core.acquisition_policy"
            ):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            tail = name.rsplit(".", 1)[-1]
            if tail in {"acquire_selected_content", "bounded_payload_view"}:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations
    source = _CLAIM_SOURCE.read_text(encoding="utf-8")
    for absent in (
        "AcquiredSourcePayload",
        "BoundedPayloadView",
        "EvidenceVerificationResult",
        "EvidenceVerificationRequest",
        "VerifiedEvidence",
        "StaticEvidenceAnalyzer",
    ):
        assert absent not in source, absent


# ── No filesystem, no traversal, no acquisition ───────────────────────────────

def test_claim_1_performs_no_filesystem_access() -> None:
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


def test_claim_1_contains_no_repository_enumeration() -> None:
    traversal_names = frozenset(
        {"fwalk", "glob", "iglob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in traversal_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_claim_1_contains_no_network_database_or_execution_calls() -> None:
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
            "generate",
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


def test_claim_1_has_no_clock_and_no_entropy() -> None:
    """Same evidence set, same claim assessment, on any machine at any time."""
    banned = frozenset(
        {
            "choice",
            "getrandbits",
            "monotonic",
            "now",
            "perf_counter",
            "random",
            "randint",
            "sample",
            "shuffle",
            "time",
            "time_ns",
            "today",
            "utcnow",
            "uuid1",
            "uuid4",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_importing_claim_1_touches_nothing() -> None:
    """Import-time inertness: only definitions run when the module loads."""
    allowed_call_names = frozenset({"frozenset", "len", "tuple", "dataclass", "field"})
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in tree.body:
            if isinstance(
                node,
                (
                    ast.Import,
                    ast.ImportFrom,
                    ast.ClassDef,
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                ),
            ):
                continue
            for call, name in _calls(node):
                if name.rsplit(".", 1)[-1] not in allowed_call_names:
                    violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


# ── No number is ever an evidence weight ──────────────────────────────────────

def test_no_claim_1_record_carries_a_numeric_confidence_field() -> None:
    banned = (
        "confidence",
        "probability",
        "support_score",
        "likelihood",
        "score",
        "weight",
        "rank",
        "count",
        "total",
    )
    for path in _CLAIM_1_SOURCES:
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


def test_no_claim_1_field_or_function_names_a_vote() -> None:
    """Counting is not weighing, and there is nowhere to write the arithmetic."""
    banned_fragments = (
        "majority",
        "vote",
        "winner",
        "winning",
        "outweigh",
        "outrank",
        "tally",
        "average",
        "mean_",
        "aggregate_confidence",
        "strength",
        "stronger",
    )
    violations: list[str] = []
    for path in _CLAIM_1_SOURCES:
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


def test_claim_1_never_compares_one_quantity_against_another() -> None:
    """The arithmetic that would let five supports beat one contradiction.

    A length compared against a *literal bound* is a finite-bound check and is
    fine.  A length compared against another length is the shape of a vote, and
    there is not one anywhere in the module.
    """

    def _has_len(node: ast.AST) -> bool:
        for child in ast.walk(node):
            if isinstance(child, ast.Call) and (
                _qualified_name(child.func) or ""
            ).rsplit(".", 1)[-1] == "len":
                return True
        return False

    violations: list[str] = []
    for path, tree in _source_trees():
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            operands = [node.left, *node.comparators]
            measured = [item for item in operands if _has_len(item)]
            if measured[1:]:
                violations.append(f"{path.name}:{node.lineno}: length vs length")
            if measured and any(
                isinstance(operator, (ast.Gt, ast.GtE, ast.Lt, ast.LtE))
                for operator in node.ops
            ):
                # A bound check: the other side must be a plain constant or a
                # module-level maximum, never something derived from the set.
                others = [item for item in operands if not _has_len(item)]
                for other in others:
                    if not isinstance(other, (ast.Constant, ast.Name)):
                        violations.append(
                            f"{path.name}:{node.lineno}: length vs derived value"
                        )

    assert violations == [], violations


def test_claim_1_has_no_arithmetic_reduction_over_evidence() -> None:
    banned = frozenset(
        {
            "Counter",
            "fmean",
            "fsum",
            "max",
            "mean",
            "median",
            "min",
            "most_common",
            "prod",
            "sum",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in banned:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(
                node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.FloorDiv, ast.Mod)
            ):
                violations.append(f"{path.name}:{node.lineno}: arithmetic operator")

    assert violations == [], violations


def test_the_claim_vocabulary_holds_no_truth_value() -> None:
    from core.claim_assessment import (
        ASSESSMENT_STATUSES,
        CORROBORATION_STATUSES,
        SEMANTIC_BASES,
    )
    from core.evidence_verification import LEVEL_DETERMINISTICALLY_VERIFIED

    for banned in (
        "true",
        "false",
        "likely_true",
        "probably_false",
        "confidence_high",
        "ground_truth",
        "semantically_verified",
        "deterministic_truth",
    ):
        assert banned not in ASSESSMENT_STATUSES, banned
    assert LEVEL_DETERMINISTICALLY_VERIFIED not in SEMANTIC_BASES
    assert len(SEMANTIC_BASES) == 2
    assert len(ASSESSMENT_STATUSES) == 8
    assert len(CORROBORATION_STATUSES) == 5


def test_final_claim_authority_is_a_property_and_not_a_settable_field() -> None:
    """No construction path can flip it, because there is no field to flip."""
    import dataclasses

    from core.claim_assessment import ClaimAssessment

    field_names = {item.name for item in dataclasses.fields(ClaimAssessment)}
    for absent in (
        "final_claim_authority",
        "objective_truth_asserted",
        "response_synthesis_performed",
        "claim_assessment_authority",
    ):
        assert absent not in field_names, absent
    assert isinstance(ClaimAssessment.final_claim_authority, property)
    assert isinstance(ClaimAssessment.objective_truth_asserted, property)
    assert isinstance(ClaimAssessment.response_synthesis_performed, property)


def test_claim_1_accepts_exactly_one_proposition() -> None:
    """Multi-proposition reasoning is SYNTHESIS.1's, and has no landing site."""
    import dataclasses

    from core.claim_assessment import ClaimAssessment, ClaimAssessmentRequest

    request_fields = {item.name for item in dataclasses.fields(ClaimAssessmentRequest)}
    assert "proposition" in request_fields
    for plural in ("propositions", "claims", "assessments", "evidence_sets"):
        assert plural not in request_fields, plural
    assessment_fields = {item.name for item in dataclasses.fields(ClaimAssessment)}
    for plural in ("propositions", "claims", "answer", "response", "narrative"):
        assert plural not in assessment_fields, plural


# ── Not wired into any live product path ──────────────────────────────────────

_CLAIM_1_MODULE_NAMES = frozenset({"claim_assessment"})

_CLAIM_1_ENTRY_POINTS = frozenset({"assess_claim"})


def _production_python_files() -> Iterable[Path]:
    excluded = {
        path.resolve()
        for path in _CLAIM_1_SOURCES + _DOWNSTREAM_CONTRACT_CONSUMERS
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


def _is_claim_1_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _CLAIM_1_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _CLAIM_1_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _CLAIM_1_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _CLAIM_1_MODULE_NAMES for alias in node.names
    )


def test_claim_1_is_not_imported_or_called_by_a_live_production_path() -> None:
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_claim_1_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _CLAIM_1_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _CLAIM_1_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _CLAIM_1_MODULE_NAMES
                        or argument.value
                        in {f"core.{item}" for item in _CLAIM_1_MODULE_NAMES}
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_the_downstream_consumers_read_claim_records_and_re_run_nothing() -> None:
    """SYNTHESIS.1 and CHECK.2 may read CLAIM.1 records, never produce them."""
    forbidden_modules = (
        "agents.ollama_client",
        "core.acquisition_policy",
        "core.acquisition_request",
        "core.candidate_eligibility",
        "core.candidate_inventory",
        "core.content_acquisition",
        "core.evidence_acquire_request",
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
        "core.evidence_candidate_pool",
        "core.evidence_content_acquisition",
        "core.evidence_promotion_gate",
        "core.evidence_set_assessment",
        "core.evidence_verification",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
    )
    forbidden_calls = frozenset(
        {
            "acquire_selected_content",
            "adjudicate",
            "analyze",
            "assess_claim",
            "assess_evidence_set",
            "bounded_payload_view",
            "verify_acquired_source",
            "verify_with_bounded_repair",
        }
    )
    forbidden_contracts = (
        "AcquiredSourcePayload",
        "BoundedPayloadView",
        "EvidenceSetAssessment",
        "EvidenceVerificationRequest",
        "EvidenceVerificationResult",
        "StaticEvidenceAnalyzer",
        "VerifiedEvidence",
    )

    bound: list[str] = []
    violations: list[str] = []
    for path in _DOWNSTREAM_CONTRACT_CONSUMERS:
        tree = _tree(path)
        source = path.read_text(encoding="utf-8")
        for module, line in _imported_modules(tree):
            if module.startswith("core.claim_assessment"):
                bound.append(f"{path.name}:{line}")
            if module.startswith(forbidden_modules):
                violations.append(f"{path.name}:{line}: import {module}")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for contract_name in forbidden_contracts:
            if contract_name in source:
                violations.append(f"{path.name}: names {contract_name}")

    assert len(_DOWNSTREAM_CONTRACT_CONSUMERS) == 2
    for consumer in _DOWNSTREAM_CONTRACT_CONSUMERS:
        assert any(item.startswith(f"{consumer.name}:") for item in bound), (
            f"{consumer.name} must bind to the frozen CLAIM.1 contract"
        )
    assert violations == [], violations
