"""DEFECT.PROBE.LIVE.3 — paired defect-fix and behavior-preservation oracle.

The subject of these tests is a single claim: a candidate may not be called
closed merely because the input the user complained about now produces the
value the user asked for.  The exact T6 branch-reorder candidate is the
counter-example the phase exists for, and it appears here verbatim.
"""

from __future__ import annotations

import ast
from dataclasses import replace
import hashlib
import inspect
import json
from pathlib import Path
from typing import Any

import pytest

import core.candidate_defect_probe as candidate_probe
import core.paired_defect_probe as paired_probe
import core.pipeline as pipeline
from core.behavioral_expectation import (
    PROVENANCE_EXPLICIT_USER_FACT,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    extract_behavioral_expectations,
)
from core.candidate_defect_probe import (
    CLOSURE_CHANGED_BUT_UNRESOLVED,
    CLOSURE_FIXED,
    CLOSURE_FIXED_BUT_REGRESSIVE,
    CLOSURE_INCONCLUSIVE,
    CLOSURE_INVALID_COMPARISON,
    CLOSURE_STATUSES,
    CLOSURE_STILL_REPRODUCED,
    CLOSURE_UNAVAILABLE,
    evaluate_candidate_defect_closure,
)
from core.check_oracle_assessment import (
    CheckOracleAssessment,
    CheckOracleAssessmentReceipt,
    ROLE_DEFECT_PRESERVATION_ORACLE,
    describe_check_oracle_assessment,
)
from core.code_dna import _classify_indent
from core.defect_probe import (
    EXECUTION_STAGE_PRE_PATCH,
    EXPECTATION_BASIS_REPOSITORY_CONTRACT,
    INPUT_BASIS_REPOSITORY_CONTRACT,
    PROBE_BASIS_REPOSITORY_CONTRACT,
    PROBE_NOT_REPRODUCED,
    PROBE_REPRODUCED,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    build_python_function_probe,
    execute_defect_probe,
    reproduced_probe_target,
)
from core.execution_eligibility_policy import (
    ELIGIBLE,
    INELIGIBLE,
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    PROFILE_FULL_VALIDATION_REQUIRED,
    evaluate_execution_eligibility,
)
from core.paired_defect_probe import (
    ORACLE_AVAILABLE,
    ORACLE_UNAVAILABLE,
    PAIRED_FIXED,
    PAIRED_FIXED_AND_PRESERVED,
    PAIRED_FIXED_BUT_REGRESSIVE,
    PAIRED_INCONCLUSIVE,
    PAIRED_INVALID_COMPARISON,
    PAIRED_STATUSES,
    PAIRED_STILL_REPRODUCED,
    PRESERVATION_PRESERVED,
    PRESERVATION_PROVENANCE,
    PRESERVATION_REGRESSED,
    PRESERVATION_UNAVAILABLE,
    REASON_BASELINE_NOT_SATISFIED,
    REASON_ORACLE_INTEGRITY,
    REASON_SUBJECT_UNSUPPORTED,
    build_preservation_cases,
    derive_paired_status,
    evaluate_paired_defect_closure,
    paired_defect_probe_guardrails,
    preservation_subject_supported,
)
from core.patch_basis import PATCH_BASIS_GROUNDED_DEFECT
from core.patch_safety import evaluate_patch_safety


ROOT = Path(__file__).resolve().parents[1]
T6_QUERY = "2-space indentation is classified as 4-space"
T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"

#: The exact branch ordering that ships today, and the two candidate rewrites
#: this phase has to tell apart.
T6_BASELINE_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
)
#: §6 — the model's minimal, safe_minimal-acceptable candidate.  It reverses the
#: prefix overlap instead of resolving it.
T6_REORDERED_BRANCHES = (
    '        if line.startswith("\\t"):\n'
    '            counts["tab"] += 1\n'
    '        elif line.startswith("  "):\n'
    '            counts["2space"] += 1\n'
    '        elif line.startswith("    "):\n'
    '            counts["4space"] += 1\n'
)


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


def _t6_plan(patched: str) -> list[dict[str, Any]]:
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert T6_BASELINE_BRANCHES in source
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": T6_BASELINE_BRANCHES,
            "patched_snippet": patched,
        }
    ]


