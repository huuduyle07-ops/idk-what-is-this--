from __future__ import annotations

import json, shutil, subprocess, sys, tempfile
import markdown as _markdown_lib
from datetime import datetime
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for
from collections import Counter 
# Resolve project root from this file's location (avoids hardcoded user paths).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from core.retriever import retrieve_context
from reasoning.deep_project_understand import deep_project_understand
from core.control_engine import run_control_structured, run_control, build_control_prompt
from agents.gemini_client import run_gemini_request
from agents.model_stats import ModelStatsScope, format_usage_report
from core.json_utils import extract_json_block
from core.validation_command import get_default_validation_command
from web.runner import run_agent_web
from web.dream_report_markdown import render_dream_report_markdown
from agents.deepseek_client import run_deepseek_review
from config import get_agent_dir, FOLDER_BLACKLIST
from core.project_tag import build_project_tag, fingerprint_repo  # re-exported for legacy callers
from core.repo_librarian import inspect_repo_inventory
from core.runtime_environment import (
    build_runtime_environment_state,
    describe_runtime_environment,
)
from core.harness_modes import (
    HarnessModeDecision,
    decide_harness_mode,
    format_harness_deny_message,
)
from core.run_lifecycle import run_patch_plan_with_artifacts
from core.sleeping_consultant import (
    run_overnight,
    start_overnight_async,
    get_run_state,
    request_stop,
)
from core import dream_artifacts
from core import dream_taxonomy
from core import benchmark_web
from core import lesson_store
from core import goal_brief as goal_brief_core
from core import goal_brief_autocomplete as goal_brief_autocomplete_core
from core import mode_router as mode_router_core
from core import review_pack_generator as review_pack_generator_core
from core.patch_safety import evaluate_patch_safety
from core.mcp_audit import list_mcp_invocations
from database.memory_consolidator import consolidate_all
from policy.decision_helper import normalize_patch_style
from web.patch_helpers import patch_plan_files
from web.routes.patch_routes import bp as patch_routes_bp
from web.routes.dream_trials_routes import bp as dream_trials_routes_bp
from web.routes.dream_references_routes import bp as dream_references_routes_bp
from web.routes.harness_controls_routes import bp as harness_controls_routes_bp
from web.routes.replay_routes import bp as replay_routes_bp
from graph.builder import build_graph_from_repo
from graph.exporter import safe_id, escape_mermaid_label
from web.graph_evidence import (
    build_scope_evidence_spread_debug,
    format_evidence_spread_markdown,
    format_memory_temperature_section,
    format_memory_temperature_shadow_section,
)

app = Flask(__name__)
app.register_blueprint(patch_routes_bp)
app.register_blueprint(dream_trials_routes_bp)
app.register_blueprint(dream_references_routes_bp)
app.register_blueprint(harness_controls_routes_bp)
app.register_blueprint(replay_routes_bp)

WEB_DIR = Path(__file__).parent
from web.session_store import load_sessions, save_sessions, find_session
from scripts.run_patch_proposal_queue import PROPOSAL_ROOT as _DREAM_PROPOSAL_ROOT
BACKUP_DIR = WEB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def save_session(
    query: str,
    repo_path: str,
    mode: str,
    result: dict,
    project_tag: str,
    patch_style: str = "safe_minimal",
    ignore_repo_dna: bool = False,
    web_mode: str = "instant",
    runtime_environment: str = "auto",
    runtime_environment_custom_name: str = "",
    runtime_environment_notes: str = "",
) -> dict:
    sessions = load_sessions()

    session = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "title": query[:40] or "New Session",
        "query": query,
        "repo_path": repo_path,
        "mode": mode,
        "result": result,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "project_tag": project_tag,
        "patch_style": patch_style,
        "ignore_repo_dna": bool(ignore_repo_dna),
        "web_mode": _normalize_web_mode(web_mode),
        "runtime_environment": runtime_environment,
        "runtime_environment_custom_name": runtime_environment_custom_name,
        "runtime_environment_notes": runtime_environment_notes,
        "harness_mode": result.get("harness_mode", ""),
        "harness_warnings": result.get("harness_warnings", []),
    }

    sessions.insert(0, session)
    save_sessions(sessions[:30])

    return session

def _normalize_web_mode(value: str | None) -> str:
    return "chat" if (value or "").strip().lower() == "chat" else "instant"

def _empty_result(answer: str = "") -> dict:
    return {
        "answer": answer,
        "context": "",
        "graph": "",
        "state": "",
        "patch": "",
        "validation": "",
        "usage": "",
    }


def _attach_model_usage(result: dict, model_calls: list[dict] | None) -> dict:
    if model_calls is not None:
        result["usage"] = format_usage_report(model_calls)
        result["model_calls"] = list(model_calls)
    return result


def _attach_runtime_environment(result: dict, runtime_state: dict[str, str]) -> dict:
    result.update(runtime_state)
    result["runtime_environment_description"] = describe_runtime_environment(
        runtime_state["runtime_environment"],
        runtime_state["runtime_environment_custom_name"],
        runtime_state["runtime_environment_notes"],
    )
    return result

def _control_target_path(control: dict | None) -> str:
    if not isinstance(control, dict):
        return ""
    patch_intent = control.get("patch_intent") or {}
    if isinstance(patch_intent, dict):
        for key in ("relative_path", "file", "target_file"):
            value = patch_intent.get(key)
            if value:
                return str(value)
    top = control.get("top_hypothesis") or {}
    symbol = top.get("symbol") if isinstance(top, dict) else ""
    if isinstance(symbol, str) and "::" in symbol:
        return symbol.split("::", 1)[0]
    return ""


def _control_source_text(control: dict | None) -> str:
    if not isinstance(control, dict):
        return ""
    patch_intent = control.get("patch_intent") or {}
    if isinstance(patch_intent, dict):
        source = patch_intent.get("source_snippet")
        if isinstance(source, str) and source.strip():
            return source
    for related in control.get("related_snippets") or []:
        if isinstance(related, dict):
            snippet = related.get("snippet")
            if isinstance(snippet, str) and snippet.strip():
                return snippet
    return ""


def _format_harness_generation_block(decision: HarnessModeDecision) -> str:
    hard_deny = format_harness_deny_message(decision)
    if hard_deny:
        return hard_deny
    lines = [
        f"Harness mode: {decision.mode}",
        decision.reason,
    ]
    if decision.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in decision.warnings)
    return "\n".join(lines)


def _patch_generation_harness_block(repo_path: str | None, control: dict) -> dict | None:
    runtime_state = build_runtime_environment_state(
        request.form.get("runtime_environment"),
        custom_name=request.form.get("runtime_environment_custom_name"),
        notes=request.form.get("runtime_environment_notes"),
    )
    decision = decide_harness_mode(
        repo_root=repo_path or ".",
        runtime_environment=runtime_state["runtime_environment"],
        request_path=repo_path or "",
        target_path=_control_target_path(control),
        source_text=_control_source_text(control),
        patch_gates_passed=True,
    )
    if decision.can_generate_patch:
        return None
    return {
        "error": _format_harness_generation_block(decision),
        "harness_mode": decision.mode,
        "harness_mode_decision": decision.to_dict(),
        "harness_warnings": list(decision.warnings),
        **runtime_state,
        "runtime_environment_description": describe_runtime_environment(
            runtime_state["runtime_environment"],
            runtime_state["runtime_environment_custom_name"],
            runtime_state["runtime_environment_notes"],
        ),
    }

def should_show_node_clean(node_id: str, show_tests: bool = False) -> bool:
    if "::expr::" in node_id:
        return False

    if node_id.startswith("call::"):
        return False

    if "::<top-level>" in node_id:
        return False

    if not show_tests and (
        "_test." in node_id
        or "test." in node_id
        or "Test" in node_id
    ):
        return False

    return True



def should_show_edge_clean(edge_type: str) -> bool:
    return edge_type in {
        "contains",
        "resolved_call",
        "calls",
        "imports",
    }

def _run_mode(
    mode: str,
    query: str,
    repo_path: str,
    agent_mode: str,
    project_tag: str,
    patch_style: str = "safe_minimal",
    ignore_repo_dna: bool = False,
    runtime_environment: str = "auto",
    runtime_environment_custom_name: str = "",
    runtime_environment_notes: str = "",
):
    """Dispatch to the right pipeline. Returns (result_dict, final_tag)."""
    if mode == "deep":
        data = deep_project_understand(query, repo_path)
        return {
            "answer": json.dumps(data, indent=2, ensure_ascii=False),
            "context": "",
            "graph": json.dumps(data.get("graph", {}), indent=2, ensure_ascii=False),
            "state": "",
            "patch": "",
            "validation": "",
        }, project_tag

    if mode == "control":
        structured = run_control_structured(query, repo_path)
        # Surface the chosen vibecoding style so the control engine's prompt
        # block honors it even in "control" mode.
        structured["patch_style"] = patch_style
        data = run_control(query, repo_path)
        return {
            "answer": data,
            "context": json.dumps(structured, indent=2, ensure_ascii=False),
            "graph": json.dumps(structured.get("evidence", []), indent=2, ensure_ascii=False),
            "state": structured.get("execution_trace", ""),
            "patch": json.dumps(structured.get("patch_intent", {}), indent=2, ensure_ascii=False),
            "validation": json.dumps(structured.get("decision", {}), indent=2, ensure_ascii=False),
        }, project_tag

    if mode == "full":
        result = run_agent_web(
            query,
            repo_path,
            agent_mode=agent_mode,
            project_tag=project_tag,
            patch_style=patch_style,
            ignore_repo_dna=ignore_repo_dna,
            runtime_environment=runtime_environment,
            runtime_environment_custom_name=runtime_environment_custom_name,
            runtime_environment_notes=runtime_environment_notes,
        )
        return result, (result.get("project_tag") or project_tag)

    # default: retrieve
    retrieved = retrieve_context(query, repo_path=repo_path, project_tag=project_tag)
    deep = deep_project_understand(query, repo_path)
    structured = run_control_structured(query, repo_path)
    prompt = (
        "You are the AI Coding Agent.\n\n"
        f"User question:\n{query}\n\n"
        f"Retrieved context:\n{retrieved}\n\n"
        f"Deep analysis:\n{json.dumps(deep, indent=2)}\n\n"
        f"Control reasoning:\n{json.dumps(structured, indent=2)}\n\n"
        "Explain clearly: what is happening, what is disconnected, what should be connected."
    )
    answer = run_gemini_request(prompt)
    return {
        "answer": answer,
        "context": retrieved,
        "graph": "",
        "state": "",
        "patch": "",
        "validation": "",
    }, project_tag


