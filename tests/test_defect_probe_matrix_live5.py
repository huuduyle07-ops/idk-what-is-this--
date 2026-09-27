"""DEFECT.PROBE.LIVE.5 — distribution-skew indentation unit discrimination.

DEFECT.PROBE.LIVE.4 asks a candidate four bounded questions about one typed
indentation fact.  Round-9 measured a candidate that answers all four and still
does not infer the base indentation unit::

    for line in text.splitlines():
        stripped = line.lstrip('\\n\\r')
        if not stripped or stripped[0] not in " \\t":
            continue
        indent = len(stripped) - len(stripped.lstrip(" \\t"))
        if "\\t" in stripped[:indent]:
            counts["tab"] += 1
        elif indent % 4 == 0:
            counts["4space"] += 1
        elif indent % 2 == 0:
            counts["2space"] += 1

It votes on *absolute* widths.  Every LIVE.4 fixture happens to give the right
width family a majority, so the matrix closed.  A deterministic diagnostic found
the smallest shape where it does not: one line at one indentation unit and two
at two.  Positive widths ``[2, 4, 4]``, true unit ``2``, and a frequency count
that says ``4space`` two votes to one.

That is the measured ceiling this phase closes, and the fifth case is the whole
phase.  Nothing about probe execution, candidate authoring, ``safe_minimal``,
targeted validation or authority changes.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import core.behavioral_matrix as matrix_probe
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    extract_behavioral_expectations,
)
from core.behavioral_matrix import (
    BASELINE_REPRODUCED,
    BASELINE_SATISFIED,
    CANDIDATE_FIXED,
    CANDIDATE_PRESERVED,
    CANDIDATE_REGRESSED,
    CANDIDATE_STILL_REPRODUCED,
    MATRIX_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE,
    MATRIX_PARTIALLY_FIXED,
    MATRIX_PROVENANCE_EXPLICIT_USER,
    MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    MATRIX_STILL_REPRODUCED,
    REASON_DEFECT_CASE_NOT_CLOSED,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
    ROLE_PRIMARY_DEFECT,
    SKEW_DEPTHS,
    SUBJECT_SPACE_UNITS,
    behavioral_matrix_guardrails,
    build_behavioral_matrix,
    evaluate_behavioral_closure,
    indentation_skew_fixture,
    skew_consistent_units,
)
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
)
import core.candidate_verification as verification
from core.candidate_verification import (
    CONTRADICTING,
    COMPONENT_PAIRED_PROBE,
    REASON_SUBJECT_INVARIANT_NOT_CLOSED,
    REJECTED,
    VERIFIED,
    evaluate_candidate_verification,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.code_dna import _classify_indent
from core.defect_probe import (
    PROBE_REPRODUCED,
    _nested_indentation_fixture,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    execute_defect_probe,
)
import core.pipeline as live_pipeline
from core.candidate_mutation_effect import CANDIDATE_EFFECT_NO_OP
from core.paired_defect_probe import PAIRED_CHANGED_BUT_UNRESOLVED
from core.patch_safety import evaluate_patch_safety


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

    monkeypatch.setattr(live_pipeline, "_call_revision_provider", lambda _state, _prompt: "")

T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The five production case ids.  The four LIVE.4 ids are byte-identical to the
#: ones LIVE.4 shipped; the fifth is appended, never inserted, so no historical
#: case changes its id or its position.
CASE_PRIMARY = "indentation_style.primary.2space"
CASE_DEEP_DEFECT = "indentation_style.generalize.2space.deep"
CASE_PRESERVE = "indentation_style.preserve.4space"
CASE_DEEP_PRESERVE = "indentation_style.preserve.4space.deep"
CASE_SKEW = "indentation_style.generalize.2space.skew"
LIVE4_CASE_IDS = (CASE_PRIMARY, CASE_DEEP_DEFECT, CASE_PRESERVE, CASE_DEEP_PRESERVE)
LIVE5_CASE_IDS = LIVE4_CASE_IDS + (CASE_SKEW,)

#: §13 — the exact branch ordering that ships today, and the two known bad
#: candidates expressed against it, copied from the suites that measured
#: them so this phase replays the same bytes rather than similar ones.
T6_BASELINE_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
)
#: The Round-7 inverted reorder.  DEFECT.PROBE.LIVE.3 already rejects it.
T6_REORDERED_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
)
#: The Round-8 ceiling: it recognises a line indented by *exactly* one unit.
T6_CEILING_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    "            continue\n"
    '        indent = len(line) - len(line.lstrip(" "))\n'
    "        if indent == 2:\n"
    '            counts["2space"] += 1\n'
    "        elif indent == 4:\n"
    '            counts["4space"] += 1\n'
)

#: The whole loop body, so a candidate that replaces more than branches fits.
T6_CLASSIFIER_BODY = (
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

#: §10 — the exact Round-9 Candidate1 implementation substance, reconstructed
#: from the captured provider response rather than from its malformed revision
#: envelope.  It measures the real indentation width and then *votes on the
#: absolute width*, which is the ceiling: every LIVE.4 fixture gives the right
#: width family a majority and this one does not.
T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY = (
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
    "    return counts.most_common(1)[0][0] if counts else None\n"
)

#: §12 — the existing LIVE.4 positive control, reused verbatim.  This phase
#: invents no second algorithm: if the oracle is still satisfiable, it is this
#: candidate that satisfies it.  Test-only, never applied to production.
#: INDENT.SEMANTICS.1 reclassified it as the *legacy raw-width control*: it
#: reads continuation alignment and docstring interiors as indentation, so the
#: eight-case matrix rejects it.  This suite measures LIVE.5's own five-case
#: oracle (see ``_t6_live5_cases``), where it still records what it recorded.
T6_UNIT_INFERRING_BODY = (
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


# ---------------------------------------------------------------------------
# The live T6 subject — the same order LIVE.4 measures, never a stand-in
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


def _t6_binding():
    binding = build_probe_target_binding(
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        target_symbol=T6_TARGET_SYMBOL,
        source_snippet=inspect.getsource(_classify_indent),
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


def _t6_cases():
    return build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )


def _t6_live5_cases():
    """The five cases this phase shipped, as the production builder builds them.

    INDENT.SEMANTICS.1 appended three more.  The candidate measurements in
    this suite are measurements of *this* phase's oracle, so they run on its
    five; tests/test_indent_semantics1.py measures the same candidates on all
    eight.
    """

    from _matrix_history import live5_cases

    cases = live5_cases(_t6_cases())
    assert tuple(case.case_id for case in cases) == LIVE5_CASE_IDS
    return cases


def _t6_plan(target: str, patched: str) -> list[dict[str, Any]]:
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert target in source
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


def _t6_matrix(plan: list[dict[str, Any]], **kwargs):
    """Run the whole matrix for one candidate, guarding the real repository."""

    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    assert safety.get("ok") is True
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    receipt = evaluate_behavioral_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_behavior_fact(),
        **kwargs,
    )
    # Candidate bytes exist only in the disposable sandbox.  Guarded every run.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert receipt.closure.sandbox_only is True
    return contract, pre, receipt


@pytest.fixture(scope="module")
def t6_round9():
    """§10 — the reconstructed Round-9 absolute-width-voting candidate."""

    return _t6_matrix(
        _t6_plan(T6_CLASSIFIER_BODY, T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY),
        matrix_cases=_t6_live5_cases(),
    )


@pytest.fixture(scope="module")
def t6_unit_inferring():
    """§12 — the legacy raw-width control, measured against five cases."""

    return _t6_matrix(
        _t6_plan(T6_CLASSIFIER_BODY, T6_UNIT_INFERRING_BODY),
        matrix_cases=_t6_live5_cases(),
    )


def _case_map(receipt) -> dict[str, Any]:
    return {item.case_id: item for item in receipt.cases}


def _positive_widths(text: str) -> list[int]:
    return [
        len(line) - len(line.lstrip(" "))
        for line in text.splitlines()
        if line.startswith(" ")
    ]


def _skew_fixture_of(cases) -> str:
    by_id = {case.case_id: case for case in cases}
    (fixture,) = by_id[CASE_SKEW].contract.structured_input["args"]
    return fixture


# ═══════════════════════════════════════════════════════════════════════════
# §2/§7/§8 — one added case, appended, nothing renamed
# ═══════════════════════════════════════════════════════════════════════════


def test_the_five_live5_cases_lead_the_production_matrix_in_a_fixed_order():
    cases = _t6_cases()

    assert tuple(case.case_id for case in cases[:5]) == LIVE5_CASE_IDS
    assert tuple(case.role for case in cases[:5]) == (
        ROLE_PRIMARY_DEFECT,
        ROLE_DEFECT_GENERALIZATION,
        ROLE_PRESERVATION,
        ROLE_PRESERVATION_GENERALIZATION,
        ROLE_DEFECT_GENERALIZATION,
    )
    # §7 — five was this phase's whole set: no ratio ladder, no 1:3 or 1:4.
    # INDENT.SEMANTICS.1 appended three fixed preservation cases after them,
    # and eight is the whole set now.
    assert len(cases) == 8
    assert all(case.role == ROLE_PRESERVATION_GENERALIZATION for case in cases[5:])


def test_the_four_live4_cases_keep_their_ids_order_and_contract_bytes():
    """§8 — append, never rewrite.  The historical four are untouched."""

    cases = _t6_cases()

    assert tuple(case.case_id for case in cases[:4]) == LIVE4_CASE_IDS
    by_id = {case.case_id: case for case in cases}
    (primary_fixture,) = by_id[CASE_PRIMARY].contract.structured_input["args"]
    (preserve_fixture,) = by_id[CASE_PRESERVE].contract.structured_input["args"]
    assert primary_fixture == _nested_indentation_fixture(2)
    assert preserve_fixture == _nested_indentation_fixture(4)


def test_the_new_case_is_a_system_derived_defect_generalization():
    """§2 — the existing role already says what this is."""

    case = {item.case_id: item for item in _t6_cases()}[CASE_SKEW]

    assert case.case_id == CASE_SKEW
    assert case.role == ROLE_DEFECT_GENERALIZATION
    assert case.provenance == MATRIX_PROVENANCE_SUBJECT_INVARIANT
    assert case.expected == "2space"
    assert case.subject_kind == SUBJECT_INDENTATION_STYLE
    # §33 — a non-primary case can never claim the user said it.
    assert case.provenance != MATRIX_PROVENANCE_EXPLICIT_USER


# ═══════════════════════════════════════════════════════════════════════════
# §3/§4 — the fixture, and the structural proof that it is real source
# ═══════════════════════════════════════════════════════════════════════════


def test_the_skew_fixture_is_parseable_python_with_the_measured_shape():
    """§4 — every pinned property of the diagnostic fixture, asserted."""

    fixture = _skew_fixture_of(_t6_cases())
    widths = _positive_widths(fixture)

    ast.parse(fixture)
    assert widths == [2, 4, 4]
    assert min(widths) == 2
    assert 2 in widths
    assert widths.count(4) > widths.count(2)
    assert all(width % 2 == 0 for width in widths)
    assert max(widths) // 2 == 2
    assert len(widths) == 3
    # One line at depth one, two at depth two.
    assert [width // 2 for width in widths] == [1, 2, 2]
    # Nesting never changes by more than one level per adjacent step.
    depths = [0] + [width // 2 for width in widths]
    assert all(
        abs(later - earlier) <= 1 for earlier, later in zip(depths, depths[1:])
    )


def test_the_skew_fixture_is_real_nested_source_not_a_width_vector():
    """§3 — the bytes parse into actual nesting, at the actual depths."""

    fixture = _skew_fixture_of(_t6_cases())
    tree = ast.parse(fixture)

    (function,) = tree.body
    assert isinstance(function, ast.FunctionDef)
    (branch,) = function.body
    assert isinstance(branch, ast.If)
    assert len(branch.body) == 2
    assert all(isinstance(node, ast.Assign) for node in branch.body)
    assert [node.col_offset for node in branch.body] == [4, 4]
    assert branch.col_offset == 2


def test_the_skew_fixture_bytes_are_deterministic_and_carry_no_randomness():
    assert indentation_skew_fixture(2) == (
        "def level_0():\n"
        "  if level_1:\n"
        "    level_2 = 2\n"
        "    level_3 = 3\n"
    )
    assert indentation_skew_fixture(2) == indentation_skew_fixture(2)
    assert _skew_fixture_of(_t6_cases()) == indentation_skew_fixture(2)
    assert SKEW_DEPTHS == (0, 1, 2, 2)
    assert [case.contract.structured_input_json for case in _t6_cases()] == [
        case.contract.structured_input_json for case in _t6_cases()
    ]


def test_the_skew_generator_keeps_the_frozen_depth_arithmetic():
    """§3 — same ``width * depth`` arithmetic, statements instead of names."""

    for width in range(1, 9):
        fixture = indentation_skew_fixture(width)
        ast.parse(fixture)
        assert _positive_widths(fixture) == [width, width * 2, width * 2]


# ═══════════════════════════════════════════════════════════════════════════
# §5 — the expectation is derivable from the bounded source alone
# ═══════════════════════════════════════════════════════════════════════════


def test_only_one_vocabulary_unit_survives_the_skew_widths():
    """§5 — a 2-space witness excludes 4space, with nothing else consulted."""

    assert SUBJECT_SPACE_UNITS == (2, 4)
    # widths {2, 4}: a base unit must divide every width, and 4 does not
    # divide 2, so 2space is the only vocabulary value left.
    assert skew_consistent_units(2) == (2,)
    # widths {4, 8}: both 2 and 4 divide them, so the shape is genuinely
    # ambiguous and this phase refuses to make a required case out of it.
    assert skew_consistent_units(4) == (2, 4)


@pytest.mark.parametrize(
    "width, consistent",
    [
        (1, ()),
        (2, (2,)),
        (3, ()),
        (4, (2, 4)),
        (5, ()),
        (6, (2,)),
        (7, ()),
        (8, (2, 4)),
    ],
)
def test_the_derivability_rule_covers_the_whole_value_grammar(width, consistent):
    """§5 — the probe accepts widths 1-8, and only one of them is its own
    unique divisor inside the classification vocabulary.

    So exactly one claimed width earns a skew case, and that is a production
    rule rather than a property of the one fact T6 happens to carry.  Width 6
    is the instructive one: its widths are divisible by 2, so 2 survives, but
    the vocabulary cannot say ``6space`` at all - the case would have no
    expressible expected value and is omitted.
    """

    assert skew_consistent_units(width) == consistent
    assert (skew_consistent_units(width) == (width,)) == (width == 2)


def test_only_the_two_space_claim_earns_a_fifth_case():
    """§5/§6 — the same rule, measured through the production adapter."""

    # Every other width the grammar accepts keeps LIVE.4's four cases.
    assert skew_consistent_units(2) == (2,)
    assert [
        width for width in range(1, 9) if skew_consistent_units(width) == (width,)
    ] == [2]


def test_the_ambiguous_mirror_is_not_a_production_case(tmp_path):
    """§6 — the 4space mirror is a control, never a required case."""

    facts, _truncated = extract_behavioral_expectations(
        "4-space indentation is classified as 2-space"
    )
    (fact,) = facts
    assert fact.expected_value == "4space"
    contract = build_probe_contract_from_behavior_fact(
        target=_t6_binding(), behavior_fact=fact
    )
    assert contract is not None

    cases = build_behavioral_matrix(probe_contract=contract, behavior_fact=fact)

    assert [case.case_id for case in cases] == [
        "indentation_style.primary.4space",
        "indentation_style.generalize.4space.deep",
        "indentation_style.preserve.2space",
        "indentation_style.preserve.2space.deep",
        # INDENT.SEMANTICS.1's three fixed cases, the same for every fact.
        "indentation_style.preserve.4space.continuation",
        "indentation_style.preserve.4space.multiline_string",
        "indentation_style.preserve.tab.go",
    ]
    assert not any(case.case_id.endswith(".skew") for case in cases)


def test_the_mirror_shape_is_a_control_every_candidate_already_answers():
    """§32 — the optional mirror: widths [4, 8, 8], and nothing discriminates."""

    mirror = indentation_skew_fixture(4)

    assert _positive_widths(mirror) == [4, 8, 8]
    assert _classify_indent(mirror) == "4space"
    assert _run_body(T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY, mirror) == "4space"
    assert _run_body(T6_UNIT_INFERRING_BODY, mirror) == "4space"


def _run_body(body: str, text: str) -> Any:
    """Evaluate one candidate body in isolation, for the offline diagnostic."""

    source = inspect.getsource(_classify_indent).replace(T6_CLASSIFIER_BODY, body)
    assert body in source
    namespace: dict[str, Any] = {}
    exec(
        "from collections import Counter\nfrom typing import Optional\n" + source,
        namespace,
    )
    return namespace["_classify_indent"](text)


def test_the_original_scratch_diagnostic_reproduces_exactly():
    """§32 — the measurement this phase was derived from, pinned."""

    skew = indentation_skew_fixture(2)

    assert _positive_widths(skew) == [2, 4, 4]
    assert _classify_indent(skew) == "4space"
    assert _run_body(T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY, skew) == "4space"
    assert _run_body(T6_UNIT_INFERRING_BODY, skew) == "2space"


# ═══════════════════════════════════════════════════════════════════════════
# §9 — the baseline fails the new case, so it is a real defect case
# ═══════════════════════════════════════════════════════════════════════════


def test_the_baseline_reproduces_the_skew_case(t6_round9):
    _contract, _pre, receipt = t6_round9
    case = _case_map(receipt)[CASE_SKEW]

    assert case.baseline_status == BASELINE_REPRODUCED
    assert case.baseline_result == PROBE_REPRODUCED
    assert case.baseline_observed == "4space"
    assert case.expected == "2space"


def test_the_skew_case_is_a_defect_case_not_a_preservation_case(t6_round9):
    _contract, _pre, receipt = t6_round9
    case = _case_map(receipt)[CASE_SKEW]

    assert case.role == ROLE_DEFECT_GENERALIZATION
    assert case.candidate_status not in {CANDIDATE_PRESERVED, CANDIDATE_REGRESSED}
    # And the four LIVE.4 baselines are exactly what LIVE.4 measured.
    cases = _case_map(receipt)
    assert cases[CASE_PRIMARY].baseline_status == BASELINE_REPRODUCED
    assert cases[CASE_DEEP_DEFECT].baseline_status == BASELINE_REPRODUCED
    assert cases[CASE_PRESERVE].baseline_status == BASELINE_SATISFIED
    assert cases[CASE_DEEP_PRESERVE].baseline_status == BASELINE_SATISFIED


# ═══════════════════════════════════════════════════════════════════════════
# §10/§11/§31 — the Round-9 candidate, and the red/green proof
# ═══════════════════════════════════════════════════════════════════════════


def test_round9_candidate_still_passes_all_four_live4_cases(t6_round9):
    _contract, _pre, receipt = t6_round9
    cases = _case_map(receipt)

    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRIMARY].candidate_observed == "2space"
    assert cases[CASE_DEEP_DEFECT].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_DEEP_DEFECT].candidate_observed == "2space"
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_PRESERVE].candidate_observed == "4space"
    assert cases[CASE_DEEP_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_DEEP_PRESERVE].candidate_observed == "4space"


def test_round9_candidate_fails_the_skew_case(t6_round9):
    """§10 — the one case that rejects it, and the value it returned."""

    _contract, _pre, receipt = t6_round9
    case = _case_map(receipt)[CASE_SKEW]

    assert case.expected == "2space"
    assert case.candidate_observed == "4space"
    assert case.candidate_result == PROBE_REPRODUCED
    # The baseline returned 4space for this shape too, so the closed
    # vocabulary for "a defect case that remains incorrect" is the exact-same
    # wrong behavior rather than a changed one.
    assert case.candidate_status == CANDIDATE_STILL_REPRODUCED
    assert case.baseline_observed == "4space"


def test_round9_candidate_is_partially_fixed_not_fixed_and_preserved(t6_round9):
    """§11 — incomplete defect closure, and not a regression."""

    _contract, _pre, receipt = t6_round9

    assert receipt.matrix_status == MATRIX_PARTIALLY_FIXED
    assert receipt.matrix_status != MATRIX_FIXED_AND_PRESERVED
    assert receipt.matrix_status != MATRIX_FIXED_BUT_REGRESSIVE
    assert receipt.matrix_status != MATRIX_STILL_REPRODUCED
    assert receipt.closure_ready is False
    assert REASON_DEFECT_CASE_NOT_CLOSED in receipt.rejection_reasons
    assert f"{REASON_DEFECT_CASE_NOT_CLOSED}:{CASE_SKEW}" in receipt.rejection_reasons
    # Exactly one case is open, and it is the skew case.
    assert [
        reason
        for reason in receipt.rejection_reasons
        if reason.startswith(f"{REASON_DEFECT_CASE_NOT_CLOSED}:")
    ] == [f"{REASON_DEFECT_CASE_NOT_CLOSED}:{CASE_SKEW}"]
    # §11 — a legacy reader is narrowed with it, never told the pair closed.
    assert receipt.paired_status == PAIRED_CHANGED_BUT_UNRESOLVED
    assert receipt.defect_closure_status == CLOSURE_CHANGED_BUT_UNRESOLVED


def test_red_green_the_four_case_matrix_accepted_the_round9_candidate():
    """§31 — the primary proof, demonstrated rather than asserted.

    The same candidate bytes, the same contract, the same repository, the same
    one sandbox: under the four LIVE.4 cases it closes, and with the skew case
    appended it does not.  That difference is the whole phase.
    """

    plan = _t6_plan(T6_CLASSIFIER_BODY, T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY)
    live4_only = tuple(
        case for case in _t6_cases() if case.case_id in LIVE4_CASE_IDS
    )
    assert tuple(case.case_id for case in live4_only) == LIVE4_CASE_IDS

    # RED: the pre-LIVE.5 oracle is satisfied by a candidate that is wrong.
    _contract, _pre, old = _t6_matrix(plan, matrix_cases=live4_only)
    assert len(old.cases) == 4
    assert old.matrix_status == MATRIX_FIXED_AND_PRESERVED
    assert old.defect_closure_status == CLOSURE_FIXED
    assert old.closure_ready is True

    # GREEN: the same four cases still pass, the skew case does not, and the
    # matrix refuses closure.  This phase's own five, not the eight that
    # INDENT.SEMANTICS.1 runs today: the proof is four against five.
    _contract, _pre, new = _t6_matrix(plan, matrix_cases=_t6_live5_cases())
    cases = _case_map(new)
    assert len(new.cases) == 5
    for case_id in LIVE4_CASE_IDS:
        assert cases[case_id].candidate_status == (
            old.case(case_id).candidate_status
        ), case_id
    assert cases[CASE_SKEW].candidate_status == CANDIDATE_STILL_REPRODUCED
    assert new.matrix_status == MATRIX_PARTIALLY_FIXED
    assert new.closure_ready is False


# ═══════════════════════════════════════════════════════════════════════════
# §12 — the unit-inferring positive control
# ═══════════════════════════════════════════════════════════════════════════


def test_the_existing_positive_control_passes_all_five_cases(t6_unit_inferring):
    """§12 — the oracle has to open as well as close."""

    _contract, _pre, receipt = t6_unit_inferring
    cases = _case_map(receipt)

    assert [item.case_id for item in receipt.cases] == list(LIVE5_CASE_IDS)
    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_DEEP_DEFECT].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_DEEP_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_SKEW].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_SKEW].candidate_observed == "2space"
    assert [item.candidate_observed for item in receipt.cases] == [
        "2space",
        "2space",
        "4space",
        "4space",
        "2space",
    ]
    assert receipt.matrix_status == MATRIX_FIXED_AND_PRESERVED
    assert receipt.defect_closure_status == CLOSURE_FIXED
    assert receipt.rejection_reasons == ()
    assert receipt.closure_ready is True


def test_this_phase_invented_no_second_positive_control():
    """§12 — LIVE.4's control, reused byte-for-byte rather than re-derived."""

    from tests.test_defect_probe_matrix_live import (
        T6_UNIT_INFERRING_BODY as live4_control,
    )

    assert T6_UNIT_INFERRING_BODY == live4_control
    # §14 — and it is never applied to production.
    assert T6_UNIT_INFERRING_BODY not in (
        (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    )


# ═══════════════════════════════════════════════════════════════════════════
# §14 — the oracle inspects behavior, never implementation
# ═══════════════════════════════════════════════════════════════════════════


def test_the_matrix_never_inspects_candidate_implementation_text():
    """§14 — a weird implementation producing correct behavior may pass."""

    source = inspect.getsource(matrix_probe)
    for technique in (
        "gcd",
        "lstrip",
        "histogram",
        "divisor",
        "modulo",
        "most_common",
        "patched_snippet",
        "candidate_source",
    ):
        assert technique not in source, technique
    # Nothing in the module reads a candidate's bytes at all.
    forbidden = {"ast", "inspect", "compile", "exec", "eval", "tokenize"}
    assert not (forbidden & _referenced_names(matrix_probe))


def _referenced_names(module) -> set[str]:
    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.alias):
            names.add(node.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


def test_a_behaviorally_correct_but_unusual_candidate_is_not_penalized():
    """§14 — the oracle is behavior, so an odd spelling of it still passes."""

    odd = (
        "    counts = Counter()\n"
        "    seen = []\n"
        "    for line in text.splitlines():\n"
        '        if not line or line[0] not in " \\t":\n'
        "            continue\n"
        '        if line.startswith("\\t"):\n'
        '            counts["tab"] += 1\n'
        "            continue\n"
        "        column = 0\n"
        '        while column < len(line) and line[column] == " ":\n'
        "            column += 1\n"
        "        seen.append(column)\n"
        '    if counts["tab"] > len(seen):\n'
        '        return "tab"\n'
        "    if seen:\n"
        "        smallest = seen[0]\n"
        "        for value in seen:\n"
        "            if value < smallest:\n"
        "                smallest = value\n"
        "        for value in seen:\n"
        "            if value % smallest:\n"
        "                smallest = 1\n"
        '        return "2space" if smallest <= 2 else "4space"\n'
        '    return "tab" if counts["tab"] else None\n'
    )
    for width, expected in ((2, "2space"), (4, "4space")):
        assert _run_body(odd, indentation_skew_fixture(width)) == expected
        assert _run_body(odd, _nested_indentation_fixture(width)) == expected


# ═══════════════════════════════════════════════════════════════════════════
# §15/§18/§19/§20/§30 — cost, sandboxes, binding and locality
# ═══════════════════════════════════════════════════════════════════════════


def test_five_cases_still_use_exactly_one_candidate_sandbox(t6_round9, monkeypatch):
    """§18 — one applied sandbox for the whole matrix, skew case included."""

    _contract, _pre, receipt = t6_round9

    assert receipt.closure.sandbox_only is True
    assert receipt.closure.candidate_apply_status == "applied"
    # Four companion probes inside that one sandbox: the primary case's two
    # observations already exist and are never re-executed.
    assert len(receipt.closure.preservation_probe_receipts) == 4
    assert set(dict(receipt.closure.preservation_probe_receipts)) == {
        CASE_DEEP_DEFECT,
        CASE_PRESERVE,
        CASE_DEEP_PRESERVE,
        CASE_SKEW,
    }


def test_the_added_cost_is_one_baseline_probe_and_one_candidate_probe():
    """§30 — O(5 fixed cases), and the delta is exactly two probes."""

    calls: list[str] = []
    real = matrix_probe.execute_defect_probe

    def counting(contract, **kwargs):
        calls.append(str(kwargs.get("execution_stage") or "candidate"))
        return real(contract, **kwargs)

    live4_only = tuple(
        case for case in _t6_cases() if case.case_id in LIVE4_CASE_IDS
    )
    plan = _t6_plan(T6_CLASSIFIER_BODY, T6_UNIT_INFERRING_BODY)

    matrix_probe.execute_defect_probe = counting
    try:
        calls.clear()
        _t6_matrix(plan, matrix_cases=live4_only)
        four = len(calls)
        calls.clear()
        _t6_matrix(plan, matrix_cases=_t6_live5_cases())
        five = len(calls)
    finally:
        matrix_probe.execute_defect_probe = real

    # One added baseline probe; the candidate probes run through the closure
    # primitive, which the receipt counts separately.
    assert five - four == 1


def test_every_case_binds_to_the_same_candidate_and_probe(t6_round9):
    """§20 — no new fingerprint primitive, and the skew case shares them."""

    contract, _pre, receipt = t6_round9
    block = receipt.as_telemetry()["behavioral_matrix"]

    assert block["candidate_fingerprint"] == receipt.closure.candidate_fingerprint
    assert block["probe_fingerprint"] == receipt.closure.probe_fingerprint
    assert receipt.closure.probe_fingerprint == contract.fingerprint
    assert len({case.contract.target for case in _t6_cases()}) == 1
    # One distinct probe per production case: five of this phase's, and the
    # three INDENT.SEMANTICS.1 appended.
    assert len({case.contract.fingerprint for case in _t6_cases()}) == 8


def test_the_module_stays_local_with_no_model_network_or_traversal():
    """§15 — fully local and deterministic."""

    forbidden = {
        "requests",
        "httpx",
        "urllib",
        "socket",
        "subprocess",
        "walk",
        "rglob",
        "glob",
        "iterdir",
        "run_gemini_request",
        "run_deepseek_review",
        "call_model",
        "random",
        "hypothesis",
        "shuffle",
        "sample",
        "choice",
        "seed",
    }
    used = _referenced_names(matrix_probe)

    assert not (used & forbidden), sorted(used & forbidden)


def test_no_ratio_search_reached_production():
    """§7/§30 — a fixed shape, not a ladder."""

    source = inspect.getsource(matrix_probe)
    for term in ("ratio", "while True", "range(1, 9)", "itertools"):
        assert term not in source, term
    guardrails = behavioral_matrix_guardrails()
    assert guardrails["bounded_fixed_case_matrix"] is True
    assert guardrails["randomized_or_generated_cases"] is False
    assert guardrails["property_based_testing_added"] is False
    assert guardrails["distribution_skew_case_is_bounded_and_fixed"] is True


# ═══════════════════════════════════════════════════════════════════════════
# §25/§26 — candidate verification and authority
# ═══════════════════════════════════════════════════════════════════════════


def _verification_evidence(contract, pre, receipt) -> dict[str, Any]:
    """The evidence mapping the pipeline assembles, with this run's receipts.

    §25 — taken from DEFECT.PROBE.LIVE.4's own suite, so what is proved here is
    the existing integration consuming a five-case matrix, not a LIVE.5 path.
    """

    block = dict(receipt.as_telemetry())
    block.update(
        {
            "targeted_validation_status": "verified",
            "targeted_validation_category": "candidate_verified",
            "targeted_validation_candidate_fingerprint": (
                receipt.closure.candidate_fingerprint
            ),
            "check_oracle_assessment_status": "current",
            "sandbox_apply_status": "applied",
        }
    )
    return {
        "policy_profile": verification.PROFILE_GROUNDED_DEFECT_BOUNDED_EVIDENCE,
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "candidate_fingerprint": receipt.closure.candidate_fingerprint,
        "candidate_target_paths": [T6_TARGET_FILE],
        "patch_safety": {
            "ok": True,
            "candidate_fingerprint": receipt.closure.candidate_fingerprint,
        },
        "pre_probe": pre.as_dict(),
        "candidate_defect_closure": block,
        "targeted_validation": block,
        "oracle_assessment": block,
        "candidate_sandbox_validation": block,
    }


def test_candidate_verification_rejects_the_round9_candidate(t6_round9):
    """§25 — consumed through the existing LIVE.4 integration, no new branch."""

    contract, pre, receipt = t6_round9
    verdict, _limits = verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )

    assert verdict.component == COMPONENT_PAIRED_PROBE
    assert verdict.verdict == CONTRADICTING
    # The existing closed-vocabulary behavioral reason, unchanged.
    assert verdict.reason == REASON_SUBJECT_INVARIANT_NOT_CLOSED
    assert CASE_SKEW in verdict.detail

    result = evaluate_candidate_verification(
        _verification_evidence(contract, pre, receipt)
    )
    assert result.status == REJECTED
    assert result.verified is False
    assert result.review_ready is False
    assert REASON_SUBJECT_INVARIANT_NOT_CLOSED in result.rejection_reasons


