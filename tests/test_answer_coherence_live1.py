"""ANSWER.COHERENCE.LIVE.1 — candidate-bound final response provenance.

Round 10 produced two candidates for one defect.  Candidate0, an inert guard,
was rejected ``still_reproduced``.  Candidate1, a branch reorder, came out of the
single verification-guided revision, parsed, earned its own fingerprint, passed
the candidate gates and was rejected ``behavior_preservation_regressed``.
Containment held.  The final answer did not:

    summary         <- Candidate0
    issues (model)  <- Candidate0
    patch_candidate <- Candidate1
    confidence      <- Candidate1
    verification    <- Candidate1

A reader was shown one patch explained by the author of another.  This suite
replays that exact pair through the production lifecycle — the replay rebuilds
Round 10's revision request byte for byte — and pins that every
candidate-authored field of the final answer now comes from one candidate,
while verification, escalation and authority stay the harness's.

No test here reaches a provider.  The single revision call is answered by a
deterministic adapter, and every real provider entry point is replaced by a
recorder that fails the test if touched.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import inspect
import json
import re
import time
from pathlib import Path
from typing import Any

import pytest

from _harness_maintenance import LATER_RECEIPTS, before_later_receipts

from core import candidate_presentation as presentation_module
from core import pipeline
from core.agent_state import AgentState
from core.answer_entity_grounding import _ANSWER_SURFACE_KEYS, ground_answer_for_display
from core.behavioral_expectation import extract_behavioral_expectations
from core.candidate_presentation import (
    AUTHORED_PRESENTATION_FIELDS,
    AUTHORING_ENVELOPE_OWNERSHIP,
    CANDIDATE_GENERATIONS,
    GENERATION_INITIAL,
    GENERATION_REVISION,
    INCOHERENCE_REASONS,
    INCOHERENT_AUTHOR_GENERATION,
    INCOHERENT_NO_AUTHOR_RECORD,
    INCOHERENT_NO_CANDIDATE_IDENTITY,
    INCOHERENT_PAYLOAD_CANDIDATE,
    INCOHERENT_RECEIPT_CANDIDATE,
    INCOHERENT_SUMMARY,
    INCOHERENT_SUPERSEDED_ISSUES,
    OWNER_CANDIDATE_BYTES,
    PRIMARY_PRESENTATION_FIELDS,
    CandidateAuthoredFields,
    CandidatePresentation,
    CandidatePresentationError,
    bind_final_candidate_presentation,
    candidate_presentation_guardrails,
    capture_candidate_authored_fields,
    install_candidate_presentation,
    superseded_candidate_history,
)
from core.candidate_revision import (
    OUTCOME_REVISED_CANDIDATE_REJECTED,
    OUTCOME_REVISED_CANDIDATE_VERIFIED,
    OUTCOME_REVISION_OUTPUT_INVALID,
    OUTPUT_NO_JSON_PAYLOAD,
    SCHEMA_VERSION as REVISION_SCHEMA_VERSION,
)
from core.candidate_sandbox_validation import candidate_fingerprint_from_payload
from core.code_dna import _classify_indent
from core.defect_probe import maybe_execute_control_defect_probe
from core.json_utils import extract_json_block
from core.localization_handoff import ground_state_answer
from core.patch_authoring_contract import PATCH_RESPONSE_SCHEMA
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from patching.patch_gates import get_confidence_and_escalation
from graph.schema import build_graph


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures"
ROUND10 = json.loads(
    (FIXTURES / "answer_coherence_live1_round10.json").read_text(encoding="utf-8")
)
REVERSAL_FIXTURE = FIXTURES / "answer_coherence_live1_reversal.json"
TARGET_FILE = ROUND10["target_file"]
TARGET_SYMBOL = ROUND10["target_symbol"]
SOURCE = ROUND10["control_source_snippet"]

CANDIDATE0 = extract_json_block(ROUND10["candidate0_response"])
CANDIDATE1 = extract_json_block(ROUND10["candidate1_response"])
SUMMARY0 = CANDIDATE0["summary"]
SUMMARY1 = CANDIDATE1["summary"]
(ISSUE0,) = CANDIDATE0["issues"]
(ISSUE1,) = CANDIDATE1["issues"]
FP0 = ROUND10["candidate0_fingerprint"]
FP1 = ROUND10["candidate1_fingerprint"]

#: The shipped ``_classify_indent`` body, as CONTROL quoted it (no final newline).
SHIPPED_BODY = (
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
    "    return counts.most_common(1)[0][0] if counts else None"
)
assert SHIPPED_BODY in SOURCE

#: The established local-only positive control: correct under every
#: DEFECT.PROBE.LIVE.5 case and admitted by PATCH.MINIMAL.LIVE.2.  Test-only.
#: INDENT.SEMANTICS.1's eight-case matrix rejects it — it reads continuation
#: alignment and docstring interiors as indentation — so the runs that need it
#: verified declare the five-case oracle (``_scenario(historical_oracle=True)``).
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
    '    return "tab" if counts["tab"] else None'
)

#: The Round-9 substance: a novel ``lstrip`` member PATCH.MINIMAL.LIVE.2 blocks.
LSTRIP_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    "        stripped = line.lstrip('\\n\\r')\n"
    '        if not stripped or stripped[0] not in " \\t":\n'
    "            continue\n"
    '        indent = len(stripped) - len(stripped.lstrip(" \\t"))\n'
    '        if "\\t" in stripped[:indent]:\n'
    '            counts["tab"] += 1\n'
    "        elif indent % 4 == 0:\n"
    '            counts["4space"] += 1\n'
    "        elif indent % 2 == 0:\n"
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None"
)


def _with_body(body: str) -> str:
    return SOURCE.replace(SHIPPED_BODY, body)


def _response(
    body: str | None,
    *,
    summary: Any = None,
    issues: Any = None,
    confidence: Any = None,
    needs_escalation: Any = False,
) -> str:
    """One authoring response in the contract's envelope order; ``None`` omits."""

    payload: dict[str, Any] = {}
    if summary is not None:
        payload["summary"] = summary
    if issues is not None:
        payload["issues"] = issues
    if body is not None:
        payload["patch_candidate"] = {
            "file": TARGET_FILE,
            "relative_path": TARGET_FILE,
            "target_node_name": TARGET_SYMBOL,
            "target_node_kind": "function",
            "target_snippet": SOURCE,
            "patched_snippet": _with_body(body),
        }
    if confidence is not None:
        payload["confidence"] = confidence
    if needs_escalation is not None:
        payload["needs_escalation"] = needs_escalation
    return json.dumps(payload, indent=2)


# ═══════════════════════════════════════════════════════════════════════════
# The deterministic Round-10 replay
# ═══════════════════════════════════════════════════════════════════════════