@app.route("/", methods=["GET", "POST"])
def index():
    sessions = load_sessions()
    current = None
    result = {}
    error = None
    active_web_mode = _normalize_web_mode(request.values.get("web_mode"))

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        repo_path = request.form.get("repo_path", "").strip()
        active_web_mode = _normalize_web_mode(request.form.get("web_mode"))
        mode = request.form.get("mode", "retrieve")
        if active_web_mode == "chat":
            mode = "retrieve"
        agent_mode = request.form.get("agent_mode", "reviewer")
        user_tag = request.form.get("project_tag")
        # Vibecoding style — picks how aggressive/creative patches may be.
        # Falls back to safe_minimal if the form omits it (backward compat).
        
        patch_style = normalize_patch_style(request.form.get("patch_style"))
        ignore_repo_dna = request.form.get("ignore_repo_dna") in {"1", "on", "true", "yes"}
        runtime_state = build_runtime_environment_state(
            request.form.get("runtime_environment"),
            custom_name=request.form.get("runtime_environment_custom_name"),
            notes=request.form.get("runtime_environment_notes"),
        )

        if not query or not repo_path:
            error = "Both 'query' and 'repo_path' are required."
            result = _empty_result(error)
            _attach_runtime_environment(result, runtime_state)
        else:
            # Compute the canonical tag once per real submission.
            project_tag = build_project_tag(repo_path, user_tag)
            final_tag = project_tag
            model_calls = None

            try:
                with ModelStatsScope() as scoped_calls:
                    model_calls = scoped_calls
                    result, final_tag = _run_mode(
                        mode=mode,
                        query=query,
                        repo_path=repo_path,
                        agent_mode=agent_mode,
                        project_tag=project_tag,
                        patch_style=patch_style,
                        ignore_repo_dna=ignore_repo_dna,
                        runtime_environment=runtime_state["runtime_environment"],
                        runtime_environment_custom_name=runtime_state["runtime_environment_custom_name"],
                        runtime_environment_notes=runtime_state["runtime_environment_notes"],
                    )
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"❌ Pipeline error in mode={mode}:\n{tb}")
                error = f"Pipeline error: {type(e).__name__}: {e}"
                result = _empty_result(error)
                result["validation"] = tb  # show traceback in the validation tab
            finally:
                _attach_runtime_environment(result, runtime_state)
                _attach_model_usage(result, model_calls)

            current = save_session(
                query,
                repo_path,
                mode,
                result,
                final_tag,
                patch_style,
                ignore_repo_dna,
                active_web_mode,
                runtime_state["runtime_environment"],
                runtime_state["runtime_environment_custom_name"],
                runtime_state["runtime_environment_notes"],
            )
            sessions = load_sessions()

    return render_template(
        "index.html",
        sessions=sessions,
        current=current,
        result=result,
        error=error,
        active_web_mode=active_web_mode,
    )

@app.route("/generate_patch", methods=["POST"])
def generate_patch():
    repo_path = request.form.get("repo_path", "")
    control_json = request.form.get("control", "")

    try:
        control = json.loads(control_json)
    except Exception:
        return {"error": "Invalid control JSON"}

    harness_block = _patch_generation_harness_block(repo_path, control)
    if harness_block:
        return harness_block

    prompt = build_control_prompt(control, "Generate patch", repo_path=repo_path or None)

    with ModelStatsScope() as model_calls:
        response = run_gemini_request(prompt)
    patch = extract_json_block(response)

    if not patch:
        return {
            "error": "Failed to generate patch",
            "usage": format_usage_report(model_calls),
        }

    return {
        "patch": json.dumps(patch, indent=2, ensure_ascii=False),
        "usage": format_usage_report(model_calls),
    }

@app.route("/undo_patch", methods=["POST"])
def undo_patch():
    repo_path = request.form.get("repo_path", "")
    target_file = request.form["file"]

    repo_root = Path(repo_path).resolve()
    file_path = (repo_root / target_file).resolve()
    try:
        file_path.relative_to(repo_root)
    except ValueError:
        return {
            "success": False,
            "message": "Unsafe undo target: file is outside repo.",
        }, 400

    # 🔥 FIX: dùng safe_path
    safe_path = target_file.replace("/", "_").replace("\\", "_")

    backups = sorted(BACKUP_DIR.glob(f"{safe_path}_*.bak"), reverse=True)

    if not backups:
        return {
            "success": False,
            "message": "No backup found",
        }

    latest = backups[0]

    file_path.write_text(latest.read_text(encoding="utf-8"), encoding="utf-8")

    latest.unlink()

    return {
        "success": True,
        "message": "Undo successful",
    }

@app.route("/dream/queue", methods=["GET", "POST"])
def dream_queue_route():
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    if request.method == "GET":
        return {"queue": dream_artifacts.read_queue(repo_path)}

    action = request.form.get("action", "add").strip().lower()
    if action == "clear":
        dream_artifacts.clear_queue(repo_path)
        return {"queue": []}

    if action == "add":
        # Phase 4.7a — taxonomy cleanup. The request can either:
        #   (new path)    dream_type + action_level
        #   (legacy path) kind ± mode (existing UI / scripts / queued items)
        # Either way we end up with both the new fields AND the legacy `kind`
        # populated so the run-time code in core/sleeping_consultant.py keeps
        # working unchanged.
        title = request.form.get("title", "").strip()
        hint = request.form.get("hint", "").strip()
        notes = request.form.get("notes", "").strip()
        reference_files_raw = request.form.get("reference_files", "").strip()
        snippets_raw = request.form.get("snippets", "").strip()
        if not title:
            return {"error": "title is required"}

        raw_dream_type = (request.form.get("dream_type") or "").strip()
        raw_action_level = (request.form.get("action_level") or "").strip()
        raw_kind = (request.form.get("kind") or "").strip()
        raw_mode = (request.form.get("mode") or "").strip()

        if raw_dream_type or raw_action_level:
            dream_type = raw_dream_type
            action_level = raw_action_level
            if not action_level:
                allowed = dream_taxonomy.allowed_action_levels(dream_type)
                action_level = allowed[0] if allowed else ""
            err = dream_taxonomy.validate(dream_type, action_level)
            if err:
                return {"error": err}
        else:
            # Legacy path: reject obvious garbage so we don't pollute the queue,
            # then normalize the recognized aliases through the taxonomy.
            legacy_kind_key = raw_kind.lower()
            legacy_aliases = {
                "", "bug", "bugs", "bug_investigation",
                "debt", "debt_cleanup",
                "idea", "ideas", "idea_trial",
                "research", "research_study",
                "reference study", "reference_study",
                "case_idea_research",
            }
            if legacy_kind_key not in legacy_aliases:
                return {"error": f"unknown kind: {raw_kind}"}
            dream_type, action_level = dream_taxonomy.normalize_legacy(
                raw_kind, raw_mode,
            )

        # Map the canonical dream_type back to the legacy `kind` value the
        # run-time code still reads. Phase 4.7a is taxonomy cleanup only; it
        # does NOT change the patch / proposal execution behavior.
        kind = dream_taxonomy.legacy_kind_for_dream_type(dream_type)

        item = {
            "kind": kind,
            "dream_type": dream_type,
            "action_level": action_level,
            "title": title,
            "hint": hint,
        }
        if notes:
            item["notes"] = notes
        if reference_files_raw:
            item["reference_files"] = [
                part.strip()
                for line in reference_files_raw.splitlines()
                for part in line.split(",")
                if part.strip()
            ]
        if snippets_raw:
            try:
                parsed_snippets = json.loads(snippets_raw)
                item["snippets"] = parsed_snippets
            except Exception:
                item["snippets"] = [snippets_raw]
        items = dream_artifacts.append_to_queue(repo_path, item)
        return {"queue": items}

    return {"error": f"unknown action: {action}"}


@app.route("/dream/taxonomy", methods=["GET"])
def dream_taxonomy_route():
    """Phase 4.7a: expose the dream_type / action_level matrix so the UI can
    populate dropdowns and hide invalid action levels per work type without
    duplicating the rules in JavaScript.
    """
    return {
        "dream_types": list(dream_taxonomy.DREAM_TYPES),
        "action_levels": list(dream_taxonomy.ACTION_LEVELS),
        "allowed_combinations": {
            k: list(v) for k, v in dream_taxonomy.ALLOWED_COMBINATIONS.items()
        },
    }


@app.route("/dream/run", methods=["POST"])
def dream_run_route():
    """Phase 2: kicks the run on a background thread and returns immediately.

    Poll /dream/status to follow progress. `dream_mode` selects Dream V2
    behaviour (`plan_only` default / `patch_if_safe` / `research`).
    `time_budget_sec` (Slice α) lets the user override the default 6-hour
    cap from the web UI; clamped to [60, 86400] (1 min – 24 hr) for sanity.
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    patch_style = normalize_patch_style(request.form.get("patch_style"))
    dream_mode = request.form.get("dream_mode", "plan_only")

    # Parse + clamp time budget. Default 6 hours matches start_overnight_async().
    try:
        budget_raw = int(request.form.get("time_budget_sec", 6 * 3600))
    except (TypeError, ValueError):
        budget_raw = 6 * 3600
    time_budget_sec = max(60, min(86400, budget_raw))  # [1 min, 24 hr]

    try:
        return start_overnight_async(
            repo_path,
            patch_style=patch_style,
            dream_mode=dream_mode,
            time_budget_sec=time_budget_sec,
        )
    except Exception as e:
        return {"error": f"start_overnight_async failed: {e}"}


@app.route("/dream/status", methods=["GET"])
def dream_status_route():
    return get_run_state()


@app.route("/dream/stop", methods=["POST"])
def dream_stop_route():
    """Slice β: ask the in-flight dream run to stop gracefully.

    Returns {stopped: bool, reason: str}. The actual stop happens between
    queue items; the currently-running item finishes first. Polling
    /dream/status will show stop_requested=true until the run exits.
    """
    try:
        return request_stop()
    except Exception as e:
        return {"error": f"stop request failed: {e}"}


@app.route("/dream/list", methods=["GET"])
def dream_list_route():
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    latest = dream_artifacts.latest_report_dir(repo_path)
    if not latest:
        return {"error": "No dream report found yet."}

    try:
        data = dream_artifacts.read_report(latest)
    except Exception as e:
        return {"error": f"failed to read list.json: {e}"}

    return {
        "report_dir": str(latest),
        "items": data.get("items", []),
        "patch_style": data.get("patch_style"),
        "dream_mode": data.get("dream_mode"),
        "completed_at": data.get("completed_at"),
    }


@app.route("/dream/reports", methods=["GET"])
def dream_reports_route():
    """All past dream runs for a repo, newest first. Feeds the sidebar list."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    return {"reports": dream_artifacts.list_all_reports(repo_path)}


@app.route("/dream/report", methods=["GET"])
def dream_report_route():
    """Full content of one historical dream run.

    Slice γ.3.1: accepts an optional `run` query parameter. With `run`, the
    report path is `<dreams>/<date>/<run>/` (new layout). Without `run`,
    falls back to `<dreams>/<date>/` (legacy layout — pre-γ.3.1 runs).

    Defensive: `run` is validated against a strict regex to prevent path
    traversal (only digits, dashes, and the literal suffix "-run" allowed).
    """
    import re
    repo_path = request.values.get("repo_path", "").strip()
    date = request.values.get("date", "").strip()
    run = request.values.get("run", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    if not date:
        return {"error": "date is required (YYYY-MM-DD)"}
    # Validate date shape (YYYY-MM-DD) — defensive.
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"error": f"invalid date format: {date}"}

    dreams_root = dream_artifacts.dreams_root(repo_path)
    if run:
        # Validate run shape (HHMMSS-run, optionally with -N collision suffix).
        if not re.match(r"^\d{6}-run(-\d+)?$", run):
            return {"error": f"invalid run id: {run}"}
        report_dir = dreams_root / date / run
    else:
        # Legacy path: list.json directly under the date dir.
        report_dir = dreams_root / date

    # Defensive: ensure resolved path stays inside dreams_root.
    try:
        report_dir.resolve().relative_to(dreams_root.resolve())
    except ValueError:
        return {"error": "report path escapes dreams root"}

    if not report_dir.is_dir():
        return {"error": f"no report for date={date}{(' run=' + run) if run else ' (legacy)'}"}
    report = dream_artifacts.read_report(report_dir)
    # Phase 5P.1: render the morning report Markdown to safe HTML for the
    # viewer modal. The raw `morning_report` text is left in place as a
    # fallback; this only adds a rendered companion field.
    report["morning_report_html"] = render_dream_report_markdown(
        report.get("morning_report", "")
    )
    _list_json_path = report_dir / "list.json"
    try:
        report["list_json_raw"] = (
            _list_json_path.read_text(encoding="utf-8") if _list_json_path.is_file() else ""
        )
    except Exception:
        report["list_json_raw"] = ""
    return report


