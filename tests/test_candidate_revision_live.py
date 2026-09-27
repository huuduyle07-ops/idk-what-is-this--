"""PATCH.AUTHOR.LIVE.1 — verification-guided single revision.

Round 8 produced four wrong candidates for one defect and the harness caught
every one of them.  The last was the interesting failure: ::

    elif line.startswith("  ") and not line.startswith("    "):

byte-changing, structurally minimal, admitted by the widened novelty rule, and
behaviorally identical to the baseline because the ``elif`` above it already
excluded the condition it added.  ``DEFECT.PROBE.LIVE.4`` measured that exactly
— primary ``still_reproduced``, depth-variant ``still_reproduced``, both
preservation cases ``preserved`` — and ``CANDIDATE.VERIFY.LIVE.1`` rejected it
for ``primary_defect_not_closed``.

None of that evidence went back to the author.  This file is the proof that it
now does, exactly once, and that everything else stayed where it was.

The tests split three ways.  The pure ones drive
:func:`assess_candidate_revision` over synthetic payloads and cost nothing.
The product smokes drive the real ``maybe_run_auto_patch`` read-only branch
against the live ``core/code_dna.py`` defect with a deterministic revision
adapter in place of the provider, and assert on the real repository's bytes
before and after.  The governance ones pin what this phase was not allowed to
move.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import time
from pathlib import Path
from typing import Any

import pytest

from _harness_maintenance import before_harness_remediation
from _matrix_history import pin_live5_indentation_matrix

from core import pipeline
from core.agent_state import AgentState
from core.behavioral_expectation import extract_behavioral_expectations
from core.behavioral_matrix import (
    CANDIDATE_FIXED,
    CANDIDATE_PRESERVED,
    CANDIDATE_REGRESSED,
    CANDIDATE_STILL_REPRODUCED,
    CASE_ROLES as MATRIX_CASE_ROLES,
    MATRIX_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE,
    MATRIX_PARTIALLY_FIXED,
    MATRIX_STILL_REPRODUCED,
    MATRIX_STATUSES,
    MATRIX_UNRESOLVED_FAILURE,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
    ROLE_PRIMARY_DEFECT,
)
from core.candidate_mutation_effect import (
    CANDIDATE_EFFECT_MUTATING,
    CANDIDATE_EFFECT_NO_OP,
)
from core.candidate_revision import (
    BEHAVIORAL_REJECTION_REASONS,
    CLOSING_MATRIX_STATUS,
    ELIGIBLE_MATRIX_STATUSES,
    INELIGIBLE_BASELINE_NOT_REPRODUCED,
    INELIGIBLE_BUDGET_CONSUMED,
    INELIGIBLE_CANDIDATE_EFFECT_NOT_MUTATING,
    INELIGIBLE_CANDIDATE_FINGERPRINT_STALE,
    INELIGIBLE_CANDIDATE_NO_OP,
    INELIGIBLE_CANDIDATE_VERIFIED,
    INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE,
    INELIGIBLE_NO_CANDIDATE,
    INELIGIBLE_ORIGINAL_SOURCE_UNAVAILABLE,
    INELIGIBLE_PATCH_BASIS_NOT_GROUNDED,
    INELIGIBLE_PATCH_SAFETY_BLOCKED,
    INELIGIBLE_REASONS,
    INELIGIBLE_ROUTE_NOT_DEFECT_REPAIR,
    INELIGIBLE_SAFE_MINIMAL_REJECTED,
    INELIGIBLE_SANDBOX_APPLY_FAILED,
    INELIGIBLE_TASK_UNAVAILABLE,
    MAX_REVISION_CALLS_PER_RUN,
    OUTCOME_NOT_ELIGIBLE,
    OUTCOME_REVISED_CANDIDATE_REJECTED,
    OUTCOME_REVISED_CANDIDATE_VERIFIED,
    OUTCOME_REVISION_OUTPUT_INVALID,
    OUTCOME_REVISION_UNAVAILABLE,
    OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE,
    OUTPUT_NO_JSON_PAYLOAD,
    OUTPUT_NO_PATCHED_SNIPPET,
    OUTPUT_NO_PATCH_CANDIDATE,
    OUTPUT_NO_RESPONSE,
    OUTPUT_PROVIDER_ERROR,
    OUTPUT_REJECTION_REASONS,
    OUTPUT_WRONG_TARGET_FILE,
    OUTPUT_WRONG_TARGET_SYMBOL,
    PHASE_ID,
    PROMPT_TEMPLATE_CONSTANTS,
    PROVENANCE_EXPLICIT_USER,
    REVISION_OUTCOMES,
    TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
    TRIGGER_NONE,
    CandidateRevisionEvidence,
    CandidateRevisionReceipt,
    RevisionCounterexample,
    assess_candidate_revision,
    build_revision_prompt,
    candidate_revision_guardrails,
    describe_candidate_revision,
    parse_revised_candidate,
    rebase_onto_original_source,
    revision_evidence_is_current,
)
from core.candidate_sandbox_validation import candidate_fingerprint_from_payload
from core.patch_authoring_contract import render_patch_authoring_contract
from core.candidate_verification import (
    REASON_PRESERVATION_REGRESSED,
    REASON_PRIMARY_DEFECT_NOT_CLOSED,
    REASON_SANDBOX_APPLY_FAILED,
    REASON_SUBJECT_INVARIANT_NOT_CLOSED,
    REJECTION_REASONS,
    REJECTED,
    VERIFIED,
)
from core.code_dna import _classify_indent
from core.live_task_routing import (
    PHASE_ID as WAITER_PHASE_ID,
    WORKFLOW_ANALYSIS_ANSWER,
    route_is_read_only,
)
from core.defect_probe import (
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.phase_registry import load_phase_registry
from graph.schema import build_graph
from patching import patch_gates


ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
T6_TASK = f"Fix this bug: {T6_QUERY}"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The shipped function, read from the repository rather than retyped.
T6_TARGET = inspect.getsource(_classify_indent)

T6_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
assert T6_BODY in T6_TARGET, "the shipped _classify_indent body moved"


def _with_body(body: str) -> str:
    return T6_TARGET.replace(T6_BODY, body)


# ── §29: the latest measured candidate, the behaviorally dead guard ──────────
DEAD_GUARD_BODY = T6_BODY.replace(
    '        elif line.startswith("  "):\n',
    '        elif line.startswith("  ") and not line.startswith("    "):\n',
)
assert DEAD_GUARD_BODY != T6_BODY

#: §30 — the already-known correct local-only candidate, the deterministic
#: revision adapter's answer.  Test-only: it is never applied to the shipped
#: ``_classify_indent`` and never offered to a live model.  Correct under the
#: five LIVE.5 cases only: INDENT.SEMANTICS.1's eight-case matrix rejects it on
#: its two Python structural cases, so the proofs that need it verified
#: declare the five-case oracle (see ``dead_guard_first_pass``).
CORRECT_LOCAL_ONLY_BODY = (
    "    counts = Counter()\n"
    "    unit = 0\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "            continue\n"
    '        counts["space"] += 1\n'
    "        width = 0\n"
    "        for ch in line:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        while width:\n"
    "            unit, width = width, unit % width\n"
    '    if unit and counts["space"] >= counts["tab"]:\n'
    '        return "2space" if unit <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)

#: §32 — the Round-7 inverted reorder: primary fixed, preservation regressed.
INVERTED_REORDER_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §33 — the Round-8 ceiling: both ordinary cases answered, neither depth case.
ROUND8_CEILING_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "            continue\n"
    "        indent = 0\n"
    "        for ch in line:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            indent += 1\n"
    "        if indent == 2:\n"
    '            counts["2space"] += 1\n'
    "        elif indent == 4:\n"
    '            counts["4space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §35 — forbidden structural novelty: a new import.
NOVEL_IMPORT_BODY = (
    "    import statistics\n"
    "    counts = Counter()\n"
    "    widths = 0\n"
    "    for line in text.splitlines():\n"
    "        widths += 1\n"
    "    if statistics and widths:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)


# ═══════════════════════════════════════════════════════════════════════════
# Synthetic payloads for the pure eligibility rule
# ═══════════════════════════════════════════════════════════════════════════

PRIMARY_CASE = {
    "case_id": "indentation_style.primary.2space",
    "role": ROLE_PRIMARY_DEFECT,
    "provenance": PROVENANCE_EXPLICIT_USER,
    "expected": "2space",
    "candidate_observed": "4space",
    "candidate_status": CANDIDATE_STILL_REPRODUCED,
}
DEEP_CASE = {
    "case_id": "indentation_style.generalize.2space.deep",
    "role": ROLE_DEFECT_GENERALIZATION,
    "provenance": "system_derived_subject_invariant",
    "expected": "2space",
    "candidate_observed": "4space",
    "candidate_status": CANDIDATE_STILL_REPRODUCED,
}
PRESERVE_CASE = {
    "case_id": "indentation_style.preserve.4space",
    "role": ROLE_PRESERVATION,
    "provenance": "system_derived_behavior_preservation",
    "expected": "4space",
    "candidate_observed": "4space",
    "candidate_status": CANDIDATE_PRESERVED,
}
PRESERVE_DEEP_CASE = {
    "case_id": "indentation_style.preserve.4space.deep",
    "role": ROLE_PRESERVATION_GENERALIZATION,
    "provenance": "system_derived_subject_invariant",
    "expected": "4space",
    "candidate_observed": "4space",
    "candidate_status": CANDIDATE_PRESERVED,
}

CANDIDATE_FINGERPRINT = "a" * 64


def _payload(**overrides: Any) -> dict[str, Any]:
    block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_effect_status": CANDIDATE_EFFECT_MUTATING,
        "candidate_probe_apply_status": "applied",
        "candidate_fingerprint": CANDIDATE_FINGERPRINT,
        "probe_fingerprint": "b" * 64,
        "behavioral_matrix_status": MATRIX_STILL_REPRODUCED,
        "behavioral_matrix_cases": [
            dict(PRIMARY_CASE),
            dict(DEEP_CASE),
            dict(PRESERVE_CASE),
            dict(PRESERVE_DEEP_CASE),
        ],
        "behavioral_matrix": {"candidate_fingerprint": CANDIDATE_FINGERPRINT},
        "candidate_verification_status": REJECTED,
        "candidate_verification_candidate_fingerprint": CANDIDATE_FINGERPRINT,
        "candidate_verification_rejection_reasons": [
            REASON_PRIMARY_DEFECT_NOT_CLOSED
        ],
    }
    block.update(overrides)
    return block


def _evidence(payload: dict[str, Any] | None = None, **overrides: Any) -> dict[str, Any]:
    evidence = {
        "task_route": {"selected_workflow": "defect_repair_patch"},
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "payload": payload if payload is not None else _payload(),
        "patch_safety": {"ok": True},
        "pre_probe": {"probe_result": "reproduced"},
        "candidate_fingerprint": CANDIDATE_FINGERPRINT,
        "rejected_target_snippet": T6_TARGET,
        "rejected_patched_snippet": _with_body(DEAD_GUARD_BODY),
        "target_file": T6_TARGET_FILE,
        "target_symbol": T6_TARGET_SYMBOL,
        "original_source": T6_TARGET,
        "preserved_task": T6_TASK,
        "revision_attempts_already_made": 0,
    }
    evidence.update(overrides)
    return evidence


# ═══════════════════════════════════════════════════════════════════════════
# §3 — what makes a rejection eligible
# ═══════════════════════════════════════════════════════════════════════════


def test_a_behaviorally_rejected_valid_candidate_is_eligible():
    assessment = assess_candidate_revision(_evidence())

    assert assessment.eligible is True
    assert assessment.trigger == TRIGGER_BEHAVIORAL_COUNTEREXAMPLE
    assert assessment.ineligible_reasons == ()
    assert assessment.evidence is not None


@pytest.mark.parametrize(
    "matrix_status,cases,reasons",
    [
        (
            MATRIX_STILL_REPRODUCED,
            [PRIMARY_CASE, DEEP_CASE, PRESERVE_CASE, PRESERVE_DEEP_CASE],
            [REASON_PRIMARY_DEFECT_NOT_CLOSED],
        ),
        (
            MATRIX_PARTIALLY_FIXED,
            [
                {**PRIMARY_CASE, "candidate_status": CANDIDATE_FIXED,
                 "candidate_observed": "2space"},
                DEEP_CASE,
                PRESERVE_CASE,
                PRESERVE_DEEP_CASE,
            ],
            [REASON_SUBJECT_INVARIANT_NOT_CLOSED],
        ),
        (
            MATRIX_FIXED_BUT_REGRESSIVE,
            [
                {**PRIMARY_CASE, "candidate_status": CANDIDATE_FIXED,
                 "candidate_observed": "2space"},
                {**DEEP_CASE, "candidate_status": CANDIDATE_FIXED,
                 "candidate_observed": "2space"},
                {**PRESERVE_CASE, "candidate_status": CANDIDATE_REGRESSED,
                 "candidate_observed": "2space"},
                PRESERVE_DEEP_CASE,
            ],
            [REASON_PRESERVATION_REGRESSED],
        ),
        (
            MATRIX_UNRESOLVED_FAILURE,
            [PRIMARY_CASE, DEEP_CASE, PRESERVE_CASE, PRESERVE_DEEP_CASE],
            [REASON_PRIMARY_DEFECT_NOT_CLOSED],
        ),
    ],
)
def test_every_contradictory_matrix_status_is_eligible(matrix_status, cases, reasons):
    """§3 — still_reproduced, partially_fixed, fixed_but_regressive, unresolved."""

    payload = _payload(
        behavioral_matrix_status=matrix_status,
        behavioral_matrix_cases=[dict(case) for case in cases],
        candidate_verification_rejection_reasons=list(reasons),
    )
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.eligible is True, matrix_status
    assert assessment.evidence.matrix_status == matrix_status
    assert assessment.evidence.failed_cases


def test_the_eligible_matrix_statuses_are_exactly_the_open_ones():
    """The mirrored vocabulary matches DEFECT.PROBE.LIVE.4's own."""

    assert ELIGIBLE_MATRIX_STATUSES <= set(MATRIX_STATUSES)
    assert CLOSING_MATRIX_STATUS in MATRIX_STATUSES
    assert CLOSING_MATRIX_STATUS == MATRIX_FIXED_AND_PRESERVED
    assert CLOSING_MATRIX_STATUS not in ELIGIBLE_MATRIX_STATUSES
    # Inconclusive and unavailable are refusals to measure, not contradictions.
    assert "inconclusive" not in ELIGIBLE_MATRIX_STATUSES
    assert "unavailable" not in ELIGIBLE_MATRIX_STATUSES


