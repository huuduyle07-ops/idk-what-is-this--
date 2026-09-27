"""EXEC.POLICY.LIVE.1 — evidence-bounded execution eligibility.

This module reduces facts produced by earlier live phases into named policy
assessments.  It deliberately does not produce evidence, execute a check,
authorize a write, or reinterpret an evidence outcome.  In particular:

``eligible`` is a policy fact, not execution authorization; and a failed
targeted validation remains failed even when every failed check is accepted as
a fresh ``defect_preservation_oracle`` conflict by the bounded human-review
profile.

The evaluator is pure.  Its only input is a mapping of already-structured
receipts, and its result depends only on that mapping.  It performs no file or
graph reads, model/network calls, subprocess work, retrieval, probing, or
validation.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


PHASE_ID = "EXEC.POLICY.LIVE.1"
SCHEMA_VERSION = "execution_eligibility_live_1_v1"

PROFILE_FULL_VALIDATION_REQUIRED = "full_validation_required"
PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW = "bounded_evidence_human_review"
POLICY_PROFILES: tuple[str, ...] = (
    PROFILE_FULL_VALIDATION_REQUIRED,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
)

ELIGIBLE = "eligible"
INELIGIBLE = "ineligible"
INSUFFICIENT_EVIDENCE = "insufficient_evidence"
INCONSISTENT_INPUT = "inconsistent_input"
ELIGIBILITY_STATUSES: tuple[str, ...] = (
    ELIGIBLE,
    INELIGIBLE,
    INSUFFICIENT_EVIDENCE,
    INCONSISTENT_INPUT,
)
LEGACY_UNASSESSED = "legacy_unassessed"

FRESHNESS_CURRENT = "current"
FRESHNESS_STALE = "stale"
FRESHNESS_INCOMPLETE = "incomplete"
FRESHNESS_INVALID = "invalid"
EVIDENCE_FRESHNESS_STATUSES: tuple[str, ...] = (
    FRESHNESS_CURRENT,
    FRESHNESS_STALE,
    FRESHNESS_INCOMPLETE,
    FRESHNESS_INVALID,
)

# Closed requirement vocabulary.  These are machine-facing policy predicates,
# not prose explanations and not new evidence outcomes.
REQ_TASK_ROUTE_DEFECT_REPAIR = "task_route_defect_repair"
REQ_GROUNDED_DEFECT_BASIS = "grounded_defect_basis"
REQ_SOURCE_TARGET_GROUNDED = "source_target_grounded"
REQ_CANDIDATE_PRESENT = "candidate_present"
REQ_PATCH_SAFETY_PASSED = "patch_safety_passed"
REQ_PRE_PROBE_REPRODUCED = "pre_probe_reproduced"
REQ_INDEPENDENT_PROBE_ORACLE = "independent_probe_oracle"
REQ_POST_PROBE_FIXED = "post_probe_fixed"
REQ_CANDIDATE_SANDBOX_APPLIED = "candidate_sandbox_applied"
REQ_CANDIDATE_IDENTITY_FRESH = "candidate_identity_fresh"
REQ_PROBE_IDENTITY_FRESH = "probe_identity_fresh"
REQ_TARGETED_EVIDENCE_VALID = "targeted_evidence_valid"
REQ_NO_REGRESSION_ORACLE_FAILURE = "no_regression_oracle_failure"
REQ_NO_UNRESOLVED_ORACLE_CONFLICT = "no_unresolved_oracle_conflict"
REQ_REPOSITORY_IDENTITY_FRESH = "repository_identity_fresh"
REQ_FULL_VALIDATION_PASSED = "full_validation_passed"
REQ_FULL_VALIDATION_BUDGET_EXHAUSTED = "full_validation_budget_exhausted"
REQ_HUMAN_APPROVAL_REQUIRED = "human_approval_required"
REQUIREMENT_IDS: tuple[str, ...] = (
    REQ_TASK_ROUTE_DEFECT_REPAIR,
    REQ_GROUNDED_DEFECT_BASIS,
    REQ_SOURCE_TARGET_GROUNDED,
    REQ_CANDIDATE_PRESENT,
    REQ_PATCH_SAFETY_PASSED,
    REQ_PRE_PROBE_REPRODUCED,
    REQ_INDEPENDENT_PROBE_ORACLE,
    REQ_POST_PROBE_FIXED,
    REQ_CANDIDATE_SANDBOX_APPLIED,
    REQ_CANDIDATE_IDENTITY_FRESH,
    REQ_PROBE_IDENTITY_FRESH,
    REQ_TARGETED_EVIDENCE_VALID,
    REQ_NO_REGRESSION_ORACLE_FAILURE,
    REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
    REQ_REPOSITORY_IDENTITY_FRESH,
    REQ_FULL_VALIDATION_PASSED,
    REQ_FULL_VALIDATION_BUDGET_EXHAUSTED,
    REQ_HUMAN_APPROVAL_REQUIRED,
)

# Closed blocking-reason vocabulary.  Evidence diagnostics remain in their
# producer receipts; this layer records only the policy consequence.
BLOCK_TASK_ROUTE_NOT_DEFECT_REPAIR = "task_route_not_defect_repair"
BLOCK_PATCH_BASIS_NOT_GROUNDED_DEFECT = "patch_basis_not_grounded_defect"
BLOCK_SOURCE_TARGET_NOT_GROUNDED = "source_target_not_grounded"
BLOCK_CANDIDATE_MISSING = "candidate_missing"
BLOCK_PATCH_SAFETY_NOT_PASSED = "patch_safety_not_passed"
BLOCK_FULL_VALIDATION_NOT_PASSED = "full_validation_not_passed"
BLOCK_FULL_VALIDATION_GENUINE_FAILURE = "full_validation_genuine_failure"
BLOCK_FULL_VALIDATION_CAUSE_NOT_ACCEPTED = (
    "full_validation_inconclusive_cause_not_accepted"
)
BLOCK_PRE_PROBE_NOT_REPRODUCED = "pre_probe_not_reproduced"
BLOCK_PROBE_PROVENANCE_NOT_INDEPENDENT = "probe_provenance_not_independent"
BLOCK_POST_PROBE_NOT_FIXED = "post_probe_not_fixed"
BLOCK_CANDIDATE_SANDBOX_NOT_APPLIED = "candidate_sandbox_not_applied"
BLOCK_TARGETED_EVIDENCE_INVALID = "targeted_evidence_invalid_or_tampered"
BLOCK_TARGETED_EVIDENCE_INCONCLUSIVE = "targeted_evidence_inconclusive"
BLOCK_TARGETED_BASELINE_NOT_PASSED = "targeted_baseline_not_passed"
BLOCK_CANDIDATE_REGRESSION_ORACLE = "candidate_regression_oracle_failure"
BLOCK_UNRESOLVED_ORACLE_CONFLICT = "unresolved_oracle_conflict"
BLOCK_FAILED_CHECK_NOT_ACCEPTED = "failed_check_not_defect_preservation_oracle"
BLOCK_CANDIDATE_FINGERPRINT_STALE = "candidate_fingerprint_mismatch"
BLOCK_PROBE_FINGERPRINT_STALE = "probe_fingerprint_mismatch"
BLOCK_CHECK_SET_FINGERPRINT_STALE = "targeted_check_set_fingerprint_mismatch"
BLOCK_REPOSITORY_IDENTITY_STALE = "repository_identity_stale"
BLOCK_EVIDENCE_MISSING = "required_evidence_missing"
BLOCK_EXECUTION_SAFETY_DENIAL = "independent_execution_safety_denial"
BLOCK_HUMAN_APPROVAL_NOT_REQUIRED = "human_approval_not_required"
BLOCK_INCONSISTENT_EVIDENCE = "inconsistent_evidence_facts"
BLOCKING_REASONS: tuple[str, ...] = (
    BLOCK_TASK_ROUTE_NOT_DEFECT_REPAIR,
    BLOCK_PATCH_BASIS_NOT_GROUNDED_DEFECT,
    BLOCK_SOURCE_TARGET_NOT_GROUNDED,
    BLOCK_CANDIDATE_MISSING,
    BLOCK_PATCH_SAFETY_NOT_PASSED,
    BLOCK_FULL_VALIDATION_NOT_PASSED,
    BLOCK_FULL_VALIDATION_GENUINE_FAILURE,
    BLOCK_FULL_VALIDATION_CAUSE_NOT_ACCEPTED,
    BLOCK_PRE_PROBE_NOT_REPRODUCED,
    BLOCK_PROBE_PROVENANCE_NOT_INDEPENDENT,
    BLOCK_POST_PROBE_NOT_FIXED,
    BLOCK_CANDIDATE_SANDBOX_NOT_APPLIED,
    BLOCK_TARGETED_EVIDENCE_INVALID,
    BLOCK_TARGETED_EVIDENCE_INCONCLUSIVE,
    BLOCK_TARGETED_BASELINE_NOT_PASSED,
    BLOCK_CANDIDATE_REGRESSION_ORACLE,
    BLOCK_UNRESOLVED_ORACLE_CONFLICT,
    BLOCK_FAILED_CHECK_NOT_ACCEPTED,
    BLOCK_CANDIDATE_FINGERPRINT_STALE,
    BLOCK_PROBE_FINGERPRINT_STALE,
    BLOCK_CHECK_SET_FINGERPRINT_STALE,
    BLOCK_REPOSITORY_IDENTITY_STALE,
    BLOCK_EVIDENCE_MISSING,
    BLOCK_EXECUTION_SAFETY_DENIAL,
    BLOCK_HUMAN_APPROVAL_NOT_REQUIRED,
    BLOCK_INCONSISTENT_EVIDENCE,
)

ACCEPTED_CONFLICT_DEFECT_PRESERVATION = "defect_preservation_oracle"
ACCEPTED_CONFLICTS: tuple[str, ...] = (
    ACCEPTED_CONFLICT_DEFECT_PRESERVATION,
)
ACCEPTED_LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED = (
    "full_validation_budget_exhausted"
)
ACCEPTED_LIMITATIONS: tuple[str, ...] = (
    ACCEPTED_LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INDEPENDENT_PROBE_BASES = frozenset(
    {
        "explicit_user_reproducer",
        "existing_repository_test",
        "repository_contract",
        "deterministic_task_fact_adapter",
    }
)
_INDEPENDENT_INPUT_BASES = frozenset(
    {
        "preserved_explicit_user_input",
        "existing_repository_test_input",
        "repository_contract_input",
        "deterministic_fixture_from_preserved_task_fact",
    }
)
_INDEPENDENT_EXPECTATION_BASES = frozenset(
    {
        "preserved_explicit_user_requirement",
        "existing_repository_test_assertion",
        "repository_contract_specification",
        "preserved_task_fact_expected_behavior",
    }
)
_TAMPERED_TARGETED_CATEGORIES = frozenset(
    {
        "selected_validation_check_modified",
        "candidate_modified_check",
    }
)
_STALE_CANDIDATE_CATEGORIES = frozenset({"candidate_fingerprint_stale"})
_STALE_REPOSITORY_CATEGORIES = frozenset({"repository_identity_mismatch"})
_HARD_EXECUTION_SAFETY_DENIALS = frozenset(
    {
        "harness_mode_blocked",
        "patch_safety_blocked",
        "unsafe_validation_command",
        "executor_risk_blocked",
        "candidate_rejected",
    }
)


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _sha256(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if _SHA256_RE.fullmatch(text) else ""


def _nonnegative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True, slots=True)
class ExecutionEligibilityAssessment:
    """Deterministic result for one named profile.

    The type contains no confidence and no authorization boolean.  The explicit
    ``authority_effect=none`` field prevents consumers from treating omission
    as an invitation to infer authority.
    """

    policy_profile: str
    eligibility_status: str
    satisfied_requirements: tuple[str, ...]
    unsatisfied_requirements: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    accepted_conflicts: tuple[str, ...]
    accepted_limitations: tuple[str, ...]
    candidate_fingerprint: str
    probe_fingerprint: str
    targeted_validation_fingerprint: str
    patch_safety_binding: str
    evidence_freshness: str
    authority_effect: str = "none"

    def __post_init__(self) -> None:
        if self.policy_profile not in POLICY_PROFILES:
            raise ValueError(f"unsupported policy profile: {self.policy_profile!r}")
        if self.eligibility_status not in ELIGIBILITY_STATUSES:
            raise ValueError(
                f"unsupported eligibility status: {self.eligibility_status!r}"
            )
        if self.evidence_freshness not in EVIDENCE_FRESHNESS_STATUSES:
            raise ValueError(
                f"unsupported evidence freshness: {self.evidence_freshness!r}"
            )
        if self.authority_effect != "none":
            raise ValueError("execution eligibility may not grant authority")
        unknown_requirements = (
            set(self.satisfied_requirements)
            | set(self.unsatisfied_requirements)
        ) - set(REQUIREMENT_IDS)
        if unknown_requirements:
            raise ValueError(
                f"unknown eligibility requirements: {sorted(unknown_requirements)!r}"
            )
        unknown_reasons = set(self.blocking_reasons) - set(BLOCKING_REASONS)
        if unknown_reasons:
            raise ValueError(
                f"unknown eligibility blocking reasons: {sorted(unknown_reasons)!r}"
            )
        if set(self.accepted_conflicts) - set(ACCEPTED_CONFLICTS):
            raise ValueError("unknown accepted evidence conflict")
        if set(self.accepted_limitations) - set(ACCEPTED_LIMITATIONS):
            raise ValueError("unknown accepted evidence limitation")

    @property
    def eligible(self) -> bool:
        return self.eligibility_status == ELIGIBLE

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "policy_profile": self.policy_profile,
            "eligibility_status": self.eligibility_status,
            "satisfied_requirements": list(self.satisfied_requirements),
            "unsatisfied_requirements": list(self.unsatisfied_requirements),
            "blocking_reasons": list(self.blocking_reasons),
            "accepted_conflicts": list(self.accepted_conflicts),
            "accepted_limitations": list(self.accepted_limitations),
            "candidate_fingerprint": self.candidate_fingerprint,
            "probe_fingerprint": self.probe_fingerprint,
            "targeted_validation_fingerprint": (
                self.targeted_validation_fingerprint
            ),
            "patch_safety_binding": self.patch_safety_binding,
            "evidence_freshness": self.evidence_freshness,
            "authority_effect": self.authority_effect,
        }
        payload["assessment_fingerprint"] = _fingerprint(payload)
        return payload


@dataclass(frozen=True, slots=True)
class ExecutionEligibilityReport:
    """Both closed policy profiles over one immutable evidence matrix."""

    assessments: tuple[ExecutionEligibilityAssessment, ...]

    def __post_init__(self) -> None:
        profiles = tuple(item.policy_profile for item in self.assessments)
        if profiles != POLICY_PROFILES:
            raise ValueError("eligibility report must contain both profiles in order")

    def assessment_for(self, profile: str) -> ExecutionEligibilityAssessment:
        for assessment in self.assessments:
            if assessment.policy_profile == profile:
                return assessment
        raise ValueError(f"unsupported policy profile: {profile!r}")

    @property
    def human_review_eligible(self) -> bool:
        return self.assessment_for(
            PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW
        ).eligible

    def as_telemetry(self) -> dict[str, Any]:
        bounded = self.assessment_for(PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW)
        profiles = {
            assessment.policy_profile: assessment.as_dict()
            for assessment in self.assessments
        }
        return {
            "execution_eligibility_phase_id": PHASE_ID,
            "execution_eligibility_schema_version": SCHEMA_VERSION,
            "execution_eligibility_profile": bounded.policy_profile,
            "execution_eligibility_status": bounded.eligibility_status,
            "execution_eligibility_profiles": profiles,
            "human_review_eligible": self.human_review_eligible,
            "eligibility_requirements_satisfied": list(
                bounded.satisfied_requirements
            ),
            "eligibility_unsatisfied_requirements": list(
                bounded.unsatisfied_requirements
            ),
            "eligibility_blocking_reasons": list(bounded.blocking_reasons),
            "accepted_evidence_conflicts": list(bounded.accepted_conflicts),
            "accepted_limitations": list(bounded.accepted_limitations),
            "execution_eligibility_candidate_fingerprint": (
                bounded.candidate_fingerprint
            ),
            "execution_eligibility_probe_fingerprint": bounded.probe_fingerprint,
            "execution_eligibility_targeted_validation_fingerprint": (
                bounded.targeted_validation_fingerprint
            ),
            "execution_eligibility_patch_safety_binding": (
                bounded.patch_safety_binding
            ),
            "evidence_freshness": bounded.evidence_freshness,
            "execution_eligibility_authority_effect": "none",
            "execution_eligibility_auto_apply_effect": "none",
            "execution_eligibility_model_calls": 0,
            "execution_eligibility_network_calls": 0,
            "execution_eligibility_repository_traversals": 0,
            "execution_eligibility_validation_calls": 0,
            "execution_eligibility_retrieval_calls": 0,
        }


class _AssessmentBuilder:
    def __init__(self, profile: str, evidence: Mapping[str, Any]) -> None:
        self.profile = profile
        self.evidence = evidence
        self.satisfied: list[str] = []
        self.unsatisfied: list[str] = []
        self.reasons: list[str] = []
        self.conflicts: list[str] = []
        self.limitations: list[str] = []
        self.has_ineligible = False
        self.has_missing = False
        self.has_inconsistent = False
        self.has_invalid = False

    def pass_requirement(self, requirement: str) -> None:
        self.satisfied.append(requirement)

    def fail_requirement(
        self,
        requirement: str,
        reason: str,
        *,
        kind: str,
    ) -> None:
        self.unsatisfied.append(requirement)
        self.reasons.append(reason)
        if kind == INELIGIBLE:
            self.has_ineligible = True
        elif kind == INSUFFICIENT_EVIDENCE:
            self.has_missing = True
        elif kind == INCONSISTENT_INPUT:
            self.has_inconsistent = True
        else:  # pragma: no cover - internal programming error
            raise ValueError(f"unsupported failure kind: {kind!r}")

    def invalid_requirement(self, requirement: str, reason: str) -> None:
        self.has_invalid = True
        self.fail_requirement(requirement, reason, kind=INELIGIBLE)

    def build(self) -> ExecutionEligibilityAssessment:
        if self.has_inconsistent:
            status = INCONSISTENT_INPUT
            freshness = FRESHNESS_STALE
        elif self.has_ineligible:
            status = INELIGIBLE
            freshness = FRESHNESS_INVALID if self.has_invalid else FRESHNESS_CURRENT
        elif self.has_missing:
            status = INSUFFICIENT_EVIDENCE
            freshness = FRESHNESS_INCOMPLETE
        else:
            status = ELIGIBLE
            freshness = FRESHNESS_CURRENT

        candidate = _sha256(self.evidence.get("candidate_fingerprint"))
        pre_probe = _mapping(self.evidence.get("pre_probe"))
        targeted = _mapping(self.evidence.get("targeted_validation"))
        safety = _mapping(self.evidence.get("patch_safety"))
        return ExecutionEligibilityAssessment(
            policy_profile=self.profile,
            eligibility_status=status,
            satisfied_requirements=_dedupe(self.satisfied),
            unsatisfied_requirements=_dedupe(self.unsatisfied),
            blocking_reasons=_dedupe(self.reasons),
            accepted_conflicts=_dedupe(self.conflicts),
            accepted_limitations=_dedupe(self.limitations),
            candidate_fingerprint=candidate,
            probe_fingerprint=_sha256(pre_probe.get("probe_fingerprint")),
            targeted_validation_fingerprint=_sha256(
                targeted.get("targeted_check_set_fingerprint")
                or targeted.get("check_set_fingerprint")
            ),
            patch_safety_binding=_sha256(safety.get("candidate_fingerprint")),
            evidence_freshness=freshness,
        )


def _task_route(evidence: Mapping[str, Any]) -> str:
    route = evidence.get("task_route")
    if isinstance(route, Mapping):
        route = route.get("task") or route.get("selected_workflow")
    text = str(route or "").strip()
    return "defect_repair" if text == "defect_repair_patch" else text


def _common_candidate_requirements(builder: _AssessmentBuilder) -> str:
    evidence = builder.evidence
    if _task_route(evidence) == "defect_repair":
        builder.pass_requirement(REQ_TASK_ROUTE_DEFECT_REPAIR)
    else:
        builder.fail_requirement(
            REQ_TASK_ROUTE_DEFECT_REPAIR,
            BLOCK_TASK_ROUTE_NOT_DEFECT_REPAIR,
            kind=INELIGIBLE,
        )

    if str(evidence.get("patch_basis") or "") == "grounded_defect":
        builder.pass_requirement(REQ_GROUNDED_DEFECT_BASIS)
    else:
        builder.fail_requirement(
            REQ_GROUNDED_DEFECT_BASIS,
            BLOCK_PATCH_BASIS_NOT_GROUNDED_DEFECT,
            kind=INELIGIBLE,
        )

    grounded = evidence.get("source_target_grounded")
    if grounded is True:
        builder.pass_requirement(REQ_SOURCE_TARGET_GROUNDED)
    else:
        builder.fail_requirement(
            REQ_SOURCE_TARGET_GROUNDED,
            BLOCK_SOURCE_TARGET_NOT_GROUNDED,
            kind=(INELIGIBLE if grounded is False else INSUFFICIENT_EVIDENCE),
        )

    raw_candidate = str(evidence.get("candidate_fingerprint") or "").strip().lower()
    candidate = _sha256(raw_candidate)
    if candidate:
        builder.pass_requirement(REQ_CANDIDATE_PRESENT)
    else:
        builder.fail_requirement(
            REQ_CANDIDATE_PRESENT,
            (
                BLOCK_CANDIDATE_MISSING
                if not raw_candidate
                else BLOCK_CANDIDATE_FINGERPRINT_STALE
            ),
            kind=(INELIGIBLE if not raw_candidate else INCONSISTENT_INPUT),
        )

    safety = _mapping(evidence.get("patch_safety"))
    if not safety:
        builder.fail_requirement(
            REQ_PATCH_SAFETY_PASSED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif safety.get("ok") is True:
        builder.pass_requirement(REQ_PATCH_SAFETY_PASSED)
    else:
        builder.fail_requirement(
            REQ_PATCH_SAFETY_PASSED,
            BLOCK_PATCH_SAFETY_NOT_PASSED,
            kind=INELIGIBLE,
        )

    safety_candidate = _sha256(safety.get("candidate_fingerprint"))
    if candidate:
        if safety_candidate == candidate:
            builder.pass_requirement(REQ_CANDIDATE_IDENTITY_FRESH)
        elif not safety_candidate:
            builder.fail_requirement(
                REQ_CANDIDATE_IDENTITY_FRESH,
                BLOCK_EVIDENCE_MISSING,
                kind=INSUFFICIENT_EVIDENCE,
            )
        else:
            builder.fail_requirement(
                REQ_CANDIDATE_IDENTITY_FRESH,
                BLOCK_CANDIDATE_FINGERPRINT_STALE,
                kind=INCONSISTENT_INPUT,
            )
    return candidate


def _full_validation_required(evidence: Mapping[str, Any]) -> ExecutionEligibilityAssessment:
    builder = _AssessmentBuilder(PROFILE_FULL_VALIDATION_REQUIRED, evidence)
    _common_candidate_requirements(builder)
    full = _mapping(evidence.get("full_validation"))
    outcome = str(full.get("outcome") or "").strip()
    if outcome == "passed":
        builder.pass_requirement(REQ_FULL_VALIDATION_PASSED)
    elif outcome:
        builder.fail_requirement(
            REQ_FULL_VALIDATION_PASSED,
            BLOCK_FULL_VALIDATION_NOT_PASSED,
            kind=INELIGIBLE,
        )
    else:
        builder.fail_requirement(
            REQ_FULL_VALIDATION_PASSED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    return builder.build()


def _pre_probe_requirements(builder: _AssessmentBuilder) -> str:
    pre = _mapping(builder.evidence.get("pre_probe"))
    if not pre:
        builder.fail_requirement(
            REQ_PRE_PROBE_REPRODUCED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_INDEPENDENT_PROBE_ORACLE,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        return ""

    if (
        pre.get("probe_result") == "reproduced"
        and pre.get("execution_stage") == "pre_patch"
        and pre.get("probe_freshness") == "current_source_isolated_bytecode_cache"
    ):
        builder.pass_requirement(REQ_PRE_PROBE_REPRODUCED)
    else:
        result = str(pre.get("probe_result") or "")
        builder.fail_requirement(
            REQ_PRE_PROBE_REPRODUCED,
            BLOCK_PRE_PROBE_NOT_REPRODUCED,
            kind=(
                INSUFFICIENT_EVIDENCE
                if result in {"", "inconclusive", "unavailable"}
                else INELIGIBLE
            ),
        )

    independent = (
        pre.get("probe_basis") in _INDEPENDENT_PROBE_BASES
        and pre.get("input_basis") in _INDEPENDENT_INPUT_BASES
        and pre.get("expected_behavior_basis") in _INDEPENDENT_EXPECTATION_BASES
    )
    if independent:
        builder.pass_requirement(REQ_INDEPENDENT_PROBE_ORACLE)
    else:
        builder.fail_requirement(
            REQ_INDEPENDENT_PROBE_ORACLE,
            BLOCK_PROBE_PROVENANCE_NOT_INDEPENDENT,
            kind=INELIGIBLE,
        )

    probe = _sha256(pre.get("probe_fingerprint"))
    binding = _mapping(pre.get("target_binding"))
    executed_source = _sha256(pre.get("executed_source_sha256"))
    localized_source = _sha256(binding.get("localized_source_sha256"))
    if probe and executed_source and executed_source == localized_source:
        builder.pass_requirement(REQ_PROBE_IDENTITY_FRESH)
        builder.pass_requirement(REQ_REPOSITORY_IDENTITY_FRESH)
    elif not probe or not executed_source or not localized_source:
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    else:
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_REPOSITORY_IDENTITY_STALE,
            kind=INCONSISTENT_INPUT,
        )
    return probe


def _closure_requirements(
    builder: _AssessmentBuilder,
    *,
    candidate: str,
    probe: str,
) -> None:
    closure = _mapping(builder.evidence.get("candidate_defect_closure"))
    if not closure:
        builder.fail_requirement(
            REQ_POST_PROBE_FIXED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_CANDIDATE_SANDBOX_APPLIED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        return

    closure_candidate = _sha256(closure.get("candidate_fingerprint"))
    if not closure_candidate:
        builder.fail_requirement(
            REQ_CANDIDATE_IDENTITY_FRESH,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif candidate and closure_candidate != candidate:
        builder.fail_requirement(
            REQ_CANDIDATE_IDENTITY_FRESH,
            BLOCK_CANDIDATE_FINGERPRINT_STALE,
            kind=INCONSISTENT_INPUT,
        )
    else:
        builder.pass_requirement(REQ_CANDIDATE_IDENTITY_FRESH)

    closure_probe = _sha256(closure.get("probe_fingerprint"))
    if not closure_probe:
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif probe and closure_probe != probe:
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_PROBE_FINGERPRINT_STALE,
            kind=INCONSISTENT_INPUT,
        )
    else:
        builder.pass_requirement(REQ_PROBE_IDENTITY_FRESH)

    status = str(closure.get("defect_closure_status") or "")
    post_result = str(closure.get("post_probe_result") or "")
    if status == "fixed" and post_result == "not_reproduced":
        builder.pass_requirement(REQ_POST_PROBE_FIXED)
    elif status == "fixed":
        builder.fail_requirement(
            REQ_POST_PROBE_FIXED,
            BLOCK_INCONSISTENT_EVIDENCE,
            kind=INCONSISTENT_INPUT,
        )
    else:
        builder.fail_requirement(
            REQ_POST_PROBE_FIXED,
            BLOCK_POST_PROBE_NOT_FIXED,
            kind=(
                INSUFFICIENT_EVIDENCE
                if status in {"", "inconclusive", "unavailable"}
                else INELIGIBLE
            ),
        )

    if (
        closure.get("sandbox_only") is True
        and closure.get("candidate_probe_apply_status") == "applied"
        and closure.get("candidate_probe_sandbox_cleanup_ok") is True
    ):
        builder.pass_requirement(REQ_CANDIDATE_SANDBOX_APPLIED)
    else:
        apply_status = str(closure.get("candidate_probe_apply_status") or "")
        builder.fail_requirement(
            REQ_CANDIDATE_SANDBOX_APPLIED,
            BLOCK_CANDIDATE_SANDBOX_NOT_APPLIED,
            kind=(
                INSUFFICIENT_EVIDENCE
                if apply_status in {"", "not_attempted", "unavailable"}
                else INELIGIBLE
            ),
        )


def _targeted_and_oracle_requirements(
    builder: _AssessmentBuilder,
    *,
    candidate: str,
    probe: str,
) -> None:
    targeted = _mapping(builder.evidence.get("targeted_validation"))
    if not targeted:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_NO_REGRESSION_ORACLE_FAILURE,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        return

    category = str(targeted.get("targeted_validation_category") or "")
    status = str(targeted.get("targeted_validation_status") or "")
    targeted_candidate = _sha256(targeted.get("candidate_fingerprint"))
    check_set = _sha256(
        targeted.get("targeted_check_set_fingerprint")
        or targeted.get("check_set_fingerprint")
    )

    if category in _TAMPERED_TARGETED_CATEGORIES:
        builder.invalid_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_TARGETED_EVIDENCE_INVALID,
        )
    elif category in _STALE_CANDIDATE_CATEGORIES:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_CANDIDATE_FINGERPRINT_STALE,
            kind=INCONSISTENT_INPUT,
        )
    elif category in _STALE_REPOSITORY_CATEGORIES:
        builder.fail_requirement(
            REQ_REPOSITORY_IDENTITY_FRESH,
            BLOCK_REPOSITORY_IDENTITY_STALE,
            kind=INCONSISTENT_INPUT,
        )
    elif status not in {"passed", "failed"}:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_TARGETED_EVIDENCE_INCONCLUSIVE,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif (
        targeted.get("selection_complete") is True
        and (_nonnegative_int(targeted.get("selected_check_count")) or 0) > 0
        and check_set
        and targeted.get("targeted_validation_sandbox_cleanup_ok") is not False
    ):
        builder.pass_requirement(REQ_TARGETED_EVIDENCE_VALID)
        builder.pass_requirement(REQ_REPOSITORY_IDENTITY_FRESH)
    else:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )

    if not targeted_candidate:
        builder.fail_requirement(
            REQ_CANDIDATE_IDENTITY_FRESH,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif candidate and targeted_candidate != candidate:
        builder.fail_requirement(
            REQ_CANDIDATE_IDENTITY_FRESH,
            BLOCK_CANDIDATE_FINGERPRINT_STALE,
            kind=INCONSISTENT_INPUT,
        )
    else:
        builder.pass_requirement(REQ_CANDIDATE_IDENTITY_FRESH)

    baseline = str(targeted.get("baseline_targeted_outcome") or "")
    candidate_outcome = str(targeted.get("candidate_targeted_outcome") or "")
    if baseline != "passed":
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_TARGETED_BASELINE_NOT_PASSED,
            kind=(
                INSUFFICIENT_EVIDENCE
                if baseline in {"", "inconclusive", "targeted_validation_not_run"}
                else INELIGIBLE
            ),
        )
    if status in {"passed", "failed"} and candidate_outcome != status:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_INCONSISTENT_EVIDENCE,
            kind=INCONSISTENT_INPUT,
        )

    # A passed targeted result needs no conflict exception.  If an oracle
    # receipt exists anyway, its identity still may not contradict the result.
    oracle = _mapping(builder.evidence.get("oracle_assessment"))
    if status == "passed" and not oracle:
        builder.pass_requirement(REQ_NO_REGRESSION_ORACLE_FAILURE)
        builder.pass_requirement(REQ_NO_UNRESOLVED_ORACLE_CONFLICT)
        return
    if not oracle:
        builder.fail_requirement(
            REQ_NO_REGRESSION_ORACLE_FAILURE,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        return

    oracle_status = str(oracle.get("check_oracle_assessment_status") or "")
    if oracle_status == "candidate_modified_check":
        builder.invalid_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_TARGETED_EVIDENCE_INVALID,
        )
    elif oracle_status in {"stale_probe", "stale_check"}:
        builder.fail_requirement(
            REQ_PROBE_IDENTITY_FRESH,
            (
                BLOCK_PROBE_FINGERPRINT_STALE
                if oracle_status == "stale_probe"
                else BLOCK_REPOSITORY_IDENTITY_STALE
            ),
            kind=INCONSISTENT_INPUT,
        )
    elif oracle_status != "current":
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_UNRESOLVED_ORACLE_CONFLICT,
            kind=INSUFFICIENT_EVIDENCE,
        )

    oracle_candidate = _sha256(oracle.get("check_oracle_candidate_fingerprint"))
    oracle_probe = _sha256(oracle.get("check_oracle_probe_fingerprint"))
    oracle_check_set = _sha256(
        oracle.get("check_oracle_check_set_fingerprint")
    )
    for actual, expected, requirement, reason in (
        (
            oracle_candidate,
            candidate,
            REQ_CANDIDATE_IDENTITY_FRESH,
            BLOCK_CANDIDATE_FINGERPRINT_STALE,
        ),
        (
            oracle_probe,
            probe,
            REQ_PROBE_IDENTITY_FRESH,
            BLOCK_PROBE_FINGERPRINT_STALE,
        ),
        (
            oracle_check_set,
            check_set,
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_CHECK_SET_FINGERPRINT_STALE,
        ),
    ):
        if actual and expected and actual == expected:
            builder.pass_requirement(requirement)
        elif not actual or not expected:
            builder.fail_requirement(
                requirement,
                BLOCK_EVIDENCE_MISSING,
                kind=INSUFFICIENT_EVIDENCE,
            )
        else:
            builder.fail_requirement(
                requirement,
                reason,
                kind=INCONSISTENT_INPUT,
            )

    assessments = [
        item
        for item in _sequence(oracle.get("check_oracle_assessments"))
        if isinstance(item, Mapping)
    ]
    selected_count = _nonnegative_int(targeted.get("selected_check_count"))
    if selected_count is None:
        builder.fail_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_INCONSISTENT_EVIDENCE,
            kind=INCONSISTENT_INPUT,
        )
        selected_count = 0
    if not assessments or (selected_count and len(assessments) != selected_count):
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )
        return

    regression_failure = False
    unresolved_failure = False
    unaccepted_failure = False
    invalid_assessment = False
    failed_count = 0
    for assessment in assessments:
        assessment_status = str(assessment.get("assessment_status") or "")
        execution = str(assessment.get("check_execution_outcome") or "")
        role = str(assessment.get("oracle_role") or "")
        if assessment_status == "candidate_modified_check":
            invalid_assessment = True
        elif assessment_status != "current":
            unresolved_failure = True

        assessment_candidate = _sha256(assessment.get("candidate_fingerprint"))
        assessment_probe = _sha256(assessment.get("probe_fingerprint"))
        if candidate:
            if not assessment_candidate:
                builder.fail_requirement(
                    REQ_CANDIDATE_IDENTITY_FRESH,
                    BLOCK_EVIDENCE_MISSING,
                    kind=INSUFFICIENT_EVIDENCE,
                )
            elif assessment_candidate != candidate:
                builder.fail_requirement(
                    REQ_CANDIDATE_IDENTITY_FRESH,
                    BLOCK_CANDIDATE_FINGERPRINT_STALE,
                    kind=INCONSISTENT_INPUT,
                )
        if probe:
            if not assessment_probe:
                builder.fail_requirement(
                    REQ_PROBE_IDENTITY_FRESH,
                    BLOCK_EVIDENCE_MISSING,
                    kind=INSUFFICIENT_EVIDENCE,
                )
            elif assessment_probe != probe:
                builder.fail_requirement(
                    REQ_PROBE_IDENTITY_FRESH,
                    BLOCK_PROBE_FINGERPRINT_STALE,
                    kind=INCONSISTENT_INPUT,
                )
        if not _sha256(assessment.get("check_source_sha256")) or not _sha256(
            assessment.get("check_fingerprint")
        ):
            unresolved_failure = True

        if execution == "failed":
            failed_count += 1
            if role == "defect_preservation_oracle" and assessment_status == "current":
                continue
            if role == "candidate_regression_oracle":
                regression_failure = True
            elif role in {"conflict_unresolved", "insufficient_basis", "unrelated"}:
                unresolved_failure = True
            else:
                unaccepted_failure = True
        elif status == "failed" and execution != "passed":
            # Aggregate pytest failure without a per-check verdict cannot be
            # policy-dismissed; it may be the regression.
            unresolved_failure = True

    if invalid_assessment:
        builder.invalid_requirement(
            REQ_TARGETED_EVIDENCE_VALID,
            BLOCK_TARGETED_EVIDENCE_INVALID,
        )
    if regression_failure:
        builder.fail_requirement(
            REQ_NO_REGRESSION_ORACLE_FAILURE,
            BLOCK_CANDIDATE_REGRESSION_ORACLE,
            kind=INELIGIBLE,
        )
    else:
        builder.pass_requirement(REQ_NO_REGRESSION_ORACLE_FAILURE)
    if unresolved_failure:
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_UNRESOLVED_ORACLE_CONFLICT,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif unaccepted_failure:
        builder.fail_requirement(
            REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
            BLOCK_FAILED_CHECK_NOT_ACCEPTED,
            kind=INELIGIBLE,
        )
    else:
        builder.pass_requirement(REQ_NO_UNRESOLVED_ORACLE_CONFLICT)

    if status == "failed":
        if failed_count and not (
            regression_failure
            or unresolved_failure
            or unaccepted_failure
            or invalid_assessment
        ):
            builder.conflicts.append(ACCEPTED_CONFLICT_DEFECT_PRESERVATION)
        elif failed_count == 0:
            builder.fail_requirement(
                REQ_NO_UNRESOLVED_ORACLE_CONFLICT,
                BLOCK_UNRESOLVED_ORACLE_CONFLICT,
                kind=INSUFFICIENT_EVIDENCE,
            )


def _bounded_full_validation(builder: _AssessmentBuilder) -> None:
    full = _mapping(builder.evidence.get("full_validation"))
    outcome = str(full.get("outcome") or "")
    category = str(full.get("category") or "")
    if outcome == "passed":
        builder.pass_requirement(REQ_FULL_VALIDATION_PASSED)
    elif outcome == "failed":
        builder.fail_requirement(
            REQ_FULL_VALIDATION_PASSED,
            BLOCK_FULL_VALIDATION_GENUINE_FAILURE,
            kind=INELIGIBLE,
        )
    elif outcome == "inconclusive" and category == "validation_budget_exhausted":
        builder.pass_requirement(REQ_FULL_VALIDATION_BUDGET_EXHAUSTED)
        builder.limitations.append(
            ACCEPTED_LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED
        )
    elif outcome == "inconclusive":
        builder.fail_requirement(
            REQ_FULL_VALIDATION_BUDGET_EXHAUSTED,
            BLOCK_FULL_VALIDATION_CAUSE_NOT_ACCEPTED,
            kind=INSUFFICIENT_EVIDENCE,
        )
    elif outcome:
        builder.fail_requirement(
            REQ_FULL_VALIDATION_PASSED,
            BLOCK_FULL_VALIDATION_CAUSE_NOT_ACCEPTED,
            kind=INSUFFICIENT_EVIDENCE,
        )
    else:
        builder.fail_requirement(
            REQ_FULL_VALIDATION_PASSED,
            BLOCK_EVIDENCE_MISSING,
            kind=INSUFFICIENT_EVIDENCE,
        )


def _bounded_human_review(evidence: Mapping[str, Any]) -> ExecutionEligibilityAssessment:
    builder = _AssessmentBuilder(PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW, evidence)
    candidate = _common_candidate_requirements(builder)
    _bounded_full_validation(builder)
    probe = _pre_probe_requirements(builder)
    _closure_requirements(builder, candidate=candidate, probe=probe)
    _targeted_and_oracle_requirements(builder, candidate=candidate, probe=probe)

    authorization = _mapping(evidence.get("execution_authorization"))
    if authorization.get("human_approval_required_for_execution") is True:
        builder.pass_requirement(REQ_HUMAN_APPROVAL_REQUIRED)
    else:
        builder.fail_requirement(
            REQ_HUMAN_APPROVAL_REQUIRED,
            (
                BLOCK_EVIDENCE_MISSING
                if "human_approval_required_for_execution" not in authorization
                else BLOCK_HUMAN_APPROVAL_NOT_REQUIRED
            ),
            kind=(
                INSUFFICIENT_EVIDENCE
                if "human_approval_required_for_execution" not in authorization
                else INELIGIBLE
            ),
        )
    denial = str(
        authorization.get("execution_authorization_denied_reason") or ""
    )
    if denial in _HARD_EXECUTION_SAFETY_DENIALS:
        builder.fail_requirement(
            REQ_PATCH_SAFETY_PASSED,
            BLOCK_EXECUTION_SAFETY_DENIAL,
            kind=INELIGIBLE,
        )
    return builder.build()


def evaluate_execution_eligibility(
    evidence: Mapping[str, Any],
) -> ExecutionEligibilityReport:
    """Pure deterministic reduction over already-produced structured facts."""

    if not isinstance(evidence, Mapping):
        evidence = {}
    return ExecutionEligibilityReport(
        assessments=(
            _full_validation_required(evidence),
            _bounded_human_review(evidence),
        )
    )


def execution_eligibility_status_of_payload(
    payload: Any,
    *,
    policy_profile: str = PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
) -> str:
    """Read current artifacts and fail old artifacts closed.

    Historical payloads have no receipt.  They are ``legacy_unassessed`` and
    never silently become eligible.
    """

    if policy_profile not in POLICY_PROFILES:
        raise ValueError(f"unsupported policy profile: {policy_profile!r}")
    block = _mapping(payload)
    profiles = _mapping(block.get("execution_eligibility_profiles"))
    assessment = _mapping(profiles.get(policy_profile))
    status = str(assessment.get("eligibility_status") or "")
    return status if status in ELIGIBILITY_STATUSES else LEGACY_UNASSESSED


def describe_execution_eligibility(report: ExecutionEligibilityReport) -> str:
    bounded = report.assessment_for(PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW)
    if bounded.eligible:
        return (
            "The reported defect was independently reproduced. The exact candidate "
            "fixes the same bounded probe in a sandbox. Full repository validation "
            "did not finish within the configured budget. The failed selected "
            "existing checks were classified as preserving the previously broken "
            "behavior. The candidate is eligible for human review, but it has not "
            "been authorized or applied to the repository."
        )
    if bounded.eligibility_status == INCONSISTENT_INPUT:
        return (
            "Execution eligibility could not be assessed because candidate, probe, "
            "check-set, or repository evidence was stale or inconsistent."
        )
    if bounded.eligibility_status == INSUFFICIENT_EVIDENCE:
        return (
            "The candidate does not yet have enough fresh bounded evidence for the "
            "human-review eligibility profile."
        )
    return (
        "The candidate is not eligible under the bounded human-review profile. "
        "Execution authorization remains unchanged."
    )


def execution_eligibility_guardrails() -> dict[str, bool]:
    return {
        "pure_evidence_reduction": True,
        "failed_validation_rewritten": False,
        "full_validation_rewritten": False,
        "targeted_validation_rewritten": False,
        "defect_probe_rewritten": False,
        "patch_safety_overridden": False,
        "execution_authority_granted": False,
        "auto_apply_granted": False,
        "human_approval_bypassed": False,
        "evidence_generated": False,
        "validation_called": False,
        "retrieval_called": False,
        "repository_traversed": False,
        "model_called": False,
        "network_called": False,
    }


__all__ = [
    "PHASE_ID",
    "SCHEMA_VERSION",
    "PROFILE_FULL_VALIDATION_REQUIRED",
    "PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW",
    "POLICY_PROFILES",
    "ELIGIBLE",
    "INELIGIBLE",
    "INSUFFICIENT_EVIDENCE",
    "INCONSISTENT_INPUT",
    "ELIGIBILITY_STATUSES",
    "LEGACY_UNASSESSED",
    "REQUIREMENT_IDS",
    "BLOCKING_REASONS",
    "ExecutionEligibilityAssessment",
    "ExecutionEligibilityReport",
    "evaluate_execution_eligibility",
    "execution_eligibility_status_of_payload",
    "describe_execution_eligibility",
    "execution_eligibility_guardrails",
]
