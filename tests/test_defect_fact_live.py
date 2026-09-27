"""DEFECT.FACT.LIVE.1 — typed behavioral expectation handoff.

The matrix proves one sentence end to end: an explicit behavioral claim is typed
once at the input boundary, survives every serialization between there and the
probe, and builds a bounded contract without anyone re-reading the user's prose.

It also proves the negatives, which matter more: a claim nobody made is never
invented, two incompatible claims never resolve themselves, and a probe's own
observation never overwrites what the user said.
"""

from __future__ import annotations

import ast
import hashlib
import inspect
import json
import re
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pytest

import core.defect_probe as defect_probe
from core import code_dna
from core.behavioral_expectation import (
    FACT_STATUS_AMBIGUOUS,
    FACT_STATUS_AVAILABLE,
    FACT_STATUS_UNAVAILABLE,
    MAX_BEHAVIORAL_EXPECTATIONS,
    PROVENANCE_EXPLICIT_USER_FACT,
    RELATION_CHANGES_FROM_TO,
    RELATION_EXPECTED_VS_OBSERVED,
    RELATION_INSTEAD_OF,
    SUBJECT_INDENTATION_STYLE,
    BehavioralExpectation,
    behavioral_expectation_guardrails,
    extract_behavioral_expectations,
    restore_behavioral_expectations,
    select_probe_behavior_fact,
    supported_behavior_facts,
)
from core.control_engine import attach_preflight_validation
from core.defect_probe import (
    BEHAVIOR_FACT_SOURCE_LEGACY,
    BEHAVIOR_FACT_SOURCE_TYPED,
    CONTRACT_STATUS_BUILT,
    CONTRACT_STATUS_UNAVAILABLE,
    FACT_STATUS_LEGACY_UNTYPED,
    INVOCATION_PYTHON_PURE_FUNCTION,
    PROBE_NOT_RUN,
    PROBE_REPRODUCED,
    PROBE_TELEMETRY_KEY,
    PROBE_UNAVAILABLE,
    REASON_BEHAVIOR_FACT_AMBIGUOUS,
    REASON_BEHAVIOR_FACT_UNAVAILABLE,
    REASON_LEGACY_ADAPTER_UNAVAILABLE,
    RELATION_EQUALS,
    attach_probe_telemetry_to_payload,
    build_probe_contract_from_behavior_fact,
    build_probe_target_binding,
    carried_behavior_facts,
    defect_probe_guardrails,
    derive_indentation_probe_from_preserved_task,
    execute_defect_probe,
    maybe_execute_control_defect_probe,
    resolve_control_defect_probe,
)
from core.explicit_evidence import extract_explicit_evidence
from core.input_understanding import understand_request
from core.live_task_routing import safe_route_live_task
from core.live_task_shape import derive_live_task_shape
from core.requirement_preservation import check_requirement_preservation
from core.semantic_waiter import ExplicitEvidenceInterpreter, StaticSemanticInterpreter


ROOT = Path(__file__).resolve().parents[1]

#: The exact Round-5/6 T6 prompt, preserved verbatim.  Never paraphrase it: the
#: whole failure this phase repairs is that the old adapter could read one
#: wording of this claim and not the one the user actually typed.
T6_PROMPT = (
    "When I point the agent at a repository that uses 2-space indentation, the "
    "patches it writes come back using 4-space indentation instead. Something "
    "looks wrong with the way repo style gets detected. Please find the root "
    "cause and fix it."
)

#: The short canonical phrase the frozen raw-prose adapter already accepted.
CANONICAL_PHRASE = "2-space indentation is classified as 4-space"
CANONICAL_TASK = f"Fix this bug: {CANONICAL_PHRASE}"

T6_TARGET_FILE = "core/code_dna.py"
T6_TARGET_SYMBOL = "_classify_indent"
T6_TARGET = f"{T6_TARGET_FILE}::{T6_TARGET_SYMBOL}"

#: A long order carrying the same claim.  Length must not gate meaning.
LONG_PROMPT = (
    "I have been running the agent across several internal services this week "
    "and want to report something that keeps happening in the same place. "
    "Our formatting conventions are documented in the contributor guide and "
    "every service follows them, so the behaviour is easy to reproduce on any "
    "of them. When I point the agent at a repository that uses 2-space "
    "indentation, the patches it writes come back using 4-space indentation "
    "instead. It happens whether the change is one line or twenty, and it "
    "happens on the first patch of a session as well as on later ones, so it "
    "does not look like state leaking between runs. Reviewers then have to "
    "reformat every hunk by hand before the change can be merged, which is "
    "eating a meaningful amount of review time across the team. Something "
    "looks wrong with the way repository style gets detected. Please find the "
    "root cause and fix it."
)

AMBIGUOUS_PROMPT = (
    "The formatter should use 2-space indentation but gets 4-space "
    "indentation, and it should use 8-space indentation but gets 2-space "
    "indentation. Please fix whichever one is broken."
)

NON_BEHAVIOR_PROMPT = "Explain how indentation works in this repository"

#: A deliberately broken classifier, small enough to execute in milliseconds.
BROKEN_CLASSIFIER = (
    "def _classify_indent(text):\n"
    "    for line in text.splitlines():\n"
    "        if line.startswith('    '):\n"
    "            return '4space'\n"
    "    return '2space'\n"
)


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _facts(text: str) -> tuple[BehavioralExpectation, ...]:
    facts, _truncated = extract_behavioral_expectations(text)
    return facts


