"""PATCH.MINIMAL.LIVE.2 — bounded local implementation novelty.

The measured claim these tests exist for is one sentence: ``safe_minimal``
rejected a *correct* fix for the T6 defect because the fix needed a loop
counter, and rejected it with the same reason it gives a new dependency.

So the file opens with the red half of the experiment — the shipped identifier
rule, reconstructed exactly, refusing the correct candidate — and closes with
the green half: the same bytes admitted, carried into the already-strong
DEFECT.PROBE.LIVE.4 matrix, and verified there.  Everything in between is the
proof that the widening is narrow: imports, definitions, signatures, globals,
nonlocals, attribute stores and novel members are rejected before and after,
and a candidate that mixes them with allowed local novelty stays rejected.

Nothing here fixes ``_classify_indent``.  The correct candidate is test-only,
lives in a disposable sandbox, and the last assertion of every T6 test is that
the real file is unchanged.
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

import core.pipeline as pipeline
import patching.patch_gates as patch_gates
from core.agent_state import AgentState
from core.behavioral_expectation import (
    SUBJECT_INDENTATION_STYLE,
    extract_behavioral_expectations,
)
from core.behavioral_matrix import (
    MATRIX_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE,
    ORDINARY_DEPTHS,
    build_behavioral_matrix,
    depth_only_depths,
    evaluate_behavioral_closure,
    indentation_depth_fixture,
)
from core.candidate_mutation_effect import (
    CANDIDATE_EFFECT_NO_OP,
    REASON_NO_OP_CANDIDATE,
    evaluate_candidate_mutation_effect,
)
from core.candidate_sandbox_validation import (
    patch_candidate_as_plan,
    patch_plan_fingerprint,
)
from core.candidate_verification import REJECTED, VERIFIED
from core.code_dna import _classify_indent
from core.defect_probe import (
    PROBE_REPRODUCED,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
from core.local_binding_novelty import (
    MAX_CHANGED_LINES,
    MAX_NOVEL_LOCAL_BINDINGS,
    MAX_TOUCHED_FUNCTIONS,
    NOVELTY_EXTERNAL_REFERENCE,
    NOVELTY_LOCAL_BINDING,
    NOVELTY_STRUCTURAL,
    PHASE_ID,
    REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY,
    REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED,
    REASON_MULTIPLE_FUNCTIONS_CHANGED,
    REASON_NOVEL_ATTRIBUTE_STORE,
    REASON_NOVEL_DEFINITION,
    REASON_NOVEL_EXTERNAL_REFERENCE,
    REASON_NOVEL_IMPORT,
    REASON_NOVEL_SCOPE_DECLARATION,
    REASON_SIGNATURE_CHANGE,
    REASON_UNPARSED_CANDIDATE,
    REASON_UNSUPPORTED_LANGUAGE,
    SHAPE_DEFINITION,
    SHAPE_FUNCTION_BODY_FRAGMENT,
    SHAPE_UNSUPPORTED,
    CandidateNoveltyClassification,
    classify_candidate_novelty,
    describe_candidate_novelty,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.patch_safety import evaluate_patch_safety
from core.phase_registry import load_phase_registry
from graph.schema import build_graph


ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The shipped function, read from the repository rather than retyped.
T6_TARGET = inspect.getsource(_classify_indent)

#: Its body, exactly as it ships.  The assertion below is this file's standing
#: guard that the phase did not repair the defect it is measuring.
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
    """One candidate for the exact live target, head and signature untouched."""

    return T6_TARGET.replace(T6_BODY, body)


# ═══════════════════════════════════════════════════════════════════════════
# §11 — the correct local-only candidate
# ═══════════════════════════════════════════════════════════════════════════
#
# It infers the base indentation *unit* as the running greatest common divisor
# of the observed leading-space widths, which is what the subject invariant
# actually says.  It counts the width with a loop rather than ``lstrip`` and
# accumulates the gcd in place rather than in a list, so it needs no novel
# member, no novel callable, no import and no new definition — only three
# bounded locals inside the existing function.
#
# Test-only.  It is never applied to production ``_classify_indent`` and never
# offered to a model.  INDENT.SEMANTICS.1's eight-case matrix rejects it on its
# two Python structural cases, so the proofs that need it to close the matrix
# declare the five-case oracle they were written against.
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

#: §22.B — the Round-7 inverted branch reorder.  No novel identifier at all.
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

#: §22.C — the Round-8 ceiling, expressed without ``lstrip`` so that it is
#: genuinely admitted by the widened gate.  It measures the real leading-space
#: width and recognises only a line indented by exactly one unit, so it answers
#: both ordinary cases and neither depth-only one.  This is the control that
#: matters most: local novelty buys eligibility, not correctness.
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

# ── §24 local good controls ────────────────────────────────────────────────
ONE_LOCAL_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    "        width = 0\n"
    '        if line.startswith("    "):\n'
    "            width = 4\n"
    '        elif line.startswith("  "):\n'
    "            width = 2\n"
    "        if width == 2:\n"
    '            counts["2space"] += 1\n'
    "        elif width == 4:\n"
    '            counts["4space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
LOOP_TARGET_BODY = (
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    "        width = 0\n"
    "        for ch in line:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        if width == 2:\n"
    '            counts["2space"] += 1\n'
    "        elif width == 4:\n"
    '            counts["4space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
COMPREHENSION_BODY = (
    "    counts = Counter()\n"
    "    widths = 0\n"
    "    for line in text.splitlines():\n"
    "        widths += len([ch for ch in line if ch == line[0]])\n"
    "    if widths:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
#: The same spelling bound in two scopes of one function is one novel local.
SHADOWING_BODY = (
    "    counts = Counter()\n"
    "    width = 0\n"
    "    for width in text.splitlines():\n"
    "        if width:\n"
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
#: §12 — four novel locals, one past the measured cap, and nothing else novel.
CAP_EXCEEDED_BODY = (
    "    counts = Counter()\n"
    "    unit = 0\n"
    "    seen = 0\n"
    "    for line in text.splitlines():\n"
    '        if not line or line[0] not in " \\t":\n'
    "            continue\n"
    "        width = 0\n"
    "        for ch in line:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        seen += width\n"
    "        while width:\n"
    "            unit, width = width, unit % width\n"
    "    if unit and seen:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

# ── §23 structural bad controls ────────────────────────────────────────────
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
NOVEL_FROM_IMPORT_BODY = (
    "    from math import gcd\n"
    "    counts = Counter()\n"
    "    unit = gcd(2, 4)\n"
    "    if unit:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
NESTED_FUNCTION_BODY = (
    "    def leading(value):\n"
    "        width = 0\n"
    "        for ch in value:\n"
    '            if ch != " ":\n'
    "                break\n"
    "            width += 1\n"
    "        return width\n"
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    "        if leading(line) == 2:\n"
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
LAMBDA_BODY = (
    "    counts = Counter()\n"
    "    measure = lambda value: len(value)\n"
    "    for line in text.splitlines():\n"
    "        if measure(line) == 2:\n"
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
GLOBAL_BODY = (
    "    global _INDENT_UNIT\n"
    "    _INDENT_UNIT = 2\n"
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    '        if line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
NONLOCAL_SOURCE = (
    "def outer(text):\n"
    "    unit = 0\n"
    "    def inner():\n"
    "        return unit\n"
    "    return inner()\n"
)
NONLOCAL_PATCHED = (
    "def outer(text):\n"
    "    unit = 0\n"
    "    def inner():\n"
    "        nonlocal unit\n"
    "        unit = 2\n"
    "        return unit\n"
    "    return inner()\n"
)
ATTRIBUTE_STORE_BODY = (
    "    counts = Counter()\n"
    "    counts.unit = 2\n"
    "    for line in text.splitlines():\n"
    '        if line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
NOVEL_CALLABLE_BODY = (
    "    counts = Counter()\n"
    "    widths = 0\n"
    "    for line in text.splitlines():\n"
    '        widths += len(line) - len(line.lstrip(" "))\n'
    "    if widths:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
SUBSCRIPT_MUTATION_BODY = (
    "    counts = Counter()\n"
    "    width = 0\n"
    "    for line in text.splitlines():\n"
    "        width += 1\n"
    '    counts["indent_unit"] = width\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
#: §14 — allowed local novelty may not carry forbidden novelty in with it.
MIXED_LOCAL_AND_IMPORT_BODY = (
    "    import statistics\n"
    "    counts = Counter()\n"
    "    width = 0\n"
    "    for line in text.splitlines():\n"
    "        width += 1\n"
    "    if statistics and width:\n"
    '        counts["2space"] += 1\n'
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §14 — two bounded locals plus a new public function, at definition level.
MIXED_LOCAL_AND_NEW_FUNCTION = _with_body(LOOP_TARGET_BODY) + (
    "\n\ndef indent_unit_of(text: str) -> int:\n"
    "    return 2\n"
)
#: §6 — same body, new parameter.
#: INDENT.RUNTIME.1 gave the live signature a keyword-only `language`
#: parameter; this still simulates a candidate that changes *that* signature
#: to something else, using whatever the live signature currently is rather
#: than a stale hardcoded string.
SIGNATURE_CHANGE_SOURCE = _with_body(LOOP_TARGET_BODY).replace(
    T6_TARGET.splitlines()[0],
    "def _classify_indent(text: str, default_unit: int = 2) -> Optional[str]:",
)


# ---------------------------------------------------------------------------
# The gate's own "already present" set, taken from the gate, never retyped
# ---------------------------------------------------------------------------


def _allowed_for(target: str, language: str = "python") -> set[str]:
    family = patch_gates._LANGUAGE_FAMILY_ALIASES.get(language, language)
    return (
        patch_gates._identifiers_in(target)
        | patch_gates._LANGUAGE_KEYWORDS
        | patch_gates._LANGUAGE_BUILTINS.get(family, set())
    )


def _novel_in(target: str, patched: str, language: str = "python") -> list[str]:
    """Exactly the lexical delta the shipped gate computes."""

    return sorted(
        patch_gates._identifiers_in(patched) - _allowed_for(target, language)
    )


def _classify(
    patched: str,
    *,
    target: str = T6_TARGET,
    language: str = "python",
    kind: str = "function",
    name: str = T6_TARGET_SYMBOL,
) -> CandidateNoveltyClassification:
    return classify_candidate_novelty(
        target_snippet=target,
        patched_snippet=patched,
        language=language,
        allowed_identifiers=_allowed_for(target, language),
        target_node_kind=kind,
        target_node_name=name,
    )


def _admits(patched: str, *, target: str = T6_TARGET, **kwargs) -> bool:
    classification = _classify(patched, target=target, **kwargs)
    return classification.admits(_novel_in(target, patched))


# ---------------------------------------------------------------------------
# The shipped gate, driven exactly as ``finalize_answer`` drives it
# ---------------------------------------------------------------------------


def _payload(patched: str, *, target: str = T6_TARGET) -> dict[str, Any]:
    return {
        "summary": "one candidate",
        "issues": [],
        "patch_candidate": {
            "file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_node_kind": "function",
            "target_node_name": T6_TARGET_SYMBOL,
            "target_snippet": target,
            "patched_snippet": patched,
        },
        "patch_plan": None,
        "confidence": 0.6,
        "needs_escalation": False,
    }


def _gate_state(block: dict[str, Any], language: str = "python") -> AgentState:
    state = AgentState(
        interface="agent",
        mode="reviewer",
        user_input=T6_QUERY,
        file_paths=[],
        primary_file=None,
        input_mode="terminal",
        language=language,
        task_type="bug_fix",
    )
    state.patch_style = "safe_minimal"
    state.task_info = {"intent": "bug_fix", "patch_style": "safe_minimal"}
    state.json_block = block
    return state


def _run_gate(patched: str, *, target: str = T6_TARGET, language: str = "python"):
    state = _gate_state(_payload(patched, target=target), language=language)
    patch_gates._enforce_safe_minimal(state)
    return state.json_block


def _gate_accepts(patched: str, **kwargs) -> bool:
    return _run_gate(patched, **kwargs).get("patch_candidate") is not None


# ---------------------------------------------------------------------------
# §35 — the pre-LIVE.2 rule, reconstructed rather than described
# ---------------------------------------------------------------------------


def _pre_live2_rule_rejects(patched: str, target: str = T6_TARGET) -> bool:
    """The shipped rule before this phase: any lexical delta is a rejection."""

    return bool(_novel_in(target, patched))


@pytest.fixture
def classifier_removed(monkeypatch):
    """Remove *only* the new classifier, leaving the rest of the gate alone.

    A classifier that reports every language unsupported is the honest way to
    switch this phase off: the gate keeps its new code path and still falls
    back to rejecting the whole delta, which is exactly the pre-LIVE.2 rule.
    """

    def _disabled(**kwargs):
        return CandidateNoveltyClassification(
            language=str(kwargs.get("language") or ""),
            language_supported=False,
            candidate_shape=SHAPE_UNSUPPORTED,
        )

    monkeypatch.setattr(patch_gates, "classify_candidate_novelty", _disabled)


# ═══════════════════════════════════════════════════════════════════════════
# §1 — the measured pre-change rejection
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(
    "body",
    [ONE_LOCAL_BODY, LOOP_TARGET_BODY, ROUND8_CEILING_BODY, CORRECT_LOCAL_ONLY_BODY],
)
def test_the_pre_live2_rule_rejected_every_purely_local_candidate(body):
    """§1/§3 — the measurement this phase starts from.

    None of these candidates reaches anything the original function did not
    already reach.  All four were rejected, and the correct one was rejected
    for the same reason as the rest.
    """

    assert _pre_live2_rule_rejects(_with_body(body)) is True


def test_the_pre_live2_reason_could_not_tell_a_counter_from_a_dependency():
    """§2 — one reason for two different kinds of novelty was the defect."""

    local = _novel_in(T6_TARGET, _with_body(CORRECT_LOCAL_ONLY_BODY))
    dependency = _novel_in(T6_TARGET, _with_body(NOVEL_IMPORT_BODY))
    assert local == ["ch", "unit", "width"]
    assert "statistics" in dependency
    # Under the old rule both are "identifiers not present in the source", and
    # the set arithmetic that produced them is identical.
    assert _pre_live2_rule_rejects(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert _pre_live2_rule_rejects(_with_body(NOVEL_IMPORT_BODY))


# ═══════════════════════════════════════════════════════════════════════════
# §38 — the classifier matrix
# ═══════════════════════════════════════════════════════════════════════════


def test_new_assignment_local_is_bounded_local_novelty():
    classification = _classify(_with_body(ONE_LOCAL_BODY))
    assert classification.bounded_local_novelty_allowed is True
    assert classification.primary_reason == REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
    assert sorted(classification.local_binding_names) == ["width"]
    (binding,) = classification.local_bindings
    assert binding.scope == T6_TARGET_SYMBOL
    assert binding.binding_kinds == ("assignment",)
    assert binding.load_count >= 1


def test_multiple_local_assignments_are_bounded_local_novelty():
    classification = _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert classification.bounded_local_novelty_allowed is True
    assert sorted(classification.local_binding_names) == ["ch", "unit", "width"]
    assert classification.containing_functions == (T6_TARGET_SYMBOL,)


def test_a_loop_target_is_a_local_binding():
    classification = _classify(_with_body(LOOP_TARGET_BODY))
    kinds = {
        item.name: item.binding_kinds for item in classification.local_bindings
    }
    assert kinds["ch"] == ("loop_target",)
    assert kinds["width"] == ("assignment",)
    assert classification.bounded_local_novelty_allowed is True


def test_a_comprehension_target_is_local_to_the_function_being_edited():
    classification = _classify(_with_body(COMPREHENSION_BODY))
    kinds = {
        item.name: item.binding_kinds for item in classification.local_bindings
    }
    assert kinds["ch"] == ("comprehension_target",)
    assert kinds["widths"] == ("assignment",)
    assert classification.bounded_local_novelty_allowed is True


def test_loads_of_a_newly_bound_local_are_part_of_the_same_novelty():
    """§5 — the load is admitted through the binding, never by spelling."""

    classification = _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    loads = {item.name: item.load_count for item in classification.local_bindings}
    assert loads["unit"] >= 2
    assert loads["width"] >= 2
    # The same spelling, loaded with nothing binding it, is not admitted.
    unbound = _with_body(
        "    counts = Counter()\n"
        "    if unit:\n"
        '        counts["2space"] += 1\n'
        "    return counts.most_common(1)[0][0] if counts else None\n"
    )
    assert _classify(unbound).bounded_local_novelty_allowed is False


def test_same_name_shadowing_is_one_deterministic_local():
    classification = _classify(_with_body(SHADOWING_BODY))
    names = sorted(classification.local_binding_names)
    assert names == ["width"]
    (binding,) = classification.local_bindings
    assert set(binding.binding_kinds) == {"assignment", "loop_target"}
    assert classification.bounded_local_novelty_allowed is True
    # Deterministic: the same input classifies identically every time.
    assert _classify(_with_body(SHADOWING_BODY)).as_dict() == {
        **classification.as_dict(),
        "novelty_fingerprint": classification.as_dict()["novelty_fingerprint"],
    }


def test_global_is_rejected():
    classification = _classify(_with_body(GLOBAL_BODY))
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_SCOPE_DECLARATION
    # §15 — a declared name is never reported as a local binding.
    assert "_INDENT_UNIT" not in classification.local_binding_names


def test_nonlocal_is_rejected():
    classification = classify_candidate_novelty(
        target_snippet=NONLOCAL_SOURCE,
        patched_snippet=NONLOCAL_PATCHED,
        language="python",
        allowed_identifiers=_allowed_for(NONLOCAL_SOURCE),
        target_node_kind="function",
        target_node_name="outer",
    )
    assert classification.bounded_local_novelty_allowed is False
    assert REASON_NOVEL_SCOPE_DECLARATION in classification.blocking_reasons


def test_an_attribute_store_is_not_a_local_binding():
    """§16 — inside a function is not the same as local to it."""

    classification = _classify(_with_body(ATTRIBUTE_STORE_BODY))
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_ATTRIBUTE_STORE
    assert "unit" not in classification.local_binding_names
    names = classification.novelty_classification()["attribute_store_novelty"]
    assert names["names"] == ["unit"]


def test_a_container_mutation_is_not_local_binding_novelty():
    """§17 — this phase is about identifier novelty, not mutation semantics."""

    classification = _classify(_with_body(SUBSCRIPT_MUTATION_BODY))
    # ``counts["indent_unit"] = width`` binds nothing: the only novel local is
    # ``width``, and the subscript store is left to the semantic verifiers.
    assert sorted(classification.local_binding_names) == ["width"]
    assert classification.bounded_local_novelty_allowed is True


def test_a_new_top_level_function_is_rejected():
    classification = _classify(MIXED_LOCAL_AND_NEW_FUNCTION)
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_DEFINITION


def test_a_nested_function_is_rejected():
    classification = _classify(_with_body(NESTED_FUNCTION_BODY))
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_DEFINITION


def test_a_lambda_is_rejected_as_an_executable_definition():
    classification = _classify(_with_body(LAMBDA_BODY))
    assert classification.bounded_local_novelty_allowed is False
    assert REASON_NOVEL_DEFINITION in classification.blocking_reasons


def test_a_signature_change_is_rejected():
    classification = _classify(SIGNATURE_CHANGE_SOURCE)
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_SIGNATURE_CHANGE


@pytest.mark.parametrize("body", [NOVEL_IMPORT_BODY, NOVEL_FROM_IMPORT_BODY])
def test_a_new_import_is_rejected(body):
    classification = _classify(_with_body(body))
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_IMPORT


def test_an_unresolved_novel_callable_is_rejected():
    """§9 — a local receiver does not make a novel member safe."""

    classification = _classify(_with_body(NOVEL_CALLABLE_BODY))
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_EXTERNAL_REFERENCE
    external = classification.novelty_classification()[
        "external_reference_novelty"
    ]
    assert "lstrip" in external["names"]


def test_mixed_allowed_and_forbidden_novelty_remains_rejected():
    """§14 — allowed local novelty cannot carry a dependency in with it."""

    classification = _classify(_with_body(MIXED_LOCAL_AND_IMPORT_BODY))
    assert "width" in classification.local_binding_names
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_NOVEL_IMPORT
    assert _gate_accepts(_with_body(MIXED_LOCAL_AND_IMPORT_BODY)) is False


def test_mixed_local_novelty_and_a_new_public_function_remains_rejected():
    classification = _classify(MIXED_LOCAL_AND_NEW_FUNCTION)
    assert classification.bounded_local_novelty_allowed is False
    assert _gate_accepts(MIXED_LOCAL_AND_NEW_FUNCTION) is False


def test_the_local_novelty_budget_is_enforced():
    """§12 — four bounded locals, nothing else novel, and still rejected."""

    classification = _classify(_with_body(CAP_EXCEEDED_BODY))
    assert len(classification.local_binding_names) == MAX_NOVEL_LOCAL_BINDINGS + 1
    assert classification.caps.binding_budget_exceeded is True
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED
    assert _gate_accepts(_with_body(CAP_EXCEEDED_BODY)) is False


def test_the_caps_are_the_measured_minimum_that_admits_the_positive_control():
    """§12 — the numbers come from measurement, not from taste."""

    assert (MAX_NOVEL_LOCAL_BINDINGS, MAX_TOUCHED_FUNCTIONS, MAX_CHANGED_LINES) == (
        3,
        1,
        24,
    )
    control = _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert control.caps.novel_local_bindings == MAX_NOVEL_LOCAL_BINDINGS
    assert control.caps.changed_lines <= MAX_CHANGED_LINES
    assert control.caps.exceeded is False


def test_two_touched_functions_are_rejected():
    """§25 — one existing function first."""

    two_functions = (
        "def first(text):\n"
        "    counts = 0\n"
        "    return counts\n"
        "\n\n"
        "def second(text):\n"
        "    counts = 0\n"
        "    return counts\n"
    )
    patched = (
        "def first(text):\n"
        "    counts = 0\n"
        "    width = 1\n"
        "    return counts + width\n"
        "\n\n"
        "def second(text):\n"
        "    counts = 0\n"
        "    depth = 1\n"
        "    return counts + depth\n"
    )
    classification = classify_candidate_novelty(
        target_snippet=two_functions,
        patched_snippet=patched,
        language="python",
        allowed_identifiers=_allowed_for(two_functions),
        target_node_kind="function",
        target_node_name="first",
    )
    assert classification.caps.touched_functions == 2
    assert classification.bounded_local_novelty_allowed is False
    assert REASON_MULTIPLE_FUNCTIONS_CHANGED in classification.blocking_reasons


# ── shapes and language coverage ───────────────────────────────────────────


def test_a_body_fragment_of_one_existing_function_is_supported():
    """The live T6 shape: a snippet that is a suite, not a definition."""

    classification = classify_candidate_novelty(
        target_snippet=T6_BODY,
        patched_snippet=CORRECT_LOCAL_ONLY_BODY,
        language="python",
        allowed_identifiers=_allowed_for(T6_BODY),
        target_node_kind="function",
        target_node_name=T6_TARGET_SYMBOL,
    )
    assert classification.candidate_shape == SHAPE_FUNCTION_BODY_FRAGMENT
    assert classification.containing_functions == (T6_TARGET_SYMBOL,)
    assert sorted(classification.local_binding_names) == ["ch", "unit", "width"]
    assert classification.bounded_local_novelty_allowed is True


def test_module_level_statements_are_not_a_supported_shape():
    """A novel name bound at column zero is a module binding, not a local."""

    classification = classify_candidate_novelty(
        target_snippet="VALUE = 1\n",
        patched_snippet="VALUE = 1\nUNIT = 2\n",
        language="python",
        allowed_identifiers=_allowed_for("VALUE = 1\n"),
        target_node_kind="function",
        target_node_name="anything",
    )
    assert classification.candidate_shape == SHAPE_UNSUPPORTED
    assert classification.bounded_local_novelty_allowed is False


def test_a_fragment_without_a_function_target_kind_is_not_widened():
    classification = classify_candidate_novelty(
        target_snippet=T6_BODY,
        patched_snippet=CORRECT_LOCAL_ONLY_BODY,
        language="python",
        allowed_identifiers=_allowed_for(T6_BODY),
        target_node_kind="class",
        target_node_name="Whatever",
    )
    assert classification.candidate_shape == SHAPE_UNSUPPORTED
    assert classification.bounded_local_novelty_allowed is False


def test_an_unparsable_candidate_fails_closed():
    classification = _classify("def _classify_indent(text:\n    return None\n")
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_UNPARSED_CANDIDATE


@pytest.mark.parametrize("language", ["javascript", "typescript", "go", "rust", ""])
def test_every_other_language_keeps_the_previous_conservative_rule(language):
    """§4/§7 — Python first, and no invented cross-language scope logic."""

    classification = classify_candidate_novelty(
        target_snippet="function f(a) { return a; }",
        patched_snippet="function f(a) { let width = 0; return a + width; }",
        language=language,
        allowed_identifiers={"function", "f", "a", "return", "let"},
        target_node_kind="function",
        target_node_name="f",
    )
    assert classification.language_supported is False
    assert classification.bounded_local_novelty_allowed is False
    assert classification.primary_reason == REASON_UNSUPPORTED_LANGUAGE


def test_python_aliases_all_reach_the_supported_classifier():
    for alias in ("py", "python", "Python", " PY "):
        classification = _classify(
            _with_body(ONE_LOCAL_BODY), language=alias.lower().strip()
        )
        assert classification.language_supported is True


# ═══════════════════════════════════════════════════════════════════════════
# §18/§19/§20 — the receipt
# ═══════════════════════════════════════════════════════════════════════════


def test_the_receipt_is_typed_bounded_and_free_of_ast_dumps():
    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    receipt = block["candidate_novelty_receipt"]
    assert receipt["phase_id"] == PHASE_ID
    assert receipt["bounded_local_novelty_allowed"] is True
    assert receipt["reason"] == REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
    classification = receipt["novelty_classification"]
    assert set(classification) == {
        "local_binding_novelty",
        "structural_novelty",
        "external_reference_novelty",
        "import_novelty",
        "scope_declaration_novelty",
        "attribute_store_novelty",
        "unresolved_novelty",
    }
    assert classification["local_binding_novelty"]["names"] == [
        "ch",
        "unit",
        "width",
    ]
    assert classification["local_binding_novelty"]["count"] == 3
    text = json.dumps(block)
    for forbidden in ("Module(", "FunctionDef(", "ast.", "confidence_score"):
        assert forbidden not in text
    # §18 — the receipt explains, it does not carry the candidate's source.
    assert CORRECT_LOCAL_ONLY_BODY not in text


def test_reasons_stay_semantically_separate():
    """§19 — every rejection names what it actually found."""

    observed = {}
    for label, patched in (
        (REASON_NOVEL_IMPORT, _with_body(NOVEL_IMPORT_BODY)),
        (REASON_NOVEL_DEFINITION, _with_body(NESTED_FUNCTION_BODY)),
        (REASON_SIGNATURE_CHANGE, SIGNATURE_CHANGE_SOURCE),
        (REASON_NOVEL_SCOPE_DECLARATION, _with_body(GLOBAL_BODY)),
        (REASON_NOVEL_ATTRIBUTE_STORE, _with_body(ATTRIBUTE_STORE_BODY)),
        (REASON_NOVEL_EXTERNAL_REFERENCE, _with_body(NOVEL_CALLABLE_BODY)),
        (REASON_LOCAL_NOVELTY_BUDGET_EXCEEDED, _with_body(CAP_EXCEEDED_BODY)),
    ):
        block = _run_gate(patched)
        assert block["patch_candidate"] is None
        observed[label] = block["issues"][0]["novelty_reason"]
    assert observed == {reason: reason for reason in observed}
    # Not collapsed back into one bucket.
    assert len(set(observed.values())) == len(observed)


def test_admission_grants_nothing(monkeypatch):
    """§20/§27 — eligibility for verification, and not one thing more."""

    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert block["patch_candidate"] is not None
    assert block["bounded_local_novelty_allowed"] is True
    for granted in (
        "human_review_eligible",
        "approval_ready",
        "execution_authorized",
        "write_authority",
        "candidate_review_ready",
        "auto_apply_allowed",
        "patch_application_authority",
    ):
        assert block.get(granted) in (None, False)
    assert block["candidate_novelty_model_calls"] == 0
    assert block["candidate_novelty_network_calls"] == 0
    assert block["candidate_novelty_repository_reads"] == 0
    assert block["candidate_novelty_repository_mutations"] == 0


def test_the_receipt_is_bound_to_one_exact_candidate_fingerprint():
    """§26 — the existing fingerprint primitive, and no second one."""

    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    expected = patch_plan_fingerprint(
        patch_candidate_as_plan(block["patch_candidate"])
    )
    assert block["candidate_novelty_candidate_fingerprint"] == expected
    assert len(expected) == 64


def test_a_refined_candidate_makes_the_classification_stale():
    """§26 — freshness is the pipeline's existing rule, reused unchanged."""

    state = _gate_state(_payload(_with_body(CORRECT_LOCAL_ONLY_BODY)))
    patch_gates._enforce_safe_minimal(state)
    assert state.json_block["candidate_novelty_admitted"] is True

    # The model refines the candidate after classification.
    state.json_block["patch_candidate"]["patched_snippet"] = _with_body(
        LOOP_TARGET_BODY
    )
    pipeline._drop_stale_candidate_validation(state)
    for key in pipeline._CANDIDATE_NOVELTY_KEYS:
        assert key not in state.json_block