def _t6_distinguishing_plan() -> list[dict[str, Any]]:
    """§7 positive control.  A fixture candidate, never applied to production.

    It resolves the overlap the real defect is made of by measuring the actual
    leading-space width rather than testing prefixes in an order, so it answers
    both widths correctly.
    """

    target = (
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
    patched = (
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
    assert target in (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    return [
        {
            "op": "replace_snippet",
            "relative_path": T6_TARGET_FILE,
            "target_snippet": target,
            "patched_snippet": patched,
        }
    ]


@pytest.fixture(scope="module")
def t6_regressive():
    """§6 — the branch-reorder candidate, measured once for every reader."""

    return _t6_paired(_t6_plan(T6_REORDERED_BRANCHES))


@pytest.fixture(scope="module")
def t6_distinguishing():
    """§7 — the width-distinguishing positive control, measured once."""

    return _t6_paired(_t6_distinguishing_plan())


def _t6_paired(plan: list[dict[str, Any]], **kwargs):
    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    assert pre.probe_result == PROBE_REPRODUCED
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
        **kwargs,
    )
    # Candidate bytes exist only in the disposable sandbox, and both halves of
    # the pair read them there.  Guarded on every T6 run, not just one test.
    assert (ROOT / T6_TARGET_FILE).read_bytes() == before
    assert paired.closure.sandbox_only is True
    return contract, pre, paired


# ---------------------------------------------------------------------------
# The subject adapter
# ---------------------------------------------------------------------------


def test_indentation_preservation_case_is_the_collision_partner_not_a_user_claim():
    fact = _t6_behavior_fact()
    cases = build_preservation_cases(target=_t6_binding(), behavior_fact=fact)

    assert len(cases) == 1
    case = cases[0]
    assert case.subject_kind == SUBJECT_INDENTATION_STYLE
    # §1/§4 — the counter-case expects the value the *baseline* already produces
    # for its own width, which is the user's claimed observed value.
    assert case.expected == fact.observed_value == "4space"
    assert case.contract.expected == "4space"
    # §9 — never labelled as something the user asked for.
    assert case.provenance == PRESERVATION_PROVENANCE
    assert case.provenance != PROVENANCE_EXPLICIT_USER_FACT
    assert "not a user requirement" in case.contract.provenance_reference
    assert "2space" in case.contract.provenance_reference


def test_preservation_case_reuses_the_frozen_fixture_generator():
    from core.defect_probe import _nested_indentation_fixture

    cases = build_preservation_cases(
        target=_t6_binding(), behavior_fact=_t6_behavior_fact()
    )
    (fixture,) = cases[0].contract.structured_input["args"]
    # §2 — the same generator, at the claimed observed width.  No second
    # indentation fixture builder exists anywhere in this phase.
    assert fixture == _nested_indentation_fixture(4)
    assert fixture != _nested_indentation_fixture(2)
    source = inspect.getsource(paired_probe)
    assert "def _nested_indentation_fixture" not in source
    assert source.count("_nested_indentation_fixture(") == 1


def test_primary_and_preservation_cases_probe_the_same_target_with_distinct_oracles():
    contract = _t6_contract()
    case = build_preservation_cases(
        target=contract.target, behavior_fact=_t6_behavior_fact()
    )[0]

    assert case.contract.target == contract.target
    assert case.contract.invocation_kind == contract.invocation_kind
    assert case.contract.side_effect_policy == contract.side_effect_policy
    assert case.contract.fingerprint != contract.fingerprint
    assert case.contract.expected != contract.expected


def test_unsupported_subject_and_untyped_transport_have_no_preservation_oracle():
    binding = _t6_binding()
    assert build_preservation_cases(target=binding, behavior_fact=None) == ()
    assert preservation_subject_supported(SUBJECT_INDENTATION_STYLE) is True
    assert preservation_subject_supported("naming_convention") is False
    assert preservation_subject_supported("") is False

    # §8 — an adapter is added by declaring one, never by generalising.  A fact
    # whose subject is absent from the table yields nothing at all.
    fact = _t6_behavior_fact()
    unsupported = object.__new__(BehavioralExpectation)
    object.__setattr__(unsupported, "subject_kind", "naming_convention")
    object.__setattr__(unsupported, "expected_value", "snake_case")
    object.__setattr__(unsupported, "observed_value", "camelCase")
    object.__setattr__(unsupported, "relation", fact.relation)
    object.__setattr__(unsupported, "provenance", fact.provenance)
    object.__setattr__(unsupported, "source_text", fact.source_text)
    object.__setattr__(unsupported, "source_start", 0)
    object.__setattr__(unsupported, "source_end", 1)
    object.__setattr__(unsupported, "obligation_ordinal", None)
    object.__setattr__(unsupported, "authoritative", True)
    object.__setattr__(unsupported, "schema_version", fact.schema_version)
    assert build_preservation_cases(target=binding, behavior_fact=unsupported) == ()


# ---------------------------------------------------------------------------
# §6 — the exact T6 wrong candidate
# ---------------------------------------------------------------------------


def test_t6_baseline_reproduces_the_defect_and_already_satisfies_the_counter_case():
    contract = _t6_contract()
    case = build_preservation_cases(
        target=contract.target, behavior_fact=_t6_behavior_fact()
    )[0]

    primary = execute_defect_probe(contract, repo_path=ROOT)
    preservation = execute_defect_probe(
        case.contract, repo_path=ROOT, execution_stage=EXECUTION_STAGE_PRE_PATCH
    )

    # The claimed defect is real at two spaces …
    assert primary.probe_result == PROBE_REPRODUCED
    assert primary.observed == "4space"
    assert primary.expected == "2space"
    # … and the four-space behavior it collides with is already correct, which
    # is precisely what makes it a usable preservation oracle (§4).
    assert preservation.probe_result == PROBE_NOT_REPRODUCED
    assert preservation.observed == "4space"
    assert preservation.expected == "4space"


def test_t6_branch_reorder_candidate_is_fixed_and_regressive_not_closed(
    t6_regressive,
):
    _contract, _pre, paired = t6_regressive

    # §6 primary — the single-case probe is genuinely satisfied.
    primary = paired.primary_case()
    assert primary["expected"] == "2space"
    assert primary["baseline_observed"] == "4space"
    assert primary["candidate_observed"] == "2space"
    assert primary["status"] == CLOSURE_FIXED
    assert paired.primary_status == CLOSURE_FIXED

    # §6 preservation — the four-space behavior the baseline had is gone.
    (case,) = paired.preservation_cases
    assert case.expected == "4space"
    assert case.baseline_observed == "4space"
    assert case.candidate_observed == "2space"
    assert case.status == PRESERVATION_REGRESSED
    assert case.provenance == PRESERVATION_PROVENANCE
    assert paired.preservation_oracle_status == ORACLE_AVAILABLE

    # §6/§17 — the closed assessment, and the field every existing consumer
    # reads, both refuse to call this fixed.
    assert paired.paired_status == PAIRED_FIXED_BUT_REGRESSIVE
    assert paired.defect_closure_status == CLOSURE_FIXED_BUT_REGRESSIVE
    assert paired.defect_closure_status != CLOSURE_FIXED
    assert paired.closure_ready is False
    assert "did not survive" in paired.closure.reason

    # §15 — the sandbox was disposable and the real repository never moved.
    assert paired.closure.sandbox_only is True
    assert paired.closure.sandbox_cleanup_ok is True
    assert _classify_indent("root\n  a\n    b\n      c\n    d\n  e\n") == "4space"


def test_t6_regressive_candidate_is_never_execution_or_review_eligible(
    t6_regressive,
):
    _contract, pre, paired = t6_regressive
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)
    fingerprint = paired.closure.candidate_fingerprint

    eligibility = evaluate_execution_eligibility(
        {
            "task_route": "defect_repair",
            "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
            "source_target_grounded": True,
            "candidate_fingerprint": fingerprint,
            "patch_safety": {**safety, "candidate_fingerprint": fingerprint},
            "full_validation": {
                "outcome": "inconclusive",
                "category": "validation_budget_exhausted",
            },
            "pre_probe": pre.as_dict(),
            "candidate_defect_closure": paired.as_telemetry(),
        }
    )

    # §13 — paired evidence grants nothing, and here it withholds what the
    # single-case receipt would have handed over.
    assert eligibility.human_review_eligible is False
    assert eligibility.assessment_for(
        PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW
    ).eligibility_status == INELIGIBLE
    assert eligibility.assessment_for(
        PROFILE_FULL_VALIDATION_REQUIRED
    ).eligibility_status == INELIGIBLE
    assert paired.as_telemetry()["paired_probe_authority_effect"] == "none"
    assert paired.as_telemetry()["candidate_probe_authority_effect"] == "none"


def test_single_case_closure_alone_would_still_call_the_wrong_candidate_fixed():
    """The measurement this phase was opened on, kept as a live regression."""

    contract = _t6_contract()
    pre = execute_defect_probe(contract, repo_path=ROOT)
    safety = evaluate_patch_safety([T6_TARGET_FILE], project_root=ROOT)

    single = evaluate_candidate_defect_closure(
        repo_path=ROOT,
        candidate_plan=_t6_plan(T6_REORDERED_BRANCHES),
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety=safety,
    )

    # DEFECT.PROBE.LIVE.2 on its own is unchanged — it still answers the one
    # question it was ever asked, and that answer is still ``fixed``.  The
    # weakness was never in this function; it was in stopping here.
    assert single.defect_closure_status == CLOSURE_FIXED
    assert single.post_probe_observed == "2space"
    assert single.preservation_probe_receipts == ()


# ---------------------------------------------------------------------------
# §7 — positive control
# ---------------------------------------------------------------------------


def test_t6_width_distinguishing_candidate_is_fixed_and_preserved(
    t6_distinguishing,
):
    _contract, _pre, paired = t6_distinguishing

    assert paired.primary_status == CLOSURE_FIXED
    assert paired.primary_case()["candidate_observed"] == "2space"
    (case,) = paired.preservation_cases
    assert case.baseline_observed == "4space"
    assert case.candidate_observed == "4space"
    assert case.status == PRESERVATION_PRESERVED
    assert paired.preservation_oracle_status == ORACLE_AVAILABLE

    # §7 — the oracle can open, not merely reject.  And the field existing
    # consumers read still says ``fixed``, so nothing a correct candidate had
    # before this phase was taken away from it (§14).
    assert paired.paired_status == PAIRED_FIXED_AND_PRESERVED
    assert paired.defect_closure_status == CLOSURE_FIXED
    assert paired.closure_ready is True


def test_correct_and_regressive_candidates_are_distinguished_by_preservation_only(
    t6_distinguishing, t6_regressive
):
    """Both candidates fix the primary case; only one keeps the other width."""

    good = t6_distinguishing[2]
    bad = t6_regressive[2]

    assert good.primary_status == bad.primary_status == CLOSURE_FIXED
    assert good.primary_case()["candidate_observed"] == "2space"
    assert bad.primary_case()["candidate_observed"] == "2space"
    assert good.paired_status != bad.paired_status
    assert good.closure_ready is True and bad.closure_ready is False


def test_paired_results_are_deterministic_across_repeated_runs(t6_regressive):
    def facts(receipt):
        telemetry = receipt.as_telemetry()
        return {
            "paired_status": telemetry["paired_status"],
            "defect_closure_status": telemetry["defect_closure_status"],
            "primary_case": telemetry["primary_case"],
            "preservation_cases": telemetry["preservation_cases"],
            "preservation_oracle_status": telemetry["preservation_oracle_status"],
            "probe_fingerprint": telemetry["probe_fingerprint"],
            "candidate_fingerprint": telemetry["candidate_fingerprint"],
        }

    first = t6_regressive[2]
    _contract, _pre, second = _t6_paired(_t6_plan(T6_REORDERED_BRANCHES))
    assert facts(first) == facts(second)
    assert json.dumps(facts(first), sort_keys=True)


# ---------------------------------------------------------------------------
# §4 — the baseline precondition
# ---------------------------------------------------------------------------


def _synthetic_fixture(tmp_path: Path, source: str):
    """A bounded stand-in target, so preconditions can be tested in isolation."""

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


def _synthetic_case(binding, *, args, expected, case_id="synthetic.preserve"):
    return paired_probe.PreservationCase(
        case_id=case_id,
        subject_kind="synthetic",
        expected=expected,
        contract=_synthetic_contract(binding, args=args, expected=expected),
        derivation="bounded fixture counter-case",
    )


def test_baseline_failing_the_counter_case_yields_no_preservation_oracle(tmp_path):
    # ``add`` is wrong for (2, 2) and wrong for (5, 1) alike, so the second case
    # is not a preservation oracle at all: nothing about it was ever correct.
    binding = _synthetic_fixture(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    assert pre.probe_result == PROBE_REPRODUCED

    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()
    paired = evaluate_paired_defect_closure(
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
        preservation_cases=[_synthetic_case(binding, args=(5, 1), expected=6)],
        sandbox_parent=sandbox_parent,
    )

    (case,) = paired.preservation_cases
    # §4 — explicitly unavailable, never counted as a regression, and never
    # counted as a preservation either.
    assert case.status == PRESERVATION_UNAVAILABLE
    assert case.reason == REASON_BASELINE_NOT_SATISFIED
    assert case.baseline_result == PROBE_REPRODUCED
    assert case.candidate_result == ""
    assert paired.preservation_oracle_status == ORACLE_UNAVAILABLE
    # §14 — with no usable oracle the single-case meaning stands untouched.
    assert paired.primary_status == CLOSURE_FIXED
    assert paired.paired_status == PAIRED_FIXED
    assert paired.defect_closure_status == CLOSURE_FIXED
    assert not list(sandbox_parent.iterdir())


def test_baseline_satisfied_counter_case_that_survives_is_preserved(tmp_path):
    binding = _synthetic_fixture(
        tmp_path, "def add(a, b):\n    return 4 if a == 9 else a + b\n"
    )
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    # The defect is narrow: only (9, 9) is wrong.
    broken = _synthetic_contract(binding, args=(9, 9), expected=18)
    pre = execute_defect_probe(broken, repo_path=tmp_path)
    assert pre.probe_result == PROBE_REPRODUCED
    assert execute_defect_probe(contract, repo_path=tmp_path).probe_result == (
        PROBE_NOT_REPRODUCED
    )

    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()
    paired = evaluate_paired_defect_closure(
        repo_path=tmp_path,
        candidate_plan=[
            {
                "op": "replace_snippet",
                "relative_path": "calc.py",
                "target_snippet": "    return 4 if a == 9 else a + b\n",
                "patched_snippet": "    return a + b\n",
            }
        ],
        probe_contract=broken,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        preservation_cases=[_synthetic_case(binding, args=(2, 2), expected=4)],
        sandbox_parent=sandbox_parent,
    )

    (case,) = paired.preservation_cases
    assert case.baseline_result == PROBE_NOT_REPRODUCED
    assert case.candidate_observed == 4
    assert case.status == PRESERVATION_PRESERVED
    assert paired.paired_status == PAIRED_FIXED_AND_PRESERVED
    assert paired.defect_closure_status == CLOSURE_FIXED


def test_counter_case_not_bound_to_the_primary_probe_is_refused(tmp_path):
    binding = _synthetic_fixture(tmp_path, "def add(a, b):\n    return a - b\n")
    other = tmp_path / "other"
    other.mkdir()
    foreign_binding = _synthetic_fixture(other, "def add(a, b):\n    return a + b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)

    sandbox_parent = tmp_path.parent / f"{tmp_path.name}-sandboxes"
    sandbox_parent.mkdir()
    paired = evaluate_paired_defect_closure(
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
        preservation_cases=[
            _synthetic_case(foreign_binding, args=(1, 1), expected=2),
            # A "counter-case" identical to the primary proves nothing twice.
            _synthetic_case(binding, args=(2, 2), expected=4, case_id="echo"),
        ],
        sandbox_parent=sandbox_parent,
    )

    assert {item.status for item in paired.preservation_cases} == {
        PRESERVATION_UNAVAILABLE
    }
    assert {item.reason for item in paired.preservation_cases} == {
        REASON_ORACLE_INTEGRITY
    }
    assert paired.preservation_oracle_status == ORACLE_UNAVAILABLE
    assert paired.paired_status == PAIRED_FIXED


# ---------------------------------------------------------------------------
# Paired derivation and vocabulary
# ---------------------------------------------------------------------------


def _case(status: str) -> paired_probe.PreservationCaseResult:
    return paired_probe.PreservationCaseResult(
        case_id="c",
        subject_kind=SUBJECT_INDENTATION_STYLE,
        expected="4space",
        status=status,
        baseline_result=PROBE_NOT_REPRODUCED,
    )


@pytest.mark.parametrize(
    "primary, cases, expected",
    [
        (CLOSURE_FIXED, (), PAIRED_FIXED),
        (CLOSURE_FIXED, (PRESERVATION_PRESERVED,), PAIRED_FIXED_AND_PRESERVED),
        (CLOSURE_FIXED, (PRESERVATION_REGRESSED,), PAIRED_FIXED_BUT_REGRESSIVE),
        (
            CLOSURE_FIXED,
            (PRESERVATION_PRESERVED, PRESERVATION_REGRESSED),
            PAIRED_FIXED_BUT_REGRESSIVE,
        ),
        (CLOSURE_FIXED, (PRESERVATION_UNAVAILABLE,), PAIRED_FIXED),
        (CLOSURE_FIXED, ("inconclusive",), PAIRED_INCONCLUSIVE),
        (CLOSURE_STILL_REPRODUCED, (PRESERVATION_REGRESSED,), PAIRED_STILL_REPRODUCED),
        (
            CLOSURE_CHANGED_BUT_UNRESOLVED,
            (PRESERVATION_PRESERVED,),
            CLOSURE_CHANGED_BUT_UNRESOLVED,
        ),
        (CLOSURE_INVALID_COMPARISON, (), PAIRED_INVALID_COMPARISON),
        (CLOSURE_UNAVAILABLE, (), CLOSURE_UNAVAILABLE),
    ],
)
def test_paired_status_derivation_is_closed_and_never_upgrades(primary, cases, expected):
    assert derive_paired_status(primary, [_case(item) for item in cases]) == expected


def test_fixed_is_never_overloaded_and_regression_has_its_own_status():
    # §5 — the two meanings are separate values, and both are reachable.
    assert PAIRED_FIXED_BUT_REGRESSIVE != PAIRED_FIXED
    assert PAIRED_FIXED_BUT_REGRESSIVE != PAIRED_FIXED_AND_PRESERVED
    assert PAIRED_FIXED_AND_PRESERVED not in CLOSURE_STATUSES
    assert CLOSURE_FIXED_BUT_REGRESSIVE in CLOSURE_STATUSES
    assert set(PAIRED_STATUSES) >= {
        PAIRED_FIXED_AND_PRESERVED,
        PAIRED_FIXED_BUT_REGRESSIVE,
        PAIRED_STILL_REPRODUCED,
        CLOSURE_CHANGED_BUT_UNRESOLVED,
        CLOSURE_INCONCLUSIVE,
        CLOSURE_INVALID_COMPARISON,
    }
    assert paired_probe.NON_CLOSING_PAIRED_STATUSES == frozenset(
        {
            PAIRED_FIXED_BUT_REGRESSIVE,
            PAIRED_STILL_REPRODUCED,
            CLOSURE_CHANGED_BUT_UNRESOLVED,
            CLOSURE_INCONCLUSIVE,
            CLOSURE_INVALID_COMPARISON,
            CLOSURE_UNAVAILABLE,
        }
    )


def test_a_preservation_result_may_not_claim_user_provenance():
    with pytest.raises(ValueError):
        replace(_case(PRESERVATION_PRESERVED), provenance=PROVENANCE_EXPLICIT_USER_FACT)
    with pytest.raises(ValueError):
        replace(_case(PRESERVATION_PRESERVED), status="closed")


def test_paired_receipt_rejects_statuses_outside_its_vocabulary():
    receipt = paired_probe.PairedDefectProbeReceipt(
        closure=candidate_probe.CandidateDefectClosureReceipt(
            probe_fingerprint="a" * 64,
            candidate_fingerprint="b" * 64,
            pre_probe_result=PROBE_REPRODUCED,
            pre_probe_observed="4space",
            post_probe_result=PROBE_NOT_REPRODUCED,
            post_probe_observed="2space",
            expected_behavior_basis=EXPECTATION_BASIS_REPOSITORY_CONTRACT,
            defect_closure_status=CLOSURE_FIXED,
        ),
        primary_status=CLOSURE_FIXED,
        paired_status=PAIRED_FIXED,
        preservation_oracle_status=ORACLE_UNAVAILABLE,
    )
    assert receipt.closure_ready is True
    with pytest.raises(ValueError):
        replace(receipt, paired_status="approved")
    with pytest.raises(ValueError):
        replace(receipt, preservation_oracle_status="granted")


# ---------------------------------------------------------------------------
# §12 telemetry, §10 patch basis, §11 VALIDATE.ORACLE, §14 compatibility
# ---------------------------------------------------------------------------


def test_telemetry_is_additive_bounded_and_carries_no_source_or_confidence(
    t6_regressive,
):
    paired = t6_regressive[2]
    telemetry = paired.as_telemetry()
    single = paired.closure.as_telemetry()

    # Additive: DEFECT.PROBE.LIVE.2's own keys are all still there, unchanged.
    for key, value in single.items():
        assert telemetry[key] == value

    assert telemetry["paired_status"] == PAIRED_FIXED_BUT_REGRESSIVE
    assert set(telemetry["primary_case"]) == {
        "expected",
        "baseline_observed",
        "candidate_observed",
        "baseline_result",
        "candidate_result",
        "status",
        "provenance",
    }
    (case,) = telemetry["preservation_cases"]
    assert set(case) == {
        "case_id",
        "subject_kind",
        "expected",
        "baseline_observed",
        "baseline_result",
        "candidate_observed",
        "candidate_result",
        "status",
        "provenance",
        "reason",
    }
    assert case["provenance"] == PRESERVATION_PROVENANCE

    # §12/§13 — no source dumps, no confidence, no authority.
    blob = json.dumps(telemetry)
    assert "def _classify_indent" not in blob
    assert "counts[" not in blob
    for forbidden in (
        "confidence",
        "score",
        "write_authority",
        "execution_authorized",
        "human_review_eligible",
        "auto_apply",
    ):
        assert forbidden not in blob
    assert telemetry["paired_probe_authority_effect"] == "none"


def test_preservation_regression_does_not_erase_the_grounded_baseline_defect(
    t6_regressive,
):
    _contract, pre, paired = t6_regressive

    # §10 — the pre-patch reproduction is a historical fact about the
    # repository, not about the candidate.  A regressive candidate cannot
    # retroactively unground it.
    assert reproduced_probe_target(pre.as_dict()) == {
        "file": T6_TARGET_FILE,
        "symbol": T6_TARGET_SYMBOL,
        "relation": "bounded_reproduction_bound",
    }
    assert paired.closure.pre_probe_result == PROBE_REPRODUCED
    assert paired.as_telemetry()["pre_probe_observed"] == "4space"
    assert paired.paired_status == PAIRED_FIXED_BUT_REGRESSIVE


def test_validate_oracle_never_reports_a_regressive_candidate_as_fixed():
    def receipt(status: str) -> CheckOracleAssessmentReceipt:
        assessment = CheckOracleAssessment(
            check_id="tests/t.py::test_x",
            check_execution_outcome="failed",
            oracle_role=ROLE_DEFECT_PRESERVATION_ORACLE,
            probe_fingerprint="a" * 64,
            role_basis="supported assertion agrees with the previous behavior",
            check_path="tests/t.py",
            check_source_sha256="d" * 64,
            check_fingerprint="e" * 64,
        )
        return CheckOracleAssessmentReceipt(
            assessments=(assessment,),
            probe_fingerprint="a" * 64,
            targeted_check_set_fingerprint="b" * 64,
            candidate_fingerprint="c" * 64,
            assessment_status="current",
            evidence_matrix={
                "post_probe": {
                    "result": PROBE_NOT_REPRODUCED,
                    "observed": "2space",
                    "defect_closure_status": status,
                },
                "targeted_validation": {"outcome": "failed"},
            },
        )

    regressive = describe_check_oracle_assessment(receipt(CLOSURE_FIXED_BUT_REGRESSIVE))
    assert "not fixed" in regressive
    assert "did not survive" in regressive
    # §11 — the existing wording for a genuinely fixed candidate is untouched.
    assert describe_check_oracle_assessment(receipt(CLOSURE_FIXED)) == (
        "The defect-specific probe is fixed, but existing targeted checks "
        "failed; the supported assertions preserve the previously observed behavior."
    )


def test_execution_policy_reads_regressive_closure_as_not_fixed():
    def eligibility(status: str):
        return evaluate_execution_eligibility(
            {
                "task_route": "defect_repair",
                "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
                "source_target_grounded": True,
                "candidate_fingerprint": "c" * 64,
                "candidate_defect_closure": {
                    "probe_fingerprint": "a" * 64,
                    "candidate_fingerprint": "c" * 64,
                    "post_probe_result": PROBE_NOT_REPRODUCED,
                    "defect_closure_status": status,
                    "sandbox_only": True,
                    "candidate_probe_apply_status": "applied",
                    "candidate_probe_sandbox_cleanup_ok": True,
                },
            }
        )

    blocked = eligibility(CLOSURE_FIXED_BUT_REGRESSIVE)
    allowed = eligibility(CLOSURE_FIXED)
    reasons = json.dumps(blocked.as_telemetry(), default=str)
    assert "post_probe" in reasons
    assert blocked.human_review_eligible is False
    # The only difference between the two payloads is the closure status, so
    # anything the regressive one loses, it loses because of that status.
    assert allowed.as_telemetry() != blocked.as_telemetry()


def test_unsupported_subject_keeps_the_existing_single_case_behavior(tmp_path):
    """§14 — T1/T2/T3-shaped tasks reach exactly the receipt they reached before."""

    binding = _synthetic_fixture(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)
    plan = [
        {
            "op": "replace_snippet",
            "relative_path": "calc.py",
            "target_snippet": "    return a - b\n",
            "patched_snippet": "    return a + b\n",
        }
    ]

    single = evaluate_candidate_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
    )
    paired = evaluate_paired_defect_closure(
        repo_path=tmp_path,
        candidate_plan=plan,
        probe_contract=contract,
        pre_probe_receipt=pre,
        patch_safety={"ok": True},
        behavior_fact=None,
    )

    assert paired.preservation_cases == ()
    assert paired.preservation_oracle_status == ORACLE_UNAVAILABLE
    assert paired.preservation_oracle_reason == REASON_SUBJECT_UNSUPPORTED
    assert paired.paired_status == PAIRED_FIXED
    ignore = {"candidate_probe_timings", "paired_probe_timings"}
    assert {
        key: value
        for key, value in paired.closure.as_telemetry().items()
        if key not in ignore
    } == {
        key: value for key, value in single.as_telemetry().items() if key not in ignore
    }


def test_unsafe_candidate_is_never_probed_and_reports_no_preservation_oracle(tmp_path):
    binding = _synthetic_fixture(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)

    paired = evaluate_paired_defect_closure(
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
        patch_safety={"ok": False, "reasons": ["unsafe"]},
        preservation_cases=[_synthetic_case(binding, args=(1, 1), expected=2)],
    )

    assert paired.defect_closure_status == CLOSURE_UNAVAILABLE
    assert paired.paired_status == CLOSURE_UNAVAILABLE
    assert paired.preservation_cases == ()
    assert paired.preservation_oracle_status == ORACLE_UNAVAILABLE
    assert paired.closure.candidate_apply_status == "not_attempted"


def test_stale_candidate_binding_stays_an_invalid_comparison(tmp_path):
    binding = _synthetic_fixture(tmp_path, "def add(a, b):\n    return a - b\n")
    contract = _synthetic_contract(binding, args=(2, 2), expected=4)
    pre = execute_defect_probe(contract, repo_path=tmp_path)

    paired = evaluate_paired_defect_closure(
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
        expected_candidate_fingerprint="d" * 64,
        preservation_cases=[_synthetic_case(binding, args=(1, 1), expected=2)],
    )

    assert paired.defect_closure_status == CLOSURE_INVALID_COMPARISON
    assert paired.paired_status == PAIRED_INVALID_COMPARISON


# ---------------------------------------------------------------------------
# §15 static boundaries
# ---------------------------------------------------------------------------


def test_paired_module_has_no_provider_network_or_traversal_surface():
    source = inspect.getsource(paired_probe)
    tree = ast.parse(source)

    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.add(node.module or "")
    for forbidden in (
        "requests",
        "httpx",
        "socket",
        "urllib",
        "urllib.request",
        "openai",
        "anthropic",
        "google.generativeai",
        "ollama",
        "subprocess",
        "os",
        "core.control_engine",
        "core.identifier_recall",
        "graph.builder",
    ):
        assert forbidden not in imported, forbidden

    forbidden_calls = {
        "eval",
        "exec",
        "compile",
        "open",
        "rglob",
        "glob",
        "walk",
        "scandir",
        "system",
        "popen",
        "run",
        "check_output",
        "Popen",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            assert name not in forbidden_calls, name

    # It never fixes the production classifier, and never authors a candidate.
    for forbidden in ("code_dna", "startswith(", "patched_snippet", "target_snippet"):
        assert forbidden not in source


def test_guardrails_state_what_this_phase_did_not_do():
    guardrails = paired_defect_probe_guardrails()
    assert guardrails["existing_fixture_generator_reused"] is True
    assert guardrails["preservation_baseline_precondition_required"] is True
    for never in (
        "preservation_expectation_labeled_user_supplied",
        "single_case_fixed_can_close_a_regressive_candidate",
        "probe_execution_primitive_changed",
        "candidate_authoring_changed",
        "safe_minimal_changed",
        "control_ranking_changed",
        "retrieval_changed",
        "behavioral_expectation_extraction_changed",
        "patch_basis_created",
        "grounded_defect_basis_erased",
        "human_review_eligibility_granted",
        "write_authority_granted",
        "execution_authorized",
        "auto_apply_granted",
        "model_called",
        "network_called",
        "repository_traversal_added",
        "production_classifier_fixed",
    ):
        assert guardrails[never] is False, never

    closure_guardrails = candidate_probe.candidate_defect_probe_guardrails()
    assert closure_guardrails["preservation_probes_share_the_primary_sandbox"] is True
    assert closure_guardrails["preservation_receipt_read_by_this_module"] is False
    assert closure_guardrails["execution_authority_granted"] is False


def test_frozen_probe_execution_and_authority_surfaces_are_unchanged():
    """The pieces this phase was forbidden to touch, pinned by AST digest."""

    pins = json.loads(
        (ROOT / "tests/fixtures/defect_probe_live3_frozen_boundaries.json").read_text(
            encoding="utf-8"
        )
    )
    from _harness_maintenance import before_harness_remediation

    # The explicitly requested harness remediation (2026-09-11) edited some of
    # these files after this phase froze them; its receipt undoes exactly those
    # edits, so the pin is checked against history and is never re-pinned.
    for relative, digest in pins["files"].items():
        actual = hashlib.sha256(before_harness_remediation(relative)).hexdigest()
        assert actual == digest, relative

    import core.candidate_defect_probe as closure_module

    for name, digest in pins["candidate_closure_functions"].items():
        node = ast.parse(inspect.getsource(getattr(closure_module, name))).body[0]
        actual = hashlib.sha256(
            ast.dump(node, include_attributes=False).encode()
        ).hexdigest()
        assert actual == digest, name


def test_production_indent_classifier_is_still_broken_and_untouched():
    # §15 — this phase measures the defect; it does not repair it, and every
    # sandbox above was disposable, so the real bytes are still the broken ones.
    assert _classify_indent("root\n  a\n    b\n      c\n      d\n    e\n  f\n") == (
        "4space"
    )
    source = (ROOT / T6_TARGET_FILE).read_text(encoding="utf-8")
    assert T6_BASELINE_BRANCHES in source
    assert T6_REORDERED_BRANCHES not in source


# ---------------------------------------------------------------------------
# Live pipeline adapter
# ---------------------------------------------------------------------------

#: A bounded stand-in for the production classifier, carrying the same prefix
#: overlap so a reordering candidate reproduces the T6 shape without touching
#: core/code_dna.py or copying the whole repository.
_OVERLAPPING_CLASSIFIER = (
    "from collections import Counter\n"
    "\n"
    "\n"
    "def classify_indent(text):\n"
    "    counts = Counter()\n"
    "    for line in text.splitlines():\n"
    "        if not line or line[0] != ' ':\n"
    "            continue\n"
    "        if line.startswith('    '):\n"
    "            counts['4space'] += 1\n"
    "        elif line.startswith('  '):\n"
    "            counts['2space'] += 1\n"
    "    return counts.most_common(1)[0][0] if counts else None\n"
)
_OVERLAP_BRANCHES = (
    "        if line.startswith('    '):\n"
    "            counts['4space'] += 1\n"
    "        elif line.startswith('  '):\n"
    "            counts['2space'] += 1\n"
)
_REORDERED_BRANCHES = (
    "        if line.startswith('  '):\n"
    "            counts['2space'] += 1\n"
    "        elif line.startswith('    '):\n"
    "            counts['4space'] += 1\n"
)


def _typed_control(repo: Path) -> dict[str, Any]:
    """A CONTROL result carrying the typed fact, exactly as DEFECT.FACT.LIVE.1 does."""

    (repo / "indent.py").write_text(_OVERLAPPING_CLASSIFIER, encoding="utf-8")
    binding = build_probe_target_binding(
        repo_path=repo,
        target_file="indent.py",
        target_symbol="classify_indent",
        source_snippet=_OVERLAPPING_CLASSIFIER.strip(),
        candidate_eligible=True,
    )
    assert binding is not None
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_t6_behavior_fact()
    )
    assert contract is not None
    pre = execute_defect_probe(contract, repo_path=repo)
    assert pre.probe_result == PROBE_REPRODUCED
    assert pre.observed == "4space"
    return {
        "query": T6_QUERY,
        "repo_path": str(repo),
        "live_route": {
            "selected_workflow": "defect_repair_patch",
            "preservation_passed": True,
            "behavioral_expectations": [_t6_behavior_fact().as_dict()],
        },
        "preflight_validation": {
            "outcome": "inconclusive",
            "category": "validation_budget_exhausted",
        },
        "patch_intent": {
            "target_file": "indent.py",
            "target_symbol": "classify_indent",
            "target_symbol_full": "indent.py::classify_indent",
            "source_snippet": _OVERLAPPING_CLASSIFIER.strip(),
        },
        "entry_resolution": {"resolved_entry_nodes": ["indent.py::classify_indent"]},
        "defect_probe": pre.as_dict(),
    }


def _pipeline_state(repo: Path, control: dict[str, Any], plan: list[dict[str, Any]]):
    from core.agent_state import AgentState

    state = AgentState(
        interface="agent",
        mode="control",
        user_input=f"Fix this bug: {T6_QUERY}",
        file_paths=[str(repo)],
        primary_file=None,
        input_mode="project",
        language="python",
        task_type="bug_fix",
        repo_path=str(repo),
        is_project_input=True,
        live_route=control["live_route"],
    )
    state.control_result = control
    state.json_block = {
        "patch_basis": PATCH_BASIS_GROUNDED_DEFECT,
        "patch_plan": plan,
        "targeted_validation_status": "failed",
        "full_validation_outcome": "inconclusive",
        "full_validation_category": "validation_budget_exhausted",
        "execution_authorized": False,
        "write_authority": False,
        "human_review_eligible": False,
    }
    return state


def _record(state, repo: Path):
    from types import SimpleNamespace

    return pipeline._record_candidate_defect_closure(
        state,
        SimpleNamespace(patch_basis=PATCH_BASIS_GROUNDED_DEFECT),
        repo,
        patch_safety={"ok": True},
    )


def _reorder_plan() -> list[dict[str, Any]]:
    return [
        {
            "op": "replace_snippet",
            "relative_path": "indent.py",
            "target_snippet": _OVERLAP_BRANCHES,
            "patched_snippet": _REORDERED_BRANCHES,
        }
    ]


def test_live_adapter_records_the_pair_and_rewrites_no_other_fact(tmp_path):
    control = _typed_control(tmp_path)
    state = _pipeline_state(tmp_path, control, _reorder_plan())

    result = _record(state, tmp_path)

    assert result is not None
    block = state.json_block
    assert block["paired_status"] == PAIRED_FIXED_BUT_REGRESSIVE
    assert block["defect_closure_status"] == CLOSURE_FIXED_BUT_REGRESSIVE
    assert block["primary_case"]["status"] == CLOSURE_FIXED
    assert block["primary_case"]["candidate_observed"] == "2space"
    (case,) = block["preservation_cases"]
    assert case["status"] == PRESERVATION_REGRESSED
    assert case["baseline_observed"] == "4space"
    assert case["candidate_observed"] == "2space"
    assert case["provenance"] == PRESERVATION_PROVENANCE
    assert block["preservation_oracle_status"] == ORACLE_AVAILABLE

    # Every other fact on the payload is exactly what it was.
    assert block["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
    assert block["targeted_validation_status"] == "failed"
    assert block["full_validation_outcome"] == "inconclusive"
    assert block["full_validation_category"] == "validation_budget_exhausted"
    assert block["execution_authorized"] is False
    assert block["write_authority"] is False
    assert block["human_review_eligible"] is False
    assert block["paired_probe_authority_effect"] == "none"
    assert state.patch_policy["paired_status"] == PAIRED_FIXED_BUT_REGRESSIVE
    # The probe never wrote to the repository it read.
    assert (tmp_path / "indent.py").read_text(encoding="utf-8") == (
        _OVERLAPPING_CLASSIFIER
    )


def test_a_refinement_discards_the_paired_facts_with_the_candidate(tmp_path):
    control = _typed_control(tmp_path)
    state = _pipeline_state(tmp_path, control, _reorder_plan())
    _record(state, tmp_path)
    assert "paired_status" in state.json_block

    # A refinement rewrites the plan, so every candidate-bound fact — paired
    # ones included — must leave rather than sit next to a plan it never
    # measured.
    state.json_block["patch_plan"] = [
        {
            "op": "replace_snippet",
            "relative_path": "indent.py",
            "target_snippet": _OVERLAP_BRANCHES,
            "patched_snippet": _OVERLAP_BRANCHES.replace("4space", "four_space"),
        }
    ]
    pipeline._drop_stale_candidate_validation(state)

    for key in (
        "paired_status",
        "primary_case",
        "preservation_cases",
        "preservation_oracle_status",
        "preservation_oracle_reason",
        "paired_probe_schema_version",
        "paired_probe_timings",
        "paired_probe_authority_effect",
        "defect_closure_status",
        "post_probe_result",
    ):
        assert key not in state.json_block, key
        assert key not in state.patch_policy, key
    assert state.json_block["patch_basis"] == PATCH_BASIS_GROUNDED_DEFECT
