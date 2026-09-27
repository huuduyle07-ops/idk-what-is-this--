"""PATCH.MINIMAL.LIVE.1 — exact no-op candidate rejection.

Round 7 authored a candidate whose ``patched_snippet`` was byte-identical to
its ``target_snippet``.  ``safe_minimal`` accepted it — correctly: it invented
no identifier and it was structurally tiny, and the existing no-op heuristic
looks for emptied/degenerate *bodies*, not for exact replacement equality.  The
read-only verification chain then spent roughly 3.65 s of candidate sandbox and
4.29 s of paired probe proving that identical bytes change nothing.

The invariant these tests pin is one line long: a patch candidate that changes
zero authoritative bytes is not a patch candidate.  It is checked before the
sandbox, before the paired probe, before targeted validation and before the
oracle, and it says nothing whatsoever about whether the model's diagnosis was
right.  Every byte-changing candidate — including the known semantically wrong
branch reorder — passes this gate untouched and is still judged by the existing
semantic verification pipeline.
"""

from __future__ import annotations

import ast
import copy
import inspect
import json
import time
from pathlib import Path
from typing import Any

import pytest

import core.candidate_mutation_effect as effect_module
import core.pipeline as pipeline
from core.agent_state import AgentState
from core.answer_entity_grounding import (
    _ANSWER_SURFACE_KEYS,
    RepositoryEntityEvidence,
    ground_answer_for_display,
)
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    extract_behavioral_expectations,
)
from core.candidate_mutation_effect import (
    CANDIDATE_EFFECT_LEGACY_UNMEASURED,
    CANDIDATE_EFFECT_MUTATING,
    CANDIDATE_EFFECT_NO_OP,
    CANDIDATE_EFFECT_NOT_APPLICABLE,
    CANDIDATE_EFFECT_STATUSES,
    OPERATION_EFFECT_EXACT_NO_OP,
    OPERATION_EFFECT_MUTATING,
    OPERATION_EFFECT_UNDETERMINED,
    OPERATION_EFFECTS,
    PHASE_ID,
    REASON_NO_OP_CANDIDATE,
    REJECTION_REASONS,
    candidate_effect_status_of_payload,
    describe_candidate_mutation_effect,
    evaluate_candidate_mutation_effect,
    reject_exact_no_op_candidate,
)
from core.candidate_sandbox_validation import (
    candidate_fingerprint_from_payload,
    patch_plan_fingerprint,
)
from core.candidate_verification import REJECTED
from core.code_dna import _classify_indent
from core.defect_probe import (
    PROBE_REPRODUCED,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.phase_registry import PHASE_ID_PREFIXES, load_phase_registry
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

#: §13 — the real Round-7 candidate.  Six ``_classify_indent`` lines, copied
#: verbatim from the CANDIDATE.VERIFY.LIVE.1 suite so all three phases measure
#: the same bytes.  The no-op candidate is this snippet on *both* sides.
T6_BASELINE_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
)
#: §14 — the known semantically *wrong* candidate.  Its bytes differ, so it
#: must survive this gate and be rejected by semantic verification instead.
T6_REORDERED_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
)
#: §15 — the deterministic width-distinguishing candidate that actually works.
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
    '        return "2space" if min(space_widths) <= 2 else "4space"\n'
    '    return "tab" if counts["tab"] else None\n'
)


# ── plan / payload helpers ──────────────────────────────────────────────────


def _op(path: str, target: str, patched: str) -> dict[str, Any]:
    return {
        "op": "replace_snippet",
        "relative_path": path,
        "target_snippet": target,
        "patched_snippet": patched,
    }


def _candidate(target: str, patched: str) -> dict[str, Any]:
    return {
        "file": T6_TARGET_FILE,
        "relative_path": T6_TARGET_FILE,
        "target_node_kind": "function",
        "target_node_name": T6_TARGET_SYMBOL,
        "target_snippet": target,
        "patched_snippet": patched,
    }