def test_a_recorded_rejection_survives_the_candidate_it_removed():
    """The rejection is the reason there is no candidate; it is not stale."""

    state = _gate_state(_payload(_with_body(NOVEL_IMPORT_BODY)))
    patch_gates._enforce_safe_minimal(state)
    assert state.json_block["patch_candidate"] is None
    assert state.json_block["candidate_novelty_admitted"] is False
    pipeline._drop_stale_candidate_validation(state)
    assert state.json_block["candidate_novelty_reason"] == REASON_NOVEL_IMPORT


def test_describe_claims_nothing_beyond_eligibility():
    allowed = describe_candidate_novelty(
        _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    )
    assert "eligible for verification" in allowed
    assert "not been judged correct" in allowed
    blocked = describe_candidate_novelty(_classify(_with_body(NOVEL_IMPORT_BODY)))
    assert REASON_NOVEL_IMPORT in blocked
    for forbidden in ("approved", "authorized", "confidence"):
        assert forbidden not in (allowed + blocked).lower()


# ═══════════════════════════════════════════════════════════════════════════
# §34/§35 — the red/green experiment
# ═══════════════════════════════════════════════════════════════════════════


def test_red_green_the_same_correct_candidate_changes_verdict(classifier_removed):
    """§34 — with the classifier removed, the correct candidate is rejected."""

    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert block["patch_candidate"] is None


