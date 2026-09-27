"""CANDIDATE.VERIFY.LIVE.1 — read-only candidate verification before human review.

The claim under test is a lifecycle claim: ``AUTO_PATCH_ENABLED=false`` must
disable mutation and *only* mutation.  Before this phase it also disabled the
candidate sandbox, the paired post-probe, defect closure, targeted validation,
the oracle assessment and the exact candidate fingerprint — while the authored
candidate was still shown to a human.  The exact T6 branch-reorder candidate is
the counter-example the phase exists for and it appears here verbatim.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

from _harness_maintenance import before_harness_remediation

import core.candidate_verification as verification
import core.pipeline as pipeline
from core.agent_state import AgentState
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    extract_behavioral_expectations,
)
from core.candidate_sandbox_validation import (
    candidate_fingerprint_from_payload,
    patch_plan_fingerprint,
)
from core.candidate_verification import (
    COMPONENT_EXACT_SANDBOX,
    COMPONENT_IDS,
    COMPONENT_INCONCLUSIVE,
    COMPONENT_INVALID,
    COMPONENT_NOT_APPLICABLE,
    COMPONENT_ORACLE_ASSESSMENT,
    COMPONENT_PAIRED_PROBE,
    COMPONENT_PATCH_SAFETY,
    COMPONENT_STALE,
    COMPONENT_TARGETED_VALIDATION,
    COMPONENT_UNAVAILABLE,
    CONTRADICTING,
    INCONCLUSIVE,
    INVALID,
    LIMITATION_NO_RELEVANT_EXISTING_CHECKS,
    PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE,
    PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
    REASON_CANDIDATE_FINGERPRINT_STALE,
    REASON_CANDIDATE_MISSING,
    REASON_PATCH_SAFETY_BLOCKED,
    REASON_PRESERVATION_REGRESSED,
    REASON_PRIMARY_DEFECT_NOT_CLOSED,
    REASON_PROBE_FINGERPRINT_STALE,
    REASON_REQUIRED_EVIDENCE_MISSING,
    REASON_SOURCE_STATE_STALE,
    REASON_TARGET_BINDING_STALE,
    REASON_TARGETED_EVIDENCE_TAMPERED,
    REASON_TARGETED_GENUINE_REGRESSION,
    REJECTED,
    REASON_SUBJECT_INVARIANT_NOT_CLOSED,
    REJECTION_REASONS,
    STALE,
    SUPPORTING,
    UNAVAILABLE,
    VERIFICATION_STATUSES,
    VERIFIED,
    CandidateVerificationReceipt,
    candidate_verification_guardrails,
    candidate_verification_is_current,
    candidate_verification_status_of_payload,
    evaluate_candidate_verification,
    verification_profile_for_basis,
)
from core.code_dna import _classify_indent
from core.defect_probe import (
    PROBE_REPRODUCED,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
from core.execution_eligibility_policy import (
    INELIGIBLE,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
)
from core.human_apply_authorization import (
    DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE,
    HUMAN_ACTION_APPLY,
    authorize_human_apply,
)
from core.paired_defect_probe import (
    PAIRED_FIXED_AND_PRESERVED,
    PAIRED_FIXED_BUT_REGRESSIVE,
    PRESERVATION_REGRESSED,
    evaluate_paired_defect_closure,
)
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
)
from core.live_task_routing import PHASE_ID as WAITER_PHASE_ID
from core.patch_safety import evaluate_patch_safety
from core.phase_registry import PHASE_ID_PREFIXES, load_phase_registry
from core.targeted_repository_validation import (
    build_targeted_validation_request,
    validate_targeted_candidate,
)
from graph.schema import build_graph


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _no_live_revision_call(monkeypatch):
    """PATCH.AUTHOR.LIVE.2 — keep this suite's provider budget at zero.

    These tests measure Candidate0's own lifecycle.  PATCH.AUTHOR.LIVE.1 hands a
    behaviorally rejected candidate back to its author, and until LIVE.2 that
    request carried no candidate wire contract, so the answer was unusable and
    Candidate0's receipts happened to survive for these assertions to read.
    That was luck, and it was a live provider call besides.  Making the single
    revision opportunity deterministically unavailable keeps the measurement on
    Candidate0 and calls nothing; the revision path itself is owned, and
    exercised, by tests/test_candidate_revision_live.py and
    tests/test_patch_authoring_contract_live2.py.
    """

    monkeypatch.setattr(pipeline, "_call_revision_provider", lambda _state, _prompt: "")

REGISTRY = ROOT / "docs" / "roadmap" / "phase_registry.json"

T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The exact branch ordering that ships today and the model's minimal,
#: safe_minimal-acceptable rewrite of it.  Copied verbatim from the
#: DEFECT.PROBE.LIVE.3 suite so both phases measure the same bytes.
T6_BASELINE_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
)
T6_REORDERED_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
)

#: §9 positive control.  It resolves the prefix overlap by measuring the actual
#: leading-space width, so it answers both widths correctly.
T6_DISTINGUISHING_TARGET = (
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
#: DEFECT.PROBE.LIVE.4 re-homed this control.  The candidate that used to
#: stand here returned the *smallest* observed indentation width, which
#: closes DEFECT.PROBE.LIVE.3's two-point oracle and still cannot classify a
#: 2-space sample whose shallowest line is six spaces wide.  The bounded
#: behavioral matrix measures that as partially_fixed, so it is no longer a
#: correct candidate and cannot carry '§9 verification opens' any more.  It
#: is kept below as T6_SUBJECT_INVARIANT_OPEN_PATCHED, with a test recording
#: exactly what became of it.  This one infers the base indentation unit as
#: the greatest common divisor of the observed widths, which is what the
#: subject invariant says, so it answers every bounded case.  Test-only: it
#: is never applied to production ``_classify_indent``.
T6_DISTINGUISHING_PATCHED = (
    "    counts = Counter()\n"
    "    space_widths = []\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "        else:\n"
    '            space_widths.append(len(line) - len(line.lstrip(" ")))\n'
    '    if counts["tab"] > len(space_widths):\n'
    '        return "tab"\n'
    "    if space_widths:\n"
    "        unit = 0\n"
    "        for width in space_widths:\n"
    "            left, right = unit, width\n"
    "            while right:\n"
    "                left, right = right, left % right\n"
    "            unit = left\n"
    '        return "2space" if 0 < unit <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)
#: INDENT.SEMANTICS.1 re-homed the pipeline half of that role.  The
#: greatest-common-divisor candidate above reads every physical leading-space
#: width, continuation alignment and docstring interiors included, so the
#: eight-case matrix rejects it on its two Python structural cases.  It still
#: carries DEFECT.PROBE.LIVE.3's two-point tests below, where it is correct, and
#: a test records its new pipeline verdict.  "Verification opens" moved to
#: INDENT.SEMANTICS.1's test-only structural control, which closes all eight
#: bounded cases.  It tokenizes its input as Python because the target takes no
#: language, so it is a control and never a production fix, and safe_minimal
#: refuses it; tests/test_indent_semantics1.py measures all three facts.
from tests.test_indent_semantics1 import (  # noqa: E402
    T6_STRUCTURAL_CONTROL_BODY as T6_STRUCTURAL_CONTROL_PATCHED,
)

#: The former control, kept verbatim so the invariant it now carries is the
#: measured one: a candidate whose subject invariant is still open is
#: rejected rather than verified.
T6_SUBJECT_INVARIANT_OPEN_PATCHED = (
    "    counts = Counter()\n"
    "    space_widths = []\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "        else:\n"
    '            space_widths.append(len(line) - len(line.lstrip(" ")))\n'
    '    if counts["tab"] > len(space_widths):\n'
    '        return "tab"\n'
    "    if space_widths:\n"
    '        return "2space" if min(space_widths) <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)


# ---------------------------------------------------------------------------
# Shared fixtures — the exact T6 order, never a hand-built stand-in
# ---------------------------------------------------------------------------


def _t6_behavior_fact() -> BehavioralExpectation:
    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    (fact,) = facts
    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    assert fact.expected_value == "2space"
    assert fact.observed_value == "4space"
    assert fact.provenance == PROVENANCE_EXPLICIT_USER_FACT
    return fact


def _t6_source_snippet() -> str:
    return inspect.getsource(_classify_indent)


def _t6_binding():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=_t6_source_snippet(),
        candidate_eligible=True,
    )
    assert binding is not None
    return binding


def _t6_contract():
    contract = build_probe_contract_from_behavior_fact(
        target=_t6_binding(), behavior_fact=_t6_behavior_fact()
    )
    assert contract is not None
    return contract


def _t6_candidate(target: str, patched: str) -> dict[str, Any]:
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert target in source
    return {
        "file": T6_TARGET_FILE,
        "relative_path": T6_TARGET_FILE,
        "target_node_kind": "function",
        "target_node_name": T6_TARGET_SYMBOL,
        "target_snippet": target,
        "patched_snippet": patched,
    }


def _t6_plan(target: str, patched: str) -> list[dict[str, Any]]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


@pytest.fixture(scope="module")
def t6_pre_probe():
    """The real pre-patch reproduction, measured once for every reader."""

    contract = _t6_contract()
    receipt = execute_defect_probe(contract, repo_path=ROOT)
    assert receipt.probe_result == PROBE_REPRODUCED
    return contract, receipt


def _paired(plan, t6_pre_probe):
    contract, pre = t6_pre_probe
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    assert safety.get("ok") is True
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    paired = evaluate_paired_defect_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_behavior_fact(),
        expected_candidate_fingerprint=patch_plan_fingerprint(plan),
    )
    # The real repository is only ever read.  Guarded on every run.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    return paired, safety, pre


@pytest.fixture(scope="module")
def t6_regressive_evidence(t6_pre_probe):
    plan = _t6_plan(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)
    return (plan,) + _paired(plan, t6_pre_probe)


@pytest.fixture(scope="module")
def t6_correct_evidence(t6_pre_probe):
    plan = _t6_plan(T6_DISTINGUISHING_TARGET, T6_DISTINGUISHING_PATCHED)
    return (plan,) + _paired(plan, t6_pre_probe)


def _evidence_from(plan, paired, safety, pre, **overrides) -> dict[str, Any]:
    """One live-shaped evidence mapping, exactly as the pipeline assembles it."""

    fingerprint = patch_plan_fingerprint(plan)
    payload = {**paired.as_telemetry()}
    payload.update(
        {
            "targeted_validation_status": "inconclusive",
            "targeted_validation_category": "no_relevant_existing_checks",
            "candidate_fingerprint": fingerprint,
            "check_oracle_assessment_status": "current",
            "check_oracle_candidate_fingerprint": fingerprint,
            "check_oracle_role_counts": {},
        }
    )
    evidence = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_fingerprint": fingerprint,
        "candidate_target_paths": [T6_TARGET_FILE],
        "patch_safety": {**safety, "candidate_fingerprint": fingerprint},
        "pre_probe": pre.as_dict(),
        "full_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "candidate_defect_closure": payload,
        "targeted_validation": payload,
        "oracle_assessment": payload,
        "candidate_sandbox_validation": payload,
    }
    evidence.update(overrides)
    return evidence


# ---------------------------------------------------------------------------
# §7 — the closed vocabulary and the type's own refusals
# ---------------------------------------------------------------------------


def test_verification_vocabulary_is_closed_and_carries_no_authority():
    assert VERIFICATION_STATUSES == (
        "verified",
        "rejected",
        "inconclusive",
        "unavailable",
        "stale",
        "invalid",
    )
    receipt = CandidateVerificationReceipt(
        status=VERIFIED,
        policy_profile=PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
        candidate_fingerprint="a" * 64,
        components=(),
    )
    assert receipt.execution_authorized is False
    assert receipt.final_repository_changed is False
    assert receipt.authority_effect == "none"
    telemetry = receipt.as_telemetry()
    assert telemetry["candidate_verification_execution_authorized"] is False
    assert telemetry["candidate_verification_final_repository_changed"] is False
    assert telemetry["candidate_verification_authority_effect"] == "none"
    assert telemetry["candidate_verification_auto_apply_effect"] == "none"
    assert telemetry["candidate_verification_model_calls"] == 0
    assert telemetry["candidate_verification_network_calls"] == 0
    assert telemetry["candidate_verification_repository_mutations"] == 0
    assert "confidence" not in json.dumps(telemetry)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "passed"},
        {"authority_effect": "grants_apply"},
        {"rejection_reasons": ("not_a_real_reason",)},
        {"accepted_limitations": ("anything_goes",)},
        {"status": VERIFIED, "rejection_reasons": (REASON_PRESERVATION_REGRESSED,)},
    ],
)
def test_receipt_refuses_values_outside_its_closed_vocabulary(kwargs):
    base = {
        "status": REJECTED,
        "policy_profile": PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
        "candidate_fingerprint": "a" * 64,
        "components": (),
    }
    with pytest.raises(ValueError):
        CandidateVerificationReceipt(**{**base, **kwargs})


def test_profile_is_derived_from_the_existing_typed_patch_basis():
    assert (
        verification_profile_for_basis(PATCH_BASIS_GROUNDED_DEFECT)
        == PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE
    )
    assert (
        verification_profile_for_basis(PATCH_BASIS_EXPLICIT_CHANGE_REQUEST)
        == PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE
    )


def test_rejection_reasons_render_in_the_canonical_structured_issue_shape():
    """§23 — no new plain-string drift into the existing ``issues`` list."""

    receipt = CandidateVerificationReceipt(
        status=REJECTED,
        policy_profile=PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
        candidate_fingerprint="a" * 64,
        components=(),
        rejection_reasons=(REASON_PRESERVATION_REGRESSED,),
    )
    (issue,) = receipt.as_issues()
    assert set(issue) == {"severity", "type", "file", "symbol", "reason", "fix", "code"}
    assert issue["severity"] == "high"
    assert issue["type"] == "candidate_verification"
    assert issue["code"] in REJECTION_REASONS
    assert isinstance(issue["reason"], str) and issue["reason"]


# ---------------------------------------------------------------------------
# §8 — the known wrong T6 candidate, measured against the real repository
# ---------------------------------------------------------------------------


def test_known_wrong_t6_candidate_is_structurally_minimal_and_safety_accepted(
    t6_regressive_evidence,
):
    """§19 — safe_minimal accepting this candidate is correct, not a bug."""

    plan, _paired_receipt, safety, _pre = t6_regressive_evidence
    (operation,) = plan
    assert safety.get("ok") is True

    # The whole candidate is a reordering of two existing ``elif`` branches:
    # one file, identical token multiset, no new identifier, no new API.  Shape
    # safety has nothing to object to, and §19 says that is the right answer.
    assert len(plan) == 1
    assert operation["relative_path"] == T6_TARGET_FILE
    assert sorted(operation["target_snippet"].split()) == sorted(
        operation["patched_snippet"].split()
    )
    assert operation["target_snippet"] != operation["patched_snippet"]


def test_known_wrong_t6_candidate_is_rejected_by_candidate_verification(
    t6_regressive_evidence,
):
    """§8 — the principal acceptance test."""

    plan, paired, safety, pre = t6_regressive_evidence

    # The evidence itself, first: primary fixed, preservation regressed.
    assert paired.primary_case()["candidate_observed"] == "2space"
    (case,) = paired.preservation_cases
    assert case.status == PRESERVATION_REGRESSED
    assert paired.paired_status == PAIRED_FIXED_BUT_REGRESSIVE

    receipt = evaluate_candidate_verification(
        _evidence_from(plan, paired, safety, pre)
    )

    assert receipt.status == REJECTED
    assert receipt.rejection_reasons == (REASON_PRESERVATION_REGRESSED,)
    assert receipt.component_verdict(COMPONENT_PATCH_SAFETY) == SUPPORTING
    assert receipt.component_verdict(COMPONENT_EXACT_SANDBOX) == SUPPORTING
    assert receipt.component_verdict(COMPONENT_PAIRED_PROBE) == CONTRADICTING
    assert receipt.review_ready is False
    assert receipt.needs_escalation is True
    assert receipt.execution_authorized is False
    assert receipt.final_repository_changed is False
    assert receipt.candidate_fingerprint == patch_plan_fingerprint(plan)
    # §10 — still readable, with its evidence attached.
    assert receipt.visible_for_debugging is True
    assert "not verified" in verification.describe_candidate_verification(receipt)


def test_high_model_confidence_cannot_rescue_the_rejected_candidate(
    t6_regressive_evidence,
):
    """§22 — the smoke carried confidence=0.4; it is not an input here at all."""

    plan, paired, safety, pre = t6_regressive_evidence
    baseline = evaluate_candidate_verification(
        _evidence_from(plan, paired, safety, pre)
    )
    for value in (0.0, 0.4, 0.99, 1.0):
        boosted = evaluate_candidate_verification(
            _evidence_from(
                plan,
                paired,
                safety,
                pre,
                confidence=value,
                writer_confidence=value,
                localization_strength=value,
            )
        )
        assert boosted.as_dict() == baseline.as_dict()
        assert boosted.status == REJECTED


def test_primary_fixed_alone_is_never_flattened_into_verified(
    t6_regressive_evidence,
):
    """§18 — the paired result governs, whatever the primary case says."""

    plan, paired, safety, pre = t6_regressive_evidence
    evidence = _evidence_from(plan, paired, safety, pre)
    # Force the single-case fields to the pre-DEFECT.PROBE.LIVE.3 reading and
    # leave the preservation case intact: verification must still reject.
    flattened = copy.deepcopy(evidence["candidate_defect_closure"])
    flattened["defect_closure_status"] = "fixed"
    flattened["paired_status"] = "fixed"
    evidence["candidate_defect_closure"] = flattened
    receipt = evaluate_candidate_verification(evidence)
    assert receipt.status == REJECTED
    assert receipt.rejection_reasons == (REASON_PRESERVATION_REGRESSED,)


# ---------------------------------------------------------------------------
# §9 — the verified positive control
# ---------------------------------------------------------------------------


def test_width_distinguishing_candidate_is_verified_without_execution_authority(
    t6_correct_evidence,
):
    plan, paired, safety, pre = t6_correct_evidence
    assert paired.paired_status == PAIRED_FIXED_AND_PRESERVED

    receipt = evaluate_candidate_verification(
        _evidence_from(plan, paired, safety, pre)
    )

    assert receipt.status == VERIFIED
    assert receipt.rejection_reasons == ()
    assert receipt.review_ready is True
    assert receipt.needs_escalation is False
    # §15 — verification opened, and it still grants nothing.
    assert receipt.execution_authorized is False
    assert receipt.final_repository_changed is False
    # §7 — the one accepted limitation is stated, never hidden.
    assert LIMITATION_NO_RELEVANT_EXISTING_CHECKS in receipt.accepted_limitations
    assert receipt.component_verdict(COMPONENT_TARGETED_VALIDATION) == (
        COMPONENT_NOT_APPLICABLE
    )


def test_correct_and_wrong_candidates_are_distinguished_by_preservation_only(
    t6_correct_evidence, t6_regressive_evidence
):
    good = evaluate_candidate_verification(_evidence_from(*t6_correct_evidence))
    bad = evaluate_candidate_verification(_evidence_from(*t6_regressive_evidence))
    assert good.status == VERIFIED and bad.status == REJECTED
    assert good.component_verdict(COMPONENT_EXACT_SANDBOX) == SUPPORTING
    assert bad.component_verdict(COMPONENT_EXACT_SANDBOX) == SUPPORTING
    assert good.candidate_fingerprint != bad.candidate_fingerprint


# ---------------------------------------------------------------------------
# §7 — availability, and never converting missing evidence into a pass
# ---------------------------------------------------------------------------


def _verified_evidence() -> dict[str, Any]:
    fingerprint = "a" * 64
    probe = "b" * 64
    source = "c" * 64
    closure = {
        "defect_closure_status": "fixed",
        "paired_status": "fixed_and_preserved",
        "post_probe_result": "not_reproduced",
        "preservation_oracle_status": "available",
        "preservation_cases": [{"case_id": "x", "status": "preserved"}],
        "candidate_fingerprint": fingerprint,
        "probe_fingerprint": probe,
        "sandbox_only": True,
        "candidate_probe_apply_status": "applied",
        "candidate_probe_sandbox_cleanup_ok": True,
        "targeted_validation_status": "passed",
        "targeted_validation_category": "targeted_checks_passed",
        "check_oracle_assessment_status": "current",
        "check_oracle_candidate_fingerprint": fingerprint,
        "check_oracle_role_counts": {},
    }
    return {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_fingerprint": fingerprint,
        "candidate_target_paths": ["core/code_dna.py"],
        "patch_safety": {"ok": True, "candidate_fingerprint": fingerprint},
        "pre_probe": {
            "probe_fingerprint": probe,
            "executed_source_sha256": source,
            "target_binding": {
                "file": "core/code_dna.py",
                "localized_source_sha256": source,
            },
        },
        "full_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "candidate_defect_closure": closure,
        "targeted_validation": closure,
        "oracle_assessment": closure,
        "candidate_sandbox_validation": closure,
    }


def test_the_synthetic_baseline_evidence_verifies():
    assert evaluate_candidate_verification(_verified_evidence()).status == VERIFIED


@pytest.mark.parametrize(
    "mutate, expected_status, expected_reason",
    [
        pytest.param(
            lambda e: e.pop("patch_safety"),
            UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            id="patch-safety-missing",
        ),
        pytest.param(
            lambda e: e.__setitem__("patch_safety", {"ok": False, "reasons": ["no"]}),
            REJECTED,
            REASON_PATCH_SAFETY_BLOCKED,
            id="patch-safety-blocked",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "candidate_probe_apply_status", "not_attempted"
            ),
            UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            id="sandbox-never-ran",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "candidate_probe_apply_status", "failed"
            ),
            REJECTED,
            verification.REASON_SANDBOX_APPLY_FAILED,
            id="sandbox-apply-failed",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__("sandbox_only", False),
            INVALID,
            verification.REASON_SANDBOX_NOT_ISOLATED,
            id="sandbox-not-isolated",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {"paired_status": "still_reproduced", "defect_closure_status": "still_reproduced"}
            ),
            REJECTED,
            REASON_PRIMARY_DEFECT_NOT_CLOSED,
            id="primary-still-reproduced",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {
                    "paired_status": "fixed_but_regressive",
                    "defect_closure_status": "fixed_but_regressive",
                }
            ),
            REJECTED,
            REASON_PRESERVATION_REGRESSED,
            id="preservation-regressed",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {"paired_status": "inconclusive", "defect_closure_status": "inconclusive"}
            ),
            INCONCLUSIVE,
            verification.REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
            id="paired-inconclusive",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {"paired_status": "unavailable", "defect_closure_status": "unavailable"}
            ),
            UNAVAILABLE,
            REASON_REQUIRED_EVIDENCE_MISSING,
            id="paired-unavailable",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {
                    "paired_status": "invalid_comparison",
                    "defect_closure_status": "invalid_comparison",
                }
            ),
            INVALID,
            verification.REASON_INVALID_COMPARISON,
            id="paired-invalid-comparison",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {
                    "targeted_validation_status": "failed",
                    "targeted_validation_category": "targeted_checks_failed",
                }
            ),
            REJECTED,
            REASON_TARGETED_GENUINE_REGRESSION,
            id="targeted-genuine-regression",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {
                    "targeted_validation_status": "inconclusive",
                    "targeted_validation_category": "selected_validation_check_modified",
                }
            ),
            INVALID,
            REASON_TARGETED_EVIDENCE_TAMPERED,
            id="candidate-edited-its-own-check",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].update(
                {
                    "targeted_validation_status": "inconclusive",
                    "targeted_validation_category": "sandbox_unavailable",
                }
            ),
            INCONCLUSIVE,
            verification.REASON_REQUIRED_EVIDENCE_INCONCLUSIVE,
            id="targeted-inconclusive",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "check_oracle_assessment_status", "stale_probe"
            ),
            STALE,
            verification.REASON_ORACLE_ASSESSMENT_STALE,
            id="oracle-stale",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "check_oracle_role_counts", {"conflict_unresolved": 1}
            ),
            REJECTED,
            verification.REASON_ORACLE_CONFLICT_UNRESOLVED,
            id="oracle-conflict-unresolved",
        ),
        pytest.param(
            lambda e: e.__setitem__("candidate_fingerprint", ""),
            UNAVAILABLE,
            REASON_CANDIDATE_MISSING,
            id="no-candidate",
        ),
    ],
)
def test_no_required_component_can_be_missing_and_still_verify(
    mutate, expected_status, expected_reason
):
    """§7 — availability-aware, and absence is never a pass."""

    evidence = _verified_evidence()
    mutate(evidence)
    receipt = evaluate_candidate_verification(evidence)
    assert receipt.status == expected_status
    assert expected_reason in receipt.rejection_reasons
    assert receipt.status != VERIFIED
    assert receipt.needs_escalation is True
    assert receipt.review_ready is False


def test_failing_checks_that_all_assert_the_defect_are_not_a_genuine_regression():
    """§16 — an existing defect-preservation test failing is not a regression.

    It is also not a pass: resolving that conflict belongs to EXEC.POLICY, so
    verification records it as inconclusive rather than deciding it twice.
    """

    evidence = _verified_evidence()
    evidence["candidate_defect_closure"].update(
        {
            "targeted_validation_status": "failed",
            "targeted_validation_category": "targeted_checks_failed",
            "check_oracle_assessments": [
                {
                    "oracle_role": "defect_preservation_oracle",
                    "candidate_result": "failed",
                    "assessment_status": "current",
                }
            ],
        }
    )
    receipt = evaluate_candidate_verification(evidence)
    assert receipt.status == INCONCLUSIVE
    assert receipt.component_verdict(COMPONENT_TARGETED_VALIDATION) == (
        COMPONENT_INCONCLUSIVE
    )


# ---------------------------------------------------------------------------
# §16 — targeted validation engages naturally, with its selector unchanged
# ---------------------------------------------------------------------------


def _tiny_repo(tmp_path: Path, assertion: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "core").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "core" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "core" / "calc.py").write_text(
        "def calc(a, b):\n    return a - b\n", encoding="utf-8"
    )
    (repo / "tests" / "test_calc.py").write_text(
        "from core.calc import calc\n\n\ndef test_calc():\n"
        f"    {assertion}\n",
        encoding="utf-8",
    )
    return repo


def _tiny_graph() -> Any:
    target = "core/calc.py::calc"
    return build_graph(
        [
            {"id": "core/calc.py", "type": "file"},
            {"id": target, "type": "function", "file": "core/calc.py"},
            {"id": "tests/test_calc.py", "type": "file"},
            {
                "id": "tests/test_calc.py::test_calc",
                "type": "function",
                "file": "tests/test_calc.py",
            },
        ],
        [
            {"source": "core/calc.py", "target": target, "type": "contains"},
            {
                "source": "tests/test_calc.py::test_calc",
                "target": target,
                "type": "resolved_call",
            },
        ],
    )


def _run_targeted(repo: Path, patched: str):
    """One real OPS.VALIDATE.3 run: baseline and candidate sandboxes, real pytest."""

    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "core/calc.py",
            "target_snippet": "def calc(a, b):\n    return a - b\n",
            "patched_snippet": patched,
        }
    ]
    request = build_targeted_validation_request(
        repo_path=repo,
        candidate_plan=plan,
        graph=_tiny_graph(),
        changed_symbols=("core/calc.py::calc",),
    )
    result = validate_targeted_candidate(
        repo_path=repo,
        candidate_plan=plan,
        request=request,
        pre_patch_probe_result="reproduced",
    )
    return plan, result


def _closure_for(plan, telemetry: dict[str, Any]) -> dict[str, Any]:
    fingerprint = patch_plan_fingerprint(plan)
    probe = "b" * 64
    payload = {
        "defect_closure_status": "fixed",
        "paired_status": "fixed_and_preserved",
        "post_probe_result": "not_reproduced",
        "preservation_oracle_status": "available",
        "preservation_cases": [{"case_id": "calc.preserve", "status": "preserved"}],
        "candidate_fingerprint": fingerprint,
        "probe_fingerprint": probe,
        "sandbox_only": True,
        "candidate_probe_apply_status": "applied",
        "candidate_probe_sandbox_cleanup_ok": True,
        "check_oracle_assessment_status": "current",
        "check_oracle_candidate_fingerprint": fingerprint,
        "check_oracle_role_counts": {},
    }
    payload.update(telemetry)
    return {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_fingerprint": fingerprint,
        "candidate_target_paths": ["core/calc.py"],
        "patch_safety": {"ok": True, "candidate_fingerprint": fingerprint},
        "pre_probe": {"probe_fingerprint": probe},
        "full_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "candidate_defect_closure": payload,
        "targeted_validation": payload,
        "oracle_assessment": payload,
        "candidate_sandbox_validation": payload,
    }


def test_a_passing_targeted_validation_supports_the_candidate(tmp_path):
    """The selector and its commands are used exactly as OPS.VALIDATE.3 has them."""

    # An existing check both the baseline and the candidate satisfy: OPS.VALIDATE.3
    # only compares against a baseline that was green, so this is the shape in
    # which a targeted pass actually means something.
    repo = _tiny_repo(tmp_path, "assert calc(0, 0) == 0")
    before = (repo / "core" / "calc.py").read_bytes()
    plan, result = _run_targeted(repo, "def calc(a, b):\n    return a + b\n")

    assert result.status == "passed"
    assert result.request.selection_complete is True
    assert [check.identifier for check in result.request.selected_checks]
    # §2 — both sandboxes were disposable; the source repository never moved.
    assert (repo / "core" / "calc.py").read_bytes() == before

    receipt = evaluate_candidate_verification(
        _closure_for(plan, result.as_telemetry())
    )
    assert receipt.component_verdict(COMPONENT_TARGETED_VALIDATION) == SUPPORTING
    assert receipt.status == VERIFIED
    assert LIMITATION_NO_RELEVANT_EXISTING_CHECKS not in receipt.accepted_limitations


def test_a_failing_targeted_check_is_a_genuine_regression(tmp_path):
    """§7 — a real existing check that breaks on the candidate rejects it."""

    repo = _tiny_repo(tmp_path, "assert calc(3, 1) == 2")
    plan, result = _run_targeted(repo, "def calc(a, b):\n    return a + b\n")

    assert result.status == "failed"

    receipt = evaluate_candidate_verification(
        _closure_for(plan, result.as_telemetry())
    )
    assert receipt.component_verdict(COMPONENT_TARGETED_VALIDATION) == CONTRADICTING
    assert receipt.status == REJECTED
    assert REASON_TARGETED_GENUINE_REGRESSION in receipt.rejection_reasons


def test_explicit_change_profile_requires_only_its_own_two_components():
    evidence = {
        "patch_basis": PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
        "candidate_fingerprint": "a" * 64,
        "patch_safety": {"ok": True, "candidate_fingerprint": "a" * 64},
        "candidate_sandbox_validation": {"sandbox_apply_status": "applied"},
    }
    receipt = evaluate_candidate_verification(evidence)
    assert receipt.policy_profile == PROFILE_EXPLICIT_CHANGE_SANDBOX_COHERENCE
    assert receipt.status == VERIFIED
    assert receipt.component_verdict(COMPONENT_PAIRED_PROBE) == COMPONENT_NOT_APPLICABLE
    assert receipt.component_verdict(COMPONENT_ORACLE_ASSESSMENT) == (
        COMPONENT_NOT_APPLICABLE
    )
    evidence["candidate_sandbox_validation"] = {"sandbox_apply_status": "failed"}
    assert evaluate_candidate_verification(evidence).status == REJECTED


# ---------------------------------------------------------------------------
# §14 — freshness, all failing closed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mutate, expected_reason",
    [
        pytest.param(
            lambda e: e.__setitem__("candidate_fingerprint", "d" * 64),
            REASON_CANDIDATE_FINGERPRINT_STALE,
            id="candidate-bytes-changed",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "probe_fingerprint", "e" * 64
            ),
            REASON_PROBE_FINGERPRINT_STALE,
            id="probe-changed",
        ),
        pytest.param(
            lambda e: e["pre_probe"].__setitem__("executed_source_sha256", "f" * 64),
            REASON_SOURCE_STATE_STALE,
            id="relevant-source-changed",
        ),
        pytest.param(
            lambda e: e.__setitem__("candidate_target_paths", ["core/somewhere_else.py"]),
            REASON_TARGET_BINDING_STALE,
            id="target-binding-changed",
        ),
        pytest.param(
            lambda e: e["candidate_defect_closure"].__setitem__(
                "check_oracle_candidate_fingerprint", "d" * 64
            ),
            REASON_CANDIDATE_FINGERPRINT_STALE,
            id="oracle-bound-elsewhere",
        ),
    ],
)
def test_stale_evidence_fails_closed_as_stale_not_as_a_finding(mutate, expected_reason):
    evidence = _verified_evidence()
    mutate(evidence)
    receipt = evaluate_candidate_verification(evidence)
    assert receipt.status == STALE
    assert expected_reason in receipt.rejection_reasons
    assert receipt.review_ready is False
    assert receipt.needs_escalation is True


def test_a_stored_receipt_stops_being_current_when_the_candidate_changes():
    receipt = evaluate_candidate_verification(_verified_evidence())
    payload = receipt.as_telemetry()
    assert candidate_verification_status_of_payload(payload) == VERIFIED
    assert candidate_verification_is_current(payload, "a" * 64) is True
    assert candidate_verification_is_current(payload, "d" * 64) is False
    # A payload from before this phase reads back as its own value, not as a pass.
    assert candidate_verification_status_of_payload({}) == "legacy_unverified"
    assert candidate_verification_is_current({}, "a" * 64) is False


def test_integrity_and_freshness_outrank_a_substantive_verdict():
    """Evidence we cannot trust may not be reported as a finding either way."""

    evidence = _verified_evidence()
    evidence["candidate_defect_closure"].update(
        {
            "paired_status": "fixed_but_regressive",
            "defect_closure_status": "fixed_but_regressive",
        }
    )
    assert evaluate_candidate_verification(evidence).status == REJECTED
    evidence["candidate_fingerprint"] = "d" * 64
    assert evaluate_candidate_verification(evidence).status == STALE
    evidence["candidate_defect_closure"]["sandbox_only"] = False
    assert evaluate_candidate_verification(evidence).status == INVALID


# ---------------------------------------------------------------------------
# §1–§3 — the lifecycle boundary in the live pipeline
# ---------------------------------------------------------------------------


def _state(user_input: str) -> AgentState:
    """An AgentState with only the fields the lifecycle boundary reads."""

    return AgentState(
        interface="agent",
        mode="planner",
        user_input=user_input,
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )


def _t6_state(candidate: dict[str, Any], pre_probe) -> AgentState:
    """A live-shaped state for the exact T6 run, minus the model calls."""

    _contract, receipt = pre_probe
    state = _state(T6_QUERY)
    state.repo_path = str(ROOT)
    state.language = "python"
    state.is_project_input = True
    state.patch_style = "safe_minimal"
    state.task_info = {"intent": "bug_fix", "patch_style": "safe_minimal"}
    state.live_route = {
        "selected_workflow": "defect_repair_patch",
        "preservation_passed": True,
        "behavioral_expectations": [_t6_behavior_fact().as_dict()],
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
            "source_snippet": _t6_source_snippet(),
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
        "patch_candidate": dict(candidate),
        "issues": [],
    }
    state.repository_graph = _t6_graph()
    return state


def _t6_graph():
    """A real ProgramGraph in which nothing existing calls the target.

    OPS.VALIDATE.3's selector is used unchanged; supplying a loaded graph is
    what lets it *complete* rather than report its metadata as unavailable.
    The finding it then reaches — that no existing check is structurally
    related to ``_classify_indent`` — is the honest one for this graph, and it
    is recorded as an accepted limitation rather than as support.
    """

    return build_graph(
        [
            {"id": T6_TARGET_FILE, "type": "file"},
            {
                "id": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "function",
                "file": T6_TARGET_FILE,
            },
            {"id": "core/unrelated.py", "type": "file"},
            {"id": "tests/test_unrelated.py", "type": "file"},
            {
                "id": "tests/test_unrelated.py::test_unrelated",
                "type": "function",
                "file": "tests/test_unrelated.py",
            },
        ],
        [
            {
                "source": T6_TARGET_FILE,
                "target": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
                "type": "contains",
            },
            {
                "source": "tests/test_unrelated.py",
                "target": "core/unrelated.py",
                "type": "imports",
            },
        ],
    )


@pytest.fixture
def t6_pipeline_run(request, monkeypatch, t6_pre_probe):
    """Drive the real ``maybe_run_auto_patch`` with mutation disabled."""

    target, patched = request.param
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(_t6_candidate(target, patched), t6_pre_probe)
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    pipeline.maybe_run_auto_patch(state, interactive=False)
    after = (ROOT / T6_TARGET_FILE).read_bytes()
    return state, before, after


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)],
    indirect=True,
)
def test_mutation_disabled_no_longer_skips_candidate_verification(t6_pipeline_run):
    """§3/§31 — every component the old early return skipped now runs."""

    state, before, after = t6_pipeline_run
    block = state.json_block

    # §20 — the exact candidate fingerprint exists, because the branch ran.
    assert block["candidate_verification_candidate_fingerprint"] == (
        candidate_fingerprint_from_payload(block)
    )
    # §5 — the exact candidate was materialized in a disposable sandbox.
    assert block["candidate_probe_apply_status"] == "applied"
    assert block["sandbox_only"] is True
    assert block["candidate_probe_sandbox_cleanup_ok"] is True
    # §6 — paired post-probe, targeted validation and oracle assessment all ran.
    assert block["post_probe_result"]
    assert block["paired_status"]
    assert block["targeted_validation_status"]
    assert "check_oracle_assessment_status" in block
    # §2 — read-only: the real repository is byte-identical.
    assert before == after
    assert _classify_indent("root\n  a\n    b\n      c\n    d\n  e\n") == "4space"


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)],
    indirect=True,
)
def test_known_wrong_t6_candidate_through_the_live_no_mutation_branch(t6_pipeline_run):
    """§8/§32 — the product smoke, replayed deterministically."""

    state, before, after = t6_pipeline_run
    block = state.json_block

    assert block["patch_safety_passed"] is True          # safe_minimal/safety accepted
    assert block.get("sandbox_apply_status", "applied") != "failed"
    assert block["primary_case"]["status"] == "fixed"     # primary defect probe fixed
    assert block["preservation_cases"][0]["status"] == PRESERVATION_REGRESSED

    assert block["candidate_verification_status"] == REJECTED
    assert REASON_PRESERVATION_REGRESSED in (
        block["candidate_verification_rejection_reasons"]
    )
    assert block["human_review_eligible"] is False
    assert block["needs_escalation"] is True
    assert block["candidate_review_ready"] is False
    assert block["candidate_visible_for_debugging"] is True
    # §8 — no approval-ready receipt is frozen for a rejected candidate.
    assert "human_apply_review" not in block
    assert block.get("approval_ready") is not True
    # §2/§15 — mutation stayed off.
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["execution_authorization_denied_reason"] == "auto_patch_disabled"
    assert block["patch_application_authority"] is False
    assert before == after

    # §10 — the user-facing wording cannot be read as "ready to apply".
    assert "not verified" in state.auto_patch_result
    assert "not ready to approve or apply" in state.auto_patch_result
    # §23 — the rejection is carried in the canonical structured issue shape.
    (issue,) = [
        item for item in block["issues"] if item.get("type") == "candidate_verification"
    ]
    assert issue["severity"] == "high"
    assert issue["code"] == REASON_PRESERVATION_REGRESSED


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_DISTINGUISHING_TARGET, T6_STRUCTURAL_CONTROL_PATCHED)],
    indirect=True,
)
def test_correct_candidate_can_be_verified_without_gaining_execution_authority(
    t6_pipeline_run,
):
    """§9/§15 — verification opens, and mutation stays off.

    INDENT.SEMANTICS.1: the candidate is the structural control, the one
    known body that closes every bounded case of the eight-case matrix.
    """

    state, before, after = t6_pipeline_run
    block = state.json_block

    assert block["paired_status"] == PAIRED_FIXED_AND_PRESERVED
    assert block["candidate_verification_status"] == VERIFIED
    assert block["candidate_review_ready"] is True
    assert block["candidate_verification_rejection_reasons"] == []

    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["execution_authorization_denied_reason"] == "auto_patch_disabled"
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False
    assert block["patch_application_authority"] is False
    assert before == after
    assert "no write was authorized" in state.auto_patch_result

    # §13/§15 — verification opened, and still no approval-ready receipt was
    # frozen: that artifact exists to let a later Apply authorize a mutation,
    # and this is the branch where mutation is switched off.
    assert "human_apply_review" not in block


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_DISTINGUISHING_TARGET, T6_DISTINGUISHING_PATCHED)],
    indirect=True,
)
def test_the_raw_width_candidate_is_rejected_for_python_block_structure(
    t6_pipeline_run,
):
    """INDENT.SEMANTICS.1 — what became of this phase's second control.

    The greatest-common-divisor candidate answers all five historical cases.
    On the continuation sample it reads the 6-wide alignment row as
    indentation, on the docstring sample the 6-wide interior row, and both
    times it reports 2space for code whose only block step is 4.
    """

    state, before, after = t6_pipeline_run
    block = state.json_block

    assert block["behavioral_matrix_status"] == "fixed_but_regressive"
    assert [
        case["case_id"]
        for case in block["behavioral_matrix_cases"]
        if case["candidate_status"] == "regressed"
    ] == [
        "indentation_style.preserve.4space.continuation",
        "indentation_style.preserve.4space.multiline_string",
    ]
    assert block["candidate_verification_status"] == REJECTED
    assert REASON_PRESERVATION_REGRESSED in (
        block["candidate_verification_rejection_reasons"]
    )
    assert block["candidate_review_ready"] is False
    assert block["human_review_eligible"] is False
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert before == after


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_DISTINGUISHING_TARGET, T6_SUBJECT_INVARIANT_OPEN_PATCHED)],
    indirect=True,
)
def test_a_candidate_whose_subject_invariant_is_open_is_rejected_not_verified(
    t6_pipeline_run,
):
    """DEFECT.PROBE.LIVE.4 — what became of this phase's original control.

    Until the behavioral matrix existed, the smallest-observed-width
    candidate was the candidate that proved verification *opens*.  It is
    correct for both ordinary widths and for the deep 4-space sample, and it
    still cannot classify a 2-space sample whose indentation begins at depth
    three.  The invariant it carried has moved to a candidate that answers
    every bounded case; the invariant it carries now is the measured one.
    """

    state, before, after = t6_pipeline_run
    block = state.json_block

    assert block["behavioral_matrix_status"] == "partially_fixed"
    assert block["candidate_verification_status"] == REJECTED
    assert block["candidate_review_ready"] is False
    assert block["human_review_eligible"] is False
    assert (
        REASON_SUBJECT_INVARIANT_NOT_CLOSED
        in block["candidate_verification_rejection_reasons"]
    )
    # §15 — and rejection still grants and revokes no authority of its own.
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert before == after


@pytest.mark.parametrize(
    "t6_pipeline_run",
    [(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)],
    indirect=True,
)
def test_a_human_apply_cannot_authorize_a_rejected_candidate(t6_pipeline_run):
    """§13 — the frozen approval path is bound, not duplicated."""

    state, _before, _after = t6_pipeline_run
    block = state.json_block
    authorization = authorize_human_apply(
        payload=block,
        repo_path=ROOT,
        patch_safety_verdict=evaluate_patch_safety(
            [T6_TARGET_FILE], project_root=ROOT
        ),
        human_action_kind=HUMAN_ACTION_APPLY,
        approved_candidate_fingerprint=candidate_fingerprint_from_payload(block),
        approved_eligibility_receipt_fingerprint="",
        allow_legacy_explicit_change=True,
    )
    assert authorization.authorized is False
    assert authorization.denial_reason == DENIAL_NOT_HUMAN_REVIEW_ELIGIBLE
    assert block["execution_eligibility_status"] == INELIGIBLE


def test_a_run_with_no_authored_candidate_records_nothing_new(monkeypatch, t6_pre_probe):
    """The receipt describes a candidate; with none, nothing is claimed."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(_t6_candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES), t6_pre_probe)
    state.json_block["patch_candidate"] = None
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert "candidate_verification_status" not in state.json_block
    assert state.json_block["execution_authorized"] is False
    assert state.json_block["execution_authorization_denied_reason"] == (
        "auto_patch_disabled"
    )