def _payload(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "target_source_grounded": True,
        "summary": "Reordered the indentation branches.",
        "confidence": 0.4,
        "needs_escalation": False,
        "patch_candidate": dict(candidate),
        "issues": [],
    }


def _effect_of(plan):
    return evaluate_candidate_mutation_effect(
        plan, candidate_fingerprint=patch_plan_fingerprint(plan)
    )


# ── live T6 state, the shape the pipeline actually assembles ────────────────


def _state(user_input: str = T6_QUERY) -> AgentState:
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


def _t6_behavior_fact():
    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    (fact,) = facts
    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    assert fact.provenance == PROVENANCE_EXPLICIT_USER_FACT
    return fact


def _t6_source_snippet() -> str:
    return inspect.getsource(_classify_indent)


@pytest.fixture(scope="module")
def t6_pre_probe():
    """The real pre-patch reproduction, measured once for every reader."""

    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=_t6_source_snippet(),
        candidate_eligible=True,
    )
    assert binding is not None
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_t6_behavior_fact()
    )
    assert contract is not None
    receipt = execute_defect_probe(contract, repo_path=ROOT)
    assert receipt.probe_result == PROBE_REPRODUCED
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


def _t6_state(candidate: dict[str, Any], pre_probe) -> AgentState:
    _contract, receipt = pre_probe
    state = _state()
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
    state.json_block = _payload(candidate)
    state.repository_graph = _t6_graph()
    return state


class _Counter:
    """Count reaching an expensive producer, then run the real one.

    Delegating rather than stubbing matters: the byte-changing control has to
    stay a genuine end-to-end run, so "the gate did not swallow it" and "the
    existing pipeline still judged it" are proved by the same execution.
    """

    def __init__(self, name: str, delegate: Any) -> None:
        self.name = name
        self.calls = 0
        self._delegate = delegate

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        self.calls += 1
        return self._delegate(*args, **kwargs)


#: The four producers §13 names, by the attribute ``core.pipeline`` calls them
#: through.  ``evaluate_behavioral_closure`` owns the exact-candidate sandbox
#: for a grounded-defect candidate — DEFECT.PROBE.LIVE.4 orchestrates the
#: bounded behavioral matrix through it and delegates to DEFECT.PROBE.LIVE.3's
#: ``evaluate_paired_defect_closure`` for a subject with no matrix, so counting
#: the entry point still counts every sandbox this route can create.
#: ``validate_candidate_in_sandbox`` is the explicit-change sibling and is
#: correctly idle on this route.
_PRODUCERS: dict[str, str] = {
    "candidate_sandbox": "validate_candidate_in_sandbox",
    "paired_probe": "evaluate_behavioral_closure",
    "targeted_validation": "validate_targeted_candidate",
    "oracle": "assess_selected_check_oracles",
}


@pytest.fixture
def producer_calls(monkeypatch):
    """Count every expensive read-only producer §13 says must not run."""

    counters: dict[str, _Counter] = {}
    for key, attribute in _PRODUCERS.items():
        counter = _Counter(attribute, getattr(pipeline, attribute))
        counters[key] = counter
        monkeypatch.setattr(pipeline, attribute, counter)
    return counters


# ═══════════════════════════════════════════════════════════════════════════
# §1/§2 — the primary invariant, exact bytes only
# ═══════════════════════════════════════════════════════════════════════════


def test_byte_identical_replacement_is_an_exact_no_op_operation():
    plan = [_op("core/calc.py", "return a - b\n", "return a - b\n")]

    result = _effect_of(plan)

    assert result.status == CANDIDATE_EFFECT_NO_OP
    assert result.operations[0].effect == OPERATION_EFFECT_EXACT_NO_OP
    assert result.exact_no_op_operation_count == 1
    assert result.mutating_operation_count == 0


