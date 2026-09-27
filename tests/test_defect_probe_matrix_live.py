"""DEFECT.PROBE.LIVE.4 — depth-variant behavioral discrimination matrix.

The subject of these tests is one measured claim: a candidate may not be called
closed merely because it answers the two shapes the oracle happens to ask about.
The Round-8 ceiling candidate is the counter-example the phase exists for — it
passes the ordinary 2-space and 4-space cases and classifies neither sample
whose indentation begins below one indentation unit — and it appears here
verbatim, together with the red/green proof that the pre-LIVE.4 oracle accepted
it.
"""

from __future__ import annotations

import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import core.behavioral_matrix as matrix_probe
import core.candidate_verification as verification
import core.paired_defect_probe as paired_probe
import core.pipeline as pipeline
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    extract_behavioral_expectations,
)
from core.behavioral_matrix import (
    BASELINE_INCONCLUSIVE,
    BASELINE_REPRODUCED,
    BASELINE_SATISFIED,
    BASELINE_UNAVAILABLE,
    CANDIDATE_CHANGED_BUT_UNRESOLVED,
    CANDIDATE_FIXED,
    CANDIDATE_INCONCLUSIVE,
    CANDIDATE_PRESERVED,
    CANDIDATE_REGRESSED,
    CANDIDATE_STILL_REPRODUCED,
    CANDIDATE_UNAVAILABLE,
    CASE_ROLES,
    MATRIX_FIXED_AND_PRESERVED,
    MATRIX_FIXED_BUT_REGRESSIVE,
    MATRIX_INCONCLUSIVE,
    MATRIX_PARTIALLY_FIXED,
    MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION,
    MATRIX_PROVENANCE_SUBJECT_INVARIANT,
    MATRIX_STATUSES,
    MATRIX_STILL_REPRODUCED,
    MATRIX_UNAVAILABLE,
    MATRIX_UNRESOLVED_FAILURE,
    ORDINARY_DEPTHS,
    REASON_BASELINE_NOT_SATISFIED,
    REASON_CASE_NO_VERDICT,
    REASON_DEFECT_CASE_NOT_CLOSED,
    REASON_MATRIX_NOT_EXECUTED,
    REASON_PRESERVATION_REGRESSED,
    ROLE_DEFECT_GENERALIZATION,
    ROLE_PRESERVATION,
    ROLE_PRESERVATION_GENERALIZATION,
    ROLE_PRIMARY_DEFECT,
    BehavioralMatrixCase,
    MatrixCaseResult,
    ProbeObservation,
    behavioral_matrix_guardrails,
    build_behavioral_matrix,
    depth_only_depths,
    evaluate_behavioral_closure,
    indentation_depth_fixture,
    matrix_subject_supported,
    reduce_behavioral_matrix,
)
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
    CLOSURE_FIXED_BUT_REGRESSIVE,
)
from core.candidate_mutation_effect import (
    CANDIDATE_EFFECT_NO_OP,
    REASON_NO_OP_CANDIDATE,
    evaluate_candidate_mutation_effect,
)
from core.candidate_verification import (
    CONTRADICTING,
    COMPONENT_PAIRED_PROBE,
    REASON_PRIMARY_DEFECT_NOT_CLOSED,
    REASON_SUBJECT_INVARIANT_NOT_CLOSED,
    REJECTED,
    VERIFIED,
    evaluate_candidate_verification,
)
from core.code_dna import _classify_indent
from core.defect_probe import (
    EXPECTATION_BASIS_REPOSITORY_CONTRACT,
    INPUT_BASIS_REPOSITORY_CONTRACT,
    PROBE_BASIS_REPOSITORY_CONTRACT,
    PROBE_INCONCLUSIVE,
    PROBE_INVALID,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    PROBE_UNAVAILABLE,
    _nested_indentation_fixture,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    build_python_function_probe,
    execute_defect_probe,
)
from core.paired_defect_probe import (
    PAIRED_CHANGED_BUT_UNRESOLVED,
    PAIRED_FIXED,
    PAIRED_FIXED_AND_PRESERVED,
    PAIRED_FIXED_BUT_REGRESSIVE,
    PRESERVATION_PRESERVED,
    PRESERVATION_PROVENANCE,
    PRESERVATION_REGRESSED,
    evaluate_paired_defect_closure,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.patch_safety import evaluate_patch_safety


ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The exact branch ordering that ships today.
T6_BASELINE_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
)
#: The Round-7 branch-reorder candidate.  DEFECT.PROBE.LIVE.3 already rejects it.
T6_REORDERED_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
)
#: §13 — the Round-8 ceiling.  It stops testing prefixes in an order and
#: measures the real leading-space width, which is why it answers both ordinary
#: cases correctly; it recognises only a line indented by *exactly* one unit,
#: which is why it classifies neither depth-only sample at all.
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

#: The whole loop body, for the two candidates that replace more than branches.
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
#: §16 — this phase's positive control: the greatest common divisor of the
#: observed indentation widths.  INDENT.SEMANTICS.1 reclassified it as the
#: *legacy raw-width control*.  It reads every physical leading-space width,
#: continuation alignment and docstring interiors included, so the eight-case
#: matrix rejects it on the two Python structural cases.  It stays here, pinned
#: to the five cases it was measured against, as a record of earlier behavior
#: and not as oracle truth.  Test-only: §17 forbids applying it to production
#: ``_classify_indent`` and this phase does not make it available to any model.
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
#: DEFECT.PROBE.LIVE.3's own positive control: the *smallest* observed width.
#: It closed LIVE.3's two-point oracle, and it is exactly the candidate that
#: makes ``partially_fixed`` reachable from a real candidate rather than only
#: from a hand-built reduction — it never regresses anything and never closes
#: the depth-only defect case.
T6_MIN_WIDTH_BODY = (
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

CASE_PRIMARY = "indentation_style.primary.2space"
CASE_DEEP_DEFECT = "indentation_style.generalize.2space.deep"
CASE_PRESERVE = "indentation_style.preserve.4space"
CASE_DEEP_PRESERVE = "indentation_style.preserve.4space.deep"
#: DEFECT.PROBE.LIVE.5 appended a fifth case to the same production matrix.
#: These four keep their identifiers, their order and their semantics; the
#: assertions below are about them and are unchanged.
CASE_SKEW = "indentation_style.generalize.2space.skew"
#: INDENT.SEMANTICS.1 appended three fixed preservation cases after the skew
#: case.  Nothing below about the four LIVE.4 cases changes; the new cases'
#: own semantics are owned by tests/test_indent_semantics1.py.
CASE_CONTINUATION = "indentation_style.preserve.4space.continuation"
CASE_MULTILINE_STRING = "indentation_style.preserve.4space.multiline_string"
CASE_GO_TAB = "indentation_style.preserve.tab.go"
LIVE4_CASE_IDS = (
    CASE_PRIMARY,
    CASE_DEEP_DEFECT,
    CASE_PRESERVE,
    CASE_DEEP_PRESERVE,
)
REQUIRED_CASE_IDS = LIVE4_CASE_IDS + (
    CASE_SKEW,
    CASE_CONTINUATION,
    CASE_MULTILINE_STRING,
    CASE_GO_TAB,
)


# ---------------------------------------------------------------------------
# The live T6 subject
# ---------------------------------------------------------------------------


def _t6_behavior_fact() -> BehavioralExpectation:
    """The typed fact the live T6 order actually carries, not a hand-built one."""

    facts, truncated = extract_behavioral_expectations(T6_QUERY)
    assert truncated is False
    assert len(facts) == 1
    fact = facts[0]
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
        target=_t6_binding(),
        behavior_fact=_t6_behavior_fact(),
    )
    assert contract is not None
    return contract


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
    # §35 — candidate bytes exist only in the disposable sandbox, and every
    # case in the matrix reads them there.  Guarded on every T6 run.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert receipt.closure.sandbox_only is True
    return contract, pre, receipt


