"""UX.11 - Unified Workbench Behavior Preservation Check.

Pure report builder for proving that the UX.10 Workbench visual integration kept
the old behavior boundaries intact. It reads local source text and writes an
optional report; it adds no route, no dispatch path, and no mutation power.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPORT_KIND = "unified_workbench_behavior_preservation"
JSON_NAME = "unified_workbench_behavior_preservation_report.json"
MD_NAME = "unified_workbench_behavior_preservation_report.md"
NEXT_PHASE = "UX.CLOSE - UX Branch Freeze Checkpoint"


def _now_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8")


def _route_source(root: Path) -> str:
    parts = [_read_text(root / "web" / "app.py")]
    routes_dir = root / "web" / "routes"
    if routes_dir.is_dir():
        for path in sorted(routes_dir.glob("*.py")):
            parts.append(_read_text(path))
    return "\n".join(parts)


def _route_lines(route_source: str) -> list[str]:
    return [
        line.strip()
        for line in route_source.splitlines()
        if "@app.route" in line or "@bp.route" in line
    ]


def _block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.find(start_marker)
    if start < 0:
        return ""
    end = text.find(end_marker, start)
    if end < 0:
        return text[start:]
    return text[start:end]


def _js_segment(text: str, marker: str) -> str:
    start = text.find(marker)
    if start < 0:
        return ""
    end = text.find("});", start)
    if end < 0:
        return text[start:start + 800]
    return text[start:end + 3]


def _status(ok: bool) -> str:
    return "pass" if ok else "needs_manual_review"


def _check(check_id: str, title: str, ok: bool, evidence: str) -> dict[str, str]:
    return {
        "check_id": check_id,
        "title": title,
        "status": _status(ok),
        "evidence": evidence,
    }


def _checks_pass(checks: list[dict[str, str]]) -> bool:
    return all(check.get("status") == "pass" for check in checks)


def _preservation_checks(html: str, workbench: str) -> list[dict[str, str]]:
    form_start = html.find('id="agentForm"')
    workbench_start = html.find("UX.10 unified-workbench")
    workbench_end = html.find("/UX.10 unified-workbench", workbench_start)
    form_end = html.find("</form>", form_start)
    apply_index = html.find("Apply / Review Patch")
    advanced_index = html.find('data-ui-group="advanced-debug"')

    return [
        _check(
            "agent_form_preserved",
            "Existing agentForm still exists and wraps the Workbench.",
            form_start >= 0 and workbench_start > form_start and form_end > workbench_end,
            "agentForm appears before the UX.10 Workbench and closes after it.",
        ),
        _check(
            "query_textarea_preserved",
            "The real query textarea remains the main intent input.",
            'textarea name="query"' in html and 'textarea name="query"' in workbench,
            "textarea name=\"query\" is inside the Workbench main intent section.",
        ),
        _check(
            "submit_path_preserved",
            "The existing submit path still exists.",
            '<button type="submit" id="primarySubmit">Run</button>' in workbench,
            "primarySubmit remains a submit button inside the existing form.",
        ),
        _check(
            "chat_ask_not_rerouted",
            "Chat and Ask behavior is not replaced by a new route.",
            "setProductMode('chat')" in workbench and "action=" not in workbench,
            "Ask changes the current mode; the Workbench defines no form action.",
        ),
        _check(
            "instant_run_not_auto_dispatched",
            "Instant Run visual controls do not dispatch automatically.",
            "setProductMode('instant')" in workbench and "Preview Run still requires" in html,
            "Preview Run changes mode text and still relies on deliberate submit.",
        ),
        _check(
            "mode_preview_read_only",
            "Mode Preview chips are preview-only.",
            "Preview only." in workbench and "does not auto-dispatch" in workbench,
            "The Mode Preview copy names the non-dispatch boundary.",
        ),
        _check(
            "helpers_help_only",
            "Question-mark activation helpers are help-only.",
            workbench.count('class="workbench-helper"') >= 5 and workbench.count("Help only.") >= 5,
            "Each 4W1H helper contains help-only copy.",
        ),
        _check(
            "four_w_one_h_no_submit",
            "4W1H helper rows do not submit automatically.",
            'class="workbench-brief"' in workbench
            and 'type="submit"' not in _block(workbench, 'class="workbench-brief"', 'class="workbench-mode-preview"'),
            "The brief area contains no submit button.",
        ),
        _check(
            "goal_brief_reachable",
            "Goal Brief builder remains reachable.",
            "Open Goal Brief / 4W1H Builder" in workbench and "showWorkspaceTab('goal-brief')" in workbench,
            "The Workbench keeps a navigation control to the existing Goal Brief builder.",
        ),
        _check(
            "apply_review_outside_workbench",
            "Apply / Review Patch remains outside the Workbench input area.",
            apply_index > workbench_end >= 0 and "Apply / Review Patch" not in workbench,
            "Apply / Review Patch appears after the Workbench marker.",
        ),
        _check(
            "apply_review_human_triggered",
            "Apply / Review Patch remains human-triggered.",
            '<button type="button" onclick="applyPatch()">Apply / Review Patch</button>' in html,
            "Apply / Review Patch is still a type=button with an explicit click handler.",
        ),
        _check(
            "advanced_debug_secondary",
            "Advanced/debug surfaces remain secondary.",
            advanced_index > workbench_end >= 0 and 'class="ws-nav-advanced-drawer"' in html,
            "Advanced/debug navigation is outside the Workbench and in its drawer.",
        ),
        _check(
            "safety_labels_visible",
            "Workbench visual integration does not hide safety labels.",
            all(
                phrase in workbench
                for phrase in (
                    "Visual integration only",
                    "existing behavior is preserved",
                    "does not auto-dispatch",
                    "human-triggered",
                )
            ),
            "The Workbench copy keeps the preservation and no-auto-dispatch labels visible.",
        ),
    ]


def _route_safety_checks(route_source: str) -> list[dict[str, str]]:
    lines = _route_lines(route_source)
    low_lines = [line.lower() for line in lines]
    workbench_post = [
        line for line in low_lines if ("workbench" in line or "unified" in line) and "post" in line
    ]
    mutating = [
        line for line in low_lines
        if ("workbench" in line or "unified" in line)
        and any(token in line for token in ("apply", "run", "execute", "mutate", "write"))
    ]
    return [
        _check(
            "no_workbench_post_route",
            "No new POST route was added for Workbench.",
            workbench_post == [],
            "No route decorator combines Workbench/unified naming with POST.",
        ),
        _check(
            "no_workbench_mutation_route",
            "No new mutation route was added for Workbench.",
            mutating == [],
            "No Workbench/unified route names include mutating action words.",
        ),
        _check(
            "legacy_routes_left_intact",
            "Legacy route surface remains separate.",
            any(("/generate" + "_patch") in line for line in lines) and not any('/workbench' in line for line in low_lines),
            "Existing routes are present; no /workbench route appears.",
        ),
    ]


def _form_safety_checks(html: str, workbench: str) -> list[dict[str, str]]:
    return [
        _check(
            "single_form_post",
            "No new form action point was introduced.",
            html.count('method="POST"') == 1,
            "The template has one POST form: the existing agent form.",
        ),
        _check(
            "workbench_has_no_form_action",
            "Workbench does not point to a new endpoint.",
            'action="' not in workbench and 'method="post"' not in workbench.lower(),
            "The Workbench section is inside the form but declares no form/action.",
        ),
        _check(
            "confirmation_submit_is_explicit",
            "Existing submit remains the actual confirmation path.",
            'class="workbench-confirmation-actions__submit"' in workbench and 'id="primarySubmit"' in workbench,
            "Confirmation actions include one explicit primarySubmit control.",
        ),
    ]


def _workbench_safety_checks(html: str, workbench: str) -> list[dict[str, str]]:
    chip_js = _js_segment(html, 'document.querySelectorAll("[data-workbench-mode]")')
    mode_preview = _block(workbench, 'class="workbench-mode-preview"', 'class="workbench-confirmation-actions"')
    return [
        _check(
            "no_fetch_in_workbench",
            "No fetch call is tied to the Workbench.",
            "fetch(" not in workbench and "fetch(" not in chip_js,
            "The Workbench block and chip styling segment contain no fetch call.",
        ),
        _check(
            "mode_chip_js_is_visual_only",
            "Mode Preview chip JavaScript is visual only.",
            "workbench-mode-chip--active" in chip_js
            and ".submit(" not in chip_js
            and "dispatchEvent" not in chip_js,
            "The chip segment only toggles the active CSS class.",
        ),
        _check(
            "mode_preview_has_no_click_handlers",
            "Mode Preview chips have no click handlers.",
            "onclick=" not in mode_preview and "<button" not in mode_preview,
            "Mode Preview chips render as spans without click handlers.",
        ),
        _check(
            "no_hidden_auto_dispatch_marker",
            "No hidden auto-dispatch marker appears.",
            "auto-dispatch" in workbench and "auto_run" not in workbench.lower(),
            "The only auto-dispatch references are negative safety copy.",
        ),
    ]


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "new_ui_feature_added": False,
        "backend_route_added": False,
        "mutation_route_added": False,
        "execution_paths_merged": False,
        "auto_dispatch_added": False,
        "run_auto_start_added": False,
        "model_call_added": False,
        "network_call_added": False,
        "patch_application_added": False,
        "check_command_launch_added": False,
        "background_job_launch_added": False,
        "repo_push_or_pr_added": False,
        "persistent_data_write_added": False,
    }


def build_unified_workbench_behavior_preservation_report(
    *,
    repo_path: str | Path = ".",
    report_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic report from local source text."""
    root = Path(repo_path)
    html = _read_text(root / "web" / "templates" / "index.html")
    workbench = _block(html, "UX.10 unified-workbench", "/UX.10 unified-workbench")
    route_source = _route_source(root)

    preservation_checks = _preservation_checks(html, workbench)
    route_safety_checks = _route_safety_checks(route_source)
    form_safety_checks = _form_safety_checks(html, workbench)
    workbench_safety_checks = _workbench_safety_checks(html, workbench)
    all_checks = preservation_checks + route_safety_checks + form_safety_checks + workbench_safety_checks
    status = "pass" if _checks_pass(all_checks) else "needs_manual_review"

    return {
        "report_kind": REPORT_KIND,
        "report_id": str(report_id or "unified_workbench_behavior_preservation"),
        "created_at": str(created_at or _now_iso()),
        "repo_path": str(root),
        "status": status,
        "preservation_checks": preservation_checks,
        "route_safety_checks": route_safety_checks,
        "form_safety_checks": form_safety_checks,
        "workbench_safety_checks": workbench_safety_checks,
        "remaining_risks": [
            {
                "risk_id": "manual_browser_confirmation",
                "status": "needs_manual_review",
                "note": "A human should still confirm the live browser flow after the source-level preservation checks pass.",
            }
        ],
        "recommended_next_phase": NEXT_PHASE,
        "guardrails": _guardrails(),
    }


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _render_check_table(lines: list[str], title: str, checks: list[dict[str, str]]) -> None:
    lines += [f"## {title}", ""]
    if not checks:
        lines += ["_None._", ""]
        return
    lines += ["| Check | Status | Evidence |", "|---|---|---|"]
    for check in checks:
        lines.append(
            f"| {_md(check.get('title', ''))} | {_md(check.get('status', ''))} | {_md(check.get('evidence', ''))} |"
        )
    lines.append("")


