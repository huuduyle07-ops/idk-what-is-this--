"""CANDIDATE.VERIFY.LIVE.1 — read-only candidate verification before human review.

``AUTO_PATCH_ENABLED`` names one thing: whether this process may **mutate** a
repository.  Until this phase it silently named a second thing as well.  The
kill switch returned out of :func:`core.pipeline.maybe_run_auto_patch` before
the candidate sandbox, the paired post-probe, the defect-closure assessment,
targeted baseline/candidate validation, the oracle assessment and the exact
candidate fingerprint — and yet the authored candidate was still rendered for a
human.  Mutation-disabled had become verification-disabled, and the T6 smoke
paid for it: the branch-reorder candidate reached the user with
``needs_escalation=false`` and no evidence of any kind, because the only code
that would have measured it lived past the return.

That candidate is the reason this module exists.  It is *structurally* tiny —
it swaps two ``elif`` branches — so ``safe_minimal`` accepts it, correctly:
shape safety is shape safety and it was never asked to detect a semantic
inversion.  What rejects it is behavior: the primary defect probe reports
``fixed`` while the deterministic preservation counter-case reports
``regressed``.  Both facts already existed; nothing ran them.

So this module adds no evidence producer.  It **orchestrates the existing ones
in the read-only branch and reduces their receipts into one closed verdict**:

``patch safety / safe_minimal``      already ran — consumed here
``exact candidate sandbox``          OPS.PATCH.2 / DEFECT.PROBE.LIVE.2 sandbox
``paired post-probe``                DEFECT.PROBE.LIVE.3
``targeted validation``              OPS.VALIDATE.3
``oracle assessment``                VALIDATE.ORACLE.LIVE.1

Three rules govern the reduction.

**Verification is not authorization.**  ``verified`` is a statement about
evidence.  It grants nothing.  Under ``AUTO_PATCH_ENABLED=false`` a verified
candidate still ends the run with ``execution_authorized=false`` and
``final_repository_changed=false``; the switch keeps doing its only job.

**Missing evidence is never a pass.**  A required component that could not be
measured yields ``unavailable`` or ``inconclusive`` for the whole verification,
never ``verified``.  The single exception is stated out loud rather than
hidden: OPS.VALIDATE.3 answering ``no_relevant_existing_checks`` is a
*completed* selection whose finding is that no existing check is structurally
related to the target.  That is knowledge, not absence of knowledge, so it is
recorded as ``not_applicable`` **and** listed in ``accepted_limitations`` — it
can never make a candidate verified on its own, because the paired probe still
has to support it.

**A paired result may not be flattened.**  ``primary fixed`` is not closure.
Any preservation case the baseline already satisfied and the candidate broke
is a contradiction, whatever the primary case says and whatever the writer's
``confidence`` field claims.  Model confidence is not an input here at all.

The evaluator is pure: a mapping of already-structured receipts in, one
receipt out.  It performs no file, graph, model, network, subprocess,
retrieval, probing or validation work, and it contains no authority setter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any, Mapping, Sequence


PHASE_ID = "CANDIDATE.VERIFY.LIVE.1"
SCHEMA_VERSION = "candidate_verification_live_1_v1"

# ── Verification profiles ────────────────────────────────────────────────────
#
# The profile names which components are *required*, and it is derived from the
# candidate's existing typed patch basis rather than invented here.
PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE = "grounded_defect_bounded_evidence"
PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE = "explicit_change_sandbox_coherence"
VERIFICATION_PROFILES: tuple[str, ...] = (
    PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
    PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE,
)

# ── Closed verification vocabulary (§7) ──────────────────────────────────────
VERIFIED = "verified"
REJECTED = "rejected"
INCONCLUSIVE = "inconclusive"
UNAVAILABLE = "unavailable"
STALE = "stale"
INVALID = "invalid"
VERIFICATION_STATUSES: tuple[str, ...] = (
    VERIFIED,
    REJECTED,
    INCONCLUSIVE,
    UNAVAILABLE,
    STALE,
    INVALID,
)

#: A payload written before this phase carries no verification at all.  It reads
#: back as its own value — never ``verified`` — and historical artifacts are not
#: rewritten to pretend a gate ran that did not exist.
LEGACY_UNVERIFIED = "legacy_unverified"

# ── Components (§6) ──────────────────────────────────────────────────────────
COMPONENT_PATCH_SAFETY = "patch_safety"
COMPONENT_EXACT_SANDBOX = "exact_candidate_sandbox"
COMPONENT_PAIRED_PROBE = "paired_defect_probe"
COMPONENT_TARGETED_VALIDATION = "targeted_validation"
COMPONENT_ORACLE_ASSESSMENT = "oracle_assessment"
COMPONENT_IDS: tuple[str, ...] = (
    COMPONENT_PATCH_SAFETY,
    COMPONENT_EXACT_SANDBOX,
    COMPONENT_PAIRED_PROBE,
    COMPONENT_TARGETED_VALIDATION,
    COMPONENT_ORACLE_ASSESSMENT,
)

#: Which components each profile requires.  A component outside a profile's set
#: is reported ``not_applicable`` and cannot block or support.
REQUIRED_COMPONENTS: dict[str, tuple[str, ...]] = {
    PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE: (
        COMPONENT_PATCH_SAFETY,
        COMPONENT_EXACT_SANDBOX,
        COMPONENT_PAIRED_PROBE,
        COMPONENT_TARGETED_VALIDATION,
        COMPONENT_ORACLE_ASSESSMENT,
    ),
    PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE: (
        COMPONENT_PATCH_SAFETY,
        COMPONENT_EXACT_SANDBOX,
    ),
}

# ── Per-component verdicts ───────────────────────────────────────────────────
SUPPORTING = "supporting"
CONTRADICTING = "contradicting"
COMPONENT_INCONCLUSIVE = "inconclusive"
COMPONENT_UNAVAILABLE = "unavailable"
COMPONENT_NOT_APPLICABLE = "not_applicable"
COMPONENT_STALE = "stale"
COMPONENT_INVALID = "invalid"
COMPONENT_VERDICTS: tuple[str, ...] = (
    SUPPORTING,
    CONTRADICTING,
    COMPONENT_INCONCLUSIVE,
    COMPONENT_UNAVAILABLE,
    COMPONENT_NOT_APPLICABLE,
    COMPONENT_STALE,
    COMPONENT_INVALID,
)

# ── Closed rejection-reason vocabulary (§23) ─────────────────────────────────
#
# Diagnostics stay in the producer receipts.  These are the machine-facing
# consequences, rendered into the payload's canonical structured ``issues``
# shape by :meth:`CandidateVerificationReceipt.as_issues`.
REASON_CANDIDATE_MISSING = "candidate_missing"
REASON_PATCH_SAFETY_BLOCKED = "patch_safety_blocked"
REASON_SANDBOX_APPLY_FAILED = "candidate_sandbox_apply_failed"
REASON_SANDBOX_NOT_ISOLATED = "candidate_sandbox_not_isolated"
REASON_PRIMARY_DEFECT_NOT_CLOSED = "primary_defect_not_closed"
REASON_PRESERVATION_REGRESSED = "behavior_preservation_regressed"
#: DEFECT.PROBE.LIVE.4.  The user's own case closed and a bounded case for
#: the same subject invariant did not, so the defect family is still open.
REASON_SUBJECT_INVARIANT_NOT_CLOSED = "subject_invariant_not_closed"
REASON_TARGETED_GENUINE_REGRESSION = "targeted_validation_genuine_regression"
REASON_TARGETED_EVIDENCE_TAMPERED = "candidate_modified_its_own_check"
REASON_ORACLE_CONFLICT_UNRESOLVED = "oracle_conflict_unresolved"
REASON_ORACLE_ASSESSMENT_STALE = "oracle_assessment_stale"
REASON_CANDIDATE_FINGERPRINT_STALE = "candidate_fingerprint_stale"
REASON_PROBE_FINGERPRINT_STALE = "probe_fingerprint_stale"
REASON_SOURCE_STATE_STALE = "source_state_stale"
REASON_TARGET_BINDING_STALE = "target_binding_stale"
REASON_INVALID_COMPARISON = "invalid_candidate_comparison"
REASON_REQUIRED_EVIDENCE_MISSING = "required_evidence_missing"
REASON_REQUIRED_EVIDENCE_INCONCLUSIVE = "required_evidence_inconclusive"
REASON_PROFILE_UNSUPPORTED = "verification_profile_unsupported"
REJECTION_REASONS: tuple[str, ...] = (
    REASON_CANDIDATE_MISSING,
    REASON_PATCH_SAFETY_BLOCKED,
    REASON_SANDBOX_APPLY_FAILED,
    REASON_SANDBOX_NOT_ISOLATED,
    REASON_PRIMARY_DEFECT_NOT_CLOSED,
    REASON_PRESERVATION_REGRESSED,
    REASON_SUBJECT_INVARIANT_NOT_CLOSED,
    REASON_TARGETED_GENUINE_REGRESSION,
    REASON_TARGETED_EVIDENCE_TAMPERED,
    REASON_ORACLE_CONFLICT_UNRESOLVED,
    REASON_ORACLE_ASSESSMENT_STALE,
    REASON_CANDIDATE_FINGERPRINT_STALE,
    REASON_PROBE_FINGERPRINT_STALE,
    REASON_SOURCE_STATE_STALE,
    REASON_TARGET_BINDING_STALE,
    REASON_INVALID_COMPARISON,
    REASON_REQUIRED_EVIDENCE_MISSING,
    REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
    REASON_PROFILE_UNSUPPORTED,
)

#: Limitations a verification may accept without being made to mean "passed".
#: Each one is recorded on the receipt, so accepting it is visible rather than
#: implicit.
LIMITATION_NO_RELEVANT_EXISTING_CHECKS = "no_relevant_existing_checks"
LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED = "full_validation_budget_exhausted"
LIMITATION_NO_PRESERVATION_ORACLE = "no_preservation_oracle_for_subject"
#: DEFECT.PROBE.LIVE.4.  The subject carries no deterministic behavioral
#: matrix, so closure rests on the DEFECT.PROBE.LIVE.3 pair alone.
LIMITATION_NO_BEHAVIORAL_MATRIX = "no_behavioral_matrix_for_subject"
ACCEPTED_LIMITATIONS: tuple[str, ...] = (
    LIMITATION_NO_RELEVANT_EXISTING_CHECKS,
    LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED,
    LIMITATION_NO_PRESERVATION_ORACLE,
    LIMITATION_NO_BEHAVIORAL_MATRIX,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

#: DEFECT.PROBE.LIVE.3 paired statuses that mean the pair closed.
_CLOSING_PAIRED_STATUSES = frozenset({"fixed_and_preserved", "fixed"})
#: DEFECT.PROBE.LIVE.4 — the only matrix status that means behavioral closure.
#: Read as a literal for the same reason the paired set is: this module reduces
#: receipts and must not import a producer to learn what its own field means.
_CLOSING_MATRIX_STATUSES = frozenset({"fixed_and_preserved"})
#: Matrix statuses whose defect family is measurably still open.
_OPEN_MATRIX_STATUSES = frozenset(
    {"partially_fixed", "unresolved_matrix_failure", "still_reproduced"}
)
#: Paired statuses whose primary case did not close at all.
_PRIMARY_OPEN_PAIRED_STATUSES = frozenset(
    {"still_reproduced", "changed_but_unresolved"}
)
#: OPS.PATCH.2 / DEFECT.PROBE.LIVE.2 apply statuses that mean "not measured".
_SANDBOX_NOT_MEASURED = frozenset({"", "not_attempted", "unavailable", "sandbox_unavailable"})
#: OPS.VALIDATE.3 categories that mean the candidate rewrote its own oracle.
_TAMPERED_TARGETED_CATEGORIES = frozenset(
    {"selected_validation_check_modified", "candidate_modified_check"}
)
#: OPS.VALIDATE.3 categories that mean the candidate binding went stale.
_STALE_TARGETED_CATEGORIES = frozenset(
    {"candidate_fingerprint_stale", "repository_identity_mismatch"}
)
#: VALIDATE.ORACLE roles that make a failing check a genuine regression.
_GENUINE_REGRESSION_ROLE = "candidate_regression_oracle"
_PRESERVATION_ORACLE_ROLE = "defect_preservation_oracle"
_UNRESOLVED_CONFLICT_ROLE = "conflict_unresolved"


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


def _dedupe(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


@dataclass(frozen=True, slots=True)
class ComponentVerdict:
    """One named evidence component's contribution, with its reason."""

    component: str
    verdict: str
    reason: str = ""
    detail: str = ""

    def __post_init__(self) -> None:
        if self.component not in COMPONENT_IDS:
            raise ValueError(f"unknown verification component: {self.component!r}")
        if self.verdict not in COMPONENT_VERDICTS:
            raise ValueError(f"unknown component verdict: {self.verdict!r}")
        if self.reason and self.reason not in REJECTION_REASONS:
            raise ValueError(f"unknown rejection reason: {self.reason!r}")

    def as_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "verdict": self.verdict,
            "reason": self.reason,
            "detail": self.detail,
        }


