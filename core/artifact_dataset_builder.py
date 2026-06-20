"""MODEL.1 — C.A.T.T.U.S Artifact Dataset Builder (report-only).

Scans existing C.A.T.T.U.S artifacts under ``.agent`` (goal briefs, worker
assignments, driver decisions, visual evidence contracts, worker result reviews,
flaky case reviews, self-evolution evidence packs, the Telegram / GitHub / n8n
remote-safety contracts, phase registry and picker reports, and lesson teaching
cards) and normalizes each one into a stable dataset row for future model and
classifier experiments.

MODEL.1 builds data only. It does not train or call models, does not call
embeddings, does not write to a database, does not apply patches, does not run
validation or a benchmark check, does not launch workers, and does not contact
Telegram, GitHub, n8n, or any network service. Dataset rows are advisory
artifacts only and grant no execution authority.

This module is stdlib-only. Row normalization is pure: it reads an already-parsed
artifact dict and never mutates it. Only the writer touches the filesystem, and
only under the chosen output directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "cattus_artifact_dataset"

#: Stable dataset task categories.
DATASET_TASKS: tuple[str, ...] = (
    "routing_or_policy_learning",
    "risk_classification",
    "artifact_summarization",
    "validation_planning",
    "visual_evidence_policy",
    "remote_safety_policy",
    "self_evolution_review",
    "lesson_teaching",
    "unknown",
)

RISK_LEVELS: tuple[str, ...] = ("low", "medium", "high", "unknown")
AUTOMATION_LEVELS: tuple[str, ...] = ("local", "report", "sandbox", "remote", "unknown")

#: (artifact_kind, base directory under the repo, glob pattern relative to the base).
#: The base directory determines the kind; content is not sniffed.
SCAN_SPECS: tuple[tuple[str, str, str], ...] = (
    ("goal_brief", ".agent/goal_briefs", "**/goal_brief.json"),
    ("worker_assignment", ".agent/worker_assignments", "**/worker_assignment.json"),
    ("driver_decision", ".agent/driver_decisions", "**/driver_decision.json"),
    ("visual_evidence_contract", ".agent/visual_evidence", "**/visual_evidence_contract.json"),
    ("worker_result_review", ".agent/worker_result_reviews", "**/worker_result_review.json"),
    ("flaky_case_review", ".agent/reliability/flaky_case_reviews", "**/flaky_case_review.json"),
    ("self_evolution_evidence_pack", ".agent/self_evolution_trials", "**/self_evolution_evidence_pack.json"),
    ("telegram_evidence_contract", ".agent/automation_contracts", "telegram_evidence_contract.json"),
    ("github_pr_safety_contract", ".agent/automation_contracts", "github_pr_safety_contract.json"),
    ("n8n_orchestration_dry_run", ".agent/automation_contracts", "n8n_orchestration_dry_run.json"),
    ("phase_registry_report", ".agent/roadmap", "phase_registry_report.json"),
    ("phase_picker_report", ".agent/roadmap", "phase_picker_report.json"),
    ("teaching_card", ".agent/teaching_cards", "**/teaching_card.json"),
)

ARTIFACT_KINDS: tuple[str, ...] = tuple(kind for kind, _, _ in SCAN_SPECS)

#: kind -> dataset task category.
_DATASET_TASK_BY_KIND: dict[str, str] = {
    "goal_brief": "validation_planning",
    "worker_assignment": "routing_or_policy_learning",
    "driver_decision": "routing_or_policy_learning",
    "visual_evidence_contract": "visual_evidence_policy",
    "worker_result_review": "risk_classification",
    "flaky_case_review": "risk_classification",
    "self_evolution_evidence_pack": "self_evolution_review",
    "telegram_evidence_contract": "remote_safety_policy",
    "github_pr_safety_contract": "remote_safety_policy",
    "n8n_orchestration_dry_run": "remote_safety_policy",
    "phase_registry_report": "artifact_summarization",
    "phase_picker_report": "routing_or_policy_learning",
    "teaching_card": "lesson_teaching",
}

#: kind -> automation tier the artifact belongs to.
_AUTOMATION_BY_KIND: dict[str, str] = {
    "goal_brief": "local",
    "worker_assignment": "local",
    "driver_decision": "local",
    "visual_evidence_contract": "local",
    "worker_result_review": "local",
    "teaching_card": "local",
    "flaky_case_review": "report",
    "phase_registry_report": "report",
    "phase_picker_report": "report",
    "self_evolution_evidence_pack": "sandbox",
    "telegram_evidence_contract": "remote",
    "github_pr_safety_contract": "remote",
    "n8n_orchestration_dry_run": "remote",
}

#: kind -> base risk level before any verdict-based escalation.
_RISK_BY_KIND: dict[str, str] = {
    "goal_brief": "low",
    "worker_assignment": "low",
    "driver_decision": "low",
    "visual_evidence_contract": "low",
    "worker_result_review": "medium",
    "flaky_case_review": "low",
    "self_evolution_evidence_pack": "medium",
    "telegram_evidence_contract": "medium",
    "github_pr_safety_contract": "medium",
    "n8n_orchestration_dry_run": "medium",
    "phase_registry_report": "low",
    "phase_picker_report": "low",
    "teaching_card": "low",
}

#: kind -> fallback target label when no verdict / vehicle / next step is present.
_TARGET_DEFAULT_BY_KIND: dict[str, str] = {
    "goal_brief": "summarize_goal_brief",
    "worker_assignment": "prepare_worker_assignment",
    "driver_decision": "recommend_vehicle",
    "visual_evidence_contract": "assess_visual_evidence",
    "worker_result_review": "review_worker_result",
    "flaky_case_review": "review_flaky_cases",
    "self_evolution_evidence_pack": "review_self_evolution",
    "telegram_evidence_contract": "review_remote_safety",
    "github_pr_safety_contract": "review_remote_safety",
    "n8n_orchestration_dry_run": "review_remote_safety",
    "phase_registry_report": "summarize_phase_registry",
    "phase_picker_report": "pick_next_phase",
    "teaching_card": "teach_lesson",
}

#: Report artifact filenames.
JSONL_NAME = "artifact_dataset.jsonl"
REPORT_JSON_NAME = "artifact_dataset_report.json"
REPORT_MD_NAME = "artifact_dataset_report.md"

ARTIFACT_DATASET_GUARDRAIL_NOTE = (
    "C.A.T.T.U.S Artifact Dataset Builder is report-only: it scans existing "
    "C.A.T.T.U.S artifacts and normalizes them into stable dataset rows for future "
    "model and classifier experiments. It builds data only — it does not train or "
    "call models, does not call embeddings, does not write to a database, does not "
    "apply patches, does not run validation or a benchmark check, does not launch "
    "workers, and does not contact Telegram, GitHub, n8n, or any network service. "
    "Dataset rows are advisory artifacts only and grant no execution authority."
)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def _first_text(*values: Any) -> str:
    for value in values:
        text = _text(value)
        if text:
            return text
    return ""


def _str_list(value: Any) -> list[str]:
    return [str(item) for item in value] if isinstance(value, list) else []


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _nested(artifact: dict[str, Any], *path: str) -> Any:
    node: Any = artifact
    for key in path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _norm_path(artifact_path: Any) -> str:
    return str(artifact_path).replace("\\", "/").strip()


def _norm_mode(value: Any) -> str:
    return _text(value).lower().replace(" ", "_").replace("-", "_")


def _shorten(value: Any, limit: int = 280) -> str:
    text = " ".join(str(value).split())
    return text[:limit]


# ── Per-kind field extraction ───────────────────────────────────────────────────

def _source_id(artifact: dict[str, Any]) -> str:
    return _first_text(
        artifact.get("assignment_id"),
        artifact.get("driver_decision_id"),
        artifact.get("review_id"),
        artifact.get("visual_evidence_id"),
        artifact.get("teaching_card_id"),
        artifact.get("pack_id"),
        artifact.get("contract_id"),
        artifact.get("dry_run_id"),
        artifact.get("report_id"),
        artifact.get("trial_id"),
    )


def _created_at(artifact: dict[str, Any]) -> str:
    return _first_text(
        artifact.get("created_at"),
        artifact.get("updated_at"),
        _nested(artifact, "summary", "created_at"),
    )


def _task_title(artifact: dict[str, Any]) -> str:
    return _shorten(
        _first_text(
            artifact.get("title"),
            artifact.get("goal"),
            artifact.get("trial_id"),
            artifact.get("pack_id"),
        ),
        limit=160,
    )


def _task_summary(artifact: dict[str, Any]) -> str:
    summary = artifact.get("summary")
    summary_text = summary if isinstance(summary, str) else ""
    return _shorten(
        _first_text(
            artifact.get("task_summary"),
            summary_text,
            artifact.get("goal"),
            artifact.get("title"),
            artifact.get("recommended_next_step"),
            artifact.get("trial_id"),
        )
    )


def _mode(artifact: dict[str, Any]) -> str:
    return _norm_mode(
        _first_text(
            artifact.get("mode"),
            artifact.get("problem_type"),
            artifact.get("source_type"),
        )
    )


def _final_verdict(kind: str, artifact: dict[str, Any]) -> str:
    if kind == "goal_brief":
        return _text(artifact.get("status"))
    if kind == "driver_decision":
        if artifact.get("blocked") is True:
            return "blocked"
        if artifact.get("approval_required") is True:
            return "needs_approval"
        return "recommended" if _text(artifact.get("recommended_vehicle")) else ""
    if kind == "worker_result_review":
        return _text(artifact.get("review_status"))
    if kind == "n8n_orchestration_dry_run":
        return _text(artifact.get("overall_verdict"))
    if kind == "phase_registry_report":
        return "valid" if artifact.get("is_valid") is True else "invalid"
    if kind == "phase_picker_report":
        return "valid" if artifact.get("registry_valid") is True else "invalid"
    if kind in ("self_evolution_evidence_pack", "telegram_evidence_contract", "github_pr_safety_contract"):
        return _text(artifact.get("final_verdict"))
    return _text(artifact.get("final_verdict"))


def _recommended_next_step(kind: str, artifact: dict[str, Any]) -> str:
    direct = _text(artifact.get("recommended_next_step"))
    if direct:
        return direct
    if kind == "worker_result_review":
        actions = _str_list(artifact.get("recommended_next_actions"))
        return actions[0] if actions else ""
    if kind == "phase_picker_report":
        return _text(_nested(artifact, "top_recommendation", "recommended_next_step"))
    return ""


def _human_gate(artifact: dict[str, Any]) -> bool:
    return bool(
        artifact.get("human_approval_required") is True
        or artifact.get("human_review_required") is True
        or artifact.get("human_review_recommended") is True
        or _nested(artifact, "guardrails", "human_review_required") is True
        or _nested(artifact, "summary", "human_review_required") is True
    )


def _features(kind: str, artifact: dict[str, Any], *, recommended_next_step: str, human_gate: bool) -> dict[str, bool]:
    risk_flags = _str_list(artifact.get("risk_flags")) + _str_list(artifact.get("claimed_risks"))
    risk_flags_low = [flag.lower() for flag in risk_flags]

    has_validation = bool(
        artifact.get("validation_run") is True
        or _str_list(artifact.get("validation_commands"))
        or _str_list(artifact.get("claimed_validation_commands"))
        or artifact.get("claimed_validation_passed") is True
        or _text(_nested(artifact, "validation", "command"))
        or _text(_nested(artifact, "risk_summary", "validation"))
    )
    has_visual_issue = bool(
        kind == "visual_evidence_contract"
        or artifact.get("visual_verification_required") is True
        or artifact.get("visual_evidence_referenced") is True
        or any("visual" in flag for flag in risk_flags_low)
    )
    has_security_sensitive_claim = any("security" in flag for flag in risk_flags_low)
    has_remote_component = kind in (
        "telegram_evidence_contract",
        "github_pr_safety_contract",
        "n8n_orchestration_dry_run",
    )
    has_patch_candidate = bool(
        kind == "self_evolution_evidence_pack"
        or "patch" in recommended_next_step.lower()
    )
    return {
        "has_validation": has_validation,
        "has_visual_issue": has_visual_issue,
        "has_security_sensitive_claim": has_security_sensitive_claim,
        "has_remote_component": has_remote_component,
        "has_patch_candidate": has_patch_candidate,
        "has_human_gate": human_gate,
    }


def _risk_level(kind: str, artifact: dict[str, Any], *, final_verdict: str) -> str:
    explicit = _text(artifact.get("risk_level")).lower()
    if explicit in ("low", "medium", "high"):
        return explicit
    if final_verdict == "blocked":
        return "high"
    return _RISK_BY_KIND.get(kind, "unknown")


def _action_lists(artifact: dict[str, Any]) -> tuple[list[str], list[str]]:
    allowed = _dedupe(
        _str_list(artifact.get("allowed_actions")) + _str_list(artifact.get("approval_options"))
    )
    blocked = _dedupe(
        _str_list(artifact.get("blocked_actions")) + _str_list(artifact.get("forbidden_actions"))
    )
    return allowed, blocked


def _target_label(*, recommended_vehicle: str, final_verdict: str, recommended_next_step: str, kind: str) -> str:
    if recommended_next_step:
        return recommended_next_step
    if recommended_vehicle:
        return recommended_vehicle
    if final_verdict:
        return final_verdict
    return _TARGET_DEFAULT_BY_KIND.get(kind, "unknown")


def compute_row_id(kind: str, artifact_path: str, source_id: str, labels: dict[str, Any]) -> str:
    """Deterministic, machine-independent row id from stable identity fields."""
    payload = "|".join(
        [
            kind,
            _norm_path(artifact_path),
            source_id,
            _text(labels.get("final_verdict")),
            _text(labels.get("recommended_next_step")),
            _text(labels.get("recommended_vehicle")),
        ]
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{kind}-{digest}"


def normalize_artifact(kind: str, artifact: Any, *, artifact_path: str = "") -> dict[str, Any]:
    """Project one parsed artifact dict onto a stable dataset row.

    Best-effort and pure: missing fields are recorded under ``quality`` rather than
    raising, and the source ``artifact`` is never mutated.
    """
    if not isinstance(artifact, dict):
        artifact = {}

    rel_path = _norm_path(artifact_path)
    source_id = _source_id(artifact)
    created_at = _created_at(artifact)
    task_title = _task_title(artifact)
    task_summary = _task_summary(artifact)
    mode = _mode(artifact)

    recommended_vehicle = _text(artifact.get("recommended_vehicle"))
    final_verdict = _final_verdict(kind, artifact)
    recommended_next_step = _recommended_next_step(kind, artifact)
    labels = {
        "recommended_vehicle": recommended_vehicle,
        "final_verdict": final_verdict,
        "recommended_next_step": recommended_next_step,
    }

    human_gate = _human_gate(artifact)
    features = _features(
        kind, artifact, recommended_next_step=recommended_next_step, human_gate=human_gate
    )
    allowed_actions, blocked_actions = _action_lists(artifact)
    risk_level = _risk_level(kind, artifact, final_verdict=final_verdict)
    automation_level = _AUTOMATION_BY_KIND.get(kind, "unknown")
    dataset_task = _DATASET_TASK_BY_KIND.get(kind, "unknown")
    target_label = _target_label(
        recommended_vehicle=recommended_vehicle,
        final_verdict=final_verdict,
        recommended_next_step=recommended_next_step,
        kind=kind,
    )

    missing_fields = [
        name
        for name, value in (
            ("source_id", source_id),
            ("created_at", created_at),
            ("task_title", task_title),
        )
        if not value
    ]
    has_signal = bool(
        source_id or created_at or task_title or final_verdict or recommended_vehicle or recommended_next_step
    )
    parse_status = "ok" if has_signal else "partial"
    row_warnings: list[str] = []
    if missing_fields:
        row_warnings.append("missing fields: " + ", ".join(missing_fields))

    return {
        "row_id": compute_row_id(kind, rel_path, source_id, labels),
        "artifact_kind": kind,
        "artifact_path": rel_path,
        "created_at": created_at,
        "source_id": source_id,
        "task_title": task_title,
        "task_summary": task_summary,
        "mode": mode,
        "risk_level": risk_level,
        "automation_level": automation_level,
        "human_approval_required": human_gate,
        "allowed_actions": allowed_actions,
        "blocked_actions": blocked_actions,
        "labels": labels,
        "features": features,
        "target": {
            "dataset_task": dataset_task,
            "target_label": target_label,
            "authority": "advisory_only",
        },
        "quality": {
            "parse_status": parse_status,
            "missing_fields": missing_fields,
            "warnings": row_warnings,
        },
    }


# ── Scanning ─────────────────────────────────────────────────────────────────

def _load_json_object(path: Path) -> tuple[dict[str, Any] | None, str]:
    """Return ``(parsed_dict, error)``; error is non-empty when the file is unusable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not parse JSON: {exc}"
    if not isinstance(data, dict):
        return None, "artifact is not a JSON object"
    return data, ""