def test_the_behavioral_rejection_reasons_are_a_subset_of_the_verifier_s():
    assert BEHAVIORAL_REJECTION_REASONS <= set(REJECTION_REASONS)
    # Every reason about form, freshness or availability is excluded.
    assert REASON_SANDBOX_APPLY_FAILED not in BEHAVIORAL_REJECTION_REASONS


def test_the_case_roles_match_the_matrix_s_own():
    from core.candidate_revision import CASE_ROLES

    assert set(CASE_ROLES) == set(MATRIX_CASE_ROLES)


# ═══════════════════════════════════════════════════════════════════════════
# §4/§5 — what may never buy a model call
# ═══════════════════════════════════════════════════════════════════════════


def test_an_exact_no_op_is_not_eligible():
    """§5/§34 — PATCH.MINIMAL.LIVE.1 already answered this precisely."""

    payload = _payload(candidate_effect_status=CANDIDATE_EFFECT_NO_OP)
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.eligible is False
    assert assessment.ineligible_reasons == (INELIGIBLE_CANDIDATE_NO_OP,)
    assert assessment.evidence is None


def test_a_safe_minimal_rejection_is_not_eligible():
    """§35 — this phase does not negotiate with a safety policy by prompt."""

    payload = _payload(candidate_novelty_admitted=False)
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_SAFE_MINIMAL_REJECTED,)


def test_a_sandbox_apply_failure_is_not_eligible():
    payload = _payload(candidate_probe_apply_status="failed")
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_SANDBOX_APPLY_FAILED,)


def test_a_stale_candidate_fingerprint_is_not_eligible():
    """§36 — the matrix measured a candidate that is no longer on the table."""

    payload = _payload(behavioral_matrix={"candidate_fingerprint": "c" * 64})
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_CANDIDATE_FINGERPRINT_STALE,)


def test_a_stale_verification_fingerprint_is_not_eligible():
    payload = _payload(candidate_verification_candidate_fingerprint="d" * 64)
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_CANDIDATE_FINGERPRINT_STALE,)


def test_a_malformed_candidate_with_no_bytes_is_not_eligible():
    assessment = assess_candidate_revision(
        _evidence(rejected_patched_snippet="", candidate_fingerprint="")
    )

    assert assessment.ineligible_reasons == (INELIGIBLE_NO_CANDIDATE,)


def test_an_unmeasured_candidate_effect_is_not_eligible():
    payload = _payload(candidate_effect_status="undetermined")
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (
        INELIGIBLE_CANDIDATE_EFFECT_NOT_MUTATING,
    )


def test_a_patch_safety_rejection_is_not_eligible():
    assessment = assess_candidate_revision(_evidence(patch_safety={"ok": False}))

    assert assessment.ineligible_reasons == (INELIGIBLE_PATCH_SAFETY_BLOCKED,)