@dataclass(frozen=True, slots=True)
class CandidateVerificationReceipt:
    """What was verified, on which exact candidate, and what it establishes.

    The type carries no confidence and no authorization boolean.  The explicit
    ``authority_effect=none``, ``execution_authorized=False`` and
    ``final_repository_changed=False`` fields exist so a consumer cannot read
    omission as an invitation to infer authority (§15, §21).
    """

    status: str
    policy_profile: str
    candidate_fingerprint: str
    components: tuple[ComponentVerdict, ...]
    rejection_reasons: tuple[str, ...] = ()
    accepted_limitations: tuple[str, ...] = ()
    probe_fingerprint: str = ""
    targeted_check_set_fingerprint: str = ""
    patch_safety_binding: str = ""
    timings: dict[str, float] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    authority_effect: str = "none"

    def __post_init__(self) -> None:
        if self.status not in VERIFICATION_STATUSES:
            raise ValueError(f"unsupported verification status: {self.status!r}")
        if self.policy_profile not in VERIFICATION_PROFILES:
            raise ValueError(f"unsupported verification profile: {self.policy_profile!r}")
        if self.authority_effect != "none":
            raise ValueError("candidate verification may not grant authority")
        unknown = set(self.rejection_reasons) - set(REJECTION_REASONS)
        if unknown:
            raise ValueError(f"unknown rejection reasons: {sorted(unknown)!r}")
        unknown_limits = set(self.accepted_limitations) - set(ACCEPTED_LIMITATIONS)
        if unknown_limits:
            raise ValueError(f"unknown accepted limitations: {sorted(unknown_limits)!r}")
        if self.status == VERIFIED and self.rejection_reasons:
            raise ValueError("a verified candidate may not carry rejection reasons")

    # ── What the status means, said once ────────────────────────────────────
    @property
    def verified(self) -> bool:
        return self.status == VERIFIED

    @property
    def review_ready(self) -> bool:
        """§10 — may this candidate be *presented* as ready to approve?

        Only a verified one.  This is not approval and not authority; it is
        permission to describe the candidate as review-ready at all.
        """

        return self.status == VERIFIED

    @property
    def visible_for_debugging(self) -> bool:
        """§10 — a rejected candidate stays readable, with its evidence."""

        return True

    @property
    def needs_escalation(self) -> bool:
        """§11 — anything short of ``verified`` fails closed to a human."""

        return self.status != VERIFIED

    @property
    def execution_authorized(self) -> bool:
        """§15 — never.  Verification is evidence, not authority."""

        return False

    @property
    def final_repository_changed(self) -> bool:
        """§2 — read-only by construction; the sandbox is the only writer."""

        return False

    def component_verdict(self, component: str) -> str:
        for item in self.components:
            if item.component == component:
                return item.verdict
        return COMPONENT_NOT_APPLICABLE

    def as_issues(self) -> list[dict[str, Any]]:
        """Rejection reasons in the payload's canonical structured shape (§23)."""

        return [
            {
                "severity": "high",
                "type": "candidate_verification",
                "file": "",
                "symbol": "",
                "reason": _REASON_TEXT.get(reason, reason),
                "fix": _REASON_FIX.get(reason, _DEFAULT_FIX),
                "code": reason,
            }
            for reason in self.rejection_reasons
        ]

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "phase_id": PHASE_ID,
            "schema_version": self.schema_version,
            "status": self.status,
            "policy_profile": self.policy_profile,
            "candidate_fingerprint": self.candidate_fingerprint,
            "components": [item.as_dict() for item in self.components],
            "rejection_reasons": list(self.rejection_reasons),
            "accepted_limitations": list(self.accepted_limitations),
            "probe_fingerprint": self.probe_fingerprint,
            "targeted_check_set_fingerprint": self.targeted_check_set_fingerprint,
            "patch_safety_binding": self.patch_safety_binding,
            "review_ready": self.review_ready,
            "visible_for_debugging": self.visible_for_debugging,
            "needs_escalation": self.needs_escalation,
            "execution_authorized": self.execution_authorized,
            "final_repository_changed": self.final_repository_changed,
            "authority_effect": self.authority_effect,
        }
        payload["verification_fingerprint"] = _fingerprint(payload)
        return payload

    def as_telemetry(self) -> dict[str, Any]:
        """The additive bounded facts this phase writes onto a payload (§21)."""

        receipt = self.as_dict()
        return {
            "candidate_verification_phase_id": PHASE_ID,
            "candidate_verification_schema_version": self.schema_version,
            "candidate_verification_status": self.status,
            "candidate_verification_profile": self.policy_profile,
            "candidate_verification_candidate_fingerprint": self.candidate_fingerprint,
            "candidate_verification_sandbox_status": self.component_verdict(
                COMPONENT_EXACT_SANDBOX
            ),
            "candidate_verification_patch_safety_status": self.component_verdict(
                COMPONENT_PATCH_SAFETY
            ),
            "candidate_verification_paired_probe_status": self.component_verdict(
                COMPONENT_PAIRED_PROBE
            ),
            "candidate_verification_targeted_validation_status": (
                self.component_verdict(COMPONENT_TARGETED_VALIDATION)
            ),
            "candidate_verification_oracle_status": self.component_verdict(
                COMPONENT_ORACLE_ASSESSMENT
            ),
            "candidate_verification_components": [
                item.as_dict() for item in self.components
            ],
            "candidate_verification_rejection_reasons": list(self.rejection_reasons),
            "candidate_verification_accepted_limitations": list(
                self.accepted_limitations
            ),
            "candidate_verification_probe_fingerprint": self.probe_fingerprint,
            "candidate_verification_targeted_check_set_fingerprint": (
                self.targeted_check_set_fingerprint
            ),
            "candidate_verification_patch_safety_binding": self.patch_safety_binding,
            "candidate_verification_receipt": receipt,
            "candidate_verification_fingerprint": receipt["verification_fingerprint"],
            "candidate_review_ready": self.review_ready,
            "candidate_visible_for_debugging": self.visible_for_debugging,
            "candidate_verification_needs_escalation": self.needs_escalation,
            "candidate_verification_execution_authorized": False,
            "candidate_verification_final_repository_changed": False,
            "candidate_verification_authority_effect": "none",
            "candidate_verification_auto_apply_effect": "none",
            "candidate_verification_model_calls": 0,
            "candidate_verification_network_calls": 0,
            "candidate_verification_repository_mutations": 0,
            "candidate_verification_timings": dict(self.timings),
        }


