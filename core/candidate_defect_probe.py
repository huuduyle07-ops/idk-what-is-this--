"""DEFECT.PROBE.LIVE.2 — immutable pre/post candidate reproduction closure.

This module evaluates one already-safe exact patch plan against the same
independently-grounded :class:`core.defect_probe.DefectProbeContract` that
reproduced the pre-patch symptom.  Candidate bytes exist only in the existing
managed disposable sandbox and are materialized by the production patch-plan
executor.  The resulting fact is deliberately independent of full validation,
targeted validation, patch basis, and execution authorization.

DEFECT.PROBE.LIVE.3 added exactly two things here and changed nothing else.
``preservation_probes`` lets a caller run further already-built immutable
contracts against the *same* sandbox bytes the primary post-probe saw, and
their raw receipts come back untouched; deciding what those observations mean
belongs to :mod:`core.paired_defect_probe`, not to this module.  And
``fixed_but_regressive`` joined the closure vocabulary so a paired assessment
can express "the claimed defect closed and previously-correct behavior did
not survive" without overloading ``fixed``, which existing readers compare
against directly.  With no preservation probes supplied — every task without a
preservation adapter — this module behaves exactly as it did before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import shutil
import tempfile
import time
from typing import Any, Mapping, Sequence

from core.candidate_sandbox_validation import (
    normalize_candidate_plan,
    patch_plan_fingerprint,
)
from core.defect_probe import (
    EXECUTION_STAGE_POST_PATCH,
    EXECUTION_STAGE_PRE_PATCH,
    EXPECTATION_BASIS_EXISTING_TEST,
    EXPECTATION_BASIS_REPOSITORY_CONTRACT,
    PROBE_INCONCLUSIVE,
    PROBE_INVALID,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    PROBE_UNAVAILABLE,
    DefectProbeContract,
    DefectProbeReceipt,
    execute_defect_probe,
    reproduced_probe_target,
)
from core.sandbox_self_evolution_runner import (
    cleanup_managed_sandbox,
    create_managed_sandbox,
)


PHASE_ID = "DEFECT.PROBE.LIVE.2"
RECEIPT_SCHEMA_VERSION = "candidate_defect_probe_live_2_v1"

CLOSURE_FIXED = "fixed"
#: DEFECT.PROBE.LIVE.3.  The primary case closed and a preservation case the
#: baseline already satisfied did not survive the candidate.  It is deliberately
#: not ``fixed``: every consumer that reads this field compares it against that
#: literal, so a regressive candidate must never arrive carrying it.
CLOSURE_FIXED_BUT_REGRESSIVE = "fixed_but_regressive"
CLOSURE_STILL_REPRODUCED = "still_reproduced"
CLOSURE_CHANGED_BUT_UNRESOLVED = "changed_but_unresolved"
CLOSURE_INCONCLUSIVE = "inconclusive"
CLOSURE_INVALID_COMPARISON = "invalid_comparison"
CLOSURE_UNAVAILABLE = "unavailable"
CLOSURE_STATUSES: tuple[str, ...] = (
    CLOSURE_FIXED,
    CLOSURE_FIXED_BUT_REGRESSIVE,
    CLOSURE_STILL_REPRODUCED,
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_INCONCLUSIVE,
    CLOSURE_INVALID_COMPARISON,
    CLOSURE_UNAVAILABLE,
)

APPLY_NOT_ATTEMPTED = "not_attempted"
APPLY_APPLIED = "applied"
APPLY_FAILED = "failed"
APPLY_UNAVAILABLE = "unavailable"


def _receipt_payload(receipt: DefectProbeReceipt | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(receipt, DefectProbeReceipt):
        return receipt.as_dict()
    return receipt if isinstance(receipt, Mapping) else {}


def _receipt_observed(payload: Mapping[str, Any]) -> Any:
    if "probe_observed" in payload:
        return payload.get("probe_observed")
    return payload.get("observed")


def _normalized_path(value: Any) -> str:
    return str(value or "").strip().replace("\\", "/")


def _candidate_paths(plan: Sequence[Mapping[str, Any]]) -> frozenset[str]:
    return frozenset(
        _normalized_path(op.get("path"))
        for op in normalize_candidate_plan(plan)
        if _normalized_path(op.get("path"))
    )


def _oracle_integrity_error(
    contract: DefectProbeContract,
    plan: Sequence[Mapping[str, Any]],
) -> str:
    source_paths = frozenset(
        _normalized_path(path)
        for path in contract.expectation_source_paths
        if _normalized_path(path)
    )
    if (
        contract.expected_behavior_basis
        in {EXPECTATION_BASIS_EXISTING_TEST, EXPECTATION_BASIS_REPOSITORY_CONTRACT}
        and not source_paths
    ):
        return (
            "independent repository-backed expectation has no immutable source "
            "artifact binding"
        )
    touched = sorted(_candidate_paths(plan).intersection(source_paths))
    if touched:
        return "candidate modifies the immutable probe oracle artifact: " + ", ".join(touched)
    return ""


@dataclass(frozen=True, slots=True)
class CandidateDefectClosureReceipt:
    """Bounded candidate evidence; never an aggregate validation verdict."""

    probe_fingerprint: str
    candidate_fingerprint: str
    pre_probe_result: str
    pre_probe_observed: Any
    post_probe_result: str
    post_probe_observed: Any
    expected_behavior_basis: str
    defect_closure_status: str
    reason: str = ""
    sandbox_only: bool = True
    candidate_apply_status: str = APPLY_NOT_ATTEMPTED
    sandbox_cleanup_ok: bool = True
    timings: dict[str, float] = field(default_factory=dict)
    #: DEFECT.PROBE.LIVE.3 companion observations, as ``(case_id, receipt)``
    #: pairs in the order they were requested.  Raw execution facts only: this
    #: module runs them and reports them, and never reads one to decide the
    #: closure status.
    preservation_probe_receipts: tuple[tuple[str, DefectProbeReceipt], ...] = ()
    schema_version: str = RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.defect_closure_status not in CLOSURE_STATUSES:
            raise ValueError(
                f"unsupported defect closure status: {self.defect_closure_status!r}"
            )
        if self.sandbox_only is not True:
            raise ValueError("candidate defect closure evidence must be sandbox-only")

    def as_telemetry(self) -> dict[str, Any]:
        return {
            "phase_id": PHASE_ID,
            "schema_version": self.schema_version,
            "probe_fingerprint": self.probe_fingerprint,
            "candidate_fingerprint": self.candidate_fingerprint,
            "pre_probe_result": self.pre_probe_result,
            "pre_probe_observed": self.pre_probe_observed,
            "post_probe_result": self.post_probe_result,
            "post_probe_observed": self.post_probe_observed,
            "expected_behavior_basis": self.expected_behavior_basis,
            "defect_closure_status": self.defect_closure_status,
            "defect_closure_reason": self.reason,
            "sandbox_only": True,
            "candidate_probe_apply_status": self.candidate_apply_status,
            "candidate_probe_sandbox_cleanup_ok": self.sandbox_cleanup_ok,
            "candidate_probe_timings": dict(self.timings),
            "candidate_probe_authority_effect": "none",
        }


def candidate_defect_closure_is_current(payload: Any, plan: Any) -> bool:
    """A refinement invalidates all evidence bound to the earlier candidate."""

    if not isinstance(payload, Mapping):
        return False
    if payload.get("defect_closure_status") not in CLOSURE_STATUSES:
        return False
    recorded = str(payload.get("candidate_fingerprint") or "")
    return bool(recorded) and recorded == patch_plan_fingerprint(plan)


def _receipt(
    *,
    contract: DefectProbeContract,
    candidate_fingerprint: str,
    pre_payload: Mapping[str, Any],
    status: str,
    reason: str,
    post_receipt: DefectProbeReceipt | None = None,
    apply_status: str = APPLY_NOT_ATTEMPTED,
    cleanup_ok: bool = True,
    timings: Mapping[str, float] | None = None,
    preservation_receipts: Sequence[tuple[str, DefectProbeReceipt]] = (),
) -> CandidateDefectClosureReceipt:
    return CandidateDefectClosureReceipt(
        probe_fingerprint=contract.fingerprint,
        candidate_fingerprint=candidate_fingerprint,
        pre_probe_result=str(pre_payload.get("probe_result") or ""),
        pre_probe_observed=_receipt_observed(pre_payload),
        post_probe_result=(post_receipt.probe_result if post_receipt else PROBE_UNAVAILABLE),
        post_probe_observed=(post_receipt.observed if post_receipt else None),
        expected_behavior_basis=contract.expected_behavior_basis,
        defect_closure_status=status,
        reason=reason,
        candidate_apply_status=apply_status,
        sandbox_cleanup_ok=cleanup_ok,
        timings=dict(timings or {}),
        preservation_probe_receipts=tuple(preservation_receipts),
    )


def _cleanup(sandbox_root: Path | None, temp_root: Path | None) -> bool:
    ok = True
    if sandbox_root is not None and sandbox_root.exists():
        try:
            cleaned, _reason = cleanup_managed_sandbox(sandbox_root)
            ok = bool(cleaned)
        except Exception:
            ok = False
    if temp_root is not None:
        try:
            if temp_root.exists():
                shutil.rmtree(temp_root, ignore_errors=True)
        except Exception:
            ok = False
        ok = ok and not temp_root.exists()
    return ok


def evaluate_candidate_defect_closure(
    *,
    repo_path: str | Path,
    candidate_plan: Any,
    probe_contract: DefectProbeContract,
    pre_probe_receipt: DefectProbeReceipt | Mapping[str, Any],
    patch_safety: Mapping[str, Any],
    expected_candidate_fingerprint: str = "",
    sandbox_parent: str | Path | None = None,
    preservation_probes: Sequence[tuple[str, DefectProbeContract]] = (),
) -> CandidateDefectClosureReceipt:
    """Apply an exact safe candidate in a managed sandbox and rerun one probe.

    ``patch_safety`` is the already-computed production safety receipt.  Anything
    other than ``ok is True`` stops before sandbox creation.  No result from this
    function is read as execution authorization.

    ``preservation_probes`` are further immutable contracts DEFECT.PROBE.LIVE.3
    already built and already validated against the primary probe.  They run in
    the same sandbox, against the same applied bytes, immediately after the
    primary post-probe, so the two halves of a pair can never describe different
    candidates.  Their receipts are returned verbatim and never consulted here.
    """

    started = time.perf_counter()
    pre_payload = _receipt_payload(pre_probe_receipt)
    operations = [
        dict(op)
        for op in (candidate_plan or [])
        if isinstance(op, Mapping)
    ]
    candidate_fingerprint = patch_plan_fingerprint(operations)

    def early(status: str, reason: str) -> CandidateDefectClosureReceipt:
        return _receipt(
            contract=probe_contract,
            candidate_fingerprint=candidate_fingerprint,
            pre_payload=pre_payload,
            status=status,
            reason=reason,
            timings={"total_sec": round(time.perf_counter() - started, 6)},
        )

    if not operations:
        return early(CLOSURE_UNAVAILABLE, "no exact candidate was available to probe")
    if not isinstance(patch_safety, Mapping) or patch_safety.get("ok") is not True:
        return early(
            CLOSURE_UNAVAILABLE,
            "candidate was not materialized because existing patch safety did not pass",
        )
    if expected_candidate_fingerprint and (
        expected_candidate_fingerprint != candidate_fingerprint
    ):
        return early(
            CLOSURE_INVALID_COMPARISON,
            "candidate changed after its expected fingerprint was bound",
        )
    if str(pre_payload.get("probe_fingerprint") or "") != probe_contract.fingerprint:
        return early(
            CLOSURE_INVALID_COMPARISON,
            "pre-patch receipt does not describe the same immutable probe",
        )
    if pre_payload.get("execution_stage") != EXECUTION_STAGE_PRE_PATCH:
        return early(CLOSURE_INVALID_COMPARISON, "pre-patch receipt stage is invalid")
    if reproduced_probe_target(pre_payload) is None:
        return early(
            CLOSURE_INVALID_COMPARISON,
            "pre-patch receipt is not independently-grounded reproduced evidence",
        )
    if pre_payload.get("probe_result") != PROBE_REPRODUCED:
        return early(CLOSURE_INVALID_COMPARISON, "pre-patch probe did not reproduce")
    if pre_payload.get("probe_expected") != probe_contract.expected:
        return early(CLOSURE_INVALID_COMPARISON, "pre-patch expected result changed")
    if (
        pre_payload.get("expected_behavior_basis")
        != probe_contract.expected_behavior_basis
    ):
        return early(CLOSURE_INVALID_COMPARISON, "expectation provenance changed")
    oracle_error = _oracle_integrity_error(probe_contract, operations)
    if oracle_error:
        return early(CLOSURE_INVALID_COMPARISON, oracle_error)

    try:
        source_repo = Path(repo_path).resolve()
    except (OSError, TypeError, ValueError):
        return early(CLOSURE_UNAVAILABLE, "repository source is unavailable")
    if not source_repo.is_dir():
        return early(CLOSURE_UNAVAILABLE, "repository source is unavailable")
    if sandbox_parent is not None:
        try:
            sandbox_parent_path = Path(sandbox_parent).resolve()
            sandbox_parent_path.relative_to(source_repo)
        except ValueError:
            pass
        except (OSError, TypeError):
            return early(CLOSURE_INCONCLUSIVE, "sandbox parent is unavailable")
        else:
            return early(
                CLOSURE_INCONCLUSIVE,
                "sandbox parent must be outside the repository being copied",
            )

    timings: dict[str, float] = {}
    temp_root: Path | None = None
    sandbox_root: Path | None = None
    post_receipt: DefectProbeReceipt | None = None
    preservation_receipts: tuple[tuple[str, DefectProbeReceipt], ...] = ()
    apply_status = APPLY_NOT_ATTEMPTED
    apply_error = ""

    sandbox_started = time.perf_counter()
    try:
        temp_root = Path(
            tempfile.mkdtemp(
                prefix="cattus-defect-probe-candidate-",
                dir=str(sandbox_parent) if sandbox_parent else None,
            )
        )
        sandbox_dir = temp_root / "repo"
        info = create_managed_sandbox(source_repo, sandbox_dir)
        timings["sandbox_creation_sec"] = round(
            time.perf_counter() - sandbox_started, 6
        )
        if not info.get("ok"):
            apply_status = APPLY_UNAVAILABLE
            apply_error = str(info.get("error") or "managed sandbox unavailable")
        else:
            sandbox_root = Path(str(info["sandbox_path"]))
            from patching.patch_plan_executor import apply_patch_plan

            apply_started = time.perf_counter()
            apply_result = apply_patch_plan(
                str(sandbox_root),
                operations,
                validation_command=None,
            )
            timings["patch_apply_sec"] = round(
                time.perf_counter() - apply_started, 6
            )
            if not apply_result.get("success"):
                apply_status = APPLY_FAILED
                apply_error = str(apply_result.get("error") or "candidate apply failed")
            else:
                apply_status = APPLY_APPLIED
                probe_started = time.perf_counter()
                post_receipt = execute_defect_probe(
                    probe_contract,
                    repo_path=sandbox_root,
                    identity_repo_path=source_repo,
                    execution_stage=EXECUTION_STAGE_POST_PATCH,
                )
                timings["post_probe_execution_sec"] = round(
                    time.perf_counter() - probe_started, 6
                )
                if preservation_probes:
                    companion_started = time.perf_counter()
                    preservation_receipts = tuple(
                        (
                            str(case_id),
                            execute_defect_probe(
                                companion,
                                repo_path=sandbox_root,
                                identity_repo_path=source_repo,
                                execution_stage=EXECUTION_STAGE_POST_PATCH,
                            ),
                        )
                        for case_id, companion in preservation_probes
                    )
                    timings["preservation_probe_execution_sec"] = round(
                        time.perf_counter() - companion_started, 6
                    )
    except Exception as exc:
        apply_status = APPLY_UNAVAILABLE
        apply_error = f"candidate probe infrastructure unavailable: {type(exc).__name__}"

    cleanup_started = time.perf_counter()
    cleanup_ok = _cleanup(sandbox_root, temp_root)
    timings["cleanup_sec"] = round(time.perf_counter() - cleanup_started, 6)
    timings["total_sec"] = round(time.perf_counter() - started, 6)

    common = {
        "contract": probe_contract,
        "candidate_fingerprint": candidate_fingerprint,
        "pre_payload": pre_payload,
        "post_receipt": post_receipt,
        "apply_status": apply_status,
        "cleanup_ok": cleanup_ok,
        "timings": timings,
        "preservation_receipts": preservation_receipts,
    }
    if not cleanup_ok:
        return _receipt(
            status=CLOSURE_INCONCLUSIVE,
            reason="managed sandbox cleanup could not be confirmed",
            **common,
        )
    if apply_status == APPLY_UNAVAILABLE:
        return _receipt(
            status=CLOSURE_INCONCLUSIVE,
            reason=apply_error or "sandbox execution infrastructure was unavailable",
            **common,
        )
    if apply_status != APPLY_APPLIED or post_receipt is None:
        return _receipt(
            status=CLOSURE_UNAVAILABLE,
            reason=apply_error or "candidate could not be materialized for probing",
            **common,
        )
    if post_receipt.probe_fingerprint != probe_contract.fingerprint:
        return _receipt(
            status=CLOSURE_INVALID_COMPARISON,
            reason="post-patch receipt does not describe the immutable pre-patch probe",
            **common,
        )
    if post_receipt.probe_result == PROBE_NOT_REPRODUCED:
        return _receipt(
            status=CLOSURE_FIXED,
            reason="the same immutable probe observed the independently expected behavior",
            **common,
        )
    if post_receipt.probe_result == PROBE_REPRODUCED:
        if post_receipt.observed == _receipt_observed(pre_payload):
            return _receipt(
                status=CLOSURE_STILL_REPRODUCED,
                reason="the exact same wrong bounded behavior remains",
                **common,
            )
        return _receipt(
            status=CLOSURE_CHANGED_BUT_UNRESOLVED,
            reason="candidate changed the observation but did not reach the expected behavior",
            **common,
        )
    if post_receipt.probe_result in {
        PROBE_INCONCLUSIVE,
        PROBE_UNAVAILABLE,
        PROBE_INVALID,
    }:
        return _receipt(
            status=CLOSURE_INCONCLUSIVE,
            reason="post-patch probe did not produce a behavioral verdict",
            **common,
        )
    return _receipt(
        status=CLOSURE_INCONCLUSIVE,
        reason="post-patch probe result was unavailable",
        **common,
    )


def candidate_defect_probe_guardrails() -> dict[str, bool]:
    return {
        "same_probe_required": True,
        "same_expectation_provenance_required": True,
        "candidate_fingerprint_bound": True,
        "patch_safety_required_before_sandbox": True,
        "real_patch_plan_primitive_used": True,
        "managed_sandbox_only": True,
        "isolated_python_bytecode_required": True,
        "preservation_probes_share_the_primary_sandbox": True,
        "preservation_receipt_read_by_this_module": False,
        "full_validation_rewritten": False,
        "targeted_validation_rewritten": False,
        "patch_basis_created": False,
        "execution_authority_granted": False,
        "auto_apply_granted": False,
        "model_called": False,
        "network_called": False,
        "repository_traversal_added": False,
    }


__all__ = [
    "PHASE_ID",
    "RECEIPT_SCHEMA_VERSION",
    "CLOSURE_FIXED",
    "CLOSURE_FIXED_BUT_REGRESSIVE",
    "CLOSURE_STILL_REPRODUCED",
    "CLOSURE_CHANGED_BUT_UNRESOLVED",
    "CLOSURE_INCONCLUSIVE",
    "CLOSURE_INVALID_COMPARISON",
    "CLOSURE_UNAVAILABLE",
    "CLOSURE_STATUSES",
    "CandidateDefectClosureReceipt",
    "candidate_defect_closure_is_current",
    "evaluate_candidate_defect_closure",
    "candidate_defect_probe_guardrails",
]