def test_round7_no_op_candidate_is_rejected_as_an_exact_no_op():
    """§13 — the real Round-7 fixture: six identical ``_classify_indent`` lines."""

    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)]

    result = _effect_of(plan)

    assert result.exact_no_effect is True
    assert result.status == CANDIDATE_EFFECT_NO_OP
    assert result.rejection_reason == REASON_NO_OP_CANDIDATE
    assert result.candidate_accepted is False
    assert result.candidate_authored is True


def test_a_single_differing_byte_is_not_an_exact_no_op():
    plan = [_op("core/calc.py", "return a - b\n", "return a + b\n")]

    result = _effect_of(plan)

    assert result.exact_no_effect is False
    assert result.status == CANDIDATE_EFFECT_MUTATING
    assert result.rejection_reason == ""
    assert result.operations[0].effect == OPERATION_EFFECT_MUTATING


@pytest.mark.parametrize(
    "target, patched, label",
    [
        ("if x:\n    return 1\n", "if x:\n        return 1\n", "indentation"),
        ("return  a\n", "return a\n", "inner whitespace"),
        ("return a\n", "return a \n", "trailing space"),
        ("return a\n", "return a\r\n", "CRLF vs LF"),
        ("return a\r\n", "return a\n", "LF vs CRLF"),
        ("return a", "return a\n", "trailing newline"),
        ("return a\n", "return a\n\n", "extra blank line"),
    ],
)
def test_formatting_only_byte_deltas_are_not_exact_no_ops(target, patched, label):
    """§16 — byte-preserving semantics own these; the gate must not claim them."""

    result = _effect_of([_op("core/calc.py", target, patched)])

    assert result.exact_no_effect is False, label
    assert result.status == CANDIDATE_EFFECT_MUTATING, label
    assert result.mutating_operation_count == 1, label


def test_comment_only_delta_is_not_an_exact_no_op():
    result = _effect_of(
        [_op("core/calc.py", "return a - b\n", "return a - b  # fix\n")]
    )

    assert result.exact_no_effect is False


# ═══════════════════════════════════════════════════════════════════════════
# §4/§17 — multi-operation candidates
# ═══════════════════════════════════════════════════════════════════════════


def test_multi_file_candidate_with_every_operation_identical_is_a_no_op():
    plan = [
        _op("core/a.py", "x = 1\n", "x = 1\n"),
        _op("core/b.py", "y = 2\n", "y = 2\n"),
        _op("core/c.py", "z = 3\n", "z = 3\n"),
    ]

    result = _effect_of(plan)

    assert result.status == CANDIDATE_EFFECT_NO_OP
    assert result.exact_no_op_operation_count == 3
    assert result.mutating_operation_count == 0


def test_mixed_candidate_with_one_mutating_operation_continues():
    """§4 — real mutation effect exists, so the model's operations stand."""

    plan = [
        _op("core/a.py", "x = 1\n", "x = 1\n"),
        _op("core/b.py", "y = 2\n", "y = 3\n"),
    ]

    result = _effect_of(plan)

    assert result.status == CANDIDATE_EFFECT_MUTATING
    assert result.exact_no_op_operation_count == 1
    assert result.mutating_operation_count == 1
    assert result.rejection_reason == ""


def test_mixed_candidate_operations_are_neither_dropped_nor_reordered():
    """§4/§17 — this phase introduces no mixed-op rewrite policy."""

    plan = [
        _op("core/a.py", "x = 1\n", "x = 1\n"),
        _op("core/b.py", "y = 2\n", "y = 3\n"),
    ]
    block = _payload(_candidate("unused", "unused"))
    block.pop("patch_candidate")
    block["patch_plan"] = copy.deepcopy(plan)
    before = copy.deepcopy(block["patch_plan"])

    result = _effect_of(plan)
    reject_exact_no_op_candidate(block, result)

    assert block["patch_plan"] == before


def test_create_file_operation_is_a_mutation():
    """A created file changes repository bytes by construction."""

    result = _effect_of(
        [{"op": "create_file", "relative_path": "core/new.py", "content": ""}]
    )

    assert result.status == CANDIDATE_EFFECT_MUTATING
    assert result.operations[0].effect == OPERATION_EFFECT_MUTATING