_DEFAULT_FIX = (
    "Read the candidate verification evidence before approving anything; the "
    "candidate is not verified."
)
_REASON_TEXT: dict[str, str] = {
    REASON_CANDIDATE_MISSING: (
        "No exact candidate was present to verify."
    ),
    REASON_PATCH_SAFETY_BLOCKED: (
        "Existing patch safety refused the candidate's target paths."
    ),
    REASON_SANDBOX_APPLY_FAILED: (
        "The exact candidate could not be applied in the disposable sandbox."
    ),
    REASON_SANDBOX_NOT_ISOLATED: (
        "Candidate evidence did not come from an isolated sandbox copy."
    ),
    REASON_PRIMARY_DEFECT_NOT_CLOSED: (
        "The bounded defect probe still reproduces the reported behavior after "
        "the candidate."
    ),
    REASON_PRESERVATION_REGRESSED: (
        "The candidate fixed the reported case but broke a behavior the "
        "unpatched code already produced correctly."
    ),
    REASON_TARGETED_GENUINE_REGRESSION: (
        "An existing check that passed on the baseline fails on the candidate."
    ),
    REASON_TARGETED_EVIDENCE_TAMPERED: (
        "The candidate modifies the very check selected to validate it."
    ),
    REASON_ORACLE_CONFLICT_UNRESOLVED: (
        "An existing check's role against the defect probe could not be "
        "resolved, so its failure cannot be interpreted."
    ),
    REASON_ORACLE_ASSESSMENT_STALE: (
        "The existing-check role classification is bound to a different probe "
        "or check set."
    ),
    REASON_CANDIDATE_FINGERPRINT_STALE: (
        "Evidence on this payload was measured against a different candidate."
    ),
    REASON_PROBE_FINGERPRINT_STALE: (
        "Evidence on this payload was measured against a different probe."
    ),
    REASON_SOURCE_STATE_STALE: (
        "The source the candidate was localized against is no longer the source "
        "that was executed."
    ),
    REASON_TARGET_BINDING_STALE: (
        "The probe target binding no longer matches the candidate's target."
    ),
    REASON_INVALID_COMPARISON: (
        "The baseline/candidate comparison was not valid, so it establishes "
        "nothing."
    ),
    REASON_REQUIRED_EVIDENCE_MISSING: (
        "A required verification component produced no evidence at all."
    ),
    REASON_REQUIRED_EVIDENCE_INCONCLUSIVE: (
        "A required verification component reached no verdict."
    ),
    REASON_PROFILE_UNSUPPORTED: (
        "This candidate has no verification profile, so nothing about it was "
        "verified."
    ),
}
_REASON_FIX: dict[str, str] = {
    REASON_PRESERVATION_REGRESSED: (
        "Author a candidate that resolves the defect without trading away the "
        "behavior the preservation counter-case measures."
    ),
    REASON_PRIMARY_DEFECT_NOT_CLOSED: (
        "Author a candidate that actually changes the probed behavior."
    ),
    REASON_TARGETED_GENUINE_REGRESSION: (
        "Inspect the failing existing check before approving the candidate."
    ),
    REASON_CANDIDATE_FINGERPRINT_STALE: (
        "Re-run verification against the current candidate."
    ),
    REASON_PROBE_FINGERPRINT_STALE: (
        "Re-run verification against the current probe."
    ),
    REASON_SOURCE_STATE_STALE: (
        "Re-localize against the current source, then re-run verification."
    ),
}