def test_passing_all_five_cases_authorizes_nothing(t6_unit_inferring):
    """§26 — evidence is evidence.  Authority is unchanged."""

    _contract, _pre, receipt = t6_unit_inferring
    telemetry = receipt.as_telemetry()

    assert receipt.matrix_status == MATRIX_FIXED_AND_PRESERVED
    for key in (
        "write_authority",
        "execution_authorized",
        "approval_ready",
        "human_review_eligible",
        "final_repository_changed",
        "auto_apply_allowed",
    ):
        assert key not in telemetry, key
    assert telemetry["behavioral_matrix_authority_effect"] == "none"
    guardrails = behavioral_matrix_guardrails()
    for flag in (
        "write_authority_granted",
        "execution_authorized",
        "auto_apply_granted",
        "human_review_eligibility_granted",
        "model_called",
        "network_called",
        "repository_traversal_added",
        "safe_minimal_changed",
        "targeted_validation_budget_changed",
        "probe_execution_primitive_changed",
        "candidate_authoring_changed",
        "production_classifier_fixed",
    ):
        assert guardrails[flag] is False, flag


def test_the_positive_control_is_supporting_evidence_not_authority(
    t6_unit_inferring,
):
    """§12/§26 — the oracle stays satisfiable, and closure is not authority."""

    contract, _pre, receipt = t6_unit_inferring
    verdict, limits = verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )

    assert verdict.verdict == verification.SUPPORTING
    assert limits == ()
    # Supporting the *matrix* component is not a verdict on the candidate:
    # the end-to-end answer is the product smoke below, which runs the real
    # pipeline branch and still ends with no authority granted.


