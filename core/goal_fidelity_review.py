"""CHECK.2 — Post-Run Goal-Fidelity Verification Contract.

CHECK.1 answered one question::

    "Did execution remain faithful to its objective execution contract?"

It deliberately did not answer the next one, and said so in every result it
produced.  CHECK.2 owns exactly that next bounded question::

    "For every explicit goal and preservation obligation, what does the
     already-assessed semantic evidence say about whether the final execution
     satisfied that obligation?"

It still does **not** answer::

    "Should the run be finally accepted?"

That reduction belongs to a future CHECK.3 / RUN.VERDICT.1, and every
:class:`GoalFidelityAssessment` structurally carries ``run_verdict_required``
so no consumer can read this phase as an acceptance.

There is no reviewer model here.  The forbidden architecture — hand a task
contract, a diff and a worker note to a model and let it say "looks correct" —
has no landing site: CHECK.2 consumes frozen CLAIM.1 ``ClaimAssessment``
records that already passed the ACQUIRE -> EVIDENCE.1 -> EVIDENCE.2 -> CLAIM.1
epistemic spine, and it makes no semantic judgement of its own.

Nine boundaries hold in every outcome.

**Execution-contract severity is monotonic.**  A CHECK.1 ``blocked`` result
cannot be rescued by any amount of supporting semantic evidence.  A forbidden
file changed plus every goal proposition supported is still blocked, and the
CHECK.1 blocking reasons are carried forward verbatim.

**No obligation is invented.**  Every obligation must trace to an authoritative
explicit source: a preservation obligation to CHECK.1's own typed preservation
finding, a goal or constraint obligation to an explicit upstream requirement
ledger bound to the same task contract.  :class:`ExplicitRequirementSource` has
no ``inferred`` provenance value to write, so a reviewer-invented "performance
should also be checked" requirement cannot be represented at all.

**No obligation is lost.**  Every CHECK.1 preservation finding and every
required ledger requirement must appear in the specification.  Three goals and
two preservation constraints produce five obligation results, even when some of
them are ``missing_claim_assessment``.

**No proposition is invented.**  CHECK.2 never writes proposition text.  Each
obligation reaches its semantics only through an explicit
:class:`ObligationClaimBinding` naming a proposition id, its digest and the
exact expected ClaimAssessment fingerprint.  There is no text similarity, no
embedding, no fuzzy match and no opportunistic reuse of a claim that happens to
be lying around.

**Polarity is supplied, never inferred.**  "Do not change embedding behaviour"
is satisfied by *support* for "the final implementation preserves the previous
embedding behaviour" and by *contradiction* of "the final implementation
changes embedding behaviour".  Nothing here can tell those apart from the
relation alone, so the binding must state its orientation and its provenance.
A binding that does not is ``binding_invalid`` rather than guessed.

**CLAIM.1 status is authoritative and is never laundered.**  ``conflicting``,
``insufficient``, ``coverage_incomplete``, ``current_state_unestablished`` and
``current_state_inconsistent`` pass through unchanged in both polarities, and
the original claim status is preserved next to the mapped obligation status in
every result.

**Semantic basis survives.**  Directional CLAIM.1 records arrive
``analyzer_assessed`` and leave ``analyzer_assessed``.  Ten satisfied
obligations are ten analyzer-assessed obligations; there is no
``semantically_verified`` and no ``goal_proven`` anywhere in the contract.

**A validation receipt is not a semantic claim.**  CHECK.1 may report that
``test_tmp_ignore`` passed and binds the final state.  That establishes the
execution of a validation, not the meaning of a goal.  An obligation with no
bound ClaimAssessment is ``missing_claim_assessment`` however suggestive the
test name is.

**Nothing is reduced.**  There is no count, no tally, no percentage, no score,
no confidence and no majority.  Three satisfied goals do not outvote one
violated preservation constraint; both stay independently visible, and CHECK.2
mints no ``run_success``, ``final_success``, ``merge_ready`` or
``implementation_correct``.

The module is pure and import-time inert.  Its only project imports are the two
frozen contracts it reconciles — ``core.claim_assessment`` and
``core.post_run_reconciliation``.  It reads no source byte, no diff, no test
and no repository; it acquires no evidence, executes no validation, calls no
model, touches no network, applies no patch, writes nothing, resolves no
conflict, repairs no worker and is wired into no live product path.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from core.claim_assessment import (
    BASIS_ANALYZER_ASSESSED,
    BASIS_NOT_ESTABLISHED,
    ClaimAssessment,
)
from core.claim_assessment import STATUS_CONFLICTING as CLAIM_CONFLICTING
from core.claim_assessment import STATUS_CONTRADICTED as CLAIM_CONTRADICTED
from core.claim_assessment import (
    STATUS_COVERAGE_INCOMPLETE as CLAIM_COVERAGE_INCOMPLETE,
)
from core.claim_assessment import (
    STATUS_CURRENT_STATE_INCONSISTENT as CLAIM_CURRENT_STATE_INCONSISTENT,
)
from core.claim_assessment import (
    STATUS_CURRENT_STATE_UNESTABLISHED as CLAIM_CURRENT_STATE_UNESTABLISHED,
)
from core.claim_assessment import (
    STATUS_INCONSISTENT_INPUT as CLAIM_INCONSISTENT_INPUT,
)
from core.claim_assessment import STATUS_INSUFFICIENT as CLAIM_INSUFFICIENT
from core.claim_assessment import STATUS_SUPPORTED as CLAIM_SUPPORTED
from core.post_run_reconciliation import (
    PRESERVATION_OBLIGATION_KINDS,
    PostRunReconciliation,
)
from core.post_run_reconciliation import STATUS_BLOCKED as CHECK_1_BLOCKED
from core.post_run_reconciliation import STATUS_INCOMPLETE as CHECK_1_INCOMPLETE
from core.post_run_reconciliation import (
    STATUS_INCONSISTENT_INPUT as CHECK_1_INCONSISTENT_INPUT,
)
from core.post_run_reconciliation import STATUS_RECONCILED as CHECK_1_RECONCILED
from core.post_run_reconciliation import (
    STATUS_RECONCILED_WITH_WARNINGS as CHECK_1_RECONCILED_WITH_WARNINGS,
)
from core.post_run_reconciliation import STATUS_SUSPICIOUS as CHECK_1_SUSPICIOUS


PHASE_ID = "CHECK.2"

REQUIREMENT_SOURCE_SCHEMA_VERSION = "check_2_explicit_requirement_source_v1"
REQUIREMENT_LEDGER_SCHEMA_VERSION = "check_2_explicit_requirement_ledger_v1"
OBLIGATION_SCHEMA_VERSION = "check_2_goal_verification_obligation_v1"
BINDING_SCHEMA_VERSION = "check_2_obligation_claim_binding_v1"
STATE_BINDING_SCHEMA_VERSION = "check_2_post_run_state_binding_v1"
SPECIFICATION_SCHEMA_VERSION = "check_2_goal_verification_specification_v1"
REQUEST_SCHEMA_VERSION = "check_2_goal_fidelity_review_request_v1"
RESULT_SCHEMA_VERSION = "check_2_goal_fidelity_assessment_v1"


# ── Obligation kinds ──────────────────────────────────────────────────────────
#: Three kinds, and each names *where the obligation came from*, never how
#: important someone thinks it is.  There is no ``quality_criterion`` and no
#: ``best_practice``: a reviewer expectation the user never stated has no kind
#: to be filed under.
OBLIGATION_KIND_GOAL = "goal_requirement"
OBLIGATION_KIND_PRESERVATION = "preservation_requirement"
OBLIGATION_KIND_CONSTRAINT = "explicit_constraint"

OBLIGATION_KINDS: tuple[str, ...] = (
    OBLIGATION_KIND_GOAL,
    OBLIGATION_KIND_PRESERVATION,
    OBLIGATION_KIND_CONSTRAINT,
)

#: The kinds an upstream requirement ledger may carry.  Preservation
#: obligations are deliberately absent: they are authoritative from CHECK.1's
#: own typed preservation findings, so a caller cannot launder one in through
#: the ledger it also supplies.
LEDGER_REQUIREMENT_KINDS: tuple[str, ...] = (
    OBLIGATION_KIND_GOAL,
    OBLIGATION_KIND_CONSTRAINT,
)


# ── Requirement provenance ────────────────────────────────────────────────────
#: How an explicit requirement came to be in the ledger.  Both values mean the
#: user or an operator literally stated it.  ``inferred`` is not a value, which
#: is what makes "no obligation invention" structural rather than a rule
#: somebody has to remember to apply.
REQUIREMENT_PROVENANCE_TASK_CONTRACT = "explicit_task_contract"
REQUIREMENT_PROVENANCE_HUMAN_BINDING = "explicit_human_binding"

REQUIREMENT_PROVENANCES: tuple[str, ...] = (
    REQUIREMENT_PROVENANCE_TASK_CONTRACT,
    REQUIREMENT_PROVENANCE_HUMAN_BINDING,
)


# ── Satisfaction polarity ─────────────────────────────────────────────────────
#: Which direction of the bound proposition means the obligation was met.  A
#: ClaimAssessment relation on its own cannot say: "preserves the previous
#: embedding behaviour" and "changes the embedding behaviour" are both
#: legitimate projections of the same preservation obligation and they read the
#: same evidence in opposite directions.
POLARITY_SUPPORT_MEANS_SATISFIED = "support_means_satisfied"
POLARITY_CONTRADICTION_MEANS_SATISFIED = "contradiction_means_satisfied"

SATISFACTION_POLARITIES: tuple[str, ...] = (
    POLARITY_SUPPORT_MEANS_SATISFIED,
    POLARITY_CONTRADICTION_MEANS_SATISFIED,
)

#: Who established the orientation.  CHECK.2 never appears in this list because
#: CHECK.2 never establishes one.
POLARITY_PROVENANCE_HUMAN_BINDING = "explicit_human_binding"
POLARITY_PROVENANCE_GOAL_PROJECTION = "upstream_goal_projection"
POLARITY_PROVENANCE_PRESERVED_REQUIREMENT = "preserved_requirement_binding"

POLARITY_PROVENANCES: tuple[str, ...] = (
    POLARITY_PROVENANCE_HUMAN_BINDING,
    POLARITY_PROVENANCE_GOAL_PROJECTION,
    POLARITY_PROVENANCE_PRESERVED_REQUIREMENT,
)


# ── Review mode ───────────────────────────────────────────────────────────────
#: What CHECK.1's objective reconciliation permits this review to *mean*.  It
#: is independent of every semantic obligation status: a run whose obligations
#: all read as satisfied is still ``blocked`` if its execution contract was
#: violated.
REVIEW_BLOCKED = "blocked"
REVIEW_DIAGNOSTIC_ONLY = "diagnostic_only"
REVIEW_ASSESSABLE = "assessable"

REVIEW_MODES: tuple[str, ...] = (
    REVIEW_BLOCKED,
    REVIEW_DIAGNOSTIC_ONLY,
    REVIEW_ASSESSABLE,
)

#: The deterministic CHECK.1 entry gate.  Semantic assessment never rescues an
#: execution-contract violation, so a blocked or unusable reconciliation stops
#: the review, and an incomplete or suspicious one caps it at diagnostics.
CHECK_1_ENTRY_POLICY: dict[str, str] = {
    CHECK_1_RECONCILED: REVIEW_ASSESSABLE,
    CHECK_1_RECONCILED_WITH_WARNINGS: REVIEW_ASSESSABLE,
    CHECK_1_INCOMPLETE: REVIEW_DIAGNOSTIC_ONLY,
    CHECK_1_SUSPICIOUS: REVIEW_DIAGNOSTIC_ONLY,
    CHECK_1_BLOCKED: REVIEW_BLOCKED,
    CHECK_1_INCONSISTENT_INPUT: REVIEW_BLOCKED,
}


# ── Obligation status vocabulary ──────────────────────────────────────────────
#: Eleven categorical values.  Every one of them names a state of the *assessed
#: evidence for one explicit obligation*, never a state of the world and never
#: an acceptance.  ``correct``, ``incorrect``, ``true``, ``false``, ``success``
#: and ``failure_probability`` are absent on purpose.
OBLIGATION_SATISFIED = "satisfied_by_assessed_evidence"
OBLIGATION_VIOLATED = "violated_by_assessed_evidence"
OBLIGATION_CONFLICTING = "conflicting_evidence"
OBLIGATION_INSUFFICIENT = "insufficient_evidence"
OBLIGATION_COVERAGE_INCOMPLETE = "coverage_incomplete"
OBLIGATION_CURRENT_STATE_UNESTABLISHED = "current_state_unestablished"
OBLIGATION_CURRENT_STATE_INCONSISTENT = "current_state_inconsistent"
OBLIGATION_MISSING_CLAIM = "missing_claim_assessment"
OBLIGATION_BINDING_INVALID = "binding_invalid"
OBLIGATION_COMPOSITE_UNSUPPORTED = "composite_obligation_unsupported"
OBLIGATION_BLOCKED_BY_RECONCILIATION = "blocked_by_reconciliation"

OBLIGATION_STATUSES: tuple[str, ...] = (
    OBLIGATION_SATISFIED,
    OBLIGATION_VIOLATED,
    OBLIGATION_CONFLICTING,
    OBLIGATION_INSUFFICIENT,
    OBLIGATION_COVERAGE_INCOMPLETE,
    OBLIGATION_CURRENT_STATE_UNESTABLISHED,
    OBLIGATION_CURRENT_STATE_INCONSISTENT,
    OBLIGATION_MISSING_CLAIM,
    OBLIGATION_BINDING_INVALID,
    OBLIGATION_COMPOSITE_UNSUPPORTED,
    OBLIGATION_BLOCKED_BY_RECONCILIATION,
)

#: The two statuses that point somewhere.  Both are bounded by assessed
#: evidence and neither is a proof.
DETERMINED_OBLIGATION_STATUSES: frozenset[str] = frozenset(
    {OBLIGATION_SATISFIED, OBLIGATION_VIOLATED}
)

#: Unresolved CLAIM.1 states, preserved identically under either polarity.  A
#: reviewer who could turn one of these into satisfied or violated would be
#: inventing the semantics CLAIM.1 declined to establish.
_UNRESOLVED_CLAIM_MAP: dict[str, str] = {
    CLAIM_CONFLICTING: OBLIGATION_CONFLICTING,
    CLAIM_INSUFFICIENT: OBLIGATION_INSUFFICIENT,
    CLAIM_COVERAGE_INCOMPLETE: OBLIGATION_COVERAGE_INCOMPLETE,
    CLAIM_CURRENT_STATE_UNESTABLISHED: OBLIGATION_CURRENT_STATE_UNESTABLISHED,
    CLAIM_CURRENT_STATE_INCONSISTENT: OBLIGATION_CURRENT_STATE_INCONSISTENT,
    CLAIM_INCONSISTENT_INPUT: OBLIGATION_BINDING_INVALID,
}

#: The only directional mapping in the module, and it is a lookup rather than a
#: judgement.  The supplied polarity picks the row; nothing here picks a row.
_POLARITY_MAP: dict[str, dict[str, str]] = {
    POLARITY_SUPPORT_MEANS_SATISFIED: {
        CLAIM_SUPPORTED: OBLIGATION_SATISFIED,
        CLAIM_CONTRADICTED: OBLIGATION_VIOLATED,
    },
    POLARITY_CONTRADICTION_MEANS_SATISFIED: {
        CLAIM_SUPPORTED: OBLIGATION_VIOLATED,
        CLAIM_CONTRADICTED: OBLIGATION_SATISFIED,
    },
}


# ── Top-level status vocabulary ───────────────────────────────────────────────
#: ``assessed`` says the review ran and every required obligation reached a
#: determined state.  It says nothing about the direction of those states: an
#: assessment holding one violated preservation obligation is ``assessed`` and
#: is not an acceptance.  There is deliberately no ``success``, ``failure``,
#: ``correct`` or ``incorrect`` value.
STATUS_ASSESSED = "assessed"
STATUS_ASSESSED_WITH_GAPS = "assessed_with_gaps"
STATUS_DIAGNOSTIC_ONLY = "diagnostic_only"
STATUS_BLOCKED = "blocked"
STATUS_INCONSISTENT_INPUT = "inconsistent_input"

GOAL_FIDELITY_STATUSES: tuple[str, ...] = (
    STATUS_ASSESSED,
    STATUS_ASSESSED_WITH_GAPS,
    STATUS_DIAGNOSTIC_ONLY,
    STATUS_BLOCKED,
    STATUS_INCONSISTENT_INPUT,
)


# ── Post-run state binding ────────────────────────────────────────────────────
#: Whether a bound ClaimAssessment can be shown to describe the same final
#: repository state CHECK.1 reconciled.  A source digest alone does not prove
#: it; only an explicit upstream receipt naming that final state does.
STATE_BINDING_BOUND = "bound_to_final_state"
STATE_BINDING_UNAVAILABLE = "final_state_binding_unavailable"

STATE_BINDING_STATES: tuple[str, ...] = (
    STATE_BINDING_BOUND,
    STATE_BINDING_UNAVAILABLE,
)

#: Who established that an evidence set describes the post-run final state.
STATE_BINDING_PROVENANCE_RECEIPT = "upstream_final_state_receipt"
STATE_BINDING_PROVENANCE_HUMAN = "explicit_human_binding"

STATE_BINDING_PROVENANCES: tuple[str, ...] = (
    STATE_BINDING_PROVENANCE_RECEIPT,
    STATE_BINDING_PROVENANCE_HUMAN,
)


# ── Reasons ───────────────────────────────────────────────────────────────────
#: Bounded, stable and emitted in canonical order.  Each names structural work
#: CHECK.2 actually performed, never a conclusion about the implementation.
CHECK2_RECONCILIATION_BOUND = "CHECK2_RECONCILIATION_BOUND"
CHECK2_CHECK_1_GATE_EVALUATED = "CHECK2_CHECK_1_GATE_EVALUATED"
CHECK2_REQUIREMENT_LEDGER_BOUND = "CHECK2_REQUIREMENT_LEDGER_BOUND"
CHECK2_SPECIFICATION_BOUND = "CHECK2_SPECIFICATION_BOUND"
CHECK2_OBLIGATION_COVERAGE_VERIFIED = "CHECK2_OBLIGATION_COVERAGE_VERIFIED"
CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED = (
    "CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED"
)
CHECK2_CLAIM_ASSESSMENTS_CONSUMED = "CHECK2_CLAIM_ASSESSMENTS_CONSUMED"
CHECK2_POLARITY_APPLIED_AS_SUPPLIED = "CHECK2_POLARITY_APPLIED_AS_SUPPLIED"
CHECK2_CLAIM_STATUS_PRESERVED = "CHECK2_CLAIM_STATUS_PRESERVED"
CHECK2_SEMANTIC_BASIS_PRESERVED = "CHECK2_SEMANTIC_BASIS_PRESERVED"
CHECK2_POST_RUN_STATE_BINDING_CHECKED = "CHECK2_POST_RUN_STATE_BINDING_CHECKED"
CHECK2_EXECUTION_SEVERITY_PRESERVED = "CHECK2_EXECUTION_SEVERITY_PRESERVED"
CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED = (
    "CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED"
)
CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED = "CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED"
CHECK2_NO_CONFLICT_ADJUDICATED = "CHECK2_NO_CONFLICT_ADJUDICATED"
CHECK2_NO_MAJORITY_COMPUTED = "CHECK2_NO_MAJORITY_COMPUTED"
CHECK2_NO_RUN_VERDICT_PRODUCED = "CHECK2_NO_RUN_VERDICT_PRODUCED"
CHECK2_INPUT_REJECTED = "CHECK2_INPUT_REJECTED"

GOAL_FIDELITY_REASONS: tuple[str, ...] = (
    CHECK2_RECONCILIATION_BOUND,
    CHECK2_CHECK_1_GATE_EVALUATED,
    CHECK2_REQUIREMENT_LEDGER_BOUND,
    CHECK2_SPECIFICATION_BOUND,
    CHECK2_OBLIGATION_COVERAGE_VERIFIED,
    CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED,
    CHECK2_CLAIM_ASSESSMENTS_CONSUMED,
    CHECK2_POLARITY_APPLIED_AS_SUPPLIED,
    CHECK2_CLAIM_STATUS_PRESERVED,
    CHECK2_SEMANTIC_BASIS_PRESERVED,
    CHECK2_POST_RUN_STATE_BINDING_CHECKED,
    CHECK2_EXECUTION_SEVERITY_PRESERVED,
    CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED,
    CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED,
    CHECK2_NO_CONFLICT_ADJUDICATED,
    CHECK2_NO_MAJORITY_COMPUTED,
    CHECK2_NO_RUN_VERDICT_PRODUCED,
    CHECK2_INPUT_REJECTED,
)


# ── Per-obligation reason codes ───────────────────────────────────────────────
OBLIGATION_REASON_CLAIM_BOUND = "claim_assessment_bound"
OBLIGATION_REASON_NO_BINDING = "no_claim_binding_supplied"
OBLIGATION_REASON_CLAIM_ABSENT = "bound_claim_assessment_not_supplied"
OBLIGATION_REASON_POLARITY_ABSENT = "satisfaction_polarity_not_supplied"
OBLIGATION_REASON_POLARITY_PROVENANCE_ABSENT = "polarity_provenance_not_supplied"
OBLIGATION_REASON_CLAIM_REFUSED = "bound_claim_assessment_refused_its_input"
OBLIGATION_REASON_MULTIPLE_BINDINGS = "multiple_claim_bindings_supplied"
OBLIGATION_REASON_RECONCILIATION_BLOCKED = "execution_reconciliation_blocked"
OBLIGATION_REASON_DIAGNOSTIC_ONLY = "execution_reconciliation_unresolved"
OBLIGATION_REASON_FINAL_STATE_BOUND = "claim_bound_to_reconciled_final_state"
OBLIGATION_REASON_FINAL_STATE_UNBOUND = "claim_not_bound_to_reconciled_final_state"
OBLIGATION_REASON_OPTIONAL = "obligation_is_optional"

OBLIGATION_RESULT_REASONS: tuple[str, ...] = (
    OBLIGATION_REASON_CLAIM_BOUND,
    OBLIGATION_REASON_NO_BINDING,
    OBLIGATION_REASON_CLAIM_ABSENT,
    OBLIGATION_REASON_POLARITY_ABSENT,
    OBLIGATION_REASON_POLARITY_PROVENANCE_ABSENT,
    OBLIGATION_REASON_CLAIM_REFUSED,
    OBLIGATION_REASON_MULTIPLE_BINDINGS,
    OBLIGATION_REASON_RECONCILIATION_BLOCKED,
    OBLIGATION_REASON_DIAGNOSTIC_ONLY,
    OBLIGATION_REASON_FINAL_STATE_BOUND,
    OBLIGATION_REASON_FINAL_STATE_UNBOUND,
    OBLIGATION_REASON_OPTIONAL,
)


# ── Inconsistencies ───────────────────────────────────────────────────────────
#: Every one of these makes the supplied review request unusable.  CHECK.2 does
#: not repair a malformed specification, does not re-derive a missing binding
#: and does not fall back to a weaker reading: a specification that cannot be
#: trusted to say which obligations exist cannot be reconciled against
#: anything.
INCONSISTENT_TASK_CONTRACT_FINGERPRINT = "task_contract_fingerprint_mismatch"
INCONSISTENT_RECONCILIATION_FINGERPRINT = (
    "check_1_reconciliation_fingerprint_mismatch"
)
INCONSISTENT_SPECIFICATION_FINGERPRINT = (
    "verification_specification_fingerprint_mismatch"
)
INCONSISTENT_LEDGER_FINGERPRINT = "requirement_ledger_fingerprint_mismatch"
INCONSISTENT_LEDGER_TASK_BINDING = "requirement_ledger_task_binding_mismatch"
INCONSISTENT_SPECIFICATION_TASK_BINDING = "specification_task_binding_mismatch"
INCONSISTENT_SPECIFICATION_RUN_BINDING = (
    "specification_reconciliation_binding_mismatch"
)
INCONSISTENT_CLAIM_FINGERPRINT = "claim_assessment_fingerprint_mismatch"
INCONSISTENT_CLAIM_PROPOSITION_BINDING = "claim_proposition_binding_mismatch"
INCONSISTENT_CLAIM_EVIDENCE_SET_BINDING = "claim_evidence_set_binding_mismatch"
INCONSISTENT_CLAIM_DUPLICATE = "duplicate_claim_assessment_supplied"
INCONSISTENT_BINDING_UNKNOWN_OBLIGATION = "claim_binding_names_unknown_obligation"
INCONSISTENT_GOAL_OBLIGATION_DROPPED = "goal_obligation_dropped"
INCONSISTENT_PRESERVATION_OBLIGATION_DROPPED = "preservation_obligation_dropped"
INCONSISTENT_OBLIGATION_WIDENED = "obligation_structure_widened"
INCONSISTENT_OBLIGATION_SOURCE_KIND = "obligation_source_kind_mismatch"
INCONSISTENT_OBLIGATION_SOURCE_TEXT = "obligation_source_text_mismatch"
INCONSISTENT_POST_RUN_STATE_BINDING = "post_run_state_binding_mismatch"
INCONSISTENT_CHECK_1_INPUT_UNUSABLE = "check_1_reconciliation_unusable"
INCONSISTENT_SEMANTIC_BASIS = "semantic_basis_not_preserved"
INCONSISTENT_UPSTREAM_AUTHORITY = "upstream_authority_asserted"
INCONSISTENT_UPSTREAM_GUARDRAIL = "upstream_guardrail_violated"

GOAL_FIDELITY_INCONSISTENCIES: tuple[str, ...] = (
    INCONSISTENT_TASK_CONTRACT_FINGERPRINT,
    INCONSISTENT_RECONCILIATION_FINGERPRINT,
    INCONSISTENT_SPECIFICATION_FINGERPRINT,
    INCONSISTENT_LEDGER_FINGERPRINT,
    INCONSISTENT_LEDGER_TASK_BINDING,
    INCONSISTENT_SPECIFICATION_TASK_BINDING,
    INCONSISTENT_SPECIFICATION_RUN_BINDING,
    INCONSISTENT_CLAIM_FINGERPRINT,
    INCONSISTENT_CLAIM_PROPOSITION_BINDING,
    INCONSISTENT_CLAIM_EVIDENCE_SET_BINDING,
    INCONSISTENT_CLAIM_DUPLICATE,
    INCONSISTENT_BINDING_UNKNOWN_OBLIGATION,
    INCONSISTENT_GOAL_OBLIGATION_DROPPED,
    INCONSISTENT_PRESERVATION_OBLIGATION_DROPPED,
    INCONSISTENT_OBLIGATION_WIDENED,
    INCONSISTENT_OBLIGATION_SOURCE_KIND,
    INCONSISTENT_OBLIGATION_SOURCE_TEXT,
    INCONSISTENT_POST_RUN_STATE_BINDING,
    INCONSISTENT_CHECK_1_INPUT_UNUSABLE,
    INCONSISTENT_SEMANTIC_BASIS,
    INCONSISTENT_UPSTREAM_AUTHORITY,
    INCONSISTENT_UPSTREAM_GUARDRAIL,
)


# ── Unresolved requirements ───────────────────────────────────────────────────
#: What still has to happen after CHECK.2.  ``run_verdict_required`` and
#: ``human_review_required`` appear on *every* result, including one where
#: every obligation reads as satisfied, and the result cannot be constructed
#: without them.
UNRESOLVED_EXECUTION_CONTRACT_VIOLATION = "execution_contract_violation_unresolved"
UNRESOLVED_EXECUTION_RECONCILIATION = "execution_reconciliation_unresolved"
UNRESOLVED_OBLIGATION_EVIDENCE = "semantic_obligation_evidence_required"
UNRESOLVED_CONFLICT_ADJUDICATION = "conflict_adjudication_unavailable"
UNRESOLVED_NEGATIVE_COVERAGE = "negative_claim_coverage_required"
UNRESOLVED_CURRENT_STATE_EVIDENCE = "current_state_evidence_required"
UNRESOLVED_OBLIGATION_BINDING = "obligation_claim_binding_required"
UNRESOLVED_COMPOSITE_OBLIGATION = "composite_obligation_projection_required"
UNRESOLVED_POST_RUN_STATE_BINDING = "post_run_semantic_state_binding_unavailable"
UNRESOLVED_VIOLATED_OBLIGATION = "violated_obligation_review_required"
UNRESOLVED_OPTIONAL_OBLIGATION = "optional_obligation_evidence_absent"
UNRESOLVED_UPSTREAM_INPUT = "upstream_input_correction_required"
UNRESOLVED_RUN_VERDICT = "run_verdict_required"
UNRESOLVED_HUMAN_REVIEW = "human_review_required"

GOAL_FIDELITY_UNRESOLVED_REQUIREMENTS: tuple[str, ...] = (
    UNRESOLVED_EXECUTION_CONTRACT_VIOLATION,
    UNRESOLVED_EXECUTION_RECONCILIATION,
    UNRESOLVED_OBLIGATION_EVIDENCE,
    UNRESOLVED_CONFLICT_ADJUDICATION,
    UNRESOLVED_NEGATIVE_COVERAGE,
    UNRESOLVED_CURRENT_STATE_EVIDENCE,
    UNRESOLVED_OBLIGATION_BINDING,
    UNRESOLVED_COMPOSITE_OBLIGATION,
    UNRESOLVED_POST_RUN_STATE_BINDING,
    UNRESOLVED_VIOLATED_OBLIGATION,
    UNRESOLVED_OPTIONAL_OBLIGATION,
    UNRESOLVED_UPSTREAM_INPUT,
    UNRESOLVED_RUN_VERDICT,
    UNRESOLVED_HUMAN_REVIEW,
)

#: Which unresolved requirement each non-determined obligation status raises.
_UNRESOLVED_FOR_OBLIGATION_STATUS: dict[str, str] = {
    OBLIGATION_CONFLICTING: UNRESOLVED_CONFLICT_ADJUDICATION,
    OBLIGATION_INSUFFICIENT: UNRESOLVED_OBLIGATION_EVIDENCE,
    OBLIGATION_COVERAGE_INCOMPLETE: UNRESOLVED_NEGATIVE_COVERAGE,
    OBLIGATION_CURRENT_STATE_UNESTABLISHED: UNRESOLVED_CURRENT_STATE_EVIDENCE,
    OBLIGATION_CURRENT_STATE_INCONSISTENT: UNRESOLVED_CURRENT_STATE_EVIDENCE,
    OBLIGATION_MISSING_CLAIM: UNRESOLVED_OBLIGATION_EVIDENCE,
    OBLIGATION_BINDING_INVALID: UNRESOLVED_OBLIGATION_BINDING,
    OBLIGATION_COMPOSITE_UNSUPPORTED: UNRESOLVED_COMPOSITE_OBLIGATION,
    OBLIGATION_BLOCKED_BY_RECONCILIATION: UNRESOLVED_EXECUTION_CONTRACT_VIOLATION,
}


# ── Stated meanings ───────────────────────────────────────────────────────────
#: Written into the contract itself so no downstream consumer can read a
#: bounded evidence state as a proof or an acceptance.
SATISFIED_MEANING = (
    "Given the supplied proposition-to-obligation orientation, the bounded "
    "CLAIM.1 assessment for this obligation points toward satisfaction of that "
    "explicit obligation. It does not mean the implementation was "
    "deterministically proven to satisfy it: the underlying semantic relations "
    "remain analyzer-assessed."
)

VIOLATED_MEANING = (
    "Given the supplied proposition-to-obligation orientation, the bounded "
    "CLAIM.1 assessment for this obligation points toward violation of that "
    "explicit obligation. It is not a deterministic proof of violation and it "
    "is not a run verdict."
)

ASSESSED_MEANING = (
    "Every required obligation reached a determined evidence state and the "
    "CHECK.1 reconciliation permitted semantic review. It does not mean the run "
    "succeeded, that the implementation is correct, or that the change may be "
    "merged; a violated obligation is an assessed one too, and the acceptance "
    "verdict is CHECK.3 and remains outstanding."
)

REVIEW_MODE_MEANING: dict[str, str] = {
    REVIEW_ASSESSABLE: (
        "CHECK.1 reconciled the execution contract, so bounded semantic "
        "obligation states may be read for this run. Acceptance remains a "
        "separate, later question."
    ),
    REVIEW_DIAGNOSTIC_ONLY: (
        "CHECK.1 left contractual execution prerequisites unresolved. Semantic "
        "obligation states are reported for diagnostics only and certify "
        "nothing about this run; supporting evidence cannot upgrade the "
        "reconciliation."
    ),
    REVIEW_BLOCKED: (
        "CHECK.1 blocked or refused this execution. No semantic obligation "
        "state is available for it and none could rescue it; the "
        "execution-contract violation stands."
    ),
}


# ── Finite bounds ─────────────────────────────────────────────────────────────
MAX_IDENTIFIER_CHARS = 160
#: Mirrors CLAIM.1's own proposition text bound; a focused test pins the two
#: together so a future upstream change cannot silently widen this one.
MAX_PROPOSITION_TEXT_CHARS = 500
MAX_LEDGER_REQUIREMENTS = 32
MAX_OBLIGATIONS = 64
MAX_BINDINGS = 64
MAX_CLAIM_ASSESSMENTS = 64
MAX_OBLIGATION_RESULTS = MAX_OBLIGATIONS


# ── Pure helpers ──────────────────────────────────────────────────────────────

def _canonical_json(payload: Any) -> str:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _fingerprint(payload: Any) -> str:
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _require_sha256(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not _is_sha256(value):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")


def _bounded_identifier(value: object, label: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    if len(value) > MAX_IDENTIFIER_CHARS:
        raise ValueError(f"{label} exceeds its finite bound")
    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} may not contain control characters")


def _bounded_tuple(values: object, maximum: int, label: str) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    if len(values) > maximum:
        raise ValueError(f"{label} exceeds its finite bound")


def _validate_unique(values: tuple[str, ...], label: str) -> None:
    seen: set[str] = set()
    for value in values:
        if value in seen:
            raise ValueError(f"duplicate {label}: {value!r}")
        seen.add(value)


def _validate_ordinals(values: tuple[Any, ...], label: str) -> None:
    """Ordinals are all present or all absent, and never ambiguous.

    A partly ordered obligation set has no canonical order, and CHECK.2 refuses
    to invent one rather than sorting the rest arbitrarily.
    """
    ordinals = tuple(item.ordinal for item in values)
    present = tuple(item for item in ordinals if item is not None)
    absent = tuple(item for item in ordinals if item is None)
    if present and absent:
        raise ValueError(f"{label} ordinals must be wholly present or wholly absent")
    _validate_unique(tuple(str(item) for item in present), f"{label} ordinal")


def _ordered_codes(codes: set[str], vocabulary: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(value for value in vocabulary if value in codes)


def _ordered_vocabulary(
    values: object, vocabulary: tuple[str, ...], label: str
) -> None:
    if not isinstance(values, tuple):
        raise TypeError(f"{label} must be a tuple")
    _validate_unique(values, label)
    for value in values:
        if value not in vocabulary:
            raise ValueError(f"unsupported {label}: {value!r}")
    expected = tuple(item for item in vocabulary if item in set(values))
    if values != expected:
        raise ValueError(f"{label} must be stated in canonical order")


def _ordinal_sort_key(record: Any) -> tuple[int, str, str]:
    """Explicit ordinals order first; otherwise identity does.

    ``zfill`` keeps the ordinal comparison lexical, so nothing in this module
    performs arithmetic over an obligation set.
    """
    if record.ordinal is None:
        return (1, "", record.obligation_id)
    return (0, str(record.ordinal).zfill(6), record.obligation_id)


# ── Explicit requirement ledger ───────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ExplicitRequirementSource:
    """One requirement the user or an operator literally stated.

    CHECK.2 never reads the requirement's prose — only its digest — so it
    structurally cannot reinterpret, narrow or broaden what the user asked for.
    """

    requirement_id: str
    requirement_kind: str
    requirement_text_sha256: str
    provenance: str
    required: bool = True
    ordinal: int | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.requirement_id, "requirement id")
        if self.requirement_kind not in LEDGER_REQUIREMENT_KINDS:
            raise ValueError(
                f"unsupported ledger requirement kind: {self.requirement_kind!r}"
            )
        _require_sha256(self.requirement_text_sha256, "requirement text digest")
        if self.provenance not in REQUIREMENT_PROVENANCES:
            raise ValueError(f"unsupported requirement provenance: {self.provenance!r}")
        if not isinstance(self.required, bool):
            raise TypeError("requirement required must be a bool")
        if self.ordinal is not None:
            if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
                raise TypeError("requirement ordinal must be an integer")
            if self.ordinal < 1:
                raise ValueError("requirement ordinal must be positive")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REQUIREMENT_SOURCE_SCHEMA_VERSION,
            "requirement_id": self.requirement_id,
            "requirement_kind": self.requirement_kind,
            "requirement_text_sha256": self.requirement_text_sha256,
            "provenance": self.provenance,
            "required": self.required,
            "ordinal": self.ordinal,
            "derived_by_check_2": False,
        }


@dataclass(frozen=True, slots=True)
class ExplicitRequirementLedger:
    """The authoritative explicit goal/constraint set for one task contract.

    Preservation obligations are absent by construction: those are authoritative
    from CHECK.1's own preservation findings, and a ledger that could carry one
    would be a second, weaker route to the same claim.
    """

    task_contract_fingerprint: str
    requirements: tuple[ExplicitRequirementSource, ...] = ()
    schema_version: str = REQUIREMENT_LEDGER_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _bounded_tuple(
            self.requirements, MAX_LEDGER_REQUIREMENTS, "ledger requirements"
        )
        if not all(
            type(item) is ExplicitRequirementSource for item in self.requirements
        ):
            raise TypeError(
                "requirements must contain ExplicitRequirementSource records"
            )
        _validate_unique(
            tuple(item.requirement_id for item in self.requirements),
            "ledger requirement id",
        )
        if self.schema_version != REQUIREMENT_LEDGER_SCHEMA_VERSION:
            raise ValueError("unsupported explicit requirement ledger schema version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "requirements": [
                item.as_dict()
                for item in sorted(self.requirements, key=lambda x: x.requirement_id)
            ],
            "preservation_requirements_supplied": False,
        }


def explicit_requirement_ledger_fingerprint(ledger: ExplicitRequirementLedger) -> str:
    if type(ledger) is not ExplicitRequirementLedger:
        raise TypeError(
            "explicit_requirement_ledger_fingerprint requires an exact "
            "ExplicitRequirementLedger"
        )
    return _fingerprint(ledger.as_dict())


# ── Specification records ─────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class GoalVerificationObligation:
    """One explicit obligation this run is to be reconciled against.

    ``source_requirement_id`` is the whole anti-invention mechanism: a
    preservation obligation must name a CHECK.1 preservation finding, and a goal
    or constraint obligation must name an entry in the explicit requirement
    ledger.  An obligation naming neither is structural widening.
    """

    obligation_id: str
    obligation_kind: str
    obligation_text_sha256: str
    source_requirement_id: str
    required: bool = True
    ordinal: int | None = None
    preservation_obligation_kind: str | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.obligation_id, "obligation id")
        if self.obligation_kind not in OBLIGATION_KINDS:
            raise ValueError(f"unsupported obligation kind: {self.obligation_kind!r}")
        _require_sha256(self.obligation_text_sha256, "obligation text digest")
        _bounded_identifier(self.source_requirement_id, "source requirement id")
        if not isinstance(self.required, bool):
            raise TypeError("obligation required must be a bool")
        if self.ordinal is not None:
            if not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool):
                raise TypeError("obligation ordinal must be an integer")
            if self.ordinal < 1:
                raise ValueError("obligation ordinal must be positive")
        if self.obligation_kind == OBLIGATION_KIND_PRESERVATION:
            if self.preservation_obligation_kind not in PRESERVATION_OBLIGATION_KINDS:
                raise ValueError(
                    "a preservation obligation carries the CHECK.1 preservation "
                    "obligation kind it was preserved under"
                )
        elif self.preservation_obligation_kind is not None:
            raise ValueError(
                "only a preservation obligation carries a preservation kind"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OBLIGATION_SCHEMA_VERSION,
            "obligation_id": self.obligation_id,
            "obligation_kind": self.obligation_kind,
            "obligation_text_sha256": self.obligation_text_sha256,
            "source_requirement_id": self.source_requirement_id,
            "preservation_obligation_kind": self.preservation_obligation_kind,
            "required": self.required,
            "ordinal": self.ordinal,
            "derived_by_check_2": False,
        }


@dataclass(frozen=True, slots=True)
class PostRunStateBinding:
    """An explicit receipt that a claim's evidence describes the final state.

    A repository source digest alone does not establish this.  Where no upstream
    receipt exists the binding is simply absent, and the obligation result says
    so rather than pretending the semantics were established for the post-run
    state.
    """

    final_state_fingerprint: str
    state_receipt_sha256: str
    provenance: str

    def __post_init__(self) -> None:
        _require_sha256(self.final_state_fingerprint, "bound final state fingerprint")
        _require_sha256(self.state_receipt_sha256, "final state receipt digest")
        if self.provenance not in STATE_BINDING_PROVENANCES:
            raise ValueError(
                f"unsupported state binding provenance: {self.provenance!r}"
            )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_BINDING_SCHEMA_VERSION,
            "final_state_fingerprint": self.final_state_fingerprint,
            "state_receipt_sha256": self.state_receipt_sha256,
            "provenance": self.provenance,
            "derived_by_check_2": False,
        }


@dataclass(frozen=True, slots=True)
class ObligationClaimBinding:
    """An exact, upstream-supplied obligation-to-proposition binding.

    ``satisfaction_polarity`` and ``polarity_provenance`` are optional in the
    *type* and mandatory in the *outcome*: a binding that omits either is
    reported as ``binding_invalid`` rather than refused at construction, because
    a missing orientation is a real upstream state that must stay auditable
    instead of raising somewhere a caller might swallow it.
    """

    obligation_id: str
    proposition_id: str
    proposition_sha256: str
    expected_claim_assessment_fingerprint: str
    satisfaction_polarity: str | None = None
    polarity_provenance: str | None = None
    expected_evidence_set_fingerprint: str | None = None
    post_run_state_binding: PostRunStateBinding | None = None

    def __post_init__(self) -> None:
        _bounded_identifier(self.obligation_id, "binding obligation id")
        _bounded_identifier(self.proposition_id, "binding proposition id")
        _require_sha256(self.proposition_sha256, "binding proposition digest")
        _require_sha256(
            self.expected_claim_assessment_fingerprint,
            "expected claim assessment fingerprint",
        )
        if (
            self.satisfaction_polarity is not None
            and self.satisfaction_polarity not in SATISFACTION_POLARITIES
        ):
            raise ValueError(
                f"unsupported satisfaction polarity: {self.satisfaction_polarity!r}"
            )
        if (
            self.polarity_provenance is not None
            and self.polarity_provenance not in POLARITY_PROVENANCES
        ):
            raise ValueError(
                f"unsupported polarity provenance: {self.polarity_provenance!r}"
            )
        _require_sha256(
            self.expected_evidence_set_fingerprint,
            "expected evidence set fingerprint",
            optional=True,
        )
        if self.post_run_state_binding is not None and (
            type(self.post_run_state_binding) is not PostRunStateBinding
        ):
            raise TypeError("post_run_state_binding must be a PostRunStateBinding")

    @property
    def polarity_established(self) -> bool:
        return (
            self.satisfaction_polarity is not None
            and self.polarity_provenance is not None
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BINDING_SCHEMA_VERSION,
            "obligation_id": self.obligation_id,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "expected_claim_assessment_fingerprint": (
                self.expected_claim_assessment_fingerprint
            ),
            "satisfaction_polarity": self.satisfaction_polarity,
            "polarity_provenance": self.polarity_provenance,
            "expected_evidence_set_fingerprint": (
                self.expected_evidence_set_fingerprint
            ),
            "post_run_state_binding": (
                None
                if self.post_run_state_binding is None
                else self.post_run_state_binding.as_dict()
            ),
            "polarity_derived_by_check_2": False,
            "proposition_text_supplied": False,
        }


@dataclass(frozen=True, slots=True)
class GoalVerificationSpecification:
    """The authoritative obligation set and its explicit claim bindings.

    CHECK.2 never builds one of these from task prose.  It is supplied, bound to
    an exact task contract and an exact CHECK.1 reconciliation, and reconciled
    against the two authoritative sources before a single obligation is read.
    """

    task_contract_fingerprint: str
    check_1_reconciliation_fingerprint: str
    requirement_ledger_fingerprint: str
    obligations: tuple[GoalVerificationObligation, ...] = ()
    bindings: tuple[ObligationClaimBinding, ...] = ()
    schema_version: str = SPECIFICATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_sha256(self.task_contract_fingerprint, "task contract fingerprint")
        _require_sha256(
            self.check_1_reconciliation_fingerprint,
            "check 1 reconciliation fingerprint",
        )
        _require_sha256(
            self.requirement_ledger_fingerprint, "requirement ledger fingerprint"
        )
        _bounded_tuple(self.obligations, MAX_OBLIGATIONS, "obligations")
        _bounded_tuple(self.bindings, MAX_BINDINGS, "obligation claim bindings")
        if not all(
            type(item) is GoalVerificationObligation for item in self.obligations
        ):
            raise TypeError(
                "obligations must contain GoalVerificationObligation records"
            )
        if not all(type(item) is ObligationClaimBinding for item in self.bindings):
            raise TypeError("bindings must contain ObligationClaimBinding records")
        _validate_unique(
            tuple(item.obligation_id for item in self.obligations), "obligation id"
        )
        _validate_ordinals(self.obligations, "obligation")
        if self.schema_version != SPECIFICATION_SCHEMA_VERSION:
            raise ValueError("unsupported goal verification specification version")

    @property
    def ordered_obligations(self) -> tuple[GoalVerificationObligation, ...]:
        return tuple(sorted(self.obligations, key=_ordinal_sort_key))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "check_1_reconciliation_fingerprint": (
                self.check_1_reconciliation_fingerprint
            ),
            "requirement_ledger_fingerprint": self.requirement_ledger_fingerprint,
            "obligations": [item.as_dict() for item in self.ordered_obligations],
            "bindings": [
                item.as_dict()
                for item in sorted(
                    self.bindings,
                    key=lambda x: (x.obligation_id, x.proposition_id),
                )
            ],
            "derived_from_task_prose": False,
        }


def goal_verification_specification_fingerprint(
    specification: GoalVerificationSpecification,
) -> str:
    if type(specification) is not GoalVerificationSpecification:
        raise TypeError(
            "goal_verification_specification_fingerprint requires an exact "
            "GoalVerificationSpecification"
        )
    return _fingerprint(specification.as_dict())


# ── The review request ────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class GoalFidelityReviewRequest:
    """One CHECK.1 reconciliation, one specification and the frozen claims.

    Nothing here is a source byte, a diff, a repository root, a filesystem
    handle, a validation command or a model.  CHECK.2 needs none of them and has
    nowhere to put them.
    """

    reconciliation: PostRunReconciliation
    specification: GoalVerificationSpecification
    requirement_ledger: ExplicitRequirementLedger
    expected_task_contract_fingerprint: str
    expected_reconciliation_fingerprint: str
    expected_specification_fingerprint: str
    expected_requirement_ledger_fingerprint: str
    claim_assessments: tuple[ClaimAssessment, ...] = ()
    expected_claim_assessment_fingerprints: tuple[str, ...] = ()
    schema_version: str = REQUEST_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if type(self.reconciliation) is not PostRunReconciliation:
            raise TypeError("a review request requires an exact PostRunReconciliation")
        if type(self.specification) is not GoalVerificationSpecification:
            raise TypeError(
                "a review request requires an exact GoalVerificationSpecification"
            )
        if type(self.requirement_ledger) is not ExplicitRequirementLedger:
            raise TypeError(
                "a review request requires an exact ExplicitRequirementLedger"
            )
        for name in (
            "expected_task_contract_fingerprint",
            "expected_reconciliation_fingerprint",
            "expected_specification_fingerprint",
            "expected_requirement_ledger_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "))
        _bounded_tuple(
            self.claim_assessments, MAX_CLAIM_ASSESSMENTS, "claim assessments"
        )
        if not all(type(item) is ClaimAssessment for item in self.claim_assessments):
            raise TypeError("claim_assessments must contain ClaimAssessment records")
        _bounded_tuple(
            self.expected_claim_assessment_fingerprints,
            MAX_CLAIM_ASSESSMENTS,
            "expected claim assessment fingerprints",
        )
        for value in self.expected_claim_assessment_fingerprints:
            _require_sha256(value, "expected claim assessment fingerprint")
        if tuple(sorted(self.expected_claim_assessment_fingerprints)) != (
            self.expected_claim_assessment_fingerprints
        ):
            raise ValueError(
                "expected claim assessment fingerprints must be canonically ordered"
            )
        if self.schema_version != REQUEST_SCHEMA_VERSION:
            raise ValueError("unsupported goal fidelity review request version")

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "reconciliation_fingerprint": (
                self.reconciliation.reconciliation_fingerprint
            ),
            "specification_fingerprint": (
                goal_verification_specification_fingerprint(self.specification)
            ),
            "requirement_ledger_fingerprint": (
                explicit_requirement_ledger_fingerprint(self.requirement_ledger)
            ),
            "expected_task_contract_fingerprint": (
                self.expected_task_contract_fingerprint
            ),
            "expected_reconciliation_fingerprint": (
                self.expected_reconciliation_fingerprint
            ),
            "expected_specification_fingerprint": (
                self.expected_specification_fingerprint
            ),
            "expected_requirement_ledger_fingerprint": (
                self.expected_requirement_ledger_fingerprint
            ),
            "claim_assessment_fingerprints": sorted(
                item.assessment_fingerprint for item in self.claim_assessments
            ),
            "expected_claim_assessment_fingerprints": list(
                self.expected_claim_assessment_fingerprints
            ),
            "source_content_supplied": False,
            "diff_content_supplied": False,
            "repository_root_supplied": False,
            "analyzer_supplied": False,
        }


def goal_fidelity_request_fingerprint(request: GoalFidelityReviewRequest) -> str:
    if type(request) is not GoalFidelityReviewRequest:
        raise TypeError(
            "goal_fidelity_request_fingerprint requires an exact "
            "GoalFidelityReviewRequest"
        )
    return _fingerprint(request.as_dict())


# ── Authority and guardrails ──────────────────────────────────────────────────

def goal_fidelity_authority(
    *, semantic_goal_review_authority: bool
) -> dict[str, bool]:
    """One narrow authority, conditional on an assessable coherent request.

    ``final_success_authority`` is false in every outcome, including the one a
    reader would most like to treat as an answer: CHECK.1 reconciled and every
    required obligation satisfied.  Combining contractual and semantic state
    into an acceptance verdict is CHECK.3's job, and CHECK.3 does not exist.
    """
    return {
        "semantic_goal_review_authority": semantic_goal_review_authority,
        "post_run_reconciliation_authority": False,
        "final_success_authority": False,
        "run_verdict_authority": False,
        "merge_authority": False,
        "implementation_correctness_authority": False,
        "objective_truth_authority": False,
        "claim_assessment_authority": False,
        "conflict_adjudication_authority": False,
        "evidence_acquisition_authority": False,
        "evidence_verification_authority": False,
        "repository_read_authority": False,
        "repository_traversal_authority": False,
        "validation_execution_authority": False,
        "command_execution_authority": False,
        "worker_launch_authority": False,
        "patch_authority": False,
        "write_authority": False,
        "routing_authority": False,
        "planning_authority": False,
        "model_selection_authority": False,
        "provider_selection_authority": False,
        "response_synthesis_authority": False,
        "final_response_authority": False,
        "human_approval_required": True,
    }


def goal_fidelity_guardrails(
    *,
    check_1_gate_evaluated: bool,
    semantic_obligations_reconciled: bool,
    claim_assessments_consumed: bool,
    preservation_obligations_checked: bool,
    semantic_provenance_preserved: bool,
    post_run_state_binding_checked: bool,
) -> dict[str, bool]:
    """Honest performed-state: what ran, and the long list of what did not."""
    return {
        "check_1_gate_evaluated": check_1_gate_evaluated,
        "semantic_obligations_reconciled": semantic_obligations_reconciled,
        "claim_assessments_consumed": claim_assessments_consumed,
        "preservation_obligations_checked": preservation_obligations_checked,
        "semantic_provenance_preserved": semantic_provenance_preserved,
        "post_run_state_binding_checked": post_run_state_binding_checked,
        "source_content_read": False,
        "diff_content_read": False,
        "repository_traversed": False,
        "evidence_acquired": False,
        "evidence_reassessed": False,
        "validation_executed": False,
        "model_called": False,
        "network_called": False,
        "proposition_invented": False,
        "proposition_rewritten": False,
        "obligation_invented": False,
        "obligation_dropped": False,
        "polarity_inferred": False,
        "claim_status_reinterpreted": False,
        "semantic_status_upgraded": False,
        "conflict_resolved": False,
        "majority_computed": False,
        "confidence_computed": False,
        "worker_repaired": False,
        "patch_modified": False,
        "files_modified": False,
        "merge_performed": False,
        "final_success_declared": False,
        "run_verdict_declared": False,
        "objective_truth_asserted": False,
    }


# ── Result records ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class ObligationResult:
    """What the assessed evidence says about one explicit obligation.

    ``obligation_status`` is the polarity-mapped reading; ``claim_status`` is
    CLAIM.1's own word, preserved beside it so the mapping stays auditable and
    so no reader has to trust that the orientation was applied correctly.
    """

    obligation_id: str
    obligation_kind: str
    obligation_text_sha256: str
    source_requirement_id: str
    required: bool
    obligation_status: str
    ordinal: int | None = None
    preservation_obligation_kind: str | None = None
    proposition_id: str | None = None
    proposition_sha256: str | None = None
    proposition_text: str | None = None
    proposition_type: str | None = None
    proposition_scope: str | None = None
    claim_status: str | None = None
    claim_assessment_fingerprint: str | None = None
    semantic_basis: str | None = None
    satisfaction_polarity: str | None = None
    polarity_provenance: str | None = None
    post_run_state_binding: str | None = None
    reasons: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _bounded_identifier(self.obligation_id, "result obligation id")
        if self.obligation_kind not in OBLIGATION_KINDS:
            raise ValueError(f"unsupported obligation kind: {self.obligation_kind!r}")
        _require_sha256(self.obligation_text_sha256, "obligation text digest")
        _bounded_identifier(self.source_requirement_id, "result source requirement id")
        if not isinstance(self.required, bool):
            raise TypeError("result required must be a bool")
        if self.obligation_status not in OBLIGATION_STATUSES:
            raise ValueError(
                f"unsupported obligation status: {self.obligation_status!r}"
            )
        if self.ordinal is not None and (
            not isinstance(self.ordinal, int) or isinstance(self.ordinal, bool)
        ):
            raise TypeError("result ordinal must be an integer")
        if (
            self.preservation_obligation_kind is not None
            and self.preservation_obligation_kind not in PRESERVATION_OBLIGATION_KINDS
        ):
            raise ValueError("unsupported preservation obligation kind")
        _bounded_identifier(self.proposition_id, "result proposition id", optional=True)
        _require_sha256(
            self.proposition_sha256, "result proposition digest", optional=True
        )
        if self.proposition_text is not None:
            if not isinstance(self.proposition_text, str):
                raise TypeError("result proposition text must be a string")
            if len(self.proposition_text) > MAX_PROPOSITION_TEXT_CHARS:
                raise ValueError("result proposition text exceeds its finite bound")
        _require_sha256(
            self.claim_assessment_fingerprint,
            "result claim assessment fingerprint",
            optional=True,
        )
        if self.semantic_basis is not None and self.semantic_basis not in (
            BASIS_ANALYZER_ASSESSED,
            BASIS_NOT_ESTABLISHED,
        ):
            raise ValueError(
                "an obligation result rests on analyzer-assessed semantic "
                "relations; aggregation does not change that"
            )
        if (
            self.satisfaction_polarity is not None
            and self.satisfaction_polarity not in SATISFACTION_POLARITIES
        ):
            raise ValueError("unsupported result satisfaction polarity")
        if (
            self.polarity_provenance is not None
            and self.polarity_provenance not in POLARITY_PROVENANCES
        ):
            raise ValueError("unsupported result polarity provenance")
        if (
            self.post_run_state_binding is not None
            and self.post_run_state_binding not in STATE_BINDING_STATES
        ):
            raise ValueError("unsupported result post-run state binding")
        _ordered_vocabulary(self.reasons, OBLIGATION_RESULT_REASONS, "result reason")
        if self.obligation_status in DETERMINED_OBLIGATION_STATUSES:
            if self.semantic_basis != BASIS_ANALYZER_ASSESSED:
                raise ValueError(
                    "a determined obligation states its analyzer-assessed basis"
                )
            if self.satisfaction_polarity is None or self.polarity_provenance is None:
                raise ValueError(
                    "a determined obligation states the supplied orientation it used"
                )
            if self.claim_status is None or self.claim_assessment_fingerprint is None:
                raise ValueError(
                    "a determined obligation names the claim assessment it read"
                )

    @property
    def determined(self) -> bool:
        return self.obligation_status in DETERMINED_OBLIGATION_STATUSES

    @property
    def goal_proven(self) -> bool:
        """Always false, including for ``satisfied_by_assessed_evidence``."""
        return False

    def as_dict(self) -> dict[str, Any]:
        return {
            "obligation_id": self.obligation_id,
            "obligation_kind": self.obligation_kind,
            "obligation_text_sha256": self.obligation_text_sha256,
            "source_requirement_id": self.source_requirement_id,
            "preservation_obligation_kind": self.preservation_obligation_kind,
            "required": self.required,
            "ordinal": self.ordinal,
            "obligation_status": self.obligation_status,
            "proposition_id": self.proposition_id,
            "proposition_sha256": self.proposition_sha256,
            "proposition_text": self.proposition_text,
            "proposition_type": self.proposition_type,
            "proposition_scope": self.proposition_scope,
            "claim_status": self.claim_status,
            "claim_assessment_fingerprint": self.claim_assessment_fingerprint,
            "semantic_basis": self.semantic_basis,
            "satisfaction_polarity": self.satisfaction_polarity,
            "polarity_provenance": self.polarity_provenance,
            "post_run_state_binding": self.post_run_state_binding,
            "reasons": list(self.reasons),
            "goal_proven": self.goal_proven,
        }


@dataclass(frozen=True, slots=True)
class ExecutionReconciliationSummary:
    """The CHECK.1 facts CHECK.2 carries forward without re-deciding them.

    Its blocking reasons survive downstream verbatim: a semantic review that
    could drop them would be a laundering route, and there is no field here that
    could weaken one.
    """

    check_1_status: str
    check_1_reconciliation_fingerprint: str
    execution_authorization_fingerprint: str
    final_state_fingerprint: str
    validation_coverage_complete: bool
    validated_state_current: bool
    check_1_inconsistencies: tuple[str, ...] = ()
    check_1_unresolved_requirements: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.check_1_status not in CHECK_1_ENTRY_POLICY:
            raise ValueError(f"unsupported CHECK.1 status: {self.check_1_status!r}")
        _require_sha256(
            self.check_1_reconciliation_fingerprint,
            "check 1 reconciliation fingerprint",
        )
        _require_sha256(
            self.execution_authorization_fingerprint,
            "execution authorization fingerprint",
        )
        _require_sha256(self.final_state_fingerprint, "final state fingerprint")
        for value, label in (
            (self.validation_coverage_complete, "validation_coverage_complete"),
            (self.validated_state_current, "validated_state_current"),
        ):
            if not isinstance(value, bool):
                raise TypeError(f"{label} must be a bool")
        for values, label in (
            (self.check_1_inconsistencies, "check 1 inconsistency"),
            (self.check_1_unresolved_requirements, "check 1 unresolved requirement"),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{label}s must be a tuple")
            for item in values:
                _bounded_identifier(item, label)

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_1_status": self.check_1_status,
            "check_1_reconciliation_fingerprint": (
                self.check_1_reconciliation_fingerprint
            ),
            "execution_authorization_fingerprint": (
                self.execution_authorization_fingerprint
            ),
            "final_state_fingerprint": self.final_state_fingerprint,
            "validation_coverage_complete": self.validation_coverage_complete,
            "validated_state_current": self.validated_state_current,
            "check_1_inconsistencies": list(self.check_1_inconsistencies),
            "check_1_unresolved_requirements": list(
                self.check_1_unresolved_requirements
            ),
            "check_1_severity_weakened": False,
        }


# ── The assessment ────────────────────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class GoalFidelityAssessment:
    """What the assessed semantic evidence says about each explicit obligation.

    Read ``status`` as a statement about *the review*, ``review_mode`` as what
    CHECK.1 permitted it to mean, and ``semantic_basis`` next to every
    determined obligation.  ``assessed`` plus one violated preservation
    obligation is a completed review that found a violation; it is not a
    success, and there is no field here that could say a run succeeded.

    ``satisfied_obligations`` and ``violated_obligations`` are lists of
    obligation identities, never quantities.  Nothing in this contract compares
    one against the other.
    """

    status: str
    review_mode: str
    task_contract_fingerprint: str
    check_1_reconciliation_fingerprint: str
    verification_specification_fingerprint: str
    requirement_ledger_fingerprint: str
    request_fingerprint: str
    execution_reconciliation: ExecutionReconciliationSummary
    obligation_results: tuple[ObligationResult, ...] = ()
    satisfied_obligations: tuple[str, ...] = ()
    violated_obligations: tuple[str, ...] = ()
    unresolved_obligations: tuple[str, ...] = ()
    unbound_claim_assessments: tuple[str, ...] = ()
    semantic_basis: str = BASIS_NOT_ESTABLISHED
    unresolved_requirements: tuple[str, ...] = ()
    reasons: tuple[str, ...] = ()
    inconsistencies: tuple[str, ...] = ()
    schema_version: str = RESULT_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.status not in GOAL_FIDELITY_STATUSES:
            raise ValueError(f"unsupported goal fidelity status: {self.status!r}")
        if self.review_mode not in REVIEW_MODES:
            raise ValueError(f"unsupported review mode: {self.review_mode!r}")
        for name in (
            "task_contract_fingerprint",
            "check_1_reconciliation_fingerprint",
            "verification_specification_fingerprint",
            "requirement_ledger_fingerprint",
            "request_fingerprint",
        ):
            _require_sha256(getattr(self, name), name.replace("_", " "))
        if type(self.execution_reconciliation) is not ExecutionReconciliationSummary:
            raise TypeError(
                "execution_reconciliation must be an ExecutionReconciliationSummary"
            )
        _bounded_tuple(
            self.obligation_results, MAX_OBLIGATION_RESULTS, "obligation results"
        )
        if not all(type(item) is ObligationResult for item in self.obligation_results):
            raise TypeError("obligation_results must contain ObligationResult records")
        identities = tuple(item.obligation_id for item in self.obligation_results)
        _validate_unique(identities, "obligation result id")
        for values, label in (
            (self.satisfied_obligations, "satisfied obligation"),
            (self.violated_obligations, "violated obligation"),
            (self.unresolved_obligations, "unresolved obligation"),
            (self.unbound_claim_assessments, "unbound claim proposition"),
        ):
            if not isinstance(values, tuple):
                raise TypeError(f"{label}s must be a tuple")
            _validate_unique(values, label)
            for item in values:
                _bounded_identifier(item, label)
            if tuple(sorted(values)) != values:
                raise ValueError(f"{label}s must be canonically ordered")
        if self.semantic_basis not in (BASIS_ANALYZER_ASSESSED, BASIS_NOT_ESTABLISHED):
            raise ValueError(
                "a goal fidelity assessment rests on analyzer-assessed semantic "
                "relations; it is never deterministically verified"
            )
        _ordered_vocabulary(
            self.unresolved_requirements,
            GOAL_FIDELITY_UNRESOLVED_REQUIREMENTS,
            "unresolved requirement",
        )
        _ordered_vocabulary(self.reasons, GOAL_FIDELITY_REASONS, "reason")
        _ordered_vocabulary(
            self.inconsistencies, GOAL_FIDELITY_INCONSISTENCIES, "inconsistency"
        )

        # -- Partition fidelity: every result lands in exactly one bucket ------
        expected_satisfied = tuple(
            sorted(
                item.obligation_id
                for item in self.obligation_results
                if item.obligation_status == OBLIGATION_SATISFIED
            )
        )
        expected_violated = tuple(
            sorted(
                item.obligation_id
                for item in self.obligation_results
                if item.obligation_status == OBLIGATION_VIOLATED
            )
        )
        expected_unresolved = tuple(
            sorted(
                item.obligation_id
                for item in self.obligation_results
                if item.obligation_status not in DETERMINED_OBLIGATION_STATUSES
            )
        )
        if self.satisfied_obligations != expected_satisfied:
            raise ValueError("satisfied obligations must mirror the obligation results")
        if self.violated_obligations != expected_violated:
            raise ValueError("violated obligations must mirror the obligation results")
        if self.unresolved_obligations != expected_unresolved:
            raise ValueError("unresolved obligations must mirror the obligation results")

        # -- Anti-rescue and anti-laundering invariants ------------------------
        if self.review_mode == REVIEW_BLOCKED and (
            self.satisfied_obligations or self.violated_obligations
        ):
            raise ValueError(
                "a blocked reconciliation yields no determined obligation state"
            )
        if self.status == STATUS_BLOCKED and self.review_mode != REVIEW_BLOCKED:
            raise ValueError("a blocked assessment states a blocked review mode")
        if self.status == STATUS_INCONSISTENT_INPUT:
            if not self.inconsistencies:
                raise ValueError("an unusable request states its inconsistency")
            if self.obligation_results:
                raise ValueError(
                    "a refused request reconciles no obligation, because the "
                    "specification that names them was refused"
                )
            if self.semantic_basis != BASIS_NOT_ESTABLISHED:
                raise ValueError("a refused request establishes no semantic basis")
        elif self.inconsistencies:
            raise ValueError("an assessed request carries no inconsistency")
        if self.status == STATUS_ASSESSED and self.review_mode != REVIEW_ASSESSABLE:
            raise ValueError("only an assessable review reaches 'assessed'")
        if UNRESOLVED_RUN_VERDICT not in self.unresolved_requirements:
            raise ValueError(
                "every goal fidelity assessment leaves the run verdict outstanding"
            )
        if UNRESOLVED_HUMAN_REVIEW not in self.unresolved_requirements:
            raise ValueError(
                "every goal fidelity assessment leaves human review outstanding"
            )
        if self.schema_version != RESULT_SCHEMA_VERSION:
            raise ValueError("unsupported goal fidelity assessment schema version")

    # -- Named views over the single canonical result list --------------------

    def _by_kind(self, kind: str) -> tuple[ObligationResult, ...]:
        return tuple(
            item for item in self.obligation_results if item.obligation_kind == kind
        )

    @property
    def goal_obligation_results(self) -> tuple[ObligationResult, ...]:
        return self._by_kind(OBLIGATION_KIND_GOAL)

    @property
    def preservation_obligation_results(self) -> tuple[ObligationResult, ...]:
        return self._by_kind(OBLIGATION_KIND_PRESERVATION)

    @property
    def constraint_obligation_results(self) -> tuple[ObligationResult, ...]:
        return self._by_kind(OBLIGATION_KIND_CONSTRAINT)

    def result_for(self, obligation_id: str) -> ObligationResult | None:
        for item in self.obligation_results:
            if item.obligation_id == obligation_id:
                return item
        return None

    # -- The answers this phase never gives -----------------------------------

    @property
    def semantic_goal_review_authority(self) -> bool:
        return (
            self.review_mode == REVIEW_ASSESSABLE
            and self.status != STATUS_INCONSISTENT_INPUT
        )

    @property
    def final_success_authority(self) -> bool:
        """Always false, including when every required obligation is satisfied."""
        return False

    @property
    def run_verdict_authority(self) -> bool:
        return False

    @property
    def merge_authority(self) -> bool:
        return False

    @property
    def objective_truth_asserted(self) -> bool:
        return False

    @property
    def goal_proven(self) -> bool:
        return False

    @property
    def check_3_required(self) -> bool:
        """CHECK.2 never discharges the run acceptance verdict."""
        return True

    def _identity(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "phase_id": PHASE_ID,
            "status": self.status,
            "review_mode": self.review_mode,
            "task_contract_fingerprint": self.task_contract_fingerprint,
            "check_1_reconciliation_fingerprint": (
                self.check_1_reconciliation_fingerprint
            ),
            "verification_specification_fingerprint": (
                self.verification_specification_fingerprint
            ),
            "requirement_ledger_fingerprint": self.requirement_ledger_fingerprint,
            "request_fingerprint": self.request_fingerprint,
            "execution_reconciliation": self.execution_reconciliation.as_dict(),
            "obligation_results": [item.as_dict() for item in self.obligation_results],
            "satisfied_obligations": list(self.satisfied_obligations),
            "violated_obligations": list(self.violated_obligations),
            "unresolved_obligations": list(self.unresolved_obligations),
            "unbound_claim_assessments": list(self.unbound_claim_assessments),
            "semantic_basis": self.semantic_basis,
            "unresolved_requirements": list(self.unresolved_requirements),
            "reasons": list(self.reasons),
            "inconsistencies": list(self.inconsistencies),
        }

    @property
    def assessment_fingerprint(self) -> str:
        """Deterministic identity.  No timestamp, no counter, no random token."""
        return _fingerprint(self._identity())

    def as_dict(self) -> dict[str, Any]:
        payload = dict(self._identity())
        payload["assessment_fingerprint"] = self.assessment_fingerprint
        payload["satisfied_meaning"] = SATISFIED_MEANING
        payload["violated_meaning"] = VIOLATED_MEANING
        payload["assessed_meaning"] = ASSESSED_MEANING
        payload["review_mode_meaning"] = REVIEW_MODE_MEANING[self.review_mode]
        payload["goal_proven"] = self.goal_proven
        payload["objective_truth_asserted"] = self.objective_truth_asserted
        payload["implementation_correctness_asserted"] = False
        payload["run_verdict_produced"] = False
        payload["semantic_evidence_reassessed"] = False
        payload["obligations_derived_by_check_2"] = False
        payload["propositions_derived_by_check_2"] = False
        payload["polarity_derived_by_check_2"] = False
        payload["authority"] = goal_fidelity_authority(
            semantic_goal_review_authority=self.semantic_goal_review_authority
        )
        payload["guardrails"] = goal_fidelity_guardrails(
            check_1_gate_evaluated=CHECK2_CHECK_1_GATE_EVALUATED in self.reasons,
            semantic_obligations_reconciled=(
                CHECK2_OBLIGATION_COVERAGE_VERIFIED in self.reasons
            ),
            claim_assessments_consumed=(
                CHECK2_CLAIM_ASSESSMENTS_CONSUMED in self.reasons
            ),
            preservation_obligations_checked=(
                CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED in self.reasons
            ),
            semantic_provenance_preserved=(
                CHECK2_SEMANTIC_BASIS_PRESERVED in self.reasons
            ),
            post_run_state_binding_checked=(
                CHECK2_POST_RUN_STATE_BINDING_CHECKED in self.reasons
            ),
        )
        return payload


def render_goal_fidelity_assessment_json(assessment: GoalFidelityAssessment) -> str:
    """Render one goal-fidelity assessment as deterministic JSON."""
    if type(assessment) is not GoalFidelityAssessment:
        raise TypeError(
            "render_goal_fidelity_assessment_json requires an exact "
            "GoalFidelityAssessment"
        )
    return json.dumps(
        assessment.as_dict(), indent=2, ensure_ascii=False, sort_keys=False
    )


# ── Upstream declaration defects ──────────────────────────────────────────────

def _upstream_defects(request: GoalFidelityReviewRequest) -> set[str]:
    """Refuse an upstream record that already claims a power it cannot have.

    CHECK.1 and CLAIM.1 both expose their denials as properties rather than
    fields, so none of these can fire today.  They are checked anyway: a future
    contract change that made one settable would be caught here rather than
    silently inherited.
    """
    codes: set[str] = set()
    reconciliation = request.reconciliation
    if (
        reconciliation.semantic_goal_review_authority
        or reconciliation.implementation_correctness_authority
        or reconciliation.final_success_authority
    ):
        codes.add(INCONSISTENT_UPSTREAM_AUTHORITY)
    reconciliation_payload = reconciliation.as_dict()
    reconciliation_guardrails = reconciliation_payload.get("guardrails") or {}
    for guardrail in (
        "semantic_goal_review_performed",
        "model_called",
        "source_content_read",
        "validation_executed",
        "final_success_declared",
        "merge_performed",
    ):
        if reconciliation_guardrails.get(guardrail):
            codes.add(INCONSISTENT_UPSTREAM_GUARDRAIL)

    for claim in request.claim_assessments:
        if claim.final_claim_authority or claim.objective_truth_asserted:
            codes.add(INCONSISTENT_UPSTREAM_AUTHORITY)
        claim_payload = claim.as_dict()
        claim_guardrails = claim_payload.get("guardrails") or {}
        for guardrail in (
            "semantic_status_upgraded",
            "proposition_rewritten",
            "conflict_resolved",
            "objective_truth_determined",
            "model_called",
            "evidence_relations_reinterpreted",
        ):
            if claim_guardrails.get(guardrail):
                codes.add(INCONSISTENT_UPSTREAM_GUARDRAIL)
        if claim.assessment_status == CLAIM_INCONSISTENT_INPUT:
            continue
        if claim.semantic_basis != BASIS_ANALYZER_ASSESSED:
            codes.add(INCONSISTENT_SEMANTIC_BASIS)
    return codes


# ── Binding and coverage ──────────────────────────────────────────────────────

def _binding_inconsistencies(request: GoalFidelityReviewRequest) -> set[str]:
    """Re-derive every identity the caller claimed, and trust none of them."""
    codes: set[str] = set()
    reconciliation = request.reconciliation
    specification = request.specification
    ledger = request.requirement_ledger

    reconciliation_fingerprint = reconciliation.reconciliation_fingerprint
    specification_fingerprint = goal_verification_specification_fingerprint(
        specification
    )
    ledger_fingerprint = explicit_requirement_ledger_fingerprint(ledger)

    if request.expected_reconciliation_fingerprint != reconciliation_fingerprint:
        codes.add(INCONSISTENT_RECONCILIATION_FINGERPRINT)
    if specification.check_1_reconciliation_fingerprint != reconciliation_fingerprint:
        codes.add(INCONSISTENT_SPECIFICATION_RUN_BINDING)
    if request.expected_specification_fingerprint != specification_fingerprint:
        codes.add(INCONSISTENT_SPECIFICATION_FINGERPRINT)
    if request.expected_requirement_ledger_fingerprint != ledger_fingerprint:
        codes.add(INCONSISTENT_LEDGER_FINGERPRINT)
    if specification.requirement_ledger_fingerprint != ledger_fingerprint:
        codes.add(INCONSISTENT_LEDGER_FINGERPRINT)

    task_fingerprint = reconciliation.task_contract_fingerprint
    if request.expected_task_contract_fingerprint != task_fingerprint:
        codes.add(INCONSISTENT_TASK_CONTRACT_FINGERPRINT)
    if specification.task_contract_fingerprint != task_fingerprint:
        codes.add(INCONSISTENT_SPECIFICATION_TASK_BINDING)
    if ledger.task_contract_fingerprint != task_fingerprint:
        codes.add(INCONSISTENT_LEDGER_TASK_BINDING)

    proposition_ids = tuple(
        item.proposition_id for item in request.claim_assessments
    )
    seen: set[str] = set()
    for proposition_id in proposition_ids:
        if proposition_id in seen:
            codes.add(INCONSISTENT_CLAIM_DUPLICATE)
        seen.add(proposition_id)
    supplied_fingerprints = tuple(
        sorted(item.assessment_fingerprint for item in request.claim_assessments)
    )
    if request.expected_claim_assessment_fingerprints and (
        request.expected_claim_assessment_fingerprints != supplied_fingerprints
    ):
        codes.add(INCONSISTENT_CLAIM_FINGERPRINT)
    return codes


def _claims_by_proposition(
    request: GoalFidelityReviewRequest,
) -> dict[str, ClaimAssessment]:
    return {item.proposition_id: item for item in request.claim_assessments}


def _bindings_by_obligation(
    specification: GoalVerificationSpecification,
) -> dict[str, tuple[ObligationClaimBinding, ...]]:
    grouped: dict[str, list[ObligationClaimBinding]] = {}
    for binding in sorted(
        specification.bindings, key=lambda x: (x.obligation_id, x.proposition_id)
    ):
        grouped.setdefault(binding.obligation_id, []).append(binding)
    return {key: tuple(value) for key, value in grouped.items()}


def _claim_binding_inconsistencies(
    request: GoalFidelityReviewRequest,
    claims: dict[str, ClaimAssessment],
) -> set[str]:
    """A bound claim must be exactly the claim the binding named."""
    codes: set[str] = set()
    obligation_ids = {
        item.obligation_id for item in request.specification.obligations
    }
    final_state = request.reconciliation.final_state_binding.final_state_fingerprint
    for binding in request.specification.bindings:
        if binding.obligation_id not in obligation_ids:
            codes.add(INCONSISTENT_BINDING_UNKNOWN_OBLIGATION)
        state_binding = binding.post_run_state_binding
        if state_binding is not None and (
            state_binding.final_state_fingerprint != final_state
        ):
            codes.add(INCONSISTENT_POST_RUN_STATE_BINDING)
        claim = claims.get(binding.proposition_id)
        if claim is None:
            continue
        if binding.proposition_sha256 != claim.proposition_sha256:
            codes.add(INCONSISTENT_CLAIM_PROPOSITION_BINDING)
        if binding.expected_claim_assessment_fingerprint != (
            claim.assessment_fingerprint
        ):
            codes.add(INCONSISTENT_CLAIM_FINGERPRINT)
        if binding.expected_evidence_set_fingerprint is not None and (
            binding.expected_evidence_set_fingerprint != claim.evidence_set_fingerprint
        ):
            codes.add(INCONSISTENT_CLAIM_EVIDENCE_SET_BINDING)
    return codes


def _obligation_source_inconsistencies(
    request: GoalFidelityReviewRequest,
) -> set[str]:
    """No obligation invention, no obligation loss, no obligation widening.

    Preservation obligations are reconciled against CHECK.1's own typed
    preservation findings, which the caller cannot mint.  Goal and constraint
    obligations are reconciled against the explicit requirement ledger, which is
    bound to the same task contract by fingerprint.
    """
    codes: set[str] = set()
    specification = request.specification
    preserved = {
        item.obligation_id: item
        for item in request.reconciliation.preservation_findings
    }
    ledger_index = {
        item.requirement_id: item for item in request.requirement_ledger.requirements
    }

    claimed_sources: set[str] = set()
    for obligation in specification.obligations:
        source_id = obligation.source_requirement_id
        if source_id in claimed_sources:
            codes.add(INCONSISTENT_OBLIGATION_WIDENED)
        claimed_sources.add(source_id)

        if obligation.obligation_kind == OBLIGATION_KIND_PRESERVATION:
            finding = preserved.get(source_id)
            if finding is None:
                codes.add(INCONSISTENT_OBLIGATION_WIDENED)
                continue
            if obligation.obligation_text_sha256 != finding.text_sha256:
                codes.add(INCONSISTENT_OBLIGATION_SOURCE_TEXT)
            if obligation.preservation_obligation_kind != finding.kind:
                codes.add(INCONSISTENT_OBLIGATION_SOURCE_KIND)
            if not obligation.required:
                codes.add(INCONSISTENT_OBLIGATION_SOURCE_KIND)
            continue

        requirement = ledger_index.get(source_id)
        if requirement is None:
            codes.add(INCONSISTENT_OBLIGATION_WIDENED)
            continue
        if obligation.obligation_text_sha256 != requirement.requirement_text_sha256:
            codes.add(INCONSISTENT_OBLIGATION_SOURCE_TEXT)
        if obligation.obligation_kind != requirement.requirement_kind:
            codes.add(INCONSISTENT_OBLIGATION_SOURCE_KIND)
        if obligation.required != requirement.required:
            codes.add(INCONSISTENT_OBLIGATION_SOURCE_KIND)

    represented_preservation = {
        item.source_requirement_id
        for item in specification.obligations
        if item.obligation_kind == OBLIGATION_KIND_PRESERVATION
    }
    for obligation_id in preserved:
        if obligation_id not in represented_preservation:
            codes.add(INCONSISTENT_PRESERVATION_OBLIGATION_DROPPED)

    represented_requirements = {
        item.source_requirement_id
        for item in specification.obligations
        if item.obligation_kind != OBLIGATION_KIND_PRESERVATION
    }
    for requirement in request.requirement_ledger.requirements:
        if not requirement.required:
            continue
        if requirement.requirement_id not in represented_requirements:
            codes.add(INCONSISTENT_GOAL_OBLIGATION_DROPPED)
    return codes


# ── One obligation ────────────────────────────────────────────────────────────

def _map_claim_status(claim: ClaimAssessment, polarity: str) -> str:
    """Look the mapping up; never decide it.

    Unresolved CLAIM.1 states are looked up first and are polarity-independent,
    so no orientation can turn ``conflicting_evidence`` into an answer.
    """
    unresolved = _UNRESOLVED_CLAIM_MAP.get(claim.assessment_status)
    if unresolved is not None:
        return unresolved
    return _POLARITY_MAP[polarity][claim.assessment_status]


def _obligation_result(
    obligation: GoalVerificationObligation,
    bindings: tuple[ObligationClaimBinding, ...],
    claims: dict[str, ClaimAssessment],
    *,
    review_mode: str,
) -> ObligationResult:
    reasons: set[str] = set()
    if not obligation.required:
        reasons.add(OBLIGATION_REASON_OPTIONAL)
    if review_mode == REVIEW_DIAGNOSTIC_ONLY:
        reasons.add(OBLIGATION_REASON_DIAGNOSTIC_ONLY)

    binding: ObligationClaimBinding | None = None
    claim: ClaimAssessment | None = None
    status: str | None = None

    if not bindings:
        status = OBLIGATION_MISSING_CLAIM
        reasons.add(OBLIGATION_REASON_NO_BINDING)
    elif bindings[1:]:
        status = OBLIGATION_COMPOSITE_UNSUPPORTED
        reasons.add(OBLIGATION_REASON_MULTIPLE_BINDINGS)
    else:
        binding = bindings[0]
        claim = claims.get(binding.proposition_id)
        if claim is None:
            status = OBLIGATION_MISSING_CLAIM
            reasons.add(OBLIGATION_REASON_CLAIM_ABSENT)
        else:
            reasons.add(OBLIGATION_REASON_CLAIM_BOUND)
            if binding.satisfaction_polarity is None:
                reasons.add(OBLIGATION_REASON_POLARITY_ABSENT)
            if binding.polarity_provenance is None:
                reasons.add(OBLIGATION_REASON_POLARITY_PROVENANCE_ABSENT)
            if not binding.polarity_established:
                status = OBLIGATION_BINDING_INVALID
            elif claim.assessment_status == CLAIM_INCONSISTENT_INPUT:
                status = OBLIGATION_BINDING_INVALID
                reasons.add(OBLIGATION_REASON_CLAIM_REFUSED)
            else:
                status = _map_claim_status(claim, binding.satisfaction_polarity)
            if binding.post_run_state_binding is None:
                reasons.add(OBLIGATION_REASON_FINAL_STATE_UNBOUND)
            else:
                reasons.add(OBLIGATION_REASON_FINAL_STATE_BOUND)

    state_binding: str | None = None
    if binding is not None and claim is not None:
        state_binding = (
            STATE_BINDING_UNAVAILABLE
            if binding.post_run_state_binding is None
            else STATE_BINDING_BOUND
        )

    if review_mode == REVIEW_BLOCKED:
        status = OBLIGATION_BLOCKED_BY_RECONCILIATION
        reasons.add(OBLIGATION_REASON_RECONCILIATION_BLOCKED)

    return ObligationResult(
        obligation_id=obligation.obligation_id,
        obligation_kind=obligation.obligation_kind,
        obligation_text_sha256=obligation.obligation_text_sha256,
        source_requirement_id=obligation.source_requirement_id,
        required=obligation.required,
        obligation_status=status,
        ordinal=obligation.ordinal,
        preservation_obligation_kind=obligation.preservation_obligation_kind,
        proposition_id=None if claim is None else claim.proposition_id,
        proposition_sha256=None if claim is None else claim.proposition_sha256,
        proposition_text=None if claim is None else claim.proposition_text,
        proposition_type=None if claim is None else claim.proposition_type,
        proposition_scope=None if claim is None else claim.proposition_scope,
        claim_status=None if claim is None else claim.assessment_status,
        claim_assessment_fingerprint=(
            None if claim is None else claim.assessment_fingerprint
        ),
        semantic_basis=None if claim is None else claim.semantic_basis,
        satisfaction_polarity=(
            None if binding is None else binding.satisfaction_polarity
        ),
        polarity_provenance=None if binding is None else binding.polarity_provenance,
        post_run_state_binding=state_binding,
        reasons=_ordered_codes(reasons, OBLIGATION_RESULT_REASONS),
    )


def _execution_summary(
    reconciliation: PostRunReconciliation,
) -> ExecutionReconciliationSummary:
    binding = reconciliation.final_state_binding
    return ExecutionReconciliationSummary(
        check_1_status=reconciliation.status,
        check_1_reconciliation_fingerprint=reconciliation.reconciliation_fingerprint,
        execution_authorization_fingerprint=(
            reconciliation.execution_authorization_fingerprint
        ),
        final_state_fingerprint=binding.final_state_fingerprint,
        validation_coverage_complete=binding.validation_coverage_complete,
        validated_state_current=binding.validated_state_current,
        check_1_inconsistencies=reconciliation.inconsistencies,
        check_1_unresolved_requirements=reconciliation.unresolved_requirements,
    )


# ── The review ────────────────────────────────────────────────────────────────

def review_goal_fidelity(
    request: GoalFidelityReviewRequest,
) -> GoalFidelityAssessment:
    """Reconcile explicit obligations against frozen CLAIM.1 assessments.

    The result states what the already-assessed semantic evidence says about
    each explicit obligation, under the review mode CHECK.1's objective
    reconciliation permits.  It never states that the run succeeded, that the
    implementation is correct, or that the change may be accepted, and it always
    leaves the run verdict (CHECK.3) and human review outstanding.
    """
    if type(request) is not GoalFidelityReviewRequest:
        raise TypeError(
            "review_goal_fidelity requires an exact GoalFidelityReviewRequest"
        )

    reconciliation = request.reconciliation
    specification = request.specification
    claims = _claims_by_proposition(request)
    request_fingerprint = goal_fidelity_request_fingerprint(request)
    summary = _execution_summary(reconciliation)
    review_mode = CHECK_1_ENTRY_POLICY[reconciliation.status]

    reasons: set[str] = {
        CHECK2_RECONCILIATION_BOUND,
        CHECK2_CHECK_1_GATE_EVALUATED,
        CHECK2_SPECIFICATION_BOUND,
        CHECK2_REQUIREMENT_LEDGER_BOUND,
        CHECK2_NO_SEMANTIC_REANALYSIS_PERFORMED,
        CHECK2_NO_CONFLICT_ADJUDICATED,
        CHECK2_NO_MAJORITY_COMPUTED,
        CHECK2_NO_RUN_VERDICT_PRODUCED,
    }

    inconsistencies = _binding_inconsistencies(request)
    inconsistencies.update(_upstream_defects(request))
    inconsistencies.update(_claim_binding_inconsistencies(request, claims))
    inconsistencies.update(_obligation_source_inconsistencies(request))
    if reconciliation.status == CHECK_1_INCONSISTENT_INPUT:
        inconsistencies.add(INCONSISTENT_CHECK_1_INPUT_UNUSABLE)

    if inconsistencies:
        reasons.add(CHECK2_INPUT_REJECTED)
        return GoalFidelityAssessment(
            status=STATUS_INCONSISTENT_INPUT,
            review_mode=REVIEW_BLOCKED,
            task_contract_fingerprint=reconciliation.task_contract_fingerprint,
            check_1_reconciliation_fingerprint=(
                reconciliation.reconciliation_fingerprint
            ),
            verification_specification_fingerprint=(
                goal_verification_specification_fingerprint(specification)
            ),
            requirement_ledger_fingerprint=(
                explicit_requirement_ledger_fingerprint(request.requirement_ledger)
            ),
            request_fingerprint=request_fingerprint,
            execution_reconciliation=summary,
            semantic_basis=BASIS_NOT_ESTABLISHED,
            unresolved_requirements=_ordered_codes(
                {
                    UNRESOLVED_UPSTREAM_INPUT,
                    UNRESOLVED_RUN_VERDICT,
                    UNRESOLVED_HUMAN_REVIEW,
                },
                GOAL_FIDELITY_UNRESOLVED_REQUIREMENTS,
            ),
            reasons=_ordered_codes(reasons, GOAL_FIDELITY_REASONS),
            inconsistencies=_ordered_codes(
                inconsistencies, GOAL_FIDELITY_INCONSISTENCIES
            ),
        )

    grouped = _bindings_by_obligation(specification)
    results = tuple(
        _obligation_result(
            obligation,
            grouped.get(obligation.obligation_id, ()),
            claims,
            review_mode=review_mode,
        )
        for obligation in specification.ordered_obligations
    )

    bound_propositions = {
        binding.proposition_id for binding in specification.bindings
    }
    unbound = tuple(
        sorted(
            proposition_id
            for proposition_id in claims
            if proposition_id not in bound_propositions
        )
    )

    consumed = tuple(item for item in results if item.claim_assessment_fingerprint)
    reasons.add(CHECK2_OBLIGATION_COVERAGE_VERIFIED)
    reasons.add(CHECK2_EXECUTION_SEVERITY_PRESERVED)
    reasons.add(CHECK2_POST_RUN_STATE_BINDING_CHECKED)
    if any(
        item.obligation_kind == OBLIGATION_KIND_PRESERVATION for item in results
    ):
        reasons.add(CHECK2_PRESERVATION_OBLIGATIONS_RECONCILED)
    if consumed:
        reasons.add(CHECK2_CLAIM_ASSESSMENTS_CONSUMED)
        reasons.add(CHECK2_CLAIM_STATUS_PRESERVED)
        reasons.add(CHECK2_SEMANTIC_BASIS_PRESERVED)
    if any(item.satisfaction_polarity is not None for item in results):
        reasons.add(CHECK2_POLARITY_APPLIED_AS_SUPPLIED)
    if unbound:
        reasons.add(CHECK2_UNBOUND_CLAIM_ASSESSMENTS_IGNORED)

    unresolved: set[str] = {UNRESOLVED_RUN_VERDICT, UNRESOLVED_HUMAN_REVIEW}
    if review_mode == REVIEW_BLOCKED:
        unresolved.add(UNRESOLVED_EXECUTION_CONTRACT_VIOLATION)
    if review_mode == REVIEW_DIAGNOSTIC_ONLY:
        unresolved.add(UNRESOLVED_EXECUTION_RECONCILIATION)

    required_gap = False
    state_binding_gap = False
    for item in results:
        if item.obligation_status == OBLIGATION_VIOLATED:
            unresolved.add(UNRESOLVED_VIOLATED_OBLIGATION)
        if item.obligation_status in DETERMINED_OBLIGATION_STATUSES:
            if item.required and item.post_run_state_binding != STATE_BINDING_BOUND:
                state_binding_gap = True
            continue
        if not item.required:
            unresolved.add(UNRESOLVED_OPTIONAL_OBLIGATION)
            continue
        required_gap = True
        unresolved.add(_UNRESOLVED_FOR_OBLIGATION_STATUS[item.obligation_status])
    if state_binding_gap:
        unresolved.add(UNRESOLVED_POST_RUN_STATE_BINDING)

    if review_mode == REVIEW_BLOCKED:
        status = STATUS_BLOCKED
    elif review_mode == REVIEW_DIAGNOSTIC_ONLY:
        status = STATUS_DIAGNOSTIC_ONLY
    elif required_gap or state_binding_gap:
        status = STATUS_ASSESSED_WITH_GAPS
    else:
        status = STATUS_ASSESSED

    return GoalFidelityAssessment(
        status=status,
        review_mode=review_mode,
        task_contract_fingerprint=reconciliation.task_contract_fingerprint,
        check_1_reconciliation_fingerprint=reconciliation.reconciliation_fingerprint,
        verification_specification_fingerprint=(
            goal_verification_specification_fingerprint(specification)
        ),
        requirement_ledger_fingerprint=(
            explicit_requirement_ledger_fingerprint(request.requirement_ledger)
        ),
        request_fingerprint=request_fingerprint,
        execution_reconciliation=summary,
        obligation_results=results,
        satisfied_obligations=tuple(
            sorted(
                item.obligation_id
                for item in results
                if item.obligation_status == OBLIGATION_SATISFIED
            )
        ),
        violated_obligations=tuple(
            sorted(
                item.obligation_id
                for item in results
                if item.obligation_status == OBLIGATION_VIOLATED
            )
        ),
        unresolved_obligations=tuple(
            sorted(
                item.obligation_id
                for item in results
                if item.obligation_status not in DETERMINED_OBLIGATION_STATUSES
            )
        ),
        unbound_claim_assessments=unbound,
        semantic_basis=(
            BASIS_ANALYZER_ASSESSED if consumed else BASIS_NOT_ESTABLISHED
        ),
        unresolved_requirements=_ordered_codes(
            unresolved, GOAL_FIDELITY_UNRESOLVED_REQUIREMENTS
        ),
        reasons=_ordered_codes(reasons, GOAL_FIDELITY_REASONS),
    )


__all__ = [
    "PHASE_ID",
    "ASSESSED_MEANING",
    "BINDING_SCHEMA_VERSION",
    "CHECK_1_ENTRY_POLICY",
    "DETERMINED_OBLIGATION_STATUSES",
    "GOAL_FIDELITY_INCONSISTENCIES",
    "GOAL_FIDELITY_REASONS",
    "GOAL_FIDELITY_STATUSES",
    "GOAL_FIDELITY_UNRESOLVED_REQUIREMENTS",
    "LEDGER_REQUIREMENT_KINDS",
    "OBLIGATION_KINDS",
    "OBLIGATION_RESULT_REASONS",
    "OBLIGATION_SCHEMA_VERSION",
    "OBLIGATION_STATUSES",
    "POLARITY_PROVENANCES",
    "REQUEST_SCHEMA_VERSION",
    "REQUIREMENT_LEDGER_SCHEMA_VERSION",
    "REQUIREMENT_PROVENANCES",
    "REQUIREMENT_SOURCE_SCHEMA_VERSION",
    "RESULT_SCHEMA_VERSION",
    "REVIEW_MODES",
    "REVIEW_MODE_MEANING",
    "SATISFACTION_POLARITIES",
    "SATISFIED_MEANING",
    "SPECIFICATION_SCHEMA_VERSION",
    "STATE_BINDING_PROVENANCES",
    "STATE_BINDING_SCHEMA_VERSION",
    "STATE_BINDING_STATES",
    "VIOLATED_MEANING",
    "ExecutionReconciliationSummary",
    "ExplicitRequirementLedger",
    "ExplicitRequirementSource",
    "GoalFidelityAssessment",
    "GoalFidelityReviewRequest",
    "GoalVerificationObligation",
    "GoalVerificationSpecification",
    "ObligationClaimBinding",
    "ObligationResult",
    "PostRunStateBinding",
    "explicit_requirement_ledger_fingerprint",
    "goal_fidelity_authority",
    "goal_fidelity_guardrails",
    "goal_fidelity_request_fingerprint",
    "goal_verification_specification_fingerprint",
    "render_goal_fidelity_assessment_json",
    "review_goal_fidelity",
]