# ── Component evaluation ─────────────────────────────────────────────────────


def _patch_safety_verdict(
    evidence: Mapping[str, Any], *, candidate: str
) -> ComponentVerdict:
    safety = _mapping(evidence.get("patch_safety"))
    if not safety:
        return ComponentVerdict(
            COMPONENT_PATCH_SAFETY,
            COMPONENT_UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            "no patch safety verdict was recorded",
        )
    bound = _sha256(safety.get("candidate_fingerprint"))
    if candidate and bound and bound != candidate:
        return ComponentVerdict(
            COMPONENT_PATCH_SAFETY,
            COMPONENT_STALE,
            REASON_CANDIDATE_FINGERPRINT_STALE,
            "patch safety describes a different candidate",
        )
    if safety.get("ok") is True:
        return ComponentVerdict(COMPONENT_PATCH_SAFETY, SUPPORTING)
    return ComponentVerdict(
        COMPONENT_PATCH_SAFETY,
        CONTRADICTING,
        REASON_PATCH_SAFETY_BLOCKED,
        "; ".join(str(item) for item in _sequence(safety.get("reasons"))),
    )


def _sandbox_verdict(
    evidence: Mapping[str, Any], *, profile: str
) -> ComponentVerdict:
    """The exact-candidate sandbox, read from whichever producer ran it.

    Both producers apply the *same* candidate with the same production plan
    primitive into a disposable managed sandbox; this reads whichever receipt
    the candidate's profile produced rather than running a third one.
    """

    if profile == PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE:
        closure = _mapping(evidence.get("candidate_defect_closure"))
        status = str(closure.get("candidate_probe_apply_status") or "")
        isolated = closure.get("sandbox_only")
        cleanup = closure.get("candidate_probe_sandbox_cleanup_ok")
        source = "candidate defect probe"
    else:
        sandbox = _mapping(evidence.get("candidate_sandbox_validation"))
        status = str(sandbox.get("sandbox_apply_status") or "")
        isolated = True if status else None
        cleanup = True if status else None
        source = "OPS.PATCH.2 candidate sandbox"

    if status in _SANDBOX_NOT_MEASURED:
        return ComponentVerdict(
            COMPONENT_EXACT_SANDBOX,
            COMPONENT_UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            f"{source} recorded no candidate application",
        )
    if status == "failed":
        return ComponentVerdict(
            COMPONENT_EXACT_SANDBOX,
            CONTRADICTING,
            REASON_SANDBOX_APPLY_FAILED,
            f"{source} could not materialize the exact candidate",
        )
    if status != "applied":
        return ComponentVerdict(
            COMPONENT_EXACT_SANDBOX,
            COMPONENT_INCONCLUSIVE,
            REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
            f"{source} reported apply status {status!r}",
        )
    if isolated is not True or cleanup is not True:
        return ComponentVerdict(
            COMPONENT_EXACT_SANDBOX,
            COMPONENT_INVALID,
            REASON_SANDBOX_NOT_ISOLATED,
            f"{source} did not report an isolated, disposed sandbox",
        )
    return ComponentVerdict(COMPONENT_EXACT_SANDBOX, SUPPORTING)


