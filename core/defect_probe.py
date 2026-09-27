"""DEFECT.PROBE.LIVE.1 — bounded, independently-oracled reproduction.

Whole-repository validation and a defect probe answer different questions.  A
validation receipt describes repository health; this module can only report
whether one already-localized behavior was observed by one immutable bounded
invocation.  A reproduced probe is execution evidence, but it is neither a
passing repository validation nor patch/write authority.

The production path is intentionally narrow:

* the task must already be routed as defect repair;
* baseline validation remains a separate fact, whether passed, failed or inconclusive;
* CONTROL must already have recalled an eligible exact source target;
* input and expectation must have an allowed non-model provenance; and
* execution uses a static worker under the existing safe argv runner and
  OPS.VALIDATE.2 bytecode isolation.

There is no repository discovery here.  Only a named source file (and, for a
repository-test probe, one named test) is read.  No shell command, ``exec``,
``eval``, model call, network call or model-authored Python string is accepted.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from core.behavioral_expectation import (
    FACT_STATUS_AMBIGUOUS,
    FACT_STATUS_AVAILABLE,
    FACT_STATUS_UNAVAILABLE,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    restore_behavioral_expectations,
    select_probe_behavior_fact,
)
from core.validation_execution import (
    SafeValidationCommand,
    run_safe_validation_command,
)
# INDENT.RUNTIME.1 — the one language label this file's indentation-style
# fixtures declare; reused rather than a second "python" spelling.
from core.indentation_observation import LANGUAGE_PYTHON


PHASE_ID = "DEFECT.PROBE.LIVE.1"
PROBE_SCHEMA_VERSION = "defect_probe_live_1_v1"
PROBE_FINGERPRINT_SCHEMA_VERSION = "immutable_defect_probe_v1"

PROBE_REPRODUCED = "reproduced"
PROBE_NOT_REPRODUCED = "not_reproduced"
PROBE_INCONCLUSIVE = "inconclusive"
PROBE_INVALID = "invalid_probe"
PROBE_UNAVAILABLE = "unavailable"
PROBE_RESULTS: tuple[str, ...] = (
    PROBE_REPRODUCED,
    PROBE_NOT_REPRODUCED,
    PROBE_INCONCLUSIVE,
    PROBE_INVALID,
    PROBE_UNAVAILABLE,
)

PROBE_BASIS_EXPLICIT_USER = "explicit_user_reproducer"
PROBE_BASIS_EXISTING_TEST = "existing_repository_test"
PROBE_BASIS_REPOSITORY_CONTRACT = "repository_contract"
PROBE_BASIS_TASK_FACT_ADAPTER = "deterministic_task_fact_adapter"
PROBE_BASIS_MODEL_AUTHORED = "model_authored"
PROBE_BASIS_UNAVAILABLE = "unavailable"
INDEPENDENT_PROBE_BASES: frozenset[str] = frozenset(
    {
        PROBE_BASIS_EXPLICIT_USER,
        PROBE_BASIS_EXISTING_TEST,
        PROBE_BASIS_REPOSITORY_CONTRACT,
        PROBE_BASIS_TASK_FACT_ADAPTER,
    }
)

INPUT_BASIS_EXPLICIT_USER = "preserved_explicit_user_input"
INPUT_BASIS_EXISTING_TEST = "existing_repository_test_input"
INPUT_BASIS_REPOSITORY_CONTRACT = "repository_contract_input"
INPUT_BASIS_TASK_FACT_ADAPTER = "deterministic_fixture_from_preserved_task_fact"
INPUT_BASIS_MODEL_AUTHORED = "model_authored_input"
INDEPENDENT_INPUT_BASES: frozenset[str] = frozenset(
    {
        INPUT_BASIS_EXPLICIT_USER,
        INPUT_BASIS_EXISTING_TEST,
        INPUT_BASIS_REPOSITORY_CONTRACT,
        INPUT_BASIS_TASK_FACT_ADAPTER,
    }
)

EXPECTATION_BASIS_EXPLICIT_USER = "preserved_explicit_user_requirement"
EXPECTATION_BASIS_EXISTING_TEST = "existing_repository_test_assertion"
EXPECTATION_BASIS_REPOSITORY_CONTRACT = "repository_contract_specification"
EXPECTATION_BASIS_TASK_FACT_ADAPTER = "preserved_task_fact_expected_behavior"
EXPECTATION_BASIS_MODEL_AUTHORED = "model_authored_expectation"
INDEPENDENT_EXPECTATION_BASES: frozenset[str] = frozenset(
    {
        EXPECTATION_BASIS_EXPLICIT_USER,
        EXPECTATION_BASIS_EXISTING_TEST,
        EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        EXPECTATION_BASIS_TASK_FACT_ADAPTER,
    }
)

INVOCATION_PYTHON_PURE_FUNCTION = "python_pure_function"
INVOCATION_EXISTING_PYTEST = "existing_pytest"
INVOCATION_KINDS: tuple[str, ...] = (
    INVOCATION_PYTHON_PURE_FUNCTION,
    INVOCATION_EXISTING_PYTEST,
)

RELATION_EQUALS = "equals"
EXPECTED_RELATIONS: tuple[str, ...] = (RELATION_EQUALS,)

SIDE_EFFECT_READ_ONLY = "read_only_no_network"
EXECUTION_STAGE_PRE_PATCH = "pre_patch"
EXECUTION_STAGE_POST_PATCH = "post_patch"
EXECUTION_STAGES: tuple[str, ...] = (
    EXECUTION_STAGE_PRE_PATCH,
    EXECUTION_STAGE_POST_PATCH,
)

DEFAULT_PROBE_TIMEOUT_SECONDS = 5
MAX_PROBE_TIMEOUT_SECONDS = 10
MAX_CONTRACT_JSON_CHARS = 16_384
MAX_OBSERVED_CHARS = 4_096

# ── DEFECT.FACT.LIVE.1 — behavior-fact vocabulary ─────────────────────────────
#: Where the behavior facts a contract was built from came from.
BEHAVIOR_FACT_SOURCE_TYPED = "typed_preserved_behavioral_expectation"
#: A run whose transport predates typed facts.  Historical only.
BEHAVIOR_FACT_SOURCE_LEGACY = "legacy_raw_prose_adapter"
BEHAVIOR_FACT_SOURCES: tuple[str, ...] = (
    BEHAVIOR_FACT_SOURCE_TYPED,
    BEHAVIOR_FACT_SOURCE_LEGACY,
)

#: Bounded reasons a contract could not be built, in the vocabulary telemetry
#: reports.  Each one is a fact about what was missing, never a guess at what
#: the user might have meant.
#: A run whose transport predates typed facts has no typed fact to report
#: available or missing.  Saying so is what keeps an old receipt readable as an
#: old receipt rather than as a modern one that came up empty.
FACT_STATUS_LEGACY_UNTYPED = "behavior_fact_legacy_raw_adapter"

REASON_BEHAVIOR_FACT_UNAVAILABLE = FACT_STATUS_UNAVAILABLE
REASON_BEHAVIOR_FACT_AMBIGUOUS = FACT_STATUS_AMBIGUOUS
REASON_BEHAVIOR_FACT_UNSUPPORTED = "behavior_fact_subject_unsupported"
REASON_LEGACY_ADAPTER_UNAVAILABLE = "legacy_raw_prose_adapter_unavailable"
REASON_ROUTE_NOT_ELIGIBLE = "route_not_eligible_for_probe"
REASON_TARGET_UNAVAILABLE = "localized_target_unavailable"

#: DEFECT.FACT.LIVE.1 owns the telemetry block this module now publishes.
FACT_PHASE_ID = "DEFECT.FACT.LIVE.1"
PROBE_TELEMETRY_SCHEMA_VERSION = "defect_fact_live_1_probe_telemetry_v1"
#: The one field name the live payload reads probe diagnostics off, everywhere.
PROBE_TELEMETRY_KEY = "defect_probe_telemetry"

CONTRACT_STATUS_BUILT = "built"
CONTRACT_STATUS_UNAVAILABLE = "unavailable"
PROBE_NOT_RUN = "not_run"

#: The subject kinds this phase can adapt into a bounded probe input.  A typed
#: fact outside it is still preserved and still reported; it simply has no
#: deterministic fixture yet, which is a truthful ``unavailable`` rather than a
#: manufactured one.
PROBE_SUPPORTED_SUBJECT_KINDS: tuple[str, ...] = (SUBJECT_INDENTATION_STYLE,)

_INDENT_VALUE_RE = re.compile(r"^(?P<width>[1-8])space$")

_WORKER_ENV = "CATTUS_DEFECT_PROBE_PAYLOAD"
_INDENT_MISCLASSIFICATION = re.compile(
    r"\b(?P<expected>[1-8])\s*(?:-|\s)\s*spaces?\s+indentation\s+"
    r"is\s+classified\s+as\s+(?P<observed>[1-8])\s*(?:-|\s)\s*spaces?\b",
    re.IGNORECASE,
)
_TEST_SELECTOR = re.compile(
    r"^(?P<file>[A-Za-z0-9_./\\-]+\.py)::"
    r"(?P<node>[A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)$"
)


def _canonical_json(value: Any) -> str:
    text = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    if len(text) > MAX_CONTRACT_JSON_CHARS:
        raise ValueError("structured probe payload exceeds its bound")
    return text


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_identity(repo: Path) -> str:
    return _sha256_bytes(str(repo.resolve()).casefold().encode("utf-8"))


def _safe_named_file(repo: Path, relative: str) -> Path | None:
    text = str(relative or "").strip().replace("\\", "/")
    if not text or text.startswith("/") or ":" in text:
        return None
    if any(part in {"", ".", ".."} for part in text.split("/")):
        return None
    try:
        target = (repo / text).resolve()
        target.relative_to(repo)
    except (OSError, ValueError):
        return None
    return target if target.is_file() else None


@dataclass(frozen=True, slots=True)
class ProbeTargetBinding:
    """An exact source target already established by localization."""

    file: str
    symbol: str
    localized_source_sha256: str
    repository_identity: str
    relation: str = "eligible_exact_source"

    @property
    def identity(self) -> str:
        return f"{self.file}::{self.symbol}"

    def as_dict(self) -> dict[str, str]:
        return {
            "file": self.file,
            "symbol": self.symbol,
            "target": self.identity,
            "relation": self.relation,
            "localized_source_sha256": self.localized_source_sha256,
            "repository_identity": self.repository_identity,
        }


@dataclass(frozen=True, slots=True)
class DefectProbeContract:
    """Immutable semantics for one bounded reproduction and its oracle."""

    target: ProbeTargetBinding
    invocation_kind: str
    structured_input_json: str
    expected_relation: str
    expected_json: str
    probe_basis: str
    input_basis: str
    expected_behavior_basis: str
    provenance_reference: str
    expectation_source_paths: tuple[str, ...] = ()
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS
    side_effect_policy: str = SIDE_EFFECT_READ_ONLY
    test_selector: str = ""
    schema_version: str = PROBE_SCHEMA_VERSION

    @property
    def structured_input(self) -> Any:
        return json.loads(self.structured_input_json)

    @property
    def expected(self) -> Any:
        return json.loads(self.expected_json)

    def identity_payload(self) -> dict[str, Any]:
        """Semantically significant immutable oracle and execution fields.

        Run identifiers and timestamps are deliberately absent.  The localized
        source digest remains the pre-patch target binding; it is not rebound to
        candidate bytes when the same contract runs in a sandbox.
        """

        return {
            "fingerprint_schema_version": PROBE_FINGERPRINT_SCHEMA_VERSION,
            "target": self.target.as_dict(),
            "invocation_kind": self.invocation_kind,
            "structured_input": self.structured_input,
            "expected_relation": self.expected_relation,
            "expected": self.expected,
            "expectation_provenance": {
                "probe_basis": self.probe_basis,
                "input_basis": self.input_basis,
                "expected_behavior_basis": self.expected_behavior_basis,
                "provenance_reference": self.provenance_reference,
                "source_paths": list(self.expectation_source_paths),
            },
            "execution_constraints": {
                "timeout_seconds": self.timeout_seconds,
                "side_effect_policy": self.side_effect_policy,
                "test_selector": self.test_selector,
                "probe_schema_version": self.schema_version,
            },
        }

    @property
    def fingerprint(self) -> str:
        return _sha256_bytes(_canonical_json(self.identity_payload()).encode("utf-8"))

    def worker_payload(self, repo: Path) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "repo_path": str(repo),
            "target": self.target.as_dict(),
            "invocation_kind": self.invocation_kind,
            "structured_input": self.structured_input,
            "side_effect_policy": self.side_effect_policy,
            "test_selector": self.test_selector,
        }


@dataclass(frozen=True, slots=True)
class DefectProbeReceipt:
    """Bounded execution facts.  No score, confidence or authority field."""

    attempted: bool
    probe_result: str
    probe_basis: str
    input_basis: str
    expected_behavior_basis: str
    target_binding: ProbeTargetBinding | None = None
    invocation_kind: str = ""
    observed: Any = None
    expected: Any = None
    timeout_seconds: int | None = None
    freshness: str = "unavailable"
    execution_stage: str = EXECUTION_STAGE_PRE_PATCH
    reason: str = ""
    source_sha256: str = ""
    side_effect_policy: str = SIDE_EFFECT_READ_ONLY
    schema_version: str = PROBE_SCHEMA_VERSION
    probe_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.probe_result not in PROBE_RESULTS:
            raise ValueError(f"unsupported probe result: {self.probe_result!r}")
        if self.execution_stage not in EXECUTION_STAGES:
            raise ValueError(f"unsupported execution stage: {self.execution_stage!r}")

    @property
    def target(self) -> str:
        return self.target_binding.identity if self.target_binding else ""

    @property
    def execution_command(self) -> str:
        if self.invocation_kind == INVOCATION_EXISTING_PYTEST:
            return "static_probe_worker:existing_pytest"
        if self.invocation_kind == INVOCATION_PYTHON_PURE_FUNCTION:
            return "static_probe_worker:python_pure_function"
        return ""

    def telemetry_fields(self) -> dict[str, Any]:
        return {
            "defect_probe_attempted": self.attempted,
            "defect_probe_basis": self.probe_basis,
            "defect_probe_target": self.target,
            "defect_probe_result": self.probe_result,
            "defect_probe_observed": self.observed,
            "defect_probe_expected_basis": self.expected_behavior_basis,
            "defect_probe_freshness": self.freshness,
            "defect_probe_fingerprint": self.probe_fingerprint,
        }

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "probe_fingerprint": self.probe_fingerprint,
            "defect_probe_attempted": self.attempted,
            "probe_result": self.probe_result,
            "probe_basis": self.probe_basis,
            "input_basis": self.input_basis,
            "expected_behavior_basis": self.expected_behavior_basis,
            "target_binding": (
                self.target_binding.as_dict() if self.target_binding else None
            ),
            "execution_kind": self.invocation_kind,
            "execution_command": self.execution_command,
            "probe_observed": self.observed,
            "probe_expected": self.expected,
            "timeout_seconds": self.timeout_seconds,
            "probe_freshness": self.freshness,
            "execution_stage": self.execution_stage,
            "probe_reason": self.reason,
            "executed_source_sha256": self.source_sha256,
            "side_effect_policy": self.side_effect_policy,
            "semantics": (
                "bounded behavior reproduction only; not repository validation, "
                "patch correctness, sole-cause proof, or write authority"
            ),
        }


def build_probe_target_binding(
    *,
    repo_path: str | Path,
    target_file: str,
    target_symbol: str,
    source_snippet: str,
    candidate_eligible: bool,
) -> ProbeTargetBinding | None:
    """Bind a probe only to one already-eligible, exact acquired source."""

    if candidate_eligible is not True or not str(source_snippet or "").strip():
        return None
    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError, TypeError):
        return None
    target = _safe_named_file(repo, target_file)
    symbol = str(target_symbol or "").strip()
    if target is None or target.suffix.lower() != ".py" or not symbol.isidentifier():
        return None
    try:
        source_bytes = target.read_bytes()
        # ``read_text`` uses universal newline translation, matching CONTROL's
        # exact-snippet acquisition on Windows while the digest still binds the
        # unmodified bytes that the worker will execute.
        source_text = target.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    if source_snippet not in source_text:
        return None
    return ProbeTargetBinding(
        file=target.relative_to(repo).as_posix(),
        symbol=symbol,
        localized_source_sha256=_sha256_bytes(source_bytes),
        repository_identity=_repo_identity(repo),
    )


def build_python_function_probe(
    *,
    target: ProbeTargetBinding,
    args: Sequence[Any],
    expected: Any,
    probe_basis: str,
    input_basis: str,
    expected_behavior_basis: str,
    provenance_reference: str,
    expectation_source_paths: Sequence[str] = (),
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS,
    kwargs: Mapping[str, Any] | None = None,
) -> DefectProbeContract:
    """Build a data-only invocation; no code or command text is accepted.

    ``kwargs`` (INDENT.RUNTIME.1) is generic bounded transport for any
    JSON-typed keyword the target function's real signature accepts — never
    interpreted here, never special-cased by target symbol name. Omitting it
    reproduces the exact prior wire shape (``"kwargs": {}``).
    """

    return DefectProbeContract(
        target=target,
        invocation_kind=INVOCATION_PYTHON_PURE_FUNCTION,
        structured_input_json=_canonical_json(
            {"args": list(args), "kwargs": dict(kwargs) if kwargs else {}}
        ),
        expected_relation=RELATION_EQUALS,
        expected_json=_canonical_json(expected),
        probe_basis=probe_basis,
        input_basis=input_basis,
        expected_behavior_basis=expected_behavior_basis,
        provenance_reference=str(provenance_reference or "")[:512],
        expectation_source_paths=tuple(
            sorted(
                {
                    str(path or "").strip().replace("\\", "/")
                    for path in expectation_source_paths
                    if str(path or "").strip()
                }
            )
        ),
        timeout_seconds=timeout_seconds,
    )


def build_existing_pytest_probe(
    *,
    target: ProbeTargetBinding,
    test_selector: str,
    provenance_reference: str,
    timeout_seconds: int = DEFAULT_PROBE_TIMEOUT_SECONDS,
) -> DefectProbeContract:
    """Build a narrow existing-test probe from an already-known selector."""

    selector_match = _TEST_SELECTOR.fullmatch(str(test_selector or ""))
    expectation_source_paths = (
        (selector_match.group("file").replace("\\", "/"),)
        if selector_match is not None
        else ()
    )
    return DefectProbeContract(
        target=target,
        invocation_kind=INVOCATION_EXISTING_PYTEST,
        structured_input_json=_canonical_json({"test_selector": test_selector}),
        expected_relation=RELATION_EQUALS,
        expected_json=_canonical_json("test_passes"),
        probe_basis=PROBE_BASIS_EXISTING_TEST,
        input_basis=INPUT_BASIS_EXISTING_TEST,
        expected_behavior_basis=EXPECTATION_BASIS_EXISTING_TEST,
        provenance_reference=str(provenance_reference or test_selector)[:512],
        expectation_source_paths=expectation_source_paths,
        timeout_seconds=timeout_seconds,
        test_selector=str(test_selector or ""),
    )


def _nested_indentation_fixture(width: int) -> str:
    """Deterministically adapt an indentation-width fact into nested text.

    Every depth adds exactly ``width`` spaces.  The shape is reusable for any
    supported width and contains more depth-two-or-greater than depth-one
    lines, which exposes classifiers that count raw prefixes as styles.
    """

    depths = (0, 1, 2, 3, 3, 2, 1)
    return "".join((" " * (width * depth)) + f"level_{index}\n" for index, depth in enumerate(depths))


def build_probe_contract_from_behavior_fact(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
) -> DefectProbeContract | None:
    """Build one bounded contract from an already-typed behavioral expectation.

    DEFECT.FACT.LIVE.1.  This is the authoritative live construction path, and
    it is deliberately not an interpreter: every semantic decision was already
    made at the input boundary, so all that happens here is adapting one typed
    value into a bounded fixture and one typed value into an oracle.

    Direction is pinned.  ``expected_value`` — what the *user* said the behavior
    should be — becomes the probe's expectation; ``observed_value`` becomes part
    of the provenance record and never the oracle.  A probe exists to find out
    whether the code satisfies the user, so a claim can never be checked against
    itself.

    ``None`` means this phase has no deterministic fixture for the fact's
    subject kind.  It never means "close enough".
    """

    if behavior_fact.subject_kind != SUBJECT_INDENTATION_STYLE:
        return None
    expected = _INDENT_VALUE_RE.fullmatch(behavior_fact.expected_value)
    observed = _INDENT_VALUE_RE.fullmatch(behavior_fact.observed_value)
    if expected is None or observed is None:
        return None
    expected_width = int(expected.group("width"))
    ordinal = behavior_fact.obligation_ordinal
    where = (
        f"preserved obligation {ordinal}"
        if ordinal is not None
        else "preserved task text"
    )
    return build_python_function_probe(
        target=target,
        args=(_nested_indentation_fixture(expected_width),),
        expected=behavior_fact.expected_value,
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference=(
            f"typed behavioral expectation ({behavior_fact.subject_kind}, "
            f"{behavior_fact.relation}) from {where}: "
            f"{behavior_fact.source_text}; deterministic nested fixture uses "
            f"{expected_width} spaces per depth; the user reported "
            f"{behavior_fact.observed_value}"
        ),
        # INDENT.RUNTIME.1 §17 — _nested_indentation_fixture is always a
        # Python-shaped sample; this adapter is only ever reached for
        # SUBJECT_INDENTATION_STYLE (guarded above).
        kwargs={"language": LANGUAGE_PYTHON},
    )


def derive_indentation_probe_from_preserved_task(
    *,
    raw_task: str,
    target: ProbeTargetBinding,
) -> DefectProbeContract | None:
    """Legacy raw-prose adapter.  Retained for compatibility, not authority.

    DEFECT.FACT.LIVE.1 moved behavior-fact construction to the input boundary.
    This function still adapts one literal ``N-space ... M-space`` sentence, and
    it is deliberately unchanged: the regex was not widened, because widening it
    would have been one more sentence template rather than a typed fact.

    It is consulted only for transport that predates typed facts — a stored
    receipt or a CONTROL result whose route carries no
    ``behavioral_expectations`` field at all.  Live production reaches
    :func:`build_probe_contract_from_behavior_fact` instead.
    """

    match = _INDENT_MISCLASSIFICATION.search(str(raw_task or ""))
    if match is None:
        return None
    expected_width = int(match.group("expected"))
    observed_width = int(match.group("observed"))
    if expected_width == observed_width:
        return None
    literal_fact = match.group(0)
    return build_python_function_probe(
        target=target,
        args=(_nested_indentation_fixture(expected_width),),
        expected=f"{expected_width}space",
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference=(
            f"preserved literal task fact: {literal_fact}; deterministic nested "
            f"fixture uses {expected_width} spaces per depth; reported behavior "
            f"was {observed_width}space"
        ),
    )


def _validate_contract(
    contract: DefectProbeContract,
    repo: Path,
    *,
    execution_stage: str,
    identity_repo: Path | None = None,
) -> tuple[str, str]:
    if execution_stage not in EXECUTION_STAGES:
        return PROBE_INVALID, "unsupported execution stage"
    if contract.probe_basis not in INDEPENDENT_PROBE_BASES:
        return PROBE_INVALID, "probe basis is not independent of model authorship"
    if contract.input_basis not in INDEPENDENT_INPUT_BASES:
        return PROBE_INVALID, "probe input has no allowed independent basis"
    if contract.expected_behavior_basis not in INDEPENDENT_EXPECTATION_BASES:
        return PROBE_INVALID, "expected behavior has no allowed independent basis"
    if not contract.provenance_reference.strip():
        return PROBE_INVALID, "probe provenance is unavailable or ambiguous"
    if contract.invocation_kind not in INVOCATION_KINDS:
        return PROBE_INVALID, "unsupported invocation kind"
    if contract.expected_relation not in EXPECTED_RELATIONS:
        return PROBE_INVALID, "unsupported expected relation"
    if contract.side_effect_policy != SIDE_EFFECT_READ_ONLY:
        return PROBE_INVALID, "probe side-effect policy is not read-only"
    if (
        not isinstance(contract.timeout_seconds, int)
        or isinstance(contract.timeout_seconds, bool)
        or not 0 < contract.timeout_seconds <= MAX_PROBE_TIMEOUT_SECONDS
    ):
        return PROBE_INVALID, "probe timeout is outside the bounded range"
    if contract.target.repository_identity != _repo_identity(identity_repo or repo):
        return PROBE_INVALID, "probe target belongs to a different repository"
    target_path = _safe_named_file(repo, contract.target.file)
    if target_path is None or target_path.suffix.lower() != ".py":
        return PROBE_INVALID, "probe target source is unavailable"
    try:
        current_digest = _sha256_bytes(target_path.read_bytes())
    except OSError:
        return PROBE_UNAVAILABLE, "probe target source could not be read"
    if (
        execution_stage == EXECUTION_STAGE_PRE_PATCH
        and current_digest != contract.target.localized_source_sha256
    ):
        return PROBE_INVALID, "localized source changed before the pre-patch probe"

    if contract.invocation_kind == INVOCATION_EXISTING_PYTEST:
        match = _TEST_SELECTOR.fullmatch(contract.test_selector)
        if match is None:
            return PROBE_INVALID, "existing test selector is not a bounded node id"
        test_file = _safe_named_file(repo, match.group("file"))
        if test_file is None:
            return PROBE_UNAVAILABLE, "named existing repository test is unavailable"
        try:
            test_source = test_file.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return PROBE_UNAVAILABLE, "named existing repository test is unreadable"
        # A bounded direct binding, not discovery: the named test source must
        # itself reference the already-grounded target symbol.
        if contract.target.symbol not in test_source:
            return PROBE_INVALID, "named test is not source-bound to the target"
    return "", ""


def _invalid_receipt(
    contract: DefectProbeContract,
    result: str,
    reason: str,
    execution_stage: str,
) -> DefectProbeReceipt:
    return DefectProbeReceipt(
        attempted=False,
        probe_result=result,
        probe_basis=contract.probe_basis,
        input_basis=contract.input_basis,
        expected_behavior_basis=contract.expected_behavior_basis,
        target_binding=contract.target,
        invocation_kind=contract.invocation_kind,
        expected=contract.expected,
        timeout_seconds=contract.timeout_seconds,
        freshness="unavailable",
        execution_stage=execution_stage,
        reason=reason,
        probe_fingerprint=contract.fingerprint,
    )


def execute_defect_probe(
    contract: DefectProbeContract,
    *,
    repo_path: str | Path,
    execution_stage: str = EXECUTION_STAGE_PRE_PATCH,
    identity_repo_path: str | Path | None = None,
) -> DefectProbeReceipt:
    """Execute one immutable contract in the static read-only worker."""

    try:
        repo = Path(repo_path).resolve()
    except (OSError, ValueError, TypeError):
        return _invalid_receipt(
            contract, PROBE_UNAVAILABLE, "repository is unavailable", execution_stage
        )

    try:
        identity_repo = (
            Path(identity_repo_path).resolve()
            if identity_repo_path is not None
            else repo
        )
    except (OSError, ValueError, TypeError):
        return _invalid_receipt(
            contract,
            PROBE_INVALID,
            "repository identity origin is unavailable",
            execution_stage,
        )

    invalid_result, invalid_reason = _validate_contract(
        contract,
        repo,
        execution_stage=execution_stage,
        identity_repo=identity_repo,
    )
    if invalid_result:
        return _invalid_receipt(
            contract, invalid_result, invalid_reason, execution_stage
        )

    worker = Path(__file__).with_name("defect_probe_worker.py").resolve()
    try:
        payload_json = _canonical_json(contract.worker_payload(repo))
    except (TypeError, ValueError) as exc:
        return _invalid_receipt(
            contract, PROBE_INVALID, f"structured probe input is invalid: {exc}", execution_stage
        )

    command = SafeValidationCommand(
        command=["python", str(worker)],
        cwd=repo,
        timeout_sec=contract.timeout_seconds,
        env={
            _WORKER_ENV: payload_json,
            # Narrow pytest selection must not import arbitrary user-installed
            # plugins and must not create .pytest_cache in the repository.
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        },
    )
    run = run_safe_validation_command(command)
    freshness = (
        "current_source_isolated_bytecode_cache"
        if run.python_bytecode_cache_isolated
        else "unavailable"
    )
    if run.timed_out:
        return DefectProbeReceipt(
            attempted=True,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="probe timeout exhausted before a behavioral verdict",
            probe_fingerprint=contract.fingerprint,
        )
    if run.blocked or run.exit_code is None:
        return DefectProbeReceipt(
            attempted=not run.blocked,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="static probe worker was unavailable",
            probe_fingerprint=contract.fingerprint,
        )
    if not run.python_bytecode_cache_isolated:
        return DefectProbeReceipt(
            attempted=True,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="current-source bytecode freshness could not be established",
            probe_fingerprint=contract.fingerprint,
        )

    try:
        worker_result = json.loads((run.stdout or "").strip())
    except (TypeError, json.JSONDecodeError):
        worker_result = None
    if not isinstance(worker_result, Mapping) or worker_result.get("status") != "completed":
        status = (
            str(worker_result.get("status"))
            if isinstance(worker_result, Mapping)
            else "worker_output_unavailable"
        )
        if isinstance(worker_result, Mapping) and worker_result.get("error_kind"):
            status = f"{status}:{worker_result.get('error_kind')}"
        return DefectProbeReceipt(
            attempted=True,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            observed=status[:MAX_OBSERVED_CHARS],
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="probe tool/import/call did not produce a behavioral verdict",
            source_sha256=(
                str(worker_result.get("source_sha256") or "")
                if isinstance(worker_result, Mapping)
                else ""
            ),
            probe_fingerprint=contract.fingerprint,
        )

    source_sha256 = str(worker_result.get("source_sha256") or "")
    if not source_sha256:
        return DefectProbeReceipt(
            attempted=True,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="worker did not bind its observation to source bytes",
            probe_fingerprint=contract.fingerprint,
        )
    if (
        execution_stage == EXECUTION_STAGE_PRE_PATCH
        and source_sha256 != contract.target.localized_source_sha256
    ):
        return DefectProbeReceipt(
            attempted=True,
            probe_result=PROBE_INCONCLUSIVE,
            probe_basis=contract.probe_basis,
            input_basis=contract.input_basis,
            expected_behavior_basis=contract.expected_behavior_basis,
            target_binding=contract.target,
            invocation_kind=contract.invocation_kind,
            expected=contract.expected,
            timeout_seconds=contract.timeout_seconds,
            freshness=freshness,
            execution_stage=execution_stage,
            reason="source changed between localization and isolated execution",
            source_sha256=source_sha256,
            probe_fingerprint=contract.fingerprint,
        )

    if contract.invocation_kind == INVOCATION_EXISTING_PYTEST:
        test_exit = worker_result.get("test_exit_code")
        if test_exit == 0:
            reproduced = False
            observed: Any = "test_passed"
        elif test_exit == 1:
            reproduced = True
            observed = "test_failed"
        else:
            return DefectProbeReceipt(
                attempted=True,
                probe_result=PROBE_INCONCLUSIVE,
                probe_basis=contract.probe_basis,
                input_basis=contract.input_basis,
                expected_behavior_basis=contract.expected_behavior_basis,
                target_binding=contract.target,
                invocation_kind=contract.invocation_kind,
                observed=f"pytest_exit_{test_exit}",
                expected=contract.expected,
                timeout_seconds=contract.timeout_seconds,
                freshness=freshness,
                execution_stage=execution_stage,
                reason=(
                    "existing test did not reach a pass/fail verdict: "
                    + str(worker_result.get("tool_diagnostic") or "")[-1000:]
                ),
                source_sha256=source_sha256,
                probe_fingerprint=contract.fingerprint,
            )
    else:
        observed = worker_result.get("observed")
        reproduced = observed != contract.expected

    return DefectProbeReceipt(
        attempted=True,
        probe_result=(PROBE_REPRODUCED if reproduced else PROBE_NOT_REPRODUCED),
        probe_basis=contract.probe_basis,
        input_basis=contract.input_basis,
        expected_behavior_basis=contract.expected_behavior_basis,
        target_binding=contract.target,
        invocation_kind=contract.invocation_kind,
        observed=observed,
        expected=contract.expected,
        timeout_seconds=contract.timeout_seconds,
        freshness=freshness,
        execution_stage=execution_stage,
        reason=(
            "claimed bounded behavior was observed"
            if reproduced
            else "expected bounded behavior was observed"
        ),
        source_sha256=source_sha256,
        probe_fingerprint=contract.fingerprint,
    )


def unavailable_probe_receipt(
    *,
    target: ProbeTargetBinding | None,
    reason: str,
) -> DefectProbeReceipt:
    return DefectProbeReceipt(
        attempted=False,
        probe_result=PROBE_UNAVAILABLE,
        probe_basis=PROBE_BASIS_UNAVAILABLE,
        input_basis="unavailable",
        expected_behavior_basis="unavailable",
        target_binding=target,
        reason=reason,
    )


@dataclass(frozen=True, slots=True)
class ControlProbeResolution:
    """Everything one resolution pass established, before any execution.

    Bounded and honest: when a contract could not be built this still says what
    the target was, which behavior facts were carried, and exactly which of them
    was missing.  Nothing here invents a value to fill a field.
    """

    in_scope: bool
    contract: DefectProbeContract | None = None
    target: ProbeTargetBinding | None = None
    reason_code: str = ""
    reason: str = ""
    behavior_facts: tuple[BehavioralExpectation, ...] = ()
    behavior_fact: BehavioralExpectation | None = None
    behavior_fact_status: str = FACT_STATUS_UNAVAILABLE
    behavior_fact_source: str = BEHAVIOR_FACT_SOURCE_TYPED

    @property
    def contract_status(self) -> str:
        return CONTRACT_STATUS_BUILT if self.contract else CONTRACT_STATUS_UNAVAILABLE


def carried_behavior_facts(
    control_result: Mapping[str, Any],
) -> tuple[tuple[BehavioralExpectation, ...], bool]:
    """Read the typed behavioral facts CONTROL is carrying, without editing one.

    Returns ``(facts, typed_transport_available)``.  The second value separates
    "this run carries no behavior fact" from "this transport predates typed
    facts entirely", which is the difference between a truthful live
    ``unavailable`` and a legacy receipt (see
    :mod:`core.behavioral_expectation`).

    CONTROL may refuse a fact it cannot use.  It may never author one, and there
    is deliberately no code path here that writes an expected or observed value.
    """
    route = (
        control_result.get("live_route")
        if isinstance(control_result, Mapping)
        else None
    )
    if not isinstance(route, Mapping) or "behavioral_expectations" not in route:
        return (), False
    return restore_behavioral_expectations(route.get("behavioral_expectations")), True


def _resolve_behavior_contract(
    control_result: Mapping[str, Any],
    target: ProbeTargetBinding,
) -> "ControlProbeResolution":
    """Build a contract from typed facts, or fall back only for legacy transport."""

    facts, typed_transport = carried_behavior_facts(control_result)

    if not typed_transport:
        # Historical compatibility only.  A run recorded before
        # DEFECT.FACT.LIVE.1 has no typed fact to carry, so the old prose
        # adapter is still what it had; it is not re-promoted for anything that
        # does carry one.
        contract = derive_indentation_probe_from_preserved_task(
            raw_task=str(control_result.get("query") or ""),
            target=target,
        )
        if contract is None:
            return ControlProbeResolution(
                in_scope=True,
                target=target,
                reason_code=REASON_LEGACY_ADAPTER_UNAVAILABLE,
                reason=(
                    "this run carries no typed behavioral expectation and the "
                    "legacy raw-prose adapter did not recognise the task text"
                ),
                behavior_fact_status=FACT_STATUS_LEGACY_UNTYPED,
                behavior_fact_source=BEHAVIOR_FACT_SOURCE_LEGACY,
            )
        return ControlProbeResolution(
            in_scope=True,
            contract=contract,
            target=target,
            behavior_fact_status=FACT_STATUS_LEGACY_UNTYPED,
            behavior_fact_source=BEHAVIOR_FACT_SOURCE_LEGACY,
        )

    fact, status = select_probe_behavior_fact(facts)
    if fact is None:
        return ControlProbeResolution(
            in_scope=True,
            target=target,
            reason_code=status,
            reason=(
                "the order states two incompatible behavioral expectations and "
                "no deterministic rule selects between them"
                if status == FACT_STATUS_AMBIGUOUS
                else "the order states no typed behavioral expectation to probe"
            ),
            behavior_facts=facts,
            behavior_fact_status=status,
        )

    contract = build_probe_contract_from_behavior_fact(
        target=target,
        behavior_fact=fact,
    )
    if contract is None:
        return ControlProbeResolution(
            in_scope=True,
            target=target,
            reason_code=REASON_BEHAVIOR_FACT_UNSUPPORTED,
            reason=(
                "no deterministic bounded fixture exists for a "
                f"{fact.subject_kind} behavioral expectation"
            ),
            behavior_facts=facts,
            behavior_fact=fact,
            behavior_fact_status=status,
        )
    return ControlProbeResolution(
        in_scope=True,
        contract=contract,
        target=target,
        behavior_facts=facts,
        behavior_fact=fact,
        behavior_fact_status=status,
    )


def resolve_control_defect_probe(
    control_result: Mapping[str, Any],
) -> ControlProbeResolution:
    """Decide whether this CONTROL result may probe, and with what contract."""

    if not isinstance(control_result, Mapping):
        return ControlProbeResolution(
            in_scope=False,
            reason_code=REASON_ROUTE_NOT_ELIGIBLE,
            reason="control result is unavailable",
        )
    route = control_result.get("live_route")
    preflight = control_result.get("preflight_validation")
    if not isinstance(route, Mapping) or not isinstance(preflight, Mapping):
        return ControlProbeResolution(
            in_scope=False,
            reason_code=REASON_ROUTE_NOT_ELIGIBLE,
            reason="route or preflight facts are unavailable",
        )
    if route.get("selected_workflow") != "defect_repair_patch":
        return ControlProbeResolution(
            in_scope=False,
            reason_code=REASON_ROUTE_NOT_ELIGIBLE,
            reason="route is not defect repair",
        )
    if route.get("preservation_passed") is not True:
        return ControlProbeResolution(
            in_scope=False,
            reason_code=REASON_ROUTE_NOT_ELIGIBLE,
            reason="task preservation did not pass",
        )
    if preflight.get("outcome") not in {"passed", "failed", "inconclusive"}:
        return ControlProbeResolution(
            in_scope=False,
            reason_code=REASON_ROUTE_NOT_ELIGIBLE,
            reason="whole-repository validation outcome is unavailable",
        )

    facts, _typed_transport = carried_behavior_facts(control_result)
    intent = control_result.get("patch_intent")
    if not isinstance(intent, Mapping):
        return ControlProbeResolution(
            in_scope=True,
            reason_code=REASON_TARGET_UNAVAILABLE,
            reason="localized target metadata is unavailable",
            behavior_facts=facts,
        )
    target_full = str(intent.get("target_symbol_full") or "")
    resolved = control_result.get("entry_resolution") or {}
    resolved_entries = (
        set(str(item) for item in resolved.get("resolved_entry_nodes") or ())
        if isinstance(resolved, Mapping)
        else set()
    )
    target = build_probe_target_binding(
        repo_path=str(control_result.get("repo_path") or ""),
        target_file=str(intent.get("target_file") or ""),
        target_symbol=str(intent.get("target_symbol") or ""),
        source_snippet=str(intent.get("source_snippet") or ""),
        candidate_eligible=bool(target_full and target_full in resolved_entries),
    )
    if target is None:
        return ControlProbeResolution(
            in_scope=True,
            reason_code=REASON_TARGET_UNAVAILABLE,
            reason="target is not an eligible exact source-backed recall result",
            behavior_facts=facts,
        )

    # WHERE and WHAT arrive separately and stay separate: the binding above is
    # the localized target, the resolution below is the typed behavior fact.
    return _resolve_behavior_contract(control_result, target)


def _control_probe_contract_resolution(
    control_result: Mapping[str, Any],
) -> tuple[DefectProbeContract | None, ProbeTargetBinding | None, str, bool]:
    """Backwards-compatible tuple view of :func:`resolve_control_defect_probe`."""

    resolution = resolve_control_defect_probe(control_result)
    return (
        resolution.contract,
        resolution.target,
        resolution.reason,
        resolution.in_scope,
    )


def derive_control_defect_probe_contract(
    control_result: Mapping[str, Any],
) -> DefectProbeContract | None:
    """Rebuild the exact typed contract from preserved, non-model CONTROL facts."""

    contract, _target, _reason, _in_scope = _control_probe_contract_resolution(
        control_result
    )
    return contract


def execute_resolved_control_defect_probe(
    control_result: Mapping[str, Any],
    resolution: ControlProbeResolution,
) -> DefectProbeReceipt | None:
    """Run one already-resolved contract, or report why there is nothing to run.

    Separated from resolution so a caller can attach telemetry describing the
    same pass that executed, rather than resolving a second time and reading
    the repository again to describe what already happened.
    """

    if not resolution.in_scope:
        return None
    if resolution.contract is None:
        return unavailable_probe_receipt(
            target=resolution.target, reason=resolution.reason
        )
    return execute_defect_probe(
        resolution.contract,
        repo_path=str(control_result.get("repo_path") or ""),
    )


def maybe_execute_control_defect_probe(
    control_result: Mapping[str, Any],
) -> DefectProbeReceipt | None:
    """Production adapter from preserved typed facts and existing CONTROL facts.

    ``None`` means this route must not probe.  An ``unavailable`` receipt means
    probing was in scope but no independently-oracled bounded contract existed.
    """

    return execute_resolved_control_defect_probe(
        control_result, resolve_control_defect_probe(control_result)
    )


def build_control_probe_telemetry(
    resolution: ControlProbeResolution,
    receipt: DefectProbeReceipt | None,
) -> dict[str, Any]:
    """Bounded, read-only facts about one probe pass, for the live payload.

    Additive diagnostics and nothing else: no source text, no score, no
    confidence, no authority field, and no value that was not already
    established by the pass this describes.

    Truthfulness is structural.  ``expected`` and ``claimed_observed`` come from
    the *user's* typed fact and are absent when there is none; ``probe_expected``
    and ``probe_observed`` come from the *receipt* and are absent when nothing
    ran.  A probe that never executed reports ``not_run`` rather than borrowing
    the ``inconclusive`` verdict that belongs to a probe that did.
    """

    fact = resolution.behavior_fact
    payload: dict[str, Any] = {
        "schema_version": PROBE_TELEMETRY_SCHEMA_VERSION,
        "phase_id": FACT_PHASE_ID,
        "in_scope": resolution.in_scope,
        "target": resolution.target.identity if resolution.target else None,
        "behavior_fact_status": resolution.behavior_fact_status,
        "behavior_fact_provenance": fact.provenance if fact else None,
        "behavior_fact_source": resolution.behavior_fact_source,
        "behavior_fact_count": len(resolution.behavior_facts),
        "contract_status": resolution.contract_status,
        "unavailable_reason": (
            resolution.reason_code if resolution.contract is None else None
        ),
        "invocation_kind": (
            resolution.contract.invocation_kind if resolution.contract else None
        ),
        "expected": fact.expected_value if fact else None,
        "claimed_observed": fact.observed_value if fact else None,
        "behavior_relation": fact.relation if fact else None,
        "probe_result": PROBE_NOT_RUN,
        "probe_observed": None,
        "probe_expected": None,
        "semantics": (
            "read-only probe diagnostics; a user claim is not defect evidence, "
            "and a bounded reproduction is neither repository validation nor "
            "patch or write authority"
        ),
    }
    if receipt is not None:
        payload["probe_result"] = (
            receipt.probe_result if receipt.attempted else PROBE_NOT_RUN
        )
        payload["probe_receipt_result"] = receipt.probe_result
        payload["probe_attempted"] = receipt.attempted
        payload["probe_fingerprint"] = receipt.probe_fingerprint or None
        if receipt.attempted:
            payload["probe_observed"] = receipt.observed
            payload["probe_expected"] = receipt.expected
        if not payload["unavailable_reason"] and not receipt.attempted:
            payload["unavailable_reason"] = receipt.reason or None
    return payload


def attach_control_probe_telemetry(
    control_result: dict[str, Any],
    telemetry: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record one probe pass's diagnostics on the CONTROL result, additively."""

    if telemetry is not None:
        control_result[PROBE_TELEMETRY_KEY] = telemetry
    return control_result


