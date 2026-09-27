"""INPUT.PRESERVE.LIVE.1 — Lossless Long-Obligation Transport.

The live T5 black-box run exposed a violation of the frozen INPUT.1
preservation contract: a request naming six explicit comparison dimensions
reached downstream analysis evidence selection carrying only the first ~250
characters of the first clause.  ``tool``, ``plugin``, ``lifecycle``,
``context`` and ``retrieval`` never arrived.

These tests pin the transport, not the consumer.  ANALYSIS.EVIDENCE.LIVE.1's
role-allocation algorithm is untouched; it simply receives what the user
actually wrote.
"""

from __future__ import annotations

import json

import pytest

from core.analysis_evidence_roles import (
    PROFILE_ARCHITECTURE_IMPLEMENTATION,
    derive_evidence_profile,
    subject_tokens,
)
from core.explicit_evidence import MAX_SCAN_CHARS
from core.live_task_routing import (
    WORKFLOW_ANALYSIS_ANSWER,
    WORKFLOW_CLARIFICATION,
    WORKFLOW_DEFECT_REPAIR,
    WORKFLOW_EXPLICIT_CHANGE,
    route_allows_patch_localization,
    route_is_read_only,
    route_live_task,
    route_receipt_from_dict,
)
from core.live_task_shape import (
    CHANGE_NEED_NONE,
    REASON_ANALYSIS_NO_CHANGE_REQUESTED,
    SHAPE_ANALYSIS_ONLY,
    SHAPE_DEFECT_REPAIR,
    SHAPE_EXPLICIT_CHANGE,
    SHAPE_NEEDS_CLARIFICATION,
    LiveTaskShape,
    derive_live_task_shape,
    split_obligations,
)
from core.obligation_preservation import (
    MAX_ACCEPTED_TASK_CHARS,
    MAX_OBLIGATION_UNIT_CHARS,
    MAX_OBLIGATION_UNITS,
    OBLIGATION_PREVIEW_CHARS,
    OVERFLOW_INPUT_TOO_LARGE,
    OVERFLOW_NONE,
    OVERFLOW_STATUSES,
    PHASE_ID,
    ObligationSet,
    derive_obligation_set,
    split_obligation_clauses,
)


# ── Fixtures, in the shape the live routes actually receive them ──────────────

#: The canonical long-form T5 request, byte-for-byte as the black-box harness
#: fed it to ``main.py``.  Its later comparison dimensions are the regression.
T5_PROMPT = (
    "Compare this repository (deepseek-harness, the DeepSeek AI agent harness) "
    "against C.A.T.T.U.S, the Python agent harness located at ../C.A.T.T.U.S. "
    "Focus on: (1) how each one structures its agent loop and extension model, "
    "(2) how each handles tool/plugin registration and lifecycle, (3) how each "
    "handles repository context and retrieval for coding tasks. Then recommend "
    "the three highest-value architectural ideas C.A.T.T.U.S should adopt from "
    "deepseek-harness, with concrete justification grounded in files you actually "
    "read."
)

#: The exact terms the live run measured as lost.  Pinned from the real
#: reproduction, never wired into production as T5-specific constants.
T5_LOST_TERMS: tuple[str, ...] = (
    "tool",
    "plugin",
    "lifecycle",
    "context",
    "retrieval",
)

SHORT_ANALYSIS = "Compare deepseek-harness and C.A.T.T.U.S architecture."
SHORT_DEFECT = "add(2,2) returns 0 / test fails"
SHORT_FEATURE = "Add task priority support across model/store/CLI."
AMBIGUOUS = "Improve the agent."
MIXED = "Explain how validation works, then fix the pytest detection bug."

