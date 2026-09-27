"""Static authority-boundary regressions for CHECK.2.

The focused suite owns behaviour.  These tests inspect syntax and prove that the
implementation has no machinery for reaching past the two frozen contracts it
was handed — no filesystem, no diff, no acquisition, no analyzer, no model, no
network, no validation runner — and that no live product path has wired the
report-only phase into the application.

Three of them are negative in an unusual way.

CHECK.2 must not be able to *judge*.  There is no reviewer model, no analyzer
entry point and no route to re-run CHECK.1 or CLAIM.1: the only semantic
direction in the module is a table lookup keyed by a polarity somebody else
supplied.

CHECK.2 must not be able to *weigh*.  Three satisfied goals must not outvote one
violated preservation constraint, so the arithmetic that would let them is
proved absent rather than merely unused: no ``sum``, no ``max``, no ``min``, no
``Counter``, and no comparison with a length on both sides.

CHECK.2 must not be able to *accept*.  ``run_success``, ``final_success``,
``merge_ready`` and ``implementation_correct`` are not fields, not properties
and not serialized keys, and the result cannot be constructed at all without
leaving the run verdict and human review outstanding.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Iterable


_REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
_CORE_ROOT = _REPOSITORY_ROOT / "core"
_REVIEW_SOURCE = _CORE_ROOT / "goal_fidelity_review.py"

_CHECK_2_SOURCES = (_REVIEW_SOURCE,)

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


def _source_trees(sources: tuple[Path, ...] = _CHECK_2_SOURCES):
    for path in sources:
        yield path, _tree(path)


# ── Imports ───────────────────────────────────────────────────────────────────

def test_check_2_imports_only_pure_helpers_and_the_two_frozen_contracts():
    allowed = frozenset(
        {
            "__future__",
            "dataclasses",
            "hashlib",
            "json",
            "typing",
            "core.claim_assessment",
            "core.post_run_reconciliation",
        }
    )
    violations: list[str] = []
    for path, tree in _source_trees():
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in allowed:
                        violations.append(f"{path.name}:{node.lineno}: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "") not in allowed:
                    violations.append(f"{path.name}:{node.lineno}: {node.module}")

    assert violations == [], violations


def test_check_2_binds_to_both_upstream_branches():
    """The registry says CHECK.1 and CLAIM.1; the source must agree."""
    bound_to_execution: list[str] = []
    bound_to_claim: list[str] = []
    for path, tree in _source_trees():
        for module, line in _imported_modules(tree):
            if module.startswith("core.post_run_reconciliation"):
                bound_to_execution.append(f"{path.name}:{line}")
            if module.startswith("core.claim_assessment"):
                bound_to_claim.append(f"{path.name}:{line}")

    assert bound_to_execution, "CHECK.2 must bind to the frozen CHECK.1 contract"
    assert bound_to_claim, "CHECK.2 must bind to the frozen CLAIM.1 contract"


def test_check_2_does_not_import_an_authority_stack():
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
        "core.acquisition_policy",
        "core.acquisition_request",
        "core.candidate_eligibility",
        "core.candidate_inventory",
        "core.content_acquisition",
        "core.context_search_runtime",
        "core.context_selection",
        "core.direct_context_runtime",
        "core.direct_file_reader",
        "core.evidence_analyzer",
        "core.evidence_analyzer_adapter",
        "core.evidence_content_acquisition",
        "core.evidence_promotion_gate",
        "core.evidence_set_assessment",
        "core.evidence_verification",
        "core.executor",
        "core.file_candidate_selector",
        "core.graph",
        "core.index",
        "core.mirror_tunnel_claim_diff_check",
        "core.model",
        "core.patch_safety",
        "core.pipeline",
        "core.post_run_observation",
        "core.repo_librarian",
        "core.repository_inventory",
        "core.retriever",
        "core.self_correct_loop",
        "core.semantic_waiter_client",
        "core.structured_synthesis",
        "core.task_contract",
        "core.validation_command",
        "core.validation_execution",
        "core.worker_result_review",
        "core.worker_runs",
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


def test_check_2_cannot_re_run_check_1_or_claim_1_or_reach_an_analyzer():
    """A phase that reconciles decided results must not be able to decide any."""
    forbidden_calls = frozenset(
        {
            "acquire_selected_content",
            "adjudicate",
            "analyze",
            "assess_claim",
            "assess_evidence_set",
            "bounded_payload_view",
            "build_observed_post_run_facts",
            "classify_authorized_paths",
            "evaluate_patch_safety",
            "execute_context_selection",
            "observed_changes_from_records",
            "reconcile_post_run",
            "select_candidates",
            "verify_acquired_source",
            "verify_with_bounded_repair",
        }
    )
    forbidden_names = (
        "AcquiredSourcePayload",
        "BoundedPayloadView",
        "EvidenceSetAssessment",
        "EvidenceVerificationRequest",
        "EvidenceVerificationResult",
        "ObservedPostRunFacts",
        "StaticEvidenceAnalyzer",
        "VerifiedEvidence",
        "WorkerReport",
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        source = path.read_text(encoding="utf-8")
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in forbidden_calls:
                violations.append(f"{path.name}:{call.lineno}: {name}")
        for forbidden in forbidden_names:
            if forbidden in source:
                violations.append(f"{path.name}: names {forbidden}")

    assert violations == [], violations


# ── No filesystem, no traversal, no execution ─────────────────────────────────

def test_check_2_performs_no_filesystem_access():
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


def test_check_2_contains_no_repository_enumeration():
    traversal_names = frozenset(
        {"fwalk", "glob", "iglob", "iterdir", "listdir", "rglob", "scandir", "walk"}
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in traversal_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_check_2_contains_no_network_database_or_execution_calls():
    authority_call_names = frozenset(
        {
            "apply_patch",
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
            "run_validation",
            "socket",
            "spawn",
            "system",
            "urlopen",
        }
    )

    violations: list[str] = []
    for path, tree in _source_trees():
        for call, name in _calls(tree):
            if name.rsplit(".", 1)[-1] in authority_call_names:
                violations.append(f"{path.name}:{call.lineno}: {name}")

    assert violations == [], violations


def test_check_2_has_no_clock_and_no_entropy():
    """Same inputs, same assessment, on any machine at any time."""
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


def test_importing_check_2_touches_nothing():
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


# ── No number is ever an obligation weight ────────────────────────────────────

def test_no_check_2_record_carries_a_numeric_confidence_field():
    banned = (
        "confidence",
        "probability",
        "likelihood",
        "score",
        "weight",
        "rank",
        "count",
        "total",
        "percent",
        "ratio",
    )
    for path in _CHECK_2_SOURCES:
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


def test_no_check_2_field_or_callable_names_a_vote():
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
        "mostly",
    )
    violations: list[str] = []
    for path in _CHECK_2_SOURCES:
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

    #: The honest denials — ``majority_computed``, ``CHECK2_NO_MAJORITY_COMPUTED``
    #: — are guardrail keys and reason-code string values, not class fields or
    #: callables, so they are outside this scan by construction.
    assert violations == [], violations


def test_check_2_never_compares_one_quantity_against_another():
    """The arithmetic that would let three satisfied goals beat one violation.

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
                others = [item for item in operands if not _has_len(item)]
                for other in others:
                    if not isinstance(other, (ast.Constant, ast.Name)):
                        violations.append(
                            f"{path.name}:{node.lineno}: length vs derived value"
                        )

    assert violations == [], violations