def attach_probe_telemetry_to_payload(
    control_result: Mapping[str, Any] | None,
    block: Any,
) -> None:
    """Surface CONTROL's existing probe diagnostics on the live payload.

    Read-only and idempotent: it copies the block CONTROL already recorded, so
    no probe is executed, no contract is rebuilt and no repository byte is read
    at display time.
    """

    if not isinstance(block, dict) or not isinstance(control_result, Mapping):
        return
    telemetry = control_result.get(PROBE_TELEMETRY_KEY)
    if isinstance(telemetry, Mapping):
        block[PROBE_TELEMETRY_KEY] = dict(telemetry)


def attach_defect_probe_receipt(
    control_result: dict[str, Any],
    receipt: DefectProbeReceipt,
) -> dict[str, Any]:
    control_result["defect_probe"] = receipt.as_dict()
    control_result.update(receipt.telemetry_fields())
    return control_result


def reproduced_probe_target(payload: Any) -> dict[str, str] | None:
    """Return the exact target only for a receipt allowed to ground a defect."""

    if not isinstance(payload, Mapping):
        return None
    if payload.get("probe_result") != PROBE_REPRODUCED:
        return None
    if payload.get("execution_stage") != EXECUTION_STAGE_PRE_PATCH:
        return None
    if payload.get("probe_basis") not in INDEPENDENT_PROBE_BASES:
        return None
    if payload.get("input_basis") not in INDEPENDENT_INPUT_BASES:
        return None
    if payload.get("expected_behavior_basis") not in INDEPENDENT_EXPECTATION_BASES:
        return None
    if payload.get("probe_freshness") != "current_source_isolated_bytecode_cache":
        return None
    binding = payload.get("target_binding")
    if not isinstance(binding, Mapping):
        return None
    file = str(binding.get("file") or "")
    symbol = str(binding.get("symbol") or "")
    digest = str(payload.get("executed_source_sha256") or "")
    localized_digest = str(binding.get("localized_source_sha256") or "")
    if (
        not file
        or not symbol
        or len(digest) != 64
        or digest != localized_digest
    ):
        return None
    return {
        "file": file,
        "symbol": symbol,
        "relation": "bounded_reproduction_bound",
    }