def test_read_only_verification_refuses_to_run_when_mutation_is_enabled():
    """The function is the mutation-disabled branch; it says so structurally."""

    state = _state("x")
    with pytest.raises(RuntimeError):
        pipeline._verify_authored_candidate_without_mutation(state)


def test_stale_verification_is_dropped_when_the_candidate_is_rewritten(
    monkeypatch, t6_pre_probe
):
    """§14 — a receipt never survives next to a candidate it did not measure."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _t6_candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES), t6_pre_probe
    )
    pipeline.maybe_run_auto_patch(state, interactive=False)
    first = state.json_block["candidate_verification_candidate_fingerprint"]
    assert first

    # A refinement replaces the candidate; the old receipt must not travel with it.
    state.json_block["patch_candidate"]["patched_snippet"] = (
        T6_REORDERED_BRANCHES + '        # refined\n'
    )
    assert candidate_verification_is_current(
        state.json_block, candidate_fingerprint_from_payload(state.json_block)
    ) is False
    pipeline._drop_stale_candidate_validation(state)
    assert "candidate_verification_status" not in state.json_block
    assert "candidate_verification_candidate_fingerprint" not in state.json_block


# ---------------------------------------------------------------------------
# §24–§27, §30 — what this phase did not touch
# ---------------------------------------------------------------------------


def test_read_only_route_still_returns_before_any_verification(monkeypatch):
    """§26 — T5 (analysis_only) is unaffected; it never reaches the branch."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    calls: list[str] = []
    monkeypatch.setattr(
        pipeline,
        "_verify_authored_candidate_without_mutation",
        lambda state: calls.append("verified"),
    )
    state = _state("compare two repos")
    state.live_route = {
        "phase_id": WAITER_PHASE_ID,
        "selected_workflow": "analysis_answer",
        "change_requested": False,
    }
    state.json_block = {}
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert calls == []
    assert state.json_block["execution_authorization_denied_reason"] == (
        "no_change_requested"
    )


