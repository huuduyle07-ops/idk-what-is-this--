"""Focused contracts for deterministic CTX.SELECT.1 actionability scoring."""

from __future__ import annotations

import copy

import pytest

from core.file_actionability import (
    MAX_SUPPLIED_ACTIONABILITY_EVIDENCE,
    MAX_SUPPLIED_RISK_ADJUSTMENTS,
    SCORING_STAGES,
    calculate_actionability_score,
    derive_candidate_action,
    score_band,
    score_file_actionability,
)
from core.file_capabilities import classify_file_capability


def _evidence(kind: str, detail: str | None = None, **extra: object) -> dict[str, object]:
    return {"kind": kind, "detail": detail or kind, **extra}


def _decision(score: object, capability: object):
    return derive_candidate_action(
        actionability_score=score.actionability_score,
        editability=capability.editability,
        readability=capability.readability,
        evidence=score.positive_evidence,
        read_policy=capability.read_policy,
        parser_support=capability.parser_support,
        authoritative_source=capability.authoritative_source,
    )


def test_strong_multi_source_evidence_raises_an_explainable_score() -> None:
    evidence = [
        _evidence("user_named_file", "core/router.py"),
        _evidence("direct_symbol_reference", "dispatch_request"),
        _evidence("test_pair", "tests/test_router.py"),
        _evidence("lexical_match", "router"),
    ]

    result = calculate_actionability_score("core/router.py", evidence)

    assert result.actionability_score == 95
    assert result.score_band == "primary_patch_candidate"
    assert [item.kind for item in result.positive_evidence] == [
        "direct_symbol_reference",
        "test_pair",
        "user_named_file",
        "lexical_match",
    ]
    assert all(isinstance(item.weight, int) for item in result.positive_evidence)
    assert result.filename_only is False


def test_filename_only_evidence_cannot_create_a_patch_candidate() -> None:
    capability = classify_file_capability("core/router.py", size_bytes=100)
    evidence = [
        _evidence("single_readable_file"),
        _evidence("likely_entrypoint"),
        _evidence("exact_filename_match"),
        _evidence("filename_token_match", "router-a"),
        _evidence("filename_token_match", "router-b"),
    ]
    score = score_file_actionability(capability, evidence)
    decision = _decision(score, capability)

    assert score.actionability_score == 100
    assert score.filename_only is True
    assert decision.action == "propose_read"
    assert decision.can_propose_patch is False
    assert any("filename-only evidence" in warning for warning in decision.warnings)
    assert decision.write_authority is False


def test_matching_test_increases_validation_confidence_score() -> None:
    base = [
        _evidence("user_named_file", "core/router.py"),
        _evidence("direct_symbol_reference", "dispatch_request"),
    ]
    without_test = calculate_actionability_score("core/router.py", base)
    with_test = calculate_actionability_score(
        "core/router.py",
        [*base, _evidence("test_pair", "tests/test_router.py")],
    )

    assert with_test.actionability_score - without_test.actionability_score == 15
    assert any(item.kind == "test_pair" for item in with_test.positive_evidence)


def test_high_blast_radius_applies_a_stable_penalty() -> None:
    evidence = [_evidence("user_named_file"), _evidence("direct_symbol_reference")]
    baseline = calculate_actionability_score("core/router.py", evidence)
    penalized = calculate_actionability_score(
        "core/router.py",
        evidence,
        risks=["high_blast_radius"],
    )

    assert baseline.actionability_score == 60
    assert penalized.actionability_score == 45
    assert penalized.risk_adjustments[0].kind == "high_blast_radius"
    assert penalized.risk_adjustments[0].weight == -15


def test_generated_state_overrides_high_relevance_and_redirects() -> None:
    capability = classify_file_capability(
        "generated/router.py",
        size_bytes=100,
        authoritative_source="schema/router.json",
    )
    evidence = [
        _evidence("user_named_file"),
        _evidence("direct_symbol_reference"),
        _evidence("test_pair"),
        _evidence("lexical_match"),
    ]
    score = score_file_actionability(capability, evidence)
    decision = _decision(score, capability)

    assert score.actionability_score == 75
    assert any(item.kind == "generated_or_vendor" for item in score.risk_adjustments)
    assert decision.action == "redirect_to_authoritative_source"
    assert decision.authoritative_source == "schema/router.json"
    assert decision.can_propose_patch is False
    assert decision.write_authority is False


@pytest.mark.parametrize("editability", ["forbidden", "outside_scope"])
def test_forbidden_state_overrides_every_score(editability: str) -> None:
    capability = {
        "path": "core/router.py",
        "parser_support": "supported",
        "editability": editability,
    }
    evidence = [
        _evidence("user_named_file"),
        _evidence("direct_symbol_reference"),
        _evidence("test_pair"),
        _evidence("lexical_match"),
    ]
    score = score_file_actionability(capability, evidence)
    decision = derive_candidate_action(
        actionability_score=100,
        editability=editability,
        readability="readable_text",
        evidence=evidence,
    )

    assert score.actionability_score == 0
    assert score.forbidden_override is True
    assert all(entry.score == 0 for entry in score.score_history)
    assert decision.action == "exclude"
    assert decision.write_authority is False