def test_an_unreproduced_baseline_is_not_eligible():
    assessment = assess_candidate_revision(
        _evidence(pre_probe={"probe_result": "not_reproduced"})
    )

    assert assessment.ineligible_reasons == (INELIGIBLE_BASELINE_NOT_REPRODUCED,)


def test_a_verified_candidate_is_not_eligible():
    """§28 — first-draft success spends nothing."""

    payload = _payload(
        candidate_verification_status=VERIFIED,
        candidate_verification_rejection_reasons=[],
        behavioral_matrix_status=MATRIX_FIXED_AND_PRESERVED,
    )
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_CANDIDATE_VERIFIED,)


@pytest.mark.parametrize("status", ["inconclusive", "unavailable", "stale", "invalid"])
def test_a_verifier_that_established_nothing_is_not_eligible(status):
    """§4 — 'the verifier could not tell' is not counterevidence."""

    payload = _payload(candidate_verification_status=status)
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (INELIGIBLE_CANDIDATE_VERIFIED,)


def test_a_non_behavioral_rejection_reason_is_not_eligible():
    """A rejection about form, not behavior, has nothing for an author to fix."""

    payload = _payload(
        candidate_verification_rejection_reasons=[REASON_SANDBOX_APPLY_FAILED]
    )
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (
        INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE,
    )


def test_an_inconclusive_matrix_is_not_eligible():
    payload = _payload(behavioral_matrix_status="inconclusive")
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (
        INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE,
    )


def test_a_matrix_with_no_failing_case_is_not_eligible():
    payload = _payload(
        behavioral_matrix_cases=[dict(PRESERVE_CASE), dict(PRESERVE_DEEP_CASE)]
    )
    assessment = assess_candidate_revision(_evidence(payload))

    assert assessment.ineligible_reasons == (
        INELIGIBLE_NO_BEHAVIORAL_COUNTEREVIDENCE,
    )


@pytest.mark.parametrize(
    "workflow", ["analysis_answer", "clarification", "explicit_change_patch", ""]
)
def test_only_the_defect_repair_route_is_eligible(workflow):
    """§47/§48 — feature authoring and analysis stay outside this contract."""

    assessment = assess_candidate_revision(
        _evidence(task_route={"selected_workflow": workflow})
    )

    assert assessment.ineligible_reasons == (INELIGIBLE_ROUTE_NOT_DEFECT_REPAIR,)


def test_an_explicit_change_basis_is_not_eligible():
    """§47 — the explicit-change path keeps its own contract."""

    assessment = assess_candidate_revision(
        _evidence(patch_basis=PATCH_BASIS_EXPLICIT_CHANGE_REQUEST)
    )

    assert assessment.ineligible_reasons == (INELIGIBLE_PATCH_BASIS_NOT_GROUNDED,)


def test_a_missing_original_source_is_not_eligible():
    assessment = assess_candidate_revision(_evidence(original_source=""))

    assert assessment.ineligible_reasons == (
        INELIGIBLE_ORIGINAL_SOURCE_UNAVAILABLE,
    )


def test_a_missing_preserved_task_is_not_eligible():
    assessment = assess_candidate_revision(_evidence(preserved_task="   "))

    assert assessment.ineligible_reasons == (INELIGIBLE_TASK_UNAVAILABLE,)


def test_the_budget_refuses_a_second_assessment():
    """§2/§37 — one call per run, enforced before anything else is read."""

    assessment = assess_candidate_revision(
        _evidence(revision_attempts_already_made=1)
    )

    assert assessment.ineligible_reasons == (INELIGIBLE_BUDGET_CONSUMED,)


def test_the_ineligibility_vocabulary_is_closed():
    with pytest.raises(ValueError):
        CandidateRevisionReceipt(
            eligible=False,
            attempted=False,
            outcome=OUTCOME_NOT_ELIGIBLE,
            ineligible_reasons=("something_new",),
        )
    assert len(set(INELIGIBLE_REASONS)) == len(INELIGIBLE_REASONS)


def test_model_confidence_is_not_an_eligibility_input():
    """§42 — evidence triggers revision, never the writer's self-assessment."""

    low = assess_candidate_revision(_evidence(_payload(confidence=0.01)))
    high = assess_candidate_revision(_evidence(_payload(confidence=0.99)))

    assert low.eligible is True and high.eligible is True
    assert low.evidence.as_dict() == high.evidence.as_dict()


# ═══════════════════════════════════════════════════════════════════════════
# §6/§7 — the evidence receipt
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_binds_the_exact_rejected_candidate_and_target():
    receipt = assess_candidate_revision(_evidence()).evidence

    assert receipt.rejected_candidate_fingerprint == CANDIDATE_FINGERPRINT
    assert receipt.target_file == T6_TARGET_FILE
    assert receipt.target_symbol == T6_TARGET_SYMBOL
    assert receipt.original_source_digest == hashlib.sha256(
        T6_TARGET.encode("utf-8")
    ).hexdigest()
    assert receipt.task_fingerprint == hashlib.sha256(
        T6_TASK.encode("utf-8")
    ).hexdigest()
    assert receipt.phase_id == PHASE_ID


def test_the_receipt_carries_the_failed_and_the_preserved_cases():
    """§7 — the two failures as counterexamples, the two holds as constraints."""

    receipt = assess_candidate_revision(_evidence()).evidence

    assert [case.case_id for case in receipt.failed_cases] == [
        "indentation_style.primary.2space",
        "indentation_style.generalize.2space.deep",
    ]
    assert [case.role for case in receipt.failed_cases] == [
        ROLE_PRIMARY_DEFECT,
        ROLE_DEFECT_GENERALIZATION,
    ]
    for case in receipt.failed_cases:
        assert case.expected == "2space"
        assert case.candidate_observed == "4space"
        assert case.status == CANDIDATE_STILL_REPRODUCED
    assert [case.case_id for case in receipt.preserved_cases] == [
        "indentation_style.preserve.4space",
        "indentation_style.preserve.4space.deep",
    ]
    for case in receipt.preserved_cases:
        assert case.expected == "4space"
        assert case.status == CANDIDATE_PRESERVED


def test_a_case_carries_only_bounded_machine_facts():
    """§6 — no prose reasoning reaches the receipt, by construction."""

    receipt = assess_candidate_revision(_evidence()).evidence
    for case in receipt.failed_cases + receipt.preserved_cases:
        assert set(case.as_dict()) == {
            "case_id",
            "role",
            "provenance",
            "expected",
            "candidate_observed",
            "status",
        }
        for value in case.as_dict().values():
            assert isinstance(value, (str, int, float, bool)) or value is None


def test_a_system_derived_case_may_not_claim_the_user_said_it():
    """§8 — provenance cannot be laundered on the way into a prompt."""

    with pytest.raises(ValueError):
        RevisionCounterexample(
            case_id="x",
            role=ROLE_DEFECT_GENERALIZATION,
            provenance=PROVENANCE_EXPLICIT_USER,
            expected="2space",
            candidate_observed="4space",
            status=CANDIDATE_STILL_REPRODUCED,
        )

    corrupted = _payload(
        behavioral_matrix_cases=[
            dict(PRIMARY_CASE),
            {**DEEP_CASE, "provenance": PROVENANCE_EXPLICIT_USER},
            dict(PRESERVE_CASE),
            dict(PRESERVE_DEEP_CASE),
        ]
    )
    receipt = assess_candidate_revision(_evidence(corrupted)).evidence
    # The corrupted case is discarded, never relabelled and never promoted.
    assert [case.case_id for case in receipt.failed_cases] == [
        "indentation_style.primary.2space"
    ]


def test_stale_evidence_is_refused_before_it_is_used():
    """§19 — every binding on the receipt is rechecked, not trusted."""

    receipt = assess_candidate_revision(_evidence()).evidence
    current = dict(
        candidate_fingerprint=CANDIDATE_FINGERPRINT,
        original_source=T6_TARGET,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
    )
    assert revision_evidence_is_current(receipt, **current) is True

    for key, value in (
        ("candidate_fingerprint", "e" * 64),
        ("original_source", T6_TARGET + "\n# moved\n"),
        ("target_file", "core/other.py"),
        ("target_symbol", "_other"),
    ):
        assert revision_evidence_is_current(receipt, **{**current, key: value}) is False


def test_the_receipt_is_immutable_and_fingerprinted():
    receipt = assess_candidate_revision(_evidence()).evidence

    with pytest.raises(Exception):
        receipt.matrix_status = MATRIX_FIXED_AND_PRESERVED  # type: ignore[misc]
    assert len(receipt.evidence_fingerprint) == 64
    # The digest covers the cases, so a different measurement is a different id.
    other = assess_candidate_revision(
        _evidence(
            _payload(
                behavioral_matrix_cases=[dict(PRIMARY_CASE), dict(PRESERVE_CASE)]
            )
        )
    ).evidence
    assert other.evidence_fingerprint != receipt.evidence_fingerprint