@pytest.fixture(scope="module")
def t6_ceiling():
    """§13 — the Round-8 two-point-passing candidate, measured once."""

    return _t6_matrix(_t6_plan(T6_BASELINE_BRANCHES, T6_CEILING_BRANCHES))


@pytest.fixture(scope="module")
def t6_reorder():
    """§14 — the known inverted reorder, measured once."""

    return _t6_matrix(_t6_plan(T6_BASELINE_BRANCHES, T6_REORDERED_BRANCHES))


@pytest.fixture(scope="module")
def t6_unit_inferring():
    """§16 — the legacy raw-width control, measured once on the five cases it
    was written against.  INDENT.SEMANTICS.1's two Python structural cases
    reject it; tests/test_indent_semantics1.py measures that verdict."""

    from _matrix_history import live5_cases

    return _t6_matrix(
        _t6_plan(T6_CLASSIFIER_BODY, T6_UNIT_INFERRING_BODY),
        matrix_cases=live5_cases(
            build_behavioral_matrix(
                probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
            )
        ),
    )


@pytest.fixture(scope="module")
def t6_min_width():
    """LIVE.3's positive control, which LIVE.4 measures as partially fixed."""

    return _t6_matrix(_t6_plan(T6_CLASSIFIER_BODY, T6_MIN_WIDTH_BODY))


def _case_map(receipt) -> dict[str, MatrixCaseResult]:
    return {item.case_id: item for item in receipt.cases}


# ═══════════════════════════════════════════════════════════════════════════
# §1/§5 — subject construction
# ═══════════════════════════════════════════════════════════════════════════


def test_exact_t6_fact_produces_the_four_bounded_cases_in_a_fixed_order():
    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )

    # This phase's four cases are the first four, in this phase's order, with
    # this phase's roles and expectations.  DEFECT.PROBE.LIVE.5 appended one.
    assert tuple(case.case_id for case in cases[:4]) == LIVE4_CASE_IDS
    assert tuple(case.role for case in cases[:4]) == (
        ROLE_PRIMARY_DEFECT,
        ROLE_DEFECT_GENERALIZATION,
        ROLE_PRESERVATION,
        ROLE_PRESERVATION_GENERALIZATION,
    )
    assert [case.expected for case in cases[:4]] == [
        "2space",
        "2space",
        "4space",
        "4space",
    ]
    # §2 — a bounded matrix, not coverage.  Eight is the whole set, and it is
    # still a fixed set: tests/test_defect_probe_matrix_live5.py owns the
    # fifth case's own semantics, tests/test_indent_semantics1.py the last
    # three's.
    assert len(cases) == 8
    assert tuple(case.case_id for case in cases) == REQUIRED_CASE_IDS


def test_matrix_construction_is_deterministic_and_carries_no_random_values():
    first = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    second = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )

    assert [case.contract.fingerprint for case in first] == [
        case.contract.fingerprint for case in second
    ]
    assert [case.as_dict() for case in first] == [case.as_dict() for case in second]
    # §2 — no generator, no sampler, no search.  Read from the parsed module
    # rather than its text, so the prose describing the rule cannot satisfy it.
    forbidden = {"random", "hypothesis", "shuffle", "sample", "choice", "seed"}
    used = _referenced_names(matrix_probe)
    assert not (used & forbidden), sorted(used & forbidden)


def _referenced_names(module) -> set[str]:
    import ast

    tree = ast.parse(inspect.getsource(module))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
        elif isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
            names.update(alias.name for alias in node.names)
    return names


def test_case_ids_are_stable_and_encode_nothing_incidental(t6_ceiling):
    _contract, _pre, receipt = t6_ceiling

    ids = [item.case_id for item in receipt.cases]
    assert ids == list(REQUIRED_CASE_IDS)
    # §21 — no temporary path, candidate fingerprint, timestamp or run id.
    fingerprint = receipt.closure.candidate_fingerprint
    for case_id in ids:
        assert fingerprint not in case_id
        assert "/" not in case_id and "\\" not in case_id
        assert case_id.startswith(f"{SUBJECT_INDENTATION_STYLE}.")


def test_only_the_primary_case_carries_the_users_own_provenance():
    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    primary, deep_defect, preserve, deep_preserve = cases[:4]

    # §4 — the user said one thing, and it is the primary case.
    assert primary.provenance == PROVENANCE_EXPLICIT_USER_FACT
    assert deep_defect.provenance == MATRIX_PROVENANCE_SUBJECT_INVARIANT
    assert deep_preserve.provenance == MATRIX_PROVENANCE_SUBJECT_INVARIANT
    # §4 compatibility — LIVE.3's own case keeps LIVE.3's own provenance.
    assert preserve.provenance == MATRIX_PROVENANCE_BEHAVIOR_PRESERVATION
    assert preserve.provenance == PRESERVATION_PROVENANCE
    for derived in (deep_defect, preserve, deep_preserve):
        assert derived.provenance != PROVENANCE_EXPLICIT_USER_FACT
        assert "not a user requirement" in derived.contract.provenance_reference


def test_a_derived_case_may_not_be_dressed_as_a_user_claim():
    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )

    with pytest.raises(ValueError, match="explicit user provenance"):
        BehavioralMatrixCase(
            case_id="forged",
            role=ROLE_DEFECT_GENERALIZATION,
            provenance=PROVENANCE_EXPLICIT_USER_FACT,
            subject_kind=SUBJECT_INDENTATION_STYLE,
            expected="2space",
            contract=cases[1].contract,
            derivation="forged",
        )


def test_unsupported_subject_and_untyped_transport_have_no_matrix():
    contract = _t6_contract()
    assert build_behavioral_matrix(probe_contract=contract, behavior_fact=None) == ()
    assert (
        build_behavioral_matrix(
            probe_contract=None, behavior_fact=_t6_behavior_fact()
        )
        == ()
    )
    assert matrix_subject_supported(SUBJECT_INDENTATION_STYLE) is True
    assert matrix_subject_supported("naming_convention") is False
    assert matrix_subject_supported("") is False

    fact = _t6_behavior_fact()
    unsupported = object.__new__(BehavioralExpectation)
    for name, value in (
        ("subject_kind", "naming_convention"),
        ("expected_value", "snake_case"),
        ("observed_value", "camelCase"),
        ("relation", fact.relation),
        ("provenance", fact.provenance),
        ("source_text", fact.source_text),
        ("source_start", 0),
        ("source_end", 1),
        ("obligation_ordinal", None),
        ("authoritative", True),
        ("schema_version", fact.schema_version),
    ):
        object.__setattr__(unsupported, name, value)
    assert (
        build_behavioral_matrix(probe_contract=contract, behavior_fact=unsupported)
        == ()
    )


