"""DEFECT.PROBE.LIVE.3 — paired defect-fix and behavior-preservation oracle.

DEFECT.PROBE.LIVE.2 asks one question of a candidate: does the bounded input
the user's claim was adapted from now produce the value the user asked for?  A
candidate that merely *moves* wrong behavior answers that question correctly.
The exact T6 branch-reorder candidate is the demonstration — swapping the
``4space``/``2space`` prefix branches makes the two-space fixture classify as
``2space`` and makes the four-space fixture classify as ``2space`` too, so the
single expected-value probe reports ``fixed`` for a candidate that destroys
behavior which was already correct.

The weakness is in the oracle, not in the probe.  So nothing about execution
changes here: the same immutable :class:`~core.defect_probe.DefectProbeContract`
runs through the same static worker in the same managed sandbox.  What this
module adds is a *second* bounded case, derived deterministically from the same
typed behavioral fact, whose expected value is the behavior the baseline
already had.

Direction is what makes the pair meaningful:

* the **primary case** asks whether the claimed defect closed — its expectation
  is ``expected_value``, what the user said the behavior should be;
* the **preservation case** asks whether previously-correct behavior survived —
  its expectation is the behavior the baseline was *already* observed to
  produce for the collision partner the same typed fact exposes.

A preservation case is therefore never a second user claim, and this module
never labels it as one.  It is system-derived evidence, and it is only an
oracle at all when the baseline itself satisfies it: a counter-case the
unpatched repository already fails proves nothing about the candidate, so it is
reported ``unavailable`` rather than counted as a regression.

Scope is deliberately narrow.  ``indentation_style`` is the only production
subject a typed behavioral expectation currently carries, so it is the only
subject with a preservation adapter.  Every other subject truthfully has no
preservation oracle, which leaves the existing single-case closure semantics
exactly as they were.

Nothing here authors a candidate, ranks a hypothesis, retrieves source, calls a
model, touches the network, walks the repository, or grants any authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
import time
from typing import Any, Mapping, Sequence

from core.behavioral_expectation import (
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
)
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
    CLOSURE_FIXED_BUT_REGRESSIVE,
    CLOSURE_INCONCLUSIVE,
    CLOSURE_INVALID_COMPARISON,
    CLOSURE_STILL_REPRODUCED,
    CLOSURE_UNAVAILABLE,
    CandidateDefectClosureReceipt,
    evaluate_candidate_defect_closure,
)
from core.defect_probe import (
    EXECUTION_STAGE_PRE_PATCH,
    EXPECTATION_BASIS_TASK_FACT_ADAPTER,
    INPUT_BASIS_TASK_FACT_ADAPTER,
    PROBE_BASIS_TASK_FACT_ADAPTER,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    DefectProbeContract,
    DefectProbeReceipt,
    ProbeTargetBinding,
    # §2: the deterministic fixture generator is reused exactly, never
    # re-implemented.  ``_INDENT_VALUE_RE`` comes with it so a preservation
    # case accepts precisely the values the primary adapter accepts; two
    # copies of that rule could drift into an oracle that silently covers a
    # different set of facts than the probe it is paired with.
    _INDENT_VALUE_RE,
    _nested_indentation_fixture,
    build_python_function_probe,
    execute_defect_probe,
)
# INDENT.RUNTIME.1 — the one language label this file's indentation-style
# fixtures declare; reused rather than a second "python" spelling.
from core.indentation_observation import LANGUAGE_PYTHON


PHASE_ID = "DEFECT.PROBE.LIVE.3"
RECEIPT_SCHEMA_VERSION = "paired_defect_probe_live_3_v1"

# ── Paired assessment vocabulary ──────────────────────────────────────────────
#: Primary fixed and every available preservation case held.
PAIRED_FIXED_AND_PRESERVED = "fixed_and_preserved"
#: Primary fixed, and a preservation case the baseline already satisfied broke.
#: Distinct from :data:`PAIRED_FIXED` on purpose: ``fixed`` may never be made
#: to mean this.
PAIRED_FIXED_BUT_REGRESSIVE = "fixed_but_regressive"
#: Primary fixed with no preservation oracle available — the pre-existing
#: single-case closure meaning, unchanged, for subjects with no adapter.
PAIRED_FIXED = CLOSURE_FIXED
PAIRED_STILL_REPRODUCED = CLOSURE_STILL_REPRODUCED
PAIRED_CHANGED_BUT_UNRESOLVED = CLOSURE_CHANGED_BUT_UNRESOLVED
PAIRED_INCONCLUSIVE = CLOSURE_INCONCLUSIVE
PAIRED_INVALID_COMPARISON = CLOSURE_INVALID_COMPARISON
PAIRED_UNAVAILABLE = CLOSURE_UNAVAILABLE
PAIRED_STATUSES: tuple[str, ...] = (
    PAIRED_FIXED_AND_PRESERVED,
    PAIRED_FIXED_BUT_REGRESSIVE,
    PAIRED_FIXED,
    PAIRED_STILL_REPRODUCED,
    PAIRED_CHANGED_BUT_UNRESOLVED,
    PAIRED_INCONCLUSIVE,
    PAIRED_INVALID_COMPARISON,
    PAIRED_UNAVAILABLE,
)

#: Statuses that mean the candidate did not close the defect cleanly.  Used by
#: readers that must not treat a regressive candidate as a closed one.
NON_CLOSING_PAIRED_STATUSES: frozenset[str] = frozenset(
    set(PAIRED_STATUSES) - {PAIRED_FIXED_AND_PRESERVED, PAIRED_FIXED}
)

# ── Per-case vocabulary ───────────────────────────────────────────────────────
PRESERVATION_PRESERVED = "preserved"
PRESERVATION_REGRESSED = "regressed"
PRESERVATION_INCONCLUSIVE = "inconclusive"
PRESERVATION_UNAVAILABLE = "unavailable"
PRESERVATION_CASE_STATUSES: tuple[str, ...] = (
    PRESERVATION_PRESERVED,
    PRESERVATION_REGRESSED,
    PRESERVATION_INCONCLUSIVE,
    PRESERVATION_UNAVAILABLE,
)

ORACLE_AVAILABLE = "available"
ORACLE_UNAVAILABLE = "unavailable"
ORACLE_INCONCLUSIVE = "inconclusive"
ORACLE_STATUSES: tuple[str, ...] = (
    ORACLE_AVAILABLE,
    ORACLE_UNAVAILABLE,
    ORACLE_INCONCLUSIVE,
)

REASON_SUBJECT_UNSUPPORTED = "subject_has_no_deterministic_preservation_case"
REASON_BASELINE_NOT_SATISFIED = "baseline_did_not_satisfy_the_counter_case"
REASON_BASELINE_NO_VERDICT = "baseline_counter_case_reached_no_verdict"
REASON_CANDIDATE_NOT_PROBED = "candidate_counter_case_was_not_probed"
REASON_ORACLE_INTEGRITY = "counter_case_is_not_bound_to_the_primary_probe"

#: §9.  A preservation expectation is derived by this phase from the collision
#: domain a typed fact already exposes.  It is *not* a user requirement and is
#: never reported as one; the primary expectation keeps its own explicit-user
#: provenance untouched.
PRESERVATION_PROVENANCE = "system_derived_behavior_preservation"


@dataclass(frozen=True, slots=True)
class PreservationCase:
    """One deterministic counter-case and the bounded contract that runs it."""

    case_id: str
    subject_kind: str
    expected: Any
    contract: DefectProbeContract
    derivation: str
    provenance: str = PRESERVATION_PROVENANCE

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "subject_kind": self.subject_kind,
            "expected": self.expected,
            "provenance": self.provenance,
            "derivation": self.derivation,
        }


@dataclass(frozen=True, slots=True)
class PreservationCaseResult:
    """Baseline and candidate observations for one counter-case."""

    case_id: str
    subject_kind: str
    expected: Any
    status: str
    baseline_result: str
    baseline_observed: Any = None
    candidate_result: str = ""
    candidate_observed: Any = None
    reason: str = ""
    provenance: str = PRESERVATION_PROVENANCE

    def __post_init__(self) -> None:
        if self.status not in PRESERVATION_CASE_STATUSES:
            raise ValueError(f"unsupported preservation status: {self.status!r}")
        if self.provenance != PRESERVATION_PROVENANCE:
            raise ValueError(
                "a preservation counter-case may only carry system-derived "
                f"provenance, not {self.provenance!r}"
            )

    @property
    def is_oracle(self) -> bool:
        """True only where the baseline established a usable counter-case."""

        return self.status in {PRESERVATION_PRESERVED, PRESERVATION_REGRESSED}

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "subject_kind": self.subject_kind,
            "expected": self.expected,
            "baseline_observed": self.baseline_observed,
            "baseline_result": self.baseline_result,
            "candidate_observed": self.candidate_observed,
            "candidate_result": self.candidate_result,
            "status": self.status,
            "provenance": self.provenance,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class PairedDefectProbeReceipt:
    """Two separately-represented cases and the closed assessment over them.

    The primary case keeps DEFECT.PROBE.LIVE.2's meaning exactly.  ``closure``
    is that phase's receipt, downgraded only when a preservation case the
    baseline already satisfied did not survive the candidate — never upgraded,
    and never rewritten when there is no preservation oracle at all.
    """

    closure: CandidateDefectClosureReceipt
    primary_status: str
    paired_status: str
    preservation_oracle_status: str
    primary_expected: Any = None
    preservation_cases: tuple[PreservationCaseResult, ...] = ()
    preservation_oracle_reason: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    schema_version: str = RECEIPT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.paired_status not in PAIRED_STATUSES:
            raise ValueError(f"unsupported paired status: {self.paired_status!r}")
        if self.preservation_oracle_status not in ORACLE_STATUSES:
            raise ValueError(
                f"unsupported preservation oracle status: "
                f"{self.preservation_oracle_status!r}"
            )

    @property
    def defect_closure_status(self) -> str:
        """The effective closure status a candidate-reading consumer sees."""

        return self.closure.defect_closure_status

    @property
    def closure_ready(self) -> bool:
        """Evidence-only: the pair closed.  Not eligibility and not authority."""

        return self.paired_status in {PAIRED_FIXED_AND_PRESERVED, PAIRED_FIXED}

    def primary_case(self) -> dict[str, Any]:
        return {
            "expected": self.primary_expected,
            "baseline_observed": self.closure.pre_probe_observed,
            "candidate_observed": self.closure.post_probe_observed,
            "baseline_result": self.closure.pre_probe_result,
            "candidate_result": self.closure.post_probe_result,
            "status": self.primary_status,
            "provenance": self.closure.expected_behavior_basis,
        }

    def as_telemetry(self) -> dict[str, Any]:
        payload = self.closure.as_telemetry()
        payload.update(
            {
                "paired_probe_phase_id": PHASE_ID,
                "paired_probe_schema_version": self.schema_version,
                "paired_status": self.paired_status,
                "primary_case": self.primary_case(),
                "preservation_oracle_status": self.preservation_oracle_status,
                "preservation_oracle_reason": self.preservation_oracle_reason,
                "preservation_cases": [
                    item.as_dict() for item in self.preservation_cases
                ],
                "paired_probe_timings": dict(self.timings),
                "paired_probe_authority_effect": "none",
            }
        )
        return payload


# ── The subject adapter ───────────────────────────────────────────────────────

def _indentation_preservation_cases(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation,
) -> tuple[PreservationCase, ...]:
    """The one production subject: an indentation width the baseline handles.

    The typed fact names two widths.  The user's ``expected_value`` is already
    the primary probe's oracle, so the remaining width — the one the user says
    the code produces *instead* — is exactly the bounded partner in the same
    collision domain, and the behavior at that width is what a fix must not
    trade away.
    """

    expected = _INDENT_VALUE_RE.fullmatch(behavior_fact.expected_value)
    observed = _INDENT_VALUE_RE.fullmatch(behavior_fact.observed_value)
    if expected is None or observed is None:
        return ()
    observed_width = int(observed.group("width"))
    if observed_width == int(expected.group("width")):
        return ()
    contract = build_python_function_probe(
        target=target,
        args=(_nested_indentation_fixture(observed_width),),
        expected=behavior_fact.observed_value,
        probe_basis=PROBE_BASIS_TASK_FACT_ADAPTER,
        input_basis=INPUT_BASIS_TASK_FACT_ADAPTER,
        expected_behavior_basis=EXPECTATION_BASIS_TASK_FACT_ADAPTER,
        provenance_reference=(
            "system-derived behavior-preservation counter-case for the "
            f"{behavior_fact.subject_kind} subject; the deterministic nested "
            f"fixture uses {observed_width} spaces per depth and its expected "
            f"result {behavior_fact.observed_value} is the behavior the "
            "unpatched code already produces, not a user requirement — the "
            f"user's requirement is {behavior_fact.expected_value} and it "
            "belongs to the primary case"
        ),
        # INDENT.RUNTIME.1 §17 — _nested_indentation_fixture is always a
        # Python-shaped sample; this adapter is only ever reached for
        # SUBJECT_INDENTATION_STYLE (guarded above).
        kwargs={"language": LANGUAGE_PYTHON},
    )
    return (
        PreservationCase(
            case_id=(
                f"{behavior_fact.subject_kind}.preserve."
                f"{behavior_fact.observed_value}"
            ),
            subject_kind=behavior_fact.subject_kind,
            expected=behavior_fact.observed_value,
            contract=contract,
            derivation=(
                "collision partner of the typed behavioral expectation: the "
                "claimed observed value probed at its own width"
            ),
        ),
    )


#: §8.  Subject → optional deterministic preservation cases.  A subject that is
#: absent here has no preservation oracle, which is a fact about this phase's
#: coverage and never a licence to invent a counter-case for it.
_PRESERVATION_ADAPTERS = {
    SUBJECT_INDENTATION_STYLE: _indentation_preservation_cases,
}


def preservation_subject_supported(subject_kind: Any) -> bool:
    return str(subject_kind or "") in _PRESERVATION_ADAPTERS


def build_preservation_cases(
    *,
    target: ProbeTargetBinding,
    behavior_fact: BehavioralExpectation | None,
) -> tuple[PreservationCase, ...]:
    """Deterministic counter-cases for one typed fact, or nothing at all.

    An empty result is the truthful answer for every subject without an
    adapter, for a fact whose values this phase cannot read, and for transport
    that carries no typed fact.  It is never an approximation.
    """

    if behavior_fact is None or target is None:
        return ()
    adapter = _PRESERVATION_ADAPTERS.get(behavior_fact.subject_kind)
    if adapter is None:
        return ()
    return adapter(target=target, behavior_fact=behavior_fact)


# ── Case and pair derivation ──────────────────────────────────────────────────

def _bound_to_primary(case: PreservationCase, primary: DefectProbeContract) -> bool:
    """A counter-case only counts when it probes the same localized target.

    Same file, same symbol, same repository, same localized bytes, the same
    read-only invocation kind, and the same expectation provenance and source
    binding — so DEFECT.PROBE.LIVE.2's existing oracle-integrity rule, which
    refuses a candidate that edits the artifact an expectation came from, covers
    both halves of the pair identically.  A different fingerprint is required
    too: a counter-case identical to the primary proves the same thing twice.
    """

    contract = case.contract
    return (
        contract.target == primary.target
        and contract.invocation_kind == primary.invocation_kind
        and contract.expected_relation == primary.expected_relation
        and contract.side_effect_policy == primary.side_effect_policy
        and contract.probe_basis == primary.probe_basis
        and contract.input_basis == primary.input_basis
        and contract.expected_behavior_basis == primary.expected_behavior_basis
        and contract.expectation_source_paths == primary.expectation_source_paths
        and contract.fingerprint != primary.fingerprint
    )


def _baseline_case_state(receipt: DefectProbeReceipt) -> tuple[bool, str, str]:
    """``(usable, status, reason)`` for one baseline counter-case run."""

    if receipt.probe_result == PROBE_NOT_REPRODUCED:
        return True, "", ""
    if receipt.probe_result == PROBE_REPRODUCED:
        # §4: the baseline is already wrong here, so a candidate that is also
        # wrong here has regressed nothing.  Refusing the oracle is the only
        # truthful move; counting it would manufacture a regression.
        return False, PRESERVATION_UNAVAILABLE, REASON_BASELINE_NOT_SATISFIED
    return False, PRESERVATION_UNAVAILABLE, REASON_BASELINE_NO_VERDICT


def _candidate_case_status(
    receipt: DefectProbeReceipt | None,
) -> tuple[str, str]:
    if receipt is None:
        return PRESERVATION_INCONCLUSIVE, REASON_CANDIDATE_NOT_PROBED
    if receipt.probe_result == PROBE_NOT_REPRODUCED:
        return PRESERVATION_PRESERVED, ""
    if receipt.probe_result == PROBE_REPRODUCED:
        return (
            PRESERVATION_REGRESSED,
            "the candidate lost behavior the baseline already produced",
        )
    return PRESERVATION_INCONCLUSIVE, receipt.reason or REASON_CANDIDATE_NOT_PROBED


def _resolved_case(
    case: PreservationCase,
    baseline: DefectProbeReceipt,
    candidate: DefectProbeReceipt | None,
) -> PreservationCaseResult:
    """Close one counter-case over its baseline and its candidate observation.

    The baseline decides whether there is an oracle here at all; only then does
    the candidate's observation get to mean anything.
    """

    usable, status, reason = _baseline_case_state(baseline)
    if usable:
        status, reason = _candidate_case_status(candidate)
    else:
        candidate = None
    return PreservationCaseResult(
        case_id=case.case_id,
        subject_kind=case.subject_kind,
        expected=case.expected,
        status=status,
        baseline_result=baseline.probe_result,
        baseline_observed=baseline.observed,
        candidate_result=candidate.probe_result if candidate else "",
        candidate_observed=candidate.observed if candidate else None,
        reason=reason,
    )


def derive_paired_status(
    primary_status: str,
    cases: Sequence[PreservationCaseResult],
) -> str:
    """Close the pair.  Only a fixed primary can be qualified by preservation.

    A primary that did not close is already answered by DEFECT.PROBE.LIVE.2's
    own vocabulary, and a preservation observation cannot make it better or
    worse than it is.
    """

    if primary_status != CLOSURE_FIXED:
        return (
            primary_status
            if primary_status in PAIRED_STATUSES
            else PAIRED_INCONCLUSIVE
        )
    statuses = {item.status for item in cases}
    if PRESERVATION_REGRESSED in statuses:
        return PAIRED_FIXED_BUT_REGRESSIVE
    if PRESERVATION_INCONCLUSIVE in statuses:
        return PAIRED_INCONCLUSIVE
    if PRESERVATION_PRESERVED in statuses:
        return PAIRED_FIXED_AND_PRESERVED
    # No case reached an oracle; the single-case meaning is unchanged.
    return PAIRED_FIXED


def _effective_closure_status(
    paired_status: str, primary_status: str
) -> tuple[str, str]:
    """What a candidate-reading consumer must see for ``defect_closure_status``.

    §11.  Existing readers compare this field against ``"fixed"``.  A regressive
    or unverified candidate must therefore never arrive carrying that value, and
    a candidate with no preservation oracle must arrive carrying exactly what it
    carried before this phase existed.

    Returns ``(status, reason)``; the reason is empty whenever the status the
    primary case produced still stands, so DEFECT.PROBE.LIVE.2's own wording is
    never overwritten by this phase.
    """

    if paired_status == PAIRED_FIXED_AND_PRESERVED:
        return CLOSURE_FIXED, ""
    if paired_status == PAIRED_FIXED_BUT_REGRESSIVE:
        return CLOSURE_FIXED_BUT_REGRESSIVE, (
            "the claimed defect closed and a preservation counter-case the "
            "baseline already satisfied did not survive the candidate"
        )
    if paired_status == PAIRED_INCONCLUSIVE and primary_status == CLOSURE_FIXED:
        return CLOSURE_INCONCLUSIVE, (
            "the claimed defect closed and a preservation counter-case reached "
            "no behavioral verdict"
        )
    return primary_status, ""


def _oracle_status(cases: Sequence[PreservationCaseResult]) -> tuple[str, str]:
    if not cases:
        return ORACLE_UNAVAILABLE, REASON_SUBJECT_UNSUPPORTED
    if any(item.is_oracle for item in cases):
        return ORACLE_AVAILABLE, ""
    if any(item.status == PRESERVATION_INCONCLUSIVE for item in cases):
        return ORACLE_INCONCLUSIVE, next(
            item.reason for item in cases
            if item.status == PRESERVATION_INCONCLUSIVE
        )
    return ORACLE_UNAVAILABLE, next(
        (item.reason for item in cases if item.reason), REASON_BASELINE_NOT_SATISFIED
    )


def evaluate_paired_defect_closure(
    *,
    repo_path: str | Path,
    candidate_plan: Any,
    probe_contract: DefectProbeContract,
    pre_probe_receipt: DefectProbeReceipt | Mapping[str, Any],
    patch_safety: Mapping[str, Any],
    behavior_fact: BehavioralExpectation | None = None,
    preservation_cases: Sequence[PreservationCase] | None = None,
    expected_candidate_fingerprint: str = "",
    sandbox_parent: str | Path | None = None,
) -> PairedDefectProbeReceipt:
    """Run the defect case and its preservation counter-cases as one pair.

    The baseline counter-cases run read-only against the real repository, the
    same way the pre-patch defect probe already did.  The candidate's
    counter-cases run inside the one managed sandbox DEFECT.PROBE.LIVE.2
    already creates, against the exact bytes its primary post-probe saw, so the
    two halves of the pair can never describe different candidates.
    """

    started = time.perf_counter()
    timings: dict[str, float] = {}
    cases = (
        tuple(preservation_cases)
        if preservation_cases is not None
        else build_preservation_cases(
            target=probe_contract.target, behavior_fact=behavior_fact
        )
    )
    integrity_failed = tuple(
        case for case in cases if not _bound_to_primary(case, probe_contract)
    )
    cases = tuple(case for case in cases if case not in integrity_failed)

    safety_ok = isinstance(patch_safety, Mapping) and patch_safety.get("ok") is True
    baselines: list[tuple[PreservationCase, DefectProbeReceipt]] = []
    if safety_ok and cases:
        baseline_started = time.perf_counter()
        baselines = [
            (
                case,
                execute_defect_probe(
                    case.contract,
                    repo_path=repo_path,
                    execution_stage=EXECUTION_STAGE_PRE_PATCH,
                ),
            )
            for case in cases
        ]
        timings["preservation_baseline_sec"] = round(
            time.perf_counter() - baseline_started, 6
        )

    closure = evaluate_candidate_defect_closure(
        repo_path=repo_path,
        candidate_plan=candidate_plan,
        probe_contract=probe_contract,
        pre_probe_receipt=pre_probe_receipt,
        patch_safety=patch_safety,
        expected_candidate_fingerprint=expected_candidate_fingerprint,
        sandbox_parent=sandbox_parent,
        preservation_probes=tuple(
            (case.case_id, case.contract)
            for case, baseline in baselines
            if _baseline_case_state(baseline)[0]
        ),
    )
    candidate_receipts = dict(closure.preservation_probe_receipts)

    resolved = [
        _resolved_case(case, baseline, candidate_receipts.get(case.case_id))
        for case, baseline in baselines
    ]
    resolved.extend(
        PreservationCaseResult(
            case_id=case.case_id,
            subject_kind=case.subject_kind,
            expected=case.expected,
            status=PRESERVATION_UNAVAILABLE,
            baseline_result="",
            reason=REASON_ORACLE_INTEGRITY,
        )
        for case in integrity_failed
    )

    oracle_status, oracle_reason = _oracle_status(resolved)
    if not safety_ok and cases:
        oracle_status, oracle_reason = ORACLE_UNAVAILABLE, REASON_CANDIDATE_NOT_PROBED
    primary_status = closure.defect_closure_status
    paired_status = derive_paired_status(primary_status, resolved)
    effective, effective_reason = _effective_closure_status(
        paired_status, primary_status
    )
    timings["paired_total_sec"] = round(time.perf_counter() - started, 6)
    return PairedDefectProbeReceipt(
        closure=(
            closure
            if effective == primary_status
            else replace(
                closure,
                defect_closure_status=effective,
                reason=effective_reason or closure.reason,
            )
        ),
        primary_status=primary_status,
        paired_status=paired_status,
        primary_expected=probe_contract.expected,
        preservation_oracle_status=oracle_status,
        preservation_oracle_reason=oracle_reason,
        preservation_cases=tuple(resolved),
        timings=timings,
    )


def paired_defect_probe_guardrails() -> dict[str, bool]:
    return {
        "same_primary_probe_required": True,
        "preservation_case_bound_to_primary_target": True,
        "preservation_baseline_precondition_required": True,
        "preservation_expectation_labeled_user_supplied": False,
        "single_case_fixed_can_close_a_regressive_candidate": False,
        "existing_fixture_generator_reused": True,
        "probe_execution_primitive_changed": False,
        "candidate_authoring_changed": False,
        "safe_minimal_changed": False,
        "control_ranking_changed": False,
        "retrieval_changed": False,
        "behavioral_expectation_extraction_changed": False,
        "patch_basis_created": False,
        "grounded_defect_basis_erased": False,
        "human_review_eligibility_granted": False,
        "write_authority_granted": False,
        "execution_authorized": False,
        "auto_apply_granted": False,
        "model_called": False,
        "network_called": False,
        "repository_traversal_added": False,
        "production_classifier_fixed": False,
    }


__all__ = [
    "PHASE_ID",
    "RECEIPT_SCHEMA_VERSION",
    "PAIRED_FIXED_AND_PRESERVED",
    "PAIRED_FIXED_BUT_REGRESSIVE",
    "PAIRED_FIXED",
    "PAIRED_STILL_REPRODUCED",
    "PAIRED_CHANGED_BUT_UNRESOLVED",
    "PAIRED_INCONCLUSIVE",
    "PAIRED_INVALID_COMPARISON",
    "PAIRED_UNAVAILABLE",
    "PAIRED_STATUSES",
    "NON_CLOSING_PAIRED_STATUSES",
    "PRESERVATION_PRESERVED",
    "PRESERVATION_REGRESSED",
    "PRESERVATION_INCONCLUSIVE",
    "PRESERVATION_UNAVAILABLE",
    "PRESERVATION_CASE_STATUSES",
    "PRESERVATION_PROVENANCE",
    "ORACLE_AVAILABLE",
    "ORACLE_UNAVAILABLE",
    "ORACLE_INCONCLUSIVE",
    "ORACLE_STATUSES",
    "REASON_SUBJECT_UNSUPPORTED",
    "REASON_BASELINE_NOT_SATISFIED",
    "REASON_BASELINE_NO_VERDICT",
    "REASON_CANDIDATE_NOT_PROBED",
    "REASON_ORACLE_INTEGRITY",
    "PreservationCase",
    "PreservationCaseResult",
    "PairedDefectProbeReceipt",
    "preservation_subject_supported",
    "build_preservation_cases",
    "derive_paired_status",
    "evaluate_paired_defect_closure",
    "paired_defect_probe_guardrails",
]