def test_green_the_same_correct_candidate_is_admitted():
    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert block["patch_candidate"] is not None
    assert block["candidate_novelty_admitted"] is True
    assert block["candidate_novelty_reason"] == (
        REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
    )


@pytest.mark.parametrize(
    "patched",
    [
        _with_body(NOVEL_IMPORT_BODY),
        _with_body(NESTED_FUNCTION_BODY),
        _with_body(NOVEL_CALLABLE_BODY),
        _with_body(GLOBAL_BODY),
        _with_body(ATTRIBUTE_STORE_BODY),
        SIGNATURE_CHANGE_SOURCE,
        MIXED_LOCAL_AND_NEW_FUNCTION,
        _with_body(MIXED_LOCAL_AND_IMPORT_BODY),
    ],
)
def test_negative_red_green_structural_novelty_is_rejected_both_ways(
    patched, monkeypatch
):
    """§35 — the widening is narrow: these never changed verdict."""

    assert _gate_accepts(patched) is False
    monkeypatch.setattr(
        patch_gates,
        "classify_candidate_novelty",
        lambda **kwargs: CandidateNoveltyClassification(
            language="python", language_supported=False
        ),
    )
    assert _gate_accepts(patched) is False


def test_the_gate_can_only_have_become_more_permissive():
    """Every candidate the old rule accepted, the new one accepts."""

    for patched in (
        T6_TARGET,
        _with_body(INVERTED_REORDER_BODY),
        _with_body(ONE_LOCAL_BODY),
        _with_body(CORRECT_LOCAL_ONLY_BODY),
        _with_body(NOVEL_IMPORT_BODY),
        _with_body(CAP_EXCEEDED_BODY),
    ):
        if not _pre_live2_rule_rejects(patched):
            assert _gate_accepts(patched) is True