def scan_artifacts(repo_path: str | Path, *, include_kinds: Any = None) -> dict[str, Any]:
    """Scan known artifact locations under ``repo_path`` and normalize each artifact.

    Returns ``{rows, scanned_paths, skipped_files, warnings}``. Missing directories
    produce warnings (not failures); malformed files are skipped with a warning.
    Never mutates any source artifact.
    """
    repo = Path(repo_path)
    include = {str(k) for k in include_kinds} if include_kinds else None

    rows: list[dict[str, Any]] = []
    scanned_paths: list[str] = []
    skipped_files: list[dict[str, str]] = []
    warnings: list[str] = []

    if not (repo / ".agent").exists():
        warnings.append(f"no .agent directory present under {_norm_path(repo)}")
        return {"rows": rows, "scanned_paths": scanned_paths, "skipped_files": skipped_files, "warnings": warnings}

    warned_dirs: set[str] = set()
    for kind, base_rel, pattern in SCAN_SPECS:
        if include is not None and kind not in include:
            continue
        base = repo / base_rel
        if not base.exists():
            if base_rel not in warned_dirs:
                warnings.append(f"artifact directory not present: {base_rel}")
                warned_dirs.add(base_rel)
            continue
        scanned_paths.append(base_rel)
        for path in sorted(base.glob(pattern)):
            if not path.is_file():
                continue
            rel = _rel_to_repo(path, repo)
            artifact, error = _load_json_object(path)
            if error or artifact is None:
                skipped_files.append({"path": rel, "error": error or "unreadable artifact"})
                warnings.append(f"skipped {rel}: {error or 'unreadable artifact'}")
                continue
            rows.append(normalize_artifact(kind, artifact, artifact_path=rel))

    return {
        "rows": rows,
        "scanned_paths": _dedupe(scanned_paths),
        "skipped_files": skipped_files,
        "warnings": warnings,
    }