def test_operation_without_both_byte_sides_is_undetermined_not_a_no_op():
    """§1 — the invariant only speaks where both byte sides are available."""

    result = _effect_of(
        [{"op": "replace_snippet", "relative_path": "core/a.py", "target_snippet": "x"}]
    )

    assert result.operations[0].effect == OPERATION_EFFECT_UNDETERMINED
    assert result.status == CANDIDATE_EFFECT_MUTATING
    assert result.exact_no_op_operation_count == 0


def test_no_candidate_at_all_is_not_applicable():
    result = _effect_of([])

    assert result.status == CANDIDATE_EFFECT_NOT_APPLICABLE
    assert result.candidate_authored is False
    assert result.rejection_reason == ""


# ═══════════════════════════════════════════════════════════════════════════
# §14/§15 — the two byte-changing positive controls
# ═══════════════════════════════════════════════════════════════════════════


def test_inverted_branch_reorder_candidate_passes_the_no_op_gate():
    """§14 — semantically wrong, but its bytes differ.  It must continue."""

    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)]

    result = _effect_of(plan)

    assert result.exact_no_effect is False
    assert result.status == CANDIDATE_EFFECT_MUTATING
    # The reorder is a permutation: same tokens, different bytes.
    assert sorted(T6_BASELINE_BRANCHES.split()) == sorted(
        T6_REORDERED_BRANCHES.split()
    )


def test_correct_width_distinguishing_candidate_passes_the_no_op_gate():
    """§15 — the candidate that actually fixes the defect is untouched."""

    plan = [
        _op(T6_TARGET_FILE, T6_DISTINGUISHING_TARGET, T6_DISTINGUISHING_PATCHED)
    ]

    result = _effect_of(plan)

    assert result.exact_no_effect is False
    assert result.status == CANDIDATE_EFFECT_MUTATING


# ═══════════════════════════════════════════════════════════════════════════
# §5/§7 — a closed reason that is not a semantic verdict
# ═══════════════════════════════════════════════════════════════════════════


def test_rejection_reason_vocabulary_is_closed():
    assert REASON_NO_OP_CANDIDATE in REJECTION_REASONS
    assert set(CANDIDATE_EFFECT_STATUSES) == {
        CANDIDATE_EFFECT_NOT_APPLICABLE,
        CANDIDATE_EFFECT_NO_OP,
        CANDIDATE_EFFECT_MUTATING,
    }
    assert set(OPERATION_EFFECTS) == {
        OPERATION_EFFECT_EXACT_NO_OP,
        OPERATION_EFFECT_MUTATING,
        OPERATION_EFFECT_UNDETERMINED,
    }


def test_the_reason_is_never_an_execution_or_semantic_verdict():
    """§5/§7 — nothing was executed, and the diagnosis was not judged."""

    source = Path(effect_module.__file__).read_text(encoding="utf-8")
    for forbidden in ("validation_failed", "probe_failed", "semantic_error"):
        assert f'"{forbidden}"' not in source
        assert f"'{forbidden}'" not in source

    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)]
    text = describe_candidate_mutation_effect(_effect_of(plan))
    assert "diagnosis" in text.lower()


def test_the_module_imports_no_io_model_or_network_dependency():
    """§3/§22 — stdlib only, and none of the stdlib that touches the world."""

    tree = ast.parse(Path(effect_module.__file__).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])

    assert imported == {"__future__", "dataclasses", "hashlib", "json", "time", "typing"}


def test_the_module_calls_nothing_that_reads_the_repository_or_the_network():
    """§3 — no traversal and no new repository scan to perform this check."""

    tree = ast.parse(Path(effect_module.__file__).read_text(encoding="utf-8"))
    called: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name):
            called.add(func.id)
        elif isinstance(func, ast.Attribute):
            called.add(func.attr)

    for forbidden in (
        "open",
        "read_text",
        "read_bytes",
        "write_text",
        "write_bytes",
        "run",
        "walk",
        "glob",
        "iterdir",
        "rglob",
    ):
        assert forbidden not in called, forbidden


