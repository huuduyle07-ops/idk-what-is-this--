"""CTX.PATCH.1 score separation, explanation, and deduplication tests."""

from __future__ import annotations

import copy

from core.file_patchability import (
    PATCHABILITY_BANDS,
    calculate_patchability_score,
    patchability_band,
    score_file_patchability,
)


def _evidence(kind: str, detail: str, evidence_id: str | None = None) -> dict:
    result = {"kind": kind, "detail": detail, "origin": "ctx_read"}
    if evidence_id is not None:
        result["evidence_id"] = evidence_id
    return result


def test_actionability_and_patchability_are_distinct_scores() -> None:
    candidate = {
        "path": "core/router.py",
        "actionability_score": 99,
        "patchability_evidence": [
            _evidence("direct_read_target_confirmation", "named branch")
        ],
    }

    score = score_file_patchability(candidate)

    assert candidate["actionability_score"] == 99
    assert score.patchability_score == 25
    assert "actionability_score" not in score.as_dict()


def test_high_relevance_may_have_low_patchability() -> None:
    score = calculate_patchability_score(
        "core/public_api.py",
        [_evidence("direct_read_target_confirmation", "relevant entrypoint")],
        risks=["shared_public_api", "unknown_blast_radius", "validation_gap"],
    )

    assert score.patchability_score == 0
    assert score.patchability_band == "blocked_or_forbidden"


def test_patchability_is_bounded_zero_through_one_hundred() -> None:
    high = calculate_patchability_score(
        "core/router.py",
        [
            _evidence(kind, kind)
            for kind in (
                "direct_read_target_confirmation",
                "diagnosis_confidence",
                "change_locality",
                "symbol_or_branch_specificity",
                "validation_coverage",
                "reversibility",
                "matching_test_or_linter",
                "authoritative_source_confidence",
            )
        ],
    )
    low = calculate_patchability_score(
        "core/router.py",
        [],
        risks=["critical_blast_radius", "validation_gap"],
    )

    assert high.patchability_score == 100
    assert low.patchability_score == 0
    assert {patchability_band(value) for value in range(101)} == {
        band for _, _, band in PATCHABILITY_BANDS
    }


def test_score_evidence_and_risk_adjustments_are_explainable() -> None:
    score = calculate_patchability_score(
        "core/router.py",
        [
            _evidence("direct_read_target_confirmation", "dispatch branch"),
            _evidence("matching_test", "tests/test_router.py"),
        ],
        risks=[
            {
                "kind": "high_dependency_centrality",
                "detail": "shared dispatcher",
            }
        ],
    )
    rendered = score.as_dict()

    assert rendered["patchability_score"] == 31
    assert rendered["positive_evidence"] == [
        {
            "kind": "direct_read_target_confirmation",
            "weight": 25,
            "detail": "dispatch branch",
            "origin": "ctx_read",
        },
        {
            "kind": "matching_test_or_linter",
            "weight": 18,
            "detail": "tests/test_router.py",
            "origin": "ctx_read",
        },
    ]
    assert rendered["risk_adjustments"] == [
        {
            "kind": "high_dependency_centrality",
            "weight": -12,
            "detail": "shared dispatcher",
        }
    ]
    assert rendered["write_authority"] is False
    assert rendered["patch_application_authority"] is False
    assert rendered["human_approval_required"] is True


def test_duplicate_evidence_is_not_counted_across_context_stages() -> None:
    supplied = [
        {
            **_evidence(
                "direct_read_target_confirmation",
                "same branch",
                "fact-1",
            ),
            "origin": origin,
        }
        for origin in ("ctx_select", "ctx_search", "ctx_read")
    ]
    before = copy.deepcopy(supplied)

    score = calculate_patchability_score("core/router.py", supplied)

    assert score.patchability_score == 25
    assert len(score.positive_evidence) == 1
    assert supplied == before


def test_repeated_dimension_is_capped_even_with_distinct_evidence_ids() -> None:
    score = calculate_patchability_score(
        "core/router.py",
        [
            _evidence("matching_test", "tests/test_a.py", "test-a"),
            _evidence("matching_test", "tests/test_b.py", "test-b"),
        ],
    )

    assert score.patchability_score == 18
    assert len(score.positive_evidence) == 1


def test_actionability_evidence_is_ignored_instead_of_double_counted() -> None:
    score = calculate_patchability_score(
        "core/router.py",
        [
            _evidence("lexical_match", "router"),
            _evidence("direct_symbol_reference", "dispatch"),
            _evidence("direct_read_target_confirmation", "dispatch branch"),
        ],
    )

    assert score.patchability_score == 25
    assert score.ignored_evidence_kinds == (
        "direct_symbol_reference",
        "lexical_match",
    )


def test_hard_block_is_explainable_and_overrides_positive_score() -> None:
    score = calculate_patchability_score(
        ".env",
        [
            _evidence("direct_read_target_confirmation", "named setting"),
            _evidence("diagnosis_confidence", "known correction"),
            _evidence("change_locality", "one value"),
            _evidence("matching_test", "tests/test_settings.py"),
        ],
        hard_blocked=True,
    )

    assert score.patchability_score == 0
    assert score.hard_blocked is True
    assert score.positive_evidence