# ═══════════════════════════════════════════════════════════════════════════
# §36 — the deterministic product smoke against the live T6 target
# ═══════════════════════════════════════════════════════════════════════════


def _t6_behavior_fact():
    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    (fact,) = facts
    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    return fact


def _t6_contract():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=T6_TARGET,
        candidate_eligible=True,
    )
    assert binding is not None
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_t6_behavior_fact()
    )
    assert contract is not None
    return contract


def _t6_plan(patched: str) -> list[dict[str, Any]]:
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert T6_TARGET in source
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": T6_TARGET,
            "patched_snippet": patched,
        }
    ]


@pytest.fixture(scope="module")
def t6_pre_probe():
    contract = _t6_contract()
    receipt = execute_defect_probe(contract, repo_path=ROOT)
    assert receipt.probe_result == PROBE_REPRODUCED
    return contract, receipt


def _t6_matrix(patched: str, t6_pre_probe, **kwargs):
    contract, pre = t6_pre_probe
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    assert safety.get("ok") is True
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    receipt = evaluate_behavioral_closure(
        repo_path=ROOT,
        candidate_plan=_t6_plan(patched),
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_behavior_fact(),
        **kwargs,
    )
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert receipt.closure.sandbox_only is True
    return receipt


def test_smoke_a_the_exact_no_op_never_reaches_the_widening():
    """§22.A/§36.A — PATCH.MINIMAL.LIVE.1 owns this one, unchanged."""

    effect = evaluate_candidate_mutation_effect(_t6_plan(T6_TARGET))
    assert effect.status == CANDIDATE_EFFECT_NO_OP
    assert effect.rejection_reason == REASON_NO_OP_CANDIDATE
    # And it carries no novel identifier at all, so the widened rule has
    # nothing to say about it either.
    assert _novel_in(T6_TARGET, T6_TARGET) == []