def test_the_receipt_holds_no_source_bytes_in_its_serialized_form():
    """§6 — digests travel in the record; the bytes travel only in the prompt."""

    serialized = json.dumps(
        assess_candidate_revision(_evidence()).evidence.as_dict(), ensure_ascii=False
    )
    assert T6_BODY not in serialized
    assert DEAD_GUARD_BODY not in serialized


# ═══════════════════════════════════════════════════════════════════════════
# §8/§9/§12 — the request, and what it may not contain
# ═══════════════════════════════════════════════════════════════════════════

def _contract():
    """The shared authoring contract for this target (PATCH.AUTHOR.LIVE.2).

    Rendered from the same producer the initial draft renders from, at the
    style the live T6 run uses.  It is a required argument now: a stateless
    revision call that does not carry the contract cannot answer in the
    shape the parser reads, which is the Round-9 defect LIVE.2 closes.
    """

    return render_patch_authoring_contract(
        style="safe_minimal", source_snippet=T6_TARGET
    )


#: §8's own list, plus the spellings the correct answer happens to use.
FORBIDDEN_TECHNIQUE_WORDS = (
    "gcd",
    "lstrip",
    "strip",
    "width",
    "unit",
    "greatest common divisor",
    "leading space",
    "count the",
    "local variable",
    "branch order",
    "reorder",
    "measure",
    "divisor",
    "modulo",
    "loop over",
    "helper function",
)


def test_no_template_constant_names_a_technique():
    """§8 — there is no advice to compose, because none is written down."""

    for constant in PROMPT_TEMPLATE_CONSTANTS:
        lowered = constant.lower()
        for word in FORBIDDEN_TECHNIQUE_WORDS:
            assert word not in lowered, (word, constant)


def test_the_prompt_is_exactly_template_plus_measured_facts():
    """§8/§12 — every line is a constant, the user's own text, or evidence."""

    receipt = assess_candidate_revision(_evidence()).evidence
    prompt = build_revision_prompt(receipt, _contract())

    permitted: list[str] = [
        *PROMPT_TEMPLATE_CONSTANTS,
        # PATCH.AUTHOR.LIVE.2: the shared authoring contract is declared
        # material, exactly as the template constants are.  It is not written
        # down here — it is the object the initial draft is held to — so a
        # sentence added to the request outside it still survives below.
        _contract().text,
        receipt.preserved_task,
        f"{receipt.target_file}::{receipt.target_symbol}",
        receipt.original_source,
        receipt.rejected_patched_snippet,
        receipt.matrix_status,
        receipt.verification_status,
        *receipt.verification_rejection_reasons,
    ]
    for case in receipt.failed_cases + receipt.preserved_cases:
        permitted.extend(
            [
                case.case_id,
                case.role,
                case.provenance,
                repr(case.expected),
                repr(case.candidate_observed),
                case.status,
            ]
        )

    residue = prompt
    # Longest first, so a value that contains another is removed as itself.
    for chunk in sorted(permitted, key=len, reverse=True):
        residue = residue.replace(chunk, " ")

    # What is left is the field labels and structural punctuation, and nothing
    # else.  A sentence added to the request without being declared a template
    # constant would survive this subtraction and fail here.
    assert set(residue.split()) <= {
        "matrix_status=",
        "verification_status=",
        "rejection_reasons=",
        "-",
        "case_id=",
        "role=",
        "provenance=",
        "expected=",
        "observed=",
        "status=",
    }, sorted(set(residue.split()))
    for word in ("gcd", "lstrip", "divisor"):
        assert word not in prompt.lower()


def test_the_prompt_shows_the_rejected_candidate_as_evidence_only():
    """§11 — labelled, and never as the base."""

    receipt = assess_candidate_revision(_evidence()).evidence
    prompt = build_revision_prompt(receipt, _contract())

    rejected_at = prompt.index(receipt.rejected_patched_snippet)
    label_at = prompt.index("REJECTED CANDIDATE - EVIDENCE ONLY")
    source_at = prompt.index("AUTHORITATIVE ORIGINAL SOURCE")
    assert label_at < rejected_at
    assert source_at < label_at
    assert "not a starting point" in prompt


def test_the_prompt_carries_the_task_verbatim():
    """§0 — the original T6 task is not rewritten, summarised or annotated."""

    receipt = assess_candidate_revision(_evidence()).evidence
    assert T6_TASK in build_revision_prompt(receipt, _contract())


def test_the_prompt_never_asks_for_hidden_reasoning():
    """§9 — no self-critique, no chain of thought, no explanation request."""

    prompt = build_revision_prompt(
        assess_candidate_revision(_evidence()).evidence, _contract()
    ).lower()
    for phrase in (
        "reasoning",
        "think step",
        "chain of thought",
        "explain why",
        "critique",
        "reflect",
        "what went wrong",
    ):
        assert phrase not in prompt


def test_the_prompt_carries_every_failed_and_preserved_case():
    receipt = assess_candidate_revision(_evidence()).evidence
    prompt = build_revision_prompt(receipt, _contract())

    for case in receipt.failed_cases + receipt.preserved_cases:
        assert case.case_id in prompt
        assert f"status={case.status}" in prompt


def test_the_prompt_is_deterministic():
    receipt = assess_candidate_revision(_evidence()).evidence
    assert build_revision_prompt(receipt, _contract()) == build_revision_prompt(
        receipt, _contract()
    )


# ═══════════════════════════════════════════════════════════════════════════
# §10/§20 — reading a revision back
# ═══════════════════════════════════════════════════════════════════════════


def _revision_response(body: str, **overrides: Any) -> str:
    candidate = {
        "relative_path": T6_TARGET_FILE,
        "target_node_kind": "function",
        "target_node_name": T6_TARGET_SYMBOL,
        "target_snippet": T6_TARGET,
        "patched_snippet": _with_body(body),
    }
    candidate.update(overrides)
    return json.dumps({"summary": "revised", "patch_candidate": candidate})


def _receipt() -> CandidateRevisionEvidence:
    return assess_candidate_revision(_evidence()).evidence


def test_a_well_formed_revision_is_accepted_against_the_original_source():
    revised = parse_revised_candidate(
        _revision_response(CORRECT_LOCAL_ONLY_BODY), _receipt()
    )

    assert revised.accepted is True
    assert revised.candidate["target_snippet"] == T6_TARGET
    assert revised.candidate["patched_snippet"] == _with_body(CORRECT_LOCAL_ONLY_BODY)


def test_a_body_fragment_is_rebased_onto_the_original_source():
    """§10/§16 — the base is always the original bytes, never a fragment."""

    response = json.dumps(
        {
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_node_name": T6_TARGET_SYMBOL,
                "target_snippet": T6_BODY,
                "patched_snippet": CORRECT_LOCAL_ONLY_BODY,
            }
        }
    )
    revised = parse_revised_candidate(response, _receipt())

    assert revised.accepted is True
    assert revised.candidate["target_snippet"] == T6_TARGET
    assert revised.candidate["patched_snippet"] == _with_body(CORRECT_LOCAL_ONLY_BODY)


def test_a_revision_based_on_the_rejected_candidate_is_refused():
    """§10 — Candidate0's sandbox is not a base for Candidate1."""

    response = _revision_response(
        CORRECT_LOCAL_ONLY_BODY, target_snippet=_with_body(DEAD_GUARD_BODY)
    )
    revised = parse_revised_candidate(response, _receipt())

    assert revised.accepted is False
    assert revised.rejection_reason == OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE


def test_rebasing_refuses_text_that_is_not_in_the_original():
    assert (
        rebase_onto_original_source(
            original_source=T6_TARGET,
            target_snippet="not present anywhere",
            patched_snippet="x",
        )
        is None
    )
    assert rebase_onto_original_source(
        original_source=T6_TARGET, target_snippet=T6_TARGET, patched_snippet="x"
    ) == (T6_TARGET, "x")


@pytest.mark.parametrize(
    "response,reason",
    [
        ("", OUTPUT_NO_RESPONSE),
        ("AGENT_ERROR: Gemini Final Error", OUTPUT_PROVIDER_ERROR),
        ("here is my advice, no json at all", OUTPUT_NO_JSON_PAYLOAD),
        (json.dumps({"summary": "no candidate"}), OUTPUT_NO_PATCH_CANDIDATE),
    ],
)
def test_an_unusable_revision_output_is_named_and_refused(response, reason):
    revised = parse_revised_candidate(response, _receipt())

    assert revised.accepted is False
    assert revised.rejection_reason == reason


