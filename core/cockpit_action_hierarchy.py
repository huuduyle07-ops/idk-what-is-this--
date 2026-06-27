"""UX.7 — Cockpit Action Hierarchy Report.

Report-only analysis of the operator cockpit navigation and action hierarchy.
Reads the HTML template and CSS to extract what surfaces are in which group
and produces a structured report.

UX.7 is a report-only layout-analysis phase.  It does not add new backend
routes, mutation routes, or execution powers.  It does not start runs, call
models, apply patches, run validation or benchmarks, contact network services,
launch workers, mutate the repo, push, merge, or open PRs.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPORT_KIND = "cockpit_action_hierarchy_report"
PREVIEW_STATUS_READY = "ready_for_review"

GUARDRAIL_NOTE = (
    "UX.7 is a report-only cockpit layout analysis phase. "
    "No new routes, execution, or mutation were added."
)

_BOUNDARIES = [
    "UX.7 reorganises existing UI surfaces only.",
    "UX.7 does not add new backend routes.",
    "UX.7 does not add new mutation routes.",
    "UX.7 does not execute tasks.",
    "UX.7 does not start runs.",
    "UX.7 does not call models.",
    "UX.7 does not apply patches.",
    "UX.7 does not run validation or benchmarks.",
    "UX.7 does not contact network services.",
    "UX.7 does not launch workers.",
    "UX.7 does not mutate the repo outside normal source-code edits for this phase.",
    "UX.7 does not push, merge, or open PRs.",
]

_GUARDRAILS: dict[str, Any] = {
    "preview_only": True,
    "layout_analysis_only": True,
    "new_backend_route_added": False,
    "new_mutation_route_added": False,
    "execution_behavior_changed": False,
    "new_model_call_added": False,
    "patch_applied": False,
    "validation_run": False,
    "benchmark_run_performed": False,
    "network_call_performed": False,
    "database_write_performed": False,
    "worker_launch_performed": False,
    "repo_mutation_performed": False,
    "merge_performed": False,
}

# Surface IDs expected in the restructured cockpit
_PRIMARY_WORKFLOW = ["chat", "memory", "settings"]
_WORKFLOW_SURFACES = [
    "run-timeline",
    "mixed-mode-router",
    "goal-brief",
    "evidence-cards",
    "continue-from-frame",
]
_ADVANCED_DEBUG_SURFACES = ["benchmarks", "dream", "graph"]
_MERGED_SURFACES = [("goal-brief", "goal-brief-4w1h")]


def _extract_ws_tabs(html: str, group_class: str) -> list[str]:
    """Return list of data-ws values found inside a named ws-nav group."""
    pattern = (
        rf'class="[^"]*{re.escape(group_class)}[^"]*"[^>]*>(.*?)</div>'
    )
    m = re.search(pattern, html, re.DOTALL)
    if not m:
        return []
    section = m.group(1)
    return re.findall(r'data-ws="([^"]+)"', section)


def _has_advanced_drawer(html: str) -> bool:
    return "ws-nav-advanced-drawer" in html or 'data-ui-group="advanced-debug"' in html


def _has_cockpit_css(css: str) -> bool:
    return (
        "ws-nav-advanced-drawer" in css
        or "ws-nav--workflow" in css
        or "ws-nav--advanced" in css
    )


def _count_primary_tabs(html: str) -> int:
    primary_start = html.find("ws-nav--primary")
    if primary_start == -1:
        return 0
    primary_end = html.find("/ws-nav-primary", primary_start)
    section = (
        html[primary_start:primary_end]
        if primary_end != -1
        else html[primary_start: primary_start + 1000]
    )
    return len(re.findall(r'data-ws="', section))


def build_cockpit_action_hierarchy_report(
    *,
    html_path: str | None = None,
    css_path: str | None = None,
    repo_path: str = ".",
    report_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Analyse the cockpit HTML/CSS and return a structured report dict."""
    created_iso = created_at or datetime.now(tz=timezone.utc).isoformat()
    rid = report_id or str(uuid.uuid4())

    html: str = ""
    if html_path and Path(html_path).exists():
        html = Path(html_path).read_text(encoding="utf-8")

    css: str = ""
    if css_path and Path(css_path).exists():
        css = Path(css_path).read_text(encoding="utf-8")

    primary_tabs = _extract_ws_tabs(html, "ws-nav--primary")
    workflow_tabs = _extract_ws_tabs(html, "ws-nav--workflow")
    advanced_tabs = _extract_ws_tabs(html, "ws-nav--advanced")

    has_drawer = _has_advanced_drawer(html)
    cockpit_css_present = _has_cockpit_css(css)
    primary_count = _count_primary_tabs(html)

    remaining_risks: list[str] = []
    if not has_drawer:
        remaining_risks.append("Advanced / Debug drawer not found in HTML")
    if primary_count > 3:
        remaining_risks.append(f"Primary nav has {primary_count} items (expected ≤3)")
    if not cockpit_css_present:
        remaining_risks.append("Cockpit workflow CSS not found in style.css")

    return {
        "report_kind": REPORT_KIND,
        "report_id": rid,
        "created_at": created_iso,
        "repo_path": repo_path,
        "preview_status": PREVIEW_STATUS_READY,
        "primary_workflow": primary_tabs or _PRIMARY_WORKFLOW,
        "workflow_surfaces": workflow_tabs or _WORKFLOW_SURFACES,
        "advanced_debug_surfaces": advanced_tabs or _ADVANCED_DEBUG_SURFACES,
        "merged_surfaces": [list(pair) for pair in _MERGED_SURFACES],
        "hidden_or_collapsed_surfaces": _ADVANCED_DEBUG_SURFACES,
        "has_advanced_drawer": has_drawer,
        "cockpit_css_present": cockpit_css_present,
        "primary_nav_count": primary_count,
        "remaining_navigation_risks": remaining_risks,
        "guardrail_note": GUARDRAIL_NOTE,
        "guardrails": dict(_GUARDRAILS),
        "boundaries": list(_BOUNDARIES),
    }