def test_check_2_has_no_arithmetic_reduction_over_obligations():
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


# ── The vocabulary holds no verdict ───────────────────────────────────────────

def test_the_check_2_vocabularies_hold_no_truth_or_acceptance_value():
    from core.goal_fidelity_review import (
        GOAL_FIDELITY_STATUSES,
        OBLIGATION_STATUSES,
        REVIEW_MODES,
        SATISFACTION_POLARITIES,
    )

    for banned in (
        "true",
        "false",
        "correct",
        "incorrect",
        "success",
        "failure",
        "failure_probability",
        "goal_proven",
        "merge_ready",
        "semantically_verified",
        "run_success",
    ):
        assert banned not in OBLIGATION_STATUSES, banned
        assert banned not in GOAL_FIDELITY_STATUSES, banned
    assert len(OBLIGATION_STATUSES) == 11
    assert len(GOAL_FIDELITY_STATUSES) == 5
    assert len(REVIEW_MODES) == 3
    assert len(SATISFACTION_POLARITIES) == 2


def test_no_provenance_vocabulary_admits_an_inferred_requirement():
    """No obligation invention, made structural rather than remembered."""
    from core.goal_fidelity_review import (
        LEDGER_REQUIREMENT_KINDS,
        POLARITY_PROVENANCES,
        REQUIREMENT_PROVENANCES,
    )

    for value in REQUIREMENT_PROVENANCES:
        assert "explicit" in value, value
    assert "inferred" not in REQUIREMENT_PROVENANCES
    assert "check_2" not in " ".join(POLARITY_PROVENANCES)
    assert "preservation_requirement" not in LEDGER_REQUIREMENT_KINDS


