"""INPUT.1 — deterministic explicit-evidence extraction tests.

The extractor exists to preserve literal user commitments.  It must never
guess meaning; every test below asserts on text the user literally supplied.
"""

from __future__ import annotations

import dataclasses

import pytest

from core.explicit_evidence import (
    MAX_CONSTRAINTS,
    MAX_FRAMEWORK_VALUES,
    MAX_LIST_ITEMS,
    MAX_NAMED_ENTITIES,
    ExplicitEvidence,
    extract_explicit_evidence,
)


DOGFOOD_PROMPT = """Analyze DeepSeek Harness against C.A.T.T.U.S using the following framework:

- Equivalent
- DeepSeek stronger
- C.A.T.T.U.S stronger
- Orthogonal
- Not worth adopting
"""


# ── list items ────────────────────────────────────────────────────────────────

def test_bullet_items_are_extracted_in_supplied_order():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert evidence.list_items == (
        "Equivalent",
        "DeepSeek stronger",
        "C.A.T.T.U.S stronger",
        "Orthogonal",
        "Not worth adopting",
    )


def test_numbered_list_items_are_extracted_in_supplied_order():
    evidence = extract_explicit_evidence("Rank them:\n1. speed\n2. safety\n3. cost\n")

    assert evidence.list_items == ("speed", "safety", "cost")


# ── framework / rubric ────────────────────────────────────────────────────────

def test_framework_cue_binds_the_following_list_as_an_ordered_rubric():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert evidence.framework is not None
    assert evidence.framework.type == "framework"
    assert evidence.framework.ordered is True
    assert evidence.framework.values == (
        "Equivalent",
        "DeepSeek stronger",
        "C.A.T.T.U.S stronger",
        "Orthogonal",
        "Not worth adopting",
    )


def test_rubric_cue_is_recognised_and_typed():
    evidence = extract_explicit_evidence("Score it using this rubric:\n- good\n- bad\n")

    assert evidence.framework is not None
    assert evidence.framework.type == "rubric"
    assert evidence.framework.values == ("good", "bad")


def test_list_before_the_cue_is_not_bound_as_framework_values():
    text = "- stray note\n\nScore it using this rubric:\n- good\n- bad\n"
    evidence = extract_explicit_evidence(text)

    assert evidence.framework is not None
    assert evidence.framework.values == ("good", "bad")
    assert "stray note" in evidence.list_items


def test_no_framework_when_no_cue_is_supplied():
    evidence = extract_explicit_evidence("Some notes:\n- alpha\n- beta\n")

    assert evidence.framework is None


# ── named entities ────────────────────────────────────────────────────────────

def test_dotted_acronym_is_preserved_verbatim_as_named_entity():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert "C.A.T.T.U.S" in evidence.named_entities


def test_multiword_titlecase_run_is_a_named_entity_without_the_leading_verb():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert "DeepSeek Harness" in evidence.named_entities
    assert "Analyze DeepSeek Harness" not in evidence.named_entities


def test_lowercase_prose_produces_no_named_entities():
    evidence = extract_explicit_evidence("can you explain how the cache works?")

    assert evidence.named_entities == ()


def test_common_latin_abbreviations_are_not_named_entities():
    evidence = extract_explicit_evidence("Use the cache, e.g. redis, i.e. the fast one.")

    assert "e.g." not in evidence.named_entities
    assert "i.e." not in evidence.named_entities


# ── comparisons ───────────────────────────────────────────────────────────────

def test_analyze_against_yields_a_two_subject_comparison():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert len(evidence.comparisons) == 1
    comparison = evidence.comparisons[0]
    assert comparison.subjects == ("DeepSeek Harness", "C.A.T.T.U.S")
    assert comparison.marker == "against"


def test_compare_with_yields_a_two_subject_comparison():
    evidence = extract_explicit_evidence("Compare Redis with Memcached please.")

    assert evidence.comparisons[0].subjects == ("Redis", "Memcached")


def test_bare_vs_yields_a_two_subject_comparison():
    evidence = extract_explicit_evidence("Redis vs Memcached: which is faster?")

    assert evidence.comparisons[0].subjects == ("Redis", "Memcached")


def test_leading_article_is_stripped_from_comparison_subjects():
    evidence = extract_explicit_evidence("Compare the harness against the router.")

    assert evidence.comparisons[0].subjects == ("harness", "router")


def test_output_format_cue_ends_a_comparison_subject():
    evidence = extract_explicit_evidence("Compare Redis with Memcached as a table.")

    assert evidence.comparisons[0].subjects == ("Redis", "Memcached")


def test_non_comparative_request_has_no_comparisons():
    evidence = extract_explicit_evidence("Fix the failing test in the parser.")

    assert evidence.comparisons == ()