def test_every_matrix_case_probes_the_primary_target_with_its_own_oracle():
    contract = _t6_contract()
    cases = build_behavioral_matrix(
        probe_contract=contract, behavior_fact=_t6_behavior_fact()
    )

    fingerprints = set()
    for case in cases:
        assert case.contract.target == contract.target
        assert case.contract.invocation_kind == contract.invocation_kind
        assert case.contract.side_effect_policy == contract.side_effect_policy
        assert case.contract.expected_behavior_basis == (
            contract.expected_behavior_basis
        )
        fingerprints.add(case.contract.fingerprint)
    # One distinct probe per case: a case identical to another proves the same
    # thing twice rather than something new.
    assert len(fingerprints) == len(cases)
    assert len(fingerprints) == 8
    assert cases[0].contract is contract


# ═══════════════════════════════════════════════════════════════════════════
# §6/§7 — fixtures
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize("width", [1, 2, 3, 4, 5, 6, 7, 8])
def test_the_depth_fixture_reproduces_the_frozen_generator_exactly(width):
    """§6 — one primitive, not a second fixture idea."""

    assert indentation_depth_fixture(width) == _nested_indentation_fixture(width)
    assert indentation_depth_fixture(width, ORDINARY_DEPTHS) == (
        _nested_indentation_fixture(width)
    )


def test_ordinary_cases_use_the_frozen_generator_bytes():
    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    by_id = {case.case_id: case for case in cases}

    (primary_fixture,) = by_id[CASE_PRIMARY].contract.structured_input["args"]
    (preserve_fixture,) = by_id[CASE_PRESERVE].contract.structured_input["args"]
    assert primary_fixture == _nested_indentation_fixture(2)
    assert preserve_fixture == _nested_indentation_fixture(4)


def _positive_widths(text: str) -> list[int]:
    return [
        len(line) - len(line.lstrip(" "))
        for line in text.splitlines()
        if line.startswith(" ")
    ]


@pytest.mark.parametrize(
    "case_id, unit, other_unit, shallowest_depth",
    [
        (CASE_DEEP_DEFECT, 2, 4, 3),
        (CASE_DEEP_PRESERVE, 4, 2, 2),
    ],
)
def test_depth_only_fixtures_contain_no_shallow_evidence(
    case_id, unit, other_unit, shallowest_depth
):
    """§7 — depth-only means depth-only, pinned structurally."""

    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    by_id = {case.case_id: case for case in cases}
    (fixture,) = by_id[case_id].contract.structured_input["args"]
    widths = _positive_widths(fixture)

    assert widths, "a depth-only fixture still has to contain indentation"
    # No line at exactly one indentation unit — the whole point of the case.
    assert unit not in widths
    # And none at the collision partner's unit either, so the sample can only
    # be classified by inferring the base unit rather than recognising a width.
    assert other_unit not in widths
    assert min(widths) == unit * shallowest_depth
    assert all(width % unit == 0 for width in widths)
    # More than one depth, so the base unit is recoverable at all.
    assert len(set(widths)) >= 2


def test_depth_only_fixture_bytes_are_deterministic():
    first = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    assert [case.contract.structured_input_json for case in first] == [
        case.contract.structured_input_json
        for case in build_behavioral_matrix(
            probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
        )
    ]
    assert indentation_depth_fixture(2, (0, 3, 4, 4, 3)) == (
        "level_0\n"
        "      level_1\n"
        "        level_2\n"
        "        level_3\n"
        "      level_4\n"
    )


def test_depth_derivation_lands_on_the_measured_round8_depths():
    """§5 — the exact depths Round 8 measured, derived rather than chosen."""

    assert depth_only_depths(2, (2, 4)) == (0, 3, 4, 4, 3)
    assert depth_only_depths(4, (2, 4)) == (0, 2, 3, 3, 2)
    # Bounded: a width whose every shallow depth collides yields nothing at all
    # rather than an unbounded search.
    assert depth_only_depths(1, tuple(range(1, 9))) == ()


def test_the_baseline_classifier_reads_every_depth_only_fixture_as_four_space():
    """The measured baseline behavior each derived case rests on."""

    cases = build_behavioral_matrix(
        probe_contract=_t6_contract(), behavior_fact=_t6_behavior_fact()
    )
    observed = {
        case.case_id: _classify_indent(case.contract.structured_input["args"][0])
        for case in cases
    }

    assert observed == {
        CASE_PRIMARY: "4space",
        CASE_DEEP_DEFECT: "4space",
        CASE_PRESERVE: "4space",
        CASE_DEEP_PRESERVE: "4space",
        # DEFECT.PROBE.LIVE.5's skew fixture, which the baseline also
        # misclassifies — which is what makes it a defect case there too.
        CASE_SKEW: "4space",
        # INDENT.SEMANTICS.1's three preservation fixtures, which the baseline
        # already answers correctly — which is what makes them oracles.
        CASE_CONTINUATION: "4space",
        CASE_MULTILINE_STRING: "4space",
        CASE_GO_TAB: "tab",
    }


# ═══════════════════════════════════════════════════════════════════════════
# §8/§9/§10 — baseline semantics
# ═══════════════════════════════════════════════════════════════════════════


def test_baseline_reproduces_the_primary_claim_and_its_generalization(t6_ceiling):
    _contract, pre, receipt = t6_ceiling
    cases = _case_map(receipt)

    # §8 — the factual reproduction anchor is untouched.
    assert pre.probe_result == PROBE_REPRODUCED
    assert cases[CASE_PRIMARY].baseline_status == BASELINE_REPRODUCED
    assert cases[CASE_PRIMARY].baseline_observed == "4space"
    assert cases[CASE_PRIMARY].expected == "2space"
    # §9 — the generalization may also fail on the baseline.  That is valid,
    # and it is not a second user claim.
    assert cases[CASE_DEEP_DEFECT].baseline_status == BASELINE_REPRODUCED
    assert cases[CASE_DEEP_DEFECT].baseline_observed == "4space"
    assert cases[CASE_DEEP_DEFECT].provenance == MATRIX_PROVENANCE_SUBJECT_INVARIANT


def test_both_preservation_cases_are_oracles_because_the_baseline_holds(t6_ceiling):
    _contract, _pre, receipt = t6_ceiling
    cases = _case_map(receipt)

    # §10 — a preservation case is an oracle only where the baseline satisfies it.
    for case_id in (CASE_PRESERVE, CASE_DEEP_PRESERVE):
        assert cases[case_id].baseline_status == BASELINE_SATISFIED
        assert cases[case_id].baseline_observed == "4space"
        assert cases[case_id].baseline_result == PROBE_NOT_REPRODUCED


def _synthetic_binding(tmp_path: Path, source: str):
    path = tmp_path / "calc.py"
    path.write_text(source, encoding="utf-8")
    (tmp_path / "contract.md").write_text("add(a, b) sums\n", encoding="utf-8")
    binding = build_probe_target_binding(
        repo_path=tmp_path,
        target_file="calc.py",
        target_symbol="add",
        source_snippet=source.strip(),
        candidate_eligible=True,
    )
    assert binding is not None
    return binding


def _synthetic_contract(binding, *, args, expected):
    return build_python_function_probe(
        target=binding,
        args=args,
        expected=expected,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        provenance_reference="repository contract: add sums its arguments",
        expectation_source_paths=("contract.md",),
    )


def _synthetic_case(binding, *, args, expected, case_id, role):
    return BehavioralMatrixCase(
        case_id=case_id,
        role=role,
        provenance=MATRIX_PROVENANCE_SUBJECT_INVARIANT,
        subject_kind="synthetic",
        expected=expected,
        contract=_synthetic_contract(binding, args=args, expected=expected),
        derivation="bounded fixture case",
    )