def _matrix_verdict(
    matrix: Mapping[str, Any],
    *,
    candidate: str,
    probe: str,
) -> tuple[ComponentVerdict, tuple[str, ...]]:
    """DEFECT.PROBE.LIVE.4 §18 — the matrix reduction, never one of its cases.

    Read in the same fail-closed order the producer reduced in: binding first,
    then a measured regression, then a defect case the candidate left open,
    then everything that is not a clean sweep.  The Round-8 ceiling candidate
    arrives here as ``partially_fixed`` — its primary case closed and the
    depth-variant case for the same subject invariant did not — and a status
    that is not ``fixed_and_preserved`` can never leave this function
    ``supporting``.
    """

    bound_candidate = _sha256(matrix.get("candidate_fingerprint"))
    if candidate and bound_candidate and bound_candidate != candidate:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_STALE,
                REASON_CANDIDATE_FINGERPRINT_STALE,
                "matrix evidence describes a different candidate",
            ),
            (),
        )
    bound_probe = _sha256(matrix.get("probe_fingerprint"))
    if probe and bound_probe and bound_probe != probe:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_STALE,
                REASON_PROBE_FINGERPRINT_STALE,
                "matrix evidence describes a different probe",
            ),
            (),
        )

    cases = [_mapping(item) for item in _sequence(matrix.get("cases"))]
    status = str(matrix.get("matrix_status") or "")

    # A regressed case is decisive on its own, and is read before the reduced
    # status so a receipt whose two halves disagree resolves against the
    # candidate rather than for it.
    for case in cases:
        if str(case.get("candidate_status") or "") == "regressed":
            return (
                ComponentVerdict(
                    COMPONENT_PAIRED_PROBE,
                    CONTRADICTING,
                    REASON_PRESERVATION_REGRESSED,
                    (
                        f"{case.get('case_id') or 'matrix case'}: baseline "
                        f"{case.get('baseline_observed')!r} became "
                        f"{case.get('candidate_observed')!r}"
                    ),
                ),
                (),
            )
    open_defects = [
        case
        for case in cases
        if str(case.get("role") or "")
        in {"primary_defect", "defect_generalization"}
        and str(case.get("candidate_status") or "") not in {"fixed", ""}
    ]

    if status == "fixed_but_regressive":
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                CONTRADICTING,
                REASON_PRESERVATION_REGRESSED,
                "the behavioral matrix reduced to fixed_but_regressive",
            ),
            (),
        )
    if status in _OPEN_MATRIX_STATUSES or open_defects:
        detail = ", ".join(
            str(case.get("case_id") or "") for case in open_defects
        )
        primary_closed = any(
            str(case.get("role") or "") == "primary_defect"
            and str(case.get("candidate_status") or "") == "fixed"
            for case in cases
        )
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                CONTRADICTING,
                (
                    REASON_SUBJECT_INVARIANT_NOT_CLOSED
                    if primary_closed
                    else REASON_PRIMARY_DEFECT_NOT_CLOSED
                ),
                (
                    f"behavioral matrix {status or 'open'}; unclosed defect "
                    f"cases: {detail or 'unreported'}"
                ),
            ),
            (),
        )
    if status == "unavailable":
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_UNAVAILABLE,
                REASON_REQUIRED_EVIDENCE_MISSING,
                "the behavioral matrix could not be executed",
            ),
            (),
        )
    if status not in _CLOSING_MATRIX_STATUSES:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_INCONCLUSIVE,
                REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
                f"behavioral matrix status {status!r}",
            ),
            (),
        )
    limitations: list[str] = []
    if not any(
        str(case.get("candidate_status") or "") == "preserved" for case in cases
    ):
        limitations.append(LIMITATION_NO_PRESERVATION_ORACLE)
    return ComponentVerdict(COMPONENT_PAIRED_PROBE, SUPPORTING), tuple(limitations)


def _paired_probe_verdict(
    evidence: Mapping[str, Any],
    *,
    candidate: str,
    probe: str,
) -> tuple[ComponentVerdict, tuple[str, ...]]:
    """§18 — the paired result, never the primary case alone.

    DEFECT.PROBE.LIVE.4 §18: where a bounded behavioral matrix was measured for
    this exact candidate, its reduction is authoritative and the paired reading
    below is not consulted — a matrix that rejects may not be overruled by the
    two cases it contains.  Every subject without a matrix keeps DEFECT.PROBE
    .LIVE.3's paired semantics unchanged, and a receipt written before LIVE.4
    existed carries no matrix at all, so it is read exactly as it always was.
    """

    closure = _mapping(evidence.get("candidate_defect_closure"))
    limitations: list[str] = []
    if not closure or not closure.get("defect_closure_status"):
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_UNAVAILABLE,
                REASON_REQUIRED_EVIDENCE_MISSING,
                "no candidate defect closure receipt was recorded",
            ),
            (),
        )

    bound_candidate = _sha256(closure.get("candidate_fingerprint"))
    if candidate and bound_candidate and bound_candidate != candidate:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_STALE,
                REASON_CANDIDATE_FINGERPRINT_STALE,
                "closure evidence describes a different candidate",
            ),
            (),
        )
    bound_probe = _sha256(closure.get("probe_fingerprint"))
    if probe and bound_probe and bound_probe != probe:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_STALE,
                REASON_PROBE_FINGERPRINT_STALE,
                "closure evidence describes a different probe",
            ),
            (),
        )

    matrix = _mapping(closure.get("behavioral_matrix"))
    if _sequence(matrix.get("cases")):
        return _matrix_verdict(matrix, candidate=candidate, probe=probe)
    limitations.append(LIMITATION_NO_BEHAVIORAL_MATRIX)

    # A regressed preservation case is decisive on its own.  It is read before
    # the closed paired status so that a receipt whose statuses disagree can
    # never resolve in the permissive direction.
    for case in _sequence(closure.get("preservation_cases")):
        item = _mapping(case)
        if str(item.get("status") or "") == "regressed":
            return (
                ComponentVerdict(
                    COMPONENT_PAIRED_PROBE,
                    CONTRADICTING,
                    REASON_PRESERVATION_REGRESSED,
                    (
                        f"{item.get('case_id') or 'preservation case'}: baseline "
                        f"{item.get('baseline_observed')!r} became "
                        f"{item.get('candidate_observed')!r}"
                    ),
                ),
                (),
            )

    paired = str(closure.get("paired_status") or "")
    status = str(closure.get("defect_closure_status") or "")
    effective = paired or status
    if effective == "fixed_but_regressive":
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                CONTRADICTING,
                REASON_PRESERVATION_REGRESSED,
                "the paired oracle downgraded closure to fixed_but_regressive",
            ),
            (),
        )
    if effective in _PRIMARY_OPEN_PAIRED_STATUSES:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                CONTRADICTING,
                REASON_PRIMARY_DEFECT_NOT_CLOSED,
                f"paired probe status {effective!r}",
            ),
            (),
        )
    if effective == "invalid_comparison":
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_INVALID,
                REASON_INVALID_COMPARISON,
                "the baseline/candidate comparison was refused as invalid",
            ),
            (),
        )
    if effective in {"inconclusive", ""}:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_INCONCLUSIVE,
                REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
                "the paired probe reached no verdict",
            ),
            (),
        )
    if effective == "unavailable":
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_UNAVAILABLE,
                REASON_REQUIRED_EVIDENCE_MISSING,
                "the paired probe could not be executed",
            ),
            (),
        )
    if effective not in _CLOSING_PAIRED_STATUSES:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_INCONCLUSIVE,
                REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
                f"unrecognized paired probe status {effective!r}",
            ),
            (),
        )

    # A closing pair still has to agree with the single-case facts it was built
    # from; disagreement is inconsistency, not closure.
    if status not in {"fixed", "fixed_and_preserved"} or str(
        closure.get("post_probe_result") or ""
    ) not in {"not_reproduced", ""}:
        return (
            ComponentVerdict(
                COMPONENT_PAIRED_PROBE,
                COMPONENT_INVALID,
                REASON_INVALID_COMPARISON,
                "paired status and closure status disagree",
            ),
            (),
        )
    if str(closure.get("preservation_oracle_status") or "") != "available":
        limitations.append(LIMITATION_NO_PRESERVATION_ORACLE)
    return ComponentVerdict(COMPONENT_PAIRED_PROBE, SUPPORTING), tuple(limitations)