def _rel_to_repo(path: Path, repo: Path) -> str:
    try:
        return _norm_path(path.relative_to(repo))
    except ValueError:
        return _norm_path(path.name)


def _row_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("artifact_kind", "")),
        str(row.get("artifact_path", "")),
        str(row.get("source_id", "")),
        str(row.get("row_id", "")),
    )


def finalize_rows(rows: list[dict[str, Any]], *, limit: Any = None) -> list[dict[str, Any]]:
    """Sort rows into a deterministic order and apply an optional row limit."""
    ordered = sorted(rows, key=_row_sort_key)
    if isinstance(limit, int) and limit >= 0:
        ordered = ordered[:limit]
    return ordered


# ── Report assembly ─────────────────────────────────────────────────────────────

def _counts(rows: list[dict[str, Any]], extractor) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        key = str(extractor(row))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _guardrails() -> dict[str, bool]:
    """This tool performs none of these actions."""
    return {
        "model_training_performed": False,
        "model_call_performed": False,
        "embedding_call_performed": False,
        "database_write_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run": False,
        "network_call_performed": False,
        "worker_launch_performed": False,
        "lesson_promotion_performed": False,
        "merge_performed": False,
    }


def build_artifact_dataset_report(
    *,
    repo_path: str | Path,
    rows: list[dict[str, Any]],
    scanned_paths: list[str],
    skipped_files: list[dict[str, str]],
    warnings: list[str],
    report_id: str = "",
    created_at: str = "",
    output_dir: str = "",
    jsonl_path: str = "",
    sample_size: int = 5,
) -> dict[str, Any]:
    """Assemble the deterministic dataset report record from already-final rows."""
    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": ARTIFACT_DATASET_GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm_path(repo_path),
        "output_dir": _norm_path(output_dir) if output_dir else "",
        "jsonl_path": _norm_path(jsonl_path) if jsonl_path else "",
        "row_count": len(rows),
        "counts_by_artifact_kind": _counts(rows, lambda r: r.get("artifact_kind")),
        "counts_by_dataset_task": _counts(rows, lambda r: _nested(r, "target", "dataset_task")),
        "counts_by_risk_level": _counts(rows, lambda r: r.get("risk_level")),
        "counts_by_target_label": _counts(rows, lambda r: _nested(r, "target", "target_label")),
        "scanned_paths": list(scanned_paths),
        "skipped_files": list(skipped_files),
        "warnings": list(warnings),
        "guardrails": _guardrails(),
        "sample_rows": [dict(row) for row in rows[:sample_size]],
    }