class _ProviderCalls:
    """Every real provider entry point, recorded and refused."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def refuse(self, name: str):
        def _refused(*_args: Any, **_kwargs: Any) -> str:
            self.calls.append(name)
            raise AssertionError(f"a deterministic test reached the provider: {name}")

        return _refused


def _no_provider(monkeypatch) -> _ProviderCalls:
    recorder = _ProviderCalls()
    monkeypatch.setattr(pipeline, "run_gemini_request", recorder.refuse("gemini"))
    monkeypatch.setattr(pipeline, "run_deepseek_review", recorder.refuse("deepseek"))
    return recorder


def _route() -> dict[str, Any]:
    return {
        "selected_workflow": "defect_repair_patch",
        "preservation_passed": True,
        "behavioral_expectations": [ROUND10["behavioral_expectation"]],
    }


def _control(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "repo_path": str(ROOT),
        "patch_style": "safe_minimal",
        "live_route": dict(route),
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "patch_intent": {
            "target_file": TARGET_FILE,
            "relative_path": TARGET_FILE,
            "target_symbol": TARGET_SYMBOL,
            "target_symbol_full": f"{TARGET_FILE}::{TARGET_SYMBOL}",
            "source_snippet": SOURCE,
        },
        "entry_resolution": {
            "resolved_entry_nodes": [f"{TARGET_FILE}::{TARGET_SYMBOL}"]
        },
        "scout": {"request_type": "bug_fix"},
    }


@pytest.fixture(scope="module")
def round10_pre_probe():
    """The bounded reproduction, derived by the production CONTROL adapter.

    Deriving it from the recorded CONTROL facts, rather than building a probe
    by hand, is what makes the fingerprint below Round 10's own.
    """

    (extracted,), truncated = extract_behavioral_expectations(ROUND10["task"])
    assert truncated is False
    # ``obligation_ordinal`` is route bookkeeping the WAITER assigns when it
    # numbers the preserved obligations; bare extraction leaves it unset.
    fact = ROUND10["behavioral_expectation"]
    assert {
        k: v for k, v in extracted.as_dict().items() if k != "obligation_ordinal"
    } == {k: v for k, v in fact.items() if k != "obligation_ordinal"}

    receipt = maybe_execute_control_defect_probe(_control(_route()))
    assert receipt is not None
    if receipt.probe_result != "reproduced":
        pytest.skip(f"baseline probe was {receipt.probe_result}, not reproduced")
    assert receipt.as_dict()["probe_fingerprint"] == ROUND10["probe_fingerprint"]
    return receipt


def _graph():
    return build_graph(
        [
            {"id": TARGET_FILE, "type": "file"},
            {
                "id": f"{TARGET_FILE}::{TARGET_SYMBOL}",
                "type": "function",
                "file": TARGET_FILE,
            },
        ],
        [
            {
                "source": TARGET_FILE,
                "target": f"{TARGET_FILE}::{TARGET_SYMBOL}",
                "type": "contains",
            }
        ],
    )


def _state(pre_probe, draft_response: str = ROUND10["candidate0_response"]):
    """Round 10's run up to the writer boundary, then the real writer boundary.

    ``finalize_answer`` receives the verbatim draft response, exactly as the CLI
    and web runners hand it over.  The two CONTROL facts the postprocess battery
    attaches to a grounded payload are supplied the way the existing product
    smokes supply them; neither is candidate-authored.
    """

    state = AgentState(
        interface="agent",
        mode="planner",
        user_input=ROUND10["task"],
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
    state.live_route = _route()
    state.control_result = _control(state.live_route)
    state.control_result["defect_probe"] = pre_probe.as_dict()
    state.repository_graph = _graph()
    pipeline.finalize_answer(state, draft_response)
    if isinstance(state.json_block, dict):
        state.json_block["patch_basis"] = PATCH_BASIS_GROUNDED_DEFECT
        state.json_block["target_source_grounded"] = True
    return state


def _run(state: AgentState, monkeypatch, revision_response: str | None):
    """The read-only lifecycle, with the revision answered deterministically."""

    requests: list[str] = []

    def adapter(_state: AgentState, prompt: str) -> str:
        requests.append(prompt)
        assert revision_response is not None, "no revision request was expected"
        return revision_response

    monkeypatch.setattr(pipeline, "_call_revision_provider", adapter)
    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    before = (ROOT / TARGET_FILE).read_bytes()
    pipeline.maybe_run_auto_patch(state, interactive=False)
    assert (ROOT / TARGET_FILE).read_bytes() == before, "the repository moved"
    return state.json_block, requests


def _scenario(
    pre_probe, draft: str, revision: str | None, *, historical_oracle: bool = False
):
    """One whole deterministic run.  Returns (state, payload, requests, calls).

    ``historical_oracle`` runs the five-case LIVE.5 matrix Round 10 ran under,
    through the one shared test helper.  INDENT.SEMANTICS.1 appended three
    cases since; a run that must reproduce Round 10's bytes, or that needs a
    candidate the matrix *closes* (none that safe_minimal admits is known to
    close all eight), declares so here.  Every other run is the product's own.
    """

    monkeypatch = pytest.MonkeyPatch()
    try:
        if historical_oracle:
            from _matrix_history import pin_live5_indentation_matrix

            pin_live5_indentation_matrix(monkeypatch)
        recorder = _no_provider(monkeypatch)
        state = _state(pre_probe, draft)
        block, requests = _run(state, monkeypatch, revision)
    finally:
        monkeypatch.undo()
    return state, copy.deepcopy(block), requests, recorder


@pytest.fixture(scope="module")
def round10(round10_pre_probe):
    """§24 — the exact Round-10 pair, driven once and read by many tests."""

    return _scenario(
        round10_pre_probe,
        ROUND10["candidate0_response"],
        ROUND10["candidate1_response"],
    )


@pytest.fixture(scope="module")
def round10_as_recorded(round10_pre_probe):
    """The same pair under the five-case oracle Round 10 itself ran.

    Candidate0's revision request lists every case it preserved, so under
    INDENT.SEMANTICS.1's eight cases the request gains three preserved-case
    lines and stops being Round 10's bytes.  tests/test_indent_semantics1.py
    proves that those three lines are the whole difference.
    """

    return _scenario(
        round10_pre_probe,
        ROUND10["candidate0_response"],
        ROUND10["candidate1_response"],
        historical_oracle=True,
    )


# ═══════════════════════════════════════════════════════════════════════════
# §24/§39 — the exact Round-10 regression
# ═══════════════════════════════════════════════════════════════════════════


def test_round10_replays_the_measured_candidate_pair(round10_as_recorded):
    """The replay is Round 10, not an approximation of it."""

    _state_, block, requests, recorder = round10_as_recorded

    assert len(requests) == 1, "exactly one revision request"
    assert recorder.calls == [], "no provider was reached"
    (request,) = requests
    # LIVE.3 adds authoritative scope and exact inputs. Project only this
    # historical hash assertion back to the recorded authoring protocol.
    from _harness_maintenance import before_author_live3_prompt
    request = before_author_live3_prompt(request, SOURCE)
    # The historical revision request is rebuilt byte for byte.
    assert len(request) == ROUND10["candidate1_request_chars"]
    assert hashlib.sha256(request.encode("utf-8")).hexdigest() == (
        ROUND10["candidate1_request_sha256"]
    )
    assert block["candidate_revision_previous_candidate_fingerprint"] == FP0
    assert block["candidate_revision_revised_candidate_fingerprint"] == FP1
    assert candidate_fingerprint_from_payload(block) == FP1
    assert block["candidate_verification_status"] == "rejected"
    assert block["candidate_verification_rejection_reasons"] == (
        ROUND10["candidate1_verification"]["rejection_reasons"]
    )
    assert block["candidate_revision_previous_candidate"]["candidate_fingerprint"] == FP0


def test_round10_recorded_the_defect_this_phase_fixes():
    """§39 red — what production displayed and persisted, frozen verbatim."""

    observed = ROUND10["observed_final_payload"]

    # summary: Candidate0's words (with the localization display annotation).
    assert observed["summary"].startswith("The `_classify_indent` function checks")
    assert "Wait, the current order IS 4-space then 2-space" in observed["summary"]
    assert "By checking for 2-space indentation first" not in observed["summary"]
    # issues: Candidate0's own issue beside the harness finding about Candidate1.
    assert ISSUE0 in observed["issues"]
    assert ISSUE1 not in observed["issues"]
    # patch identity and confidence: Candidate1's.
    assert observed["candidate_verification_candidate_fingerprint"] == FP1
    assert observed["confidence"] == CANDIDATE1["confidence"] == 1.0
    assert CANDIDATE0["confidence"] == 0.9


def test_round10_summary_belongs_to_the_candidate_it_is_shown_with(round10):
    _state_, block, _requests, _recorder = round10

    assert block["summary"] == SUMMARY1
    assert block["summary"] != SUMMARY0


def test_round10_patch_confidence_and_summary_are_one_candidates(round10):
    """§39 green — summary, patch and confidence all bound to Candidate1."""

    _state_, block, _requests, _recorder = round10

    assert candidate_fingerprint_from_payload(block) == FP1
    assert block["confidence"] == CANDIDATE1["confidence"] == 1.0
    assert block["summary"] == SUMMARY1
    assert block["final_candidate_fingerprint"] == FP1
    assert block["final_candidate_generation"] == GENERATION_REVISION
    assert block["candidate_presentation_coherent"] is True
    assert block["candidate_presentation_incoherence_reasons"] == []
    assert block["candidate_presentation_authored_fields"] == [
        "summary",
        "issues",
        "confidence",
        "needs_escalation",
    ]


def test_round10_model_issues_follow_the_candidate_and_harness_findings_stay(round10):
    """§10/§15 — Candidate1's own issue, and the harness finding about Candidate1."""

    _state_, block, _requests, _recorder = round10
    issues = block["issues"]

    assert ISSUE0 not in issues
    assert ISSUE1 in issues
    (finding,) = [
        item
        for item in issues
        if isinstance(item, dict) and item.get("type") == "candidate_verification"
    ]
    assert finding["code"] == "behavior_preservation_regressed"
    # Harness findings first, the author's own entries after, as every gate
    # already orders them.
    assert issues == [finding, ISSUE1]