def test_smoke_b_the_inverted_reorder_is_shape_safe_and_matrix_rejected(
    t6_pre_probe,
):
    """§22.B/§36.B — unchanged in both halves."""

    patched = _with_body(INVERTED_REORDER_BODY)
    assert _novel_in(T6_TARGET, patched) == []
    assert _gate_accepts(patched) is True
    receipt = _t6_matrix(patched, t6_pre_probe)
    assert receipt.matrix_status == MATRIX_FIXED_BUT_REGRESSIVE


def test_smoke_c_the_round8_ceiling_is_admitted_and_still_matrix_rejected(
    t6_pre_probe,
):
    """§22.C/§36.C — the control that proves eligibility is not correctness."""

    patched = _with_body(ROUND8_CEILING_BODY)
    classification = _classify(patched)
    assert classification.bounded_local_novelty_allowed is True
    assert sorted(classification.local_binding_names) == ["ch", "indent"]
    assert _gate_accepts(patched) is True

    receipt = _t6_matrix(patched, t6_pre_probe)
    assert receipt.matrix_status != MATRIX_FIXED_AND_PRESERVED
    assert receipt.matrix_status == MATRIX_FIXED_BUT_REGRESSIVE


def test_smoke_d_the_correct_local_only_candidate_passes_gate_and_matrix(
    t6_pre_probe,
):
    """§34/§36.D — the primary stop-condition proof, first half.

    Against the matrix this phase was measured on.  INDENT.SEMANTICS.1's
    eight-case matrix rejects this candidate on its two Python structural
    cases, and no candidate the gate admits is known to close that matrix
    (tests/test_indent_semantics1.py), so the proof declares the five-case
    oracle through the one shared test helper.
    """

    from _matrix_history import live5_cases

    patched = _with_body(CORRECT_LOCAL_ONLY_BODY)
    assert _pre_live2_rule_rejects(patched) is True
    assert _gate_accepts(patched) is True

    contract, _pre = t6_pre_probe
    receipt = _t6_matrix(
        patched,
        t6_pre_probe,
        matrix_cases=live5_cases(
            build_behavioral_matrix(
                probe_contract=contract, behavior_fact=_t6_behavior_fact()
            )
        ),
    )
    assert receipt.matrix_status == MATRIX_FIXED_AND_PRESERVED
    assert (ROOT / T6_TARGET_FILE).read_bytes() == (
        ROOT / T6_TARGET_FILE
    ).read_bytes()