def test_a_preservation_case_the_baseline_already_fails_is_never_a_regression(
    tmp_path,
):
    """§10 — never manufacture a regression from baseline-broken behavior."""

    binding = _synthetic_binding(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    assert pre.probe_result == PROBE_REPRODUCED

    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()
    receipt = evaluate_behavioral_closure(
        repo_path=tmp_path,
        candidate_plan=[
            {
                "op": "replace_snippet",
                "relative_path": "calc.py",
                "target_snippet": "    return a - b\n",
                "patched_snippet": "    return a + b\n",
            }
        ],
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        matrix_cases=[
            _synthetic_case(
                binding,
                args=(2, 2),
                expected=4,
                case_id="synthetic.primary",
                role=ROLE_PRIMARY_DEFECT,
            ),
            # ``add`` is wrong for (5, 1) exactly as it is wrong for (2, 2), so
            # nothing here was ever correct for a candidate to have broken.
            _synthetic_case(
                binding,
                args=(5, 1),
                expected=99,
                case_id="synthetic.preserve",
                role=ROLE_PRESERVATION,
            ),
        ],
        sandbox_parent=sandbox_parent,
    )

    case = {item.case_id: item for item in receipt.cases}["synthetic.preserve"]
    assert case.baseline_status == BASELINE_REPRODUCED
    assert case.candidate_status == CANDIDATE_UNAVAILABLE
    assert case.reason == REASON_BASELINE_NOT_SATISFIED
    assert case.candidate_result == ""
    assert case.candidate_observed is None
    assert not list(sandbox_parent.iterdir())


# ═══════════════════════════════════════════════════════════════════════════
# §13 — the Round-8 ceiling candidate
# ═══════════════════════════════════════════════════════════════════════════


def test_round8_ceiling_candidate_passes_both_ordinary_cases(t6_ceiling):
    _contract, _pre, receipt = t6_ceiling
    cases = _case_map(receipt)

    # Exactly what Round 8 measured: the two-point oracle is satisfied.
    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRIMARY].candidate_observed == "2space"
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_PRESERVE].candidate_observed == "4space"


def test_round8_ceiling_candidate_fails_both_depth_variant_cases(t6_ceiling):
    _contract, _pre, receipt = t6_ceiling
    cases = _case_map(receipt)

    # And exactly what Round 8 measured next: with no line at one indentation
    # unit, the candidate classifies nothing at all.
    assert cases[CASE_DEEP_DEFECT].candidate_status == CANDIDATE_CHANGED_BUT_UNRESOLVED
    assert cases[CASE_DEEP_DEFECT].candidate_observed is None
    assert cases[CASE_DEEP_PRESERVE].candidate_status == CANDIDATE_REGRESSED
    assert cases[CASE_DEEP_PRESERVE].candidate_observed is None


def test_round8_ceiling_candidate_does_not_reach_behavioral_closure(t6_ceiling):
    _contract, _pre, receipt = t6_ceiling

    assert receipt.matrix_status != MATRIX_FIXED_AND_PRESERVED
    assert receipt.matrix_status == MATRIX_FIXED_BUT_REGRESSIVE
    assert receipt.closure_ready is False
    # §11 — a legacy reader may not be told the pair closed either.
    assert receipt.paired_status != PAIRED_FIXED_AND_PRESERVED
    assert receipt.defect_closure_status != CLOSURE_FIXED
    assert REASON_PRESERVATION_REGRESSED in receipt.rejection_reasons


def test_red_green_the_pre_live4_oracle_accepted_the_ceiling_candidate():
    """§33 — the measured ceiling, demonstrated rather than asserted.

    The same candidate bytes, the same contract, the same repository: under
    DEFECT.PROBE.LIVE.3's two-point oracle it closes, and under this phase's
    matrix it does not.  That difference is the whole phase.
    """

    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    plan = _t6_plan(T6_BASELINE_BRANCHES, T6_CEILING_BRANCHES)
    before = (ROOT / T6_TARGET_FILE).read_bytes()

    old = evaluate_paired_defect_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_behavior_fact(),
    )

    # RED: the two-point oracle is satisfied by a candidate that is wrong.
    assert old.paired_status == PAIRED_FIXED_AND_PRESERVED
    assert old.defect_closure_status == CLOSURE_FIXED
    assert old.closure_ready is True
    assert len(old.preservation_cases) == 1
    assert old.preservation_cases[0].status == PRESERVATION_PRESERVED

    new = evaluate_behavioral_closure(
        repo_path=ROOT,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
        behavior_fact=_t6_behavior_fact(),
    )

    # GREEN: the ordinary cases still pass, a depth variant does not, and the
    # matrix refuses closure.
    cases = _case_map(new)
    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert {
        cases[CASE_DEEP_DEFECT].candidate_status,
        cases[CASE_DEEP_PRESERVE].candidate_status,
    } != {CANDIDATE_FIXED, CANDIDATE_PRESERVED}
    assert new.matrix_status != MATRIX_FIXED_AND_PRESERVED
    assert new.closure_ready is False
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before


# ═══════════════════════════════════════════════════════════════════════════
# §14/§15/§16 — the other captured candidates
# ═══════════════════════════════════════════════════════════════════════════


def test_known_inverted_reorder_stays_fixed_but_regressive(t6_reorder):
    """§14 — the LIVE.3 verdict must not drift to anything more permissive."""

    _contract, _pre, receipt = t6_reorder
    cases = _case_map(receipt)

    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_REGRESSED
    assert cases[CASE_PRESERVE].candidate_observed == "2space"
    assert receipt.matrix_status == MATRIX_FIXED_BUT_REGRESSIVE
    assert receipt.paired_status == PAIRED_FIXED_BUT_REGRESSIVE
    assert receipt.defect_closure_status == CLOSURE_FIXED_BUT_REGRESSIVE
    assert receipt.closure_ready is False


def test_the_exact_no_op_candidate_is_rejected_before_any_matrix_work():
    """§15 — the cheap-first funnel stays intact; LIVE.4 never runs for it."""

    plan = _t6_plan(T6_BASELINE_BRANCHES, T6_BASELINE_BRANCHES)
    effect = evaluate_candidate_mutation_effect(plan)

    assert effect.status == CANDIDATE_EFFECT_NO_OP
    assert effect.rejection_reason == REASON_NO_OP_CANDIDATE
    assert effect.candidate_accepted is False


def test_the_no_op_candidate_never_reaches_the_matrix_producer(monkeypatch):
    """§15 — measured at this phase's own boundary, not asserted.

    PATCH.MINIMAL.LIVE.1 removes the candidate when it rejects one, so the
    grounded-defect recorder finds no plan and neither builds a matrix nor
    creates a sandbox.  The end-to-end funnel is measured by
    ``tests/test_patch_minimal_live.py``, which counts this same entry point.
    """

    from types import SimpleNamespace

    calls: list[Any] = []
    monkeypatch.setattr(
        pipeline,
        "evaluate_behavioral_closure",
        lambda *args, **kwargs: calls.append(kwargs),
    )
    state = _t6_recorder_state(T6_BASELINE_BRANCHES)
    before = (ROOT / T6_TARGET_FILE).read_bytes()

    pipeline._record_candidate_mutation_effect(state)
    result = pipeline._record_candidate_defect_closure(
        state,
        SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT),
        ROOT,
        patch_safety={"ok": True},
    )

    assert state.json_block["candidate_effect_status"] == CANDIDATE_EFFECT_NO_OP
    assert not state.json_block.get("patch_plan")
    assert calls == []
    assert result is None
    assert "behavioral_matrix" not in state.json_block
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before