def _only_fact(text: str) -> BehavioralExpectation:
    facts = _facts(text)
    assert len(facts) == 1, facts
    return facts[0]


def _tmp_binding(tmp_path: Path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    binding = build_probe_target_binding(
        repo_path=tmp_path,
        target_file="indent.py",
        target_symbol="_classify_indent",
        source_snippet=BROKEN_CLASSIFIER.strip(),
        candidate_eligible=True,
    )
    assert binding is not None
    return binding


def _control_result(
    *,
    prompt: str,
    repo_path: Path,
    target_file: str,
    source_snippet: str,
    target_symbol: str = "_classify_indent",
    route=None,
) -> dict:
    """One CONTROL result shaped exactly like the live defect-repair path's."""
    if route is None:
        route = safe_route_live_task(prompt, repository_available=True).as_dict()
    target_full = f"{target_file}::{target_symbol}"
    return {
        "query": prompt,
        "repo_path": str(repo_path),
        "live_route": route,
        "patch_intent": {
            "target_file": target_file,
            "target_symbol": target_symbol,
            "target_symbol_full": target_full,
            "source_snippet": source_snippet,
        },
        "entry_resolution": {"resolved_entry_nodes": [target_full]},
        "localization_candidates": [{"symbol": target_full}],
        "top_hypothesis": {"symbol": target_full},
    }


def _preflight() -> dict:
    return {"outcome": "inconclusive", "category": "validation_budget_exhausted"}


def _live_t6_control() -> dict:
    """The real repository target, exactly as the live T6 run localizes it."""
    control = _control_result(
        prompt=T6_PROMPT,
        repo_path=ROOT,
        target_file=T6_TARGET_FILE,
        source_snippet=inspect.getsource(code_dna._classify_indent).strip(),
    )
    control["preflight_validation"] = _preflight()
    return control


# ---------------------------------------------------------------------------
# 1. typed fact extraction
# ---------------------------------------------------------------------------


def test_exact_t6_wording_yields_expected_2space_and_observed_4space():
    fact = _only_fact(T6_PROMPT)

    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    assert fact.expected_value == "2space"
    assert fact.observed_value == "4space"
    assert fact.relation == RELATION_INSTEAD_OF
    assert fact.provenance == PROVENANCE_EXPLICIT_USER_FACT
    assert fact.authoritative is True
    # The quoted span is the user's own text, not a reconstruction of it.
    assert fact.source_text in T6_PROMPT


def test_canonical_phrase_yields_the_same_semantic_fact_as_the_t6_wording():
    canonical = _only_fact(CANONICAL_PHRASE)
    live = _only_fact(T6_PROMPT)

    # Semantic equivalence at intake is the point: two structurally different
    # sentences that mean the same thing produce one claim.  The relation label
    # still records *how* each user phrased it, because that is a fact too.
    assert canonical.behavior_key == live.behavior_key
    assert canonical.expected_value == live.expected_value == "2space"
    assert canonical.observed_value == live.observed_value == "4space"
    assert canonical.relation == RELATION_EXPECTED_VS_OBSERVED
    assert live.relation == RELATION_INSTEAD_OF


def test_long_prompt_carries_the_same_typed_fact_with_no_length_gate():
    assert len(LONG_PROMPT) > 700
    fact = _only_fact(LONG_PROMPT)

    assert fact.behavior_key == _only_fact(T6_PROMPT).behavior_key
    assert fact.expected_value == "2space"
    assert fact.observed_value == "4space"


def test_reversed_wording_is_not_silently_swapped():
    fact = _only_fact(
        "The classifier returns 4-space indentation instead of 2-space indentation."
    )

    # "Y instead of X" names the expectation second.  Reading it the other way
    # round would build a probe that asserts the defect.
    assert fact.expected_value == "2space"
    assert fact.observed_value == "4space"
    assert fact.relation == RELATION_INSTEAD_OF


def test_transition_wording_is_read_as_a_change_from_expected_to_observed():
    fact = _only_fact("It converts from 2-space indentation to 4-space indentation.")

    assert fact.relation == RELATION_CHANGES_FROM_TO
    assert fact.expected_value == "2space"
    assert fact.observed_value == "4space"


def test_facts_are_reported_in_the_order_the_user_wrote_them():
    facts = _facts(AMBIGUOUS_PROMPT)

    assert [fact.expected_value for fact in facts] == ["2space", "8space"]
    assert [fact.source_start for fact in facts] == sorted(
        fact.source_start for fact in facts
    )


def test_values_are_never_read_out_of_the_middle_of_a_number():
    # "12-space" is not "2-space", and a single-digit vocabulary must not slice
    # one out of it.  No value means no pair, which means no fact.
    assert _facts("Indentation of 12-space became 24-space in the output.") == ()
    assert _facts("It uses 2x-space indent and returns 4x-space indent.") == ()


def test_identical_values_state_no_mismatch_and_produce_no_fact():
    assert _facts("2-space indentation is classified as 2-space") == ()


def test_ambiguous_incompatible_claims_are_preserved_but_never_resolved():
    facts = _facts(AMBIGUOUS_PROMPT)

    assert len(facts) == 2
    assert all(fact.authoritative is False for fact in facts)

    selected, status = select_probe_behavior_fact(facts)
    assert selected is None
    assert status == FACT_STATUS_AMBIGUOUS


def test_repeated_compatible_claims_stay_authoritative():
    facts = _facts(
        "It should use 2-space indentation but gets 4-space indentation. "
        "Again: 2-space indentation is classified as 4-space."
    )

    assert len(facts) == 2
    assert all(fact.authoritative for fact in facts)
    selected, status = select_probe_behavior_fact(facts)
    assert status == FACT_STATUS_AVAILABLE
    assert selected is not None and selected.behavior_key == (
        "indentation_style:2space->4space"
    )


def test_non_behavior_task_yields_no_fact_and_invents_nothing():
    assert _facts(NON_BEHAVIOR_PROMPT) == ()
    assert extract_explicit_evidence(NON_BEHAVIOR_PROMPT).behavioral_expectations == ()

    selected, status = select_probe_behavior_fact(())
    assert selected is None
    assert status == FACT_STATUS_UNAVAILABLE


def test_unrelated_values_across_a_sentence_boundary_are_not_paired():
    # Two values the user did not relate to each other are two values, not a
    # claim.  A pair may not straddle a sentence the user ended.
    assert _facts(
        "The repository uses 2-space indentation. Unrelated: the log shows "
        "4-space indentation somewhere else entirely."
    ) == ()


def test_values_with_no_recognised_connective_produce_nothing():
    assert _facts("2-space indentation, 4-space indentation, tabs.") == ()


def test_a_pair_without_its_subject_noun_is_not_an_indentation_claim():
    assert _facts("The padding should be 2 spaces but becomes 4 spaces.") == ()


def test_a_subject_named_just_before_the_pair_still_grounds_it():
    fact = _only_fact("indentation of 2-space turns into 4-space")

    assert fact.subject_kind == SUBJECT_INDENTATION_STYLE
    assert (fact.expected_value, fact.observed_value) == ("2space", "4space")


def test_a_subject_named_a_sentence_earlier_grounds_nothing():
    assert _facts(
        "Indentation matters a great deal to our team here. The timeout went "
        "from 2 spaces to 4 spaces."
    ) == ()


def test_a_value_may_not_straddle_a_line_break():
    assert _facts("indentation x = 2\nspace and 4 space") == ()


# ---------------------------------------------------------------------------
# 2. the typed record itself
# ---------------------------------------------------------------------------


def test_behavioral_expectation_refuses_a_non_user_provenance():
    with pytest.raises(ValueError, match="explicit user provenance"):
        BehavioralExpectation(
            subject_kind=SUBJECT_INDENTATION_STYLE,
            expected_value="2space",
            observed_value="4space",
            relation=RELATION_INSTEAD_OF,
            provenance="model_authored",
            source_text="2-space ... 4-space instead",
        )


def test_behavioral_expectation_refuses_a_mismatch_that_is_not_one():
    with pytest.raises(ValueError, match="may not be the same value"):
        BehavioralExpectation(
            subject_kind=SUBJECT_INDENTATION_STYLE,
            expected_value="2space",
            observed_value="2space",
            relation=RELATION_INSTEAD_OF,
            source_text="2-space",
        )


def test_behavioral_expectation_refuses_an_unquoted_claim():
    with pytest.raises(ValueError, match="quote the user span"):
        BehavioralExpectation(
            subject_kind=SUBJECT_INDENTATION_STYLE,
            expected_value="2space",
            observed_value="4space",
            relation=RELATION_INSTEAD_OF,
            source_text="",
        )


def test_behavioral_expectation_vocabularies_are_closed():
    for bad_subject in ("tab_width", ""):
        with pytest.raises(ValueError, match="subject kind"):
            BehavioralExpectation(
                subject_kind=bad_subject,
                expected_value="2space",
                observed_value="4space",
                relation=RELATION_INSTEAD_OF,
                source_text="x",
            )
    with pytest.raises(ValueError, match="behavior relation"):
        BehavioralExpectation(
            subject_kind=SUBJECT_INDENTATION_STYLE,
            expected_value="2space",
            observed_value="4space",
            relation="becomes_maybe",
            source_text="x",
        )


def test_obligation_ordinal_binds_once_and_never_reaches_the_values():
    fact = _only_fact(T6_PROMPT)
    bound = fact.bind_obligation_ordinal(3)

    assert bound.obligation_ordinal == 3
    assert bound.expected_value == fact.expected_value
    assert bound.observed_value == fact.observed_value
    assert bound.bind_obligation_ordinal(3) is bound
    with pytest.raises(ValueError, match="already bound"):
        bound.bind_obligation_ordinal(4)


def test_serialization_round_trips_without_degrading_to_a_preview_string():
    facts = _facts(T6_PROMPT)
    restored = restore_behavioral_expectations([fact.as_dict() for fact in facts])

    assert restored == facts


def test_restore_refuses_a_payload_that_is_not_a_complete_fact():
    assert restore_behavioral_expectations([{"subject_kind": "indentation_style"}]) == ()
    assert restore_behavioral_expectations("2space -> 4space") == ()
    assert restore_behavioral_expectations(None) == ()


def test_extraction_is_bounded():
    claim = "It should use 2-space indentation but gets 4-space indentation. "
    facts, truncated = extract_behavioral_expectations(claim * 20)

    assert len(facts) <= MAX_BEHAVIORAL_EXPECTATIONS
    assert truncated is True


# ---------------------------------------------------------------------------
# 3. preservation
# ---------------------------------------------------------------------------


def test_fact_survives_the_task_contract():
    contract = understand_request(T6_PROMPT)

    assert contract.preservation.passed is True
    assert len(contract.behavioral_expectations) == 1
    fact = contract.behavioral_expectations[0]
    assert (fact.expected_value, fact.observed_value) == ("2space", "4space")
    payload = contract.as_dict()["behavioral_expectations"]
    assert payload[0]["expected_value"] == "2space"
    assert payload[0]["observed_value"] == "4space"


def test_fact_survives_the_live_shape_bound_to_its_preserved_obligation():
    shape = derive_live_task_shape(T6_PROMPT, repository_available=True)

    assert shape.task_shape == "defect_repair"
    assert len(shape.behavioral_expectations) == 1
    fact = shape.behavioral_expectations[0]
    assert fact.obligation_ordinal == 0
    assert fact.source_text in shape.obligations[fact.obligation_ordinal]


def test_fact_survives_the_route_receipt_and_its_serialization():
    route = safe_route_live_task(T6_PROMPT, repository_available=True)
    payload = route.as_dict()

    assert payload["selected_workflow"] == "defect_repair_patch"
    assert payload["preservation_passed"] is True
    assert restore_behavioral_expectations(payload["behavioral_expectations"]) == (
        route.behavioral_expectations
    )
    carried = payload["behavioral_expectations"][0]
    assert carried["expected_value"] == "2space"
    assert carried["observed_value"] == "4space"
    assert carried["provenance"] == PROVENANCE_EXPLICIT_USER_FACT


def test_preservation_gate_fails_when_an_interpreter_drops_the_fact():
    evidence = extract_explicit_evidence(T6_PROMPT)
    lossy = ExplicitEvidenceInterpreter().interpret(T6_PROMPT, evidence)
    lossy = replace(lossy, behavioral_expectations=())

    report = check_requirement_preservation(evidence, lossy)

    assert report.passed is False
    assert report.has_missing("behavioral_expectation")


def test_preservation_gate_fails_when_an_interpreter_swaps_expected_and_observed():
    evidence = extract_explicit_evidence(T6_PROMPT)
    interpretation = ExplicitEvidenceInterpreter().interpret(T6_PROMPT, evidence)
    original = interpretation.behavioral_expectations[0]
    inverted = replace(
        original,
        expected_value=original.observed_value,
        observed_value=original.expected_value,
    )

    report = check_requirement_preservation(
        evidence, replace(interpretation, behavioral_expectations=(inverted,))
    )

    assert report.passed is False
    assert report.has_missing("behavioral_expectation")


def test_preservation_gate_fails_when_an_interpreter_invents_a_fact():
    evidence = extract_explicit_evidence(NON_BEHAVIOR_PROMPT)
    invented = BehavioralExpectation(
        subject_kind=SUBJECT_INDENTATION_STYLE,
        expected_value="2space",
        observed_value="4space",
        relation=RELATION_INSTEAD_OF,
        source_text="a span the user never wrote",
    )
    interpreter = StaticSemanticInterpreter(
        replace(
            ExplicitEvidenceInterpreter().interpret(NON_BEHAVIOR_PROMPT, evidence),
            behavioral_expectations=(invented,),
        )
    )

    report = check_requirement_preservation(
        evidence, interpreter.interpret(NON_BEHAVIOR_PROMPT, evidence)
    )

    assert report.passed is False
    assert any("never stated it" in reason for reason in report.reasons)


def test_a_fact_whose_span_left_the_preserved_text_does_not_ship():
    facts = _facts(T6_PROMPT)

    assert supported_behavior_facts(facts, [T6_PROMPT]) == facts
    assert supported_behavior_facts(facts, ["an unrelated preserved obligation"]) == ()


# ---------------------------------------------------------------------------
# 4. probe contract construction
# ---------------------------------------------------------------------------


def test_typed_fact_builds_a_contract_bound_to_the_localized_target(tmp_path):
    binding = _tmp_binding(tmp_path)
    fact = _only_fact(T6_PROMPT)

    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=fact
    )

    assert contract is not None
    # WHERE and WHAT stay separate fields, never one opaque string.
    assert contract.target.identity == "indent.py::_classify_indent"
    assert contract.expected == "2space"
    assert contract.expected_relation == RELATION_EQUALS
    assert contract.invocation_kind == INVOCATION_PYTHON_PURE_FUNCTION
    assert "4space" in contract.provenance_reference
    assert fact.source_text in contract.provenance_reference