def test_the_correct_candidate_answers_all_four_matrix_cases_by_construction():
    """§21 — the behavioral matrix is authoritative, and this is why it passes."""

    namespace: dict[str, Any] = {}
    exec(  # noqa: S102 - test-only evaluation of a test-only candidate
        compile(
            "from collections import Counter\n"
            "from typing import Optional\n" + _with_body(CORRECT_LOCAL_ONLY_BODY),
            "<live2-positive-control>",
            "exec",
        ),
        namespace,
    )
    candidate = namespace[T6_TARGET_SYMBOL]
    cases = {
        "ordinary 2space": (indentation_depth_fixture(2, ORDINARY_DEPTHS), "2space"),
        "deep 2space": (
            indentation_depth_fixture(2, depth_only_depths(2, (2, 4))),
            "2space",
        ),
        "ordinary 4space": (indentation_depth_fixture(4, ORDINARY_DEPTHS), "4space"),
        "deep 4space": (
            indentation_depth_fixture(4, depth_only_depths(4, (2, 4))),
            "4space",
        ),
    }
    for label, (text, expected) in cases.items():
        assert candidate(text) == expected, label
    # The shipped function still gets two of the four wrong: not fixed here.
    assert _classify_indent(cases["ordinary 2space"][0]) == "4space"