@app.route("/dream/apply", methods=["POST"])
def dream_apply_route():
    """Apply selected dream items to the real repo. One commit per item.

    `selection`: '1', '1,2', or 'all'.
    """
    import subprocess

    repo_path = request.form.get("repo_path", "").strip()
    selection = request.form.get("selection", "").strip().lower()

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    if not selection:
        return {"error": "selection is required (e.g., '1', '1,2', 'all')"}

    latest = dream_artifacts.latest_report_dir(repo_path)
    if not latest:
        return {"error": "No dream report found to apply."}

    try:
        data = json.loads((latest / "list.json").read_text(encoding="utf-8"))
    except Exception as e:
        return {"error": f"failed to read list.json: {e}"}

    items = data.get("items", [])

    if selection == "all":
        chosen_idxs: list[int] = [it.get("idx") for it in items if isinstance(it.get("idx"), int)]
    else:
        try:
            chosen_idxs = [int(x.strip()) for x in selection.split(",") if x.strip()]
        except Exception:
            return {"error": f"invalid selection: {selection}"}

    chosen = [it for it in items if it.get("idx") in chosen_idxs]
    if not chosen:
        return {"error": "no matching items in selection"}

    results = []
    for it in chosen:
        idx = it.get("idx")
        title = it.get("title", "untitled")
        kind = (it.get("kind") or "").lower()
        item_dir_path = latest / it.get("item_dir_name", "")

        if kind in {"idea", "research"}:
            results.append({
                "idx": idx, "title": title,
                "status": f"skipped_{kind}",
                "message": (
                    "Non-patch item — see design.md / proposal.md / plan_analysis.json "
                    "in artifacts."
                ),
            })
            continue

        item_status = it.get("status")
        if item_status in {
            "planned_no_patch",
            "patch_skipped_needs_vibe",
            "research_note_created",
            "needs_manual_review",
            "blocked_missing_context",
        }:
            results.append({
                "idx": idx, "title": title,
                "status": "skipped_plan_only",
                "message": (
                    f"Item is `{item_status}`; nothing to apply. "
                    "Re-run Dream in patch_if_safe mode if you want a patch."
                ),
            })
            continue

        plan_path = item_dir_path / "patch_plan.json"
        if it.get("status") != "ready_to_apply":
            results.append({
                "idx": idx,
                "title": title,
                "status": "skipped_not_ready",
                "message": f"Item status is {it.get('status')}, not ready_to_apply.",
            })
            continue
        if not plan_path.exists():
            results.append({
                "idx": idx, "title": title,
                "status": "skipped_no_plan",
                "message": f"patch_plan.json not found at {plan_path}",
            })
            continue

        try:
            plan = json.loads(plan_path.read_text(encoding="utf-8"))
        except Exception as e:
            results.append({
                "idx": idx, "title": title,
                "status": "error",
                "message": f"failed to read patch_plan: {e}",
            })
            continue

        touched = patch_plan_files(plan)
        patch_safety = evaluate_patch_safety(
            touched,
            project_root=Path(repo_path).resolve(),
        )
        if not patch_safety["ok"]:
            results.append({
                "idx": idx,
                "title": title,
                "status": "blocked_by_safety",
                "message": (
                    "Dream apply blocked by safety gate: "
                    + "; ".join(patch_safety["reasons"])
                ),
                "patch_safety": patch_safety,
            })
            continue

        # Apply to real repo and validate again, even though it passed in sandbox.
        language = inspect_repo_inventory(repo_path).get("primary_language", "unknown")
        validation_command = get_default_validation_command(language, Path(repo_path))

        result = run_patch_plan_with_artifacts(
            repo_path,
            plan,
            validation_command=validation_command or None,
            user_query=title,
            control_result={"route": "dream_apply", "idx": idx, "title": title},
            source="web_dream_apply",
        )
        if not result.get("success"):
            results.append({
                "idx": idx, "title": title,
                "status": "apply_failed",
                "message": (result.get("message") or "")[:200],
            })
            continue

        # Stage only the paths this plan touched, then commit.
        touched = sorted({path for path in touched if path})
        commit_status = "applied (no commit — no touched paths)"
        if touched:
            try:
                subprocess.run(
                    ["git", "-C", repo_path, "add", *touched],
                    check=True, capture_output=True,
                )
                subprocess.run(
                    ["git", "-C", repo_path, "commit", "-m", f"[dream] {title}"],
                    check=True, capture_output=True,
                )
                commit_status = "applied + committed"
            except subprocess.CalledProcessError as e:
                stderr = (e.stderr or b"").decode("utf-8", errors="replace")[:200]
                commit_status = f"applied, but commit failed: {stderr}"
            except FileNotFoundError:
                commit_status = "applied (git not available; commit skipped)"

        results.append({
            "idx": idx, "title": title,
            "status": "applied",
            "message": commit_status,
        })

    return {"results": results}


@app.route("/dream/promote-artifact", methods=["POST"])
def dream_promote_artifact_route():
    """Slice γ3.2: mark one refined artifact as preferred for a Dream item.

    Pure metadata operation. No LLM, no patch apply, no artifact writes —
    only the `list.json` for the run is rewritten with `preferred_artifact`
    and `preferred_artifact_kind` fields on the matching item.

    Inputs (form-data): `repo_path`, `date` (YYYY-MM-DD), `run` (HHMMSS-run),
    `item_idx` (int), `artifact` (filename only — must match
    `plan_analysis.refined_passN.json` or `proposal.refined_passN.md`).

    Legacy reports without a `run` are rejected with a friendly 400.
    """
    import re

    repo_path = request.form.get("repo_path", "").strip()
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    artifact = request.form.get("artifact", "").strip()
    item_idx_raw = request.form.get("item_idx", "").strip()

    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": f"invalid date format: {date}"}, 400
    if not run:
        return {
            "ok": False,
            "error": "Promotion only supported for timestamped run directories. This is a legacy report.",
        }, 400
    if not re.match(r"^\d{6}-run(-\d+)?$", run):
        return {"ok": False, "error": f"invalid run id: {run}"}, 400
    try:
        item_idx = int(item_idx_raw)
    except (TypeError, ValueError):
        return {"ok": False, "error": "item_idx must be an integer"}, 400

    try:
        out = dream_artifacts.promote_artifact(repo_path, date, run, item_idx, artifact)
        return out
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except (FileNotFoundError, LookupError) as e:
        return {"ok": False, "error": str(e)}, 404
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500


def _goal_brief_payload() -> dict:
    if request.is_json:
        data = request.get_json(silent=True)
        return data if isinstance(data, dict) else {}
    return request.form.to_dict()


def _truthy_form_value(value: object) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@app.route("/goal-brief/autocomplete", methods=["POST"])
def goal_brief_autocomplete_route():
    payload = _goal_brief_payload()
    result = goal_brief_autocomplete_core.autocomplete_goal_brief(
        str(payload.get("messy_intent") or ""),
        repo_path=(str(payload.get("repo_path") or "").strip() or None),
        mode_hint=(str(payload.get("mode_hint") or "").strip() or None),
        validation_hint=(str(payload.get("validation_hint") or "").strip() or None),
    )
    if not result.get("ok"):
        return result, 400
    draft = result["draft"]
    return {
        "ok": True,
        "draft": draft,
        "markdown": goal_brief_autocomplete_core.render_goal_brief_draft_markdown(draft),
    }


@app.route("/mode/router", methods=["POST"])
def mode_router_route():
    payload = _goal_brief_payload()
    goal_brief = payload.get("goal_brief") if isinstance(payload.get("goal_brief"), dict) else None
    handoff_draft = payload.get("handoff_draft") if isinstance(payload.get("handoff_draft"), dict) else None
    result = mode_router_core.route_mode(
        str(payload.get("user_intent") or ""),
        goal_brief=goal_brief,
        handoff_draft=handoff_draft,
    )
    if not result.get("ok"):
        return result, 400
    draft = result["draft"]
    return {
        "ok": True,
        "draft": draft,
        "markdown": mode_router_core.render_mode_route_markdown(draft),
    }


@app.route("/review-pack/generate", methods=["POST"])
def review_pack_generate_route():
    payload = _goal_brief_payload()
    goal_brief = payload.get("goal_brief") if isinstance(payload.get("goal_brief"), dict) else None
    mode_router_result = (
        payload.get("mode_router_result")
        if isinstance(payload.get("mode_router_result"), dict)
        else None
    )
    handoff_draft = payload.get("handoff_draft") if isinstance(payload.get("handoff_draft"), dict) else None
    result = review_pack_generator_core.generate_review_pack(
        goal_brief=goal_brief,
        mode_router_result=mode_router_result,
        handoff_draft=handoff_draft,
        repo_path=(str(payload.get("repo_path") or "").strip() or None),
        worker_target=(str(payload.get("worker_target") or "").strip() or None),
    )
    if not result.get("ok"):
        return result, 400
    draft = result["draft"]
    return {
        "ok": True,
        "draft": draft,
        "markdown": review_pack_generator_core.render_review_pack_markdown(draft),
    }