def test_round10_harness_truth_is_what_production_recorded(round10):
    """§7/§15/§34 — verification, escalation and authority are unchanged."""

    _state_, block, _requests, _recorder = round10
    observed = ROUND10["observed_final_payload"]

    for key in (
        "needs_escalation",
        "human_review_eligible",
        "approval_ready",
        "execution_authorized",
        "candidate_verification_status",
        "candidate_verification_rejection_reasons",
        "candidate_verification_candidate_fingerprint",
        "candidate_revision_outcome",
    ):
        assert block[key] == observed[key], key
    assert block["needs_escalation"] is True
    assert block["human_review_eligible"] is False
    assert block["approval_ready"] is False
    assert block["execution_authorized"] is False
    assert block["write_authority"] is False
    assert block["auto_apply_allowed"] is False
    assert block["final_repository_changed"] is False


def test_round10_model_claims_stay_separate_from_harness_truth(round10):
    """§7 — what the author claimed, beside what the harness established."""

    _state_, block, _requests, _recorder = round10

    assert block["candidate_presentation_model_confidence"] == 1.0
    assert block["candidate_presentation_model_needs_escalation"] is False
    assert block["needs_escalation"] is True
    assert block["candidate_verification_status"] == "rejected"
    # §8 — confidence is the author's own and was not clamped after rejection.
    assert block["confidence"] == 1.0


def test_round10_candidate0_survives_only_as_rejected_history(round10):
    """§3/§27 — kept, labelled, and never the primary explanation."""

    _state_, block, _requests, _recorder = round10
    history = block["candidate_revision_previous_candidate"]

    assert history["status"] == "rejected_evidence_only"
    assert history["generation"] == GENERATION_INITIAL
    assert history["candidate_fingerprint"] == FP0
    assert history["authored_fields"] == [
        "summary",
        "issues",
        "confidence",
        "needs_escalation",
    ]
    assert history["summary"] == SUMMARY0
    assert history["issues"] == [ISSUE0]
    assert history["model_confidence"] == CANDIDATE0["confidence"] == 0.9
    assert history["model_needs_escalation"] is False
    assert history["verification_status"] == "rejected"
    assert history["verification_rejection_reasons"] == (
        ROUND10["candidate0_verification"]["rejection_reasons"]
    )
    # PATCH.AUTHOR.LIVE.1's existing history fields are all still there.
    assert history["patched_snippet"] == CANDIDATE0["patch_candidate"]["patched_snippet"]
    assert history["relative_path"] == TARGET_FILE
    assert history["target_node_name"] == TARGET_SYMBOL


def test_round10_the_final_authors_account_leads_the_payload(round10):
    """A reader meets Candidate1's explanation before Candidate0's rejected one."""

    _state_, block, _requests, _recorder = round10
    keys = list(block)

    assert keys[:4] == ["summary", "issues", "patch_candidate", "confidence"]
    assert keys.index("summary") < keys.index("candidate_revision_previous_candidate")


def test_round10_candidate0_narrative_appears_nowhere_else(round10):
    """§2 — Candidate0's words exist in exactly one place: its history."""

    _state_, block, _requests, _recorder = round10
    outside_history = {
        key: value
        for key, value in block.items()
        if key != "candidate_revision_previous_candidate"
    }
    serialized = json.dumps(outside_history, ensure_ascii=False)

    assert SUMMARY0 not in serialized
    assert ISSUE0 not in serialized


# ═══════════════════════════════════════════════════════════════════════════
# §13/§14 — first-candidate paths
# ═══════════════════════════════════════════════════════════════════════════

FIRST_DRAFT_SUMMARY = (
    "Infer the indentation unit from the leading widths instead of testing the "
    "4-space prefix first."
)
FIRST_DRAFT_ISSUES = [
    {
        "severity": "high",
        "type": "bug",
        "file": TARGET_FILE,
        "symbol": TARGET_SYMBOL,
        "reason": "A 4-space-deep line in a 2-space file is counted as 4space.",
        "fix": "Derive the unit from the widths.",
    }
]


def test_first_draft_success_presents_candidate0_unchanged(round10_pre_probe):
    """§13 — no revision, and every user-visible field is the author's own."""

    draft = _response(
        CORRECT_LOCAL_ONLY_BODY,
        summary=FIRST_DRAFT_SUMMARY,
        issues=FIRST_DRAFT_ISSUES,
        confidence=0.8,
    )
    authored = extract_json_block(draft)
    _state_, block, requests, recorder = _scenario(
        round10_pre_probe, draft, None, historical_oracle=True
    )

    assert requests == [] and recorder.calls == []
    assert block["candidate_verification_status"] == "verified"
    assert block["candidate_revision_attempted"] is False
    assert "candidate_revision_previous_candidate" not in block
    # Semantically unchanged: the same summary, issues, confidence and patch.
    assert block["summary"] == authored["summary"]
    assert block["issues"] == authored["issues"]
    assert block["confidence"] == authored["confidence"]
    assert block["patch_candidate"] == authored["patch_candidate"]
    fingerprint = candidate_fingerprint_from_payload(block)
    assert block["final_candidate_fingerprint"] == fingerprint
    assert block["candidate_verification_candidate_fingerprint"] == fingerprint
    assert block["final_candidate_generation"] == GENERATION_INITIAL
    assert block["candidate_presentation_coherent"] is True
    # Verified is evidence, not authority (§16/§34).
    assert block["execution_authorized"] is False
    assert block["write_authority"] is False
    assert block["auto_apply_allowed"] is False


def test_first_draft_no_op_is_rejected_and_its_account_stays_bound(round10_pre_probe):
    """§14 — an exact no-op Candidate0 is the only candidate, and says so."""

    draft = _response(
        SHIPPED_BODY,
        summary="The classifier already handles 2-space files.",
        issues=["No defect found."],
        confidence=0.7,
    )
    _state_, block, requests, recorder = _scenario(round10_pre_probe, draft, None)

    assert requests == [] and recorder.calls == []
    assert block["patch_candidate"] is None
    assert block["candidate_effect_status"] == "no_op"
    assert block["summary"] == "The classifier already handles 2-space files."
    assert "No defect found." in block["issues"]
    assert block["final_candidate_generation"] == GENERATION_INITIAL
    assert block["final_candidate_fingerprint"] == (
        block["candidate_effect_candidate_fingerprint"]
    )
    assert block["candidate_presentation_coherent"] is True
    # §14 — nothing implies a verified or approval-ready state.
    assert block["needs_escalation"] is True
    assert block["human_review_eligible"] is False
    assert block["approval_ready"] is False
    assert "candidate_verification_status" not in block