def test_a_revision_naming_another_file_or_symbol_is_refused():
    """§20 — a wrong target is not a candidate for this defect."""

    wrong_file = parse_revised_candidate(
        _revision_response(CORRECT_LOCAL_ONLY_BODY, relative_path="core/other.py"),
        _receipt(),
    )
    assert wrong_file.rejection_reason == OUTPUT_WRONG_TARGET_FILE

    wrong_symbol = parse_revised_candidate(
        _revision_response(CORRECT_LOCAL_ONLY_BODY, target_node_name="_other"),
        _receipt(),
    )
    assert wrong_symbol.rejection_reason == OUTPUT_WRONG_TARGET_SYMBOL


def test_a_revision_with_no_patch_is_refused_however_good_its_explanation():
    """§39 — a correct diagnosis with no candidate is still not a candidate."""

    response = json.dumps(
        {
            "summary": (
                "The 4-space branch shadows the 2-space branch, so a 2-space "
                "file is counted as 4-space."
            ),
            "patch_candidate": {
                "relative_path": T6_TARGET_FILE,
                "target_node_name": T6_TARGET_SYMBOL,
                "target_snippet": T6_TARGET,
                "patched_snippet": "",
            },
        }
    )
    revised = parse_revised_candidate(response, _receipt())

    assert revised.accepted is False
    assert revised.rejection_reason == OUTPUT_NO_PATCHED_SNIPPET


def test_a_confidence_travels_only_when_the_provider_returned_one():
    """§42 — Candidate0's confidence is never carried onto Candidate1."""

    without = parse_revised_candidate(
        _revision_response(CORRECT_LOCAL_ONLY_BODY), _receipt()
    )
    assert without.confidence is None

    body = json.loads(_revision_response(CORRECT_LOCAL_ONLY_BODY))
    body["confidence"] = 0.7
    with_value = parse_revised_candidate(json.dumps(body), _receipt())
    assert with_value.confidence == pytest.approx(0.7)


def test_the_output_rejection_vocabulary_is_closed():
    assert len(set(OUTPUT_REJECTION_REASONS)) == len(OUTPUT_REJECTION_REASONS)
    with pytest.raises(ValueError):
        parse_revised_candidate("", _receipt()).__class__(
            accepted=False, rejection_reason="made_up"
        )


# ═══════════════════════════════════════════════════════════════════════════
# §15/§37/§40 — the receipt and the budget
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_cannot_record_more_than_one_call():
    with pytest.raises(ValueError):
        CandidateRevisionReceipt(
            eligible=True,
            attempted=True,
            attempt_count=2,
            outcome=OUTCOME_REVISED_CANDIDATE_REJECTED,
            trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
        )
    with pytest.raises(ValueError):
        CandidateRevisionReceipt(
            eligible=False,
            attempted=False,
            attempt_count=1,
            outcome=OUTCOME_NOT_ELIGIBLE,
        )


def test_the_outcome_vocabulary_is_closed():
    assert len(set(REVISION_OUTCOMES)) == len(REVISION_OUTCOMES)
    with pytest.raises(ValueError):
        CandidateRevisionReceipt(
            eligible=True, attempted=False, outcome="probably_fine"
        )


def test_the_receipt_grants_nothing_whatever_the_outcome():
    """§26 — a verified revision is authorship, never authority."""

    receipt = CandidateRevisionReceipt(
        eligible=True,
        attempted=True,
        attempt_count=1,
        outcome=OUTCOME_REVISED_CANDIDATE_VERIFIED,
        trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
    )
    assert receipt.execution_authorized is False
    assert receipt.final_repository_changed is False
    assert receipt.as_dict()["authority_effect"] == "none"
    assert receipt.model_call_budget_consumed == 1
    assert receipt.model_call_budget_remaining == 0
    assert receipt.needs_escalation is False

    failed = CandidateRevisionReceipt(
        eligible=True,
        attempted=True,
        attempt_count=1,
        outcome=OUTCOME_REVISED_CANDIDATE_REJECTED,
        trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
    )
    assert failed.needs_escalation is True


def test_the_receipt_records_no_prose_reasoning():
    """§15 — sizes and a latency, never a transcript."""

    receipt = CandidateRevisionReceipt(
        eligible=True,
        attempted=True,
        attempt_count=1,
        outcome=OUTCOME_REVISED_CANDIDATE_VERIFIED,
        trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
        input_chars=4096,
        output_chars=2048,
    )
    serialized = json.dumps(receipt.as_dict())
    assert "prompt" not in serialized
    assert "response" not in serialized
    assert receipt.as_dict()["input_chars"] == 4096


def test_the_unattempted_receipt_says_so_plainly():
    receipt = CandidateRevisionReceipt(
        eligible=False,
        attempted=False,
        outcome=OUTCOME_NOT_ELIGIBLE,
        ineligible_reasons=(INELIGIBLE_CANDIDATE_NO_OP,),
    )
    assert receipt.trigger == TRIGGER_NONE
    assert receipt.model_call_budget_consumed == 0
    assert receipt.model_call_budget_remaining == MAX_REVISION_CALLS_PER_RUN
    assert "no verification-guided revision" in describe_candidate_revision(receipt)


def test_describe_never_claims_the_candidate_is_ready():
    for outcome in REVISION_OUTCOMES:
        attempted = outcome != OUTCOME_NOT_ELIGIBLE
        receipt = CandidateRevisionReceipt(
            eligible=attempted,
            attempted=attempted,
            attempt_count=1 if attempted else 0,
            outcome=outcome,
            trigger=(
                TRIGGER_BEHAVIORAL_COUNTEREXAMPLE if attempted else TRIGGER_NONE
            ),
        )
        text = describe_candidate_revision(receipt).lower()
        for forbidden in ("ready to apply", "approved", "safe to apply", "applied"):
            assert forbidden not in text


# ═══════════════════════════════════════════════════════════════════════════
# The deterministic product smoke (§30, §31, §32, §33, §34, §35, §51)
# ═══════════════════════════════════════════════════════════════════════════


def _behavior_fact():
    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    (fact,) = facts
    return fact


@pytest.fixture(scope="module")
def t6_pre_probe():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=T6_TARGET,
        candidate_eligible=True,
    )
    assert binding is not None
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_behavior_fact()
    )
    assert contract is not None
    receipt = execute_defect_probe(contract, repo_path=ROOT)
    if receipt.probe_result != "reproduced":
        pytest.skip(f"baseline probe was {receipt.probe_result}, not reproduced")
    return contract, receipt


def _t6_graph():
    return build_graph(
        [
            {"id": T6_TARGET_FILE, "type": "file"},
            {
                "id": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "function",
                "file": T6_TARGET_FILE,
            },
            {"id": "core/unrelated.py", "type": "file"},
        ],
        [
            {
                "source": T6_TARGET_FILE,
                "target": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "contains",
            }
        ],
    )


def _t6_state(patched: str, pre_probe, *, workflow="defect_repair_patch") -> AgentState:
    _contract, receipt = pre_probe
    state = AgentState(
        interface="agent",
        mode="planner",
        user_input=T6_TASK,
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )
    state.repo_path = str(ROOT)
    state.is_project_input = True
    state.patch_style = "safe_minimal"
    state.task_info = {"intent": "bug_fix", "patch_style": "safe_minimal"}
    state.live_route = {
        "selected_workflow": workflow,
        "preservation_passed": True,
        "behavioral_expectations": [_behavior_fact().as_dict()],
    }
    state.control_result = {
        "repo_path": str(ROOT),
        "live_route": dict(state.live_route),
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "defect_probe": receipt.as_dict(),
        "patch_intent": {
            "target_file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_symbol": T6_TARGET_SYMBOL,
            "target_symbol_full": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
            "source_snippet": T6_TARGET,
        },
        "entry_resolution": {
            "resolved_entry_nodes": [f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}"]
        },
        "scout": {"request_type": "bug_fix"},
    }
    state.json_block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "target_source_grounded": True,
        "confidence": 0.4,
        "needs_escalation": False,
        "patch_candidate": {
            "file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_node_kind": "function",
            "target_node_name": T6_TARGET_SYMBOL,
            "target_snippet": T6_TARGET,
            "patched_snippet": patched,
        },
        "issues": [],
    }
    # The two frozen minimality gates, exactly as ``finalize_answer`` runs them.
    pipeline._record_candidate_mutation_effect(state)
    patch_gates._enforce_safe_minimal(state)
    state.repository_graph = _t6_graph()
    return state


def _drive(state: AgentState, monkeypatch, revision: str | None):
    """Run the read-only lifecycle with a deterministic revision adapter."""

    calls: list[str] = []

    def adapter(_state: AgentState, prompt: str) -> str:
        calls.append(prompt)
        assert revision is not None, "no provider call was expected"
        return revision

    monkeypatch.setattr(pipeline, "_call_revision_provider", adapter)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    pipeline.maybe_run_auto_patch(state, interactive=False)
    after = (ROOT / T6_TARGET_FILE).read_bytes()
    assert before == after, "the real repository was modified"
    return state.json_block, calls