@app.route("/goal-brief/start", methods=["POST"])
def goal_brief_start_route():
    payload = _goal_brief_payload()
    try:
        result = goal_brief_core.create_goal_brief(
            goal=str(payload.get("goal") or ""),
            repo_path=(str(payload.get("repo_path") or "").strip() or None),
            export_md=_truthy_form_value(payload.get("export_md")),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return result


@app.route("/goal-brief/update", methods=["POST"])
def goal_brief_update_route():
    payload = _goal_brief_payload()
    try:
        result = goal_brief_core.update_goal_brief(
            str(payload.get("brief_ref") or ""),
            answer=str(payload.get("answer") or ""),
            repo_path=(str(payload.get("repo_path") or "").strip() or None),
            export_md=_truthy_form_value(payload.get("export_md")),
        )
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return result


@app.route("/health", methods=["GET"])
def health_route():
    """Settings/Health panel data (Phase 5 Slice 2). Cheap checks only — no
    model loads, no long-running probes. See core/health.py for the per-check
    rules and timeouts."""
    from core.health import get_system_health  # lazy import; isolates failures
    try:
        return get_system_health()
    except Exception as e:
        return (
            {"error": f"health check crashed: {e}", "checks": [], "summary": {}},
            500,
        )


@app.route("/tools/registry", methods=["GET"])
def tools_registry_route():
    """Phase 8-prep.1: read-only, mode-aware listing of the tool registry.

    Metadata only. Annotates each tool with an `allowed` boolean computed
    via tool_registry.is_tool_allowed under the requested capability_mode
    (default read_only). Never invokes any registered tool.
    """
    from core import tool_registry

    mode = (request.values.get("mode") or "read_only").strip()
    if mode not in tool_registry.VALID_CAPABILITY_MODES:
        return (
            {
                "ok": False,
                "error": (
                    f"unknown mode {mode!r}; must be one of "
                    f"{sorted(tool_registry.VALID_CAPABILITY_MODES)}"
                ),
            },
            400,
        )

    try:
        tools = tool_registry.list_tools()
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500

    allowed_count = 0
    for t in tools:
        # list_tools returns deep copies — safe to annotate in place.
        is_allowed = tool_registry.is_tool_allowed(t["name"], capability_mode=mode)
        t["allowed"] = bool(is_allowed)
        if is_allowed:
            allowed_count += 1

    return {
        "ok": True,
        "capability_mode": mode,
        "tools": tools,
        "allowed_count": allowed_count,
        "total_count": len(tools),
    }


_MCP_AUDIT_DEFAULT_LIMIT = 50
_MCP_AUDIT_MAX_LIMIT = 200


def _mcp_audit_limit(value: str | None) -> int:
    try:
        limit = int((value or "").strip())
    except (AttributeError, TypeError, ValueError):
        return _MCP_AUDIT_DEFAULT_LIMIT
    if limit <= 0:
        return _MCP_AUDIT_DEFAULT_LIMIT
    return min(limit, _MCP_AUDIT_MAX_LIMIT)


@app.route("/mcp/audit", methods=["GET"])
def mcp_audit_route():
    """Read recent MCP invocation audit events without executing tools."""
    limit = _mcp_audit_limit(request.values.get("limit"))
    try:
        events = list_mcp_invocations(limit=limit)
    except Exception as e:
        return {
            "ok": False,
            "events": [],
            "count": 0,
            "limit": limit,
            "error": f"{type(e).__name__}: {e}",
        }, 500
    return {
        "ok": True,
        "events": events,
        "count": len(events),
        "limit": limit,
    }


_MCP_INSPECTOR_TARGETS = {
    "read_only": PROJECT_ROOT / "scripts" / "mcp_readonly_server.py",
    "artifact_write": PROJECT_ROOT / "scripts" / "mcp_artifact_write_server.py",
}


def _mcp_inspector_command(target: str) -> list[str] | None:
    script_path = _MCP_INSPECTOR_TARGETS.get(target)
    if script_path is None:
        return None
    script_arg = script_path.relative_to(PROJECT_ROOT).as_posix()
    return [
        shutil.which("npx") or "npx",
        "-y",
        "@modelcontextprotocol/inspector",
        sys.executable,
        script_arg,
    ]


def _launch_mcp_inspector(command: list[str]) -> None:
    subprocess.Popen(
        command,
        cwd=PROJECT_ROOT,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


@app.route("/mcp/inspector/launch", methods=["POST"])
def mcp_inspector_launch_route():
    target = (request.form.get("target") or "").strip()
    command = _mcp_inspector_command(target)
    if command is None:
        return {"ok": False, "error": "unknown MCP Inspector target"}, 400
    try:
        _launch_mcp_inspector(command)
    except Exception as e:
        return {
            "ok": False,
            "target": target,
            "error": (
                f"failed to launch MCP Inspector for {target}: "
                f"{type(e).__name__}: {e}"
            ),
        }, 500
    return {"ok": True, "target": target}


@app.route("/benchmarks/list", methods=["GET"])
def benchmarks_list_route():
    """List past benchmark reports for the Benchmarks tab (Phase 5 Slice 3).
    Returns metadata only — call /benchmarks/report for full content."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    from core.benchmarks_view import list_benchmark_reports
    return {"reports": list_benchmark_reports(repo_path)}


@app.route("/benchmarks/cases", methods=["GET"])
def benchmarks_cases_route():
    """List benchmark cases for the Run Selected modal."""
    try:
        return {"ok": True, "cases": benchmark_web.list_benchmark_cases()}
    except Exception as e:
        return {"ok": False, "error": f"failed to list benchmark cases: {type(e).__name__}"}, 500


@app.route("/benchmarks/run", methods=["POST"])
def benchmarks_run_route():
    """Start a background benchmark run.

    Form fields:
      - repo_path: where reports should be written under .agent/benchmarks.
      - selection: all | selected.
      - cases: JSON list or comma-separated names when selection=selected.
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}, 400

    selection = request.form.get("selection", "all").strip().lower()
    selected_cases: list[str] | None = None
    if selection == "selected":
        raw_cases = request.form.get("cases", "").strip()
        try:
            parsed = json.loads(raw_cases) if raw_cases.startswith("[") else None
        except Exception:
            parsed = None
        if isinstance(parsed, list):
            selected_cases = [str(item).strip() for item in parsed if str(item).strip()]
        else:
            selected_cases = [item.strip() for item in raw_cases.split(",") if item.strip()]
        if not selected_cases:
            return {"error": "choose at least one benchmark case"}, 400
    elif selection != "all":
        return {"error": f"unknown benchmark selection: {selection}"}, 400

    def _form_bool(name: str, default: bool = False) -> bool:
        raw = request.form.get(name)
        if raw is None:
            return default
        return raw.strip().lower() not in {"0", "false", "no", "off", ""}

    try:
        retry_failed = int(request.form.get("retry_failed", "0"))
    except (TypeError, ValueError):
        retry_failed = 0
    retry_failed = max(0, min(3, retry_failed))

    try:
        result = benchmark_web.start_benchmark_run_async(
            repo_path=repo_path,
            selected_cases=selected_cases,
            fast=_form_bool("fast", True),
            turbo=_form_bool("turbo", False),
            skip_toolchain_failures=_form_bool("skip_toolchain_failures", True),
            retry_failed=retry_failed,
            markdown=_form_bool("markdown", True),
        )
    except Exception as e:
        return {"error": f"failed to start benchmark run: {type(e).__name__}: {e}"}, 500
    status = 409 if result.get("error") else 200
    return result, status


@app.route("/benchmarks/status", methods=["GET"])
def benchmarks_status_route():
    return benchmark_web.get_benchmark_state()


@app.route("/benchmarks/stop", methods=["POST"])
def benchmarks_stop_route():
    try:
        return benchmark_web.request_benchmark_stop()
    except Exception as e:
        return {"error": f"stop request failed: {type(e).__name__}: {e}"}, 500


@app.route("/benchmarks/report", methods=["GET"])
def benchmarks_report_route():
    """Full content of one benchmark report (Phase 5 Slice 3).

    `filename` must match `benchmark_report_<digits>.json` and resolve to a
    file inside `<repo_path>/.agent/benchmarks/` (path-traversal guard)."""
    repo_path = request.values.get("repo_path", "").strip()
    filename = request.values.get("filename", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    if not filename:
        return {"error": "filename is required"}
    from core.benchmarks_view import read_benchmark_report
    data = read_benchmark_report(repo_path, filename)
    if data is None:
        return {"error": f"report not found or invalid name: {filename}"}, 404
    # Phase 14.3: attach a read-only failure taxonomy for display. This only
    # classifies already-loaded results; it never writes artifacts or changes
    # scoring, and the stored report file on disk is left untouched.
    from core.failure_taxonomy import summarize_benchmark_failures
    return {**data, "failure_taxonomy": summarize_benchmark_failures(data)}


@app.route("/benchmarks/create-case", methods=["POST"])
def benchmarks_create_case_route():
    """Create a new benchmark case by copying a source repo into cases/."""
    try:
        result = benchmark_web.create_benchmark_case_from_repo(
            source_repo_path=request.form.get("source_repo_path", "").strip(),
            case_name=request.form.get("case_name", "").strip(),
            user_prompt=request.form.get("prompt", "").strip(),
            validation_command=request.form.get("validation_command", "").strip(),
            expected_changed_files=request.form.get("expected_changed_files", ""),
            forbidden_changed_files=request.form.get("forbidden_changed_files", ""),
            use_llm=(request.form.get("use_llm", "true").strip().lower() not in {"0", "false", "no", "off"}),
            overwrite=(request.form.get("overwrite", "false").strip().lower() not in {"0", "false", "no", "off", ""}),
        )
    except Exception as e:
        return {"ok": False, "error": f"failed to create case: {type(e).__name__}: {e}"}, 500
    return result, 200 if result.get("ok") else 400


@app.route("/benchmarks/case-defaults", methods=["GET"])
def benchmarks_case_defaults_route():
    """Suggest Add Case defaults from repo structure and current git diff."""
    try:
        result = benchmark_web.infer_case_defaults(
            request.values.get("source_repo_path", "").strip(),
            user_prompt=request.values.get("prompt", "").strip(),
        )
    except Exception as e:
        return {"ok": False, "error": f"failed to infer defaults: {type(e).__name__}: {e}"}, 500
    return result, 200 if result.get("ok") else 400


@app.route("/benchmarks/prompt-cost", methods=["GET"])
def benchmarks_prompt_cost_route():
    """Phase 5.7: read-only Prompt / Cost Quantifier panel data.

    Groups existing ``benchmark_report_*.json`` files by
    ``brain_stamp.prompt_config_hash``. Never runs benchmarks, never calls a
    model, never executes a patch, and never touches the source reports.
    """
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"ok": False, "error": f"repo_path is not a directory: {repo_path}"}, 400

    from core.prompt_cost_quantifier import build_prompt_cost_report  # lazy import
    benchmark_root = Path(repo_path).resolve() / ".agent" / "benchmarks"
    try:
        report = build_prompt_cost_report(benchmark_root)
    except Exception as e:
        return (
            {"ok": False, "error": f"prompt cost report failed: {type(e).__name__}: {e}"},
            500,
        )
    return {"ok": True, "report": report}


@app.route("/dream/seed-from-benchmark", methods=["POST"])
def dream_seed_from_benchmark_route():
    """Append items to the dream queue based on a benchmark report.

    Failed and flaky cases become `kind=bug`; slowest passing cases become
    `kind=debt`.
    Each appended item carries `source=benchmark`, `benchmark_report` (the JSON
    filename used), and `case_name` for traceability.

    Optional form field `report_filename` (Phase 5 Slice 3) seeds from a
    specific historical report instead of auto-picking the newest.
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    report_filename = (request.form.get("report_filename") or "").strip() or None

    try:
        items = dream_artifacts.seed_queue_from_latest_benchmark(
            repo_path,
            report_filename=report_filename,
        )
    except Exception as e:
        return {"error": f"seed failed: {e}"}, 500

    # Empty list is a valid outcome (dedupe matched everything, OR no reports
    # exist yet, OR the chosen report had no failures/slow cases). Caller's JS
    # distinguishes count=0 from count>0 to show a friendly message.
    return {"added": items, "count": len(items)}


# ---------------------------------------------------------------------------
# Phase 12.8a — Presentation evidence pack helpers. Read-only routes that
# wrap scripts/build_presentation_evidence_pack.py so the existing builder
# can be invoked from the Benchmarks tab without running benchmarks or
# calling models.
# ---------------------------------------------------------------------------

_EVIDENCE_SUBDIR = Path(".agent") / "presentation_evidence"


def _evidence_output_dir(repo_path: str) -> Path:
    return Path(repo_path) / _EVIDENCE_SUBDIR


def _is_safe_evidence_name(name: str) -> bool:
    if not name or not name.endswith(".md"):
        return False
    if any(sep in name for sep in ("/", "\\")):
        return False
    if name in (".", "..") or name.startswith(".."):
        return False
    return True


@app.route("/presentation/evidence/build", methods=["POST"])
def presentation_evidence_build_route():
    """Build the presentation evidence pack under
    <repo_path>/.agent/presentation_evidence/.

    Read-only with respect to benchmark, experiment, trend, and watchlist
    source reports — only writes to the output folder."""
    repo_path = request.form.get("repo_path", "").strip() or request.values.get(
        "repo_path", ""
    ).strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {
            "ok": False,
            "error": f"repo_path is not a directory: {repo_path}",
        }, 400

    try:
        from scripts import build_presentation_evidence_pack as evidence_pack

        result = evidence_pack.build_evidence_pack(repo_path)
    except Exception as exc:  # noqa: BLE001 - reported to client verbatim
        return {
            "ok": False,
            "error": f"failed to build evidence pack: {type(exc).__name__}: {exc}",
        }, 500

    output_dir = Path(result["output_dir"])
    return {
        "ok": True,
        "output_dir": str(output_dir),
        "files": sorted(p.name for p in output_dir.glob("*.md")),
    }


@app.route("/presentation/evidence/list", methods=["GET"])
def presentation_evidence_list_route():
    """List Markdown files inside <repo_path>/.agent/presentation_evidence/.

    Returns an empty list (with `exists=false`) when the folder is missing,
    so the UI can show a friendly call-to-build state."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {
            "ok": False,
            "error": f"repo_path is not a directory: {repo_path}",
        }, 400

    output_dir = _evidence_output_dir(repo_path)
    if not output_dir.is_dir():
        return {
            "ok": True,
            "output_dir": str(output_dir),
            "exists": False,
            "files": [],
        }

    files = []
    for path in sorted(output_dir.glob("*.md")):
        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        files.append({"name": path.name, "size": size})
    return {
        "ok": True,
        "output_dir": str(output_dir),
        "exists": True,
        "files": files,
    }


