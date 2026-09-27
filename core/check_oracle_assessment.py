"""VALIDATE.ORACLE.LIVE.1 — role of an existing check relative to a probe.

Targeted validation records whether existing checks executed and passed.  That
fact is immutable here.  This module answers a different, additive question:
does a safely extractable assertion for the same bounded target/input relation
agree with the independently grounded behavior in an immutable defect probe?

Only the selected Python/pytest sources supplied by OPS.VALIDATE.3 are read.
The supported assertion language is deliberately small: direct equality,
inequality, and boolean assertions over one call with literal arguments (or
local literal bindings).  Everything more complicated remains unresolved.
There is no model call, test generation, repository traversal, execution, or
authority decision.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
import hashlib
import json
from pathlib import Path
import re
import time
from typing import Any, Mapping, Sequence

from core.defect_probe import (
    INDEPENDENT_EXPECTATION_BASES,
    INDEPENDENT_INPUT_BASES,
    INDEPENDENT_PROBE_BASES,
    INPUT_BASIS_TASK_FACT_ADAPTER,
    RELATION_EQUALS,
    DefectProbeContract,
)
from core.targeted_repository_validation import (
    TargetedCheck,
    TargetedValidationResult,
)
from core.validation_outcome import (
    VALIDATION_FAILED,
    VALIDATION_INCONCLUSIVE,
    VALIDATION_PASSED,
)


PHASE_ID = "VALIDATE.ORACLE.LIVE.1"
ASSESSMENT_SCHEMA_VERSION = "check_oracle_assessment_live_1_v1"

ROLE_CANDIDATE_REGRESSION_ORACLE = "candidate_regression_oracle"
ROLE_DEFECT_PRESERVATION_ORACLE = "defect_preservation_oracle"
ROLE_COMPATIBLE_BUT_NONEXCLUSIVE = "compatible_but_nonexclusive"
ROLE_UNRELATED = "unrelated"
ROLE_CONFLICT_UNRESOLVED = "conflict_unresolved"
ROLE_INSUFFICIENT_BASIS = "insufficient_basis"
ORACLE_ROLES: tuple[str, ...] = (
    ROLE_CANDIDATE_REGRESSION_ORACLE,
    ROLE_DEFECT_PRESERVATION_ORACLE,
    ROLE_COMPATIBLE_BUT_NONEXCLUSIVE,
    ROLE_UNRELATED,
    ROLE_CONFLICT_UNRESOLVED,
    ROLE_INSUFFICIENT_BASIS,
)

ASSESSMENT_CURRENT = "current"
ASSESSMENT_STALE_PROBE = "stale_probe"
ASSESSMENT_STALE_CHECK = "stale_check"
ASSESSMENT_INVALIDATED_CHECK = "candidate_modified_check"
ASSESSMENT_UNAVAILABLE = "unavailable"
ASSESSMENT_STATUSES: tuple[str, ...] = (
    ASSESSMENT_CURRENT,
    ASSESSMENT_STALE_PROBE,
    ASSESSMENT_STALE_CHECK,
    ASSESSMENT_INVALIDATED_CHECK,
    ASSESSMENT_UNAVAILABLE,
)

CHECK_PASSED = "passed"
CHECK_FAILED = "failed"
CHECK_INCONCLUSIVE = "inconclusive"
CHECK_NOT_RUN = "not_run"
CHECK_OUTCOME_UNRESOLVED = "outcome_unresolved"
CHECK_EXECUTION_OUTCOMES: tuple[str, ...] = (
    CHECK_PASSED,
    CHECK_FAILED,
    CHECK_INCONCLUSIVE,
    CHECK_NOT_RUN,
    CHECK_OUTCOME_UNRESOLVED,
)

RELATION_NOT_EQUALS = "not_equals"
#: DEFECT.PROBE.LIVE.3 closure status, spelled here as the literal this
#: module already reads ``defect_closure_status`` with.  Importing
#: :mod:`core.candidate_defect_probe` for one string would pull the sandbox
#: runner into a module whose whole point is that it only parses text.
CLOSURE_FIXED_BUT_REGRESSIVE = "fixed_but_regressive"
MAX_SELECTED_SOURCE_BYTES = 262_144
MAX_ASSERTIONS_PER_CHECK = 64
_FAILED_SELECTOR = re.compile(r"(?m)^FAILED\s+(?P<selector>[^\s]+)")
_MISSING = object()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _normalized_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _bounded_selected_source(repo: Path, relative: str) -> tuple[Path | None, bytes, str]:
    normalized = _normalized_path(relative)
    if not normalized or normalized.startswith("/") or ":" in normalized:
        return None, b"", "selected check path is not a safe repository-relative path"
    if any(part in {"", ".", ".."} for part in normalized.split("/")):
        return None, b"", "selected check path is not a safe repository-relative path"
    try:
        path = (repo / normalized).resolve()
        path.relative_to(repo)
        source = path.read_bytes()
    except (OSError, ValueError):
        return None, b"", "selected check source is unavailable"
    if len(source) > MAX_SELECTED_SOURCE_BYTES:
        return None, b"", "selected check source exceeds the bounded parser size"
    return path, source, ""


def _literal(node: ast.AST, bindings: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Name) and node.id in bindings:
        return bindings[node.id]
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return _MISSING
    try:
        _canonical_json(value)
    except (TypeError, ValueError, OverflowError):
        return _MISSING
    return value


def _bind_literal_statement(statement: ast.stmt, bindings: dict[str, Any]) -> None:
    """Record only a simple local literal binding, in execution order."""

    name = ""
    value_node: ast.AST | None = None
    if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
        target = statement.targets[0]
        if isinstance(target, ast.Name):
            name = target.id
            value_node = statement.value
    elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
        name = statement.target.id
        value_node = statement.value
    if name and value_node is not None:
        value = _literal(value_node, bindings)
        if value is not _MISSING:
            bindings[name] = value


def _called_name(call: ast.Call) -> str:
    function = call.func
    if isinstance(function, ast.Name):
        return function.id
    if isinstance(function, ast.Attribute):
        return function.attr
    return ""


def _indentation_signature(value: str) -> tuple[int, ...] | None:
    lines = value.splitlines()
    if len(lines) < 2:
        return None
    widths: list[int] = []
    for line in lines:
        if not line.strip():
            continue
        prefix = line[: len(line) - len(line.lstrip(" \t"))]
        if "\t" in prefix:
            return None
        widths.append(len(prefix))
    if len(widths) < 2 or not any(widths):
        return None
    return tuple(widths)


def _input_relation(
    *,
    call: ast.Call,
    bindings: Mapping[str, Any],
    contract: DefectProbeContract,
) -> tuple[bool | None, str]:
    if any(isinstance(argument, ast.Starred) for argument in call.args):
        return None, "unsupported starred call argument"
    args: list[Any] = []
    for argument in call.args:
        value = _literal(argument, bindings)
        if value is _MISSING:
            return None, "call input is not a bounded literal"
        args.append(value)
    kwargs: dict[str, Any] = {}
    for keyword in call.keywords:
        if keyword.arg is None:
            return None, "unsupported expanded keyword argument"
        value = _literal(keyword.value, bindings)
        if value is _MISSING:
            return None, "call input is not a bounded literal"
        kwargs[keyword.arg] = value

    structured = contract.structured_input
    if not isinstance(structured, Mapping):
        return None, "probe input is not a structured call"
    expected_args = structured.get("args")
    expected_kwargs = structured.get("kwargs")
    if args == expected_args and kwargs == expected_kwargs:
        return True, "exact_literal_input"

    # DEFECT.PROBE's deterministic task-fact adapter may give identifiers
    # different names while preserving the exact nonblank indentation shape.
    # This comparison is enabled only by that typed provenance; it contains no
    # target or test-name special case.
    if (
        contract.input_basis == INPUT_BASIS_TASK_FACT_ADAPTER
        and kwargs == (expected_kwargs or {})
        and len(args) == 1
        and isinstance(args[0], str)
        and isinstance(expected_args, list)
        and len(expected_args) == 1
        and isinstance(expected_args[0], str)
    ):
        actual_signature = _indentation_signature(args[0])
        expected_signature = _indentation_signature(expected_args[0])
        if actual_signature is not None and actual_signature == expected_signature:
            return True, "typed_indentation_shape_input"
    return False, "different_bounded_input"


@dataclass(frozen=True, slots=True)
class _ExtractedRelation:
    operator: str
    expected: Any
    input_basis: str
    line: int


def _contains_target_call(node: ast.AST, target_symbol: str) -> bool:
    return any(
        isinstance(child, ast.Call) and _called_name(child) == target_symbol
        for child in ast.walk(node)
    )


def _direct_relation(
    assertion: ast.Assert,
    *,
    target_symbol: str,
    bindings: Mapping[str, Any],
    contract: DefectProbeContract,
) -> tuple[_ExtractedRelation | None, bool, bool]:
    """Return ``(relation, matching_target_input, target_seen)``."""

    expression = assertion.test
    call: ast.Call | None = None
    operator = ""
    expected: Any = _MISSING

    if isinstance(expression, ast.Compare) and len(expression.ops) == 1 and len(expression.comparators) == 1:
        left, right = expression.left, expression.comparators[0]
        if isinstance(left, ast.Call) and _called_name(left) == target_symbol:
            call = left
            expected = _literal(right, bindings)
        elif isinstance(right, ast.Call) and _called_name(right) == target_symbol:
            call = right
            expected = _literal(left, bindings)
        if isinstance(expression.ops[0], ast.Eq):
            operator = RELATION_EQUALS
        elif isinstance(expression.ops[0], ast.NotEq):
            operator = RELATION_NOT_EQUALS
    elif isinstance(expression, ast.Call) and _called_name(expression) == target_symbol:
        call = expression
        operator = RELATION_EQUALS
        expected = True
    elif (
        isinstance(expression, ast.UnaryOp)
        and isinstance(expression.op, ast.Not)
        and isinstance(expression.operand, ast.Call)
        and _called_name(expression.operand) == target_symbol
    ):
        call = expression.operand
        operator = RELATION_EQUALS
        expected = False

    target_seen = _contains_target_call(expression, target_symbol)
    if call is None:
        matching_nested = False
        for child in ast.walk(expression):
            if not isinstance(child, ast.Call) or _called_name(child) != target_symbol:
                continue
            matches, _basis = _input_relation(
                call=child,
                bindings=bindings,
                contract=contract,
            )
            if matches is True or matches is None:
                matching_nested = True
                break
        return None, matching_nested, target_seen
    matches, input_basis = _input_relation(
        call=call,
        bindings=bindings,
        contract=contract,
    )
    if matches is not True:
        return None, matches is None, target_seen
    if not operator or expected is _MISSING:
        return None, True, target_seen
    return (
        _ExtractedRelation(
            operator=operator,
            expected=expected,
            input_basis=input_basis,
            line=int(getattr(assertion, "lineno", 0) or 0),
        ),
        True,
        target_seen,
    )


def _selected_functions(tree: ast.Module, identifier: str) -> tuple[ast.AST, ...]:
    _path, separator, node_name = identifier.partition("::")
    functions = tuple(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    if not separator:
        return tuple(node for node in functions if node.name.startswith("test_"))
    return tuple(node for node in functions if node.name == node_name)


def _extract_relations(
    source: bytes,
    *,
    check: TargetedCheck,
    contract: DefectProbeContract,
) -> tuple[tuple[_ExtractedRelation, ...], bool, bool, str]:
    try:
        tree = ast.parse(source, filename=check.path)
    except (SyntaxError, ValueError, MemoryError, RecursionError):
        return (), True, False, "selected check source could not be parsed safely"
    functions = _selected_functions(tree, check.identifier)
    if not functions:
        return (), True, False, "selected pytest identity was not found in its source"

    relations: list[_ExtractedRelation] = []
    unsupported_matching = False
    target_seen = False
    assertion_count = 0
    for function in functions:
        assert isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef))
        bindings: dict[str, Any] = {}
        for statement in function.body:
            if not isinstance(statement, ast.Assert):
                _bind_literal_statement(statement, bindings)
                for child in ast.walk(statement):
                    if (
                        not isinstance(child, ast.Call)
                        or _called_name(child) != contract.target.symbol
                    ):
                        continue
                    target_seen = True
                    matches, _basis = _input_relation(
                        call=child,
                        bindings=bindings,
                        contract=contract,
                    )
                    if matches is True or matches is None:
                        unsupported_matching = True
                continue
            assertion_count += 1
            if assertion_count > MAX_ASSERTIONS_PER_CHECK:
                return (), True, target_seen, "selected check exceeds the assertion bound"
            relation, matching_or_unknown, seen = _direct_relation(
                statement,
                target_symbol=contract.target.symbol,
                bindings=bindings,
                contract=contract,
            )
            target_seen = target_seen or seen
            if relation is not None:
                relations.append(relation)
            elif matching_or_unknown:
                unsupported_matching = True
    return tuple(relations), unsupported_matching, target_seen, ""


def _semantic_role(
    relations: Sequence[_ExtractedRelation],
    *,
    contract: DefectProbeContract,
    unsupported_matching: bool,
    target_seen: bool,
) -> tuple[str, str]:
    if contract.expected_relation != RELATION_EQUALS:
        return ROLE_CONFLICT_UNRESOLVED, "probe expected relation is unsupported"
    if not relations:
        if unsupported_matching:
            return (
                ROLE_CONFLICT_UNRESOLVED,
                "same target/input relation is present but its assertion is unsupported",
            )
        if target_seen:
            return ROLE_UNRELATED, "selected check exercises a different bounded input relation"
        return ROLE_UNRELATED, "selected check has no assertion for the bounded probe relation"
    if unsupported_matching:
        return (
            ROLE_CONFLICT_UNRESOLVED,
            "at least one same target/input assertion is outside the bounded relation language",
        )

    desired = contract.expected
    compatible: list[_ExtractedRelation] = []
    conflicting: list[_ExtractedRelation] = []
    for relation in relations:
        if relation.operator == RELATION_EQUALS:
            (compatible if relation.expected == desired else conflicting).append(relation)
        elif relation.operator == RELATION_NOT_EQUALS:
            (conflicting if relation.expected == desired else compatible).append(relation)
        else:
            return ROLE_CONFLICT_UNRESOLVED, "extracted relation operator is unsupported"
    line_list = ",".join(str(item.line) for item in relations)
    input_kinds = ",".join(sorted({item.input_basis for item in relations}))
    basis = (
        f"structured assertions at lines {line_list}; input={input_kinds}; "
        f"independent expectation={contract.expected_behavior_basis}"
    )
    if compatible and conflicting:
        return ROLE_CONFLICT_UNRESOLVED, basis + "; assertions disagree with each other"
    if conflicting:
        return ROLE_DEFECT_PRESERVATION_ORACLE, basis + "; assertion conflicts with desired behavior"
    if all(item.operator == RELATION_EQUALS for item in compatible):
        return ROLE_CANDIDATE_REGRESSION_ORACLE, basis + "; assertion equals desired behavior"
    return ROLE_COMPATIBLE_BUT_NONEXCLUSIVE, basis + "; assertion permits desired behavior"


def _failed_check_ids(output: str, checks: Sequence[TargetedCheck]) -> frozenset[str]:
    reported = {
        match.group("selector").replace("\\", "/")
        for match in _FAILED_SELECTOR.finditer(str(output or ""))
    }
    failed: set[str] = set()
    for check in checks:
        identifier = _normalized_path(check.identifier)
        if identifier in reported:
            failed.add(check.identifier)
        elif "::" not in identifier and any(
            item.startswith(identifier + "::") for item in reported
        ):
            failed.add(check.identifier)
    return frozenset(failed)


def _check_execution_outcome(
    check: TargetedCheck,
    result: TargetedValidationResult,
    failed_ids: frozenset[str],
) -> str:
    executed = frozenset(result.candidate_checks_executed)
    if check.identifier not in executed:
        return CHECK_NOT_RUN
    if result.candidate_outcome == VALIDATION_PASSED:
        return CHECK_PASSED
    if result.candidate_outcome == VALIDATION_INCONCLUSIVE:
        return CHECK_INCONCLUSIVE
    if result.candidate_outcome == VALIDATION_FAILED:
        if check.identifier in failed_ids or len(executed) == 1:
            return CHECK_FAILED
        return CHECK_OUTCOME_UNRESOLVED
    return CHECK_OUTCOME_UNRESOLVED


@dataclass(frozen=True, slots=True)
class CheckOracleAssessment:
    check_id: str
    check_execution_outcome: str
    oracle_role: str
    probe_fingerprint: str
    role_basis: str
    check_path: str
    check_source_sha256: str
    check_fingerprint: str
    assessment_status: str = ASSESSMENT_CURRENT
    candidate_fingerprint: str = ""
    schema_version: str = ASSESSMENT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.oracle_role not in ORACLE_ROLES:
            raise ValueError(f"unsupported oracle role: {self.oracle_role!r}")
        if self.assessment_status not in ASSESSMENT_STATUSES:
            raise ValueError(f"unsupported assessment status: {self.assessment_status!r}")
        if self.check_execution_outcome not in CHECK_EXECUTION_OUTCOMES:
            raise ValueError(
                f"unsupported check execution outcome: {self.check_execution_outcome!r}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "check_execution_outcome": self.check_execution_outcome,
            "oracle_role": self.oracle_role,
            "probe_fingerprint": self.probe_fingerprint,
            "role_basis": self.role_basis,
            "check_path": self.check_path,
            "check_source_sha256": self.check_source_sha256,
            "check_fingerprint": self.check_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "assessment_status": self.assessment_status,
        }


@dataclass(frozen=True, slots=True)
class CheckOracleAssessmentReceipt:
    assessments: tuple[CheckOracleAssessment, ...]
    probe_fingerprint: str
    targeted_check_set_fingerprint: str
    candidate_fingerprint: str
    assessment_status: str
    evidence_matrix: dict[str, Any]
    timings: dict[str, float] = field(default_factory=dict)
    schema_version: str = ASSESSMENT_SCHEMA_VERSION

    def as_telemetry(self) -> dict[str, Any]:
        counts = {role: 0 for role in ORACLE_ROLES}
        for assessment in self.assessments:
            counts[assessment.oracle_role] += 1
        return {
            "check_oracle_assessment_status": self.assessment_status,
            "check_oracle_assessments": [item.as_dict() for item in self.assessments],
            "check_oracle_probe_fingerprint": self.probe_fingerprint,
            "check_oracle_check_set_fingerprint": self.targeted_check_set_fingerprint,
            "check_oracle_candidate_fingerprint": self.candidate_fingerprint,
            "check_oracle_role_counts": counts,
            "check_oracle_evidence_matrix": dict(self.evidence_matrix),
            "check_oracle_timings": dict(self.timings),
            "check_oracle_authority_effect": "none",
            "check_oracle_model_calls": 0,
            "check_oracle_network_calls": 0,
            "check_oracle_repository_traversals": 0,
        }


def _independent_basis_error(contract: DefectProbeContract, check: TargetedCheck) -> str:
    if contract.probe_basis not in INDEPENDENT_PROBE_BASES:
        return "probe basis is not independent"
    if contract.input_basis not in INDEPENDENT_INPUT_BASES:
        return "probe input basis is not independent"
    if contract.expected_behavior_basis not in INDEPENDENT_EXPECTATION_BASES:
        return "desired behavior basis is not independent"
    if not contract.provenance_reference.strip():
        return "desired behavior provenance is unavailable"
    expectation_paths = {
        _normalized_path(path) for path in contract.expectation_source_paths
    }
    if (
        contract.expected_behavior_basis == "existing_repository_test_assertion"
        and _normalized_path(check.path) in expectation_paths
    ):
        return "the selected check is the probe expectation source, not an independent comparator"
    return ""


def _assessment_status(assessments: Sequence[CheckOracleAssessment]) -> str:
    statuses = {item.assessment_status for item in assessments}
    if not statuses or statuses == {ASSESSMENT_CURRENT}:
        return ASSESSMENT_CURRENT
    if ASSESSMENT_STALE_PROBE in statuses:
        return ASSESSMENT_STALE_PROBE
    if ASSESSMENT_INVALIDATED_CHECK in statuses:
        return ASSESSMENT_INVALIDATED_CHECK
    return ASSESSMENT_UNAVAILABLE


def _matrix(
    *,
    assessments: Sequence[CheckOracleAssessment],
    targeted: TargetedValidationResult,
    closure: Mapping[str, Any],
    full_validation: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "full_validation": {
            "outcome": full_validation.get("outcome"),
            "category": full_validation.get("category"),
        },
        "pre_probe": {
            "result": closure.get("pre_probe_result") or targeted.pre_patch_probe_result,
            "observed": closure.get("pre_probe_observed"),
        },
        "post_probe": {
            "result": closure.get("post_probe_result"),
            "observed": closure.get("post_probe_observed"),
            "defect_closure_status": closure.get("defect_closure_status"),
        },
        "targeted_validation": {
            "outcome": targeted.status,
            "category": targeted.category,
        },
        "selected_checks": [item.as_dict() for item in assessments],
    }


def assess_selected_check_oracles(
    *,
    repo_path: str | Path,
    probe_contract: DefectProbeContract,
    targeted_validation: TargetedValidationResult,
    defect_closure: Mapping[str, Any] | None = None,
    full_validation: Mapping[str, Any] | None = None,
) -> CheckOracleAssessmentReceipt:
    """Classify only OPS.VALIDATE.3's immutable selected check set."""

    started = time.perf_counter()
    closure = defect_closure if isinstance(defect_closure, Mapping) else {}
    full = full_validation if isinstance(full_validation, Mapping) else {}
    request = targeted_validation.request
    recorded_probe = str(closure.get("probe_fingerprint") or probe_contract.fingerprint)
    probe_stale = recorded_probe != probe_contract.fingerprint
    changed_paths = {_normalized_path(path) for path in request.changed_paths}
    failed_ids = _failed_check_ids(
        targeted_validation.output_excerpt,
        request.selected_checks,
    )

    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError, TypeError):
        repo = Path(repo_path)
    assessments: list[CheckOracleAssessment] = []
    source_read_seconds = 0.0
    parse_seconds = 0.0

    for check in request.selected_checks:
        read_started = time.perf_counter()
        path, source, source_error = _bounded_selected_source(repo, check.path)
        source_read_seconds += time.perf_counter() - read_started
        source_digest = hashlib.sha256(source).hexdigest() if source else ""
        check_fingerprint = _fingerprint(
            {
                "check_id": check.identifier,
                "check_path": check.path,
                "source_sha256": source_digest,
            }
        )
        execution = _check_execution_outcome(check, targeted_validation, failed_ids)
        status = ASSESSMENT_CURRENT
        role = ROLE_CONFLICT_UNRESOLVED
        basis = ""

        if probe_stale:
            status = ASSESSMENT_STALE_PROBE
            role = ROLE_INSUFFICIENT_BASIS
            basis = "recorded closure probe fingerprint does not match the immutable probe"
        elif _normalized_path(check.path) in changed_paths:
            status = ASSESSMENT_INVALIDATED_CHECK
            role = ROLE_INSUFFICIENT_BASIS
            basis = "candidate modifies the selected check; OPS.VALIDATE.3 evidence is invalid"
        else:
            basis_error = _independent_basis_error(probe_contract, check)
            if basis_error:
                role = ROLE_INSUFFICIENT_BASIS
                basis = basis_error
            elif _normalized_path(check.relation_target) not in {
                _normalized_path(probe_contract.target.identity),
                _normalized_path(probe_contract.target.file),
                "preserved_user_command",
            }:
                role = ROLE_UNRELATED
                basis = "selected structural relation is not bound to the probe target"
            elif path is None or source_error:
                status = ASSESSMENT_UNAVAILABLE
                role = ROLE_CONFLICT_UNRESOLVED
                basis = source_error or "selected check source is unavailable"
            else:
                parse_started = time.perf_counter()
                relations, unsupported, target_seen, parse_error = _extract_relations(
                    source,
                    check=check,
                    contract=probe_contract,
                )
                parse_seconds += time.perf_counter() - parse_started
                if parse_error:
                    status = ASSESSMENT_UNAVAILABLE
                    role = ROLE_CONFLICT_UNRESOLVED
                    basis = parse_error
                else:
                    role, basis = _semantic_role(
                        relations,
                        contract=probe_contract,
                        unsupported_matching=unsupported,
                        target_seen=target_seen,
                    )

        assessments.append(
            CheckOracleAssessment(
                check_id=check.identifier,
                check_execution_outcome=execution,
                oracle_role=role,
                probe_fingerprint=probe_contract.fingerprint,
                role_basis=basis,
                check_path=check.path,
                check_source_sha256=source_digest,
                check_fingerprint=check_fingerprint,
                assessment_status=status,
                candidate_fingerprint=request.candidate_fingerprint,
            )
        )

    elapsed = time.perf_counter() - started
    receipt_status = _assessment_status(assessments)
    matrix = _matrix(
        assessments=assessments,
        targeted=targeted_validation,
        closure=closure,
        full_validation=full,
    )
    return CheckOracleAssessmentReceipt(
        assessments=tuple(assessments),
        probe_fingerprint=probe_contract.fingerprint,
        targeted_check_set_fingerprint=request.check_set_fingerprint,
        candidate_fingerprint=request.candidate_fingerprint,
        assessment_status=receipt_status,
        evidence_matrix=matrix,
        timings={
            "selected_source_read_seconds": round(source_read_seconds, 6),
            "bounded_ast_parse_seconds": round(parse_seconds, 6),
            "total_seconds": round(elapsed, 6),
            "selected_check_count": len(assessments),
        },
    )