@pytest.fixture(scope="module")
def dead_guard_first_pass(t6_pre_probe):
    """§29 — the exact latest candidate, measured once and reused read-only.

    The revision lifecycle needs a revision the matrix *closes*.  Under
    INDENT.SEMANTICS.1's eight cases no candidate safe_minimal admits is known
    to (tests/test_indent_semantics1.py), so this proof declares the five-case
    oracle it was written against, through the one shared test helper.
    """

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    calls: list[str] = []

    original_provider = pipeline._call_revision_provider
    original_switch = pipeline.AUTO_PATCH_ENABLED

    def adapter(_state: AgentState, prompt: str) -> str:
        calls.append(prompt)
        return _revision_response(CORRECT_LOCAL_ONLY_BODY)

    pipeline._call_revision_provider = adapter
    pipeline.AUTO_PATCH_ENABLED = False
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    try:
        with pytest.MonkeyPatch.context() as history:
            pin_live5_indentation_matrix(history)
            pipeline.maybe_run_auto_patch(state, interactive=False)
    finally:
        pipeline._call_revision_provider = original_provider
        pipeline.AUTO_PATCH_ENABLED = original_switch
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    return state, calls, before


def test_smoke_the_dead_guard_reproduces_its_measured_rejection(t6_pre_probe):
    """§29 — the phase's starting fact, re-measured rather than remembered."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block = state.json_block

    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_MUTATING
    assert block["patch_candidate"] is not None

    original_provider = pipeline._call_revision_provider
    original_switch = pipeline.AUTO_PATCH_ENABLED
    pipeline._call_revision_provider = lambda _s, _p: "AGENT_ERROR: not expected"
    pipeline.AUTO_PATCH_ENABLED = False
    try:
        pipeline._verify_authored_candidate_without_mutation(state)
    finally:
        pipeline._call_revision_provider = original_provider
        pipeline.AUTO_PATCH_ENABLED = original_switch

    cases = {
        case["case_id"]: case["candidate_status"]
        for case in block["behavioral_matrix_cases"]
    }
    assert cases == {
        "indentation_style.primary.2space": CANDIDATE_STILL_REPRODUCED,
        "indentation_style.generalize.2space.deep": CANDIDATE_STILL_REPRODUCED,
        "indentation_style.preserve.4space": CANDIDATE_PRESERVED,
        "indentation_style.preserve.4space.deep": CANDIDATE_PRESERVED,
        # DEFECT.PROBE.LIVE.5 appended the distribution-skew case.  The dead
        # guard is behaviorally identical to the baseline, so it reproduces
        # that one too and the reduction is still still_reproduced.
        "indentation_style.generalize.2space.skew": CANDIDATE_STILL_REPRODUCED,
        # INDENT.SEMANTICS.1 appended three preservation cases the baseline
        # already answers, so the dead guard preserves all three.
        "indentation_style.preserve.4space.continuation": CANDIDATE_PRESERVED,
        "indentation_style.preserve.4space.multiline_string": CANDIDATE_PRESERVED,
        "indentation_style.preserve.tab.go": CANDIDATE_PRESERVED,
    }
    assert block["behavioral_matrix_status"] == MATRIX_STILL_REPRODUCED
    assert block["candidate_verification_status"] == REJECTED
    assert REASON_PRIMARY_DEFECT_NOT_CLOSED in (
        block["candidate_verification_rejection_reasons"]
    )
    assert block["candidate_revision_eligible"] is True


def test_smoke_one_revision_turns_the_dead_guard_into_a_verified_candidate(
    dead_guard_first_pass,
):
    """§30/§51 — the primary deterministic proof, end to end."""

    state, calls, before = dead_guard_first_pass
    block = state.json_block

    assert len(calls) == 1
    assert block["candidate_revision_attempted"] is True
    assert block["candidate_revision_attempt_count"] == 1
    assert block["candidate_revision_trigger"] == TRIGGER_BEHAVIORAL_COUNTEREXAMPLE
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED
    # DEFECT.PROBE.LIVE.5: three failing defect cases reach the author rather
    # than two, carried by PATCH.AUTHOR.LIVE.1's existing failed_cases path.
    assert block["candidate_revision_counterexample_count"] == 3
    assert block["candidate_revision_preserved_case_count"] == 2

    # Candidate1 went through every gate again, on its own bytes.
    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_MUTATING
    assert block["candidate_novelty_admitted"] is True
    assert block["candidate_probe_apply_status"] == "applied"
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_AND_PRESERVED
    assert block["candidate_verification_status"] == VERIFIED
    assert block["patch_candidate"]["patched_snippet"] == _with_body(
        CORRECT_LOCAL_ONLY_BODY
    )

    # §26 — and it authorized nothing.
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before


def test_smoke_candidate_one_gets_a_fresh_fingerprint_and_no_inherited_receipt(
    dead_guard_first_pass,
):
    """§16/§17 — Candidate1 earned all of its evidence again."""

    state, _calls, _before = dead_guard_first_pass
    block = state.json_block

    previous = block["candidate_revision_previous_candidate_fingerprint"]
    revised = block["candidate_revision_revised_candidate_fingerprint"]
    assert len(previous) == 64 and len(revised) == 64
    assert previous != revised
    assert candidate_fingerprint_from_payload(block) == revised

    # Every candidate-bound receipt now names Candidate1, not Candidate0.
    for key in (
        "candidate_effect_candidate_fingerprint",
        "candidate_novelty_candidate_fingerprint",
        "candidate_verification_candidate_fingerprint",
        "execution_eligibility_candidate_fingerprint",
    ):
        assert block[key] == revised, key
    assert block["behavioral_matrix"]["candidate_fingerprint"] == revised


def test_smoke_candidate_zero_survives_only_as_rejected_evidence(
    dead_guard_first_pass,
):
    """§11/§27 — visible for debugging, never presented as a candidate."""

    state, _calls, _before = dead_guard_first_pass
    previous = state.json_block["candidate_revision_previous_candidate"]

    assert previous["status"] == "rejected_evidence_only"
    assert previous["patched_snippet"] == _with_body(DEAD_GUARD_BODY)
    assert previous["candidate_fingerprint"] == (
        state.json_block["candidate_revision_previous_candidate_fingerprint"]
    )
    assert state.json_block["patch_candidate"]["patched_snippet"] != (
        previous["patched_snippet"]
    )


def test_smoke_the_request_was_built_from_measured_cases_only(
    dead_guard_first_pass,
):
    """§7/§8 — what the model actually saw."""

    _state, calls, _before = dead_guard_first_pass
    (prompt,) = calls

    assert T6_TASK in prompt
    assert "core/code_dna.py::_classify_indent" in prompt
    assert "expected='2space' observed='4space' status=still_reproduced" in prompt
    assert "indentation_style.generalize.2space.deep" in prompt
    assert "expected='4space' observed='4space' status=preserved" in prompt
    for word in ("gcd", "lstrip", "divisor", "local variable", "branch order"):
        assert word not in prompt.lower()


def test_smoke_a_bad_revision_stops_cleanly_with_no_third_attempt(
    t6_pre_probe, monkeypatch
):
    """§31 — Candidate1 rejected, budget spent, escalation raised, repo clean."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, calls = _drive(
        state, monkeypatch, _revision_response(INVERTED_REORDER_BODY)
    )

    assert len(calls) == 1
    assert block["candidate_revision_attempt_count"] == 1
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_BUT_REGRESSIVE
    assert block["candidate_verification_status"] == REJECTED
    assert block["needs_escalation"] is True
    assert block["human_review_eligible"] is False
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["candidate_revision_model_call_budget_remaining"] == 0


def test_smoke_a_second_revision_is_never_requested(t6_pre_probe, monkeypatch):
    """§2/§38 — re-entering the branch does not buy another call."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, calls = _drive(
        state, monkeypatch, _revision_response(INVERTED_REORDER_BODY)
    )
    assert len(calls) == 1

    pipeline._verify_authored_candidate_without_mutation(state)
    assert len(calls) == 1
    assert block["candidate_revision_attempt_count"] == 1
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED


@pytest.mark.parametrize(
    "response,outcome,reason",
    [
        ("this is not json", OUTCOME_REVISION_OUTPUT_INVALID, OUTPUT_NO_JSON_PAYLOAD),
        (
            "AGENT_ERROR: Gemini Final Error: all models failed",
            OUTCOME_REVISION_UNAVAILABLE,
            OUTPUT_PROVIDER_ERROR,
        ),
    ],
)
def test_smoke_an_unusable_revision_stops_without_a_further_call(
    t6_pre_probe, monkeypatch, response, outcome, reason
):
    """§20/§45 — one failed attempt consumes the single opportunity."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, calls = _drive(state, monkeypatch, response)

    assert len(calls) == 1
    assert block["candidate_revision_outcome"] == outcome
    assert block["candidate_revision_output_rejection_reason"] == reason
    assert block["candidate_revision_present"] is False
    # Candidate0's own rejection is what the payload still carries.
    assert block["candidate_verification_status"] == REJECTED
    assert block["needs_escalation"] is True
    assert block["execution_authorized"] is False


