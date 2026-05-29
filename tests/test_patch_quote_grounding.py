"""Phase 12.9 — Quote-only patch grounding.

A patch_candidate's target_snippet must appear *verbatim* in real source text
(the target file or retrieved source context) before it is accepted as a
candidate. Hallucinated target snippets that the apply-time gate would reject
anyway must never surface as valid candidates in the final patch result.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.agent_state import AgentState
from patching.patch_gates import reject_ungrounded_candidate_quotes
from patching.patch_grounding import (
    UNGROUNDED_WARNING,
    GroundingResult,
    enforce_patch_candidate_grounding,
    source_snippet_exists,
    validate_patch_candidate_grounding,
)


# --- Shared fixture text -------------------------------------------------

VIP_LINE = 'df.loc[idx, "Name"] == row["Name"] + " (VIP)"'
VIP_FIX = 'df.loc[idx, "Name"] = row["Name"] + " (VIP)"'
ILOC_LINE = "df_report = df.iloc[1:11]"
ILOC_FIX = "df_report = df.head(10)"
ENUMERATE_HALLUCINATION = "for i, customer in enumerate(customers, start=1):"

SAMPLE_SOURCE = (
    "import pandas as pd\n"
    "\n"
    "\n"
    "def build_report(df):\n"
    "    for idx, row in df.iterrows():\n"
    '        if row["is_vip"]:\n'
    "            " + VIP_LINE + "\n"
    "    " + ILOC_LINE + "\n"
    "    return df_report\n"
)


def test_sample_source_sanity():
    # The fixture must actually contain the good snippets and NOT the bad one,
    # otherwise the grounding tests below prove nothing.
    assert VIP_LINE in SAMPLE_SOURCE
    assert ILOC_LINE in SAMPLE_SOURCE
    assert ENUMERATE_HALLUCINATION not in SAMPLE_SOURCE


def _candidate(target_snippet: str, patched_snippet: str) -> dict:
    return {
        "relative_path": "report.py",
        "target_node_name": "build_report",
        "target_snippet": target_snippet,
        "patched_snippet": patched_snippet,
    }


def _block(candidate: dict, **extra) -> dict:
    block = {
        "summary": "fix",
        "issues": [],
        "patch_candidate": candidate,
        "patch_plan": None,
        "confidence": 0.9,
        "needs_escalation": False,
    }
    block.update(extra)
    return block


# --- source_snippet_exists primitive -------------------------------------

def test_source_snippet_exists_is_exact_substring():
    assert source_snippet_exists(ILOC_LINE, SAMPLE_SOURCE) is True
    assert source_snippet_exists(ENUMERATE_HALLUCINATION, SAMPLE_SOURCE) is False
    # empty inputs are never grounded
    assert source_snippet_exists("", SAMPLE_SOURCE) is False
    assert source_snippet_exists(ILOC_LINE, "") is False


# --- validate_patch_candidate_grounding (unit) ---------------------------

def test_rejects_hallucinated_enumerate_target_unit():
    """Test 1 (unit half): the enumerate snippet is not in source."""
    candidate = _candidate(ENUMERATE_HALLUCINATION, "for i, customer in enumerate(customers, start=2):")
    result = validate_patch_candidate_grounding(candidate, SAMPLE_SOURCE)
    assert isinstance(result, GroundingResult)
    assert result.is_grounded is False
    assert result.matched_file is None
    assert result.matched_snippet is None


def test_accepts_exact_pandas_iloc_snippet():
    """Test 2: exact iloc snippet is grounded."""
    candidate = _candidate(ILOC_LINE, ILOC_FIX)
    result = validate_patch_candidate_grounding(candidate, SAMPLE_SOURCE)
    assert result.is_grounded is True
    assert result.matched_snippet == ILOC_LINE
    # With a bare-string source the matched file falls back to the candidate's path.
    assert result.matched_file == "report.py"


def test_accepts_exact_vip_assignment_typo_snippet():
    """Test 3: exact VIP `==` typo snippet is grounded (we patch the typo)."""
    candidate = _candidate(VIP_LINE, VIP_FIX)
    result = validate_patch_candidate_grounding(candidate, SAMPLE_SOURCE)
    assert result.is_grounded is True
    assert result.matched_snippet == VIP_LINE


def test_grounding_accepts_dict_of_files_and_reports_matched_file():
    candidate = _candidate(ILOC_LINE, ILOC_FIX)
    sources = {"other.py": "print('nope')\n", "report.py": SAMPLE_SOURCE}
    result = validate_patch_candidate_grounding(candidate, sources)
    assert result.is_grounded is True
    assert result.matched_file == "report.py"


def test_grounding_accepts_list_of_path_text_pairs():
    candidate = _candidate(VIP_LINE, VIP_FIX)
    sources = [("a.py", "unrelated\n"), ("report.py", SAMPLE_SOURCE)]
    result = validate_patch_candidate_grounding(candidate, sources)
    assert result.is_grounded is True
    assert result.matched_file == "report.py"


def test_empty_target_snippet_is_ungrounded_with_readable_reason():
    candidate = _candidate("", ILOC_FIX)
    result = validate_patch_candidate_grounding(candidate, SAMPLE_SOURCE)
    assert result.is_grounded is False
    assert "target_snippet" in result.reason


def test_no_fuzzy_matching_accepts_unrelated_snippets():
    """Test 7: near-miss snippets must NOT be accepted — grounding is exact."""
    near_misses = [
        "df_report = df.iloc[1:10]",          # 1:10 vs 1:11
        ILOC_FIX,                              # the fixed form, not in source
        "for i, customer in enumerate(customers, start=2):",
        VIP_FIX,                               # single `=`, source has `==`
        "df_report  = df.iloc[1:11]",          # extra whitespace
    ]
    for snippet in near_misses:
        result = validate_patch_candidate_grounding(_candidate(snippet, "x"), SAMPLE_SOURCE)
        assert result.is_grounded is False, f"unexpectedly grounded: {snippet!r}"
    # control: the exact snippet IS grounded, proving we don't reject everything.
    assert validate_patch_candidate_grounding(_candidate(ILOC_LINE, ILOC_FIX), SAMPLE_SOURCE).is_grounded


# --- enforce_patch_candidate_grounding (result-level) --------------------

def test_enforce_rejects_hallucinated_candidate():
    """Test 1: rejected, patch_plan null, confidence lowered, warning recorded."""
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"), patch_plan=[{"op": "noop"}], confidence=0.9)
    result = enforce_patch_candidate_grounding(block, SAMPLE_SOURCE)

    assert result.is_grounded is False
    # patch_plan nulled
    assert block["patch_plan"] is None
    # confidence lowered
    assert block["confidence"] < 0.9
    # candidate marked invalid
    assert block["patch_candidate"]["rejected"] is True
    # human-readable warning recorded as an issue
    assert any(i.get("reason") == UNGROUNDED_WARNING for i in block["issues"])


def test_enforce_lowers_control_confidence_when_present():
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"), control_confidence=0.8)
    enforce_patch_candidate_grounding(block, SAMPLE_SOURCE)
    assert block["control_confidence"] < 0.8


def test_enforce_preserves_valid_existing_patch_candidate():
    """Test 4: valid exact candidate is preserved unchanged."""
    plan = [{"op": "replace_snippet", "relative_path": "report.py",
             "target_snippet": ILOC_LINE, "patched_snippet": ILOC_FIX}]
    block = _block(_candidate(ILOC_LINE, ILOC_FIX), patch_plan=plan, confidence=0.9)
    result = enforce_patch_candidate_grounding(block, SAMPLE_SOURCE)

    assert result.is_grounded is True
    assert "rejected" not in block["patch_candidate"]
    assert block["patch_plan"] == plan        # preserved
    assert block["confidence"] == 0.9          # untouched
    assert block["issues"] == []               # no warning added
    assert block["needs_escalation"] is False


def test_enforce_does_not_create_patch_plan_for_ungrounded_candidate():
    """Test 5: an ungrounded candidate never yields a patch_plan."""
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"), patch_plan=None)
    enforce_patch_candidate_grounding(block, SAMPLE_SOURCE)
    assert block["patch_plan"] is None


def test_enforce_warning_is_human_readable():
    """Test 6: the recorded warning reads like a clear sentence."""
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"))
    result = enforce_patch_candidate_grounding(block, SAMPLE_SOURCE)
    assert result.reason == UNGROUNDED_WARNING
    assert UNGROUNDED_WARNING.startswith("Rejected ungrounded patch candidate")
    assert "not found in source" in UNGROUNDED_WARNING


# --- live gate wiring (reject_ungrounded_candidate_quotes) ---------------

def _make_state(repo_path, json_block, control_result=None) -> AgentState:
    return AgentState(
        interface="cli",
        mode="reviewer",
        user_input="number customers from 2",
        file_paths=[],
        primary_file=None,
        input_mode="repo",
        language="python",
        task_type="patch",
        repo_path=str(repo_path) if repo_path is not None else None,
        project_tag="test",
        json_block=json_block,
        control_result=control_result,
    )


def test_live_gate_rejects_hallucinated_candidate_against_repo_file(tmp_path):
    (tmp_path / "report.py").write_text(SAMPLE_SOURCE, encoding="utf-8")
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"), confidence=0.9)
    state = _make_state(tmp_path, block)

    reject_ungrounded_candidate_quotes(state)

    assert state.json_block["patch_candidate"]["rejected"] is True
    assert state.json_block["patch_plan"] is None
    assert state.json_block["confidence"] < 0.9
    assert any(i.get("reason") == UNGROUNDED_WARNING for i in state.json_block["issues"])


def test_live_gate_preserves_valid_candidate_against_repo_file(tmp_path):
    (tmp_path / "report.py").write_text(SAMPLE_SOURCE, encoding="utf-8")
    block = _block(_candidate(ILOC_LINE, ILOC_FIX), confidence=0.9)
    state = _make_state(tmp_path, block)

    reject_ungrounded_candidate_quotes(state)

    assert "rejected" not in state.json_block["patch_candidate"]
    assert state.json_block["confidence"] == 0.9


def test_live_gate_grounds_against_retrieved_context_when_file_absent(tmp_path):
    # No report.py on disk — grounding must use retrieved CONTROL context.
    control = {"patch_intent": {"source_snippet": SAMPLE_SOURCE}}
    block = _block(_candidate(ILOC_LINE, ILOC_FIX), confidence=0.9)
    state = _make_state(tmp_path, block, control_result=control)

    reject_ungrounded_candidate_quotes(state)

    # iloc snippet is present in the retrieved context → grounded → preserved.
    assert "rejected" not in state.json_block["patch_candidate"]


def test_live_gate_rejects_when_absent_from_file_and_context(tmp_path):
    control = {"patch_intent": {"source_snippet": SAMPLE_SOURCE}}
    block = _block(_candidate(ENUMERATE_HALLUCINATION, "x"), confidence=0.9)
    state = _make_state(tmp_path, block, control_result=control)

    reject_ungrounded_candidate_quotes(state)

    assert state.json_block["patch_candidate"]["rejected"] is True
    assert state.json_block["patch_plan"] is None