# ── Markdown rendering ──────────────────────────────────────────────────────────

def _counts_table(lines: list[str], title: str, counts: dict[str, int]) -> None:
    lines += [f"## {title}", ""]
    if counts:
        lines += ["| Key | Count |", "| --- | --- |"]
        for key in sorted(counts):
            lines.append(f"| `{_md(key)}` | {counts[key]} |")
    else:
        lines.append("_None._")
    lines.append("")


def render_artifact_dataset_markdown(report: dict[str, Any]) -> str:
    """Render the dataset report as one operator-readable Markdown document."""
    lines: list[str] = [
        "# C.A.T.T.U.S Artifact Dataset Report",
        "",
        f"> {report.get('guardrail_note', ARTIFACT_DATASET_GUARDRAIL_NOTE)}",
        "",
        "_Report only: MODEL.1 scans existing C.A.T.T.U.S artifacts and normalizes them "
        "into stable dataset rows. It builds data only and grants no execution authority._",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Row count:** {report.get('row_count', 0)}",
        f"- **Scanned paths:** {', '.join(f'`{_md(p)}`' for p in report.get('scanned_paths') or []) or '(none)'}",
        "",
        "## Dataset Files",
        "",
        f"- **JSONL:** `{_md(report.get('jsonl_path') or '(none)')}`",
        f"- **Output directory:** `{_md(report.get('output_dir') or '(none)')}`",
        "",
    ]

    _counts_table(lines, "Counts by Artifact Kind", report.get("counts_by_artifact_kind") or {})
    _counts_table(lines, "Counts by Dataset Task", report.get("counts_by_dataset_task") or {})
    _counts_table(lines, "Counts by Risk Level", report.get("counts_by_risk_level") or {})
    _counts_table(lines, "Counts by Target Label", report.get("counts_by_target_label") or {})

    # Skipped files
    lines += ["## Skipped Files", ""]
    skipped = report.get("skipped_files") or []
    if skipped:
        lines += ["| Path | Reason |", "| --- | --- |"]
        for entry in skipped:
            lines.append(f"| `{_md(entry.get('path'))}` | {_md(entry.get('error'))} |")
    else:
        lines.append("_None — every discovered artifact parsed cleanly._")
    lines.append("")

    # Warnings
    lines += ["## Warnings", ""]
    report_warnings = report.get("warnings") or []
    if report_warnings:
        for warning in report_warnings:
            lines.append(f"- {_md(warning)}")
    else:
        lines.append("_None._")
    lines.append("")

    # Sample rows
    lines += ["## Sample Rows", ""]
    sample_rows = report.get("sample_rows") or []
    if sample_rows:
        lines += ["| Row id | Kind | Dataset task | Risk | Target label |", "| --- | --- | --- | --- | --- |"]
        for row in sample_rows:
            target = row.get("target") or {}
            lines.append(
                f"| `{_md(row.get('row_id'))}` | {_md(row.get('artifact_kind'))} | "
                f"{_md(target.get('dataset_task'))} | {_md(row.get('risk_level'))} | "
                f"{_md(target.get('target_label'))} |"
            )
    else:
        lines.append("_None — the dataset is empty._")
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- MODEL.1 does not train models.",
        "- MODEL.1 does not call models.",
        "- MODEL.1 does not call embeddings.",
        "- MODEL.1 does not write to databases.",
        "- MODEL.1 does not apply patches.",
        "- MODEL.1 does not run validation or benchmarks.",
        "- MODEL.1 does not launch workers.",
        "- MODEL.1 does not contact Telegram, GitHub, n8n, or network services.",
        "- Dataset rows are advisory artifacts only and grant no execution authority.",
        "",
    ]
    return "\n".join(lines) + "\n"