def write_cockpit_action_hierarchy_artifacts(
    report: dict[str, Any],
    output_root: str = ".agent/ux/cockpit_action_hierarchy",
) -> dict[str, str]:
    """Write JSON and Markdown artifacts; return {ok, json_path, md_path}."""
    import json as _json

    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)

    json_path = out / "cockpit_action_hierarchy_report.json"
    md_path   = out / "cockpit_action_hierarchy_report.md"

    json_path.write_text(_json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path)}


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# UX.7 — Cockpit Action Hierarchy Report",
        "",
        f"**Report ID:** {report.get('report_id')}",
        f"**Created:** {report.get('created_at')}",
        f"**Repo:** {report.get('repo_path')}",
        f"**Status:** {report.get('preview_status')}",
        "",
        "## Primary Workflow",
        "",
    ]
    for s in report.get("primary_workflow", []):
        lines.append(f"- `{s}`")
    lines += ["", "## Workflow Surfaces", ""]
    for s in report.get("workflow_surfaces", []):
        lines.append(f"- `{s}`")
    lines += ["", "## Advanced / Debug Surfaces (collapsed)", ""]
    for s in report.get("advanced_debug_surfaces", []):
        lines.append(f"- `{s}`")
    lines += ["", "## Merged Surfaces", ""]
    for pair in report.get("merged_surfaces", []):
        lines.append(f"- {pair[0]} ← {pair[1]}")
    lines += ["", "## Navigation Risks", ""]
    risks = report.get("remaining_navigation_risks", [])
    if risks:
        for r in risks:
            lines.append(f"- ⚠ {r}")
    else:
        lines.append("- None")
    lines += [
        "",
        "## Guardrail Note",
        "",
        report.get("guardrail_note", ""),
        "",
        "## Boundaries",
        "",
    ]
    for b in report.get("boundaries", []):
        lines.append(f"- {b}")
    return "\n".join(lines) + "\n"