def test_first_draft_safe_minimal_rejection_keeps_the_authors_claim(round10_pre_probe):
    """§14/§19 — the gate demotes the payload's confidence; the claim survives."""

    draft = _response(
        LSTRIP_BODY,
        summary="Measure the indent width after stripping line endings.",
        issues=["Prefix tests misclassify nested lines."],
        confidence=0.95,
    )
    _state_, block, requests, recorder = _scenario(round10_pre_probe, draft, None)

    assert requests == [] and recorder.calls == []
    assert block["candidate_novelty_admitted"] is False
    assert block["patch_candidate"] is None
    # PATCH.MINIMAL's existing demotion, unchanged ...
    assert block["confidence"] == 0.2
    # ... and the author's own claim, kept beside it rather than rewritten.
    assert block["candidate_presentation_model_confidence"] == 0.95
    assert block["summary"] == "Measure the indent width after stripping line endings."
    assert block["final_candidate_generation"] == GENERATION_INITIAL
    assert block["final_candidate_fingerprint"] == (
        block["candidate_novelty_candidate_fingerprint"]
    )
    assert block["candidate_presentation_coherent"] is True
    assert block["candidate_revision_attempted"] is False


# ═══════════════════════════════════════════════════════════════════════════
# §16 — Candidate1 verified
# ═══════════════════════════════════════════════════════════════════════════

VERIFIED_SUMMARY1 = (
    "Derive the base indentation unit from every leading width so nested lines "
    "cannot outvote the unit."
)
VERIFIED_ISSUE1 = "Branch order let 4-space-deep lines outvote a 2-space unit."


@pytest.fixture(scope="module")
def verified_revision(round10_pre_probe):
    return _scenario(
        round10_pre_probe,
        ROUND10["candidate0_response"],
        _response(
            CORRECT_LOCAL_ONLY_BODY,
            summary=VERIFIED_SUMMARY1,
            issues=[VERIFIED_ISSUE1],
            confidence=0.85,
            needs_escalation=True,
        ),
        historical_oracle=True,
    )


def test_verified_candidate1_is_presented_with_its_own_account(verified_revision):
    _state_, block, requests, recorder = verified_revision

    assert len(requests) == 1 and recorder.calls == []
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_VERIFIED
    assert block["candidate_verification_status"] == "verified"
    revised = block["candidate_revision_revised_candidate_fingerprint"]
    assert candidate_fingerprint_from_payload(block) == revised
    assert block["final_candidate_fingerprint"] == revised
    assert block["final_candidate_generation"] == GENERATION_REVISION
    assert block["summary"] == VERIFIED_SUMMARY1
    assert block["issues"] == [VERIFIED_ISSUE1]
    assert block["confidence"] == 0.85
    assert block["candidate_presentation_coherent"] is True
    assert block["candidate_revision_previous_candidate"]["summary"] == SUMMARY0


def test_verified_candidate1_gains_no_authority_from_coherence(verified_revision):
    """§16/§34 — a coherent presentation authorizes nothing."""

    _state_, block, _requests, _recorder = verified_revision

    assert block["execution_authorized"] is False
    assert block["write_authority"] is False
    assert block["auto_apply_allowed"] is False
    assert block["patch_application_authority"] is False
    assert block["final_repository_changed"] is False
    # The author's own escalation claim is recorded, and is not the harness's.
    assert block["candidate_presentation_model_needs_escalation"] is True
    for key in pipeline._CANDIDATE_PRESENTATION_KEYS:
        assert "authori" not in key and "approval" not in key and "eligib" not in key


# ═══════════════════════════════════════════════════════════════════════════
# §5/§17 — an invalid revision creates no ghost Candidate1
# ═══════════════════════════════════════════════════════════════════════════


def test_invalid_revision_leaves_candidate0_as_the_only_candidate(round10_pre_probe):
    _state_, block, requests, recorder = _scenario(
        round10_pre_probe, ROUND10["candidate0_response"], "this is not json"
    )

    assert len(requests) == 1 and recorder.calls == []
    assert block["candidate_revision_outcome"] == OUTCOME_REVISION_OUTPUT_INVALID
    assert block["candidate_revision_output_rejection_reason"] == OUTPUT_NO_JSON_PAYLOAD
    # No Candidate1 bundle, fingerprint or confidence anywhere.
    assert block["candidate_revision_present"] is False
    assert block["candidate_revision_revised_candidate_fingerprint"] == ""
    assert "candidate_revision_previous_candidate" not in block
    assert block["final_candidate_generation"] == GENERATION_INITIAL
    assert block["final_candidate_fingerprint"] == FP0
    assert candidate_fingerprint_from_payload(block) == FP0
    # Candidate0's narrative and patch stay internally bound.
    assert block["summary"] == SUMMARY0
    assert ISSUE0 in block["issues"]
    assert block["confidence"] == 0.9
    assert block["candidate_presentation_model_confidence"] == 0.9
    assert block["candidate_presentation_coherent"] is True
    # And it is still not reviewable.
    assert block["needs_escalation"] is True
    assert block["human_review_eligible"] is False


# ═══════════════════════════════════════════════════════════════════════════
# §18 — Candidate1 rejected by safe_minimal, and Candidate1 as an exact no-op
# ═══════════════════════════════════════════════════════════════════════════


def test_safe_minimal_rejected_candidate1_keeps_its_own_account(round10_pre_probe):
    revision = _response(
        LSTRIP_BODY,
        summary="Strip line endings, then measure the indent width modulo four.",
        issues=["Prefix tests cannot see nesting depth."],
        confidence=0.95,
    )
    _state_, block, requests, recorder = _scenario(
        round10_pre_probe, ROUND10["candidate0_response"], revision
    )

    assert len(requests) == 1 and recorder.calls == []
    assert block["candidate_novelty_admitted"] is False
    assert block["patch_candidate"] is None
    assert block["candidate_revision_outcome"] == OUTCOME_REVISED_CANDIDATE_REJECTED
    revised = block["candidate_revision_revised_candidate_fingerprint"]
    assert block["candidate_novelty_candidate_fingerprint"] == revised
    assert block["final_candidate_fingerprint"] == revised
    assert block["final_candidate_generation"] == GENERATION_REVISION
    assert block["summary"] == (
        "Strip line endings, then measure the indent width modulo four."
    )
    assert "Prefix tests cannot see nesting depth." in block["issues"]
    assert ISSUE0 not in block["issues"]
    assert block["confidence"] == 0.2
    assert block["candidate_presentation_model_confidence"] == 0.95
    assert block["candidate_presentation_coherent"] is True
    assert block["needs_escalation"] is True


def test_no_op_candidate1_is_identified_truthfully(round10_pre_probe):
    revision = _response(
        SHIPPED_BODY,
        summary="The current branch order is already correct.",
        confidence=0.6,
    )
    _state_, block, requests, recorder = _scenario(
        round10_pre_probe, ROUND10["candidate0_response"], revision
    )

    assert len(requests) == 1 and recorder.calls == []
    assert block["candidate_effect_status"] == "no_op"
    assert block["patch_candidate"] is None
    revised = block["candidate_revision_revised_candidate_fingerprint"]
    assert block["candidate_effect_candidate_fingerprint"] == revised
    assert block["final_candidate_fingerprint"] == revised
    assert block["final_candidate_generation"] == GENERATION_REVISION
    assert block["summary"] == "The current branch order is already correct."
    assert block["confidence"] == 0.6
    assert ISSUE0 not in block.get("issues", [])
    assert block["candidate_presentation_coherent"] is True


# ═══════════════════════════════════════════════════════════════════════════
# §8/§9/§26 — a field Candidate1 omits is absent, never Candidate0's
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def silent_revision(round10_pre_probe):
    """The Round-10 revision with its summary, issues and confidence removed."""

    silent = {
        key: value
        for key, value in CANDIDATE1.items()
        if key not in {"summary", "issues", "confidence"}
    }
    return _scenario(
        round10_pre_probe, ROUND10["candidate0_response"], json.dumps(silent)
    )


def test_missing_summary_does_not_inherit_candidate0s(silent_revision):
    _state_, block, _requests, _recorder = silent_revision

    assert candidate_fingerprint_from_payload(block) == FP1
    assert "summary" not in block
    assert block["candidate_revision_previous_candidate"]["summary"] == SUMMARY0