def test_smoke_a_no_op_revision_is_rejected_by_the_frozen_minimality_gate(
    t6_pre_probe, monkeypatch
):
    """§21/§39 — Candidate1 re-enters PATCH.MINIMAL.LIVE.1, and stops there."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, calls = _drive(state, monkeypatch, _revision_response(T6_BODY))

    assert len(calls) == 1
    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert block["patch_candidate"] is None
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED
    assert block["needs_escalation"] is True
    assert block["execution_authorized"] is False


def test_smoke_a_structurally_novel_revision_is_rejected_by_safe_minimal(
    t6_pre_probe, monkeypatch
):
    """§22 — Candidate1 re-enters PATCH.MINIMAL.LIVE.2 with no special favour."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    block, calls = _drive(
        state, monkeypatch, _revision_response(NOVEL_IMPORT_BODY)
    )

    assert len(calls) == 1
    assert block["candidate_novelty_admitted"] is False
    assert block["patch_candidate"] is None
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED
    assert block["needs_escalation"] is True


def test_smoke_a_revision_built_on_the_rejected_candidate_is_refused(
    t6_pre_probe, monkeypatch
):
    """§10 — the base is the original source, checked on the live target."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    response = _revision_response(
        CORRECT_LOCAL_ONLY_BODY, target_snippet=_with_body(DEAD_GUARD_BODY)
    )
    block, calls = _drive(state, monkeypatch, response)

    assert len(calls) == 1
    assert block["candidate_revision_outcome"] == OUTCOME_REVISION_OUTPUT_INVALID
    assert block["candidate_revision_output_rejection_reason"] == (
        OUTPUT_NOT_BASED_ON_ORIGINAL_SOURCE
    )
    assert block["patch_candidate"]["patched_snippet"] == _with_body(DEAD_GUARD_BODY)


def test_smoke_the_inverted_reorder_is_eligible_and_revisable(
    t6_pre_probe, monkeypatch
):
    """§32 — fixed_but_regressive is deterministic counterevidence too."""

    # A verified revision needs the five-case oracle; see dead_guard_first_pass.
    pin_live5_indentation_matrix(monkeypatch)
    state = _t6_state(_with_body(INVERTED_REORDER_BODY), t6_pre_probe)
    block, calls = _drive(
        state, monkeypatch, _revision_response(CORRECT_LOCAL_ONLY_BODY)
    )

    assert len(calls) == 1
    assert block["candidate_revision_eligible"] is True
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_AND_PRESERVED
    assert block["execution_authorized"] is False


def test_smoke_the_round8_ceiling_is_eligible_and_its_depth_cases_are_shown(
    t6_pre_probe, monkeypatch
):
    """§33 — the failed depth cases go back, and no algorithm does."""

    # A verified revision needs the five-case oracle; see dead_guard_first_pass.
    pin_live5_indentation_matrix(monkeypatch)
    state = _t6_state(_with_body(ROUND8_CEILING_BODY), t6_pre_probe)
    block, calls = _drive(
        state, monkeypatch, _revision_response(CORRECT_LOCAL_ONLY_BODY)
    )

    (prompt,) = calls
    assert block["candidate_revision_eligible"] is True
    assert "indentation_style" in prompt
    for word in ("gcd", "lstrip", "divisor"):
        assert word not in prompt.lower()
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED


def test_smoke_an_exact_no_op_candidate_never_reaches_the_provider(
    t6_pre_probe, monkeypatch
):
    """§34 — cheap-first behaviour is preserved exactly."""

    started = time.perf_counter()
    state = _t6_state(T6_TARGET, t6_pre_probe)
    block, calls = _drive(state, monkeypatch, None)

    assert calls == []
    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert block["candidate_revision_eligible"] is False
    assert block["candidate_revision_attempted"] is False
    assert block["candidate_revision_ineligible_reasons"] == [
        INELIGIBLE_CANDIDATE_NO_OP
    ]
    assert block["candidate_revision_model_call_budget_consumed"] == 0
    # No probe, no sandbox, no model call: the whole path is a byte comparison.
    assert time.perf_counter() - started < 5.0


def test_smoke_a_safe_minimal_rejection_never_reaches_the_provider(
    t6_pre_probe, monkeypatch
):
    """§35 — a policy refusal is not negotiated by prompt."""

    state = _t6_state(_with_body(NOVEL_IMPORT_BODY), t6_pre_probe)
    block, calls = _drive(state, monkeypatch, None)

    assert calls == []
    assert block["candidate_novelty_admitted"] is False
    assert block["candidate_revision_attempted"] is False
    assert block["candidate_revision_ineligible_reasons"] == [
        INELIGIBLE_SAFE_MINIMAL_REJECTED
    ]


def test_smoke_a_first_draft_success_costs_no_extra_call(t6_pre_probe, monkeypatch):
    """§28/§46 — T1/T2/T3 shape: nothing to revise, nothing spent."""

    # A verified first draft needs the five-case oracle; see dead_guard_first_pass.
    pin_live5_indentation_matrix(monkeypatch)
    state = _t6_state(_with_body(CORRECT_LOCAL_ONLY_BODY), t6_pre_probe)
    block, calls = _drive(state, monkeypatch, None)

    assert calls == []
    assert block["candidate_verification_status"] == VERIFIED
    assert block["candidate_revision_eligible"] is False
    assert block["candidate_revision_attempted"] is False
    assert block["candidate_revision_ineligible_reasons"] == [
        INELIGIBLE_CANDIDATE_VERIFIED
    ]
    assert block["candidate_revision_previous_candidate_fingerprint"] == ""
    assert block["execution_authorized"] is False


def test_smoke_an_explicit_change_route_is_left_alone(t6_pre_probe, monkeypatch):
    """§47 — feature authoring keeps its own contract in LIVE.1."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    state.json_block["patch_basis"] = PATCH_BASIS_EXPLICIT_CHANGE_REQUEST
    block, calls = _drive(state, monkeypatch, None)

    assert calls == []
    assert block["candidate_revision_attempted"] is False
    assert INELIGIBLE_PATCH_BASIS_NOT_GROUNDED in (
        block["candidate_revision_ineligible_reasons"]
    )


def test_smoke_a_read_only_route_never_reaches_the_revision_branch(
    t6_pre_probe, monkeypatch
):
    """§48 — analysis_only authors nothing, so it revises nothing."""

    state = _t6_state(_with_body(DEAD_GUARD_BODY), t6_pre_probe)
    # A real WAITER read-only receipt, not just a workflow string: the guard
    # reads ``change_requested`` off a receipt it recognises.
    read_only = {
        "phase_id": WAITER_PHASE_ID,
        "selected_workflow": WORKFLOW_ANALYSIS_ANSWER,
        "change_requested": False,
    }
    state.live_route = read_only
    state.control_result["live_route"] = dict(read_only)
    assert route_is_read_only(state.live_route) is True

    block, calls = _drive(state, monkeypatch, None)

    assert calls == []
    # The read-only guard returns before the candidate lifecycle is entered at
    # all, so no revision decision is even recorded.
    assert "candidate_revision_outcome" not in block
    assert block.get("execution_authorized") is not True


# ═══════════════════════════════════════════════════════════════════════════
# Governance
# ═══════════════════════════════════════════════════════════════════════════