# ── §36.D second half: the full read-only lifecycle ────────────────────────


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


def _t6_lifecycle_state(patched: str, pre_probe) -> AgentState:
    """A live-shaped state whose candidate has been through the real gate."""

    _contract, receipt = pre_probe
    state = AgentState(
        interface="agent",
        mode="planner",
        user_input=f"Fix this bug: {T6_QUERY}",
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
    # The real gate runs first, exactly as ``finalize_answer`` runs it.
    patch_gates._enforce_safe_minimal(state)
    state.repository_graph = _t6_graph()
    return state


@pytest.fixture(scope="module")
def t6_correct_lifecycle(t6_pre_probe, request):
    """Declared against the five-case oracle; see the §36.D smoke above."""

    from _matrix_history import pin_live5_indentation_matrix

    state = _t6_lifecycle_state(_with_body(CORRECT_LOCAL_ONLY_BODY), t6_pre_probe)
    original = pipeline.AUTO_PATCH_ENABLED
    pipeline.AUTO_PATCH_ENABLED = False
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    try:
        with pytest.MonkeyPatch.context() as history:
            pin_live5_indentation_matrix(history)
            pipeline.maybe_run_auto_patch(state, interactive=False)
    finally:
        pipeline.AUTO_PATCH_ENABLED = original
    after = (ROOT / T6_TARGET_FILE).read_bytes()
    return state, before, after


def test_smoke_d_the_correct_candidate_verifies_without_gaining_authority(
    t6_correct_lifecycle,
):
    """§36.D — admitted, matrix-passed, verified, and still not authorized."""

    state, before, after = t6_correct_lifecycle
    block = state.json_block

    assert block["candidate_novelty_admitted"] is True
    assert block["candidate_novelty_reason"] == (
        REASON_BOUNDED_LOCAL_IDENTIFIER_NOVELTY
    )
    assert block["patch_candidate"] is not None
    assert block["candidate_verification_status"] == VERIFIED

    # §28 — a wider candidate language is not mutation permission.
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False
    assert before == after


def test_the_real_classify_indent_is_untouched(t6_correct_lifecycle):
    """§0/§33 — this phase measures the defect; it does not repair it."""

    live = inspect.getsource(_classify_indent)
    assert live == T6_TARGET
    assert T6_BODY in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert CORRECT_LOCAL_ONLY_BODY not in (ROOT / T6_TARGET_FILE).read_text(
        encoding="utf-8"
    )
    assert "gcd" not in live
    assert _classify_indent(indentation_depth_fixture(2, ORDINARY_DEPTHS)) == "4space"


def test_a_locally_novel_candidate_cannot_bypass_the_behavioral_matrix(
    t6_pre_probe,
):
    """§21 — there is no path from admission to a verdict."""

    admitted = _with_body(ROUND8_CEILING_BODY)
    state = _t6_lifecycle_state(admitted, t6_pre_probe)
    assert state.json_block["candidate_novelty_admitted"] is True

    original = pipeline.AUTO_PATCH_ENABLED
    pipeline.AUTO_PATCH_ENABLED = False
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    try:
        pipeline.maybe_run_auto_patch(state, interactive=False)
    finally:
        pipeline.AUTO_PATCH_ENABLED = original

    block = state.json_block
    assert block["candidate_verification_status"] == REJECTED
    assert block["execution_authorized"] is False
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before


# ═══════════════════════════════════════════════════════════════════════════
# §33 — static boundaries, and the re-pin turned into a proof
# ═══════════════════════════════════════════════════════════════════════════

REVERSAL_FIXTURE = (
    ROOT / "tests" / "fixtures" / "patch_minimal_live2_safe_minimal_reversal.json"
)


def test_the_safe_minimal_re_pin_is_a_reversible_proof():
    """The old digest is reproducible from the shipped file, not asserted."""

    fixture = json.loads(REVERSAL_FIXTURE.read_text(encoding="utf-8"))
    path = ROOT / fixture["path"]
    post = before_harness_remediation(fixture["path"], path.read_bytes())
    assert hashlib.sha256(post).hexdigest() == fixture["post_sha256"]

    text = post.decode("utf-8")
    for hunk in fixture["hunks"]:
        assert text.count(hunk["post"]) == 1
        text = text.replace(hunk["post"], hunk["pre"])
    assert hashlib.sha256(text.encode("utf-8")).hexdigest() == fixture["pre_sha256"]


def test_only_the_safe_minimal_gate_moved_inside_patch_gates():
    """One of thirty-five top-level definitions changed, and it is the gate."""

    fixture = json.loads(REVERSAL_FIXTURE.read_text(encoding="utf-8"))
    # Bytes, not text: the file is CRLF and the stored hunks are too, so a
    # newline-normalising read would silently match nothing and "prove" that
    # nothing changed.
    post = before_harness_remediation(fixture["path"]).decode("utf-8")
    pre = post
    for hunk in fixture["hunks"]:
        pre = pre.replace(hunk["post"], hunk["pre"])

    def definitions(source: str) -> dict[str, str]:
        return {
            node.name: hashlib.sha256(ast.dump(node).encode("utf-8")).hexdigest()
            for node in ast.parse(source).body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }

    before, after = definitions(pre), definitions(post)
    assert set(before) == set(after)
    assert sorted(set(after) - set(before)) == fixture["added_top_level_definitions"]
    assert sorted(set(before) - set(after)) == (
        fixture["removed_top_level_definitions"]
    )
    assert len(before) == fixture["top_level_definitions"] == 35
    changed = sorted(name for name in before if before[name] != after[name])
    assert changed == fixture["changed_top_level_definitions"] == [
        "_enforce_safe_minimal"
    ]


@pytest.mark.parametrize(
    "fixture_name",
    [
        "defect_probe_live4_frozen_boundaries.json",
        "candidate_verify_live1_frozen_boundaries.json",
    ],
)
def test_every_other_frozen_boundary_file_is_byte_identical(fixture_name):
    """Historical §33 boundaries still reconstruct after authorized maintenance."""

    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / fixture_name).read_text(encoding="utf-8")
    )
    for rel, digest in fixture["files"].items():
        actual = hashlib.sha256(before_harness_remediation(rel)).hexdigest()
        assert actual == digest, rel