# ═══════════════════════════════════════════════════════════════════════════
# §34 — the product smoke: five candidates, five distinct rejections
# ═══════════════════════════════════════════════════════════════════════════


def _pipeline_run(monkeypatch, target: str, patched: str):
    """Drive the real ``maybe_run_auto_patch`` with mutation disabled.

    §34 — no provider call: the candidate is placed on the state exactly as
    CANDIDATE.VERIFY.LIVE.1's own suite places it, so what runs is the
    product path rather than a harness of this phase's own making.

    The product builds eight cases since INDENT.SEMANTICS.1.  These smokes
    measure this phase's five, declared through the one shared test helper;
    tests/test_indent_semantics1.py drives the same product path on all eight.
    """

    from _matrix_history import pin_live5_indentation_matrix
    from tests.test_candidate_verification import _t6_candidate, _t6_state

    pin_live5_indentation_matrix(monkeypatch)
    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
    monkeypatch.setattr(live_pipeline, 'AUTO_PATCH_ENABLED', False)
    state = _t6_state(_t6_candidate(target, patched), (contract, pre))
    before = (ROOT / T6_TARGET_FILE).read_bytes()
    live_pipeline.maybe_run_auto_patch(state, interactive=False)
    after = (ROOT / T6_TARGET_FILE).read_bytes()
    assert before == after
    return state.json_block