# ── urls / paths / quotes ─────────────────────────────────────────────────────

def test_urls_are_extracted_without_trailing_punctuation():
    evidence = extract_explicit_evidence("See https://example.com/spec.html, then stop.")

    assert evidence.urls == ("https://example.com/spec.html",)


def test_file_paths_are_extracted():
    evidence = extract_explicit_evidence("Patch core/router.py and tests/test_router.py only.")

    assert evidence.file_paths == ("core/router.py", "tests/test_router.py")


def test_url_segments_are_not_reported_as_file_paths():
    evidence = extract_explicit_evidence("Read https://example.com/docs/spec.md now.")

    assert evidence.file_paths == ()


def test_double_quoted_and_backticked_terms_are_extracted():
    evidence = extract_explicit_evidence('Keep the "hot path" and the `fast_lane` flag.')

    assert evidence.quoted_terms == ("hot path", "fast_lane")


def test_apostrophes_do_not_create_quoted_terms():
    evidence = extract_explicit_evidence("don't break it's behaviour")

    assert evidence.quoted_terms == ()


# ── constraints ───────────────────────────────────────────────────────────────

def test_prohibition_constraint_is_captured_verbatim():
    evidence = extract_explicit_evidence("Fix the bug. Do not modify tests.")

    kinds = {(item.kind, item.text) for item in evidence.constraints}
    assert ("prohibition", "Do not modify tests") in kinds


def test_must_constraint_is_captured():
    evidence = extract_explicit_evidence("The output must stay deterministic.")

    assert evidence.constraints[0].kind == "requirement"
    assert evidence.constraints[0].text == "The output must stay deterministic"


def test_only_constraint_is_captured_as_restriction():
    evidence = extract_explicit_evidence("Touch only the parser module.")

    assert evidence.constraints[0].kind == "restriction"


def test_framework_cue_is_captured_as_a_framework_reference_constraint():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert any(item.kind == "framework_reference" for item in evidence.constraints)


def test_must_not_is_a_prohibition_not_a_requirement():
    evidence = extract_explicit_evidence("You must not touch the database.")

    assert evidence.constraints[0].kind == "prohibition"


# ── requested output ──────────────────────────────────────────────────────────

def test_requested_table_output_is_extracted():
    evidence = extract_explicit_evidence("Give me the results as a table.")

    assert tuple(item.format for item in evidence.requested_outputs) == ("table",)


def test_requested_json_output_is_extracted():
    evidence = extract_explicit_evidence("Respond in JSON.")

    assert tuple(item.format for item in evidence.requested_outputs) == ("json",)


def test_no_output_cue_yields_no_requested_output():
    evidence = extract_explicit_evidence("Explain the cache.")

    assert evidence.requested_outputs == ()


# ── shape / bounds / purity ───────────────────────────────────────────────────

def test_conversational_input_yields_empty_evidence():
    evidence = extract_explicit_evidence("hey, what is up?")

    assert evidence.is_empty() is True


def test_dogfood_prompt_is_not_empty_evidence():
    assert extract_explicit_evidence(DOGFOOD_PROMPT).is_empty() is False


def test_collections_are_bounded_and_truncation_is_reported():
    text = "Notes:\n" + "\n".join(f"- item {n}" for n in range(MAX_LIST_ITEMS + 25))
    evidence = extract_explicit_evidence(text)

    assert len(evidence.list_items) == MAX_LIST_ITEMS
    assert "list_items" in evidence.truncated_fields


def test_framework_values_are_bounded():
    text = "Use this rubric:\n" + "\n".join(f"- v{n}" for n in range(MAX_FRAMEWORK_VALUES + 5))
    evidence = extract_explicit_evidence(text)

    assert evidence.framework is not None
    assert len(evidence.framework.values) == MAX_FRAMEWORK_VALUES


def test_named_entities_and_constraints_are_bounded():
    assert MAX_NAMED_ENTITIES > 0
    assert MAX_CONSTRAINTS > 0


def test_evidence_records_are_immutable():
    evidence = extract_explicit_evidence(DOGFOOD_PROMPT)

    with pytest.raises(dataclasses.FrozenInstanceError):
        evidence.named_entities = ()  # type: ignore[misc]


def test_extraction_is_deterministic():
    first = extract_explicit_evidence(DOGFOOD_PROMPT)
    second = extract_explicit_evidence(DOGFOOD_PROMPT)

    assert first.as_dict() == second.as_dict()


def test_empty_input_is_accepted():
    evidence = extract_explicit_evidence("")

    assert isinstance(evidence, ExplicitEvidence)
    assert evidence.is_empty() is True