def check_oracle_assessment_is_current(
    assessment: CheckOracleAssessment,
    *,
    probe_contract: DefectProbeContract,
    repo_path: str | Path,
) -> bool:
    """A changed probe or selected source makes a prior assessment stale."""

    return check_oracle_assessment_freshness(
        assessment,
        probe_contract=probe_contract,
        repo_path=repo_path,
    ) == ASSESSMENT_CURRENT


def check_oracle_assessment_freshness(
    assessment: CheckOracleAssessment,
    *,
    probe_contract: DefectProbeContract,
    repo_path: str | Path,
) -> str:
    """Return the explicit current/stale status of a prior assessment."""

    if assessment.assessment_status != ASSESSMENT_CURRENT:
        return assessment.assessment_status
    if assessment.probe_fingerprint != probe_contract.fingerprint:
        return ASSESSMENT_STALE_PROBE
    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError, TypeError):
        return ASSESSMENT_STALE_CHECK
    _path, source, error = _bounded_selected_source(repo, assessment.check_path)
    if error or not source:
        return ASSESSMENT_STALE_CHECK
    if hashlib.sha256(source).hexdigest() != assessment.check_source_sha256:
        return ASSESSMENT_STALE_CHECK
    return ASSESSMENT_CURRENT


def describe_check_oracle_assessment(receipt: CheckOracleAssessmentReceipt) -> str:
    roles = {item.oracle_role for item in receipt.assessments}
    post = receipt.evidence_matrix.get("post_probe") or {}
    targeted = receipt.evidence_matrix.get("targeted_validation") or {}
    if post.get("defect_closure_status") == CLOSURE_FIXED_BUT_REGRESSIVE:
        # The paired oracle already answered this, and no arrangement of
        # existing-check roles may restate a regressive candidate as a fixed one.
        return (
            "The defect-specific probe closed, but a bounded preservation "
            "counter-case the baseline already satisfied did not survive the "
            "candidate; this candidate is not fixed."
        )
    if (
        roles
        and roles == {ROLE_DEFECT_PRESERVATION_ORACLE}
        and post.get("defect_closure_status") == "fixed"
        and targeted.get("outcome") == VALIDATION_FAILED
    ):
        return (
            "The defect-specific probe is fixed, but existing targeted checks "
            "failed; the supported assertions preserve the previously observed behavior."
        )
    if roles and roles == {ROLE_DEFECT_PRESERVATION_ORACLE}:
        return (
            "The supported existing assertions conflict with the independently "
            "grounded desired behavior; execution facts remain unchanged."
        )
    if ROLE_CONFLICT_UNRESOLVED in roles or ROLE_INSUFFICIENT_BASIS in roles:
        return (
            "The probe and targeted-check facts remain separate; at least one "
            "check's relationship to the desired behavior is unresolved."
        )
    return "Existing targeted checks were classified relative to the independent probe."