@app.route("/presentation/evidence/file", methods=["GET"])
def presentation_evidence_file_route():
    """Read one evidence Markdown file by name.

    Path guard rejects path traversal, non-`.md` suffixes, and any name
    containing a path separator. Resolved path is confirmed to be inside
    the evidence output directory."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {
            "ok": False,
            "error": f"repo_path is not a directory: {repo_path}",
        }, 400

    name = request.values.get("name", "").strip()
    if not _is_safe_evidence_name(name):
        return {
            "ok": False,
            "error": f"invalid evidence file name: {name!r}",
        }, 400

    output_dir = _evidence_output_dir(repo_path).resolve()
    target = (output_dir / name).resolve()
    try:
        target.relative_to(output_dir)
    except ValueError:
        return {
            "ok": False,
            "error": "evidence path escapes presentation_evidence directory",
        }, 400

    if not target.is_file():
        return {
            "ok": False,
            "error": f"evidence file not found: {name}",
        }, 404

    try:
        content = target.read_text(encoding="utf-8")
    except OSError as exc:
        return {
            "ok": False,
            "error": f"failed to read evidence file: {type(exc).__name__}: {exc}",
        }, 500

    response = {
        "ok": True,
        "name": name,
        "content": content,
        "size": len(content),
    }
    if request.values.get("as", "").strip().lower() == "html":
        try:
            response["html"] = _markdown_lib.markdown(
                content,
                extensions=["fenced_code", "tables", "toc"],
            )
        except Exception as exc:  # noqa: BLE001
            response["html"] = ""
            response["html_error"] = (
                f"markdown render failed: {type(exc).__name__}: {exc}"
            )
    return response


# ---------------------------------------------------------------------------
# Phase 5 Polish: UI-driven patch proposal flow.
# Three sibling routes turn the Phase 4.5 Level 3 proposal queue CLI into a
# one-click button on the Dream tab. Approval is the click itself; the queue's
# `human_approved_for_proposal=true` gate is satisfied per-call inside
# core.proposal_runner — never on disk.
# ---------------------------------------------------------------------------

@app.route("/dream/plan/latest", methods=["GET"])
def dream_plan_latest():
    """Return latest background_dream_plan_*.json items so the UI can list them."""
    from scripts.run_patch_proposal_queue import _latest_plan, _load_json
    plan_path = _latest_plan()
    if plan_path is None:
        return {"items": [], "plan_path": None}
    data = _load_json(plan_path) or {}
    items = [item for item in (data.get("items") or []) if isinstance(item, dict)]
    return {
        "plan_path": str(plan_path),
        "items": items,
    }


@app.route("/dream/proposals/make", methods=["POST"])
def dream_proposals_make():
    """Trigger a single-item proposal run from the UI."""
    from core.proposal_runner import make_proposal_for_item
    item_json = request.form.get("item", "")
    try:
        item = json.loads(item_json)
    except Exception:
        return {"ok": False, "error": "item must be valid JSON"}, 400
    result = make_proposal_for_item(item)
    if not result.get("ok"):
        # 409 Conflict for busy lock, 400 for bad item.
        status = 409 if "in progress" in (result.get("error") or "") else 400
        return result, status
    return result


@app.route("/dream/proposals/status", methods=["GET"])
def dream_proposals_status():
    """Poll endpoint for the in-flight proposal run."""
    from core.proposal_runner import get_status
    return get_status()


@app.route("/dream/create-lesson-candidate", methods=["POST"])
def dream_create_lesson_candidate_route():
    """Create a candidate lesson from any eligible Dream item (not just ready_to_apply).

    Never calls any model, patch executor, validation command, or subprocess.
    Always produces a candidate-bucket lesson with active_knowledge_allowed=False.
    Promotion requires an explicit Promote click in the Memory tab.
    """
    import config as _cfg
    from core import lesson_store as _ls
    from core.dream_artifacts import resolve_run_dir, load_item_for_promotion
    import re as _re

    repo_path = request.form.get("repo_path", "").strip() or None
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    item_idx_raw = request.form.get("item_idx", "").strip()

    if not item_idx_raw:
        return {"ok": False, "error": "item_idx is required"}, 400
    try:
        item_idx = int(item_idx_raw)
    except ValueError:
        return {"ok": False, "error": "item_idx must be an integer"}, 400

    if not date or not run:
        return {"ok": False, "error": "date and run are required"}, 400

    if not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": "invalid date format"}, 400
    if not _re.match(r"^[\w.-]{1,64}$", run):
        return {"ok": False, "error": "invalid run id format"}, 400

    try:
        report_dir = dream_artifacts.resolve_run_dir(repo_path or "", date, run)
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400

    try:
        _list_data, item = load_item_for_promotion(report_dir, item_idx)
    except (LookupError, RuntimeError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 404

    candidate = {
        "title": item.get("title", ""),
        "hint": item.get("hint", ""),
        "kind": item.get("kind", ""),
        "source": "dream",
        "case_name": item.get("case_name") or None,
        "language": item.get("language", ""),
        "category": item.get("category", ""),
        "item_status": item.get("status", ""),
        "dream_ref": f"{date}/{run}/{item.get('item_dir_name', str(item_idx))}",
    }

    # Force LESSON_AUTO_ACTIVE off — candidate must never land in active/.
    _prev = getattr(_cfg, "LESSON_AUTO_ACTIVE", False)
    _cfg.LESSON_AUTO_ACTIVE = False
    try:
        record = _ls.save_candidate_lesson(
            candidate,
            source="dream",
            source_report=f"{date}/{run}",
            case_name=candidate["case_name"],
            title=f"Dream item: {item.get('title', 'untitled')}",
            summary=item.get("hint", ""),
            repo_path=repo_path,
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    finally:
        _cfg.LESSON_AUTO_ACTIVE = _prev

    return {
        "ok": True,
        "lesson_id": record.get("id"),
        "status": record.get("status"),
        "active_knowledge_allowed": record.get("active_knowledge_allowed", False),
        "scope": record.get("scope"),
    }


@app.route("/dream/create-proposal", methods=["POST"])
def dream_create_proposal_route():
    """Write a static proposal draft (proposal.md + proposal.json + item.json)
    to .agent/proposals/dream-<date>-<run>/<item_dir_name>/.

    No model call, no subprocess, no patch execution.
    """
    from core.dream_artifacts import resolve_run_dir, load_item_for_promotion
    import re as _re

    repo_path = request.form.get("repo_path", "").strip() or None
    date = request.form.get("date", "").strip()
    run = request.form.get("run", "").strip()
    item_idx_raw = request.form.get("item_idx", "").strip()

    if not item_idx_raw:
        return {"ok": False, "error": "item_idx is required"}, 400
    try:
        item_idx = int(item_idx_raw)
    except ValueError:
        return {"ok": False, "error": "item_idx must be an integer"}, 400

    if not date or not _re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        return {"ok": False, "error": "invalid date format"}, 400
    if not run or not _re.match(r"^[\w.-]{1,64}$", run):
        return {"ok": False, "error": "invalid run id format"}, 400

    try:
        report_dir = dream_artifacts.resolve_run_dir(repo_path or "", date, run)
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400

    try:
        _list_data, item = load_item_for_promotion(report_dir, item_idx)
    except (LookupError, RuntimeError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 404

    item_dir_name = item.get("item_dir_name") or dream_artifacts.slugify(
        f"{item_idx:02d}-{item.get('title', 'item')}"
    )
    run_label = f"dream-{date}-{run}"
    proposal_dir = _DREAM_PROPOSAL_ROOT / run_label / item_dir_name
    try:
        proposal_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        return {"ok": False, "error": f"could not create proposal dir: {e}"}, 500

    now_iso = datetime.now().isoformat(timespec="seconds")
    title = item.get("title", "untitled")
    hint = item.get("hint", "")
    status = item.get("status", "unknown")
    kind = item.get("kind", "?")
    blockers = item.get("patch_blockers") or []

    proposal_json = {
        "source": "dream",
        "date": date,
        "run_id": run,
        "item_idx": item_idx,
        "title": title,
        "hint": hint,
        "kind": kind,
        "status": status,
        "patch_blockers": blockers,
        "created_at": now_iso,
        "human_review_required": True,
    }

    item_json = {
        "case_name": item.get("case_name") or dream_artifacts.slugify(title),
        "title": title,
        "hint": hint,
        "source": "dream",
        "created_at": now_iso,
    }

    blocker_lines = []
    for b in blockers:
        code = b.get("code", "unknown")
        msg = b.get("message", "")
        hint_text = b.get("override_hint", "")
        blocker_lines.append(f"- `{code}`: {msg}")
        if hint_text:
            blocker_lines.append(f"  - *Override path*: {hint_text}")

    evidence_link = ""
    if item.get("item_dir_name"):
        evidence_link = f"\n**Evidence:** [{item['item_dir_name']}/](./{item['item_dir_name']}/)\n"

    proposal_md_lines = [
        f"# Proposal draft: {title}",
        "",
        "> **Human review required.** This is a static draft generated from a Dream",
        "> item. It has not been validated, patched, or reviewed by any model.",
        "> Review the content below and decide whether to create a candidate lesson.",
        "",
        f"**Kind:** {kind}  ",
        f"**Status at creation:** {status}  ",
        f"**Created:** {now_iso}",
        f"**Dream run:** {date} / {run}",
        "",
    ]
    if hint:
        proposal_md_lines += [
            "## Suspected root cause",
            "",
            hint,
            "",
        ]
    if blocker_lines:
        proposal_md_lines += ["## Why no patch", ""] + blocker_lines + [""]
    if evidence_link:
        proposal_md_lines.append(evidence_link)
    proposal_md_lines += [
        "## Next steps",
        "",
        "1. Review this draft.",
        "2. If the root cause is confirmed, click **Create candidate lesson** on the Dream item card.",
        "3. Promote the candidate lesson in the Memory → Lessons tab once it looks correct.",
        "",
    ]

    try:
        (proposal_dir / "proposal.json").write_text(
            json.dumps(proposal_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (proposal_dir / "item.json").write_text(
            json.dumps(item_json, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        (proposal_dir / "proposal.md").write_text(
            "\n".join(proposal_md_lines), encoding="utf-8"
        )
    except OSError as e:
        return {"ok": False, "error": f"write failed: {e}"}, 500

    return {"ok": True, "proposal_dir": str(proposal_dir)}


@app.route("/session/<session_id>")
def load_session(session_id):
    sessions = load_sessions()
    current = find_session(session_id)
    active_web_mode = _normalize_web_mode((current or {}).get("web_mode"))

    return render_template(
        "index.html",
        sessions=sessions,
        current=current,
        result=current.get("result", {}) if current else {},
        active_web_mode=active_web_mode,
    )

@app.route("/generate_candidates", methods=["POST"])
def generate_candidates():
    control_json = request.form["control"]
    repo_path = (request.form.get("repo_path") or "").strip() or None

    try:
        control = json.loads(control_json)
    except Exception:
        return {"error": "Invalid control JSON"}

    harness_block = _patch_generation_harness_block(repo_path, control)
    if harness_block:
        return harness_block

    prompts = [
        ("gemini_default", build_control_prompt(control, "Generate the best safe patch.", repo_path=repo_path)),
        ("gemini_minimal", build_control_prompt(control, "Generate the smallest possible patch.", repo_path=repo_path)),
        ("deepseek_review", build_control_prompt(control, "Generate an alternative conservative patch.", repo_path=repo_path)),
    ]

    candidates = []

    with ModelStatsScope() as model_calls:
        for name, prompt in prompts:
            if name == "deepseek_review":
                raw = run_deepseek_review(prompt)
            else:
                raw = run_gemini_request(prompt)

            patch = extract_json_block(raw)
            if patch:
                candidates.append({
                    "name": name,
                    "patch": patch,
                    "confidence": patch.get("confidence", 0.0),
                })

    return {
        "candidates": candidates,
        "usage": format_usage_report(model_calls),
    }

@app.route("/render_graph", methods=["POST"])
def render_graph():
    """Return Mermaid source for the program graph of a repo.

    Two modes:
      - mode=clean (default)  → applies should_show_node_clean / should_show_edge_clean
                                 to drop expr/call::/test nodes and noisy edge types.
                                 Best for understanding the architecture at a glance.
      - mode=debug            → emits everything raw (no filtering). Useful when
                                 hunting for why a particular node/edge isn't where
                                 you expect, or when you want the full picture.

    The frontend has two buttons (Clean / Debug) that pass the mode here.
    Form params:
      repo_path   (required)
      mode        clean | debug   (default: clean)
      show_tests  "1" / "true"    (clean mode only — include test files)
      max_edges   int             (default 150)
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path:
        return {"error": "No repo_path supplied."}, 400
    if not Path(repo_path).is_dir():
        return {"error": f"Path is not a directory: {repo_path}"}, 400

    mode = request.form.get("mode", "clean").strip().lower()
    if mode not in {"clean", "debug"}:
        mode = "clean"
    show_tests = request.form.get("show_tests", "").lower() in {"1", "true", "yes"}
    max_edges = int(request.form.get("max_edges", "150"))

    try:
        graph = build_graph_from_repo(repo_path)
    except Exception as e:
        return {"error": f"Failed to build graph: {e}"}, 500

    if not graph.edges:
        return {"error": "Graph is empty (no edges).", "mermaid": "graph TD\n  empty[\"(no edges)\"]"}

    # ---- Filtering pass (mode-aware) ----
    raw_edges = list(graph.edges)
    if mode == "clean":
        edges = [
            e for e in raw_edges
            if should_show_edge_clean(e.type)
            and should_show_node_clean(e.source, show_tests=show_tests)
            and should_show_node_clean(e.target, show_tests=show_tests)
        ]
    else:  # debug — keep everything
        edges = raw_edges

    filtered_count = len(edges)
    if filtered_count == 0:
        # Clean mode killed every edge — fall back to a hint instead of an empty render.
        return {
            "mermaid": "graph TD\n  empty[\"(clean filter removed all edges — try Debug)\"]",
            "mode": mode,
            "total_edges": len(raw_edges),
            "rendered_edges": 0,
            "truncated": False,
            "filtered_out": len(raw_edges),
        }

    # ---- Cap by hub degree if too many ----
    truncated = False
    if len(edges) > max_edges:
        deg = Counter()
        for e in edges:
            deg[e.source] += 1
            deg[e.target] += 1
        edges.sort(key=lambda e: deg[e.source] + deg[e.target], reverse=True)
        edges = edges[:max_edges]
        truncated = True

    # ---- Emit Mermaid ----
    lines = ["graph TD"]
    seen_nodes = set()

    for edge in edges:
        src = safe_id(edge.source)
        tgt = safe_id(edge.target)

        seen_nodes.add((src, edge.source))
        seen_nodes.add((tgt, edge.target))

        edge_label = escape_mermaid_label(edge.type)
        lines.append(f'  {src} -->|{edge_label}| {tgt}')

    label_lines = [
        f'  {sid}["{escape_mermaid_label(lbl)}"]'
        for sid, lbl in sorted(seen_nodes)
    ]
    
    mermaid = "\n".join([lines[0]] + label_lines + lines[1:])

    return {
        "mermaid": mermaid,
        "mode": mode,
        "show_tests": show_tests,
        "total_edges": len(raw_edges),
        "filtered_out": len(raw_edges) - filtered_count,
        "rendered_edges": len(edges),
        "truncated": truncated,
    }