# ── Writing ──────────────────────────────────────────────────────────────────

def _render_jsonl(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    lines = [json.dumps(row, ensure_ascii=False, sort_keys=True) for row in rows]
    return "\n".join(lines) + "\n"


def write_artifact_dataset(
    repo_path: str | Path,
    output_dir: str | Path,
    *,
    report_id: str = "",
    created_at: str = "",
    include_kinds: Any = None,
    limit: Any = None,
) -> dict[str, Any]:
    """Scan, normalize, and write the JSONL dataset + JSON + Markdown report.

    Returns ``{ok, jsonl_path, json_path, md_path, report, rows}``. Source artifacts
    are read only; nothing outside ``output_dir`` is written.
    """
    scan = scan_artifacts(repo_path, include_kinds=include_kinds)
    rows = finalize_rows(scan["rows"], limit=limit)

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = out_dir / JSONL_NAME
    json_path = out_dir / REPORT_JSON_NAME
    md_path = out_dir / REPORT_MD_NAME

    report = build_artifact_dataset_report(
        repo_path=repo_path,
        rows=rows,
        scanned_paths=scan["scanned_paths"],
        skipped_files=scan["skipped_files"],
        warnings=scan["warnings"],
        report_id=report_id,
        created_at=created_at,
        output_dir=str(out_dir),
        jsonl_path=str(jsonl_path),
    )

    jsonl_path.write_text(_render_jsonl(rows), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    md_path.write_text(render_artifact_dataset_markdown(report), encoding="utf-8")

    return {
        "ok": True,
        "jsonl_path": str(jsonl_path),
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
        "rows": rows,
    }