# ═══════════════════════════════════════════════════════════════════════════
# §9/§10/§11 — what the rejected payload says
# ═══════════════════════════════════════════════════════════════════════════


@pytest.fixture
def rejected_payload():
    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)]
    block = _payload(_candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES))
    result = evaluate_candidate_mutation_effect(
        plan, candidate_fingerprint=candidate_fingerprint_from_payload(block)
    )
    reject_exact_no_op_candidate(block, result)
    return block, result


def test_rejected_payload_carries_no_usable_patch_candidate(rejected_payload):
    block, _ = rejected_payload

    assert block["patch_candidate"] is None
    assert block.get("patch_plan") in (None, [], ())


def test_rejected_payload_states_the_candidate_status(rejected_payload):
    block, _ = rejected_payload

    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert block["candidate_effect_rejection_reason"] == REASON_NO_OP_CANDIDATE
    assert block["candidate_effect_authored"] is True
    assert block["candidate_effect_accepted"] is False
    assert block["candidate_effect_phase_id"] == PHASE_ID


def test_rejected_payload_grants_no_review_or_approval(rejected_payload):
    """§9/§19 — a no-op can never be reviewable, approvable or authorized."""

    block, _ = rejected_payload

    assert block["human_review_eligible"] is False
    assert block["candidate_review_ready"] is False
    assert block["approval_ready"] is False
    assert block["needs_escalation"] is True
    assert block.get("write_authority", False) is False
    assert block.get("execution_authorized", False) is False
    assert block.get("final_repository_changed", False) is False


def test_rejected_payload_keeps_the_authored_bytes_visible_for_debugging(
    rejected_payload,
):
    """§10 — the model's output stays inspectable, just not usable."""

    block, _ = rejected_payload

    assert block["candidate_visible_for_debugging"] is True
    rejected = block["candidate_effect_rejected_candidate"]
    assert rejected[0]["target_snippet"] == T6_BASELINE_BRANCHES
    assert rejected[0]["patched_snippet"] == T6_BASELINE_BRANCHES


def test_rejected_payload_fabricates_no_verification_evidence(rejected_payload):
    """§11 — nothing ran, so nothing may be reported as having run."""

    block, _ = rejected_payload

    for fabricated in (
        "sandbox_apply_status",
        "candidate_validation_status",
        "post_probe_result",
        "paired_status",
        "targeted_validation_status",
        "check_oracle_assessment_status",
        "candidate_verification_status",
    ):
        assert fabricated not in block, fabricated


def test_rejected_payload_records_a_typed_issue(rejected_payload):
    block, _ = rejected_payload

    (issue,) = [
        item for item in block["issues"] if item.get("type") == "candidate_effect"
    ]
    assert issue["severity"] == "high"
    assert REASON_NO_OP_CANDIDATE in issue["reason"]


def test_rejection_does_not_relitigate_the_models_diagnosis(rejected_payload):
    """§7 — mutation effect and diagnosis correctness stay separate."""

    block, _ = rejected_payload

    assert block["confidence"] == 0.4
    assert block["summary"] == "Reordered the indentation branches."


def test_a_mutating_candidate_payload_is_left_alone():
    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)]
    block = _payload(_candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES))
    before = copy.deepcopy(block)

    reject_exact_no_op_candidate(block, _effect_of(plan))

    assert block == before


def test_legacy_payload_reads_back_as_unmeasured_never_as_mutating():
    assert candidate_effect_status_of_payload({}) == CANDIDATE_EFFECT_LEGACY_UNMEASURED
    assert candidate_effect_status_of_payload(None) == (
        CANDIDATE_EFFECT_LEGACY_UNMEASURED
    )


# ═══════════════════════════════════════════════════════════════════════════
# §12/§18 — binding and telemetry
# ═══════════════════════════════════════════════════════════════════════════


