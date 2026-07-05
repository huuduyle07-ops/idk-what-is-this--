"""EVAL.N1 - Evidence Quality Planning (report-only).

Defines the deterministic plan for judging whether evidence actually supports a
patch, claim, validation result, benchmark result, or final answer. EVAL.N1
does not score real artifacts yet. It never runs validation or benchmarks, calls
models, applies patches, launches workers, invokes MCP tools, contacts networks,
writes databases, changes routes/auth/scoring gates, or approves/rejects work.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


REPORT_KIND = "evidence_quality_plan"
JSON_NAME = "evidence_quality_plan.json"
MD_NAME = "evidence_quality_plan.md"
DEFAULT_OUTPUT_ROOT = Path(".agent") / "eval" / "evidence_quality_plan"

EVIDENCE_QUALITY_PLAN_STATUSES: tuple[str, ...] = (
    "evidence_quality_plan_ready",
    "evidence_quality_plan_ready_with_warnings",
    "evidence_quality_plan_incomplete",
    "evidence_quality_plan_blocked",
)

FUTURE_VERDICTS: tuple[str, ...] = (
    "strongly_supported",
    "supported",
    "partially_supported",
    "weakly_supported",
    "unsupported",
    "contradicted",
    "missing_evidence",
    "not_applicable",
)

FUTURE_SCORE_FIELDS: tuple[str, ...] = (
    "claim_support_score",
    "patch_relevance_score",
    "validation_relevance_score",
    "benchmark_relevance_score",
    "contradiction_risk_score",
    "missing_evidence_score",
    "confidence_alignment_score",
    "overall_evidence_quality_score",
)

SUPPORTED_ARTIFACT_TYPES: tuple[str, ...] = (
    "patch proposal JSON",
    "diff file",
    "validation result JSON/text",
    "benchmark result JSON/text",
    "replay comparison artifact",
    "Mirror Tunnel trace/scoring preview",
    "Commander review pack",
    "final answer text",
    "evidence pack artifact",
    "roadmap/phase registry artifact",
)

EVIDENCE_DIMENSIONS: tuple[dict[str, str], ...] = (
    {
        "dimension_id": "claim_support",
        "question": "Does the evidence support what the final answer claims?",
        "future_signal": "Compare final-answer claims against cited patch, validation, benchmark, replay, and warning artifacts.",
    },
    {
        "dimension_id": "patch_relevance",
        "question": "Does the patch touch files related to the stated goal?",
        "future_signal": "Compare changed paths and hunks with the task goal, suspected root cause, and forbidden/decoy file risks.",
    },
    {
        "dimension_id": "validation_relevance",
        "question": "Do validation/test results exercise the changed behavior?",
        "future_signal": "Check whether validation commands and named tests cover the files, paths, or behavior changed by the patch.",
    },
    {
        "dimension_id": "benchmark_relevance",
        "question": "Are benchmark cases relevant to the bug/task?",
        "future_signal": "Check whether benchmark case metadata matches the task language, failure mode, and claimed fix.",
    },
    {
        "dimension_id": "missing_evidence",
        "question": "What evidence is absent but required?",
        "future_signal": "List absent patch, diff, validation, benchmark, replay, or review artifacts required by the claim type.",
    },
    {
        "dimension_id": "evidence_freshness",
        "question": "Was evidence generated after the relevant patch/artifact?",
        "future_signal": "Classify evidence timestamps as pre_patch, post_patch, or unknown_timestamp.",
    },
    {
        "dimension_id": "contradiction_detection",
        "question": "Do claims contradict diff, validation, benchmark, replay, or warnings?",
        "future_signal": "Flag explicit disagreements between claims and artifact outcomes, warnings, skipped checks, or unchanged files.",
    },
    {
        "dimension_id": "confidence_alignment",
        "question": "Does the final answer overstate certainty compared with evidence?",
        "future_signal": "Compare words such as safe, verified, fixed, and complete against available support.",
    },
    {
        "dimension_id": "scope_alignment",
        "question": "Does the evidence cover the claimed scope, or only a smaller part?",
        "future_signal": "Check whether evidence supports the full claimed scope, one file, one test, formatting only, or a narrow smoke path.",
    },
    {
        "dimension_id": "human_review_boundary",
        "question": "Does the report clearly say what still requires human review?",
        "future_signal": "Require explicit human-review notes for unresolved judgment, visual evidence, policy, risk, or production readiness.",
    },
)

EVIDENCE_FRESHNESS_RULES: tuple[str, ...] = (
    "evidence generated before the relevant patch/artifact is pre_patch and should be marked stale",
    "evidence generated after the relevant patch/artifact may be post_patch",
    "unknown timestamp should warn, not block",
    "benchmark/validation claims must reference the result they came from",
    "final answer claims must not imply validation passed unless evidence exists",
)

CLAIM_VS_EVIDENCE_RULES: tuple[str, ...] = (
    "final answer claims must identify the evidence artifact that supports them",
    "final answer claims must not imply validation passed unless evidence exists",
    "a claim of fixed must be backed by a relevant patch plus relevant validation or an explicit no-validation boundary",
    "a claim of benchmark improvement must cite a benchmark artifact and case identity",
    "a claim must not silently expand beyond the evidence scope",
    "a warning in evidence must be carried forward unless a later artifact resolves it",
)

VALIDATION_BENCHMARK_RELEVANCE_RULES: tuple[str, ...] = (
    "validation is relevant when it exercises the changed behavior or changed files",
    "if changed files are not represented in tests/validation, warn",
    "benchmark relevance requires a case tied to the bug, language, failure mode, or claimed capability",
    "if evidence only covers formatting but claim says behavior fixed, warn or contradict",
    "validation and benchmark results must be distinguished from commands that were only planned",
)

MISSING_EVIDENCE_RULES: tuple[str, ...] = (
    "if patch exists but no validation result exists, warn",
    "if validation claim exists but no validation artifact exists, block in future scoring",
    "if benchmark claim exists but no benchmark artifact exists, block in future scoring",
    "if changed files are not represented in tests/validation, warn",
    "if no diff or patch artifact exists, patch relevance is missing_evidence",
    "if final answer cites an artifact that is absent, mark missing_evidence",
)

CONFIDENCE_ALIGNMENT_RULES: tuple[str, ...] = (
    "if final answer says safe or verified without evidence, mark confidence_overstated",
    "strongly_supported requires fresh, relevant, non-contradictory evidence",
    "supported allows narrow evidence only when the final answer states the same narrow scope",
    "partially_supported requires explicit uncovered scope",
    "unsupported or contradicted evidence must prevent confident completion language in future scoring",
)

HUMAN_REVIEW_BOUNDARY: tuple[str, ...] = (
    "human review remains required for production readiness, policy judgment, and risk acceptance",
    "future reports must name evidence gaps that require human review",
    "visual/UI evidence may require human review unless a later explicit visual evidence contract covers it",
    "unknown timestamps, missing artifacts, and contradiction warnings must stay visible to the human reviewer",
)

INTEGRATION_BOUNDARIES: tuple[str, ...] = (
    "report-only",
    "planning only",
    "deterministic/artifact planning only",
    "no model call",
    "no patch apply",
    "no validation run",
    "no benchmark run",
    "no MCP invocation",
    "no worker launch",
    "no Dream execution",
    "no Replay janitor apply",
    "no Docker/subprocess",
    "no network",
    "no database write",
    "no route behavior change",
    "no auth policy change",
    "no scoring gate change",
    "no automatic approval/rejection",
    "writes plan artifacts only",
)

GUARDRAIL_FALSE_FLAGS: tuple[str, ...] = (
    "model_call_performed",
    "patch_apply_performed",
    "validation_run_performed",
    "benchmark_run_performed",
    "mcp_invocation_performed",
    "worker_launch_performed",
    "dream_execution_performed",
    "replay_janitor_apply_performed",
    "docker_or_subprocess_used",
    "network_contacted",
    "database_write_performed",
    "route_behavior_changed",
    "auth_policy_changed",
    "scoring_gate_changed",
    "automatic_approval_or_rejection_performed",
    "evidence_scoring_performed",
)

EVIDENCE_QUALITY_PLAN_GUARDRAIL_NOTE = (
    "Evidence Quality Plan is report-only and planning-only: it defines how a "
    "future report should evaluate evidence support, freshness, relevance, "
    "contradictions, confidence alignment, scope, and human-review boundaries. "
    "It does not score a real patch, run validation or benchmarks, call models, "
    "apply patches, invoke MCP tools, launch workers, or change scoring gates."
)

RECOMMENDED_NEXT_PHASE = {
    "phase_id": "EVAL.N2",
    "title": "Evidence Quality Report Contract",
    "reason": (
        "Apply the EVAL.N1 plan to existing artifacts and produce a "
        "deterministic evidence quality report, still without running tests or "
        "benchmarks."
    ),
}


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _guardrails() -> dict[str, bool]:
    return {key: False for key in GUARDRAIL_FALSE_FLAGS}


def build_evidence_quality_plan() -> dict[str, Any]:
    """Build the deterministic EVAL.N1 evidence quality plan."""
    return {
        "report_kind": REPORT_KIND,
        "plan_id": "evidence-quality-plan",
        "guardrail_note": EVIDENCE_QUALITY_PLAN_GUARDRAIL_NOTE,
        "plan_status": "evidence_quality_plan_ready",
        "evidence_quality_purpose": (
            "Define how future C.A.T.T.U.S reports should decide whether "
            "evidence actually supports a patch, claim, validation result, "
            "benchmark result, or final answer."
        ),
        "evidence_dimensions": [dict(item) for item in EVIDENCE_DIMENSIONS],
        "supported_artifact_types": list(SUPPORTED_ARTIFACT_TYPES),
        "future_verdicts": list(FUTURE_VERDICTS),
        "future_score_fields": list(FUTURE_SCORE_FIELDS),
        "evidence_freshness_rules": list(EVIDENCE_FRESHNESS_RULES),
        "claim_vs_evidence_rules": list(CLAIM_VS_EVIDENCE_RULES),
        "validation_benchmark_relevance_rules": list(VALIDATION_BENCHMARK_RELEVANCE_RULES),
        "missing_evidence_rules": list(MISSING_EVIDENCE_RULES),
        "confidence_alignment_rules": list(CONFIDENCE_ALIGNMENT_RULES),
        "human_review_boundary": list(HUMAN_REVIEW_BOUNDARY),
        "integration_boundaries": list(INTEGRATION_BOUNDARIES),
        "guardrails": _guardrails(),
        "evidence_quality_plan_statuses": list(EVIDENCE_QUALITY_PLAN_STATUSES),
        "recommended_next_phase": dict(RECOMMENDED_NEXT_PHASE),
        "warnings": [],
        "blocked_reasons": [],
    }


def _render_list(lines: list[str], values: list[Any], *, code: bool = False) -> None:
    if values:
        for value in values:
            lines.append(f"- `{_md(value)}`" if code else f"- {_md(value)}")
    else:
        lines.append("_None._")
    lines.append("")


def render_evidence_quality_plan_markdown(report: dict[str, Any]) -> str:
    """Render an EVAL.N1 evidence quality plan as Markdown."""
    next_phase = report.get("recommended_next_phase") if isinstance(report.get("recommended_next_phase"), dict) else {}
    lines: list[str] = [
        "# Evidence Quality Plan",
        "",
        f"> {report.get('guardrail_note', EVIDENCE_QUALITY_PLAN_GUARDRAIL_NOTE)}",
        "",
        "_Report only: EVAL.N1 defines the evidence quality plan and scores no real patch or artifact._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Plan status:** `{_md(report.get('plan_status', ''))}`",
        f"- **Dimension count:** {len(report.get('evidence_dimensions') or [])}",
        f"- **Future verdict count:** {len(report.get('future_verdicts') or [])}",
        f"- **Future score field count:** {len(report.get('future_score_fields') or [])}",
        f"- **Recommended next phase:** `{_md(next_phase.get('phase_id', ''))}`",
        "",
        "## Evidence Quality Purpose",
        "",
        _md(report.get("evidence_quality_purpose", "")),
        "",
        "## Evidence Dimensions",
        "",
        "| Dimension | Question | Future signal |",
        "|---|---|---|",
    ]
    for item in report.get("evidence_dimensions") or []:
        lines.append(
            "| {dimension} | {question} | {future_signal} |".format(
                dimension=_md(item.get("dimension_id", "")),
                question=_md(item.get("question", "")),
                future_signal=_md(item.get("future_signal", "")),
            )
        )
    lines.append("")

    sections = (
        ("Supported Artifact Types", "supported_artifact_types", True),
        ("Future Verdicts", "future_verdicts", True),
        ("Future Score Fields", "future_score_fields", True),
        ("Evidence Freshness Rules", "evidence_freshness_rules", False),
        ("Claim-vs-Evidence Rules", "claim_vs_evidence_rules", False),
        ("Validation/Benchmark Relevance Rules", "validation_benchmark_relevance_rules", False),
        ("Missing Evidence Rules", "missing_evidence_rules", False),
        ("Confidence Alignment Rules", "confidence_alignment_rules", False),
        ("Human Review Boundary", "human_review_boundary", False),
        ("Integration Boundaries", "integration_boundaries", False),
    )
    for title, key, code in sections:
        lines += [f"## {title}", ""]
        _render_list(lines, list(report.get(key) or []), code=code)

    lines += ["## Guardrails", ""]
    guardrails = report.get("guardrails") if isinstance(report.get("guardrails"), dict) else {}
    for key in sorted(guardrails):
        lines.append(f"- `{_md(key)}`: {str(bool(guardrails[key])).lower()}")
    lines.append("")

    lines += [
        "## Recommended Next Phase",
        "",
        f"- **Phase:** `{_md(next_phase.get('phase_id', ''))}`",
        f"- **Title:** {_md(next_phase.get('title', ''))}",
        f"- **Reason:** {_md(next_phase.get('reason', ''))}",
        "",
    ]
    return "\n".join(lines)


def write_evidence_quality_plan(output_dir: str | Path = DEFAULT_OUTPUT_ROOT) -> dict[str, Any]:
    """Build and write EVAL.N1 JSON + Markdown plan artifacts."""
    report = build_evidence_quality_plan()
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_evidence_quality_plan_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