def _failing_check_roles(evidence: Mapping[str, Any]) -> tuple[set[str], bool]:
    """Roles of the checks VALIDATE.ORACLE saw fail, and whether it is current."""

    oracle = _mapping(evidence.get("oracle_assessment"))
    current = str(oracle.get("check_oracle_assessment_status") or "") == "current"
    roles: set[str] = set()
    for item in _sequence(oracle.get("check_oracle_assessments")):
        assessment = _mapping(item)
        if str(assessment.get("candidate_result") or "") == "failed":
            roles.add(str(assessment.get("oracle_role") or ""))
    return roles, current


def _targeted_verdict(
    evidence: Mapping[str, Any], *, candidate: str
) -> tuple[ComponentVerdict, tuple[str, ...]]:
    targeted = _mapping(evidence.get("targeted_validation"))
    status = str(targeted.get("targeted_validation_status") or "")
    category = str(targeted.get("targeted_validation_category") or "")
    if not status:
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_UNAVAILABLE,
                REASON_REQUIRED_EVIDENCE_MISSING,
                "targeted validation did not run",
            ),
            (),
        )
    bound = _sha256(targeted.get("candidate_fingerprint"))
    if candidate and bound and bound != candidate:
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_STALE,
                REASON_CANDIDATE_FINGERPRINT_STALE,
                "targeted validation describes a different candidate",
            ),
            (),
        )
    if category in _TAMPERED_TARGETED_CATEGORIES:
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_INVALID,
                REASON_TARGETED_EVIDENCE_TAMPERED,
                category,
            ),
            (),
        )
    if category in _STALE_TARGETED_CATEGORIES:
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_STALE,
                REASON_CANDIDATE_FINGERPRINT_STALE,
                category,
            ),
            (),
        )
    if status == "passed":
        return ComponentVerdict(COMPONENT_TARGETED_VALIDATION, SUPPORTING), ()
    if status == "failed":
        roles, current = _failing_check_roles(evidence)
        if not current or not roles:
            return (
                ComponentVerdict(
                    COMPONENT_TARGETED_VALIDATION,
                    CONTRADICTING,
                    REASON_TARGETED_GENUINE_REGRESSION,
                    "a selected existing check failed on the candidate",
                ),
                (),
            )
        if roles - {_PRESERVATION_ORACLE_ROLE}:
            reason = (
                REASON_ORACLE_CONFLICT_UNRESOLVED
                if roles & {_UNRESOLVED_CONFLICT_ROLE}
                else REASON_TARGETED_GENUINE_REGRESSION
            )
            return (
                ComponentVerdict(
                    COMPONENT_TARGETED_VALIDATION,
                    CONTRADICTING,
                    reason,
                    "failing check roles: " + ", ".join(sorted(roles)),
                ),
                (),
            )
        # Every failing check is an existing test that asserts the defect.
        # That is a conflict for EXEC.POLICY to accept or refuse; verification
        # records it as unresolved rather than resolving it a second time.
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_INCONCLUSIVE,
                REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
                "every failing check asserts the defect being repaired",
            ),
            (),
        )
    if category == "no_relevant_existing_checks":
        # A *completed* selection whose finding is that nothing existing covers
        # this target.  Recorded as an accepted limitation so it is visible, and
        # it never supports the candidate on its own.
        return (
            ComponentVerdict(
                COMPONENT_TARGETED_VALIDATION,
                COMPONENT_NOT_APPLICABLE,
                "",
                "no existing check is structurally related to the target",
            ),
            (LIMITATION_NO_RELEVANT_EXISTING_CHECKS,),
        )
    return (
        ComponentVerdict(
            COMPONENT_TARGETED_VALIDATION,
            COMPONENT_INCONCLUSIVE,
            REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
            category or status,
        ),
        (),
    )


def _oracle_verdict(
    evidence: Mapping[str, Any],
    *,
    candidate: str,
    targeted: ComponentVerdict,
) -> ComponentVerdict:
    oracle = _mapping(evidence.get("oracle_assessment"))
    status = str(oracle.get("check_oracle_assessment_status") or "")
    if not status:
        if targeted.verdict in {COMPONENT_UNAVAILABLE, COMPONENT_NOT_APPLICABLE}:
            return ComponentVerdict(
                COMPONENT_ORACLE_ASSESSMENT,
                COMPONENT_NOT_APPLICABLE,
                "",
                "there was no selected check set to classify",
            )
        return ComponentVerdict(
            COMPONENT_ORACLE_ASSESSMENT,
            COMPONENT_UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            "existing-check role classification did not run",
        )
    bound = _sha256(oracle.get("check_oracle_candidate_fingerprint"))
    if candidate and bound and bound != candidate:
        return ComponentVerdict(
            COMPONENT_ORACLE_ASSESSMENT,
            COMPONENT_STALE,
            REASON_CANDIDATE_FINGERPRINT_STALE,
            "oracle assessment describes a different candidate",
        )
    if status == "current":
        counts = _mapping(oracle.get("check_oracle_role_counts"))
        if int(counts.get(_UNRESOLVED_CONFLICT_ROLE) or 0) > 0:
            return ComponentVerdict(
                COMPONENT_ORACLE_ASSESSMENT,
                CONTRADICTING,
                REASON_ORACLE_CONFLICT_UNRESOLVED,
                "an existing check's role against the probe is unresolved",
            )
        return ComponentVerdict(COMPONENT_ORACLE_ASSESSMENT, SUPPORTING)
    if status == "candidate_modified_check":
        return ComponentVerdict(
            COMPONENT_ORACLE_ASSESSMENT,
            COMPONENT_INVALID,
            REASON_TARGETED_EVIDENCE_TAMPERED,
            status,
        )
    if status in {"stale_probe", "stale_check"}:
        return ComponentVerdict(
            COMPONENT_ORACLE_ASSESSMENT,
            COMPONENT_STALE,
            REASON_ORACLE_ASSESSMENT_STALE,
            status,
        )
    return ComponentVerdict(
        COMPONENT_ORACLE_ASSESSMENT,
        COMPONENT_UNAVAILABLE,
        REASON_REQUIRED_EVIDENCE_MISSING,
        status,
    )