def test_missing_confidence_does_not_inherit_candidate0s(silent_revision):
    _state_, block, _requests, _recorder = silent_revision

    assert "confidence" not in block
    assert block["candidate_presentation_model_confidence"] is None
    # The existing reader of the field sees "unavailable", not 0.9.
    confidence, _escalation = get_confidence_and_escalation(block)
    assert confidence == 0.0


def test_missing_issues_do_not_inherit_candidate0s(silent_revision):
    _state_, block, _requests, _recorder = silent_revision

    assert ISSUE0 not in block["issues"]
    assert all(
        isinstance(item, dict) and item.get("type") == "candidate_verification"
        for item in block["issues"]
    )
    assert block["candidate_presentation_authored_fields"] == ["needs_escalation"]
    assert block["candidate_presentation_coherent"] is True


# ═══════════════════════════════════════════════════════════════════════════
# §25 — cross-binding is impossible through the composer, or fails closed
# ═══════════════════════════════════════════════════════════════════════════

FP_A = "a" * 64
FP_B = "b" * 64
C1_CANDIDATE = {
    "file": TARGET_FILE,
    "relative_path": TARGET_FILE,
    "target_node_kind": "function",
    "target_node_name": TARGET_SYMBOL,
    "target_snippet": SOURCE,
    "patched_snippet": _with_body(CORRECT_LOCAL_ONLY_BODY),
}
HARNESS_FINDING = {
    "severity": "high",
    "type": "candidate_verification",
    "reason": "measured",
    "code": "behavior_preservation_regressed",
}


def _record0() -> CandidateAuthoredFields:
    return capture_candidate_authored_fields(CANDIDATE0, generation=GENERATION_INITIAL)


def _record1(**drop: bool) -> CandidateAuthoredFields:
    response = {k: v for k, v in CANDIDATE1.items() if not drop.get(k)}
    return capture_candidate_authored_fields(
        response,
        generation=GENERATION_REVISION,
        confidence=response.get("confidence"),
        supersedes=_record0(),
    )


def _candidate0_payload() -> dict[str, Any]:
    """Candidate0's account as it stands when the revision installs Candidate1."""

    block = copy.deepcopy(CANDIDATE0)
    block["issues"] = [HARNESS_FINDING, ISSUE0]
    return block


def test_a_summary0_with_patch1_cannot_be_installed():
    """A — an initial record cannot install a candidate over another one."""

    with pytest.raises(CandidatePresentationError):
        install_candidate_presentation(
            _candidate0_payload(), candidate=C1_CANDIDATE, authored=_record0()
        )
    block = _candidate0_payload()
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=_record1())
    assert block["summary"] == SUMMARY1
    assert block["patch_candidate"] == C1_CANDIDATE


def test_a_summary0_beside_a_candidate1_identity_fails_closed():
    block = {"summary": SUMMARY0, "confidence": 1.0, "issues": [ISSUE1]}
    block["candidate_verification_candidate_fingerprint"] = FP_B

    presentation = bind_final_candidate_presentation(
        block,
        author=_record1(),
        revised_candidate_present=True,
        revised_candidate_fingerprint=FP_B,
        payload_candidate_fingerprint=None,
    )

    assert presentation.coherent is False
    assert presentation.incoherence_reasons == (INCOHERENT_SUMMARY,)
    assert presentation.candidate_fingerprint == ""
    assert "summary" not in block and "confidence" not in block
    telemetry = presentation.as_telemetry()
    assert telemetry["final_candidate_fingerprint"] == ""
    assert telemetry["final_candidate_generation"] == ""
    assert telemetry["candidate_presentation_coherent"] is False


def test_a_candidate0_author_record_cannot_present_candidate1():
    block = {"summary": SUMMARY0}
    presentation = bind_final_candidate_presentation(
        block,
        author=_record0(),
        revised_candidate_present=True,
        revised_candidate_fingerprint=FP_B,
        payload_candidate_fingerprint=None,
    )

    assert presentation.coherent is False
    assert INCOHERENT_AUTHOR_GENERATION in presentation.incoherence_reasons
    assert "summary" not in block


def test_b_summary1_with_confidence0_cannot_be_installed():
    """B — Candidate1 supplied no confidence, so Candidate0's 0.9 leaves."""

    block = _candidate0_payload()
    install_candidate_presentation(
        block, candidate=C1_CANDIDATE, authored=_record1(confidence=True)
    )

    assert block["summary"] == SUMMARY1
    assert "confidence" not in block


def test_c_issues0_with_fingerprint1_cannot_be_installed_or_bound():
    """C — Candidate0's own issue leaves; the harness finding stays."""

    block = _candidate0_payload()
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=_record1())
    assert block["issues"] == [HARNESS_FINDING, ISSUE1]

    # A later write that put Candidate0's issue back is caught, not shipped.
    block["issues"].append(ISSUE0)
    block["candidate_verification_candidate_fingerprint"] = FP_B
    presentation = bind_final_candidate_presentation(
        block,
        author=_record1(),
        revised_candidate_present=True,
        revised_candidate_fingerprint=FP_B,
        payload_candidate_fingerprint=None,
    )
    assert presentation.coherent is False
    assert INCOHERENT_SUPERSEDED_ISSUES in presentation.incoherence_reasons
    assert block["issues"] == [HARNESS_FINDING]


@pytest.mark.parametrize(
    "kwargs,reason",
    [
        (
            dict(revised_candidate_present=True, revised_candidate_fingerprint=""),
            INCOHERENT_NO_CANDIDATE_IDENTITY,
        ),
        (
            dict(revised_candidate_present=True, revised_candidate_fingerprint="x"),
            INCOHERENT_NO_CANDIDATE_IDENTITY,
        ),
    ],
)
def test_d_patch1_without_a_candidate_identity_fails_closed(kwargs, reason):
    """D — a revision with no exact fingerprint presents no author's account."""

    block = {"summary": SUMMARY1, "confidence": 1.0, "patch_candidate": C1_CANDIDATE}
    presentation = bind_final_candidate_presentation(
        block,
        author=_record1(),
        payload_candidate_fingerprint=candidate_fingerprint_from_payload(block),
        **kwargs,
    )

    assert presentation.coherent is False
    assert reason in presentation.incoherence_reasons
    assert "summary" not in block and "confidence" not in block
    # Candidate bytes are evidence, not narrative; the receipts still name them.
    assert block["patch_candidate"] == C1_CANDIDATE


def test_d_a_revision_without_an_author_record_fails_closed():
    block = {"summary": SUMMARY1}
    presentation = bind_final_candidate_presentation(
        block,
        author=None,
        revised_candidate_present=True,
        revised_candidate_fingerprint=FP_B,
        payload_candidate_fingerprint=None,
    )

    assert presentation.incoherence_reasons == (INCOHERENT_NO_AUTHOR_RECORD,)
    assert "summary" not in block


def test_d_payload_bytes_or_a_receipt_naming_another_candidate_fail_closed():
    block = {"summary": SUMMARY1, "candidate_fingerprint": FP_A}
    presentation = bind_final_candidate_presentation(
        block,
        author=_record1(),
        revised_candidate_present=True,
        revised_candidate_fingerprint=FP_B,
        payload_candidate_fingerprint=FP_A,
    )

    assert presentation.coherent is False
    assert set(presentation.incoherence_reasons) == {
        INCOHERENT_PAYLOAD_CANDIDATE,
        INCOHERENT_RECEIPT_CANDIDATE,
    }


def test_d_an_initial_candidate_no_receipt_names_has_no_identity():
    """§4 — present bytes alone are never the identity source."""

    block = {"summary": SUMMARY0, "patch_candidate": C1_CANDIDATE}
    presentation = bind_final_candidate_presentation(
        block,
        author=_record0(),
        revised_candidate_present=False,
        revised_candidate_fingerprint="",
        payload_candidate_fingerprint=candidate_fingerprint_from_payload(block),
    )

    assert presentation.coherent is False
    assert INCOHERENT_NO_CANDIDATE_IDENTITY in presentation.incoherence_reasons