def test_probe_input_is_a_fixture_in_the_users_expected_style(tmp_path):
    contract = build_probe_contract_from_behavior_fact(
        target=_tmp_binding(tmp_path),
        behavior_fact=_only_fact(T6_PROMPT),
    )
    assert contract is not None
    args = contract.structured_input["args"]
    assert len(args) == 1
    fixture = args[0]

    # Every depth is exactly two spaces: the fixture is built from the user's
    # *expected* value, so a correct classifier answers with that same value.
    assert "\n  level_1\n" in fixture
    assert "\n    level_2\n" in fixture
    assert "\n        level_3\n" not in fixture
    assert contract.expected == "2space"


def test_unsupported_subject_kind_yields_no_contract_rather_than_a_guess(tmp_path):
    binding = _tmp_binding(tmp_path)
    fact = BehavioralExpectation(
        subject_kind=SUBJECT_INDENTATION_STYLE,
        expected_value="2space",
        observed_value="4space",
        relation=RELATION_INSTEAD_OF,
        source_text="2-space ... 4-space instead",
    )
    unnormalizable = replace(fact, expected_value="wide", observed_value="narrow")

    assert (
        build_probe_contract_from_behavior_fact(
            target=binding, behavior_fact=unnormalizable
        )
        is None
    )


def test_live_t6_control_result_builds_a_contract_from_the_typed_fact(monkeypatch):
    def refuse(**_kwargs):
        raise AssertionError("the legacy raw-prose adapter must not be consulted")

    monkeypatch.setattr(
        defect_probe, "derive_indentation_probe_from_preserved_task", refuse
    )

    resolution = resolve_control_defect_probe(_live_t6_control())

    assert resolution.in_scope is True
    assert resolution.contract_status == CONTRACT_STATUS_BUILT
    assert resolution.behavior_fact_source == BEHAVIOR_FACT_SOURCE_TYPED
    assert resolution.behavior_fact_status == FACT_STATUS_AVAILABLE
    assert resolution.target is not None
    assert resolution.target.identity == T6_TARGET
    assert resolution.behavior_fact is not None
    assert resolution.behavior_fact.expected_value == "2space"
    assert resolution.behavior_fact.observed_value == "4space"
    assert resolution.contract is not None
    assert resolution.contract.expected == "2space"
    assert resolution.contract.invocation_kind == INVOCATION_PYTHON_PURE_FUNCTION