FIXTURE = ROOT / "tests" / "fixtures" / "patch_author_live1_frozen_boundaries.json"
#: PATCH.AUTHOR.LIVE.2 changed core/pipeline.py after this phase did, so the
#: shipped file is two phases downstream of the bytes pinned here.  Undoing
#: LIVE.2 first reproduces this fixture's post file exactly, which keeps
#: post_sha256 a live assertion rather than a stale number.
LIVE2_FIXTURE = (
    ROOT / "tests" / "fixtures" / "patch_author_live2_contract_reversal.json"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _without_live2(path: str, text: str) -> str:
    """Undo the harness remediation, then LIVE.2, to reconstruct LIVE.1's post.

    Both later changes are undone from their own receipts and every link is
    asserted: the remediation helper checks its own digests, the LIVE.2 post
    digest is checked here, and the caller then proves LIVE.1's exact bytes and
    definition scope.
    """

    live2 = json.loads(LIVE2_FIXTURE.read_text(encoding="utf-8"))
    reversal = next(r for r in live2["reversals"] if r["path"] == path)
    text = before_harness_remediation(path, text.encode("utf-8")).decode("utf-8")
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == reversal["post_sha256"]
    for hunk in reversal["hunks"]:
        assert text.count(hunk["post"]) == 1
        text = text.replace(hunk["post"], hunk["pre"])
    return text


def test_every_frozen_file_is_byte_identical():
    """Historical §49 boundaries reconstruct after authorized maintenance."""

    for rel, digest in _fixture()["files"].items():
        actual = hashlib.sha256(before_harness_remediation(rel)).hexdigest()
        assert actual == digest, rel


def test_the_pipeline_change_is_a_reversible_containment_proof():
    """The pre-phase bytes are reproducible from the shipped file."""

    fixture = _fixture()["pipeline"]
    # Bytes, not text: pipeline.py is CRLF and the stored hunks are too.
    text = _without_live2(
        fixture["path"], (ROOT / fixture["path"]).read_bytes().decode("utf-8")
    )
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == fixture["post_sha256"]

    for hunk in fixture["hunks"]:
        assert text.count(hunk["post"]) == 1
        text = text.replace(hunk["post"], hunk["pre"])
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == fixture["pre_sha256"]


def test_only_the_read_only_branch_moved_inside_the_pipeline():
    """Seven new definitions, none removed, exactly one existing one changed."""

    fixture = _fixture()["pipeline"]
    post_text = _without_live2(
        fixture["path"], (ROOT / fixture["path"]).read_bytes().decode("utf-8")
    )
    pre_text = post_text
    for hunk in fixture["hunks"]:
        pre_text = pre_text.replace(hunk["post"], hunk["pre"])

    def definitions(source: str) -> dict[str, str]:
        return {
            node.name: hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    before, after = definitions(pre_text), definitions(post_text)
    assert len(before) == fixture["top_level_definitions"] == 35
    assert sorted(set(before) - set(after)) == fixture[
        "removed_top_level_definitions"
    ] == []
    assert sorted(set(after) - set(before)) == fixture[
        "added_top_level_definitions"
    ] == [
        "_call_revision_provider",
        "_drop_candidate_bound_receipts",
        "_maybe_revise_rejected_candidate",
        "_record_candidate_revision",
        "_revision_attempts_already_made",
        "_revision_author_configuration",
        "_run_read_only_candidate_lifecycle",
    ]
    changed = sorted(n for n in before if n in after and before[n] != after[n])
    assert changed == fixture["changed_top_level_definitions"] == [
        "_verify_authored_candidate_without_mutation"
    ]


def test_the_extracted_lifecycle_is_the_body_it_replaced():
    """The producers, and their order, are the ones that were already there."""

    source = inspect.getsource(pipeline._run_read_only_candidate_lifecycle)
    order = [
        source.index(name)
        for name in (
            "_drop_stale_candidate_validation",
            "evaluate_patch_safety",
            "_record_candidate_sandbox_validation",
            "_record_candidate_defect_closure",
            "_record_targeted_repository_validation",
            "_record_candidate_verification",
            "_record_execution_eligibility",
        )
    ]
    assert order == sorted(order)
    assert "run_gemini_request" not in source
    assert "_call_revision_provider" not in source


def test_the_real_classify_indent_is_untouched():
    """§0/§49 — this phase measures the defect; it does not repair it."""

    live = inspect.getsource(_classify_indent)
    assert live == T6_TARGET
    assert T6_BODY in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    for body in (CORRECT_LOCAL_ONLY_BODY, DEAD_GUARD_BODY, ROUND8_CEILING_BODY):
        assert body not in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert "gcd" not in live


def test_the_module_is_pure_and_stdlib_only():
    """§43/§44 — evidence construction opens nothing and reaches nothing."""

    source = (ROOT / "core" / "candidate_revision.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert modules <= {
        "__future__",
        "core",  # core.json_utils only, itself stdlib-pure
        "dataclasses",
        "hashlib",
        "json",
        "re",
        "typing",
    }
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & {"open", "exec", "eval", "compile", "input", "__import__"})
    for forbidden in ("requests", "httpx", "urllib", "subprocess", "os.walk"):
        assert forbidden not in source
    # It names no provider: the one call lives in the pipeline adapter.
    assert "run_gemini_request" not in source


def test_the_revision_call_is_one_named_adapter_with_no_retry():
    """§2/§14/§38 — one request, the draft role, no loop and no reviewer."""

    source = inspect.getsource(pipeline._call_revision_provider)
    assert source.count("run_gemini_request") == 1
    assert "for " not in source and "while " not in source

    adapter = inspect.getsource(pipeline._maybe_revise_rejected_candidate)
    assert adapter.count("_call_revision_provider(") == 1
    for forbidden in (
        "run_deepseek_review",
        "run_review_pipeline",
        "_run_one_review_round",
        "run_self_correct_loop",
        "retrieve_context",
        "build_graph",
        "build_control_prompt",
    ):
        assert forbidden not in adapter, forbidden

    provider, model = pipeline._revision_author_configuration()
    from config import MODELS

    assert provider == "google"
    assert model == MODELS[0]


def test_the_revision_telemetry_is_owned_by_the_control_plane():
    """§41 — harness-authored, and disjoint from the answer surface."""

    from core.answer_entity_grounding import _ANSWER_SURFACE_KEYS

    keys = set(pipeline._CANDIDATE_REVISION_KEYS)
    assert not (keys & set(_ANSWER_SURFACE_KEYS))
    for answer_key in ("summary", "issues", "patch_candidate", "confidence"):
        assert answer_key not in keys

    receipt = CandidateRevisionReceipt(
        eligible=True,
        attempted=True,
        attempt_count=1,
        outcome=OUTCOME_REVISED_CANDIDATE_VERIFIED,
        trigger=TRIGGER_BEHAVIORAL_COUNTEREXAMPLE,
    )
    assert set(receipt.as_telemetry()) <= keys


def test_answer_grounding_cannot_rewrite_the_revision_receipt(
    dead_guard_first_pass,
):
    """§41 — ANSWER.GROUND.LIVE.4 may not touch these statuses or counters."""

    from core.answer_entity_grounding import ground_answer_for_display

    state, _calls, _before = dead_guard_first_pass
    block = json.loads(json.dumps(state.json_block))
    before = {key: block.get(key) for key in pipeline._CANDIDATE_REVISION_KEYS}

    _text, _human, display, _receipt = ground_answer_for_display(state, "", block)

    after = {key: display.get(key) for key in pipeline._CANDIDATE_REVISION_KEYS}
    assert after == before
    # And grounding did not silently drop the group either.
    assert after["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED
    assert after["candidate_revision_attempt_count"] == 1


def test_the_guardrails_say_what_this_phase_refuses():
    guardrails = candidate_revision_guardrails()

    assert guardrails["max_revision_calls_per_run"] == MAX_REVISION_CALLS_PER_RUN == 1
    for key in (
        "no_op_candidate_can_trigger_revision",
        "safe_minimal_rejection_can_trigger_revision",
        "stale_candidate_can_trigger_revision",
        "malformed_candidate_can_trigger_revision",
        "revision_supplies_implementation_hints",
        "revision_reveals_hidden_reasoning",
        "revision_reuses_previous_candidate_receipts",
        "revision_adds_reviewer_or_debate_calls",
        "revision_performs_retrieval",
        "revision_traverses_the_repository",
        "revision_changes_validation_budgets",
        "revision_grants_execution_authority",
        "revision_widens_auto_apply",
        "revision_mutates_the_repository",
    ):
        assert guardrails[key] is False, key


def test_the_registry_entry_is_present_and_honest():
    registry = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    phases = {entry["phase_id"]: entry for entry in registry["phases"]}
    phase = phases[PHASE_ID]

    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is True
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    for required in (
        "PATCH.MINIMAL.LIVE.1",
        "PATCH.MINIMAL.LIVE.2",
        "DEFECT.PROBE.LIVE.4",
        "CANDIDATE.VERIFY.LIVE.1",
        "DEFECT.FACT.LIVE.1",
        "PATCH.BASIS.LIVE.1",
        "OPS.PATCH.2",
        "CONTROL.LOCALIZE.LIVE.2",
        "RETRIEVE.LIVE.4",
        "EXEC.POLICY.LIVE.1",
        "EXEC.APPROVAL.LIVE.1",
        "EXEC.AUTH.LIVE.1",
    ):
        assert required in phase["prerequisites"], required


def test_evidence_construction_is_negligible_next_to_a_provider_call():
    """§43 — the unavoidable cost is the call, not the receipt."""

    evidence = _evidence()
    started = time.perf_counter()
    for _ in range(200):
        assess_candidate_revision(evidence)
    assert time.perf_counter() - started < 2.0

    receipt = assess_candidate_revision(evidence).evidence
    started = time.perf_counter()
    for _ in range(200):
        build_revision_prompt(receipt, _contract())
    assert time.perf_counter() - started < 2.0