def test_a_payload_that_never_carried_a_candidate_is_not_annotated():
    block = {"summary": "No change is needed; this is an explanation."}
    assert (
        bind_final_candidate_presentation(
            block,
            author=capture_candidate_authored_fields(
                block, generation=GENERATION_INITIAL
            ),
            revised_candidate_present=False,
            revised_candidate_fingerprint="",
            payload_candidate_fingerprint=None,
        )
        is None
    )
    assert block == {"summary": "No change is needed; this is an explanation."}


def test_the_record_types_refuse_mixed_generations():
    with pytest.raises(CandidatePresentationError):
        CandidateAuthoredFields(generation=GENERATION_INITIAL, supersedes=_record0())
    with pytest.raises(CandidatePresentationError):
        CandidateAuthoredFields(generation=GENERATION_REVISION, supersedes=_record1())
    with pytest.raises(CandidatePresentationError):
        CandidateAuthoredFields(generation="generation_2")
    with pytest.raises(CandidatePresentationError):
        CandidateAuthoredFields(
            generation=GENERATION_INITIAL, values={"human_review_eligible": True}
        )
    with pytest.raises(CandidatePresentationError):
        CandidatePresentation(coherent=True, candidate_fingerprint="", generation="")
    with pytest.raises(CandidatePresentationError):
        CandidatePresentation(
            coherent=False, candidate_fingerprint=FP_A, generation=GENERATION_INITIAL,
            incoherence_reasons=(INCOHERENT_SUMMARY,),
        )
    with pytest.raises(CandidatePresentationError):
        superseded_candidate_history({}, _record1())


# ═══════════════════════════════════════════════════════════════════════════
# §1/§10/§26 — the record, the install and the history, as units
# ═══════════════════════════════════════════════════════════════════════════


def test_capture_records_only_what_the_response_supplied():
    record = capture_candidate_authored_fields(
        {"summary": "s", "patch_candidate": {"x": 1}, "human_review_eligible": True},
        generation=GENERATION_INITIAL,
    )

    assert record.authored_fields == ("summary",)
    assert record.supplied("summary") and not record.supplied("confidence")
    assert record.model_confidence is None and record.model_needs_escalation is None
    assert capture_candidate_authored_fields(None, generation=GENERATION_INITIAL) is None
    assert capture_candidate_authored_fields("text", generation=GENERATION_INITIAL) is None


def test_capture_takes_the_revision_confidence_from_the_parser():
    record = capture_candidate_authored_fields(
        {"confidence": 7}, generation=GENERATION_REVISION, confidence=None
    )
    assert not record.supplied("confidence")
    record = capture_candidate_authored_fields(
        {}, generation=GENERATION_REVISION, confidence=0.5
    )
    assert record.model_confidence == 0.5


def test_the_record_is_a_private_copy():
    response = {"summary": "s", "issues": [{"reason": "r"}]}
    record = capture_candidate_authored_fields(response, generation=GENERATION_INITIAL)
    response["issues"][0]["reason"] = "edited"
    response["summary"] = "edited"

    assert record.value("summary") == "s"
    assert record.issue_entries == [{"reason": "r"}]
    record.value("issues")[0]["reason"] = "edited again"
    assert record.issue_entries == [{"reason": "r"}]
    assert copy.deepcopy(record) == record


def test_install_removes_exactly_the_superseded_authors_entries():
    """Multiset semantics: the author's two lines go; a resembling finding stays."""

    record0 = capture_candidate_authored_fields(
        {"issues": ["same", "same"]}, generation=GENERATION_INITIAL
    )
    record1 = capture_candidate_authored_fields(
        {"summary": "one"}, generation=GENERATION_REVISION, supersedes=record0
    )
    block = {"issues": ["same", {"type": "candidate_effect"}, "same", "same"]}
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record1)

    assert block["issues"] == [{"type": "candidate_effect"}, "same"]
    assert block["patch_plan"] is None


def test_install_without_an_author_record_attributes_nothing():
    """No record of Candidate0's author: nothing pre-install may describe Candidate1."""

    record1 = capture_candidate_authored_fields(
        {"summary": "one", "issues": ["mine"]},
        generation=GENERATION_REVISION,
        supersedes=None,
    )
    block = {"summary": "zero", "issues": ["unknown"], "confidence": 0.9}
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record1)

    assert block["summary"] == "one"
    assert block["issues"] == ["mine"]
    assert "confidence" not in block


def test_install_keeps_a_non_list_issues_value_as_the_author_wrote_it():
    record1 = capture_candidate_authored_fields(
        {"issues": "one prose issue"},
        generation=GENERATION_REVISION,
        supersedes=_record0(),
    )
    block = {"issues": [ISSUE0]}
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record1)
    assert block["issues"] == "one prose issue"

    block = {"issues": [HARNESS_FINDING, ISSUE0]}
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record1)
    assert block["issues"] == [HARNESS_FINDING, "one prose issue"]


def test_install_never_writes_needs_escalation():
    """§7 — the harness owns the payload's escalation flag."""

    block = {"needs_escalation": True}
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=_record1())
    assert block["needs_escalation"] is True
    assert "needs_escalation" not in PRIMARY_PRESENTATION_FIELDS


def test_the_history_without_a_record_claims_no_narrative():
    history = superseded_candidate_history(
        {"summary": "zero", "candidate_verification_status": "rejected"}, None
    )
    assert history["authored_fields"] is None
    assert "summary" not in history and "issues" not in history
    assert history["verification_status"] == "rejected"
    assert history["generation"] == GENERATION_INITIAL


# ═══════════════════════════════════════════════════════════════════════════
# §23 — display, persistence and history reload carry the same binding
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture(scope="module")
def round10_display(round10):
    """The state after ANSWER.GROUND, exactly as the CLI and web runners use it."""

    state = copy.deepcopy(round10[0])
    receipt = ground_state_answer(state)
    return state, receipt


def _assert_round10_coherent(payload: dict[str, Any]) -> None:
    assert payload["summary"] == SUMMARY1
    assert candidate_fingerprint_from_payload(payload) == FP1
    assert payload["confidence"] == 1.0
    assert payload["final_candidate_fingerprint"] == FP1
    assert payload["final_candidate_generation"] == GENERATION_REVISION
    assert payload["candidate_presentation_coherent"] is True
    assert ISSUE0 not in payload["issues"] and ISSUE1 in payload["issues"]
    assert payload["candidate_revision_previous_candidate"]["summary"] == SUMMARY0


def test_the_display_payload_is_coherent(round10_display):
    state, _receipt = round10_display

    _assert_round10_coherent(state.json_block)
    assert json.loads(state.final_answer) == state.json_block
    assert state.human_answer == state.final_answer


def test_the_persisted_payload_is_coherent(round10_display, monkeypatch):
    """The CLI's persistence: the structured artifact and the assistant message."""

    from core import session_io

    state, _receipt = round10_display
    artifacts: list[tuple[Any, str, str]] = []
    messages: list[tuple[Any, str, str]] = []
    monkeypatch.setattr(
        session_io, "save_artifact", lambda *args: artifacts.append(args)
    )
    monkeypatch.setattr(
        session_io, "save_message", lambda *args: messages.append(args)
    )

    session_io.save_structured_outputs(state)

    ((_sid, kind, artifact),) = artifacts
    ((_sid2, role, message),) = messages
    assert kind == "structured_output" and role == "assistant"
    _assert_round10_coherent(json.loads(artifact))
    _assert_round10_coherent(json.loads(message))
    assert json.loads(artifact) == json.loads(message)