@app.route("/graph/evidence_spread", methods=["GET", "POST"])
def graph_evidence_spread_route():
    """Read-only scope-aware evidence spread debug output for Graph/Chat."""
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path:
        return {"ok": False, "error": "No repo_path supplied."}, 400
    if not Path(repo_path).is_dir():
        return {"ok": False, "error": f"Path is not a directory: {repo_path}"}, 400

    query = request.values.get("query", "")
    target_node = request.values.get("target_node", "").strip() or None
    seed_nodes = _split_csv(request.values.get("seed_nodes"))
    try:
        top_n = int(request.values.get("top_n", "10"))
    except ValueError:
        top_n = 10

    try:
        graph = build_graph_from_repo(repo_path)
        return build_scope_evidence_spread_debug(
            graph,
            query,
            target_node=target_node,
            seed_nodes=seed_nodes,
            top_n=top_n,
        )
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to explain evidence spread: {type(e).__name__}: {e}",
        }, 500


@app.route("/graph/evidence_spread/export", methods=["POST"])
def graph_evidence_spread_export_route():
    """Export the scope-aware evidence spread explanation as a Markdown file.

    Read-only / explain-only. Writes under
    ``<.agent>/reports/evidence_spread/`` for the analyzed repo. No model
    calls, no patch generation, no ranking or weight mutation.
    """
    import re
    from datetime import datetime, timezone

    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path:
        return {"ok": False, "error": "No repo_path supplied."}, 400
    if not Path(repo_path).is_dir():
        return {"ok": False, "error": f"Path is not a directory: {repo_path}"}, 400

    query = request.values.get("query", "")
    target_node = request.values.get("target_node", "").strip() or None
    seed_nodes = _split_csv(request.values.get("seed_nodes"))
    try:
        top_n = int(request.values.get("top_n", "10"))
    except ValueError:
        top_n = 10

    try:
        graph = build_graph_from_repo(repo_path)
        result = build_scope_evidence_spread_debug(
            graph,
            query,
            target_node=target_node,
            seed_nodes=seed_nodes,
            top_n=top_n,
        )
        markdown = format_evidence_spread_markdown(result)

        reports_dir = (get_agent_dir(repo_path) / "reports" / "evidence_spread").resolve()
        reports_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        slug_source = (target_node or query or "report").strip()
        slug = re.sub(r"[^A-Za-z0-9._-]+", "_", slug_source).strip("_") or "report"
        slug = slug[:60]
        filename = f"evidence_spread_{timestamp}_{slug}.md"

        out_path = (reports_dir / filename).resolve()
        # Path containment guard — out_path must stay inside reports_dir.
        try:
            out_path.relative_to(reports_dir)
        except ValueError:
            return {
                "ok": False,
                "error": "Refused to write outside reports directory.",
            }, 400

        out_path.write_text(markdown, encoding="utf-8")

        preview = markdown if len(markdown) <= 4000 else markdown[:4000] + "\n..."

        return {
            "ok": True,
            "path": str(out_path),
            "filename": out_path.name,
            "markdown_preview": preview,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": f"Failed to export evidence spread: {type(e).__name__}: {e}",
        }, 500