#: Three long single-clause requests whose only late content is, respectively,
#: a safety constraint, an output-format requirement and a write prohibition.
#: Each one exceeds the old 240-character cap, and none of them carries a
#: clause separator the old splitter would have honoured.
LATE_CONSTRAINT = (
    "Analyze how the retrieval subsystem selects candidate files for a coding task, "
    "describe the ranking function it applies to each candidate, and explain which "
    "module owns the final bounded entry cap, so that I can understand exactly where "
    "the ordering decision is made before CONTROL ever sees the list. "
    "Do not modify files."
)
LATE_OUTPUT_FORMAT = (
    "Analyze how the retrieval subsystem selects candidate files for a coding task, "
    "describe the ranking function it applies to each candidate, and explain which "
    "module owns the final bounded entry cap, so that I can understand exactly where "
    "the ordering decision is made before CONTROL ever sees the list. "
    "Return exactly three recommendations."
)
LATE_NO_WRITE = (
    "Review the architecture of the validation subsystem and explain how the preflight "
    "command is chosen for a repository, how the executed result is bound back to the "
    "originating claim, and which gate refuses an ungrounded patch when no source "
    "snippet was acquired during the whole run. Analysis only, and do not write."
)

#: A long request whose *late* half names the second comparison subject, the
#: comparison relationship and the rubric the answer is bound to.
LATE_SUBJECT_RELATIONSHIP_RUBRIC = (
    "I have been reading through the harness for a while now and I would like a "
    "proper written treatment of how the whole thing actually hangs together, "
    "because the module names alone have stopped being enough for me to reason "
    "about where a change belongs. Compare the ingestion pipeline against the "
    "validation pipeline on latency, on memory footprint, and on failure isolation."
)


def _obligation_text(values) -> str:
    return " ".join(str(value) for value in values).casefold()


# ── 1. the authoritative producer ─────────────────────────────────────────────

def test_phase_id_is_the_input_preserve_phase():
    assert PHASE_ID == "INPUT.PRESERVE.LIVE.1"


def test_short_obligations_are_unchanged():
    """The frozen short-request behaviour is exactly what it was."""
    assert split_obligations("compare X and Y, then recommend Z") == (
        "compare X and Y",
        "recommend Z",
    )


def test_short_request_produces_one_unit_and_no_overflow():
    obligations = derive_obligation_set(SHORT_ANALYSIS)

    assert obligations.values == (SHORT_ANALYSIS.rstrip("."),)
    assert obligations.overflow_status == OVERFLOW_NONE
    assert obligations.authoritative_truncated is False
    assert obligations.preview_truncated is False


def test_an_obligation_set_over_the_old_cap_preserves_every_accepted_unit():
    """>250 characters of commitments, and not one character of them lost."""
    obligations = derive_obligation_set(T5_PROMPT)

    assert obligations.authoritative_truncated is False
    assert obligations.overflow_status == OVERFLOW_NONE
    assert obligations.preserved_obligation_count == obligations.accepted_obligation_count
    assert sum(len(value) for value in obligations.values) > 240


def _words(text: str) -> set[str]:
    cleaned = text.replace("/", " ").replace("(", " ").replace(")", " ")
    return {word.strip(".,:;") for word in cleaned.split() if word.strip(".,:;")}


def test_no_authoritative_unit_is_cut_mid_word():
    """The old cap sliced ``handles`` into ``handle``. Nothing may do that.

    A character cap does not merely lose words — it invents them, and the
    invented fragment then travels downstream as if the user had typed it.
    """
    obligations = derive_obligation_set(T5_PROMPT)
    written = _words(T5_PROMPT)

    for unit in obligations.units:
        for word in _words(unit.text):
            assert word in written, f"unit word {word!r} is not a word the user wrote"


def test_authoritative_units_stay_within_the_declared_unit_bound():
    obligations = derive_obligation_set(T5_PROMPT)

    assert obligations.units
    for unit in obligations.units:
        assert len(unit.text) <= MAX_OBLIGATION_UNIT_CHARS
    assert len(obligations.units) <= MAX_OBLIGATION_UNITS


# ── 2. the T5 regression ──────────────────────────────────────────────────────

def test_t5_later_comparison_dimensions_reach_the_authoritative_contract():
    """The measured live failure, pinned.

    Every term the black-box run lost is a term the user typed, and each one
    must survive into the obligation set downstream consumes.
    """
    text = _obligation_text(split_obligations(T5_PROMPT))

    for term in T5_LOST_TERMS:
        assert term in T5_PROMPT.casefold(), f"fixture drift: {term!r} left the prompt"
        assert term in text, f"explicit term {term!r} did not survive transport"


