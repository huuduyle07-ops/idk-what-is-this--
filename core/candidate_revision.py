"""PATCH.AUTHOR.LIVE.1 — one verification-guided author revision, or none.

Round 8 measured the same failure four different ways.  The model authored an
inverted branch, then an exact no-op, then an exact no-op again, then a guard
that was byte-changing, structurally valid, admitted by the widened novelty
rule — and behaviorally identical to the baseline, because the branch above it
already excluded the condition it added.  Every one of those was caught.
``DEFECT.PROBE.LIVE.4`` ran four bounded cases and reported, deterministically,
that the primary case and its depth-variant generalization were still
reproduced while both preservation cases held; ``CANDIDATE.VERIFY.LIVE.1``
turned that into ``rejected / primary_defect_not_closed``.

The harness knew exactly why the candidate was wrong.  The model was never
told.

This module is that return path, and nothing else.  It builds one immutable
receipt out of evidence the run already holds, decides whether that receipt is
the kind of evidence a second authoring attempt could actually use, and renders
a deterministic revision request.  It does not call a provider, read a file,
walk a repository, run a probe, judge a candidate, or grant anything.

**What it is not.**  Not a repair loop: the budget is one call per run and the
counter lives on the receipt.  Not a reviewer, critic or debate turn: the same
authoring role is asked once more, with evidence.  Not a hint channel: the
request carries measured cases, never a technique — see
:func:`build_revision_prompt` and the closed template constants beneath it.
Not a verdict: whether the revised candidate is any good is decided by the
frozen gate/probe/verification pipeline, which Candidate₁ re-enters from the
top with no receipt of Candidate₀'s carried forward.

**Cheap rejections do not buy a model call.**  ``PATCH.MINIMAL.LIVE.1`` already
answers an exact no-op precisely — the model proposed no mutation — and a
``safe_minimal`` rejection, a sandbox apply failure, a stale fingerprint or a
malformed patch are all deterministic facts about the candidate's *form*.
Spending a provider call to negotiate around any of them would make the trigger
mean "something went wrong" instead of "the verifier produced behavioral
counterevidence".  Only the latter is eligible here.

Stdlib only.  The vocabularies of the producers this module reduces are
mirrored as literals rather than imported, for the reason
``core.candidate_verification`` gives: a reducer must not import a producer to
learn what its own field means.  Equality with the real vocabularies is proved
by test.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, replace
from typing import Any, Mapping, Sequence

from core.json_utils import extract_json_block
from core.author_escalation_admission import admit_author_escalation
from core.patch_authoring_contract import PatchAuthoringContract


PHASE_ID = "PATCH.AUTHOR.LIVE.1"
SCHEMA_VERSION = "candidate_revision_live_1_v1"

#: §2/§37 — the whole budget.  There is no configuration knob: a second
#: revision would be a repair loop, which is the thing this phase is not.
MAX_REVISION_CALLS_PER_RUN = 1


# ── Trigger vocabulary (§15, closed) ──────────────────────────────────────────
TRIGGER_NONE = "none"
#: The only trigger.  Deterministic behavioral counterevidence from the frozen
#: verifier, bound to this exact candidate.
TRIGGER_BEHAVIORAL_COUNTEREXAMPLE = "behavioral_counterexample"
REVISION_TRIGGERS: tuple[str, ...] = (
    TRIGGER_NONE,
    TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
)


# ── Outcome vocabulary (§40, closed) ──────────────────────────────────────────
OUTCOME_NOT_ELIGIBLE = "not_eligible"
OUTCOME_REVISED_CANDIDATE_PRODUCED = "revised_candidate_produced"
OUTCOME_REVISION_OUTPUT_INVALID = "revision_output_invalid"
OUTCOME_REVISED_CANDIDATE_REJECTED = "revised_candidate_rejected"
OUTCOME_REVISED_CANDIDATE_VERIFIED = "revised_candidate_verified"
OUTCOME_REVISION_UNAVAILABLE = "revision_unavailable"
OUTCOME_STALE = "stale"
REVISION_OUTCOMES: tuple[str, ...] = (
    OUTCOME_NOT_ELIGIBLE,
    OUTCOME_REVISED_CANDIDATE_PRODUCED,
    OUTCOME_REVISION_OUTPUT_INVALID,
    OUTCOME_REVISED_CANDIDATE_REJECTED,
    OUTCOME_REVISED_CANDIDATE_VERIFIED,
    OUTCOME_REVISION_UNAVAILABLE,
    OUTCOME_STALE,
)

#: Outcomes that mean the single provider opportunity was spent.
OUTCOMES_CONSUMING_THE_BUDGET: frozenset[str] = frozenset(
    {
        OUTCOME_REVISED_CANDIDATE_PRODUCED,
        OUTCOME_REVISION_OUTPUT_INVALID,
        OUTCOME_REVISED_CANDIDATE_REJECTED,
        OUTCOME_REVISED_CANDIDATE_VERIFIED,
        OUTCOME_REVISION_UNAVAILABLE,
    }
)


# ── Ineligibility vocabulary (§4, closed) ─────────────────────────────────────
INELIGIBLE_ROUTE_NOT_DEFECT_REPAIR = "route_is_not_defect_repair"
INELIGIBLE_PATCH_BASIS_NOT_GROUNDED = "patch_basis_is_not_grounded_defect"
INELIGIBLE_NO_CANDIDATE = "no_candidate_was_authored"
INELIGIBLE_CANDIDATE_NO_OP = "candidate_was_an_exact_no_op"
INELIGIBLE_CANDIDATE_EFFECT_NOT_MUTATING = "candidate_effect_is_not_mutating"
INELIGIBLE_SAFE_MINIMAL_REJECTED = "safe_minimal_rejected_the_candidate"
INELIGIBLE_PATCH_SAFETY_BLOCKED = "patch_safety_blocked_the_candidate"
INELIGIBLE_SANDBOX_APPLY_FAILED = "candidate_sandbox_apply_did_not_succeed"
INELIGIBLE_BASELINE_NOT_REPRODUCED = "baseline_defect_was_not_reproduced"
INELIGIBLE_TARGET_BINDING_UNAVAILABLE = "target_binding_is_not_current_and_exact"
INELIGIBLE_ORIGINAL_SOURCE_UNAVAILABLE = "authoritative_original_source_unavailable"
INELIGIBLE_TASK_UNAVAILABLE = "preserved_task_is_unavailable"
INELIGIBLE_CANDIDATE_FINGERPRINT_STALE = "candidate_fingerprint_is_stale"
INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE = "no_deterministic_behavioral_counterevidence"
INELIGIBLE_CANDIDATE_VERIFIED = "candidate_verification_did_not_reject"
INELIGIBLE_BUDGET_CONSUMED = "revision_budget_already_consumed"
INELIGIBLE_REASONS: tuple[str, ...] = (
    INELIGIBLE_ROUTE_NOT_DEFECT_REPAIR,
    INELIGIBLE_PATCH_BASIS_NOT_GROUNDED,
    INELIGIBLE_NO_CANDIDATE,
    INELIGIBLE_CANDIDATE_NO_OP,
    INELIGIBLE_CANDIDATE_EFFECT_NOT_MUTATING,
    INELIGIBLE_SAFE_MINIMAL_REJECTED,
    INELIGIBLE_PATCH_SAFETY_BLOCKED,
    INELIGIBLE_SANDBOX_APPLY_FAILED,
    INELIGIBLE_BASELINE_NOT_REPRODUCED,
    INELIGIBLE_TARGET_BINDING_UNAVAILABLE,
    INELIGIBLE_ORIGINAL_SOURCE_UNAVAILABLE,
    INELIGIBLE_TASK_UNAVAILABLE,
    INELIGIBLE_CANDIDATE_FINGERPRINT_STALE,
    INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE,
    INELIGIBLE_CANDIDATE_VERIFIED,
    INELIGIBLE_BUDGET_CONSUMED,
)


# ── Revision-output rejection vocabulary (§20, closed) ────────────────────────
OUTPUT_NO_RESPONSE = "revision_provider_returned_nothing"
OUTPUT_PROVIDER_ERROR = "revision_provider_reported_an_error"
OUTPUT_NO_JSON_PAYLOAD = "revision_output_carried_no_json_payload"
OUTPUT_NO_PATCH_CANDIDATE = "revision_output_carried_no_patch_candidate"
OUTPUT_NO_PATCHED_SNIPPET = "revision_candidate_has_no_patched_snippet"
OUTPUT_NO_TARGET_SNIPPET = "revision_candidate_has_no_target_snippet"
OUTPUT_WRONG_TARGET_FILE = "revision_candidate_names_a_different_file"
OUTPUT_WRONG_TARGET_SYMBOL = "revision_candidate_names_a_different_symbol"
OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE = "revision_candidate_is_not_based_on_the_original_source"
OUTPUT_AUTHOR_ESCALATION = "revision_author_escalation_quarantined"
from core.candidate_replacement_span import SPAN_REJECTION_REASONS

OUTPUT_REJECTION_REASONS: tuple[str, ...] = (
    *SPAN_REJECTION_REASONS,
    OUTPUT_NO_RESPONSE,
    OUTPUT_PROVIDER_ERROR,
    OUTPUT_NO_JSON_PAYLOAD,
    OUTPUT_NO_PATCH_CANDIDATE,
    OUTPUT_NO_PATCHED_SNIPPET,
    OUTPUT_NO_TARGET_SNIPPET,
    OUTPUT_WRONG_TARGET_FILE,
    OUTPUT_WRONG_TARGET_SYMBOL,
    OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE,
    OUTPUT_AUTHOR_ESCALATION,
)

#: §45 — a provider that never answered is infrastructure, not a bad candidate.
#: It still consumes the single opportunity, because retrying is a loop.
OUTPUT_UNAVAILABLE_REASONS: frozenset[str] = frozenset(
    {OUTPUT_NO_RESPONSE, OUTPUT_PROVIDER_ERROR}
)


# ── Mirrored producer vocabularies (proved equal by test) ─────────────────────
#: DEFECT.PROBE.LIVE.4 matrix statuses that carry usable counterevidence: the
#: matrix ran, it reached a verdict, and that verdict contradicts the candidate.
ELIGIBLE_MATRIX_STATUSES: frozenset[str] = frozenset(
    {
        "still_reproduced",
        "partially_fixed",
        "fixed_but_regressive",
        "unresolved_matrix_failure",
    }
)
#: The one matrix status that closes.  Present so "not eligible because it
#: passed" is expressible without importing the producer.
CLOSING_MATRIX_STATUS = "fixed_and_preserved"

#: CANDIDATE.VERIFY.LIVE.1 rejection reasons that are statements about measured
#: behavior.  Every other reason it can emit is about form, freshness or
#: evidence availability, and none of those is something a rewrite can answer.
BEHAVIORAL_REJECTION_REASONS: frozenset[str] = frozenset(
    {
        "primary_defect_not_closed",
        "behavior_preservation_regressed",
        "subject_invariant_not_closed",
    }
)

#: DEFECT.PROBE.LIVE.4 case roles, and the two families they split into.
ROLE_PRIMARY_DEFECT = "primary_defect"
ROLE_DEFECT_GENERALIZATION = "defect_generalization"
ROLE_PRESERVATION = "preservation"
ROLE_PRESERVATION_GENERALIZATION = "preservation_generalization"
CASE_ROLES: tuple[str, ...] = (
    ROLE_PRIMARY_DEFECT,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
)
DEFECT_ROLES: frozenset[str] = frozenset(
    {ROLE_PRIMARY_DEFECT, ROLE_DEFECT_GENERALIZATION}
)
PRESERVATION_ROLES: frozenset[str] = frozenset(
    {ROLE_PRESERVATION, ROLE_PRESERVATION_GENERALIZATION}
)

#: The provenance that means "the user said this".  §8's hard boundary: a
#: system-derived case may never be dressed in it.
PROVENANCE_EXPLICIT_USER = "explicit_user_fact"

#: Per-case candidate verdicts that are counterexamples, and those that are
#: constraints the revision has to keep satisfying.
FAILED_CASE_STATUSES: frozenset[str] = frozenset(
    {"still_reproduced", "changed_but_unresolved", "regressed"}
)
PRESERVED_CASE_STATUSES: frozenset[str] = frozenset({"fixed", "preserved"})

#: OPS.PATCH.2 / DEFECT.PROBE.LIVE.2 apply status that means the sandbox
#: actually materialized the candidate.
APPLY_APPLIED = "applied"

#: PATCH.MINIMAL.LIVE.1 effect status a revision-eligible candidate must carry.
EFFECT_MUTATING = "mutating"
EFFECT_NO_OP = "no_op"


# ── Bounds (§13) ──────────────────────────────────────────────────────────────
MAX_COUNTEREXAMPLE_CASES = 8
MAX_PRESERVED_CASES = 8
MAX_CONCRETE_CASES = 8
MAX_CONCRETE_INPUT_BYTES = 16_384
MAX_SNIPPET_CHARS = 20_000
MAX_TASK_CHARS = 8_000
MAX_OBSERVED_CHARS = 512
MAX_IDENTIFIER_CHARS = 512


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def _fingerprint(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _text(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, (list, tuple)):
        return value
    return ()


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit]


def _scalar(value: Any) -> Any:
    """One bounded machine fact, never an object graph."""

    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _clip(str(value), MAX_OBSERVED_CHARS)


# ══════════════════════════════════════════════════════════════════════════════
# §7 — the failed / preserved case shape
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RevisionCounterexample:
    """One measured case, reduced to bounded machine facts and nothing more.

    There is no field for prose, for a suggestion, or for why the harness
    thinks the case failed.  What the case expected, what the candidate did,
    and what the frozen oracle called that: three facts the model can act on
    without being told how.
    """

    case_id: str
    role: str
    provenance: str
    expected: Any
    candidate_observed: Any
    status: str
    input_language: str = ""
    input_text: str | None = None
    case_probe_fingerprint: str = ""

    def __post_init__(self) -> None:
        if self.input_text is not None and (
            not isinstance(self.input_text, str)
            or len(self.input_text.encode("utf-8")) > MAX_CONCRETE_INPUT_BYTES
            or not _SHA256_RE.fullmatch(self.case_probe_fingerprint)
        ):
            raise ValueError("concrete input requires bounded executed probe identity")
        if self.role not in CASE_ROLES:
            raise ValueError(f"unsupported case role: {self.role!r}")
        if self.role != ROLE_PRIMARY_DEFECT and (
            self.provenance == PROVENANCE_EXPLICIT_USER
        ):
            # §8 — the user said one thing, and it is the primary case.  A
            # system-derived generalization may not borrow their authority on
            # its way into a prompt.
            raise ValueError(
                "only the primary case may carry explicit user provenance"
            )

    @property
    def is_failure(self) -> bool:
        return self.status in FAILED_CASE_STATUSES

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "role": self.role,
            "provenance": self.provenance,
            "expected": self.expected,
            "candidate_observed": self.candidate_observed,
            "status": self.status,
            **({"input_language": self.input_language, "input_text": self.input_text,
                "case_probe_fingerprint": self.case_probe_fingerprint}
               if self.input_text is not None else {}),
        }


def _counterexample_from_case(case: Any) -> RevisionCounterexample | None:
    """Read one DEFECT.PROBE.LIVE.4 case dict into the bounded shape."""

    data = _mapping(case)
    case_id = _clip(_text(data.get("case_id")), MAX_IDENTIFIER_CHARS)
    role = _text(data.get("role"))
    status = _text(data.get("candidate_status"))
    if not case_id or role not in CASE_ROLES or not status:
        return None
    provenance = _clip(_text(data.get("provenance")), MAX_IDENTIFIER_CHARS)
    try:
        return RevisionCounterexample(
            case_id=case_id,
            role=role,
            provenance=provenance,
            expected=_scalar(data.get("expected")),
            candidate_observed=_scalar(data.get("candidate_observed")),
            status=status,
            input_language=_clip(_text(data.get("input_language")), MAX_IDENTIFIER_CHARS),
            input_text=data.get("input_text"),
            case_probe_fingerprint=_text(data.get("case_probe_fingerprint")),
        )
    except ValueError:
        # A case that claims user provenance for a system-derived role is
        # discarded rather than laundered.  Losing it can only make the
        # evidence smaller, never wrong.
        return None


# ══════════════════════════════════════════════════════════════════════════════
# §6 — the immutable revision evidence receipt
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CandidateRevisionEvidence:
    """Everything the one revision request is allowed to know.

    Assembled entirely from receipts the run already produced.  Nothing here is
    fetched, re-measured or inferred, and every string on it is either the
    user's own text, authoritative repository bytes the run already held, the
    rejected candidate's own bytes, or a closed-vocabulary token.
    """

    preserved_task: str
    task_fingerprint: str
    target_file: str
    target_symbol: str
    original_source: str
    original_source_digest: str
    rejected_candidate_fingerprint: str
    rejected_target_snippet: str
    rejected_patched_snippet: str
    verification_status: str
    verification_rejection_reasons: tuple[str, ...]
    matrix_status: str
    failed_cases: tuple[RevisionCounterexample, ...]
    preserved_cases: tuple[RevisionCounterexample, ...]
    probe_fingerprint: str = ""
    matrix_evidence_fingerprint: str = ""
    run_identity: str = ""
    trigger: str = TRIGGER_BEHAVIORAL_COUNTEREXAMPLE
    phase_id: str = PHASE_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.trigger not in REVISION_TRIGGERS:
            raise ValueError(f"unsupported revision trigger: {self.trigger!r}")
        cases = self.failed_cases + self.preserved_cases
        if len(cases) > MAX_CONCRETE_CASES or self.concrete_counterexample_bytes > MAX_CONCRETE_INPUT_BYTES:
            raise ValueError("revision concrete evidence exceeds its bounds")
        if not self.failed_cases:
            raise ValueError("revision evidence requires at least one failed case")
        if not self.original_source:
            raise ValueError("revision evidence requires the original source")
        if not self.preserved_task:
            raise ValueError("revision evidence requires the preserved task")

    @property
    def counterexample_count(self) -> int:
        return len(self.failed_cases)

    @property
    def concrete_counterexample_count(self) -> int:
        return sum(case.input_text is not None for case in self.failed_cases + self.preserved_cases)

    @property
    def concrete_counterexample_bytes(self) -> int:
        return sum(len(case.input_text.encode("utf-8")) for case in self.failed_cases + self.preserved_cases
                   if case.input_text is not None)

    @property
    def evidence_fingerprint(self) -> str:
        return _fingerprint(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "schema_version": self.schema_version,
            "trigger": self.trigger,
            "task_fingerprint": self.task_fingerprint,
            "target_file": self.target_file,
            "target_symbol": self.target_symbol,
            "original_source_digest": self.original_source_digest,
            "rejected_candidate_fingerprint": self.rejected_candidate_fingerprint,
            "probe_fingerprint": self.probe_fingerprint,
            "matrix_evidence_fingerprint": self.matrix_evidence_fingerprint,
            "run_identity": self.run_identity,
            "verification_status": self.verification_status,
            "verification_rejection_reasons": list(self.verification_rejection_reasons),
            "matrix_status": self.matrix_status,
            "failed_cases": [case.as_dict() for case in self.failed_cases],
            "preserved_cases": [case.as_dict() for case in self.preserved_cases],
        }


# ══════════════════════════════════════════════════════════════════════════════
# §3/§4 — eligibility
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RevisionAssessment:
    """Whether one revision call is warranted, and the evidence if it is."""

    eligible: bool
    trigger: str
    ineligible_reasons: tuple[str, ...] = ()
    evidence: CandidateRevisionEvidence | None = None

    def __post_init__(self) -> None:
        if self.trigger not in REVISION_TRIGGERS:
            raise ValueError(f"unsupported revision trigger: {self.trigger!r}")
        unknown = set(self.ineligible_reasons) - set(INELIGIBLE_REASONS)
        if unknown:
            raise ValueError(f"unknown ineligibility reasons: {sorted(unknown)!r}")
        if self.eligible and self.evidence is None:
            raise ValueError("an eligible assessment must carry its evidence")
        if self.eligible and self.ineligible_reasons:
            raise ValueError("an eligible assessment may not carry a refusal")
        if not self.eligible and self.evidence is not None:
            raise ValueError("an ineligible assessment may not carry evidence")


def _ineligible(*reasons: str) -> RevisionAssessment:
    ordered: list[str] = []
    for reason in reasons:
        if reason and reason not in ordered:
            ordered.append(reason)
    return RevisionAssessment(
        eligible=False, trigger=TRIGGER_NONE, ineligible_reasons=tuple(ordered)
    )


def assess_candidate_revision(evidence: Mapping[str, Any]) -> RevisionAssessment:
    """The whole eligibility rule, as one pure reduction over live receipts.

    The order below is deliberate and cheap-first.  Route, basis and candidate
    presence are one lookup each; the behavioral question is asked last, so a
    payload that never got as far as a measurement is refused without anyone
    having to reason about matrix statuses.
    """

    attempts = evidence.get("revision_attempts_already_made")
    try:
        already = int(attempts or 0)
    except (TypeError, ValueError):
        already = 0
    if already >= MAX_REVISION_CALLS_PER_RUN:
        return _ineligible(INELIGIBLE_BUDGET_CONSUMED)

    route = _mapping(evidence.get("task_route"))
    if _text(route.get("selected_workflow")) != "defect_repair_patch":
        # §47/§48 — feature authoring and analysis stop here, whatever their
        # candidate looks like.
        return _ineligible(INELIGIBLE_ROUTE_NOT_DEFECT_REPAIR)

    if _text(evidence.get("patch_basis")) != "grounded_defect":
        return _ineligible(INELIGIBLE_PATCH_BASIS_NOT_GROUNDED)

    block = _mapping(evidence.get("payload"))

    # §5/§21 — an exact no-op has a precise cheap answer already.  Ask before
    # asking whether a candidate exists, because the no-op gate is what removed
    # it, and "no candidate" would otherwise hide the real reason.
    effect_status = _text(block.get("candidate_effect_status"))
    if effect_status == EFFECT_NO_OP:
        return _ineligible(INELIGIBLE_CANDIDATE_NO_OP)

    # §35 — safe_minimal's refusal is a policy statement about the candidate's
    # form.  This phase does not use a model call to negotiate with it.
    if block.get("candidate_novelty_admitted") is False:
        return _ineligible(INELIGIBLE_SAFE_MINIMAL_REJECTED)

    candidate_fingerprint = _text(evidence.get("candidate_fingerprint"))
    rejected_target = _text(evidence.get("rejected_target_snippet"))
    rejected_patched = _text(evidence.get("rejected_patched_snippet"))
    if not candidate_fingerprint or not rejected_patched:
        return _ineligible(INELIGIBLE_NO_CANDIDATE)

    if effect_status != EFFECT_MUTATING:
        # Undetermined, unmeasured or legacy.  Not a measured mutation, so not
        # a candidate whose behavior was meaningfully contradicted.
        return _ineligible(INELIGIBLE_CANDIDATE_EFFECT_NOT_MUTATING)

    if _mapping(evidence.get("patch_safety")).get("ok") is not True:
        return _ineligible(INELIGIBLE_PATCH_SAFETY_BLOCKED)

    if _text(block.get("candidate_probe_apply_status")) != APPLY_APPLIED:
        # §4 — a candidate the sandbox could not materialize was never
        # behaviorally measured, so there is no counterexample to send back.
        return _ineligible(INELIGIBLE_SANDBOX_APPLY_FAILED)

    pre_probe = _mapping(evidence.get("pre_probe"))
    if _text(pre_probe.get("probe_result")) != "reproduced":
        return _ineligible(INELIGIBLE_BASELINE_NOT_REPRODUCED)

    target_file = _text(evidence.get("target_file"))
    target_symbol = _text(evidence.get("target_symbol"))
    if not target_file or not target_symbol:
        return _ineligible(INELIGIBLE_TARGET_BINDING_UNAVAILABLE)

    original_source = _text(evidence.get("original_source"))
    if not original_source:
        return _ineligible(INELIGIBLE_ORIGINAL_SOURCE_UNAVAILABLE)

    preserved_task = _text(evidence.get("preserved_task")).strip()
    if not preserved_task:
        return _ineligible(INELIGIBLE_TASK_UNAVAILABLE)

    # §19 — the matrix and the verification must both name this exact candidate.
    matrix_fingerprint = _text(
        _mapping(block.get("behavioral_matrix")).get("candidate_fingerprint")
    ) or _text(block.get("candidate_fingerprint"))
    verification_fingerprint = _text(
        block.get("candidate_verification_candidate_fingerprint")
    )
    if matrix_fingerprint and matrix_fingerprint != candidate_fingerprint:
        return _ineligible(INELIGIBLE_CANDIDATE_FINGERPRINT_STALE)
    if verification_fingerprint and verification_fingerprint != candidate_fingerprint:
        return _ineligible(INELIGIBLE_CANDIDATE_FINGERPRINT_STALE)

    verification_status = _text(block.get("candidate_verification_status"))
    rejection_reasons = tuple(
        _text(reason)
        for reason in _sequence(block.get("candidate_verification_rejection_reasons"))
        if _text(reason)
    )
    if verification_status != "rejected":
        # §28 — verified, inconclusive, unavailable, stale and invalid all stop
        # here.  Only a rejection carries a contradiction to answer.
        return _ineligible(INELIGIBLE_CANDIDATE_VERIFIED)
    if not (set(rejection_reasons) & BEHAVIORAL_REJECTION_REASONS):
        return _ineligible(INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE)

    matrix_status = _text(block.get("behavioral_matrix_status"))
    if matrix_status not in ELIGIBLE_MATRIX_STATUSES:
        return _ineligible(INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE)

    # Concrete rows are the matrix receipt's own case set, not an independently
    # supplied list. Historical abstract-only evidence keeps its older shape.
    matrix = _mapping(block.get("behavioral_matrix"))
    rows = _sequence(block.get("behavioral_matrix_cases"))
    if any(_mapping(row).get("input_text") is not None for row in rows):
        if (matrix.get("cases") != rows
                or matrix.get("candidate_fingerprint") != candidate_fingerprint
                or matrix.get("probe_fingerprint") != block.get("probe_fingerprint")):
            return _ineligible(INELIGIBLE_CANDIDATE_FINGERPRINT_STALE)

    failed: list[RevisionCounterexample] = []
    preserved: list[RevisionCounterexample] = []
    for case in _sequence(block.get("behavioral_matrix_cases")):
        item = _counterexample_from_case(case)
        if item is None:
            continue
        if item.is_failure:
            if len(failed) < MAX_COUNTEREXAMPLE_CASES:
                failed.append(item)
        elif item.status in PRESERVED_CASE_STATUSES:
            if len(preserved) < MAX_PRESERVED_CASES:
                preserved.append(item)

    # At most eight selected cases, failures first. Never truncate a fixture
    # into different input: retain the abstract fact when concrete bytes do not fit.
    remaining = MAX_CONCRETE_INPUT_BYTES
    bounded = []
    for item in (failed + preserved)[:MAX_CONCRETE_CASES]:
        size = len(item.input_text.encode("utf-8")) if item.input_text is not None else 0
        if size > remaining:
            item = replace(item, input_text=None, case_probe_fingerprint="")
        else:
            remaining -= size
        bounded.append(item)
    failed = [item for item in bounded if item.is_failure]
    preserved = [item for item in bounded if not item.is_failure]

    if not failed:
        # The matrix said the candidate is open but named no failing case.  No
        # counterexample means no evidence-guided revision; the run stops with
        # the frozen rejection it already has.
        return _ineligible(INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE)

    receipt = CandidateRevisionEvidence(
        preserved_task=_clip(preserved_task, MAX_TASK_CHARS),
        task_fingerprint=_sha256(preserved_task),
        target_file=_clip(target_file, MAX_IDENTIFIER_CHARS),
        target_symbol=_clip(target_symbol, MAX_IDENTIFIER_CHARS),
        original_source=_clip(original_source, MAX_SNIPPET_CHARS),
        original_source_digest=_sha256(original_source),
        rejected_candidate_fingerprint=candidate_fingerprint,
        rejected_target_snippet=_clip(rejected_target, MAX_SNIPPET_CHARS),
        rejected_patched_snippet=_clip(rejected_patched, MAX_SNIPPET_CHARS),
        verification_status=verification_status,
        verification_rejection_reasons=rejection_reasons,
        matrix_status=matrix_status,
        failed_cases=tuple(failed),
        preserved_cases=tuple(preserved),
        probe_fingerprint=_text(block.get("probe_fingerprint")),
        matrix_evidence_fingerprint=_fingerprint(block.get("behavioral_matrix_cases")),
        run_identity=_clip(_text(evidence.get("run_identity")), MAX_IDENTIFIER_CHARS),
    )
    return RevisionAssessment(
        eligible=True,
        trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
        evidence=receipt,
    )


def revision_evidence_is_current(
    receipt: CandidateRevisionEvidence,
    *,
    candidate_fingerprint: str,
    original_source: str,
    target_file: str,
    target_symbol: str,
    preserved_task: str | None = None,
    payload: Mapping[str, Any] | None = None,
    run_identity: str | None = None,
) -> bool:
    """§19 — the receipt is valid only while everything it bound still holds."""

    if not isinstance(receipt, CandidateRevisionEvidence):
        return False
    if receipt.rejected_candidate_fingerprint != _text(candidate_fingerprint):
        return False
    if receipt.original_source_digest != _sha256(_text(original_source)):
        return False
    if receipt.target_file != _text(target_file):
        return False
    if receipt.target_symbol != _text(target_symbol):
        return False
    if receipt.run_identity and receipt.run_identity != run_identity:
        return False
    if preserved_task is not None and receipt.task_fingerprint != _sha256(preserved_task.strip()):
        return False
    if payload is not None:
        matrix = _mapping(payload.get("behavioral_matrix"))
        if (receipt.matrix_evidence_fingerprint != _fingerprint(payload.get("behavioral_matrix_cases"))
                or receipt.probe_fingerprint != _text(payload.get("probe_fingerprint"))
                or matrix.get("candidate_fingerprint") != candidate_fingerprint
                or payload.get("candidate_verification_candidate_fingerprint") != candidate_fingerprint):
            return False
    return bool(_SHA256_RE.match(receipt.original_source_digest))


# ══════════════════════════════════════════════════════════════════════════════
# §8/§12 — the deterministic revision request
# ══════════════════════════════════════════════════════════════════════════════
#
# Everything below that is not a substitution is a fixed constant, and the
# phase's own test reads these constants and asserts that none of them names a
# technique.  That is the mechanism behind "no implementation hints": there is
# no code path that can compose advice, because there is no advice to compose.

_HEADER = (
    "REVISION REQUEST. A previous candidate for this task was rejected by "
    "deterministic verification. You are being asked once for a corrected "
    "candidate."
)
_TASK_HEADING = "ORIGINAL TASK (verbatim, unchanged):"
_TARGET_HEADING = "TARGET:"
#: §14 — the revision request is stateless, so the contract travels with it.
#: This heading is this call's framing; the contract text beneath it is the
#: shared material and is byte-identical to the initial author's.
_CONTRACT_HEADING = (
    "PATCH CANDIDATE CONTRACT - authoritative, and identical to the contract "
    "the first draft was given. It is repeated in full because this request "
    "is stateless: nothing you were told in an earlier call is available to "
    "you now. Every field name in it is protocol, and a synonym is not read."
)
_SOURCE_HEADING = (
    "AUTHORITATIVE ORIGINAL SOURCE. This is the current content of the target "
    "and the base your candidate must replace:"
)
_REJECTED_HEADING = (
    "REJECTED CANDIDATE - EVIDENCE ONLY. This was executed and rejected. It is "
    "shown so you know what has already been tried. It is not the source of "
    "truth, it is not a starting point, and no part of it is known to be right."
)
_EVIDENCE_HEADING = (
    "DETERMINISTIC VERIFICATION. Each line is one case the harness executed "
    "against the rejected candidate. Each is an observed result, not an opinion."
)
_FAILED_HEADING = "Cases the rejected candidate did not satisfy:"
_PRESERVED_HEADING = (
    "Cases the rejected candidate did satisfy, which your candidate must "
    "continue to satisfy:"
)
_INSTRUCTION = (
    "INSTRUCTION. Produce one revised patch candidate, if the evidence supports "
    "a safe fix, that addresses the "
    "original task while satisfying every case listed above. Author it against "
    "the authoritative original source shown above; do not build on the "
    "rejected candidate and do not assume it was correct. Your target_snippet "
    "must come from the authoritative original source. Return exactly the JSON "
    "object the PATCH CANDIDATE CONTRACT above specifies: a top-level "
    "patch_candidate field, whose target_snippet field holds the bytes you "
    "are replacing and whose patched_snippet field holds the bytes that "
    "replace them. Those field names are the protocol and no other spelling "
    "is read. If you cannot safely author, return a null candidate with "
    "needs_escalation=true and exactly one non-none escalation_reason from "
    "the shared contract. Return that JSON object and nothing else."
)

#: Every fixed sentence the request can contain.  The hint test reads exactly
#: this tuple, so a template added later without being listed here fails.
PROMPT_TEMPLATE_CONSTANTS: tuple[str, ...] = (
    _HEADER,
    _TASK_HEADING,
    _TARGET_HEADING,
    _SOURCE_HEADING,
    _REJECTED_HEADING,
    _EVIDENCE_HEADING,
    _FAILED_HEADING,
    _PRESERVED_HEADING,
    _CONTRACT_HEADING,
    _INSTRUCTION,
)


def _render_case(case: RevisionCounterexample) -> str:
    rendered = (
        f"- case_id={case.case_id}"
        f" role={case.role}"
        f" provenance={case.provenance}"
        f" expected={case.expected!r}"
        f" observed={case.candidate_observed!r}"
        f" status={case.status}"
    )
    if case.input_text is not None:
        rendered += (
            f"\ninput_language={case.input_language}"
            f"\ncase_probe_fingerprint={case.case_probe_fingerprint}"
            f"\nINPUT ({len(case.input_text.encode('utf-8'))} UTF-8 bytes):\n"
            + case.input_text + "\nEND INPUT"
        )
    return rendered


def build_revision_prompt(
    receipt: CandidateRevisionEvidence, contract: PatchAuthoringContract, *, scope_text: str = "",
    authoring_source: str | None = None, oop_context: str = "",
) -> str:
    """§12 — the request, assembled by concatenation and nothing cleverer.

    ``contract`` is PATCH.AUTHOR.LIVE.2's correction, and it is a required
    argument rather than an optional one: this call is stateless, so a
    revision request that does not carry the authoring contract is a request
    the model cannot answer in the required shape.  Round 9 proved that
    empirically - asked to "return the normal patch-candidate JSON schema",
    a schema it had never been shown, it returned a bare
    ``target_snippet``/``replacement_snippet`` pair and its work was thrown
    away at the parser.

    The contract is rendered by ``core.patch_authoring_contract`` from the
    same accessor the initial draft uses, so the two are the same bytes.
    Everything around it - the task, the target, the source, the rejected
    bytes and the measured cases - is this call's own evidence and is
    deliberately not the initial draft's framing.
    """

    parts: list[str] = [
        _HEADER,
        "",
        _TASK_HEADING,
        receipt.preserved_task,
        "",
        _TARGET_HEADING,
        f"{receipt.target_file}::{receipt.target_symbol}",
        "",
        _CONTRACT_HEADING,
        contract.text,
        *(["", scope_text] if scope_text else []),
        *(["", oop_context] if oop_context else []),
        "",
        _SOURCE_HEADING,
        receipt.original_source if authoring_source is None else authoring_source,
        "",
        _REJECTED_HEADING,
        receipt.rejected_patched_snippet,
        "",
        _EVIDENCE_HEADING,
        f"matrix_status={receipt.matrix_status}",
        f"verification_status={receipt.verification_status}",
        "rejection_reasons=" + ",".join(receipt.verification_rejection_reasons),
        "",
        _FAILED_HEADING,
    ]
    parts.extend(_render_case(case) for case in receipt.failed_cases)
    if receipt.preserved_cases:
        parts.extend(["", _PRESERVED_HEADING])
        parts.extend(_render_case(case) for case in receipt.preserved_cases)
    parts.extend(["", _INSTRUCTION])
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════════════════
# §20 — reading the revision back
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class RevisedCandidate:
    """A revision that survived parsing, or the reason it did not."""

    accepted: bool
    rejection_reason: str = ""
    candidate: dict[str, Any] | None = None
    confidence: float | None = None
    quarantine_receipt: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.accepted and self.candidate is None:
            raise ValueError("an accepted revision must carry a candidate")
        if not self.accepted and self.rejection_reason not in OUTPUT_REJECTION_REASONS:
            raise ValueError(f"unknown output rejection: {self.rejection_reason!r}")

    @property
    def unavailable(self) -> bool:
        """§45 — the provider never answered, as opposed to answering badly."""

        return not self.accepted and self.rejection_reason in (
            OUTPUT_UNAVAILABLE_REASONS
        )


def _rejected_output(reason: str) -> RevisedCandidate:
    return RevisedCandidate(accepted=False, rejection_reason=reason)


def rebase_onto_original_source(
    *, original_source: str, target_snippet: str, patched_snippet: str
) -> tuple[str, str] | None:
    """§10/§16 — express the revision as a replacement of the ORIGINAL bytes.

    Exactly one substitution, exactly as the existing partial-body normalizer
    performs it.  A fragment that is not present in the original source is not
    rebasable and returns ``None``; in particular a fragment that exists only in
    the rejected candidate's bytes cannot be laundered into a base here.
    """

    if not original_source or not target_snippet or not patched_snippet:
        return None
    if target_snippet == original_source:
        return original_source, patched_snippet
    if original_source.count(target_snippet) != 1:
        return None
    return original_source, original_source.replace(target_snippet, patched_snippet, 1)


def parse_revised_candidate(
    response: Any, receipt: CandidateRevisionEvidence, *, authoring_context=None,
) -> RevisedCandidate:
    """Turn one provider response into Candidate₁, or refuse it outright.

    Refusal is terminal.  There is no repair prompt, no reformat request and no
    second call: §20 says an unusable revision ends the run, and the single
    opportunity is spent either way.
    """

    text = _text(response)
    if not text.strip():
        return _rejected_output(OUTPUT_NO_RESPONSE)
    if text.strip().startswith("AGENT_ERROR:"):
        return _rejected_output(OUTPUT_PROVIDER_ERROR)

    block = extract_json_block(text)
    if not isinstance(block, dict):
        return _rejected_output(OUTPUT_NO_JSON_PAYLOAD)

    admission = admit_author_escalation(block, raw_response=text)
    if not admission.admitted:
        return RevisedCandidate(
            accepted=False, rejection_reason=OUTPUT_AUTHOR_ESCALATION,
            quarantine_receipt=admission.quarantine_receipt(),
        )

    candidate = block.get("patch_candidate")
    if not isinstance(candidate, Mapping):
        return _rejected_output(OUTPUT_NO_PATCH_CANDIDATE)

    patched = _text(candidate.get("patched_snippet"))
    if not patched.strip():
        return _rejected_output(OUTPUT_NO_PATCHED_SNIPPET)
    target = _text(candidate.get("target_snippet"))
    if not target.strip():
        return _rejected_output(OUTPUT_NO_TARGET_SNIPPET)

    declared_path = _text(candidate.get("relative_path")) or _text(candidate.get("file"))
    if declared_path.replace("\\", "/").strip("/") != receipt.target_file:
        return _rejected_output(OUTPUT_WRONG_TARGET_FILE)
    declared_symbol = _text(candidate.get("target_node_name"))
    if declared_symbol and declared_symbol != receipt.target_symbol:
        return _rejected_output(OUTPUT_WRONG_TARGET_SYMBOL)

    original_source = receipt.original_source
    repair = getattr(authoring_context, "authoring_repair_scope", None)
    if repair is not None and len(repair.measured.members) > 1:
        from core.authoring_repair_scope import AuthoringScopeError
        try:
            authoring_context.revision_prompt(receipt)  # baseline and freshness proof
            repair.validate_candidate(block)
        except AuthoringScopeError as exc:
            return _rejected_output(exc.reason if exc.reason in SPAN_REJECTION_REASONS
                                    else OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE)
        except ValueError:
            return _rejected_output(OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE)
        # Preserve the exact validated pair, including supported sub-envelopes.
        # A model-selected quote is never expanded to a different candidate.
        rebased = (target, patched)
    else:
        rebased = rebase_onto_original_source(
            original_source=original_source,
            target_snippet=target,
            patched_snippet=patched,
        )
    if rebased is None:
        return _rejected_output(OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE)
    base, replacement = rebased

    # §42 — a confidence travels only when the provider actually returned one
    # in this response.  Candidate₀'s is never carried across.
    confidence: float | None = None
    raw_confidence = block.get("confidence", candidate.get("confidence"))
    if isinstance(raw_confidence, (int, float)) and not isinstance(raw_confidence, bool):
        confidence = max(0.0, min(1.0, float(raw_confidence)))

    revised = {
        "file": receipt.target_file,
        "relative_path": receipt.target_file,
        "target_node_kind": _text(candidate.get("target_node_kind")) or "function",
        "target_node_name": receipt.target_symbol,
        "target_snippet": base,
        "patched_snippet": replacement,
    }
    return RevisedCandidate(accepted=True, candidate=revised, confidence=confidence)


# ══════════════════════════════════════════════════════════════════════════════
# §15/§37/§40 — the bounded revision receipt
# ══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True, slots=True)
class CandidateRevisionReceipt:
    """Bounded control-plane telemetry for the one revision opportunity.

    No prose reasoning, no provider transcript, no chain of thought.  Sizes and
    a latency are recorded because a model call has a cost and hiding it would
    make the budget unauditable; the content of the call is not.
    """

    eligible: bool
    attempted: bool
    outcome: str
    trigger: str = TRIGGER_NONE
    attempt_count: int = 0
    ineligible_reasons: tuple[str, ...] = ()
    previous_candidate_fingerprint: str = ""
    revised_candidate_fingerprint: str = ""
    evidence_fingerprint: str = ""
    counterexample_count: int = 0
    preserved_case_count: int = 0
    output_rejection_reason: str = ""
    provider: str = ""
    model: str = ""
    author_selection: str = ""
    latency_seconds: float = 0.0
    evidence_seconds: float = 0.0
    input_chars: int = 0
    output_chars: int = 0
    revised_candidate_present: bool = False
    #: §33 — the contract the revision author was actually handed.  Empty on
    #: every receipt that spent no call, because none was rendered.
    authoring_contract_version: str = ""
    authoring_contract_fingerprint: str = ""
    revision_contract_present: bool = False
    authoring_scope_fingerprint: str = ""
    concrete_counterexample_count: int = 0
    concrete_counterexample_bytes: int = 0
    phase_id: str = PHASE_ID
    schema_version: str = SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.outcome not in REVISION_OUTCOMES:
            raise ValueError(f"unsupported revision outcome: {self.outcome!r}")
        if self.trigger not in REVISION_TRIGGERS:
            raise ValueError(f"unsupported revision trigger: {self.trigger!r}")
        unknown = set(self.ineligible_reasons) - set(INELIGIBLE_REASONS)
        if unknown:
            raise ValueError(f"unknown ineligibility reasons: {sorted(unknown)!r}")
        if self.output_rejection_reason and (
            self.output_rejection_reason not in OUTPUT_REJECTION_REASONS
        ):
            raise ValueError(
                f"unknown output rejection: {self.output_rejection_reason!r}"
            )
        if self.attempt_count > MAX_REVISION_CALLS_PER_RUN:
            raise ValueError("more than one verification-guided revision call")
        if self.attempted and self.attempt_count != 1:
            raise ValueError("an attempted revision consumed exactly one call")
        if not self.attempted and self.attempt_count:
            raise ValueError("an unattempted revision consumed no call")

    @property
    def model_call_budget_consumed(self) -> int:
        return self.attempt_count

    @property
    def model_call_budget_remaining(self) -> int:
        return MAX_REVISION_CALLS_PER_RUN - self.attempt_count

    @property
    def needs_escalation(self) -> bool:
        """§2/§20/§31 — anything short of a verified revision goes to a human."""

        if not self.attempted:
            return False
        return self.outcome != OUTCOME_REVISED_CANDIDATE_VERIFIED

    @property
    def execution_authorized(self) -> bool:
        """§26 — never.  A revision is authorship, not authority."""

        return False

    @property
    def final_repository_changed(self) -> bool:
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "schema_version": self.schema_version,
            "eligible": self.eligible,
            "attempted": self.attempted,
            "trigger": self.trigger,
            "attempt_count": self.attempt_count,
            "outcome": self.outcome,
            "ineligible_reasons": list(self.ineligible_reasons),
            "previous_candidate_fingerprint": self.previous_candidate_fingerprint,
            "revised_candidate_fingerprint": self.revised_candidate_fingerprint,
            "evidence_fingerprint": self.evidence_fingerprint,
            "counterexample_count": self.counterexample_count,
            "preserved_case_count": self.preserved_case_count,
            "output_rejection_reason": self.output_rejection_reason,
            "provider": self.provider,
            "model": self.model,
            "author_selection": self.author_selection,
            "latency_seconds": self.latency_seconds,
            "evidence_seconds": self.evidence_seconds,
            "input_chars": self.input_chars,
            "output_chars": self.output_chars,
            "revised_candidate_present": self.revised_candidate_present,
            "model_call_budget_consumed": self.model_call_budget_consumed,
            "model_call_budget_remaining": self.model_call_budget_remaining,
            "authority_effect": "none",
            "execution_authorized": self.execution_authorized,
            "final_repository_changed": self.final_repository_changed,
            # PATCH.AUTHOR.LIVE.2 §33 — which contract the author was held
            # to, by identity rather than by repeating its text.  Deliberately
            # not flattened alongside: §34 records that this receipt is
            # already duplicated into the payload, and three more duplicated
            # keys would make that worse.
            "authoring_contract_version": self.authoring_contract_version,
            "authoring_contract_fingerprint": self.authoring_contract_fingerprint,
            "revision_contract_present": self.revision_contract_present,
            "authoring_scope_fingerprint": self.authoring_scope_fingerprint,
            "concrete_counterexample_count": self.concrete_counterexample_count,
            "concrete_counterexample_bytes": self.concrete_counterexample_bytes,
        }

    def as_telemetry(self) -> dict[str, Any]:
        return {
            "candidate_revision_phase_id": self.phase_id,
            "candidate_revision_schema_version": self.schema_version,
            "candidate_revision_eligible": self.eligible,
            "candidate_revision_attempted": self.attempted,
            "candidate_revision_trigger": self.trigger,
            "candidate_revision_attempt_count": self.attempt_count,
            "candidate_revision_outcome": self.outcome,
            "candidate_revision_ineligible_reasons": list(self.ineligible_reasons),
            "candidate_revision_previous_candidate_fingerprint": (
                self.previous_candidate_fingerprint
            ),
            "candidate_revision_revised_candidate_fingerprint": (
                self.revised_candidate_fingerprint
            ),
            "candidate_revision_evidence_fingerprint": self.evidence_fingerprint,
            "candidate_revision_counterexample_count": self.counterexample_count,
            "candidate_revision_preserved_case_count": self.preserved_case_count,
            "candidate_revision_output_rejection_reason": (
                self.output_rejection_reason
            ),
            "candidate_revision_provider": self.provider,
            "candidate_revision_model": self.model,
            "candidate_revision_author_selection": self.author_selection,
            "candidate_revision_latency_seconds": self.latency_seconds,
            "candidate_revision_evidence_seconds": self.evidence_seconds,
            "candidate_revision_input_chars": self.input_chars,
            "candidate_revision_output_chars": self.output_chars,
            "candidate_revision_present": self.revised_candidate_present,
            "candidate_revision_model_calls": self.attempt_count,
            "candidate_revision_model_call_budget_consumed": (
                self.model_call_budget_consumed
            ),
            "candidate_revision_model_call_budget_remaining": (
                self.model_call_budget_remaining
            ),
            "candidate_revision_network_calls": self.attempt_count,
            "candidate_revision_retrieval_calls": 0,
            "candidate_revision_repository_traversals": 0,
            "candidate_revision_repository_mutations": 0,
            "candidate_revision_reviewer_calls": 0,
            "candidate_revision_authority_effect": "none",
            "candidate_revision_receipt": self.as_dict(),
        }


def not_eligible_receipt(assessment: RevisionAssessment) -> CandidateRevisionReceipt:
    """§28 — the zero-cost path, recorded rather than left silent."""

    return CandidateRevisionReceipt(
        eligible=False,
        attempted=False,
        outcome=OUTCOME_NOT_ELIGIBLE,
        trigger=TRIGGER_NONE,
        ineligible_reasons=assessment.ineligible_reasons,
    )


def describe_candidate_revision(receipt: CandidateRevisionReceipt) -> str:
    """One operator-facing line that never reads as approval."""

    if not receipt.attempted:
        if receipt.ineligible_reasons:
            return (
                "no verification-guided revision was requested — "
                + "; ".join(receipt.ineligible_reasons)
            )
        return "no verification-guided revision was requested"
    if receipt.outcome == OUTCOME_REVISED_CANDIDATE_VERIFIED:
        return (
            "one revision was requested against "
            f"{receipt.counterexample_count} deterministic counterexample(s); "
            "the revised candidate verified, and verification grants no "
            "execution authority"
        )
    if receipt.outcome == OUTCOME_REVISION_OUTPUT_INVALID:
        return (
            "one revision was requested and its output was unusable "
            f"({receipt.output_rejection_reason}); no further attempt is made"
        )
    if receipt.outcome == OUTCOME_REVISION_UNAVAILABLE:
        return (
            "one revision was requested and the authoring provider was "
            "unavailable; no further attempt is made"
        )
    return (
        "one revision was requested against "
        f"{receipt.counterexample_count} deterministic counterexample(s) and the "
        "revised candidate was not verified; no further attempt is made"
    )


def candidate_revision_guardrails() -> dict[str, Any]:
    """The boundaries this phase asserts about itself (§49)."""

    return {
        "max_revision_calls_per_run": MAX_REVISION_CALLS_PER_RUN,
        "revision_is_conditional_on_behavioral_counterevidence": True,
        "no_op_candidate_can_trigger_revision": False,
        "safe_minimal_rejection_can_trigger_revision": False,
        "stale_candidate_can_trigger_revision": False,
        "malformed_candidate_can_trigger_revision": False,
        "revision_reveals_hidden_reasoning": False,
        "revision_supplies_implementation_hints": False,
        "revision_is_based_on_the_original_source": True,
        "revision_reuses_previous_candidate_receipts": False,
        "revision_adds_reviewer_or_debate_calls": False,
        "revision_performs_retrieval": False,
        "revision_traverses_the_repository": False,
        "revision_changes_validation_budgets": False,
        "revision_grants_execution_authority": False,
        "revision_widens_auto_apply": False,
        "revision_mutates_the_repository": False,
        # PATCH.AUTHOR.LIVE.2 — the authoring-contract asymmetry, closed.
        "revision_receives_the_initial_authoring_contract": True,
        "revision_and_initial_draft_share_one_contract": True,
        "revision_prompt_is_self_contained_about_the_wire_contract": True,
        "revision_contract_supplies_implementation_hints": False,
        "revision_output_parser_accepts_field_aliases": False,
        "malformed_revision_output_is_repaired": False,
        "prompt_compliance_can_substitute_for_a_deterministic_gate": False,
    }
