from __future__ import annotations

from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class EvidenceConfidence:
    source_type: str
    confidence: float
    reason: str
    is_blocking: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_type", (self.source_type or "unknown").strip() or "unknown")
        object.__setattr__(self, "confidence", _clamp_confidence(self.confidence))
        object.__setattr__(self, "reason", self.reason or "No confidence reason provided.")


def classify_evidence_confidence(
    source_type: str,
    *,
    has_exact_quote: bool = False,
    has_benchmark_result: bool = False,
    has_linter_finding: bool = False,
    graph_distance: int | None = None,
    is_llm_only: bool = False,
    is_missing: bool = False,
) -> EvidenceConfidence:
    normalized = _normalize_source_type(source_type)

    if is_missing or normalized == "missing":
        return EvidenceConfidence("missing", 0.0, "Evidence is missing.")

    if has_exact_quote or normalized == "exact_quote":
        return EvidenceConfidence("exact_quote", 1.0, "Exact source quote provides direct grounding.")

    if has_benchmark_result or normalized == "benchmark":
        return EvidenceConfidence("benchmark", 0.95, "Benchmark result provides direct executable evidence.")

    if has_linter_finding or normalized in {"linter", "static_analysis"}:
        source = "linter" if has_linter_finding or normalized == "linter" else "static_analysis"
        return EvidenceConfidence(source, 0.75, "Static analysis or linter finding provides tool-grounded evidence.")

    if graph_distance is not None or normalized == "graph_proximity":
        distance_scores = {0: 0.70, 1: 0.55, 2: 0.40}
        if graph_distance in distance_scores:
            return EvidenceConfidence(
                "graph_proximity",
                distance_scores[graph_distance],
                f"Graph proximity evidence at distance {graph_distance}.",
            )
        return EvidenceConfidence(
            "graph_proximity",
            0.0,
            "Graph proximity evidence is unavailable or outside the supported distance window.",
        )

    if is_llm_only or normalized == "llm_claim":
        return EvidenceConfidence("llm_claim", 0.25, "LLM-only claim is weak until grounded by external evidence.")

    return EvidenceConfidence("unknown", 0.0, "Evidence source is missing or unknown.")


def combine_evidence_confidences(items: list[EvidenceConfidence]) -> EvidenceConfidence:
    if not items:
        return EvidenceConfidence("unknown", 0.0, "No evidence confidence items were provided.", is_blocking=True)

    strongest = max(items, key=lambda item: item.confidence)
    blocking = all(_is_weak_or_absent(item) for item in items)
    reason = (
        f"Strongest evidence source: {strongest.source_type} "
        f"({strongest.confidence:.2f}). {strongest.reason}"
    )
    return EvidenceConfidence("combined", strongest.confidence, reason, is_blocking=blocking)


def format_evidence_confidence_block(items: list[EvidenceConfidence]) -> str:
    combined = combine_evidence_confidences(items)
    lines = ["### Evidence Confidence"]

    if items:
        for item in items:
            suffix = " [blocking]" if item.is_blocking else ""
            lines.append(f"- {item.source_type}: {item.confidence:.2f}{suffix} - {item.reason}")
    else:
        lines.append("- unknown: 0.00 [blocking] - No evidence confidence items were provided.")

    combined_suffix = " [blocking]" if combined.is_blocking else ""
    lines.append(f"**Combined:** {combined.confidence:.2f}{combined_suffix} - {combined.reason}")
    return "\n".join(lines)


def _normalize_source_type(source_type: str) -> str:
    return (source_type or "unknown").strip().lower()


def _clamp_confidence(value: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not isfinite(numeric):
        return 0.0
    return min(1.0, max(0.0, numeric))


def _is_weak_or_absent(item: EvidenceConfidence) -> bool:
    return item.source_type in {"missing", "unknown", "llm_claim"} and item.confidence < 0.30