def test_a_byte_changing_candidate_does_reach_the_matrix_producer(monkeypatch):
    """The companion control: the funnel narrows no-ops, and nothing else."""

    from types import SimpleNamespace

    calls: list[Any] = []
    monkeypatch.setattr(
        pipeline,
        "evaluate_behavioral_closure",
        lambda *args, **kwargs: calls.append(kwargs) or None,
    )
    state = _t6_recorder_state(T6_CEILING_BRANCHES)

    pipeline._record_candidate_mutation_effect(state)
    pipeline._record_candidate_defect_closure(
        state,
        SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT),
        ROOT,
        patch_safety={"ok": True},
    )

    assert state.json_block["patch_plan"]
    assert len(calls) == 1


def _t6_recorder_state(patched: str):
    """The narrow live state ``_record_candidate_defect_closure`` reads."""

    from core.agent_state import AgentState

    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
    route = {
        "selected_workflow": "defect_repair_patch",
        "preservation_passed": True,
        "behavioral_expectations": [_t6_behavior_fact().as_dict()],
    }
    state = AgentState(
        interface="agent",
        mode="control",
        user_input=f"Fix this bug: {T6_QUERY}",
        file_paths=[str(ROOT)],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
        repo_path=str(ROOT),
        is_project_input=True,
        live_route=route,
    )
    state.control_result = {
        "repo_path": str(ROOT),
        "live_route": dict(route),
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "defect_probe": pre.as_dict(),
        "patch_intent": {
            "target_file": T6_TARGET_FILE,
            "relative_path": T6_TARGET_FILE,
            "target_symbol": T6_TARGET_SYMBOL,
            "target_symbol_full": f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}",
            "source_snippet": inspect.getsource(_classify_indent).strip(),
        },
        "entry_resolution": {
            "resolved_entry_nodes": [f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}"]
        },
    }
    state.json_block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "patch_plan": _t6_plan(T6_BASELINE_BRANCHES, patched),
    }
    return state


def test_the_legacy_raw_width_control_closed_the_five_case_matrix(t6_unit_inferring):
    """§16 — the oracle has to open as well as close.

    Measured on the five cases this control was written against.  The
    eight-case oracle opens for tests/test_indent_semantics1.py's structural
    control instead, and rejects this one there.
    """

    _contract, _pre, receipt = t6_unit_inferring
    cases = _case_map(receipt)

    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_DEEP_DEFECT].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_DEEP_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert [item.candidate_observed for item in receipt.cases] == [
        "2space",
        "2space",
        "4space",
        "4space",
        # DEFECT.PROBE.LIVE.5's skew case, which this control also answers.
        "2space",
    ]
    assert receipt.matrix_status == MATRIX_FIXED_AND_PRESERVED
    assert receipt.paired_status == PAIRED_FIXED_AND_PRESERVED
    assert receipt.defect_closure_status == CLOSURE_FIXED
    assert receipt.rejection_reasons == ()
    assert receipt.closure_ready is True


def test_the_positive_control_is_never_applied_to_production():
    """§17 — a test-only implementation, and it stays that way."""

    live = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert T6_UNIT_INFERRING_BODY not in live
    assert T6_CLASSIFIER_BODY in live
    # And the phase does not hand it to a writer: no production module mentions
    # the control's identifiers.
    assert "space_widths" not in inspect.getsource(matrix_probe)


def test_live3s_own_positive_control_is_only_partially_fixed(t6_min_width):
    """§11/§12 — one closing defect case never speaks for another.

    DEFECT.PROBE.LIVE.3 accepted the smallest-observed-width candidate, and it
    is correct for both ordinary widths and for the deep 4-space sample.  It
    still cannot classify a 2-space sample whose shallowest line is six spaces
    wide, so the defect family is measurably open and the matrix says so.
    """

    _contract, _pre, receipt = t6_min_width
    cases = _case_map(receipt)

    assert cases[CASE_PRIMARY].candidate_status == CANDIDATE_FIXED
    assert cases[CASE_DEEP_DEFECT].candidate_status == CANDIDATE_STILL_REPRODUCED
    assert cases[CASE_DEEP_DEFECT].candidate_observed == "4space"
    assert cases[CASE_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert cases[CASE_DEEP_PRESERVE].candidate_status == CANDIDATE_PRESERVED
    assert receipt.matrix_status == MATRIX_PARTIALLY_FIXED
    assert receipt.closure_ready is False
    assert REASON_DEFECT_CASE_NOT_CLOSED in receipt.rejection_reasons
    assert f"{REASON_DEFECT_CASE_NOT_CLOSED}:{CASE_DEEP_DEFECT}" in (
        receipt.rejection_reasons
    )
    # §11 — the legacy fields are narrowed with it, never left saying "closed".
    assert receipt.paired_status == PAIRED_CHANGED_BUT_UNRESOLVED
    assert receipt.defect_closure_status == CLOSURE_CHANGED_BUT_UNRESOLVED


# ═══════════════════════════════════════════════════════════════════════════
# §11/§12 — the reduction
# ═══════════════════════════════════════════════════════════════════════════


def _result(
    case_id: str,
    role: str,
    *,
    baseline: str = BASELINE_REPRODUCED,
    candidate: str = CANDIDATE_FIXED,
) -> MatrixCaseResult:
    return MatrixCaseResult(
        case_id=case_id,
        role=role,
        provenance=(
            PROVENANCE_EXPLICIT_USER_FACT
            if role == ROLE_PRIMARY_DEFECT
            else MATRIX_PROVENANCE_SUBJECT_INVARIANT
        ),
        subject_kind=SUBJECT_INDENTATION_STYLE,
        expected="2space",
        baseline_status=baseline,
        candidate_status=candidate,
    )


def _primary(candidate: str = CANDIDATE_FIXED) -> MatrixCaseResult:
    return _result(CASE_PRIMARY, ROLE_PRIMARY_DEFECT, candidate=candidate)


def _generalization(candidate: str) -> MatrixCaseResult:
    return _result(CASE_DEEP_DEFECT, ROLE_DEFECT_GENERALIZATION, candidate=candidate)


def _preservation(candidate: str, case_id: str = CASE_PRESERVE) -> MatrixCaseResult:
    return _result(
        case_id,
        ROLE_PRESERVATION,
        baseline=BASELINE_SATISFIED,
        candidate=candidate,
    )


def test_one_defect_generalization_failure_blocks_closure():
    status, reasons = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_FIXED),
            _generalization(CANDIDATE_STILL_REPRODUCED),
            _preservation(CANDIDATE_PRESERVED),
        )
    )

    assert status == MATRIX_PARTIALLY_FIXED
    assert status not in {MATRIX_FIXED_AND_PRESERVED}
    assert REASON_DEFECT_CASE_NOT_CLOSED in reasons


def test_one_preservation_regression_blocks_closure_whatever_the_defects_did():
    status, reasons = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_FIXED),
            _generalization(CANDIDATE_FIXED),
            _preservation(CANDIDATE_REGRESSED),
        )
    )

    assert status == MATRIX_FIXED_BUT_REGRESSIVE
    assert REASON_PRESERVATION_REGRESSED in reasons