def defect_probe_guardrails() -> dict[str, bool]:
    return {
        "repository_validation_replaced": False,
        "patch_correctness_established": False,
        "sole_cause_established": False,
        "write_authority_granted": False,
        "model_expectation_accepted": False,
        "arbitrary_code_accepted": False,
        "shell_execution_allowed": False,
        "network_allowed": False,
        "repository_traversal_added": False,
        "global_timeout_changed": False,
        "retrieval_changed": False,
        "ranking_changed": False,
        # DEFECT.FACT.LIVE.1.  Behavior facts are carried, never authored here.
        "behavior_fact_authored_by_control": False,
        "behavior_fact_authored_by_probe": False,
        "raw_prose_reparsed_when_typed_fact_available": False,
        "probe_observation_overwrote_user_claim": False,
    }


__all__ = [
    "PHASE_ID",
    "FACT_PHASE_ID",
    "PROBE_TELEMETRY_KEY",
    "PROBE_TELEMETRY_SCHEMA_VERSION",
    "PROBE_NOT_RUN",
    "CONTRACT_STATUS_BUILT",
    "CONTRACT_STATUS_UNAVAILABLE",
    "BEHAVIOR_FACT_SOURCE_LEGACY",
    "BEHAVIOR_FACT_SOURCE_TYPED",
    "BEHAVIOR_FACT_SOURCES",
    "FACT_STATUS_LEGACY_UNTYPED",
    "REASON_BEHAVIOR_FACT_AMBIGUOUS",
    "REASON_BEHAVIOR_FACT_UNAVAILABLE",
    "REASON_BEHAVIOR_FACT_UNSUPPORTED",
    "REASON_LEGACY_ADAPTER_UNAVAILABLE",
    "REASON_ROUTE_NOT_ELIGIBLE",
    "REASON_TARGET_UNAVAILABLE",
    "PROBE_SUPPORTED_SUBJECT_KINDS",
    "PROBE_SCHEMA_VERSION",
    "PROBE_FINGERPRINT_SCHEMA_VERSION",
    "PROBE_REPRODUCED",
    "PROBE_NOT_REPRODUCED",
    "PROBE_INCONCLUSIVE",
    "PROBE_INVALID",
    "PROBE_UNAVAILABLE",
    "PROBE_RESULTS",
    "PROBE_BASIS_EXPLICIT_USER",
    "PROBE_BASIS_EXISTING_TEST",
    "PROBE_BASIS_REPOSITORY_CONTRACT",
    "PROBE_BASIS_TASK_FACT_ADAPTER",
    "PROBE_BASIS_MODEL_AUTHORED",
    "INPUT_BASIS_EXPLICIT_USER",
    "INPUT_BASIS_EXISTING_TEST",
    "INPUT_BASIS_REPOSITORY_CONTRACT",
    "INPUT_BASIS_TASK_FACT_ADAPTER",
    "INPUT_BASIS_MODEL_AUTHORED",
    "EXPECTATION_BASIS_EXPLICIT_USER",
    "EXPECTATION_BASIS_EXISTING_TEST",
    "EXPECTATION_BASIS_REPOSITORY_CONTRACT",
    "EXPECTATION_BASIS_TASK_FACT_ADAPTER",
    "EXPECTATION_BASIS_MODEL_AUTHORED",
    "INVOCATION_PYTHON_PURE_FUNCTION",
    "INVOCATION_EXISTING_PYTEST",
    "SIDE_EFFECT_READ_ONLY",
    "EXECUTION_STAGE_PRE_PATCH",
    "EXECUTION_STAGE_POST_PATCH",
    "ProbeTargetBinding",
    "DefectProbeContract",
    "DefectProbeReceipt",
    "build_probe_target_binding",
    "build_python_function_probe",
    "build_existing_pytest_probe",
    "derive_indentation_probe_from_preserved_task",
    "build_probe_contract_from_behavior_fact",
    "derive_control_defect_probe_contract",
    "execute_defect_probe",
    "execute_resolved_control_defect_probe",
    "maybe_execute_control_defect_probe",
    "resolve_control_defect_probe",
    "carried_behavior_facts",
    "ControlProbeResolution",
    "build_control_probe_telemetry",
    "attach_control_probe_telemetry",
    "attach_probe_telemetry_to_payload",
    "attach_defect_probe_receipt",
    "reproduced_probe_target",
    "defect_probe_guardrails",
]