def test_forbidden_authorities_are_not_constructor_settable():
    import dataclasses

    from core.goal_fidelity_review import GoalFidelityAssessment, ObligationResult

    assessment_fields = {
        item.name for item in dataclasses.fields(GoalFidelityAssessment)
    }
    for absent in (
        "final_success_authority",
        "run_verdict_authority",
        "merge_authority",
        "objective_truth_asserted",
        "goal_proven",
        "semantic_goal_review_authority",
        "run_success",
        "implementation_correct",
        "merge_ready",
        "safe_to_merge",
    ):
        assert absent not in assessment_fields, absent
    for name in (
        "final_success_authority",
        "run_verdict_authority",
        "merge_authority",
        "objective_truth_asserted",
        "goal_proven",
        "semantic_goal_review_authority",
        "check_3_required",
    ):
        assert isinstance(getattr(GoalFidelityAssessment, name), property), name

    result_fields = {item.name for item in dataclasses.fields(ObligationResult)}
    assert "goal_proven" not in result_fields
    assert isinstance(ObligationResult.goal_proven, property)


def test_the_result_cannot_be_built_without_an_outstanding_run_verdict():
    import pytest

    from core.goal_fidelity_review import (
        UNRESOLVED_HUMAN_REVIEW,
        UNRESOLVED_RUN_VERDICT,
        ExecutionReconciliationSummary,
        GoalFidelityAssessment,
        REVIEW_ASSESSABLE,
        STATUS_ASSESSED,
    )

    digest = "0" * 64
    summary = ExecutionReconciliationSummary(
        check_1_status="reconciled",
        check_1_reconciliation_fingerprint=digest,
        execution_authorization_fingerprint=digest,
        final_state_fingerprint=digest,
        validation_coverage_complete=True,
        validated_state_current=True,
    )
    payload = {
        "status": STATUS_ASSESSED,
        "review_mode": REVIEW_ASSESSABLE,
        "task_contract_fingerprint": digest,
        "check_1_reconciliation_fingerprint": digest,
        "verification_specification_fingerprint": digest,
        "requirement_ledger_fingerprint": digest,
        "request_fingerprint": digest,
        "execution_reconciliation": summary,
    }
    with pytest.raises(ValueError):
        GoalFidelityAssessment(**payload, unresolved_requirements=())
    with pytest.raises(ValueError):
        GoalFidelityAssessment(
            **payload, unresolved_requirements=(UNRESOLVED_RUN_VERDICT,)
        )
    built = GoalFidelityAssessment(
        **payload,
        unresolved_requirements=(UNRESOLVED_RUN_VERDICT, UNRESOLVED_HUMAN_REVIEW),
    )
    assert built.check_3_required is True