def test_this_phase_adds_no_model_network_subprocess_or_traversal_surface():
    """§29/§32 — the classifier is pure, and stdlib only."""

    source = before_harness_remediation("core/local_binding_novelty.py").decode("utf-8")
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module.split(".")[0])
    assert modules <= {
        "__future__",
        "ast",
        "dataclasses",
        "difflib",
        "hashlib",
        "json",
        "textwrap",
        "time",
        "typing",
    }
    # The import allowlist above is the real proof: none of ast, difflib,
    # hashlib, json, textwrap, time, dataclasses or typing can open a file, a
    # socket or a subprocess.  This adds the one thing an allowlist misses -
    # a builtin reached without an import.
    called = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert not (called & {"open", "exec", "eval", "compile", "input", "__import__"})

    # Prose may name what the module refuses to do; the code may not do it.
    for forbidden in ("requests", "httpx", "urllib", "os.walk", "run_gemini_request"):
        assert forbidden not in source


def test_classification_is_negligible_next_to_the_probes():
    """§32 — bounded snippets, parsed twice, and nothing else."""

    started = time.perf_counter()
    for _ in range(50):
        _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    elapsed = time.perf_counter() - started
    assert elapsed < 2.0
    single = _classify(_with_body(CORRECT_LOCAL_ONLY_BODY))
    assert single.classification_seconds < 0.5


# ═══════════════════════════════════════════════════════════════════════════
# Governance
# ═══════════════════════════════════════════════════════════════════════════


def test_the_registry_entry_is_present_and_honest():
    registry = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    phases = {entry["phase_id"]: entry for entry in registry["phases"]}
    phase = phases[PHASE_ID]
    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    for required in (
        "PATCH.MINIMAL.LIVE.1",
        "DEFECT.PROBE.LIVE.4",
        "CANDIDATE.VERIFY.LIVE.1",
        "OPS.PATCH.2",
        "PATCH.BASIS.LIVE.1",
        "CONTROL.LOCALIZE.LIVE.2",
        "RETRIEVE.LIVE.4",
    ):
        assert required in phase["prerequisites"]


def test_the_novelty_keys_are_owned_by_the_control_plane():
    """§31 — harness-authored telemetry, disjoint from the answer surface."""

    block = _run_gate(_with_body(CORRECT_LOCAL_ONLY_BODY))
    written = {key for key in block if key.startswith("candidate_novelty_")}
    written.add("bounded_local_novelty_allowed")
    assert written <= set(pipeline._CANDIDATE_NOVELTY_KEYS)
    for answer_key in ("summary", "issues", "patch_candidate", "confidence"):
        assert answer_key not in pipeline._CANDIDATE_NOVELTY_KEYS


def test_the_novelty_class_vocabulary_is_closed():
    classification = _classify(_with_body(NOVEL_CALLABLE_BODY))
    for finding in classification.findings:
        assert finding.novelty_class in {
            NOVELTY_LOCAL_BINDING,
            NOVELTY_STRUCTURAL,
            NOVELTY_EXTERNAL_REFERENCE,
            "import",
            "scope_declaration",
            "attribute_store",
            "unresolved",
        }


def test_there_is_no_identifier_allowlist_in_this_phase():
    """The stop condition's hard rule: no ``lstrip``, no T6 spellings.

    The module's own prose is allowed to name the Round-6 identifiers, because
    explaining the measurement is the point.  What may not exist is a *value*:
    no string constant the classifier can compare an identifier against, and no
    collection of identifier spellings anywhere in its executable code.
    """

    tree = ast.parse(
        (ROOT / "core" / "local_binding_novelty.py").read_text(encoding="utf-8")
    )
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            first = body[0] if body else None
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstrings.add(id(first.value))

    literals = {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    }
    for forbidden in (
        "lstrip",
        "stripped",
        "mode",
        "append",
        "space_widths",
        "_classify_indent",
        "width",
        "unit",
        "ch",
    ):
        assert forbidden not in literals, forbidden


@pytest.mark.parametrize("replacement", [
    'return f"{text}space"',
    'return rf"{text}space"',
    'return "unbound_literal_text"',
])
def test_python_string_prefixes_and_literal_text_are_not_identifiers(replacement):
    target = "def render(text):\n    return text\n"
    candidate = "def render(text):\n    " + replacement + "\n"
    assert _run_gate(candidate, target=target)["patch_candidate"] is not None


@pytest.mark.parametrize("replacement", [
    'return f"{new_remote_call(text)}"',
    'return f"{text.new_remote_method()}"',
    'return f"{text:{new_remote_width()}}"',
])
def test_python_formatted_expressions_cannot_hide_external_novelty(replacement):
    target = "def render(text):\n    return text\n"
    candidate = "def render(text):\n    " + replacement + "\n"
    assert _run_gate(candidate, target=target)["patch_candidate"] is None


@pytest.mark.parametrize("new_module", ["untrusted_api", "trusted_api.remote"])
def test_python_from_import_cannot_hide_a_new_module_behind_existing_alias(new_module):
    target = "def render(text):\n    from trusted_api import parse\n    return parse(text)\n"
    candidate = target.replace("from trusted_api import", "from " + new_module + " import")
    block = _run_gate(candidate, target=target)
    assert block["patch_candidate"] is None
    assert block["candidate_novelty_reason"] == REASON_NOVEL_IMPORT