def test_live_t6_bounded_probe_reproduces_the_defect():
    receipt = maybe_execute_control_defect_probe(_live_t6_control())

    assert receipt is not None
    assert receipt.probe_result == PROBE_REPRODUCED
    assert receipt.observed == "4space"
    assert receipt.expected == "2space"
    assert receipt.target == T6_TARGET
    assert receipt.execution_stage == "pre_patch"
    assert receipt.invocation_kind == INVOCATION_PYTHON_PURE_FUNCTION


def test_probe_execution_does_not_mutate_the_users_typed_fact():
    control = _live_t6_control()
    before = carried_behavior_facts(control)[0]
    attach_preflight_validation(control, _preflight())
    after = carried_behavior_facts(control)[0]

    assert before == after
    telemetry = control[PROBE_TELEMETRY_KEY]
    # The claim and the observation are separate provenances even when they
    # happen to agree.
    assert telemetry["claimed_observed"] == "4space"
    assert telemetry["probe_observed"] == "4space"
    assert telemetry["expected"] == "2space"


def test_absent_behavior_fact_reports_unavailable_and_probes_nothing(tmp_path):
    prompt = "Fix this bug: the repository style detector is broken."
    control = _control_result(
        prompt=prompt,
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
    )
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = attach_preflight_validation(control, _preflight())

    telemetry = control[PROBE_TELEMETRY_KEY]
    assert telemetry["contract_status"] == CONTRACT_STATUS_UNAVAILABLE
    assert telemetry["unavailable_reason"] == REASON_BEHAVIOR_FACT_UNAVAILABLE
    assert telemetry["expected"] is None
    assert telemetry["claimed_observed"] is None
    assert control["defect_probe"]["probe_result"] == PROBE_UNAVAILABLE