def test_a_blocked_review_cannot_carry_a_determined_obligation():
    import pytest

    from core.goal_fidelity_review import (
        OBLIGATION_SATISFIED,
        REVIEW_BLOCKED,
        STATUS_BLOCKED,
        UNRESOLVED_HUMAN_REVIEW,
        UNRESOLVED_RUN_VERDICT,
        BASIS_ANALYZER_ASSESSED,
        ExecutionReconciliationSummary,
        GoalFidelityAssessment,
        OBLIGATION_KIND_GOAL,
        ObligationResult,
        POLARITY_PROVENANCE_GOAL_PROJECTION,
        POLARITY_SUPPORT_MEANS_SATISFIED,
    )

    digest = "0" * 64
    summary = ExecutionReconciliationSummary(
        check_1_status="blocked",
        check_1_reconciliation_fingerprint=digest,
        execution_authorization_fingerprint=digest,
        final_state_fingerprint=digest,
        validation_coverage_complete=True,
        validated_state_current=True,
    )
    satisfied = ObligationResult(
        obligation_id="G1",
        obligation_kind=OBLIGATION_KIND_GOAL,
        obligation_text_sha256=digest,
        source_requirement_id="R-G1",
        required=True,
        obligation_status=OBLIGATION_SATISFIED,
        claim_status="supported_by_assessed_evidence",
        claim_assessment_fingerprint=digest,
        semantic_basis=BASIS_ANALYZER_ASSESSED,
        satisfaction_polarity=POLARITY_SUPPORT_MEANS_SATISFIED,
        polarity_provenance=POLARITY_PROVENANCE_GOAL_PROJECTION,
    )
    with pytest.raises(ValueError):
        GoalFidelityAssessment(
            status=STATUS_BLOCKED,
            review_mode=REVIEW_BLOCKED,
            task_contract_fingerprint=digest,
            check_1_reconciliation_fingerprint=digest,
            verification_specification_fingerprint=digest,
            requirement_ledger_fingerprint=digest,
            request_fingerprint=digest,
            execution_reconciliation=summary,
            obligation_results=(satisfied,),
            satisfied_obligations=("G1",),
            unresolved_requirements=(
                UNRESOLVED_RUN_VERDICT,
                UNRESOLVED_HUMAN_REVIEW,
            ),
        )


# ── Anti-truth-laundering in the serialization ────────────────────────────────

def _sample_assessment_payload() -> dict:
    from tests.test_goal_fidelity_review import single_goal_case

    _, result = single_goal_case(bind_final_state=True)
    from core.goal_fidelity_review import render_goal_fidelity_assessment_json

    return json.loads(render_goal_fidelity_assessment_json(result))


def test_a_fully_satisfied_assessment_serializes_no_acceptance_field():
    payload = _sample_assessment_payload()
    assert payload["status"] == "assessed"
    assert payload["satisfied_obligations"] == ["G1"]

    body = json.dumps(payload)
    for banned in (
        '"run_success"',
        '"final_success"',
        '"merge_ready"',
        '"safe_to_merge"',
        '"implementation_correct"',
        '"goal_satisfied"',
        '"semantic_truth_verified"',
        '"goal_fidelity_satisfied"',
        '"confidence"',
        '"probability"',
        '"score"',
        '"satisfied_count"',
    ):
        assert banned not in body, banned


def test_the_serialized_denials_are_present_and_false():
    payload = _sample_assessment_payload()
    for key in (
        "goal_proven",
        "objective_truth_asserted",
        "implementation_correctness_asserted",
        "run_verdict_produced",
        "semantic_evidence_reassessed",
        "obligations_derived_by_check_2",
        "propositions_derived_by_check_2",
        "polarity_derived_by_check_2",
    ):
        assert payload[key] is False, key
    assert payload["authority"]["final_success_authority"] is False
    assert payload["authority"]["merge_authority"] is False
    assert payload["authority"]["run_verdict_authority"] is False
    assert payload["authority"]["objective_truth_authority"] is False
    assert payload["authority"]["human_approval_required"] is True
    assert payload["guardrails"]["model_called"] is False
    assert payload["guardrails"]["source_content_read"] is False
    assert payload["guardrails"]["diff_content_read"] is False
    assert payload["guardrails"]["evidence_acquired"] is False
    assert payload["guardrails"]["validation_executed"] is False
    assert payload["guardrails"]["obligation_invented"] is False
    assert payload["guardrails"]["polarity_inferred"] is False


def test_the_semantic_basis_never_serializes_an_upgrade():
    payload = _sample_assessment_payload()
    assert payload["semantic_basis"] == "analyzer_assessed"
    for item in payload["obligation_results"]:
        assert item["semantic_basis"] == "analyzer_assessed"
    assert "deterministically_verified" not in json.dumps(payload)


# ── The result carries identity, never source content ─────────────────────────

