from __future__ import annotations
from typing import Any, Dict, List

from graph.query import explain_symbol, impact_analysis

def analyze_symbol_risk(graph, symbol_name: str) -> Dict[str, Any]:
    info = explain_symbol(graph, symbol_name)
    impacted = impact_analysis(graph, symbol_name)

    risk_score = 1 # Base risk for any candidate
    reasons = []

    if impacted:
        reasons.append(f"Symbol is used by {len(impacted)} upstream caller(s).")

    if info["calls"]:
        reasons.append(f"Symbol calls {len(info['calls'])} downstream symbol(s).")

    if not impacted and not info["calls"]:
        reasons.append("Isolated symbol or missing graph context.")

    if len(impacted) > 3:
        reasons.append("High propagation risk")

    if len(info["calls"]) > 4:
        reasons.append("Deep call chain")

    risk_score += (
        len(impacted) * 2 +
        len(info["calls"])
    )
    if risk_score >= 6:
        level = "high"
    elif risk_score >= 3:
        level = "medium"
    else:
        level = "low"

    return {
        "symbol": symbol_name,
        "risk_level": level,
        "risk_score": risk_score,
        "called_by": info["called_by"],
        "calls": info["calls"],
        "reasons": reasons,
    }


def explain_root_cause(graph, symptom_symbol: str) -> Dict[str, Any]:
    info = explain_symbol(graph, symptom_symbol)
    impacted = impact_analysis(graph, symptom_symbol)

    return {
        "symptom": symptom_symbol,
        "likely_root": symptom_symbol,
        "called_by": info["called_by"],
        "calls": info["calls"],
        "impact": impacted,
        "reason": (
            "This symbol is likely relevant because it participates in the resolved call graph."
            if info["called_by"] or info["calls"]
            else "No strong graph relationship found; treat as local issue."
        ),
    }


def build_reasoning_context(graph, candidates: List[str]) -> str:
    lines = ["=== REASONING ENGINE CONTEXT ==="]

    if not hasattr(graph, "nodes") or not graph.nodes:
        lines.append("[WARNING] Project graph is empty or unindexed. Reasoning results may be incomplete.")

    for name in candidates:
        root = explain_root_cause(graph, name)
        risk = analyze_symbol_risk(graph, name)

        lines.append(f"\nSymbol: {name}")
        lines.append(f"- likely_root: {root['likely_root']}")
        lines.append(f"- called_by: {root['called_by']}")
        lines.append(f"- calls: {root['calls']}")
        lines.append(f"- impact: {root['impact']}")
        lines.append(f"- risk: {risk['risk_level']} ({risk['risk_score']})")

        for r in risk["reasons"]:
            lines.append(f"  - {r}")

    return "\n".join(lines)