def test_a_regression_outranks_an_undecided_case():
    """§12 — precedence is fixed, and a regression is decisive."""

    status, _reasons = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_FIXED),
            _generalization(CANDIDATE_INCONCLUSIVE),
            _preservation(CANDIDATE_REGRESSED),
        )
    )

    assert status == MATRIX_FIXED_BUT_REGRESSIVE


def test_missing_required_evidence_can_never_become_verified():
    for undecided in (CANDIDATE_INCONCLUSIVE, CANDIDATE_UNAVAILABLE):
        status, reasons = reduce_behavioral_matrix(
            (
                _primary(CANDIDATE_FIXED),
                _generalization(undecided),
                _preservation(CANDIDATE_PRESERVED),
            )
        )
        assert status == MATRIX_INCONCLUSIVE, undecided
        assert REASON_CASE_NO_VERDICT in reasons

    assert reduce_behavioral_matrix(()) == (
        MATRIX_UNAVAILABLE,
        (REASON_MATRIX_NOT_EXECUTED,),
    )


def test_no_defect_case_closing_reduces_by_how_the_failures_look():
    still, _ = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_STILL_REPRODUCED),
            _generalization(CANDIDATE_STILL_REPRODUCED),
        )
    )
    changed, _ = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_STILL_REPRODUCED),
            _generalization(CANDIDATE_CHANGED_BUT_UNRESOLVED),
        )
    )

    assert still == MATRIX_STILL_REPRODUCED
    assert changed == MATRIX_UNRESOLVED_FAILURE


def test_a_clean_sweep_is_the_only_route_to_closure():
    status, reasons = reduce_behavioral_matrix(
        (
            _primary(CANDIDATE_FIXED),
            _generalization(CANDIDATE_FIXED),
            _preservation(CANDIDATE_PRESERVED),
            _preservation(CANDIDATE_PRESERVED, case_id=CASE_DEEP_PRESERVE),
        )
    )

    assert status == MATRIX_FIXED_AND_PRESERVED
    assert reasons == ()


def test_the_reduction_is_deterministic_for_the_same_inputs():
    cases = (
        _primary(CANDIDATE_FIXED),
        _generalization(CANDIDATE_STILL_REPRODUCED),
        _preservation(CANDIDATE_PRESERVED),
    )

    assert reduce_behavioral_matrix(cases) == reduce_behavioral_matrix(cases)
    assert reduce_behavioral_matrix(tuple(reversed(cases))) == (
        reduce_behavioral_matrix(cases)
    )


def test_a_case_may_not_carry_a_verdict_from_the_other_role_family():
    with pytest.raises(ValueError, match="preservation verdict"):
        _result(CASE_PRIMARY, ROLE_PRIMARY_DEFECT, candidate=CANDIDATE_PRESERVED)
    with pytest.raises(ValueError, match="defect verdict"):
        _result(
            CASE_PRESERVE,
            ROLE_PRESERVATION,
            baseline=BASELINE_SATISFIED,
            candidate=CANDIDATE_FIXED,
        )


@pytest.mark.parametrize(
    "probe_result",
    [PROBE_REPRODUCED, PROBE_NOT_REPRODUCED, PROBE_INCONCLUSIVE, PROBE_INVALID, PROBE_UNAVAILABLE],
)
def test_preservation_verdicts_agree_with_live3_for_every_probe_result(probe_result):
    """The two halves of one receipt may not disagree about "regressed"."""

    receipt = _receipt_with(probe_result)
    live3_status, _ = paired_probe._candidate_case_status(receipt)
    live4_status, _ = matrix_probe._preservation_candidate_status(
        ProbeObservation.of(receipt)
    )

    assert live4_status == {
        "preserved": CANDIDATE_PRESERVED,
        "regressed": CANDIDATE_REGRESSED,
        "inconclusive": CANDIDATE_INCONCLUSIVE,
    }[live3_status]


@pytest.mark.parametrize(
    "probe_result, expected",
    [
        (PROBE_NOT_REPRODUCED, BASELINE_SATISFIED),
        (PROBE_REPRODUCED, BASELINE_REPRODUCED),
        (PROBE_INCONCLUSIVE, BASELINE_INCONCLUSIVE),
        (PROBE_UNAVAILABLE, BASELINE_INCONCLUSIVE),
    ],
)
def test_baseline_status_reads_one_probe_result_at_a_time(probe_result, expected):
    status, _reason = matrix_probe._baseline_status(
        ProbeObservation.of(_receipt_with(probe_result))
    )

    assert status == expected
    assert matrix_probe._baseline_status(None)[0] == BASELINE_UNAVAILABLE


def _receipt_with(probe_result: str):
    from core.defect_probe import DefectProbeReceipt

    return DefectProbeReceipt(
        attempted=True,
        probe_result=probe_result,
        probe_basis=PROBE_BASIS_REPOSITORY_CONTRACT,
        input_basis=INPUT_BASIS_REPOSITORY_CONTRACT,
        expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
        observed="4space",
    )


# ═══════════════════════════════════════════════════════════════════════════
# §18/§19/§22/§23 — integration and binding
# ═══════════════════════════════════════════════════════════════════════════


def test_the_matrix_uses_exactly_one_candidate_sandbox(t6_ceiling, monkeypatch):
    """§23 — extra cost is probe executions, never repeated patch application."""

    import core.candidate_defect_probe as candidate_probe

    sandboxes: list[Any] = []
    real = candidate_probe.create_managed_sandbox

    def counting(*args, **kwargs):
        sandboxes.append(args)
        return real(*args, **kwargs)

    monkeypatch.setattr(candidate_probe, "create_managed_sandbox", counting)
    _contract, _pre, receipt = _t6_matrix(
        _t6_plan(T6_BASELINE_BRANCHES, T6_CEILING_BRANCHES)
    )

    assert len(sandboxes) == 1
    assert len(receipt.cases) == 8
    assert receipt.closure.candidate_apply_status == "applied"
    assert receipt.closure.sandbox_cleanup_ok is True
    # Seven companion receipts from that *one* sandbox, plus the primary probe.
    # DEFECT.PROBE.LIVE.5 added a case and INDENT.SEMANTICS.1 three, not a
    # sandbox.
    assert len(receipt.closure.preservation_probe_receipts) == 7


def test_every_matrix_case_binds_to_the_same_candidate_and_probe(t6_ceiling):
    """§22 — one fingerprint algorithm, one candidate, one probe."""

    contract, _pre, receipt = t6_ceiling
    telemetry = receipt.as_telemetry()
    block = telemetry["behavioral_matrix"]

    assert block["candidate_fingerprint"] == receipt.closure.candidate_fingerprint
    assert block["probe_fingerprint"] == contract.fingerprint
    assert telemetry["candidate_fingerprint"] == block["candidate_fingerprint"]
    assert telemetry["probe_fingerprint"] == block["probe_fingerprint"]


def test_a_changed_candidate_makes_the_matrix_evidence_stale(t6_ceiling):
    """§22 — no second fingerprint algorithm, and no evidence that outlives it."""

    _contract, _pre, receipt = t6_ceiling
    telemetry = receipt.as_telemetry()

    verdict, _limits = verification._matrix_verdict(
        telemetry["behavioral_matrix"],
        candidate="0" * 64,
        probe=telemetry["probe_fingerprint"],
    )

    assert verdict.verdict == verification.COMPONENT_STALE
    assert verdict.reason == verification.REASON_CANDIDATE_FINGERPRINT_STALE