def test_ambiguous_behavior_facts_report_ambiguous_and_probe_nothing(tmp_path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = _control_result(
        prompt=AMBIGUOUS_PROMPT,
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
    )
    control = attach_preflight_validation(control, _preflight())

    telemetry = control[PROBE_TELEMETRY_KEY]
    assert telemetry["behavior_fact_status"] == FACT_STATUS_AMBIGUOUS
    assert telemetry["unavailable_reason"] == REASON_BEHAVIOR_FACT_AMBIGUOUS
    assert telemetry["contract_status"] == CONTRACT_STATUS_UNAVAILABLE
    assert telemetry["expected"] is None
    assert control["defect_probe"]["probe_result"] == PROBE_UNAVAILABLE


# ---------------------------------------------------------------------------
# 5. the legacy raw-prose adapter
# ---------------------------------------------------------------------------


def test_legacy_adapter_still_reads_the_canonical_phrase(tmp_path):
    contract = derive_indentation_probe_from_preserved_task(
        raw_task=CANONICAL_PHRASE, target=_tmp_binding(tmp_path)
    )

    assert contract is not None
    assert contract.expected == "2space"


def test_legacy_adapter_regex_was_not_widened():
    # The frozen pattern still refuses the live T6 wording.  That refusal is the
    # bug report this phase answers, and widening the regex would have been the
    # wrong answer to it.
    assert defect_probe._INDENT_MISCLASSIFICATION.search(T6_PROMPT) is None
    assert defect_probe._INDENT_MISCLASSIFICATION.search(CANONICAL_PHRASE) is not None


def test_legacy_untyped_transport_still_reaches_the_old_adapter(tmp_path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    # A CONTROL result recorded before typed facts existed: the route carries no
    # ``behavioral_expectations`` field at all.
    legacy_route = {
        "selected_workflow": "defect_repair_patch",
        "preservation_passed": True,
    }
    control = _control_result(
        prompt=CANONICAL_TASK,
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
        route=legacy_route,
    )
    control["preflight_validation"] = _preflight()

    resolution = resolve_control_defect_probe(control)

    assert resolution.behavior_fact_source == BEHAVIOR_FACT_SOURCE_LEGACY
    # An old run has no typed fact to call available or missing, and says so.
    assert resolution.behavior_fact_status == FACT_STATUS_LEGACY_UNTYPED
    assert resolution.behavior_fact is None
    assert resolution.contract_status == CONTRACT_STATUS_BUILT
    assert resolution.contract is not None
    assert resolution.contract.expected == "2space"


def test_legacy_untyped_transport_reports_a_legacy_unavailable_reason(tmp_path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = _control_result(
        prompt=T6_PROMPT,
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
        route={
            "selected_workflow": "defect_repair_patch",
            "preservation_passed": True,
        },
    )
    control["preflight_validation"] = _preflight()

    resolution = resolve_control_defect_probe(control)

    # An old run is reported as an old run.  It is never reinterpreted as though
    # typed facts had existed and been found wanting.
    assert resolution.behavior_fact_source == BEHAVIOR_FACT_SOURCE_LEGACY
    assert resolution.behavior_fact_status == FACT_STATUS_LEGACY_UNTYPED
    assert resolution.reason_code == REASON_LEGACY_ADAPTER_UNAVAILABLE
    assert resolution.contract is None


def test_typed_transport_never_falls_back_to_raw_prose(monkeypatch, tmp_path):
    def refuse(**_kwargs):
        raise AssertionError("typed transport must not consult the prose adapter")

    monkeypatch.setattr(
        defect_probe, "derive_indentation_probe_from_preserved_task", refuse
    )
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = _control_result(
        prompt="Fix this bug: the style detector is broken.",
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
    )
    control["preflight_validation"] = _preflight()

    resolution = resolve_control_defect_probe(control)

    assert resolution.behavior_fact_source == BEHAVIOR_FACT_SOURCE_TYPED
    assert resolution.contract is None


# ---------------------------------------------------------------------------
# 6. CONTROL carry
# ---------------------------------------------------------------------------


def test_control_carries_the_typed_fact_beside_the_localized_target():
    control = attach_preflight_validation(_live_t6_control(), _preflight())

    assert control["behavior_fact_transport"] == "typed_preserved_contract"
    assert control["behavior_facts"] == [
        fact.as_dict() for fact in carried_behavior_facts(control)[0]
    ]
    # Separate fields: the target says where, the fact says what behavior.
    assert control["localization_handoff"]["localized_target"] == T6_TARGET
    assert control["behavior_facts"][0]["expected_value"] == "2space"


def test_control_cannot_rewrite_a_carried_fact():
    control = _live_t6_control()
    route_fact = dict(control["live_route"]["behavioral_expectations"][0])
    attach_preflight_validation(control, _preflight())

    carried = control["behavior_facts"][0]
    for field in ("subject_kind", "expected_value", "observed_value", "relation"):
        assert carried[field] == route_fact[field]


def test_control_refuses_a_fact_whose_provenance_is_not_the_user():
    control = _live_t6_control()
    control["live_route"]["behavioral_expectations"][0]["provenance"] = "model_authored"

    facts, typed = carried_behavior_facts(control)

    # Restoration rejects it outright: there is no path by which a model-authored
    # claim becomes a probe expectation.
    assert typed is True
    assert facts == ()


def test_a_source_derived_value_cannot_replace_the_users_expectation():
    control = _live_t6_control()
    attach_preflight_validation(control, _preflight())

    telemetry = control[PROBE_TELEMETRY_KEY]
    # The classifier under test answers "4space".  The expectation the probe
    # checks against is still the user's "2space".
    assert telemetry["expected"] == "2space"
    assert telemetry["probe_expected"] == "2space"
    assert telemetry["probe_observed"] == "4space"


# ---------------------------------------------------------------------------
# 7. telemetry
# ---------------------------------------------------------------------------


def test_live_payload_exposes_the_existing_probe_receipt():
    control = attach_preflight_validation(_live_t6_control(), _preflight())
    block = {"patch_plan": None}

    attach_probe_telemetry_to_payload(control, block)

    telemetry = block[PROBE_TELEMETRY_KEY]
    assert telemetry["target"] == T6_TARGET
    assert telemetry["expected"] == "2space"
    assert telemetry["claimed_observed"] == "4space"
    assert telemetry["probe_result"] == PROBE_REPRODUCED
    assert telemetry["probe_observed"] == "4space"
    assert telemetry["probe_expected"] == "2space"
    assert telemetry["contract_status"] == CONTRACT_STATUS_BUILT
    assert telemetry["invocation_kind"] == INVOCATION_PYTHON_PURE_FUNCTION


def test_payload_telemetry_is_a_copy_and_never_re_executes_a_probe(monkeypatch):
    control = attach_preflight_validation(_live_t6_control(), _preflight())

    def refuse(*_args, **_kwargs):
        raise AssertionError("payload surfacing must not execute a probe")

    monkeypatch.setattr(defect_probe, "execute_defect_probe", refuse)
    monkeypatch.setattr(defect_probe, "resolve_control_defect_probe", refuse)

    block: dict = {}
    attach_probe_telemetry_to_payload(control, block)

    assert block[PROBE_TELEMETRY_KEY] == control[PROBE_TELEMETRY_KEY]
    block[PROBE_TELEMETRY_KEY]["probe_result"] = "tampered"
    assert control[PROBE_TELEMETRY_KEY]["probe_result"] == PROBE_REPRODUCED


def test_display_grounding_keeps_the_answer_and_the_payload_one_copy():
    """ANSWER.GROUND.LIVE.3 stays intact: telemetry never splits the two copies.

    ``ground_answer_for_display`` serializes the answer from the block. A key
    added to the block *after* that point would appear in the patch payload and
    not in the answer, which is exactly the invariant ANSWER.GROUND.LIVE.3
    exists to hold. The probe receipt therefore reaches the payload earlier, at
    ``enforce_payload_target``, where both copies still agree.
    """
    from core.localization_handoff import ground_answer_for_display

    control = attach_preflight_validation(_live_t6_control(), _preflight())
    # No localization candidates: the display seam takes its early return.
    control.pop("localization_candidates", None)
    state = SimpleNamespace(
        control_result=control,
        live_route=control["live_route"],
        user_input=T6_PROMPT,
        repo_path=str(ROOT),
    )
    payload = {"summary": "no repository entities named here", "patch_plan": None}

    answer, human, block, _grounding = ground_answer_for_display(
        state, json.dumps(payload), dict(payload)
    )

    assert json.loads(answer) == block
    assert json.loads(human) == block
    assert PROBE_TELEMETRY_KEY not in block


def test_telemetry_emits_no_probe_values_when_nothing_ran(tmp_path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = _control_result(
        prompt=AMBIGUOUS_PROMPT,
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
    )
    control = attach_preflight_validation(control, _preflight())

    telemetry = control[PROBE_TELEMETRY_KEY]
    assert telemetry["probe_result"] == PROBE_NOT_RUN
    assert telemetry["probe_observed"] is None
    assert telemetry["probe_expected"] is None
    assert telemetry["probe_attempted"] is False
    assert telemetry["invocation_kind"] is None


def test_telemetry_is_absent_for_a_route_that_may_not_probe(tmp_path):
    (tmp_path / "indent.py").write_text(BROKEN_CLASSIFIER, encoding="utf-8")
    control = _control_result(
        prompt="Explain how repository style detection works.",
        repo_path=tmp_path,
        target_file="indent.py",
        source_snippet=BROKEN_CLASSIFIER.strip(),
    )
    control = attach_preflight_validation(control, _preflight())

    telemetry = control[PROBE_TELEMETRY_KEY]
    assert telemetry["in_scope"] is False
    assert telemetry["probe_result"] == PROBE_NOT_RUN
    assert telemetry["target"] is None
    assert telemetry["expected"] is None
    assert "defect_probe" not in control


def test_telemetry_carries_no_authority_or_confidence_field():
    control = attach_preflight_validation(_live_t6_control(), _preflight())
    telemetry = control[PROBE_TELEMETRY_KEY]

    for forbidden in (
        "write_authority",
        "execution_authorized",
        "human_review_eligible",
        "approval_ready",
        "confidence",
        "score",
        "source",
        "source_snippet",
    ):
        assert forbidden not in telemetry


def test_localization_handoff_remains_compatible():
    control = attach_preflight_validation(_live_t6_control(), _preflight())
    handoff = control["localization_handoff"]

    assert set(handoff) == {
        "localized_target",
        "control_target",
        "replacement_receipt",
        "semantics",
    }
    assert handoff["localized_target"] == T6_TARGET


# ---------------------------------------------------------------------------
# 8. compatibility with the other live routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "prompt",
    [
        "Fix this bug: calc.py add(2, 2) returns 0 instead of 4.",
        "pytest fails with AssertionError in test_add; please fix it.",
        "Running main.py crashes with a TypeError. Find the root cause and fix it.",
    ],
)
def test_other_defect_tasks_still_route_without_a_typed_behavior_fact(prompt):
    route = safe_route_live_task(prompt, repository_available=True)

    assert route.selected_workflow == "defect_repair_patch"
    # A behavioral expectation is never mandatory for a defect route.
    assert route.as_dict()["preservation_passed"] is True


def test_explicit_change_route_is_unchanged():
    route = safe_route_live_task(
        "Add task priority support to the CLI", repository_available=True
    )

    assert route.selected_workflow == "explicit_change_patch"
    assert route.behavioral_expectations == ()


def test_analysis_route_is_unchanged():
    route = safe_route_live_task(
        "Compare this repository against deepseek-harness", repository_available=True
    )

    assert route.selected_workflow == "analysis_answer"
    assert route.behavioral_expectations == ()


def test_an_analysis_order_that_states_a_behavior_fact_still_answers():
    # A typed fact is descriptive.  It does not promote a read-only order into a
    # patch route, and no probe is constructed for one.
    route = safe_route_live_task(
        "Explain why a repository that uses 2-space indentation gets 4-space "
        "indentation instead.",
        repository_available=True,
    )

    assert route.selected_workflow == "analysis_answer"
    assert route.change_requested is False


# ---------------------------------------------------------------------------
# 9. static boundaries
# ---------------------------------------------------------------------------


def test_behavioral_expectation_module_has_no_io_model_or_traversal_primitives():
    source = (ROOT / "core/behavioral_expectation.py").read_text(encoding="utf-8")

    for forbidden in (
        "import os",
        "import requests",
        "import httpx",
        "urllib",
        "socket",
        "subprocess",
        "open(",
        "Path(",
        ".rglob(",
        ".glob(",
        "os.walk(",
        "eval(",
        "exec(",
        "embedding",
        "run_gemini_request",
        "run_ollama",
    ):
        assert forbidden not in source, forbidden

    # It is a pure value module: no repository, no provider, no authority.
    assert "core.retriever" not in source
    assert "core.indexer" not in source
    assert T6_TARGET_SYMBOL not in source


def test_guardrails_pin_the_boundaries_this_phase_promised():
    fact_guardrails = behavioral_expectation_guardrails()
    for flag in (
        "model_call_performed",
        "network_call_performed",
        "repository_traversal_performed",
        "file_read_performed",
        "retrieval_changed",
        "ranking_changed",
        "probe_execution_changed",
        "defect_established",
        "patch_basis_established",
        "write_authority",
        "source_derived_expectation_accepted",
        "model_authored_expectation_accepted",
    ):
        assert fact_guardrails[flag] is False

    probe_guardrails = defect_probe_guardrails()
    for flag in (
        "behavior_fact_authored_by_control",
        "behavior_fact_authored_by_probe",
        "raw_prose_reparsed_when_typed_fact_available",
        "probe_observation_overwrote_user_claim",
        "write_authority_granted",
        "retrieval_changed",
        "ranking_changed",
        "repository_traversal_added",
        "model_expectation_accepted",
    ):
        assert probe_guardrails[flag] is False


def test_probe_execution_surface_is_pinned_ast_identical():
    """The freeze is proved against digests, not asserted in a docstring.

    CONTROL.LOCALIZE.LIVE.2 pinned the whole of ``core/defect_probe.py`` by
    file digest.  This phase is authorised to change contract *construction* in
    that file, so that digest was re-pinned — and the invariant it used to carry
    moved here, at function granularity, where it says the thing that actually
    matters: nothing that runs a probe changed.

    INDENT.RUNTIME.1 note: it *was* authorized to change contract
    construction further (``build_python_function_probe`` and
    ``build_probe_contract_from_behavior_fact`` both gained a ``kwargs``
    parameter/argument), so this reads the reconstructed historical source
    through ``before_later_receipts`` — the same idiom every other
    frozen-boundary test in this suite already uses — rather than the live
    bytes directly.
    """
    from _harness_maintenance import before_later_receipts

    pins = json.loads(
        (ROOT / "tests/fixtures/defect_fact_live1_frozen_probe_execution.json").read_text(
            encoding="utf-8"
        )
    )
    # The original test read this file with read_text(), which normalizes
    # CRLF to LF; before_later_receipts preserves raw bytes, so match that
    # normalization here too -- the pinned strings below were captured
    # LF-normalized.
    source = before_later_receipts(
        "core/defect_probe.py", (ROOT / "core/defect_probe.py").read_bytes()
    ).decode("utf-8").replace("\r\n", "\n")
    nodes = {
        node.name: node
        for node in ast.parse(source).body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef))
    }

    for name, digest in pins["functions"].items():
        assert name in nodes, name
        actual = hashlib.sha256(
            ast.dump(nodes[name], include_attributes=False).encode()
        ).hexdigest()
        assert actual == digest, name

    # The legacy adapter kept its body, its signature and its literal pattern.
    adapter = nodes["derive_indentation_probe_from_preserved_task"]
    body = adapter.body[1:] if ast.get_docstring(adapter) else adapter.body
    payload = "|".join(ast.dump(item, include_attributes=False) for item in body)
    payload += "|" + ast.dump(adapter.args, include_attributes=False)
    assert (
        hashlib.sha256(payload.encode()).hexdigest() == pins["legacy_adapter_body"]
    )
    pattern = re.search(
        r"_INDENT_MISCLASSIFICATION = re\.compile\((.*?)\n\)", source, re.S
    )
    assert pattern is not None
    assert pattern.group(1) == pins["legacy_adapter_regex"]


def test_probe_execution_surface_is_untouched(tmp_path):
    # Same contract, same execution path, same verdict as DEFECT.PROBE.LIVE.1.
    binding = _tmp_binding(tmp_path)
    contract = build_probe_contract_from_behavior_fact(
        target=binding, behavior_fact=_only_fact(T6_PROMPT)
    )
    assert contract is not None

    receipt = execute_defect_probe(contract, repo_path=tmp_path)

    assert receipt.probe_result == PROBE_REPRODUCED
    assert receipt.observed == "4space"
    assert receipt.expected == "2space"
    assert receipt.side_effect_policy == "read_only_no_network"
    assert receipt.freshness == "current_source_isolated_bytecode_cache"