def test_the_result_names_no_path_diff_or_source_excerpt():
    payload = _sample_assessment_payload()
    body = json.dumps(payload)
    for banned in (
        '"diff"',
        '"patch"',
        '"hunk"',
        '"file_content"',
        '"source_text"',
        '"excerpt"',
        '"span"',
        '"repository_root"',
        '"changed_paths"',
    ):
        assert banned not in body, banned


def test_no_check_2_record_carries_a_repository_path_field():
    import dataclasses

    from core.goal_fidelity_review import (
        ExplicitRequirementSource,
        GoalVerificationObligation,
        ObligationClaimBinding,
        ObligationResult,
        PostRunStateBinding,
    )

    banned = ("path", "diff", "patch", "content", "excerpt", "span", "root")
    for record in (
        ExplicitRequirementSource,
        GoalVerificationObligation,
        ObligationClaimBinding,
        ObligationResult,
        PostRunStateBinding,
    ):
        for field in dataclasses.fields(record):
            folded = field.name.casefold()
            for term in banned:
                assert term not in folded, f"{record.__name__}.{field.name}"


# ── Not wired into any live product path ──────────────────────────────────────

_CHECK_2_MODULE_NAMES = frozenset({"goal_fidelity_review"})

_CHECK_2_ENTRY_POINTS = frozenset(
    {"review_goal_fidelity", "render_goal_fidelity_assessment_json"}
)


def _production_python_files() -> Iterable[Path]:
    excluded = {path.resolve() for path in _CHECK_2_SOURCES}
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


def _is_check_2_import(node: ast.AST) -> bool:
    qualified = {f"core.{name}" for name in _CHECK_2_MODULE_NAMES}
    if isinstance(node, ast.Import):
        return any(
            alias.name in _CHECK_2_MODULE_NAMES or alias.name in qualified
            for alias in node.names
        )
    if not isinstance(node, ast.ImportFrom):
        return False
    module = node.module or ""
    if module in _CHECK_2_MODULE_NAMES or module in qualified:
        return True
    return (module == "core" or (node.level and not module)) and any(
        alias.name in _CHECK_2_MODULE_NAMES for alias in node.names
    )


def test_check_2_is_not_imported_or_called_by_a_live_production_path():
    callers: list[str] = []
    for path in _production_python_files():
        tree = _tree(path)
        reasons: set[str] = set()
        for node in ast.walk(tree):
            if _is_check_2_import(node):
                reasons.add(f"import@{node.lineno}")
            if isinstance(node, ast.Call):
                name = _qualified_name(node.func) or ""
                if name.rsplit(".", 1)[-1] in _CHECK_2_ENTRY_POINTS:
                    reasons.add(f"call@{node.lineno}")
                if name == "getattr" and any(
                    isinstance(argument, ast.Constant)
                    and argument.value in _CHECK_2_ENTRY_POINTS
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-call@{node.lineno}")
                if name in {"__import__", "importlib.import_module"} and any(
                    isinstance(argument, ast.Constant)
                    and isinstance(argument.value, str)
                    and (
                        argument.value in _CHECK_2_MODULE_NAMES
                        or argument.value
                        in {f"core.{item}" for item in _CHECK_2_MODULE_NAMES}
                    )
                    for argument in node.args
                ):
                    reasons.add(f"dynamic-import@{node.lineno}")
        if reasons:
            relative = path.relative_to(_REPOSITORY_ROOT).as_posix()
            callers.append(f"{relative}: {', '.join(sorted(reasons))}")

    assert callers == [], callers


def test_check_2_does_not_change_the_frozen_check_1_or_claim_1_behaviour():
    """The two upstream contracts must read exactly as they did before."""
    from core.claim_assessment import ASSESSMENT_STATUSES, SEMANTIC_BASES
    from core.post_run_reconciliation import (
        RECONCILED_MEANING,
        RECONCILIATION_STATUSES,
        reconciliation_authority,
    )

    assert len(ASSESSMENT_STATUSES) == 8
    assert len(SEMANTIC_BASES) == 2
    assert len(RECONCILIATION_STATUSES) == 6
    assert "CHECK.2" in RECONCILED_MEANING
    authority = reconciliation_authority(post_run_reconciliation_authority=True)
    assert authority["semantic_goal_review_authority"] is False
    assert authority["final_success_authority"] is False