def test_pipeline_discards_matrix_facts_with_the_candidate_they_measured():
    """§22 — every matrix key travels with the plan it was measured against."""

    for key in (
        "behavioral_matrix",
        "behavioral_matrix_status",
        "behavioral_matrix_cases",
        "behavioral_matrix_rejection_reasons",
        "behavioral_matrix_case_count",
        "behavioral_matrix_subject_kind",
        "behavioral_matrix_timings",
        "behavioral_matrix_authority_effect",
        "behavioral_matrix_phase_id",
        "behavioral_matrix_schema_version",
    ):
        assert key in pipeline._CANDIDATE_DEFECT_PROBE_KEYS, key


def test_candidate_verification_consumes_the_matrix_not_the_primary_case(
    t6_ceiling,
):
    """§18 — matrix semantics are authoritative where a matrix was measured."""

    contract, pre, receipt = t6_ceiling
    verdict, _limits = verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )

    assert verdict.component == COMPONENT_PAIRED_PROBE
    assert verdict.verdict == CONTRADICTING


def test_a_two_point_passing_candidate_is_rejected_end_to_end(t6_ceiling):
    """§18/§34 — the reduction that a reader actually sees."""

    contract, pre, receipt = t6_ceiling
    result = evaluate_candidate_verification(_verification_evidence(contract, pre, receipt))

    assert result.status == REJECTED
    assert result.verified is False
    # §12/§34 - an unverified candidate may not be *presented* as ready, which
    # is the field the pipeline then narrows human_review_eligible from.
    assert result.review_ready is False
    assert result.as_telemetry()["candidate_review_ready"] is False
    assert result.as_telemetry()["candidate_verification_needs_escalation"] is True
    reasons = set(result.rejection_reasons)
    assert reasons & {
        verification.REASON_PRESERVATION_REGRESSED,
        REASON_SUBJECT_INVARIANT_NOT_CLOSED,
        REASON_PRIMARY_DEFECT_NOT_CLOSED,
    }


def test_the_partially_fixed_candidate_is_rejected_for_the_subject_invariant(
    t6_min_width,
):
    """§18 — the primary claim closed; the subject invariant did not."""

    contract, pre, receipt = t6_min_width
    verdict, _limits = verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )

    assert verdict.verdict == CONTRADICTING
    assert verdict.reason == REASON_SUBJECT_INVARIANT_NOT_CLOSED
    result = evaluate_candidate_verification(
        _verification_evidence(contract, pre, receipt)
    )
    assert result.status == REJECTED
    assert result.review_ready is False
    assert result.as_telemetry()["candidate_review_ready"] is False


def test_the_legacy_raw_width_control_was_not_rejected_by_the_five_case_matrix(
    t6_unit_inferring,
):
    """§16/§29 — supporting evidence, and still not authority."""

    contract, _pre, receipt = t6_unit_inferring
    verdict, limits = verification._matrix_verdict(
        receipt.as_telemetry()["behavioral_matrix"],
        candidate=receipt.closure.candidate_fingerprint,
        probe=contract.fingerprint,
    )

    assert verdict.verdict == verification.SUPPORTING
    assert limits == ()


def _verification_evidence(contract, pre, receipt) -> dict[str, Any]:
    """The evidence mapping the pipeline assembles, with this run's receipts."""

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


def test_a_receipt_without_a_matrix_keeps_live3_paired_semantics():
    """§18/§19 — a pre-LIVE.4 receipt is read exactly as it always was."""

    legacy = {
        "defect_closure_status": "fixed",
        "paired_status": "fixed_and_preserved",
        "preservation_oracle_status": "available",
        "post_probe_result": "not_reproduced",
        "candidate_fingerprint": "a" * 64,
        "probe_fingerprint": "b" * 64,
        "preservation_cases": [
            {"case_id": CASE_PRESERVE, "status": "preserved"},
        ],
    }

    verdict, limits = verification._paired_probe_verdict(
        {"candidate_defect_closure": legacy}, candidate="a" * 64, probe="b" * 64
    )

    assert verdict.verdict == verification.SUPPORTING
    # And it is recorded that closure rested on the pair alone.
    assert verification.LIMITATION_NO_BEHAVIORAL_MATRIX in limits


def test_a_matrix_run_reports_only_the_cases_live3_actually_ran(t6_ceiling):
    """§19 — no old receipt, and no new one, claims a depth case ran as LIVE.3."""

    _contract, _pre, receipt = t6_ceiling
    telemetry = receipt.as_telemetry()

    assert len(telemetry["preservation_cases"]) == 1
    (legacy_case,) = telemetry["preservation_cases"]
    assert legacy_case["case_id"] == CASE_PRESERVE
    assert legacy_case["provenance"] == PRESERVATION_PROVENANCE
    assert legacy_case["status"] == PRESERVATION_PRESERVED
    # The depth-variant cases exist only where they were measured.
    assert {item["case_id"] for item in telemetry["behavioral_matrix_cases"]} == set(
        REQUIRED_CASE_IDS
    )


def test_the_legacy_status_is_narrowed_by_the_matrix_never_widened(t6_ceiling):
    """§11/§19 — a legacy reader cannot be told the pair closed."""

    _contract, _pre, receipt = t6_ceiling

    assert receipt.paired.preservation_cases[0].status == PRESERVATION_PRESERVED
    assert receipt.paired_status not in {PAIRED_FIXED_AND_PRESERVED, PAIRED_FIXED}
    assert receipt.defect_closure_status != CLOSURE_FIXED