def test_t5_route_carries_the_later_dimensions_to_downstream_consumers():
    route = route_live_task(T5_PROMPT, repository_available=True)
    text = _obligation_text(route.as_dict()["obligations"])

    for term in T5_LOST_TERMS:
        assert term in text


def test_t5_relationship_is_not_flattened_into_a_keyword_bag():
    """``compare A against B`` stays one readable commitment."""
    values = split_obligations(T5_PROMPT)
    first = values[0].casefold()

    assert "compare" in first
    assert "deepseek-harness" in first
    assert "c.a.t.t.u.s" in first


def test_t5_late_recommendation_relationship_survives():
    text = _obligation_text(split_obligations(T5_PROMPT))

    assert "recommend" in text
    assert "three" in text
    assert "adopt" in text


# ── 3. late commitments in a long single clause ───────────────────────────────

def test_late_safety_constraint_survives_transport():
    """Security-relevant: a prohibition written last is still a prohibition."""
    text = _obligation_text(split_obligations(LATE_CONSTRAINT))

    assert "do not modify files" in text


def test_late_output_format_requirement_survives_transport():
    text = _obligation_text(split_obligations(LATE_OUTPUT_FORMAT))

    assert "exactly three recommendations" in text


def test_late_write_prohibition_survives_transport():
    text = _obligation_text(split_obligations(LATE_NO_WRITE))

    assert "do not write" in text


def test_late_subject_relationship_and_rubric_all_survive():
    text = _obligation_text(split_obligations(LATE_SUBJECT_RELATIONSHIP_RUBRIC))

    # subject, named 380 characters into the request
    assert "validation pipeline" in text
    # relationship
    assert "compare" in text
    # rubric dimensions
    assert "latency" in text
    assert "memory footprint" in text
    assert "failure isolation" in text


# ── 4. ordering and duplicates ────────────────────────────────────────────────

def test_ordering_follows_the_user_not_length_or_alphabet():
    request = (
        "First compare the alpha subsystem against the beta subsystem; "
        "then evaluate throughput; "
        "then evaluate a much longer dimension about operational recoverability; "
        "finally summarise"
    )
    values = split_obligations(request)

    positions = [request.casefold().index(value.casefold()[:20]) for value in values]
    assert positions == sorted(positions), "obligations were reordered"


def test_unit_ordinals_are_dense_and_ascending():
    obligations = derive_obligation_set(T5_PROMPT)

    assert [unit.ordinal for unit in obligations.units] == list(
        range(len(obligations.units))
    )


def test_exact_duplicate_clauses_are_deduplicated_deterministically():
    request = "compare A and B; compare A and B; then recommend C"
    first = split_obligations(request)
    second = split_obligations(request)

    assert first == second
    assert len(first) == 2


def test_distinct_dimensions_are_never_collapsed_to_save_characters():
    """``compare lifecycle`` and ``compare retrieval`` are two obligations."""
    request = "compare lifecycle; compare retrieval"
    values = split_obligations(request)

    assert values == ("compare lifecycle", "compare retrieval")


# ── 5. storage versus display ─────────────────────────────────────────────────

def test_preview_may_truncate_while_the_authoritative_set_does_not():
    obligations = derive_obligation_set(T5_PROMPT)

    assert obligations.preview_truncated is True
    assert len(obligations.preview) <= OBLIGATION_PREVIEW_CHARS
    assert obligations.authoritative_truncated is False
    assert sum(len(value) for value in obligations.values) > len(obligations.preview)


def test_preview_is_never_the_authoritative_storage():
    """A consumer reading ``values`` may not be handed the preview string."""
    obligations = derive_obligation_set(T5_PROMPT)

    assert obligations.preview not in obligations.values


def test_short_request_preview_is_not_truncated():
    obligations = derive_obligation_set(SHORT_ANALYSIS)

    assert obligations.preview_truncated is False
    assert obligations.preview.casefold().startswith("compare deepseek-harness")


