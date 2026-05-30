from __future__ import annotations

from dataclasses import FrozenInstanceError

from core.evidence_confidence import (
    EvidenceConfidence,
    classify_evidence_confidence,
    combine_evidence_confidences,
    format_evidence_confidence_block,
)


def test_exact_quote_confidence_is_highest_and_immutable():
    evidence = classify_evidence_confidence("exact_quote")

    assert evidence == EvidenceConfidence(
        source_type="exact_quote",
        confidence=1.0,
        reason="Exact source quote provides direct grounding.",
    )

    try:
        evidence.confidence = 0.2
    except FrozenInstanceError:
        pass
    else:
        raise AssertionError("EvidenceConfidence must be immutable")


def test_exact_quote_flag_overrides_source_type():
    evidence = classify_evidence_confidence("unknown", has_exact_quote=True)

    assert evidence.source_type == "exact_quote"
    assert evidence.confidence == 1.0


def test_benchmark_confidence_from_source_type_and_flag():
    assert classify_evidence_confidence("benchmark").confidence == 0.95
    flagged = classify_evidence_confidence("unknown", has_benchmark_result=True)
    assert flagged.source_type == "benchmark"
    assert flagged.confidence == 0.95


def test_linter_and_static_analysis_confidence():
    assert classify_evidence_confidence("linter").confidence == 0.75
    assert classify_evidence_confidence("static_analysis").confidence == 0.75
    flagged = classify_evidence_confidence("unknown", has_linter_finding=True)
    assert flagged.source_type == "linter"
    assert flagged.confidence == 0.75


def test_graph_proximity_distances_zero_one_two():
    distance_zero = classify_evidence_confidence("graph_proximity", graph_distance=0)
    distance_one = classify_evidence_confidence("graph_proximity", graph_distance=1)
    distance_two = classify_evidence_confidence("graph_proximity", graph_distance=2)

    assert distance_zero.confidence == 0.70
    assert distance_one.confidence == 0.55
    assert distance_two.confidence == 0.40
    assert "distance 0" in distance_zero.reason
    assert "distance 1" in distance_one.reason
    assert "distance 2" in distance_two.reason


def test_graph_distance_without_graph_source_type_still_classifies_as_graph_proximity():
    evidence = classify_evidence_confidence("unknown", graph_distance=1)

    assert evidence.source_type == "graph_proximity"
    assert evidence.confidence == 0.55


def test_llm_only_confidence_from_source_type_and_flag():
    assert classify_evidence_confidence("llm_claim").confidence == 0.25
    flagged = classify_evidence_confidence("unknown", is_llm_only=True)
    assert flagged.source_type == "llm_claim"
    assert flagged.confidence == 0.25


def test_missing_and_unknown_confidence_are_zero():
    assert classify_evidence_confidence("missing").confidence == 0.0
    assert classify_evidence_confidence("unknown").confidence == 0.0

    missing = classify_evidence_confidence("benchmark", is_missing=True)
    assert missing.source_type == "missing"
    assert missing.confidence == 0.0


def test_dataclass_clamps_confidence_values():
    high = EvidenceConfidence("manual", 1.5, "above range")
    low = EvidenceConfidence("manual", -0.5, "below range")

    assert high.confidence == 1.0
    assert low.confidence == 0.0


def test_combine_uses_max_confidence_and_mentions_strongest_source():
    items = [
        classify_evidence_confidence("llm_claim"),
        classify_evidence_confidence("graph_proximity", graph_distance=2),
        classify_evidence_confidence("benchmark"),
    ]

    combined = combine_evidence_confidences(items)

    assert combined.source_type == "combined"
    assert combined.confidence == 0.95
    assert "benchmark" in combined.reason
    assert combined.is_blocking is False


def test_empty_combine_returns_blocking_unknown_zero():
    combined = combine_evidence_confidences([])

    assert combined.source_type == "unknown"
    assert combined.confidence == 0.0
    assert combined.is_blocking is True
    assert "No evidence" in combined.reason


def test_combine_blocks_only_when_all_evidence_is_weak_or_absent():
    weak_items = [
        classify_evidence_confidence("missing"),
        classify_evidence_confidence("unknown"),
        classify_evidence_confidence("llm_claim"),
    ]
    mixed_items = weak_items + [classify_evidence_confidence("graph_proximity", graph_distance=2)]

    assert combine_evidence_confidences(weak_items).is_blocking is True
    assert combine_evidence_confidences(mixed_items).is_blocking is False


def test_markdown_formatting_includes_items_and_combined_summary():
    items = [
        classify_evidence_confidence("exact_quote"),
        classify_evidence_confidence("llm_claim"),
    ]

    block = format_evidence_confidence_block(items)

    assert block.startswith("### Evidence Confidence")
    assert "- exact_quote: 1.00" in block
    assert "- llm_claim: 0.25" in block
    assert "**Combined:** 1.00" in block
    assert "Strongest evidence source: exact_quote" in block