def test_an_unsupported_subject_falls_back_to_the_live3_pair(tmp_path):
    """§18/§30 — tasks without matrix support keep current probe behavior."""

    binding = _synthetic_binding(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    assert pre.probe_result == PROBE_REPRODUCED

    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()
    receipt = evaluate_behavioral_closure(
        repo_path=tmp_path,
        candidate_plan=[
            {
                "op": "replace_snippet",
                "relative_path": "calc.py",
                "target_snippet": "    return a - b\n",
                "patched_snippet": "    return a + b\n",
            }
        ],
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        behavior_fact=None,
        sandbox_parent=sandbox_parent,
    )

    assert isinstance(receipt, paired_probe.PairedDefectProbeReceipt)
    assert not isinstance(receipt, matrix_probe.BehavioralMatrixReceipt)
    assert receipt.paired_status == PAIRED_FIXED
    assert "behavioral_matrix" not in receipt.as_telemetry()


# ═══════════════════════════════════════════════════════════════════════════
# §20/§25/§29 — telemetry, cost and authority
# ═══════════════════════════════════════════════════════════════════════════


def test_the_matrix_receipt_is_bounded_and_carries_no_source_or_confidence(
    t6_ceiling,
):
    _contract, _pre, receipt = t6_ceiling
    telemetry = receipt.as_telemetry()
    block = telemetry["behavioral_matrix"]

    assert set(block) == {
        "phase_id",
        # DEFECT.PROBE.LIVE.5 — additive, inside this same one canonical
        # structure rather than a second subtree beside it.
        "discrimination_phase_ids",
        "schema_version",
        "subject_kind",
        "case_count",
        "cases",
        "matrix_status",
        "rejection_reasons",
        "candidate_fingerprint",
        "probe_fingerprint",
        "authority_effect",
    }
    assert block["subject_kind"] == SUBJECT_INDENTATION_STYLE
    assert block["case_count"] == 8
    for case in block["cases"]:
        assert set(case) == {
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
            # INDENT.SEMANTICS.1 retains its declared semantics;
            # PATCH.AUTHOR.LIVE.3 adds bounded executed input evidence.
            "input_text",
            "case_probe_fingerprint",
            "input_language",
            "observation_tier",
            "claim_strength",
            "fallback_reason",
            "reference_assessment",
        }
        assert case["role"] in CASE_ROLES
        assert isinstance(case["input_text"], str)
        assert len(case["input_text"].encode("utf-8")) <= 16_384
        assert len(case["case_probe_fingerprint"]) == 64
    rendered = json.dumps(telemetry, ensure_ascii=False)
    for forbidden in ("confidence", "authority_to", "def _classify_indent"):
        assert forbidden not in rendered
    assert block["authority_effect"] == "none"


def test_the_matrix_grants_no_authority(t6_unit_inferring):
    """§29 — even a clean sweep sets nothing."""

    _contract, _pre, receipt = t6_unit_inferring
    telemetry = receipt.as_telemetry()

    assert receipt.matrix_status == MATRIX_FIXED_AND_PRESERVED
    for key in (
        "write_authority",
        "execution_authorized",
        "approval_ready",
        "human_review_eligible",
        "final_repository_changed",
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
        "production_classifier_fixed",
        "randomized_or_generated_cases",
        "property_based_testing_added",
        "single_passing_case_can_close_the_matrix",
    ):
        assert guardrails[flag] is False, flag


def test_matrix_cost_is_reported_by_stage_and_stays_bounded(t6_ceiling):
    """§25 — construction, baselines, candidate probes and reduction, apart."""

    _contract, _pre, receipt = t6_ceiling

    assert set(receipt.timings) >= {
        "matrix_construction_sec",
        "matrix_baseline_sec",
        "matrix_candidate_probe_sec",
        "matrix_reduction_sec",
        "matrix_total_sec",
    }
    # Construction and reduction are pure and must not be measurable work.
    assert receipt.timings["matrix_construction_sec"] < 0.5
    assert receipt.timings["matrix_reduction_sec"] < 0.1
    # O(fixed case count): seven companion baselines and seven companion
    # candidate probes, because the primary case's two observations already
    # exist and are never re-executed.
    assert len(receipt.closure.preservation_probe_receipts) == 7


def test_the_module_opens_no_provider_network_or_repository_walk():
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
    }
    used = _referenced_names(matrix_probe)

    assert not (used & forbidden), sorted(used & forbidden)


# ═══════════════════════════════════════════════════════════════════════════
# §26/§27/§28 — the frozen boundaries
# ═══════════════════════════════════════════════════════════════════════════


def _frozen_boundaries() -> dict[str, Any]:
    path = ROOT / "tests" / "fixtures" / "defect_probe_live4_frozen_boundaries.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_frozen_collaborator_is_byte_identical():
    """§26/§27 — safe_minimal, budgets, probe execution and authority frozen."""

    boundaries = _frozen_boundaries()
    assert boundaries["phase_id"] == "DEFECT.PROBE.LIVE.4"

    from _harness_maintenance import before_harness_remediation

    # The explicitly requested harness remediation (2026-09-11) edited some of
    # these files after this phase froze them; its receipt undoes exactly those
    # edits, so the pin is checked against history and is never re-pinned.
    drifted = []
    for relative, digest in boundaries["files"].items():
        actual = hashlib.sha256(before_harness_remediation(relative)).hexdigest()
        if actual != digest:
            drifted.append(f"{relative}: {digest} -> {actual}")
    assert not drifted, "frozen boundary drift:\n" + "\n".join(drifted)


def test_the_frozen_set_covers_the_boundaries_this_phase_promised():
    files = set(_frozen_boundaries()["files"])

    for required in (
        "core/code_dna.py",
        "core/defect_probe.py",
        "core/defect_probe_worker.py",
        "core/candidate_defect_probe.py",
        "core/paired_defect_probe.py",
        "core/behavioral_expectation.py",
        "core/candidate_mutation_effect.py",
        "core/targeted_repository_validation.py",
        "core/execution_eligibility_policy.py",
        "core/live_execution_authorization.py",
        "core/human_apply_authorization.py",
        "patching/patch_gates.py",
        "core/answer_entity_grounding.py",
    ):
        assert required in files, required


def test_the_production_classifier_was_not_repaired():
    """§0 — LIVE.4 fixes an oracle, not ``_classify_indent``."""

    source = inspect.getsource(_classify_indent)

    assert 'elif line.startswith("    "):' in source
    assert '            counts["4space"] += 1' in source
    assert "gcd" not in source
    assert "space_widths" not in source
    # And it still misclassifies every one of the four bounded samples.
    assert _classify_indent(_nested_indentation_fixture(2)) == "4space"


def test_new_matrix_telemetry_stays_inside_the_harness_control_plane():
    """§28 — ANSWER.GROUND.LIVE.4 ownership covers the new keys."""

    from core.answer_entity_grounding import _ANSWER_SURFACE_KEYS

    matrix_keys = {
        key
        for key in pipeline._CANDIDATE_DEFECT_PROBE_KEYS
        if key.startswith("behavioral_matrix")
    }

    assert matrix_keys
    assert not (matrix_keys & _ANSWER_SURFACE_KEYS)


# ═══════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════


def test_the_phase_is_registered_with_its_measured_claim():
    from core.phase_registry import load_phase_registry

    data = load_phase_registry(
        str(ROOT / "docs" / "roadmap" / "phase_registry.json")
    )
    by_id = {item["phase_id"]: item for item in data["phases"]}
    phase = by_id["DEFECT.PROBE.LIVE.4"]

    assert phase["status"] == "complete"
    assert phase["model_calls_allowed"] is False
    assert phase["network_allowed"] is False
    assert phase["human_approval_required"] is True
    assert phase["merge_allowed"] is False
    assert "DEFECT.PROBE.LIVE.3" in phase["prerequisites"]
    assert "CANDIDATE.VERIFY.LIVE.1" in phase["prerequisites"]
    assert "PATCH.MINIMAL.LIVE.1" in phase["prerequisites"]

    text = " ".join(phase["notes"] + [phase["summary"]]).lower()
    for term in (
        "depth",
        "indentation unit",
        "matrix",
        "system-derived",
        "no execution authority",
        "no model call",
        "no network call",
        "safe_minimal",
        "_classify_indent",
    ):
        assert term.lower() in text, term

    ids = {item["phase_id"] for item in data["phases"]}
    for forbidden_phase in (
        # PATCH.MINIMAL.LIVE.3 completed on 2026-09-13 with authoritative
        # bindings and proven immutable result-field reads. The guard moves
        # to the next unused id; the matrix itself remains unchanged.
        "PATCH.MINIMAL.LIVE.4",
        # DEFECT.PROBE.LIVE.5 shipped on 2026-09-10 and appended the
        # distribution-skew case to this phase's matrix.  It is a real phase
        # now, so the "no phase invented itself here" guard moves on.
        "DEFECT.PROBE.LIVE.6",
        "DEFECT.PROBE.LIVE.4.PLAN",
    ):
        assert forbidden_phase not in ids