# ── 6. bounded input and overflow ─────────────────────────────────────────────

def test_accepted_input_bound_reuses_the_frozen_input_1_policy():
    assert MAX_ACCEPTED_TASK_CHARS == MAX_SCAN_CHARS


def test_input_over_the_accepted_bound_reports_overflow_explicitly():
    """Never silently accept 5,000 characters and then keep 250."""
    oversized = "compare alpha and beta. " * 20_000
    assert len(oversized) > MAX_ACCEPTED_TASK_CHARS

    obligations = derive_obligation_set(oversized)

    assert obligations.overflow_status == OVERFLOW_INPUT_TOO_LARGE
    assert obligations.overflow_status in OVERFLOW_STATUSES
    assert obligations.input_chars == len(oversized)


def test_a_five_thousand_character_request_is_not_reduced_to_two_hundred_fifty():
    request = "; ".join(
        f"evaluate dimension {index} of the subsystem in careful detail"
        for index in range(90)
    )
    assert len(request) > 5_000

    obligations = derive_obligation_set(request)
    total = sum(len(value) for value in obligations.values)

    assert total > 250
    assert obligations.overflow_status in OVERFLOW_STATUSES
    if obligations.overflow_status == OVERFLOW_NONE:
        assert obligations.authoritative_truncated is False


def test_overflow_is_recorded_rather_than_hidden():
    request = "; ".join(f"evaluate dimension {index}" for index in range(400))

    obligations = derive_obligation_set(request)

    if obligations.accepted_obligation_count > obligations.preserved_obligation_count:
        assert obligations.overflow_status != OVERFLOW_NONE
        assert obligations.authoritative_truncated is True


# ── 7. the preservation gate sees what downstream sees ────────────────────────

def test_the_gate_and_downstream_read_the_same_obligation_set():
    """Gate passed / downstream received fewer must be impossible."""
    shape = derive_live_task_shape(T5_PROMPT, repository_available=True)
    route = route_live_task(T5_PROMPT, repository_available=True)

    assert shape.preservation_passed is True
    assert shape.obligations == shape.obligation_set.values
    assert route.obligations == shape.obligations
    assert tuple(route.as_dict()["obligations"]) == shape.obligations


def test_the_shape_reports_no_authoritative_truncation_when_preservation_passed():
    shape = derive_live_task_shape(T5_PROMPT, repository_available=True)

    assert shape.preservation_passed is True
    assert shape.obligation_set.authoritative_truncated is False


def test_a_shape_cannot_carry_fewer_obligations_than_the_gate_inspected():
    """The regression is unrepresentable, not merely covered by a test.

    A ``LiveTaskShape`` whose downstream tuple disagrees with the authoritative
    set the preservation gate read cannot be constructed at all.
    """
    obligations = derive_obligation_set(T5_PROMPT)
    truncated = tuple(value[:240] for value in obligations.values)
    assert truncated != obligations.values

    with pytest.raises(ValueError, match="authoritative set"):
        LiveTaskShape(
            task_shape=SHAPE_ANALYSIS_ONLY,
            change_requested=False,
            defect_claim_present=False,
            change_need_source=CHANGE_NEED_NONE,
            reasons=(REASON_ANALYSIS_NO_CHANGE_REQUESTED,),
            obligations=truncated,
            obligation_set=obligations,
        )


def test_a_shape_cannot_claim_preservation_over_a_truncated_set():
    incomplete = ObligationSet.from_historical(("compare A and B",))
    assert incomplete.authoritative_truncated is True

    with pytest.raises(ValueError, match="failed to reach the authoritative"):
        LiveTaskShape(
            task_shape=SHAPE_ANALYSIS_ONLY,
            change_requested=False,
            defect_claim_present=False,
            change_need_source=CHANGE_NEED_NONE,
            reasons=(REASON_ANALYSIS_NO_CHANGE_REQUESTED,),
            obligations=incomplete.values,
            obligation_set=incomplete,
            preservation_passed=True,
        )