@app.route("/vault_path", methods=["POST"])
def vault_path():
    """Resolve the on-disk path of the Obsidian graph vault for a given repo.

    Returns the absolute path so the frontend can either:
      - launch obsidian:// with a registered vault name (if user already
        registered the folder), or
      - show the path so the user can add it as a new vault.
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path:
        return {"error": "No repo_path supplied."}, 400


    vault = get_agent_dir(repo_path) / "Obsidian Graph" / "latest"

    if not vault.is_dir():
        return {
            "error": "Vault not generated yet. Run mode=full or retrieve at least once.",
            "expected_path": str(vault),
            "exists": False,
        }, 404

    return {
        "vault_path": str(vault),
        "vault_name": vault.parent.parent.name,  # the .agent/<repo_name>/ folder
        "exists": True,
    }


@app.route("/consolidate_memory", methods=["POST"])
def consolidate_memory_route():
    """Manual memory consolidation. Strict dedupe across memory_notes plus
    the web sessions log. Not wired into any pipeline — runs only when
    the user clicks the button in the UI.
    """
    raw_tag = (request.form.get("project_tag") or "").strip()
    project_tag = raw_tag or None

    sessions_paths = [
        WEB_DIR / "sessions.json",
        WEB_DIR / "sessions_log.json",
    ]

    try:
        stats = consolidate_all(
            project_tag=project_tag,
            sessions_paths=sessions_paths,
        )
    except Exception as e:
        import traceback
        return {
            "success": False,
            "error": f"{type(e).__name__}: {e}",
            "traceback": traceback.format_exc(),
        }, 500

    sessions_total = sum(s.get("removed", 0) for s in stats.get("sessions", []))
    test_logs = stats.get("test_logs") or {}
    return {
        "success": True,
        "memory_notes_removed": stats["memory_notes_removed"],
        "sessions_removed": sessions_total,
        "sessions": stats["sessions"],
        "test_logs_removed": test_logs.get("dirs_removed", 0),
        "test_logs": test_logs,
        "project_tag": stats["project_tag"],
    }


# ============================================================
# Phase 6.1 — Lesson management routes
# ============================================================
# Backed by core/lesson_store.py. These routes are read/write JSON only:
# no patch flow, no retrieval helper, no auto-creation. The Memory tab UI
# is the sole consumer today.

def _lesson_repo_path(raw: str | None) -> str | None:
    """Normalize an optional repo_path argument. Empty string => None."""
    if not raw:
        return None
    value = raw.strip()
    return value or None


_MAX_LESSON_PROPOSAL_BYTES = 512_000


def _path_is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except (OSError, ValueError):
        return False


def _lesson_proposal_roots(repo_path: str | None) -> list[Path]:
    roots = [
        PROJECT_ROOT / ".agent" / "proposals",
        get_agent_dir(None) / "proposals",
    ]
    if repo_path:
        roots.append(get_agent_dir(repo_path) / "proposals")

    out: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        try:
            resolved = root.resolve()
        except OSError:
            resolved = root
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(resolved)
    return out


def _find_lesson_record(
    lesson_id: str,
    repo_path: str | None,
    *,
    scope: str | None = None,
    repo_scope_id: str | None = None,
) -> dict:
    for record in lesson_store.list_lessons(
        repo_path=repo_path,
        scope=scope,
        repo_scope_id=repo_scope_id,
    ):
        if record.get("id") == lesson_id:
            return record
    raise LookupError(f"lesson not found: {lesson_id}")


def _lesson_scope_arg(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value or None


def _lesson_repo_scope_id_arg(raw: str | None) -> str | None:
    value = (raw or "").strip()
    return value or None


def _resolve_lesson_proposal_md(record: dict, repo_path: str | None) -> Path:
    raw = record.get("source_report")
    if not isinstance(raw, str) or not raw.strip():
        raise FileNotFoundError("lesson has no source_report")

    source_report = Path(raw.strip())
    if not source_report.is_absolute():
        source_report = PROJECT_ROOT / source_report
    try:
        proposal_dir = source_report.resolve()
    except OSError as e:
        raise FileNotFoundError("source_report path cannot be resolved") from e

    allowed_roots = _lesson_proposal_roots(repo_path)
    if not any(_path_is_inside(proposal_dir, root) for root in allowed_roots):
        raise ValueError("lesson source_report is outside allowed proposal roots")

    proposal_md = (proposal_dir / "proposal.md").resolve()
    if not _path_is_inside(proposal_md, proposal_dir):
        raise ValueError("proposal path escapes source_report")
    if not proposal_md.is_file():
        raise FileNotFoundError("proposal.md not found for this lesson")
    return proposal_md


@app.route("/lessons/list", methods=["GET"])
def lessons_list_route():
    """List lessons for the Memory tab.

    Query params:
      - repo_path (optional): includes current repo-scoped lessons plus global.
      - status (optional): one of candidate | active | blocked.
    """
    repo_path = _lesson_repo_path(request.values.get("repo_path"))
    status = (request.values.get("status") or "").strip() or None
    scope = _lesson_scope_arg(request.values.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(request.values.get("repo_scope_id"))
    include_global = (request.values.get("include_global") or "true").lower() != "false"
    if status is not None and status not in lesson_store.LESSON_STATUSES:
        return {"ok": False, "error": f"invalid status: {status!r}"}, 400
    try:
        lessons = lesson_store.list_lessons(
            status=status,
            repo_path=repo_path,
            include_global=include_global,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"failed to list lessons: {type(e).__name__}"}, 500
    return {"ok": True, "lessons": lessons}


@app.route("/lessons/proposal", methods=["GET"])
def lessons_proposal_route():
    """Read proposal.md for a lesson created from proposal artifacts.

    Query params:
      - repo_path (optional): current repo scope for repo lessons.
      - lesson_id: lesson record id.
    """
    repo_path = _lesson_repo_path(request.values.get("repo_path"))
    scope = _lesson_scope_arg(request.values.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(request.values.get("repo_scope_id"))
    lesson_id = (request.values.get("lesson_id") or "").strip()
    if not lesson_id:
        return {"ok": False, "error": "lesson_id is required"}, 400

    try:
        record = _find_lesson_record(
            lesson_id,
            repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
        proposal_md = _resolve_lesson_proposal_md(record, repo_path)
        if proposal_md.stat().st_size > _MAX_LESSON_PROPOSAL_BYTES:
            return {"ok": False, "error": "proposal.md is too large to display"}, 413
        content = proposal_md.read_text(encoding="utf-8", errors="replace")
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"failed to read proposal: {type(e).__name__}"}, 500

    return {
        "ok": True,
        "lesson_id": lesson_id,
        "title": record.get("title") or "Untitled lesson",
        "proposal_path": str(proposal_md),
        "content": content,
    }


@app.route("/lessons/promote", methods=["POST"])
def lessons_promote_route():
    """Move a candidate lesson to active. JSON body: {repo_path?, lesson_id, scope?, repo_scope_id?}."""
    payload = request.get_json(silent=True) or {}
    repo_path = _lesson_repo_path(payload.get("repo_path"))
    scope = _lesson_scope_arg(payload.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(payload.get("repo_scope_id"))
    lesson_id = (payload.get("lesson_id") or "").strip()
    if not lesson_id:
        return {"ok": False, "error": "lesson_id is required"}, 400
    try:
        record = lesson_store.promote_lesson(
            lesson_id,
            repo_path=repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"failed to promote lesson: {type(e).__name__}"}, 500
    return {"ok": True, "lesson": record}


@app.route("/lessons/block", methods=["POST"])
def lessons_block_route():
    """Move any lesson to blocked. JSON body: {repo_path?, lesson_id, scope?, repo_scope_id?}."""
    payload = request.get_json(silent=True) or {}
    repo_path = _lesson_repo_path(payload.get("repo_path"))
    scope = _lesson_scope_arg(payload.get("scope"))
    repo_scope_id = _lesson_repo_scope_id_arg(payload.get("repo_scope_id"))
    lesson_id = (payload.get("lesson_id") or "").strip()
    if not lesson_id:
        return {"ok": False, "error": "lesson_id is required"}, 400
    try:
        record = lesson_store.block_lesson(
            lesson_id,
            repo_path=repo_path,
            scope=scope,
            repo_scope_id=repo_scope_id,
        )
    except LookupError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"failed to block lesson: {type(e).__name__}"}, 500
    return {"ok": True, "lesson": record}


# ---------------------------------------------------------------------------
# Phase 5 Polish — Proposal browser + promote-to-lesson surfaces.
# Lifts scripts/create_lesson_from_proposal.py into a one-click button on the
# Memory tab so users don't need a terminal to turn a validated proposal into
# a lesson candidate. The lesson_quality gate is the only auto-promotion
# decision; the user must still click "Promote" on the lesson card to move
# the resulting candidate to active/.
# ---------------------------------------------------------------------------

@app.route("/proposals/view", methods=["GET"])
def proposals_view_route():
    """Read proposal.md for a proposal directory under .agent/proposals/.

    Query param: proposal_dir — path under .agent/proposals/ (path-guarded).
    """
    from scripts.create_lesson_from_proposal import _resolve_proposal_dir
    raw = (request.values.get("proposal_dir") or "").strip()
    try:
        proposal_dir = _resolve_proposal_dir(raw)
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    proposal_md = proposal_dir / "proposal.md"
    if not proposal_md.is_file():
        return {"ok": False, "error": "proposal.md not found"}, 404
    # Cap to the same size limit as the lesson-side reader.
    try:
        if proposal_md.stat().st_size > 200_000:
            return {"ok": False, "error": "proposal.md is too large to display"}, 413
        content = proposal_md.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"ok": False, "error": f"failed to read proposal: {type(e).__name__}"}, 500
    return {
        "ok": True,
        "proposal_path": str(proposal_md),
        "content": content,
    }


@app.route("/proposals/list", methods=["GET"])
def proposals_list_route():
    """List recent .agent/proposals/<run>/<item>/ artifacts (path-guarded)."""
    from scripts.run_patch_proposal_queue import PROPOSAL_ROOT
    if not PROPOSAL_ROOT.is_dir():
        return {"runs": []}
    runs = []
    try:
        run_dirs = [d for d in PROPOSAL_ROOT.iterdir() if d.is_dir()]
    except OSError as e:
        return {"runs": [], "error": f"could not read proposal root: {e}"}, 500
    run_dirs.sort(reverse=True)
    for run_dir in run_dirs[:20]:
        items = []
        try:
            item_dirs = sorted(d for d in run_dir.iterdir() if d.is_dir())
        except OSError:
            continue
        for item_dir in item_dirs:
            item_json = item_dir / "item.json"
            validation_json = item_dir / "validation.json"
            apply_json = item_dir / "apply_result.json"
            try:
                item = json.loads(item_json.read_text(encoding="utf-8")) if item_json.is_file() else {}
            except Exception:
                item = {}
            try:
                validation = json.loads(validation_json.read_text(encoding="utf-8")) if validation_json.is_file() else {}
            except Exception:
                validation = {}
            try:
                apply_result = json.loads(apply_json.read_text(encoding="utf-8")) if apply_json.is_file() else {}
            except Exception:
                apply_result = {}
            items.append({
                "proposal_dir": str(item_dir),
                "rel_dir": item_dir.relative_to(PROPOSAL_ROOT).as_posix(),
                "case_name": item.get("case_name"),
                "validation_ok": validation.get("validation_ok"),
                "apply_success": apply_result.get("success"),
                "has_proposal_md": (item_dir / "proposal.md").is_file(),
            })
        runs.append({"run_id": run_dir.name, "items": items})
    return {"runs": runs}


@app.route("/proposals/promote", methods=["POST"])
def proposals_promote_route():
    """Wrap scripts/create_lesson_from_proposal.create_lesson_from_proposal.

    Form fields:
      proposal_dir   — path under .agent/proposals/ (path-traversal guarded)
      allow_failed   — "true" to override the validation/apply gate
      repo_path      — optional analyzed repo path; repo-scopes when supplied
    """
    from scripts.create_lesson_from_proposal import (
        _resolve_proposal_dir,
        create_lesson_from_proposal,
    )
    raw = request.form.get("proposal_dir", "")
    allow_failed = (request.form.get("allow_failed") or "").lower() == "true"
    repo_path = (request.form.get("repo_path") or "").strip() or None
    try:
        proposal_dir = _resolve_proposal_dir(raw)
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    try:
        lesson = create_lesson_from_proposal(
            proposal_dir,
            repo_path=repo_path,
            allow_failed=allow_failed,
        )
    except RuntimeError as e:
        # Refused because validation/apply failed and allow_failed=False.
        return {"ok": False, "refused": True, "error": str(e)}, 200
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    evaluation = lesson.get("evaluation") or {}
    return {
        "ok": True,
        "lesson_id": lesson.get("id"),
        "status": lesson.get("status"),
        "scope": lesson.get("scope"),
        "repo_scope_id": lesson.get("repo_scope_id"),
        "active_knowledge_allowed": lesson.get("active_knowledge_allowed"),
        "promotion": evaluation.get("promotion"),
    }


# ---------------------------------------------------------------------------
# Phase 6.4e — gated "auto candidate creation" operator actions.
# Backed by core/lesson_auto_candidates.py. These are explicit, controlled
# triggers (the helper is an exact no-op unless enabled=True is passed, which
# only happens here). They create CANDIDATE lessons only; promotion to active
# stays a manual Memory-tab action and lesson_quality remains the routing
# authority. They never run benchmarks/models/patch executors/validation, never
# enable retrieval, and never mutate the source artifacts.
# ---------------------------------------------------------------------------

def _truthy_form(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


@app.route("/lessons/create-candidate-from-proposal", methods=["POST"])
def lessons_create_candidate_from_proposal_route():
    """Create a lesson candidate from a proposal artifact (uniform result).

    Form/JSON: proposal_dir (required), repo_path?, global_candidate?,
    include_failed?. Returns {ok, result} where result carries
    status/scope/source_key/reason/active_knowledge_allowed.
    """
    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_proposal

    payload = request.get_json(silent=True) or request.form
    proposal_dir = (payload.get("proposal_dir") or "").strip()
    if not proposal_dir:
        return {"ok": False, "error": "proposal_dir is required"}, 400
    repo_path = (payload.get("repo_path") or "").strip() or None
    try:
        result = maybe_create_lesson_candidate_from_proposal(
            proposal_dir,
            repo_path=repo_path,
            enabled=True,
            global_candidate=_truthy_form(payload.get("global_candidate")),
            include_failed=_truthy_form(payload.get("include_failed")),
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "result": result}


@app.route("/lessons/create-candidate-from-dream", methods=["POST"])
def lessons_create_candidate_from_dream_route():
    """Create a lesson candidate from a Dream ready_to_apply item (uniform result).

    Form/JSON: item_dir (required; may be a relative date/run/item ref resolved
    against the repo's dreams root), repo_path (required for repo scope),
    global_candidate?, include_failed?.
    """
    from core.lesson_auto_candidates import maybe_create_lesson_candidate_from_dream_item

    payload = request.get_json(silent=True) or request.form
    item_dir = (payload.get("item_dir") or payload.get("dream_item_dir") or "").strip()
    if not item_dir:
        return {"ok": False, "error": "item_dir is required"}, 400
    repo_path = (payload.get("repo_path") or "").strip() or None
    try:
        result = maybe_create_lesson_candidate_from_dream_item(
            item_dir,
            repo_path=repo_path,
            enabled=True,
            global_candidate=_truthy_form(payload.get("global_candidate")),
            include_failed=_truthy_form(payload.get("include_failed")),
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "result": result}


@app.route("/upload_folder", methods=["POST"])
def upload_folder():
    files = request.files.getlist("files")

    if not files:
        return {"error": "No files uploaded"}, 400

    top_folder = Path(files[0].filename).parts[0] if files[0].filename else "repo"

    temp_dir = tempfile.mkdtemp()
    repo_path = Path(temp_dir) / top_folder
    repo_path.mkdir(parents=True, exist_ok=True)
    repo_root = repo_path.resolve()

    saved = 0
    skipped = []

    for f in files:
        raw_name = (f.filename or "").replace("\\", "/")
        rel = Path(raw_name)

        # Strip leading top folder to avoid /repo/repo/...
        if rel.parts and rel.parts[0] == top_folder:
            rel = Path(*rel.parts[1:]) if len(rel.parts) > 1 else Path(rel.name)

        # Reject empty / dangerous names
        if not rel.parts or any(part in {"", ".", ".."} for part in rel.parts):
            skipped.append(raw_name)
            continue

        # Skip blacklisted folders/files before saving
        if any(part in FOLDER_BLACKLIST for part in rel.parts):
            skipped.append(raw_name)
            continue

        # Skip env/secrets
        if rel.name == ".env" or rel.name.startswith(".env."):
            skipped.append(raw_name)
            continue

        target = (repo_path / rel).resolve()

        # Path traversal guard
        try:
            target.relative_to(repo_root)
        except ValueError:
            skipped.append(raw_name)
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        f.save(target)
        saved += 1

    inventory = inspect_repo_inventory(str(repo_path))

    if inventory["indexable_count"] == 0:
        return {
            "error": "Upload created a repo with 0 indexable files.",
            "repo_path": str(repo_path),
            "saved_raw_files": saved,
            "skipped": skipped[:20],
            **inventory,
        }, 400

    project_tag = build_project_tag(str(repo_path))

    return {
        "repo_path": str(repo_path),
        "project_tag": project_tag,
        "saved_raw_files": saved,
        "skipped": skipped[:20],
        **inventory,
    }

# --- Phase 7.1: Mayor Mode handoff routes ---------------------------------
from core import handoff_notes as _handoff_notes
from core import handoff_composer as _handoff_composer
from scripts import run_subagent_handoff as _handoff_runner


def _split_csv(value: str | None) -> list[str]:
    if not value:
        return []
    out: list[str] = []
    for chunk in value.split(","):
        s = chunk.strip()
        if s and s not in out:
            out.append(s)
    return out


@app.route("/handoffs/compose", methods=["POST"])
def handoffs_compose_route():
    if request.is_json:
        payload = request.get_json(silent=True)
        data = payload if isinstance(payload, dict) else {}
    else:
        data = request.form.to_dict()

    goal_brief = data.get("goal_brief") if isinstance(data.get("goal_brief"), dict) else {}
    result = _handoff_composer.compose_handoff_draft(
        goal_brief=goal_brief,
        repo_path=(str(data.get("repo_path") or "").strip() or None),
        allowed_files=data.get("allowed_files"),
        validation_command=(str(data.get("validation_command") or "").strip() or None),
        title=data.get("title"),
        task_summary=data.get("task_summary"),
        forbidden_files=data.get("forbidden_files"),
    )
    draft = result["draft"]
    return {
        "ok": True,
        "draft": draft,
        "markdown": _handoff_composer.render_handoff_draft_markdown(draft),
    }


@app.route("/handoffs/create", methods=["POST"])
def handoffs_create_route():
    try:
        result = _handoff_notes.create_handoff_note(
            title=request.form.get("title", ""),
            intended_worker=request.form.get("intended_worker", ""),
            task_type=request.form.get("task_type", ""),
            repo_path=(request.form.get("repo_path") or "").strip() or None,
            allowed_files=_split_csv(request.form.get("allowed_files")),
            forbidden_files=_split_csv(request.form.get("forbidden_files")),
            validation_command=(request.form.get("validation_command") or "").strip() or None,
            context_summary=request.form.get("context_summary", ""),
            expected_output=request.form.get("expected_output", ""),
            extra_safety_rules=_split_csv(request.form.get("extra_safety_rules")),
        )
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "handoff_id": Path(result["path"]).name,
        "handoff_path": result["path"],
        "slug": result["slug"],
        "meta": result["meta"],
    }


@app.route("/handoffs/list", methods=["GET"])
def handoffs_list_route():
    include_archived = (request.values.get("include_archived") or "").lower() == "true"
    try:
        notes = _handoff_notes.list_handoff_notes(include_archived=include_archived)
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "handoffs": notes}


@app.route("/handoffs/run", methods=["POST"])
def handoffs_run_route():
    # Accept handoff_id (filename) or handoff_path (absolute) for backward compat.
    handoff_id = (request.form.get("handoff_id") or "").strip()
    handoff_path = (request.form.get("handoff_path") or "").strip()
    ref = handoff_id or handoff_path
    if not ref:
        return {"ok": False, "error": "handoff_id or handoff_path is required"}, 400
    allow_run = (request.form.get("allow_run") or "").lower() == "true"
    worker = (request.form.get("worker") or "").strip() or None
    worker_command = (request.form.get("worker_command") or "").strip() or None
    try:
        timeout_sec = int(request.form.get("timeout_sec") or _handoff_runner.DEFAULT_TIMEOUT_SEC)
    except ValueError:
        return {"ok": False, "error": "timeout_sec must be an integer"}, 400
    try:
        resolved = _handoff_notes.resolve_handoff_note(ref)
        result = _handoff_runner.run_handoff(
            note_path=str(resolved),
            allow_run=allow_run,
            worker_override=worker,
            worker_command_override=worker_command,
            timeout_sec=timeout_sec,
        )
    except (ValueError, FileNotFoundError) as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "dry_run": result.get("dry_run"),
        "artifact_dir": result.get("artifact_dir"),
        "exit_code": result.get("exit_code"),
        "timed_out": result.get("timed_out"),
        "error": result.get("error"),
        "run": result,
    }


@app.route("/worker-runs/list", methods=["GET"])
def worker_runs_list_route():
    """Phase 7.2: delegate to core.worker_runs.list_worker_runs.

    The response shape is a strict superset of the Phase 7.1 listing
    (legacy fields preserved + run_id, handoff_title, has_proposal_md,
    has_patch_plan_json, has_handoff_md, has_worker_run_json added).
    """
    from core import worker_runs as _worker_runs
    try:
        runs = _worker_runs.list_worker_runs(
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "runs": runs}


@app.route("/worker-runs/view", methods=["GET"])
def worker_runs_view_route():
    """Phase 7.2: full detail for a single worker run.

    Accepts ?run_id=<dir name> (relative to .agent/worker_runs/) or
    ?path=<absolute or relative path>. Path-traversal guarded.
    """
    from core import worker_runs as _worker_runs
    run_id = (request.values.get("run_id") or "").strip()
    path = (request.values.get("path") or "").strip()
    if not run_id and not path:
        return {"ok": False, "error": "run_id or path is required"}, 400
    target = path or run_id
    try:
        run = _worker_runs.read_worker_run(
            target,
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 404
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {"ok": True, "run": run}


@app.route("/proposals/validate", methods=["POST"])
def proposals_validate_route():
    """Phase 7.2.1: revalidate an imported worker proposal's patch_plan.json
    in a temp clone of repo_path. Writes apply_result.json +
    validation.json + validation_output.txt into the proposal_dir. Never
    modifies the real repo or repo_path.
    """
    from core import worker_runs as _worker_runs
    proposal_dir = (request.form.get("proposal_dir") or "").strip()
    repo_path = (request.form.get("repo_path") or "").strip()
    if not proposal_dir:
        return {"ok": False, "error": "proposal_dir is required"}, 400
    if not repo_path:
        return {"ok": False, "error": "repo_path is required"}, 400
    try:
        timeout_sec = int(request.form.get("validation_timeout_sec") or 60)
    except ValueError:
        return {"ok": False, "error": "validation_timeout_sec must be int"}, 400
    try:
        result = _worker_runs.validate_imported_worker_proposal(
            proposal_dir,
            repo_path,
            validation_timeout_sec=timeout_sec,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 400
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return result


@app.route("/worker-runs/import", methods=["POST"])
def worker_runs_import_route():
    """Phase 7.2: import a complete (non-dry-run) worker run as a proposal.

    Refuses dry-run / incomplete runs and any path that escapes
    .agent/worker_runs/. Never modifies the real repo.
    """
    from core import worker_runs as _worker_runs
    run_id = (request.form.get("run_id") or "").strip()
    path = (request.form.get("path") or "").strip()
    if not run_id and not path:
        return {"ok": False, "error": "run_id or path is required"}, 400
    target = path or run_id
    try:
        result = _worker_runs.import_worker_run_as_proposal(
            target,
            worker_runs_root=_handoff_runner.WORKER_RUNS_ROOT,
        )
    except FileNotFoundError as e:
        return {"ok": False, "error": str(e)}, 400
    except ValueError as e:
        return {"ok": False, "error": str(e)}, 400
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}, 500
    return {
        "ok": True,
        "proposal_dir": result["proposal_dir"],
        "source_run_id": result["source_run_id"],
        "item": result["item"],
    }

@app.route("/local_critique", methods=["POST"])
def local_critique():
    import os
    from agents.ollama_client import run_local_critique

    if os.getenv("OLLAMA_ENABLED", "false").lower() in {"0", "false", "no"}:
        return {"ok": False, "error": "Ollama is disabled — set OLLAMA_ENABLED=true in .env to use local critique"}

    patch_text = request.form.get("patch", "").strip()
    if not patch_text:
        return {"ok": False, "error": "No patch provided — generate a patch first"}

    query = request.form.get("query", "")
    context = request.form.get("context", "")
    preflight = request.form.get("preflight", "")

    prompt_parts = []
    if query:
        prompt_parts.append(f"User request:\n{query}")
    if context:
        prompt_parts.append(f"Context snippets:\n{context}")
    if preflight:
        prompt_parts.append(f"Preflight output:\n{preflight}")
    prompt_parts.append(f"Patch JSON:\n{patch_text}")

    result = run_local_critique("\n\n".join(prompt_parts))

    if "error" in result:
        return {"ok": False, "error": result["error"]}

    show_thought = os.getenv("SHOW_LOCAL_THOUGHT", "false").lower() not in {"0", "false", "no"}
    response: dict = {"ok": True, "critic": result["critic"]}
    if show_thought and result.get("thought"):
        response["thought"] = result["thought"]
    return response


@app.route("/new")
def new_session():
    return redirect(url_for("index", web_mode=_normalize_web_mode(request.values.get("web_mode"))))


_help_cache: dict[str, str] = {}

@app.route('/help')
def help_route():
    readme_path = PROJECT_ROOT / 'README.md'
    cache_key = str(readme_path)
    if cache_key not in _help_cache:
        if readme_path.exists():
            raw = readme_path.read_text(encoding='utf-8')
            _help_cache[cache_key] = _markdown_lib.markdown(
                raw,
                extensions=['fenced_code', 'tables', 'toc'],
            )
        else:
            _help_cache[cache_key] = '<p>README.md not found.</p>'
    return _help_cache[cache_key], 200, {'Content-Type': 'text/html; charset=utf-8'}


if __name__ == "__main__":
    from web.runner import run_web_app

    run_web_app(app, debug=True)


# === Phase 12.13f: explain-only graph explainability debug view ===
@app.route("/graph/explainability/view", methods=["GET"])
def graph_explainability_view_route():
    """Read-only debug view of the explain-only report sections.

    Renders already-computed evidence-spread Markdown (which carries the
    Evidence Confidence and Graph Attraction / Repulsion sections) plus a
    Related Notes / Lessons section derived from the same spread nodes. It makes
    no model/API calls, writes nothing, and changes no ranking - explain-only.
    """
    repo_path = (request.values.get("repo_path") or "").strip()
    if not repo_path:
        return {"ok": False, "error": "repo_path is required"}, 400
    if not Path(repo_path).is_dir():
        return {"ok": False, "error": f"Path is not a directory: {repo_path}"}, 400

    from core.related_notes import (
        explain_related_notes,
        format_related_notes_markdown,
    )

    query = (request.values.get("query") or "").strip()
    target_node = (request.values.get("target_node") or "").strip()
    try:
        top_n = int((request.values.get("top_n") or "10").strip() or "10")
    except (TypeError, ValueError):
        top_n = 10

    result = build_scope_evidence_spread_debug(
        build_graph_from_repo(repo_path),
        query,
        target_node=target_node or None,
        top_n=top_n,
    )
    spread_md = format_evidence_spread_markdown(result)

    # Derive note-like records from the already-computed spread nodes so the
    # Related Notes layer has explain-only input without any DB/model access.
    derived_notes = [
        {
            "note_id": node.get("node_id"),
            "title": node.get("node_id"),
            "source_type": "graph",
            "text": "; ".join(node.get("reasons") or []),
            "path": str(node.get("node_id") or "").split("::", 1)[0],
        }
        for node in (result.get("nodes") or [])
    ]
    related_items = explain_related_notes(
        derived_notes,
        query=query,
        target_node=target_node,
        target_path="",
    )
    related_md = format_related_notes_markdown(related_items)

    # Phase 12.14b: explain-only Memory Temperature view over the same derived
    # notes. Visibility only - no retrieval, ranking, or prompt behavior.
    temperature_md = format_memory_temperature_section(derived_notes)
    shadow_md = format_memory_temperature_shadow_section(derived_notes)

    markdown_text = (
        spread_md.rstrip()
        + "\n\n## Related Notes / Lessons\n\n"
        + related_md.strip()
        + "\n\n"
        + temperature_md.strip()
        + "\n\n"
        + shadow_md.strip()
        + "\n"
    )

    response = {
        "ok": True,
        "markdown": markdown_text,
        "sections": [
            "Evidence Confidence",
            "Graph Attraction / Repulsion",
            "Related Notes / Lessons",
            "Memory Temperature",
            "Memory Temperature Shadow Retrieval",
        ],
    }
    if request.values.get("as", "").strip().lower() == "html":
        try:
            import markdown as _md_render

            response["html"] = _md_render.markdown(
                markdown_text,
                extensions=["fenced_code", "tables", "toc"],
            )
        except Exception as exc:  # noqa: BLE001
            response["html"] = ""
            response["html_error"] = f"{type(exc).__name__}: {exc}"
    return response