def _source_freshness_verdict(evidence: Mapping[str, Any]) -> ComponentVerdict | None:
    """§14 — the source that was executed must be the source that was localized.

    Reuses the DEFECT.PROBE.LIVE.1 receipt's own two digests rather than
    re-hashing anything here, so "fresh" means exactly what the probe already
    meant by it.
    """

    pre = _mapping(evidence.get("pre_probe"))
    if not pre:
        return None
    binding = _mapping(pre.get("target_binding"))
    executed = _sha256(pre.get("executed_source_sha256"))
    localized = _sha256(binding.get("localized_source_sha256"))
    if not executed or not localized:
        return None
    if executed != localized:
        return ComponentVerdict(
            COMPONENT_PAIRED_PROBE,
            COMPONENT_STALE,
            REASON_SOURCE_STATE_STALE,
            "the probed source is not the localized source",
        )
    return None


def _target_binding_verdict(evidence: Mapping[str, Any]) -> ComponentVerdict | None:
    """§14 — the candidate must target the file the probe is bound to."""

    pre = _mapping(evidence.get("pre_probe"))
    binding = _mapping(pre.get("target_binding"))
    bound_file = str(binding.get("file") or "").replace("\\", "/").strip()
    if not bound_file:
        return None
    paths = {
        str(item or "").replace("\\", "/").strip()
        for item in _sequence(evidence.get("candidate_target_paths"))
    }
    if not paths or bound_file in paths:
        return None
    return ComponentVerdict(
        COMPONENT_PAIRED_PROBE,
        COMPONENT_STALE,
        REASON_TARGET_BINDING_STALE,
        f"probe is bound to {bound_file!r}; the candidate targets {sorted(paths)!r}",
    )


# ── The reduction ────────────────────────────────────────────────────────────

#: Reduction precedence.  Integrity beats freshness, freshness beats a
#: substantive verdict — evidence we cannot trust may not be reported as a
#: finding about the candidate — and only a clean sweep reaches ``verified``.
_STATUS_PRECEDENCE: tuple[tuple[str, str], ...] = (
    (COMPONENT_INVALID, INVALID),
    (COMPONENT_STALE, STALE),
    (CONTRADICTING, REJECTED),
    (COMPONENT_UNAVAILABLE, UNAVAILABLE),
    (COMPONENT_INCONCLUSIVE, INCONCLUSIVE),
)


def verification_profile_for_basis(patch_basis: Any) -> str:
    """Map an existing typed patch basis onto a verification profile."""

    basis = str(patch_basis or "").strip()
    if basis == "grounded_defect":
        return PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE
    return PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE


def evaluate_candidate_verification(
    evidence: Mapping[str, Any],
) -> CandidateVerificationReceipt:
    """Reduce already-recorded receipts into one closed verification verdict.

    Pure.  Every input is a receipt some earlier phase already produced, and the
    result depends only on that mapping.
    """

    profile = str(evidence.get("policy_profile") or "").strip()
    if profile not in VERIFICATION_PROFILES:
        profile = verification_profile_for_basis(evidence.get("patch_basis"))
    required = REQUIRED_COMPONENTS[profile]
    candidate = _sha256(evidence.get("candidate_fingerprint"))
    pre_probe = _mapping(evidence.get("pre_probe"))
    probe = _sha256(pre_probe.get("probe_fingerprint"))
    targeted_receipt = _mapping(evidence.get("targeted_validation"))

    if not candidate:
        return CandidateVerificationReceipt(
            status=UNAVAILABLE,
            policy_profile=profile,
            candidate_fingerprint="",
            components=(),
            rejection_reasons=(REASON_CANDIDATE_MISSING,),
            timings=dict(_mapping(evidence.get("timings"))),
        )

    limitations: list[str] = []
    verdicts: dict[str, ComponentVerdict] = {}

    verdicts[COMPONENT_PATCH_SAFETY] = _patch_safety_verdict(
        evidence, candidate=candidate
    )
    verdicts[COMPONENT_EXACT_SANDBOX] = _sandbox_verdict(evidence, profile=profile)

    if COMPONENT_PAIRED_PROBE in required:
        stale = _source_freshness_verdict(evidence) or _target_binding_verdict(evidence)
        if stale is not None:
            verdicts[COMPONENT_PAIRED_PROBE] = stale
        else:
            paired, paired_limits = _paired_probe_verdict(
                evidence, candidate=candidate, probe=probe
            )
            verdicts[COMPONENT_PAIRED_PROBE] = paired
            limitations.extend(paired_limits)
    else:
        verdicts[COMPONENT_PAIRED_PROBE] = ComponentVerdict(
            COMPONENT_PAIRED_PROBE,
            COMPONENT_NOT_APPLICABLE,
            "",
            "this candidate has no grounded defect probe",
        )

    if COMPONENT_TARGETED_VALIDATION in required:
        targeted, targeted_limits = _targeted_verdict(evidence, candidate=candidate)
        limitations.extend(targeted_limits)
    else:
        targeted = ComponentVerdict(
            COMPONENT_TARGETED_VALIDATION,
            COMPONENT_NOT_APPLICABLE,
            "",
            "targeted validation is not part of this verification profile",
        )
    verdicts[COMPONENT_TARGETED_VALIDATION] = targeted

    if COMPONENT_ORACLE_ASSESSMENT in required:
        verdicts[COMPONENT_ORACLE_ASSESSMENT] = _oracle_verdict(
            evidence, candidate=candidate, targeted=targeted
        )
    else:
        verdicts[COMPONENT_ORACLE_ASSESSMENT] = ComponentVerdict(
            COMPONENT_ORACLE_ASSESSMENT,
            COMPONENT_NOT_APPLICABLE,
            "",
            "existing-check roles are not part of this verification profile",
        )

    full = _mapping(evidence.get("full_validation"))
    if (
        str(full.get("outcome") or "") == "inconclusive"
        and str(full.get("category") or "") == "validation_budget_exhausted"
    ):
        limitations.append(LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED)

    components = tuple(verdicts[name] for name in COMPONENT_IDS)
    considered = [verdicts[name] for name in required]

    status = VERIFIED
    reasons: list[str] = []
    for verdict_kind, resolved in _STATUS_PRECEDENCE:
        matching = [item for item in considered if item.verdict == verdict_kind]
        if matching:
            status = resolved
            reasons = [item.reason for item in matching if item.reason]
            break

    return CandidateVerificationReceipt(
        status=status,
        policy_profile=profile,
        candidate_fingerprint=candidate,
        components=components,
        rejection_reasons=_dedupe(reasons),
        accepted_limitations=_dedupe(limitations),
        probe_fingerprint=probe,
        targeted_check_set_fingerprint=_sha256(
            targeted_receipt.get("targeted_check_set_fingerprint")
        ),
        patch_safety_binding=_sha256(
            _mapping(evidence.get("patch_safety")).get("candidate_fingerprint")
        ),
        timings=dict(_mapping(evidence.get("timings"))),
    )