def test_telemetry_is_bound_to_the_exact_candidate_fingerprint(rejected_payload):
    block, result = rejected_payload
    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)]

    assert result.candidate_fingerprint == patch_plan_fingerprint(plan)
    assert block["candidate_effect_candidate_fingerprint"] == (
        result.candidate_fingerprint
    )


def test_telemetry_reports_the_operation_counts(rejected_payload):
    block, _ = rejected_payload

    assert block["exact_no_op_operation_count"] == 1
    assert block["mutating_operation_count"] == 0
    assert block["undetermined_operation_count"] == 0


def test_telemetry_carries_no_confidence_or_authority(rejected_payload):
    """§18 — no model confidence, no authority, no source dump."""

    block, _ = rejected_payload
    telemetry = {
        key: value
        for key, value in block.items()
        if key.startswith("candidate_effect_")
        or key.endswith("_operation_count")
    }
    rendered = json.dumps(telemetry, ensure_ascii=False)

    assert "confidence" not in rendered
    assert "authority" not in rendered
    receipt = json.dumps(block["candidate_effect_receipt"], ensure_ascii=False)
    assert "target_snippet" not in receipt
    assert "patched_snippet" not in receipt
    assert telemetry["candidate_effect_model_calls"] == 0
    assert telemetry["candidate_effect_network_calls"] == 0
    assert telemetry["candidate_effect_repository_reads"] == 0
    assert telemetry["candidate_effect_repository_mutations"] == 0


def test_receipt_fingerprint_is_deterministic_and_excludes_timing():
    plan = [_op(T6_TARGET_FILE, T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)]

    first = _effect_of(plan).as_dict()
    second = _effect_of(plan).as_dict()

    assert first["effect_fingerprint"] == second["effect_fingerprint"]
    assert "evaluation_seconds" not in first


# ═══════════════════════════════════════════════════════════════════════════
# §6/§13 — stage order in the live lifecycle
# ═══════════════════════════════════════════════════════════════════════════


def test_finalize_answer_rejects_the_round7_no_op_candidate():
    """§6/§8 — the gate runs with, and ahead of, the candidate-shape preflight."""

    state = _state()
    state.json_block = None
    candidate = _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)
    answer = "Here is the fix.\n```json\n" + json.dumps(_payload(candidate)) + "\n```"

    pipeline.finalize_answer(state, answer)

    assert state.json_block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert state.json_block["patch_candidate"] is None
    assert state.json_block["needs_escalation"] is True


def test_finalize_answer_leaves_a_byte_changing_candidate_alone():
    state = _state()
    state.json_block = None
    candidate = _candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES)
    answer = "Here is the fix.\n```json\n" + json.dumps(_payload(candidate)) + "\n```"

    pipeline.finalize_answer(state, answer)

    assert state.json_block["candidate_effect_status"] == CANDIDATE_EFFECT_MUTATING
    assert state.json_block["patch_candidate"]["patched_snippet"] == (
        T6_REORDERED_BRANCHES
    )
    assert state.json_block["needs_escalation"] is False


def test_no_op_candidate_runs_no_sandbox_probe_validation_or_oracle(
    monkeypatch, producer_calls, t6_pre_probe
):
    """§13 — the expensive chain is not entered to prove nothing changed."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES), t6_pre_probe
    )
    before = (ROOT / T6_TARGET_FILE).read_bytes()

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert producer_calls["candidate_sandbox"].calls == 0
    assert producer_calls["paired_probe"].calls == 0
    assert producer_calls["targeted_validation"].calls == 0
    assert producer_calls["oracle"].calls == 0
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before


def test_no_op_candidate_ends_the_run_with_no_authority(monkeypatch, t6_pre_probe):
    """§9/§19 — the terminal payload states the absence of every authority."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES), t6_pre_probe
    )

    pipeline.maybe_run_auto_patch(state, interactive=False)
    block = state.json_block

    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert block["candidate_effect_rejection_reason"] == REASON_NO_OP_CANDIDATE
    assert block["human_review_eligible"] is False
    assert block["candidate_review_ready"] is False
    assert block["approval_ready"] is False
    assert block["needs_escalation"] is True
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False