def test_mutation_enabled_runs_do_not_enter_the_read_only_branch(monkeypatch):
    """§24/§25 — T1/T2/T3 and T4 keep their existing control flow exactly."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", True)
    calls: list[str] = []
    monkeypatch.setattr(
        pipeline,
        "_verify_authored_candidate_without_mutation",
        lambda state: calls.append("verified"),
    )
    state = _state("fix the bug")
    state.live_route = {"selected_workflow": "defect_repair_patch"}
    state.json_block = {"needs_escalation": True, "confidence": 0.9}
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert calls == []


def test_the_module_makes_no_model_network_or_subprocess_call():
    """§27/§30 — the reducer is pure and its source proves it."""

    source = (ROOT / "core" / "candidate_verification.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "dataclasses", "hashlib", "json", "re", "typing"}

    # Identifiers actually referenced by the code, not words in its prose: the
    # module docstring says out loud that it performs no subprocess or network
    # work, so a substring scan would flag its own promise.
    used: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            used.add(node.id)
        elif isinstance(node, ast.Attribute):
            used.add(node.attr)
    for forbidden in (
        "subprocess",
        "Popen",
        "check_output",
        "system",
        "open",
        "urlopen",
        "requests",
        "httpx",
        "socket",
        "Path",
        "environ",
        "getenv",
        "read_text",
        "write_text",
        "run_gemini_request",
        "run_deepseek_review",
        "evaluate_paired_defect_closure",
        "validate_targeted_candidate",
        "validate_candidate_in_sandbox",
    ):
        assert forbidden not in used, forbidden


def test_guardrails_state_every_boundary_this_phase_holds():
    guardrails = candidate_verification_guardrails()
    assert guardrails["verification_runs_when_mutation_is_disabled"] is True
    assert guardrails["verification_is_read_only"] is True
    for boundary in (
        "verification_grants_execution_authority",
        "verification_enables_auto_apply",
        "verification_changes_approval_semantics",
        "verification_changes_safe_minimal",
        "verification_changes_candidate_generation",
        "verification_changes_validation_commands",
        "verification_changes_validate_selector",
        "verification_edits_control_or_retrieval",
        "verification_changes_behavioral_expectation",
        "verification_fixes_classify_indent",
        "verification_calls_a_model",
        "verification_calls_the_network",
        "verification_traverses_the_repository",
        "verification_mutates_the_real_repository",
        "confidence_can_override_verification",
        "missing_evidence_can_become_a_pass",
        "primary_fixed_alone_can_verify",
    ):
        assert guardrails[boundary] is False, boundary


def test_classify_indent_is_still_deliberately_broken():
    """§30 — the production defect this phase measures is not repaired here."""

    assert _classify_indent("root\n  a\n    b\n      c\n    d\n  e\n") == "4space"


def test_frozen_prerequisite_files_are_untouched():
    """Historical §30 bytes reconstruct after the explicit harness remediation."""

    pinned = json.loads(
        (ROOT / "tests" / "fixtures" / "candidate_verify_live1_frozen_boundaries.json")
        .read_text(encoding="utf-8")
    )
    import hashlib

    for relative, digest in sorted(pinned["files"].items()):
        actual = hashlib.sha256(before_harness_remediation(relative)).hexdigest()
        assert actual == digest, relative


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


def test_candidate_verification_is_registered_as_a_live_lifecycle_fix():
    data = load_phase_registry(str(REGISTRY))
    phase = {item["phase_id"]: item for item in data["phases"]}[
        "CANDIDATE.VERIFY.LIVE.1"
    ]

    assert "CANDIDATE" in PHASE_ID_PREFIXES
    assert phase["title"] == "Read-Only Candidate Verification Before Human Review"
    # CANDIDATE.* is an ID namespace inside OPS, not a new track.
    assert phase["track"] == "OPS"
    assert phase["status"] == "complete"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["model_calls_allowed"] is False
    assert phase["requires_sandbox"] is True
    assert phase["budget_tier"] == "local_only"

    for live_file in (
        "core/candidate_verification.py",
        "core/pipeline.py",
        "tests/test_candidate_verification.py",
    ):
        assert live_file in phase["allowed_files"]

    for frozen in (
        "core/code_dna.py",
        "core/patch_safety.py",
        "core/defect_probe.py",
        "core/paired_defect_probe.py",
        "core/targeted_repository_validation.py",
        "core/check_oracle_assessment.py",
        "core/execution_eligibility_policy.py",
        "core/human_apply_authorization.py",
        "patching/",
        "policy/",
    ):
        assert frozen in phase["forbidden_files"]
        assert frozen not in phase["allowed_files"]

    text = phase["summary"] + " " + " ".join(phase["notes"])
    for term in (
        "AUTO_PATCH_ENABLED controls mutation",
        "read-only",
        "exact candidate",
        "paired",
        "preservation",
        "no execution authority",
        "no model call",
        "no network call",
        "_classify_indent",
        "not report-only",
    ):
        assert term.lower() in text.lower(), term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        "CANDIDATE.VERIFY.LIVE.1.PLAN",
        "CANDIDATE.VERIFY.LIVE.1.READINESS",
        "CANDIDATE.VERIFY.LIVE.1.CLOSE",
        "CANDIDATE.VERIFY.LIVE.2",
    ):
        assert forbidden_phase not in ids