def test_no_silent_authoritative_truncation_across_the_fixture_matrix():
    for request in (
        SHORT_ANALYSIS,
        SHORT_DEFECT,
        SHORT_FEATURE,
        AMBIGUOUS,
        MIXED,
        T5_PROMPT,
        LATE_CONSTRAINT,
        LATE_OUTPUT_FORMAT,
        LATE_NO_WRITE,
        LATE_SUBJECT_RELATIONSHIP_RUBRIC,
    ):
        obligations = derive_obligation_set(request)
        assert obligations.overflow_status == OVERFLOW_NONE, request[:60]
        assert obligations.authoritative_truncated is False, request[:60]
        assert (
            obligations.preserved_obligation_count
            == obligations.accepted_obligation_count
        ), request[:60]


# ── 8. the receipt ────────────────────────────────────────────────────────────

def test_receipt_exposes_bounded_preservation_facts():
    receipt = derive_obligation_set(T5_PROMPT).as_dict()

    assert receipt["phase_id"] == PHASE_ID
    assert receipt["accepted_obligation_count"] >= 1
    assert receipt["preserved_obligation_count"] == receipt["accepted_obligation_count"]
    assert receipt["preview_truncated"] is True
    assert receipt["authoritative_truncated"] is False
    assert receipt["overflow_status"] == OVERFLOW_NONE


def test_receipt_does_not_dump_the_whole_private_request():
    receipt = derive_obligation_set(T5_PROMPT).as_dict()
    rendered = json.dumps(receipt, ensure_ascii=False)

    assert T5_PROMPT not in rendered
    assert len(receipt["preview"]) <= OBLIGATION_PREVIEW_CHARS


def test_receipt_is_deterministic():
    assert derive_obligation_set(T5_PROMPT).as_dict() == derive_obligation_set(
        T5_PROMPT
    ).as_dict()


# ── 9. route compatibility (WAITER is not retuned) ────────────────────────────

@pytest.mark.parametrize(
    ("request_text", "shape", "workflow"),
    [
        (SHORT_ANALYSIS, SHAPE_ANALYSIS_ONLY, WORKFLOW_ANALYSIS_ANSWER),
        (T5_PROMPT, SHAPE_ANALYSIS_ONLY, WORKFLOW_ANALYSIS_ANSWER),
        (SHORT_DEFECT, SHAPE_DEFECT_REPAIR, WORKFLOW_DEFECT_REPAIR),
        (SHORT_FEATURE, SHAPE_EXPLICIT_CHANGE, WORKFLOW_EXPLICIT_CHANGE),
        (AMBIGUOUS, SHAPE_NEEDS_CLARIFICATION, WORKFLOW_CLARIFICATION),
        (MIXED, SHAPE_NEEDS_CLARIFICATION, WORKFLOW_CLARIFICATION),
        (LATE_CONSTRAINT, SHAPE_ANALYSIS_ONLY, WORKFLOW_ANALYSIS_ANSWER),
        (LATE_OUTPUT_FORMAT, SHAPE_ANALYSIS_ONLY, WORKFLOW_ANALYSIS_ANSWER),
        (LATE_NO_WRITE, SHAPE_ANALYSIS_ONLY, WORKFLOW_ANALYSIS_ANSWER),
    ],
)
def test_routes_are_unchanged_by_lossless_transport(request_text, shape, workflow):
    route = route_live_task(request_text, repository_available=True)

    assert route.task_shape == shape
    assert route.selected_workflow == workflow


def test_analysis_routes_still_grant_no_write_authority():
    route = route_live_task(T5_PROMPT, repository_available=True)

    assert route.write_authority is False
    assert route.patch_localization_allowed is False
    assert route.control_source_snippet_required is False
    assert route.defect_established is False


def test_mixed_obligation_detection_still_reads_user_written_clauses():
    """Sub-splitting a long clause may not manufacture a clarification route."""
    clauses = split_obligation_clauses(T5_PROMPT)

    assert len(clauses) == 2
    assert clauses[0].casefold().startswith("compare this repository")
    assert clauses[1].casefold().startswith("recommend the three")


# ── 10. ANALYSIS.EVIDENCE.LIVE.1 receives the later obligations ───────────────