def check_oracle_guardrails() -> dict[str, bool]:
    return {
        "selected_checks_only": True,
        "bounded_selected_source_reads_only": True,
        "check_execution_rewritten": False,
        "targeted_validation_rewritten": False,
        "full_validation_rewritten": False,
        "post_probe_rewritten": False,
        "regressive_closure_read_as_fixed": False,
        "generated_test_accepted_as_independent": False,
        "candidate_modified_check_rehabilitated": False,
        "test_name_heuristics_used": False,
        "replacement_test_generated": False,
        "patch_authority_granted": False,
        "execution_authority_granted": False,
        "auto_apply_granted": False,
        "retrieval_changed": False,
        "model_called": False,
        "network_called": False,
        "repository_traversed": False,
    }


__all__ = [
    "PHASE_ID",
    "ASSESSMENT_SCHEMA_VERSION",
    "CLOSURE_FIXED_BUT_REGRESSIVE",
    "ROLE_CANDIDATE_REGRESSION_ORACLE",
    "ROLE_DEFECT_PRESERVATION_ORACLE",
    "ROLE_COMPATIBLE_BUT_NONEXCLUSIVE",
    "ROLE_UNRELATED",
    "ROLE_CONFLICT_UNRESOLVED",
    "ROLE_INSUFFICIENT_BASIS",
    "ORACLE_ROLES",
    "ASSESSMENT_CURRENT",
    "ASSESSMENT_STALE_PROBE",
    "ASSESSMENT_STALE_CHECK",
    "ASSESSMENT_INVALIDATED_CHECK",
    "ASSESSMENT_UNAVAILABLE",
    "CHECK_PASSED",
    "CHECK_FAILED",
    "CHECK_INCONCLUSIVE",
    "CHECK_NOT_RUN",
    "CHECK_OUTCOME_UNRESOLVED",
    "CheckOracleAssessment",
    "CheckOracleAssessmentReceipt",
    "assess_selected_check_oracles",
    "check_oracle_assessment_is_current",
    "check_oracle_assessment_freshness",
    "describe_check_oracle_assessment",
    "check_oracle_guardrails",
]