def test_smoke_the_unit_inferring_control_is_verified_and_authorizes_nothing(
    monkeypatch,
):
    """§34E — all five cases pass, verification verified, nothing authorized."""

    block = _pipeline_run(
        monkeypatch, T6_CLASSIFIER_BODY, T6_UNIT_INFERRING_BODY
    )

    assert block["behavioral_matrix_case_count"] == 5
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_AND_PRESERVED
    assert {
        case["case_id"]: case["candidate_status"]
        for case in block["behavioral_matrix_cases"]
    } == {
        CASE_PRIMARY: CANDIDATE_FIXED,
        CASE_DEEP_DEFECT: CANDIDATE_FIXED,
        CASE_PRESERVE: CANDIDATE_PRESERVED,
        CASE_DEEP_PRESERVE: CANDIDATE_PRESERVED,
        CASE_SKEW: CANDIDATE_FIXED,
    }
    assert block["candidate_verification_status"] == VERIFIED
    assert block["candidate_verification_rejection_reasons"] == []
    # §26 — and it authorized nothing.
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False
    assert block["auto_apply_allowed"] is False
    assert block["write_authority"] is False


def test_smoke_the_round9_candidate_is_rejected_for_the_skew_case(monkeypatch):
    """§34D — the new rejection, through the product path."""

    block = _pipeline_run(
        monkeypatch, T6_CLASSIFIER_BODY, T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY
    )

    assert block["behavioral_matrix_case_count"] == 5
    assert block["behavioral_matrix_status"] == MATRIX_PARTIALLY_FIXED
    open_cases = [
        case["case_id"]
        for case in block["behavioral_matrix_cases"]
        if case["role"] == ROLE_DEFECT_GENERALIZATION
        or case["role"] == ROLE_PRIMARY_DEFECT
        if case["candidate_status"] != CANDIDATE_FIXED
    ]
    assert open_cases == [CASE_SKEW]
    assert block["candidate_verification_status"] == REJECTED
    assert REASON_SUBJECT_INVARIANT_NOT_CLOSED in (
        block["candidate_verification_rejection_reasons"]
    )
    assert block["candidate_review_ready"] is False
    assert block["execution_authorized"] is False
    assert block["final_repository_changed"] is False