# ── Payload-side helpers ─────────────────────────────────────────────────────


def candidate_verification_status_of_payload(block: Any) -> str:
    """What a payload's stored verification says, legacy included."""

    if not isinstance(block, Mapping):
        return LEGACY_UNVERIFIED
    status = str(block.get("candidate_verification_status") or "").strip()
    return status if status in VERIFICATION_STATUSES else LEGACY_UNVERIFIED


def candidate_verification_is_current(block: Any, current_fingerprint: Any) -> bool:
    """Is a stored verification still bound to the candidate on the table?

    §14 — a refinement that rewrites the candidate changes its fingerprint, so
    the stored receipt stops matching and is stale by construction.  There is no
    path here that lets an earlier candidate's ``verified`` be reused.
    """

    if candidate_verification_status_of_payload(block) == LEGACY_UNVERIFIED:
        return False
    recorded = _sha256(
        _mapping(block).get("candidate_verification_candidate_fingerprint")
    )
    return bool(recorded) and recorded == _sha256(current_fingerprint)


def describe_candidate_verification(receipt: CandidateVerificationReceipt) -> str:
    """One operator-facing line that never reads as approval."""

    if receipt.status == VERIFIED:
        limits = (
            f" (accepted limitations: {', '.join(receipt.accepted_limitations)})"
            if receipt.accepted_limitations
            else ""
        )
        return (
            "every required available component supports this exact candidate; "
            "verification grants no execution authority" + limits
        )
    if receipt.rejection_reasons:
        return (
            "not verified — "
            + "; ".join(
                _REASON_TEXT.get(reason, reason)
                for reason in receipt.rejection_reasons
            )
        )
    return "not verified — no required component established anything"


def candidate_verification_guardrails() -> dict[str, bool]:
    """The boundaries this phase asserts about itself (§30)."""

    return {
        "verification_runs_when_mutation_is_disabled": True,
        "verification_is_read_only": True,
        "verification_grants_execution_authority": False,
        "verification_enables_auto_apply": False,
        "verification_changes_approval_semantics": False,
        "verification_changes_safe_minimal": False,
        "verification_changes_candidate_generation": False,
        "verification_changes_validation_commands": False,
        "verification_changes_validate_selector": False,
        "verification_edits_control_or_retrieval": False,
        "verification_changes_behavioral_expectation": False,
        "verification_fixes_classify_indent": False,
        "verification_calls_a_model": False,
        "verification_calls_the_network": False,
        "verification_traverses_the_repository": False,
        "verification_mutates_the_real_repository": False,
        "confidence_can_override_verification": False,
        "missing_evidence_can_become_a_pass": False,
        "primary_fixed_alone_can_verify": False,
    }


__all__ = [
    "PHASE_ID",
    "SCHEMA_VERSION",
    "PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE",
    "PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE",
    "VERIFICATION_PROFILES",
    "VERIFIED",
    "REJECTED",
    "INCONCLUSIVE",
    "UNAVAILABLE",
    "STALE",
    "INVALID",
    "VERIFICATION_STATUSES",
    "LEGACY_UNVERIFIED",
    "COMPONENT_PATCH_SAFETY",
    "COMPONENT_EXACT_SANDBOX",
    "COMPONENT_PAIRED_PROBE",
    "COMPONENT_TARGETED_VALIDATION",
    "COMPONENT_ORACLE_ASSESSMENT",
    "COMPONENT_IDS",
    "REQUIRED_COMPONENTS",
    "SUPPORTING",
    "CONTRADICTING",
    "COMPONENT_INCONCLUSIVE",
    "COMPONENT_UNAVAILABLE",
    "COMPONENT_NOT_APPLICABLE",
    "COMPONENT_STALE",
    "COMPONENT_INVALID",
    "COMPONENT_VERDICTS",
    "REJECTION_REASONS",
    "ACCEPTED_LIMITATIONS",
    "LIMITATION_NO_RELEVANT_EXISTING_CHECKS",
    "LIMITATION_FULL_VALIDATION_BUDGET_EXHAUSTED",
    "LIMITATION_NO_PRESERVATION_ORACLE",
    "LIMITATION_NO_BEHAVIORAL_MATRIX",
    "REASON_CANDIDATE_MISSING",
    "REASON_PATCH_SAFETY_BLOCKED",
    "REASON_SANDBOX_APPLY_FAILED",
    "REASON_SANDBOX_NOT_ISOLATED",
    "REASON_PRIMARY_DEFECT_NOT_CLOSED",
    "REASON_PRESERVATION_REGRESSED",
    "REASON_SUBJECT_INVARIANT_NOT_CLOSED",
    "REASON_TARGETED_GENUINE_REGRESSION",
    "REASON_TARGETED_EVIDENCE_TAMPERED",
    "REASON_ORACLE_CONFLICT_UNRESOLVED",
    "REASON_ORACLE_ASSESSMENT_STALE",
    "REASON_CANDIDATE_FINGERPRINT_STALE",
    "REASON_PROBE_FINGERPRINT_STALE",
    "REASON_SOURCE_STATE_STALE",
    "REASON_TARGET_BINDING_STALE",
    "REASON_INVALID_COMPARISON",
    "REASON_REQUIRED_EVIDENCE_MISSING",
    "REASON_REQUIRED_EVIDENCE_INCONCLUSIVE",
    "REASON_PROFILE_UNSUPPORTED",
    "ComponentVerdict",
    "CandidateVerificationReceipt",
    "verification_profile_for_basis",
    "evaluate_candidate_verification",
    "candidate_verification_status_of_payload",
    "candidate_verification_is_current",
    "describe_candidate_verification",
    "candidate_verification_guardrails",
]