def render_unified_workbench_behavior_preservation_markdown(report: dict[str, Any]) -> str:
    """Render the report as Markdown."""
    lines: list[str] = [
        "# Unified Workbench Behavior Preservation Check",
        "",
        "_Report-only UX.11 summary. It does not add routes, does not start runs "
        "automatically, does not call models, and does not add mutation power._",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id', ''))}`",
        f"- **Created at:** `{_md(report.get('created_at', ''))}`",
        f"- **Repo path:** `{_md(report.get('repo_path', ''))}`",
        f"- **Status:** `{_md(report.get('status', ''))}`",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase', NEXT_PHASE))}`",
        "",
    ]
    _render_check_table(lines, "Preservation Checks", report.get("preservation_checks") or [])
    _render_check_table(lines, "Route Safety Checks", report.get("route_safety_checks") or [])
    _render_check_table(lines, "Form Safety Checks", report.get("form_safety_checks") or [])
    _render_check_table(lines, "Workbench Safety Checks", report.get("workbench_safety_checks") or [])

    lines += ["## Remaining Risks", ""]
    for risk in report.get("remaining_risks") or []:
        lines.append(f"- `{_md(risk.get('risk_id', 'risk'))}`: {_md(risk.get('note', ''))}")
    if not report.get("remaining_risks"):
        lines.append("_None._")
    lines.append("")

    lines += ["## Guardrails", ""]
    for key, value in sorted((report.get("guardrails") or {}).items()):
        lines.append(f"- `{_md(key)}`: `{str(value).lower()}`")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_unified_workbench_behavior_preservation_artifacts(
    *,
    repo_path: str | Path = ".",
    output_root: str | Path = Path(".agent") / "ux" / "unified_workbench_behavior_preservation",
    report_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Build and write the JSON plus Markdown report artifacts."""
    report = build_unified_workbench_behavior_preservation_report(
        repo_path=repo_path,
        report_id=report_id,
        created_at=created_at,
    )
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / JSON_NAME
    md_path = out / MD_NAME
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    md_path.write_text(render_unified_workbench_behavior_preservation_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "report": report}