def test_smoke_the_exact_no_op_never_reaches_the_matrix(monkeypatch):
    """§34A — earliest rejection: mutation effect, before any matrix work."""

    block = _pipeline_run(monkeypatch, T6_CLASSIFIER_BODY, T6_CLASSIFIER_BODY)

    assert block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert "behavioral_matrix" not in block
    assert "behavioral_matrix_cases" not in block
    assert block["execution_authorized"] is False


def test_smoke_the_inverted_reorder_is_rejected_for_preservation(monkeypatch):
    """§34B — a different rejection: preservation regression."""

    block = _pipeline_run(
        monkeypatch, T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES
    )

    assert block["behavioral_matrix_case_count"] == 5
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_BUT_REGRESSIVE
    regressed = [
        case["case_id"]
        for case in block["behavioral_matrix_cases"]
        if case["candidate_status"] == CANDIDATE_REGRESSED
    ]
    assert CASE_PRESERVE in regressed
    # The skew case is not what stops this one — it answers it correctly.
    skew = {
        case["case_id"]: case for case in block["behavioral_matrix_cases"]
    }[CASE_SKEW]
    assert skew["candidate_observed"] == "2space"
    assert block["candidate_verification_status"] == REJECTED
    assert block["execution_authorized"] is False


def test_smoke_the_round8_ceiling_is_rejected_for_the_depth_variants(monkeypatch):
    """§34C/§13 — a third rejection, and the separation is the diagnostic."""

    block = _pipeline_run(monkeypatch, T6_BASELINE_BRANCHES, T6_CEILING_BRANCHES)

    assert block["behavioral_matrix_case_count"] == 5
    cases = {
        case["case_id"]: case for case in block["behavioral_matrix_cases"]
    }
    # It classifies neither depth-only sample at all.
    assert cases[CASE_DEEP_DEFECT]["candidate_observed"] is None
    assert cases[CASE_DEEP_PRESERVE]["candidate_observed"] is None
    assert cases[CASE_DEEP_PRESERVE]["candidate_status"] == CANDIDATE_REGRESSED
    assert block["behavioral_matrix_status"] == MATRIX_FIXED_BUT_REGRESSIVE
    assert block["candidate_verification_status"] == REJECTED
    assert block["execution_authorized"] is False