def test_no_op_candidate_user_facing_result_says_no_change_was_proposed(
    monkeypatch, t6_pre_probe
):
    """§10 — not "verified patch ready for review"."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES), t6_pre_probe
    )

    pipeline.maybe_run_auto_patch(state, interactive=False)

    assert "no repository change" in (state.auto_patch_result or "").lower()
    assert "ready" not in (state.auto_patch_result or "").lower()


def test_byte_changing_candidate_still_reaches_the_verification_producers(
    monkeypatch, producer_calls, t6_pre_probe
):
    """§14/§25 — the gate must not swallow candidates that do change bytes."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES), t6_pre_probe
    )

    pipeline.maybe_run_auto_patch(state, interactive=False)
    block = state.json_block

    # The grounded-defect route materializes its exact candidate inside the
    # paired probe; the explicit-change sandbox is correctly idle here.
    assert producer_calls["paired_probe"].calls == 1
    assert producer_calls["targeted_validation"].calls == 1
    assert block["candidate_probe_apply_status"] == "applied"


def test_no_op_rejection_is_effectively_free(monkeypatch, t6_pre_probe):
    """§21 — Round 7 spent ~3.65 s sandbox + ~4.29 s probe on this candidate."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES), t6_pre_probe
    )

    started = time.perf_counter()
    pipeline.maybe_run_auto_patch(state, interactive=False)
    elapsed = time.perf_counter() - started

    assert state.json_block["candidate_effect_evaluation_seconds"] < 0.1
    assert elapsed < 1.0


# ═══════════════════════════════════════════════════════════════════════════
# §14 — semantic verification still owns byte-changing candidates
# ═══════════════════════════════════════════════════════════════════════════


def test_known_wrong_reorder_candidate_is_still_semantically_rejected(
    monkeypatch, t6_pre_probe
):
    """§14 — this phase must NOT replace semantic candidate verification."""

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    state = _t6_state(
        _candidate(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES), t6_pre_probe
    )
    before = (ROOT / T6_TARGET_FILE).read_bytes()

    pipeline.maybe_run_auto_patch(state, interactive=False)
    block = state.json_block

    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_MUTATING
    assert block["candidate_verification_status"] == REJECTED
    assert block["human_review_eligible"] is False
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert _classify_indent("root\n  a\n    b\n      c\n    d\n  e\n") == "4space"


# ═══════════════════════════════════════════════════════════════════════════
# §20 — ANSWER.GROUND.LIVE.4 compatibility
# ═══════════════════════════════════════════════════════════════════════════


_EVIDENCE = RepositoryEntityEvidence(
    repository_id="cattus-repo",
    display_name="C.A.T.T.U.S",
    aliases=frozenset({"C.A.T.T.U.S"}),
    existing_paths=frozenset({"main.py", "core/candidate_mutation_effect.py"}),
    source_symbols=frozenset(
        {"core/candidate_mutation_effect.py::candidate"}
    ),
    analysis_paths=frozenset(),
    execution_paths=frozenset(),
    current=True,
)


def _ground(payload):
    import core.answer_entity_grounding as module

    original = module._state_repository_evidence
    module._state_repository_evidence = lambda _state: (_EVIDENCE,)
    try:
        return ground_answer_for_display(_state(), "", payload)
    finally:
        module._state_repository_evidence = original


def test_no_op_telemetry_keys_are_outside_the_answer_surface():
    """§20 — the new identifiers are harness-authored, not model claims."""

    for key in (
        "candidate_effect_phase_id",
        "candidate_effect_status",
        "candidate_effect_rejection_reason",
        "candidate_effect_candidate_fingerprint",
        "candidate_effect_receipt",
        "candidate_effect_rejected_candidate",
        "exact_no_op_operation_count",
        "mutating_operation_count",
        "undetermined_operation_count",
    ):
        assert key not in _ANSWER_SURFACE_KEYS, key


def test_no_op_telemetry_survives_answer_grounding_byte_identically(
    rejected_payload,
):
    """§20 — the reason/status must not become a fabricated repository entity."""

    block, _ = rejected_payload
    before = copy.deepcopy(block)

    _, _, display, _ = _ground(block)

    for key, value in before.items():
        if key in {"summary", "issues"}:
            continue
        assert display[key] == value, f"harness field {key!r} was mutated"
    assert display["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert display["candidate_effect_rejection_reason"] == REASON_NO_OP_CANDIDATE
    assert display["candidate_effect_receipt"]["phase_id"] == PHASE_ID


# ═══════════════════════════════════════════════════════════════════════════
# Governance
# ═══════════════════════════════════════════════════════════════════════════


def test_phase_is_registered_with_an_existing_prefix_and_track():
    data = load_phase_registry(str(REGISTRY))
    (phase,) = [
        item for item in data["phases"] if item["phase_id"] == "PATCH.MINIMAL.LIVE.1"
    ]

    assert phase["track"] == "CONTROL"
    assert "PATCH" in PHASE_ID_PREFIXES
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["human_approval_required"] is True
    for prerequisite in (
        "PATCH.BASIS.LIVE.1",
        "OPS.PATCH.2",
        "DEFECT.PROBE.LIVE.3",
        "CANDIDATE.VERIFY.LIVE.1",
        "ANSWER.GROUND.LIVE.4",
    ):
        assert prerequisite in phase["prerequisites"]
# ═══════════════════════════════════════════════════════════════════════════
# §24 — product smoke: the Round-7 T6 run, replayed without a provider call
# ═══════════════════════════════════════════════════════════════════════════


def test_round7_t6_product_smoke_replayed_deterministically(
    monkeypatch, producer_calls, t6_pre_probe
):
    """The whole Round-7 T6 chain, on the exact captured candidate bytes.

    Everything upstream of the candidate is real: the target binding, the
    behavioral fact extracted from the user's own words, and a defect probe
    that genuinely reproduces against ``core/code_dna.py``. Only the model call
    is replaced, by the candidate Round 7 actually authored.
    """

    contract, pre_receipt = t6_pre_probe

    # Target correct, behavioral fact correct, baseline probe already reproduced.
    assert contract.target.file == T6_TARGET_FILE
    assert contract.target.symbol == T6_TARGET_SYMBOL
    fact = _t6_behavior_fact()
    assert (fact.expected_value, fact.observed_value) == ("2space", "4space")
    assert pre_receipt.probe_result == PROBE_REPRODUCED

    monkeypatch.setattr(pipeline, "AUTO_PATCH_ENABLED", False)
    candidate = _candidate(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)
    state = _t6_state(candidate, t6_pre_probe)
    before = (ROOT / T6_TARGET_FILE).read_bytes()

    # Candidate authored: the payload really carries it going in.
    assert state.json_block["patch_candidate"]["patched_snippet"] == (
        state.json_block["patch_candidate"]["target_snippet"]
    )

    pipeline.maybe_run_auto_patch(state, interactive=False)
    block = state.json_block

    # Exact candidate effect: no_op.
    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert block["candidate_effect_rejection_reason"] == REASON_NO_OP_CANDIDATE

    # Rejected BEFORE sandbox, paired candidate probe, targeted validation and
    # oracle — none of them was entered.
    for name, counter in producer_calls.items():
        assert counter.calls == 0, name

    # No usable patch candidate, and no authority of any kind.
    assert block["patch_candidate"] is None
    assert block["needs_escalation"] is True
    assert block["human_review_eligible"] is False
    assert block["approval_ready"] is False
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False

    # The real repository is byte-identical and the defect is still there.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert _classify_indent("root\n  a\n    b\n      c\n    d\n  e\n") == "4space"