def test_history_reload_is_coherent(round10_display, tmp_path, monkeypatch):
    """The web history: the saved session, reloaded the way /session/<id> does."""

    import web.session_store as session_store
    from web.app import app, save_session

    state, receipt = round10_display
    monkeypatch.setattr(session_store, "SESSION_FILE", tmp_path / "sessions.json")
    # The result assembly web/runner.py performs after ANSWER.GROUND.
    result = {
        "answer": state.final_answer,
        "patch": json.dumps(state.json_block, indent=2) if state.json_block else "",
        "answer_entity_grounding": receipt,
    }
    saved = save_session(ROUND10["task"], str(ROOT), "full", result, "cattus")

    reloaded = session_store.find_session(saved["id"])["result"]
    _assert_round10_coherent(json.loads(reloaded["answer"]))
    _assert_round10_coherent(json.loads(reloaded["patch"]))

    app.config["TESTING"] = True
    with app.test_client() as client:
        assert client.get(f"/session/{saved['id']}").status_code == 200


# ═══════════════════════════════════════════════════════════════════════════
# §22 — ANSWER.GROUND reads the right author, and never the binding
# ═══════════════════════════════════════════════════════════════════════════


def test_grounding_leaves_the_binding_and_the_history_byte_identical(
    round10, round10_display
):
    _state_, operational, _requests, _recorder = round10
    state, _receipt = round10_display
    display = state.json_block

    for key in pipeline._CANDIDATE_PRESENTATION_KEYS:
        assert display[key] == operational[key], key
    assert display["candidate_revision_previous_candidate"] == (
        operational["candidate_revision_previous_candidate"]
    )
    for key in pipeline._CANDIDATE_VERIFICATION_KEYS:
        if key in operational:
            assert display[key] == operational[key], key
    for key in pipeline._CANDIDATE_PRESENTATION_KEYS:
        assert "not established in the current evidence" not in json.dumps(display[key])


def test_the_binding_keys_are_harness_owned_not_answer_surface():
    keys = set(pipeline._CANDIDATE_PRESENTATION_KEYS)

    assert not (keys & set(_ANSWER_SURFACE_KEYS))
    assert "candidate_revision_previous_candidate" not in _ANSWER_SURFACE_KEYS


def test_candidate1s_own_prose_is_still_grounded():
    """The final author's summary is on the answer surface and gets checked."""

    record1 = capture_candidate_authored_fields(
        {"summary": "The defect lives in core/imaginary_indent_detector.py."},
        generation=GENERATION_REVISION,
        supersedes=_record0(),
    )
    block = _candidate0_payload()
    install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record1)
    block["final_candidate_fingerprint"] = FP_B
    state = AgentState(
        interface="agent",
        mode="planner",
        user_input=ROUND10["task"],
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language="python",
        task_type="bug_fix",
    )
    state.repo_path = str(ROOT)
    state.repository_graph = _graph()

    _text, _human, display, receipt = ground_answer_for_display(state, "", block)

    assert "not established in the current evidence" in display["summary"]
    assert receipt["unverified_entity_count"] >= 1
    assert display["final_candidate_fingerprint"] == FP_B
    assert display["patch_candidate"]["patched_snippet"] == C1_CANDIDATE["patched_snippet"]


# ═══════════════════════════════════════════════════════════════════════════
# Vocabulary and contract parity
# ═══════════════════════════════════════════════════════════════════════════


def test_the_ownership_table_is_the_authoring_contracts_envelope():
    """§11 — ownership is declared for exactly the fields the author is given."""

    envelope = set(re.findall(r'^\s*"(\w+)":', PATCH_RESPONSE_SCHEMA, re.MULTILINE))
    envelope -= {"op", "relative_path", "content", "target_snippet", "patched_snippet"}

    assert set(AUTHORING_ENVELOPE_OWNERSHIP) == envelope
    assert AUTHORED_PRESENTATION_FIELDS == (
        "summary",
        "issues",
        "confidence",
        "needs_escalation",
    )
    assert {
        name
        for name, owner in AUTHORING_ENVELOPE_OWNERSHIP.items()
        if owner == OWNER_CANDIDATE_BYTES
    } == {"patch_candidate", "patch_plan"}
    assert CANDIDATE_GENERATIONS == ("initial", "revision")


def test_the_incoherence_vocabulary_is_closed():
    assert len(set(INCOHERENCE_REASONS)) == len(INCOHERENCE_REASONS) == 7
    with pytest.raises(CandidatePresentationError):
        CandidatePresentation(
            coherent=False,
            candidate_fingerprint="",
            generation="",
            incoherence_reasons=("probably_fine",),
        )


def test_the_telemetry_is_one_flat_group_with_no_nested_receipt():
    """§41 — additive keys, no second duplicated receipt block."""

    presentation = CandidatePresentation(
        coherent=True, candidate_fingerprint=FP_A, generation=GENERATION_INITIAL
    )
    telemetry = presentation.as_telemetry()

    assert tuple(telemetry) == pipeline._CANDIDATE_PRESENTATION_KEYS
    assert all(not isinstance(value, dict) for value in telemetry.values())
    assert telemetry["candidate_presentation_schema_version"] == (
        "candidate_presentation_live_1_v1"
    )
    # §42 — the revision receipt's own wire version did not move.
    assert REVISION_SCHEMA_VERSION == "candidate_revision_live_1_v1"
    assert pipeline._CANDIDATE_PRESENTATION_KEYS in (
        pipeline._CANDIDATE_BOUND_RECEIPT_GROUPS
    )


def test_the_guardrails_say_what_this_phase_refuses():
    guardrails = candidate_presentation_guardrails()

    assert guardrails["presentation_fields_follow_one_candidate"] is True
    assert guardrails["superseded_author_kept_as_rejected_history"] is True
    for key in (
        "missing_fields_inherit_from_a_superseded_author",
        "presentation_generates_text",
        "presentation_clamps_confidence",
        "presentation_writes_needs_escalation",
        "presentation_grants_review_or_approval",
        "presentation_grants_execution_authority",
        "presentation_changes_verification",
        "presentation_makes_model_calls",
        "presentation_traverses_the_repository",
    ):
        assert guardrails[key] is False, key


# ═══════════════════════════════════════════════════════════════════════════
# Governance: containment, frozen boundaries, cost, registry
# ═══════════════════════════════════════════════════════════════════════════


def _reversal() -> dict[str, Any]:
    return json.loads(REVERSAL_FIXTURE.read_text(encoding="utf-8"))