def test_the_four_bad_candidates_fail_for_four_different_reasons(monkeypatch):
    """§13 — preserve the diagnostic separation, asserted as one table."""

    no_op = _pipeline_run(monkeypatch, T6_CLASSIFIER_BODY, T6_CLASSIFIER_BODY)
    reorder = _pipeline_run(
        monkeypatch, T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES
    )
    ceiling = _pipeline_run(
        monkeypatch, T6_BASELINE_BRANCHES, T6_CEILING_BRANCHES
    )
    round9 = _pipeline_run(
        monkeypatch, T6_CLASSIFIER_BODY, T6_ROUND9_ABSOLUTE_WIDTH_VOTING_BODY
    )

    # Four candidates, four distinct earliest causes.
    assert no_op["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert "behavioral_matrix_status" not in no_op
    assert reorder["behavioral_matrix_status"] == MATRIX_FIXED_BUT_REGRESSIVE
    assert ceiling["behavioral_matrix_status"] == MATRIX_FIXED_BUT_REGRESSIVE
    assert round9["behavioral_matrix_status"] == MATRIX_PARTIALLY_FIXED
    # And the two fixed_but_regressive ones regress *different* cases.
    def regressed(block):
        return {
            case["case_id"]
            for case in block["behavioral_matrix_cases"]
            if case["candidate_status"] == CANDIDATE_REGRESSED
        }

    assert regressed(reorder) != regressed(ceiling)
    assert CASE_PRESERVE in regressed(reorder)
    assert CASE_DEEP_PRESERVE in regressed(ceiling)
    assert CASE_PRESERVE not in regressed(ceiling)


# ═══════════════════════════════════════════════════════════════════════════
# §27/§28 — telemetry and phase visibility
# ═══════════════════════════════════════════════════════════════════════════


def test_the_existing_matrix_receipt_exposes_five_cases_and_no_second_subtree(
    t6_round9,
):
    """§27 — one canonical behavioral_matrix structure."""

    _contract, _pre, receipt = t6_round9
    telemetry = receipt.as_telemetry()
    block = telemetry["behavioral_matrix"]

    assert block["case_count"] == 5
    assert telemetry["behavioral_matrix_case_count"] == 5
    assert [case["case_id"] for case in block["cases"]] == list(LIVE5_CASE_IDS)
    # No duplicate subtree, and no LIVE.5-specific receipt beside it.
    matrix_keys = {
        key
        for key in telemetry
        if key.startswith("behavioral_matrix") or "skew" in key
    }
    assert "behavioral_matrix_live5" not in matrix_keys
    assert not any(key.endswith("_skew") for key in telemetry)
    assert sum(1 for key in telemetry if isinstance(telemetry[key], dict)) >= 1


def test_distribution_skew_discrimination_is_determinable_from_the_receipt(
    t6_round9,
):
    """§28 — a reader can tell the skew oracle was active, explicitly."""

    _contract, _pre, receipt = t6_round9
    block = receipt.as_telemetry()["behavioral_matrix"]

    # This phase's id is named, in order, after LIVE.4's.  INDENT.SEMANTICS.1
    # appended its own after it rather than replacing either.
    assert block["discrimination_phase_ids"][:2] == [
        "DEFECT.PROBE.LIVE.4",
        "DEFECT.PROBE.LIVE.5",
    ]
    assert block["discrimination_phase_ids"][2:] == ["INDENT.SEMANTICS.1"]
    assert block["phase_id"] == "DEFECT.PROBE.LIVE.4"
    # §28 — structural wire shape is unchanged for every field a pre-LIVE.5
    # reader consumed, so a stored LIVE.4 receipt is not reinterpreted.  This
    # phase did not bump the version; INDENT.SEMANTICS.1 did, because every
    # case record gained five semantic fields. PATCH.AUTHOR.LIVE.3 also
    # transports the bounded executed input and its probe fingerprint.
    assert block["schema_version"] == "behavioral_matrix_live_4_v2"
    live5_case_fields = {
        "case_id",
        "role",
        "provenance",
        "subject_kind",
        "expected",
        "baseline_observed",
        "baseline_result",
        "baseline_status",
        "candidate_observed",
        "candidate_result",
        "candidate_status",
        "reason",
    }
    for case in block["cases"]:
        assert set(case) - live5_case_fields == {
            "input_text",
            "case_probe_fingerprint",
            "input_language",
            "observation_tier",
            "claim_strength",
            "fallback_reason",
            "reference_assessment",
        }
        assert live5_case_fields <= set(case)
    rendered = json.dumps(receipt.as_telemetry(), ensure_ascii=False)
    for forbidden in ("confidence", "authority_to", "def _classify_indent", "gcd"):
        assert forbidden not in rendered


def test_cost_is_reported_by_stage_for_five_cases(t6_round9):
    """§30 — the same four timing stages, still bounded."""

    _contract, _pre, receipt = t6_round9

    assert set(receipt.timings) >= {
        "matrix_construction_sec",
        "matrix_baseline_sec",
        "matrix_candidate_probe_sec",
        "matrix_reduction_sec",
        "matrix_total_sec",
    }
    assert receipt.timings["matrix_construction_sec"] < 0.5
    assert receipt.timings["matrix_reduction_sec"] < 0.1


def test_answer_ground_leaves_the_new_case_and_phase_metadata_identical(
    t6_round9,
):
    """§29 — harness-authored state, byte/value-identical after grounding.

    The new case id, its status and its provenance, and the matrix phase
    metadata, are the harness's own facts.  ANSWER.GROUND.LIVE.4's display
    boundary recurses only into its answer-surface keys, so it must leave all
    of this exactly as measured - asserted here rather than assumed.
    """

    import copy

    from core.answer_entity_grounding import ground_state_answer

    _contract, _pre, receipt = t6_round9
    payload = receipt.as_telemetry()
    before = copy.deepcopy(payload)

    class _Terminal:
        repo_path = str(ROOT)
        user_input = T6_QUERY
        final_answer = json.dumps(payload, ensure_ascii=False)
        human_answer = T6_QUERY
        json_block = payload

    state = _Terminal()
    ground_state_answer(state)
    block = state.json_block

    # The whole matrix subtree survives value-identical.
    assert block["behavioral_matrix"] == before["behavioral_matrix"]
    assert block["behavioral_matrix_cases"] == before["behavioral_matrix_cases"]
    for key in (
        "behavioral_matrix_phase_id",
        "behavioral_matrix_schema_version",
        "behavioral_matrix_status",
        "behavioral_matrix_case_count",
        "behavioral_matrix_subject_kind",
        "behavioral_matrix_rejection_reasons",
        "behavioral_matrix_authority_effect",
    ):
        assert block[key] == before[key], key
    # And the new case specifically, field by field.
    skew = {
        case["case_id"]: case for case in block["behavioral_matrix_cases"]
    }[CASE_SKEW]
    assert skew["case_id"] == CASE_SKEW
    assert skew["role"] == ROLE_DEFECT_GENERALIZATION
    assert skew["provenance"] == MATRIX_PROVENANCE_SUBJECT_INVARIANT
    assert skew["candidate_status"] == CANDIDATE_STILL_REPRODUCED
    assert skew["expected"] == "2space"
    assert skew["candidate_observed"] == "4space"
    assert block["behavioral_matrix"]["discrimination_phase_ids"] == [
        "DEFECT.PROBE.LIVE.4",
        "DEFECT.PROBE.LIVE.5",
        # INDENT.SEMANTICS.1, appended after this phase's own id.
        "INDENT.SEMANTICS.1",
    ]


# ═══════════════════════════════════════════════════════════════════════════
# §23/§24/§29 — the frozen boundaries
# ═══════════════════════════════════════════════════════════════════════════


def _frozen() -> dict[str, Any]:
    path = ROOT / "tests" / "fixtures" / "defect_probe_live5_frozen_boundaries.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_frozen_collaborator_is_byte_identical():
    """§23/§24/§26/§29 — safe_minimal, budgets, probe execution, authority."""

    frozen = _frozen()
    assert frozen["phase_id"] == "DEFECT.PROBE.LIVE.5"

    from _harness_maintenance import before_harness_remediation

    # The explicitly requested harness remediation (2026-09-11) edited some of
    # these files after this phase froze them; its receipt undoes exactly those
    # edits, so the pin is checked against history and is never re-pinned.
    drifted = []
    for relative, digest in frozen["files"].items():
        actual = hashlib.sha256(before_harness_remediation(relative)).hexdigest()
        if actual != digest:
            drifted.append(f"{relative}: {digest} -> {actual}")
    assert not drifted, "frozen boundary drift:\n" + "\n".join(drifted)


def test_the_frozen_set_covers_the_boundaries_this_phase_promised():
    files = set(_frozen()["files"])

    for required in (
        "core/code_dna.py",
        "core/defect_probe.py",
        "core/defect_probe_worker.py",
        "core/candidate_defect_probe.py",
        "core/paired_defect_probe.py",
        "core/behavioral_expectation.py",
        "core/candidate_revision.py",
        "core/candidate_verification.py",
        "core/candidate_mutation_effect.py",
        "core/local_binding_novelty.py",
        "core/targeted_repository_validation.py",
        "core/execution_eligibility_policy.py",
        "core/live_execution_authorization.py",
        "core/human_apply_authorization.py",
        "core/answer_entity_grounding.py",
        "core/pipeline.py",
        "patching/patch_gates.py",
    ):
        assert required in files, required


def test_the_production_classifier_was_not_repaired():
    """§0 — LIVE.5 fixes an oracle, not ``_classify_indent``."""

    source = inspect.getsource(_classify_indent)

    assert 'elif line.startswith("    "):' in source
    assert '            counts["4space"] += 1' in source
    assert "gcd" not in source
    assert "space_widths" not in source
    # And it still misclassifies the skew sample, which is why the case exists.
    assert _classify_indent(indentation_skew_fixture(2)) == "4space"
    assert _classify_indent(_nested_indentation_fixture(2)) == "4space"


def test_the_only_production_change_is_the_matrix_module():
    """§16/§17 — one authoritative matrix builder, and the probe untouched.

    The reversal is shipped rather than claimed: applying the stored hunks to
    the file in the tree reproduces the pre-phase bytes, and that digest is the
    one PATCH.AUTHOR.LIVE.1 pinned before this phase existed.  So the re-pin
    below is a proof, not a bumped hash.
    """

    from _harness_maintenance import before_later_receipts

    reversal = _frozen()["behavioral_matrix"]
    # INDENT.SEMANTICS.1 edited this file after this phase shipped it.  Its
    # receipt, first in LATER_RECEIPTS, undoes exactly those edits and asserts
    # both digests, so this proof still runs on the bytes this phase shipped
    # and nothing here is re-pinned.
    shipped = before_later_receipts(
        reversal["path"], (ROOT / reversal["path"]).read_bytes()
    ).decode("utf-8")

    assert (
        hashlib.sha256(shipped.encode("utf-8")).hexdigest() == reversal["post_sha256"]
    )
    restored = shipped
    for hunk in reversal["hunks"]:
        assert restored.count(hunk["post"]) == 1, hunk["post"][:60]
        restored = restored.replace(hunk["post"], hunk["pre"])
    assert (
        hashlib.sha256(restored.encode("utf-8")).hexdigest() == reversal["pre_sha256"]
    )
    # The pre-phase digest is exactly what the previous phase froze.
    previous = json.loads(
        (
            ROOT / "tests" / "fixtures" / "patch_author_live1_frozen_boundaries.json"
        ).read_text(encoding="utf-8")
    )
    assert previous["behavioral_matrix_pre_live5_sha256"] == reversal["pre_sha256"]
    assert previous["files"]["core/behavioral_matrix.py"] == reversal["post_sha256"]

    # Three definitions added, none removed, three changed — and each of the
    # three for a reason this phase names.
    assert _top_level_names(restored) | set(reversal["added_definitions"]) == (
        _top_level_names(shipped)
    )
    assert reversal["added_definitions"] == [
        "_skew_contract",
        "indentation_skew_fixture",
        "skew_consistent_units",
    ]
    assert reversal["removed_definitions"] == []
    assert reversal["changed_definitions"] == [
        # the additive discrimination_phase_ids field
        "BehavioralMatrixReceipt",
        # the appended fifth case
        "_indentation_matrix_cases",
        # the three new guardrail flags
        "behavioral_matrix_guardrails",
    ]
    assert reversal["top_level_definitions_pre"] == 18
    assert reversal["top_level_definitions_post"] == 21
    # Every other frozen module is byte-identical, which the sibling test pins;
    # this one records that the matrix module is the *only* production change.
    assert "core/behavioral_matrix.py" not in _frozen()["files"]


def _top_level_names(source: str) -> set[str]:
    tree = ast.parse(source)
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


# ═══════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════


def test_the_phase_is_registered_with_its_measured_claim():
    from core.phase_registry import load_phase_registry

    data = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    by_id = {item["phase_id"]: item for item in data["phases"]}
    phase = by_id["DEFECT.PROBE.LIVE.5"]

    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["budget_tier"] == "local_only"
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    for prerequisite in (
        "DEFECT.PROBE.LIVE.4",
        "PATCH.AUTHOR.LIVE.1",
        "CANDIDATE.VERIFY.LIVE.1",
        "PATCH.MINIMAL.LIVE.2",
    ):
        assert prerequisite in phase["prerequisites"], prerequisite

    text = " ".join(phase["notes"] + [phase["summary"]]).lower()
    for term in (
        "distribution-skew",
        "indentation unit",
        "matrix",
        "system-derived",
        "no execution authority",
        "no model call",
        "no network call",
        "safe_minimal",
        "_classify_indent",
    ):
        assert term in text, term

    ids = {item["phase_id"] for item in data["phases"]}
    # PATCH.AUTHOR.LIVE.2 shipped on 2026-09-10 and took the revision envelope;
    # the next unused ids stand in for "has not shipped" now.
    assert "PATCH.AUTHOR.LIVE.2" in ids
    for forbidden_phase in ("PATCH.AUTHOR.LIVE.4", "DEFECT.PROBE.LIVE.6"):
        assert forbidden_phase not in ids


def test_the_revision_schema_bug_was_left_to_patch_author_live2():
    """§22 — two separate issues, kept separate, and separately owned.

    This phase reconstructed the Round-9 candidate's *substance* to measure it
    and deliberately did not touch its malformed *envelope*.  PATCH.AUTHOR.LIVE.2
    is the phase that owns the envelope, so the invariant is no longer "the file
    is untouched". Later phases have explicit reversal receipts. Reversing
    those and LIVE.2 must reproduce, byte for byte, what this phase pinned.
    """

    from core.phase_registry import load_phase_registry

    data = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    by_id = {item["phase_id"]: item for item in data["phases"]}
    owner = by_id["PATCH.AUTHOR.LIVE.2"]
    assert "core/candidate_revision.py" in owner["allowed_files"]
    assert "core/behavioral_matrix.py" in owner["forbidden_files"]

    live2 = json.loads(
        (
            ROOT / "tests" / "fixtures" / "patch_author_live2_contract_reversal.json"
        ).read_text(encoding="utf-8")
    )
    reversal = next(
        item
        for item in live2["reversals"]
        if item["path"] == "core/candidate_revision.py"
    )
    from _harness_maintenance import before_harness_remediation

    shipped = before_harness_remediation("core/candidate_revision.py").decode("utf-8")
    assert hashlib.sha256(shipped.encode("utf-8")).hexdigest() == reversal["post_sha256"]
    for hunk in reversal["hunks"]:
        assert shipped.count(hunk["post"]) == 1
        shipped = shipped.replace(hunk["post"], hunk["pre"])
    assert hashlib.sha256(shipped.encode("utf-8")).hexdigest() == (
        _frozen()["candidate_revision_pre_live2_sha256"]
    )