def test_analysis_evidence_receives_the_later_t5_dimensions():
    """The consumer is unchanged; its input is no longer truncated.

    This asserts what INPUT.PRESERVE owns — what ANALYSIS.EVIDENCE is *handed*.
    How many of those words then win its bounded token budget is
    ANALYSIS.EVIDENCE's own frozen decision, and this phase does not touch it.
    """
    route = route_live_task(T5_PROMPT, repository_available=True)
    planner_input = _obligation_text([*route.obligations, *route.subjects])

    for term in T5_LOST_TERMS:
        assert term in planner_input, f"{term!r} never reached evidence selection"


def test_analysis_evidence_is_no_longer_handed_a_fabricated_token():
    """The 240-character cut ended a unit at ``handle``, and the token stream
    carried that fragment into path matching as though the user had typed it.
    A word the user never wrote may not reach evidence selection.
    """
    route = route_live_task(T5_PROMPT, repository_available=True)
    tokens = subject_tokens([*route.subjects, *route.obligations])

    assert "handle" not in tokens
    assert "handles" in tokens


def test_analysis_evidence_profile_is_still_architecture_for_t5():
    route = route_live_task(T5_PROMPT, repository_available=True)
    profile = derive_evidence_profile(
        obligations=route.obligations, subjects=route.subjects
    )

    assert profile == PROFILE_ARCHITECTURE_IMPLEMENTATION


# ── 11. historical artifacts and INPUT.1/.2/.3 compatibility ──────────────────

def test_a_historical_truncated_obligation_list_still_reads():
    """An old run's stored obligations are data, not a preservation claim."""
    historical = (
        "Compare this repository (deepseek-harness, the DeepSeek AI agent harness) "
        "against C.A.T.T.U.S, the Python agent harness located at ../C.A.T.T.U.S. "
        "Focus on: (1) how each one structures its agent loop and extension mo",
    )
    restored = ObligationSet.from_historical(historical)

    assert restored.values == historical
    assert restored.authoritative_truncated is True
    assert restored.overflow_status != OVERFLOW_NONE


def test_historical_artifacts_are_not_reinterpreted_as_preserved():
    restored = ObligationSet.from_historical(("compare A and B",))

    assert restored.as_dict()["authoritative_truncated"] is True


def test_a_stored_route_payload_without_the_new_receipt_still_reads():
    """An old run's ``live_route`` predates ``obligation_preservation``."""
    historical_payload = {
        "phase_id": "WAITER.LIVE.1",
        "task_shape": SHAPE_ANALYSIS_ONLY,
        "selected_workflow": WORKFLOW_ANALYSIS_ANSWER,
        "change_requested": False,
        "change_need_source": "none",
        "patch_localization_allowed": False,
        "obligations": ["Compare this repository (deepseek-harness, the Deep"],
    }

    assert route_receipt_from_dict(historical_payload) == historical_payload
    assert route_is_read_only(historical_payload) is True
    assert route_allows_patch_localization(historical_payload) is False
    assert "obligation_preservation" not in historical_payload


def test_input_1_contract_still_carries_the_verbatim_raw_request():
    shape = derive_live_task_shape(T5_PROMPT, repository_available=True)

    assert shape.contract is not None
    assert shape.contract.raw_request.text == T5_PROMPT
    assert shape.contract.routing_allowed is True


def test_input_1_explicit_constraints_still_reach_the_contract():
    shape = derive_live_task_shape(LATE_CONSTRAINT, repository_available=True)

    prohibitions = [
        item.text
        for item in shape.contract.explicit_evidence.constraints
        if item.kind == "prohibition"
    ]
    assert prohibitions


# ── 12. context budget ────────────────────────────────────────────────────────

def test_the_serialized_route_does_not_duplicate_the_raw_request_many_times():
    route = route_live_task(T5_PROMPT, repository_available=True)
    rendered = json.dumps(route.as_dict(), ensure_ascii=False)

    # The obligations appear once. The raw request itself is not copied into
    # the route receipt at all.
    assert rendered.count("highest-value architectural ideas") <= 1