def test_the_production_change_is_a_reversible_containment_proof():
    """Every edited file's pre-phase bytes are rebuilt from the shipped ones."""

    fixture = _reversal()
    assert [r["path"] for r in fixture["reversals"]] == [
        "core/pipeline.py",
        "core/agent_state.py",
    ]
    for reversal in fixture["reversals"]:
        shipped = before_later_receipts(
            reversal["path"],
            (ROOT / reversal["path"]).read_bytes(),
            newer_than=REVERSAL_FIXTURE,
        )
        assert hashlib.sha256(shipped).hexdigest() == reversal["post_sha256"]
        text = shipped.decode("utf-8")
        for hunk in reversal["hunks"]:
            assert text.count(hunk["post"]) == 1
            text = text.replace(hunk["post"], hunk["pre"], 1)
        assert hashlib.sha256(text.encode("utf-8")).hexdigest() == reversal["pre_sha256"]

    remediation = json.loads(
        (FIXTURES / "2026-09-10-harness-remediation-reversal.json").read_text(
            encoding="utf-8"
        )
    )
    pipeline_link = next(
        r for r in remediation["reversals"] if r["path"] == "core/pipeline.py"
    )
    live5 = json.loads(
        (FIXTURES / "defect_probe_live5_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    by_path = {r["path"]: r for r in fixture["reversals"]}
    # The chain: this phase's preimage is exactly the history already pinned.
    assert by_path["core/pipeline.py"]["pre_sha256"] == pipeline_link["post_sha256"]
    assert by_path["core/agent_state.py"]["pre_sha256"] == (
        live5["files"]["core/agent_state.py"]
    )
    assert REVERSAL_FIXTURE in LATER_RECEIPTS


def test_the_pipeline_change_is_two_helpers_and_three_touched_definitions():
    def definitions(source: str) -> dict[str, str]:
        return {
            node.name: hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    for reversal in _reversal()["reversals"]:
        post = (ROOT / reversal["path"]).read_bytes().decode("utf-8")
        pre = post
        for hunk in reversal["hunks"]:
            pre = pre.replace(hunk["post"], hunk["pre"], 1)
        before, after = definitions(pre), definitions(post)
        assert sorted(set(before) - set(after)) == reversal["removed_definitions"] == []
        assert sorted(set(after) - set(before)) == reversal["added_definitions"]
        assert sorted(
            n for n in before if n in after and before[n] != after[n]
        ) == reversal["changed_definitions"]

    pipeline_reversal, state_reversal = _reversal()["reversals"]
    assert pipeline_reversal["added_definitions"] == [
        "_record_candidate_presentation",
        "_recorded_candidate_presentation",
    ]
    assert pipeline_reversal["changed_definitions"] == [
        "_maybe_revise_rejected_candidate",
        "_verify_authored_candidate_without_mutation",
        "finalize_answer",
    ]
    assert pipeline_reversal["added_assignments"] == ["_CANDIDATE_PRESENTATION_KEYS"]
    assert pipeline_reversal["changed_assignments"] == [
        "_CANDIDATE_BOUND_RECEIPT_GROUPS"
    ]
    assert state_reversal["added_definitions"] == []
    assert state_reversal["changed_definitions"] == ["AgentState"]


def test_the_install_is_one_call_in_the_revision_path():
    """§20/§21 — no candidate-authored field is written beside the install."""

    source = inspect.getsource(pipeline._maybe_revise_rejected_candidate)

    assert source.count("install_candidate_presentation(") == 1
    assert source.count("_call_revision_provider(") == 1
    for forbidden in (
        'block["patch_candidate"] =',
        'block["confidence"] =',
        'block["summary"]',
        'block["issues"]',
        'block.pop("confidence"',
    ):
        assert forbidden not in source, forbidden
    capture = inspect.getsource(pipeline.finalize_answer)
    assert capture.index("capture_candidate_authored_fields(") < capture.index(
        "reject_schema_drift(state)"
    )


FROZEN_FILES = (
    "core/candidate_revision.py",
    "core/candidate_verification.py",
    "core/behavioral_matrix.py",
    "core/behavioral_expectation.py",
    "core/defect_probe.py",
    "core/candidate_defect_probe.py",
    "core/paired_defect_probe.py",
    "core/candidate_mutation_effect.py",
    "core/candidate_sandbox_validation.py",
    "core/local_binding_novelty.py",
    "core/targeted_repository_validation.py",
    "core/check_oracle_assessment.py",
    "core/execution_eligibility_policy.py",
    "core/execution_outcome_telemetry.py",
    "core/live_execution_authorization.py",
    "core/human_apply_authorization.py",
    "core/answer_entity_grounding.py",
    "core/localization_handoff.py",
    "core/patch_authoring_contract.py",
    "core/prompter.py",
    "core/control_engine.py",
    "core/code_dna.py",
    "core/session_io.py",
    "core/live_task_routing.py",
    "core/live_task_shape.py",
    "patching/patch_gates.py",
    "policy/decision_helper.py",
    "web/runner.py",
    "web/session_store.py",
    "main.py",
)


def test_every_frozen_boundary_is_byte_identical():
    """Probes, verification, safe_minimal, validation, authority, routing, display.

    Evaluated through the maintenance chain, so a later receipt that edits one
    of these files is undone before comparison rather than silently re-pinned.
    """

    pins = json.loads(
        (FIXTURES / "answer_coherence_live1_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    assert tuple(pins["files"]) == FROZEN_FILES
    drifted = [
        rel
        for rel, digest in pins["files"].items()
        if hashlib.sha256(
            before_later_receipts(rel, (ROOT / rel).read_bytes())
        ).hexdigest()
        != digest
    ]
    assert not drifted, drifted


def test_the_real_classify_indent_is_untouched():
    """§30 — structural indentation semantics are future work.

    INDENT.RUNTIME.1 was authorized to add a keyword-only ``language``
    parameter to ``_classify_indent``'s signature. This reads the
    reconstructed pre-INDENT.RUNTIME.1 source through
    ``before_later_receipts`` (the same helper ``test_every_frozen_
    boundary_is_byte_identical`` above already uses) so it keeps proving the
    *algorithm* has not moved since Round 10, through a signature line this
    phase was authorized to change.
    """

    # SOURCE (Round 10's recorded control_source_snippet) was captured
    # LF-normalized; before_later_receipts preserves core/code_dna.py's raw
    # (partly CRLF) bytes, so normalize the same way before comparing.
    historical_source = (
        before_later_receipts(
            "core/code_dna.py", (ROOT / "core/code_dna.py").read_bytes()
        )
        .decode("utf-8")
        .replace("\r\n", "\n")
    )
    (node,) = [
        item
        for item in ast.parse(historical_source).body
        if isinstance(item, ast.FunctionDef) and item.name == "_classify_indent"
    ]
    historical_function = ast.get_source_segment(historical_source, node)
    assert historical_function.rstrip("\n") == SOURCE
    assert "gcd" not in inspect.getsource(_classify_indent)


def test_the_module_is_pure_and_stdlib_only():
    """§29/§40 — composition reaches no provider, file, network or repository."""

    source = (ROOT / "core" / "candidate_presentation.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert modules <= {"__future__", "copy", "dataclasses", "re", "types", "typing"}
    called = {
        node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    for forbidden in (
        "open", "read_text", "read_bytes", "walk", "rglob", "glob", "exec", "eval",
        "run_gemini_request", "run_deepseek_review", "retrieve_context", "sha256",
    ):
        assert forbidden not in called, forbidden


def test_binding_costs_microseconds():
    """§40 — composition overhead is sub-millisecond per run."""

    record = _record1()
    started = time.perf_counter()
    for _ in range(1000):
        block = _candidate0_payload()
        install_candidate_presentation(block, candidate=C1_CANDIDATE, authored=record)
        block["candidate_verification_candidate_fingerprint"] = FP_B
        bind_final_candidate_presentation(
            block,
            author=record,
            revised_candidate_present=True,
            revised_candidate_fingerprint=FP_B,
            payload_candidate_fingerprint=None,
        )
    per_run = (time.perf_counter() - started) / 1000
    assert per_run < 0.001, per_run


def test_the_registry_entry_is_present_and_honest():
    from core.phase_registry import load_phase_registry

    registry = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    phase = {item["phase_id"]: item for item in registry["phases"]}[
        presentation_module.PHASE_ID
    ]

    assert phase["status"] == "complete"
    assert phase["track"] == "CHECK"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    for required in (
        "PATCH.AUTHOR.LIVE.1",
        "PATCH.AUTHOR.LIVE.2",
        "CANDIDATE.VERIFY.LIVE.1",
        "DEFECT.PROBE.LIVE.5",
        "PATCH.MINIMAL.LIVE.1",
        "PATCH.MINIMAL.LIVE.2",
        "ANSWER.GROUND.LIVE.4",
        "EXEC.POLICY.LIVE.1",
        "EXEC.APPROVAL.LIVE.1",
        "EXEC.AUTH.LIVE.1",
    ):
        assert required in phase["prerequisites"], required
    for artifact in (
        "core/candidate_presentation.py",
        "tests/test_answer_coherence_live1.py",
        "tests/fixtures/answer_coherence_live1_round10.json",
        "tests/fixtures/answer_coherence_live1_reversal.json",
        "tests/fixtures/answer_coherence_live1_frozen_boundaries.json",
    ):
        assert artifact in phase["expected_artifacts"], artifact
        assert (ROOT / artifact).exists(), artifact
    ids = {item["phase_id"] for item in registry["phases"]}
    for forbidden_phase in (
        "ANSWER.COHERENCE.LIVE.2",
        "DIAG.INDENT.SEMANTICS.1",
        "PATCH.AUTHOR.LIVE.4",
    ):
        assert forbidden_phase not in ids