def test_score_is_always_bounded_to_the_integer_range_zero_through_one_hundred() -> None:
    saturated = calculate_actionability_score(
        "core/router.py",
        [_evidence(kind) for kind in (
            "user_named_file",
            "user_named_symbol",
            "exact_filename_match",
            "filename_token_match",
            "path_token_match",
            "likely_entrypoint",
            "configuration_file",
            "test_pair",
            "direct_import_reference",
            "direct_symbol_reference",
            "lexical_match",
            "task_term_match",
            "recent_change_hint",
            "single_readable_file",
        )],
    )
    floored = calculate_actionability_score(
        "core/router.py",
        (),
        risks=[
            "high_dependency_centrality",
            "high_blast_radius",
            "file_class_risk",
            "validation_gap",
        ],
    )

    assert saturated.actionability_score == 100
    assert isinstance(saturated.actionability_score, int)
    assert floored.actionability_score == 0
    assert all(0 <= entry.score <= 100 for entry in (*saturated.score_history, *floored.score_history))


def test_duplicate_evidence_is_not_double_counted() -> None:
    item = _evidence(
        "direct_symbol_reference",
        "dispatch_request",
        evidence_id="symbol:dispatch_request",
    )
    single = calculate_actionability_score("core/router.py", [item])
    duplicate = calculate_actionability_score(
        "core/router.py",
        [item, copy.deepcopy(item), {**item, "weight": 999}],
    )

    assert duplicate == single
    assert duplicate.actionability_score == 25
    assert len(duplicate.positive_evidence) == 1


def test_actionability_evidence_and_risk_intake_are_defensively_bounded() -> None:
    with pytest.raises(ValueError, match="evidence exceeds"):
        calculate_actionability_score(
            "core/router.py",
            (
                _evidence("lexical_match", f"match_{index}")
                for index in range(MAX_SUPPLIED_ACTIONABILITY_EVIDENCE + 1)
            ),
        )
    with pytest.raises(ValueError, match="risks exceeds"):
        calculate_actionability_score(
            "core/router.py",
            [],
            risks=(
                {"kind": "high_blast_radius", "detail": f"risk_{index}"}
                for index in range(MAX_SUPPLIED_RISK_ADJUSTMENTS + 1)
            ),
        )


def test_risk_kind_is_counted_once_with_deterministic_detail() -> None:
    risks = [
        {"kind": "high_blast_radius", "detail": "z-last"},
        {"kind": "high_blast_radius", "detail": "a-first"},
    ]

    first = calculate_actionability_score(
        "core/router.py",
        [_evidence("user_named_file")],
        risks=risks,
    )
    second = calculate_actionability_score(
        "core/router.py",
        [_evidence("user_named_file")],
        risks=reversed(risks),
    )

    assert first == second
    assert first.actionability_score == 20
    assert [(item.kind, item.detail) for item in first.risk_adjustments] == [
        ("high_blast_radius", "a-first")
    ]


def test_stage_history_is_deterministic_and_inputs_are_not_mutated() -> None:
    evidence = [
        _evidence("lexical_match", "router"),
        _evidence("exact_filename_match", "router.py"),
        _evidence("likely_entrypoint", "main"),
    ]
    before = copy.deepcopy(evidence)

    first = calculate_actionability_score("core/router.py", evidence)
    second = calculate_actionability_score("core/router.py", reversed(evidence))

    assert first == second
    assert evidence == before
    assert tuple(item.stage for item in first.score_history) == SCORING_STAGES
    assert tuple(item.score for item in first.score_history) == (10, 36, 56)
    assert first.as_dict() == second.as_dict()


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100, "primary_patch_candidate"),
        (80, "primary_patch_candidate"),
        (79, "inspect_before_patch"),
        (60, "inspect_before_patch"),
        (59, "supporting_context"),
        (35, "supporting_context"),
        (34, "low_priority_context"),
        (1, "low_priority_context"),
        (0, "forbidden_or_no_evidence"),
    ],
)
def test_score_band_boundaries_are_pinned(score: int, expected: str) -> None:
    assert score_band(score) == expected


def test_read_only_file_can_be_proposed_for_read_but_never_patch() -> None:
    decision = derive_candidate_action(
        actionability_score=95,
        editability="read_only",
        readability="readable_text",
        evidence=[_evidence("direct_symbol_reference")],
    )

    assert decision.action == "propose_read"
    assert decision.can_propose_read is True
    assert decision.can_propose_patch is False
    assert decision.write_authority is False


def test_sensitive_file_requires_human_approval_regardless_of_score() -> None:
    decision = derive_candidate_action(
        actionability_score=100,
        editability="sensitive_requires_approval",
        readability="sensitive",
        read_policy="explicit_human_approval_required",
        evidence=[_evidence("direct_symbol_reference")],
    )

    assert decision.action == "requires_human_approval"
    assert decision.can_propose_read is False
    assert decision.can_propose_patch is False
    assert decision.write_authority is False


def test_unsupported_readable_text_can_be_inspect_before_patch_with_reduced_confidence() -> None:
    capability = classify_file_capability("core/router.yaml", size_bytes=100)
    evidence = [
        _evidence("user_named_file"),
        _evidence("direct_symbol_reference"),
        _evidence("test_pair"),
    ]
    score = score_file_actionability(capability, evidence)
    decision = _decision(score, capability)

    assert score.actionability_score == 67
    assert any(item.kind == "parser_unsupported" for item in score.risk_adjustments)
    assert decision.action == "propose_inspect_then_patch"
    assert decision.can_propose_patch is True
    assert decision.write_authority is False
    assert any("raw textual understanding only" in warning for warning in decision.warnings)
    assert "editability requires review" in decision.warnings
