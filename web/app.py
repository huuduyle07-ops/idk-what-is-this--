from __future__ import annotations

import json, sys, shutil, tempfile
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
from core.executor import Executor
from agents.gemini_client import run_gemini_request
from core.json_utils import extract_json_block
from core.validation_command import get_default_validation_command
from web.runner import run_agent_web
from agents.deepseek_client import run_deepseek_review
from config import LANGUAGE_MAP, get_agent_dir, FOLDER_BLACKLIST
from core.project_tag import build_project_tag, fingerprint_repo  # re-exported for legacy callers
from core.repo_librarian import inspect_repo_inventory
from core.sleeping_consultant import (
    run_overnight,
    start_overnight_async,
    get_run_state,
)
from core import dream_artifacts
from database.memory_consolidator import consolidate_all
from policy.decision_helper import normalize_patch_style
from graph.builder import build_graph_from_repo
from graph.exporter import safe_id, escape_mermaid_label

def _detect_patch_language(patch: dict) -> str:
    """Best-effort language inference from the target file extension."""
    target = patch.get("relative_path") or patch.get("file") or ""
    ext = Path(target).suffix.lower()
    return LANGUAGE_MAP.get(ext, "unknown")
app = Flask(__name__)

WEB_DIR = Path(__file__).parent
SESSION_FILE = WEB_DIR / "sessions.json"
BACKUP_DIR = WEB_DIR / "backups"
BACKUP_DIR.mkdir(exist_ok=True)

def load_sessions() -> list[dict]:
    if not SESSION_FILE.exists():
        return []

    try:
        return json.loads(SESSION_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_sessions(sessions: list[dict]) -> None:
    SESSION_FILE.write_text(
        json.dumps(sessions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def save_session(
    query: str,
    repo_path: str,
    mode: str,
    result: dict,
    project_tag: str,
    patch_style: str = "safe_minimal",
    ignore_repo_dna: bool = False,
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
    }

    sessions.insert(0, session)
    save_sessions(sessions[:30])

    return session

def find_session(session_id: str) -> dict | None:
    for s in load_sessions():
        if s.get("id") == session_id:
            return s
    return None

def _empty_result(answer: str = "") -> dict:
    return {
        "answer": answer,
        "context": "",
        "graph": "",
        "state": "",
        "patch": "",
        "validation": "",
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

    if request.method == "POST":
        query = request.form.get("query", "").strip()
        repo_path = request.form.get("repo_path", "").strip()
        mode = request.form.get("mode", "retrieve")
        agent_mode = request.form.get("agent_mode", "reviewer")
        user_tag = request.form.get("project_tag")
        # Vibecoding style — picks how aggressive/creative patches may be.
        # Falls back to safe_minimal if the form omits it (backward compat).
        
        patch_style = normalize_patch_style(request.form.get("patch_style"))
        ignore_repo_dna = request.form.get("ignore_repo_dna") in {"1", "on", "true", "yes"}

        if not query or not repo_path:
            error = "Both 'query' and 'repo_path' are required."
            result = _empty_result(error)
        else:
            # Compute the canonical tag once per real submission.
            project_tag = build_project_tag(repo_path, user_tag)
            final_tag = project_tag

            try:
                result, final_tag = _run_mode(
                    mode=mode,
                    query=query,
                    repo_path=repo_path,
                    agent_mode=agent_mode,
                    project_tag=project_tag,
                    patch_style=patch_style,
                    ignore_repo_dna=ignore_repo_dna,
                )
            except Exception as e:
                import traceback
                tb = traceback.format_exc()
                print(f"❌ Pipeline error in mode={mode}:\n{tb}")
                error = f"Pipeline error: {type(e).__name__}: {e}"
                result = _empty_result(error)
                result["validation"] = tb  # show traceback in the validation tab

            current = save_session(
                query, repo_path, mode, result, final_tag, patch_style, ignore_repo_dna
            )
            sessions = load_sessions()

    return render_template(
        "index.html",
        sessions=sessions,
        current=current,
        result=result,
        error=error,
    )

@app.route("/generate_patch", methods=["POST"])
def generate_patch():
    repo_path = request.form.get("repo_path", "")
    control_json = request.form.get("control", "")

    try:
        control = json.loads(control_json)
    except Exception:
        return {"error": "Invalid control JSON"}

    prompt = build_control_prompt(control, "Generate patch")

    response = run_gemini_request(prompt)
    patch = extract_json_block(response)

    if not patch:
        return {"error": "Failed to generate patch"}

    return {
        "patch": json.dumps(patch, indent=2, ensure_ascii=False)
    }

@app.route("/apply_patch", methods=["POST"])
def apply_patch():
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form["patch"]
    apply_policy = request.form.get("apply_policy", "ask")
    MAX_BACKUPS = 7

    # Server-side enforcement of "plan only" — never apply.
    if apply_policy == "plan":
        return {
            "success": False,
            "message": "Plan-only policy: server refused to apply.",
            "diff": "",
            "validation": "",
        }

    try:
        parsed = json.loads(patch_json)

        if isinstance(parsed.get("patch_candidate"), dict):
            patch = parsed["patch_candidate"]
        else:
            patch = parsed

        if "patched_snippet" not in patch:
            return {
                "success": False,
                "message": "No patch_candidate found. Expected top-level patch_candidate or direct patch object.",
                "diff": "",
                "validation": "",
            }
    except Exception:
        return {"error": "Invalid patch JSON"}

    target_file = patch.get("relative_path") or patch.get("file")
    if not target_file:
        return {"error": "Patch missing target file"}

    repo_root = Path(repo_path).resolve()
    file_path = (repo_root / target_file).resolve()
    try:
        file_path.relative_to(repo_root)
    except ValueError:
        return {
            "success": False,
        "message": "Unsafe patch target: file is outside repo.",
        "diff": "",
        "validation": "",
    }, 400
    safe_path = target_file.replace("/", "_").replace("\\", "_")
    backup_path = BACKUP_DIR / f"{safe_path}_{datetime.now().timestamp()}.bak"

    if file_path.exists():
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

    backups = sorted(BACKUP_DIR.glob(f"{safe_path}_*.bak"), reverse=True)
    for old in backups[MAX_BACKUPS:]:
        old.unlink()

    executor = Executor(
        project_root=repo_path,
        rollback_on_validation_fail=True,
    )

    lang = _detect_patch_language(patch)
    validation_command = get_default_validation_command(lang, repo_root)
    
    result = executor.run(
        patch=patch,
        language=lang,
        validation_command=validation_command,
    )

    return {
        "message": result.message,
        "diff": result.diff,
        "validation": result.validation_output,
        "success": result.success,
    }

@app.route("/test_patch_plan", methods=["POST"])
def test_patch_plan():
    """Dry-run a multi-op patch_plan in a temp clone, then validate."""
    from patching.patch_plan_executor import apply_patch_plan

    repo_path = request.form.get("repo_path", "")
    patch_json = request.form.get("patch", "")
    patch_style = request.form.get("patch_style", "")

    if patch_style == "safe_minimal":
        return {
            "success": False,
            "message": "safe_minimal mode forbids patch_plan. Switch to balanced or vibe to test multi-file changes.",
            "diff": "",
            "validation": "",
        }

    try:
        patch = json.loads(patch_json)
    except Exception:
        return {"error": "Invalid patch JSON"}

    plan = patch.get("patch_plan")
    if not isinstance(plan, list) or not plan:
        return {
            "success": False,
            "message": "No patch_plan found in payload.",
            "diff": "",
            "validation": "",
        }

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_repo = Path(temp_dir) / "repo"
        shutil.copytree(
            repo_path,
            temp_repo,
            ignore=shutil.ignore_patterns(
                "target",
                ".git",
                ".agent",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                "dist",
                "build",
                ".venv",
                "venv",
                ".env",
                ".env.*"
            ),
        )

        if (temp_repo / "Cargo.toml").exists():
            lang = "rust"
        elif (temp_repo / "go.mod").exists():
            lang = "go"
        elif (temp_repo / "package.json").exists():
            lang = "javascript"
        elif any(temp_repo.glob("*.py")) or any(temp_repo.rglob("*.py")):
            lang = "python"
        elif (
            any(temp_repo.rglob("*.cs"))
            or any(temp_repo.rglob("*.sln"))
            or any(temp_repo.rglob("*.csproj"))
            ):
            lang = "csharp"
        elif (
            any(temp_repo.rglob("*.cpp"))
            or any(temp_repo.rglob("*.cc"))
            or any(temp_repo.rglob("*.cxx"))
            or any(temp_repo.rglob("*.hpp"))
            or any(temp_repo.rglob("*.hxx"))
        ):
            lang = "cpp"
        else:
            lang = "unknown"

        validation_command = get_default_validation_command(lang, temp_repo)

        result = apply_patch_plan(
            str(temp_repo),
            plan,
            validation_command=validation_command,
        )

        combined_diff = "\n\n".join(d for d in result.get("diffs", []) if d)
        summary = result.get("message") or ""

        if not result.get("success"):
            failed = result.get("failed_op") or {}
            idx = result.get("failed_op_index")
            err = result.get("error") or "unknown"
            summary = (
                f"Plan dry-run failed at op #{idx}: {err}\n"
                f"Failed op: {json.dumps(failed, ensure_ascii=False)[:200]}\n"
                f"Rollback performed: {result.get('rollback_performed')}"
            )

        return {
            "success": result.get("success", False),
            "message": summary,
            "diff": combined_diff,
            "validation": result.get("validation_output", ""),
            "applied_ops": result.get("applied_ops", []),
            "rollback_performed": result.get("rollback_performed", False),
        }

@app.route("/apply_patch_plan", methods=["POST"])
def apply_patch_plan_route():
    """Apply a multi-op patch_plan (used by balanced/vibe styles)."""
    from patching.patch_plan_executor import apply_patch_plan

    repo_path = request.form.get("repo_path", "")
    patch_json = request.form.get("patch", "")
    apply_policy = request.form.get("apply_policy", "ask")
    patch_style = request.form.get("patch_style", "")

    if apply_policy == "plan":
        return {
            "success": False,
            "message": "Plan-only policy: server refused to apply.",
            "diff": "",
            "validation": "",
        }

    # safe_minimal forbids patch_plan. Defense in depth on top of the prompt rule.
    if patch_style == "safe_minimal":
        return {
            "success": False,
            "message": "safe_minimal mode forbids patch_plan. Switch to balanced or vibe to apply multi-file changes.",
            "diff": "",
            "validation": "",
        }

    try:
        patch = json.loads(patch_json)
    except Exception:
        return {"error": "Invalid patch JSON"}

    plan = patch.get("patch_plan")
    if not isinstance(plan, list) or not plan:
        return {
            "success": False,
            "message": "No patch_plan found in payload. (Looking for top-level 'patch_plan': [...] )",
            "diff": "",
            "validation": "",
        }

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    repo_root = Path(repo_path).resolve()

    # Simple repo-level language detection for validation.
    if (repo_root / "Cargo.toml").exists():
        lang = "rust"
    elif (repo_root / "go.mod").exists():
        lang = "go"
    elif (repo_root / "package.json").exists():
        lang = "javascript"
    elif any(repo_root.glob("*.py")) or any(repo_root.rglob("*.py")):
        lang = "python"
    elif (
        any(repo_root.rglob("*.cs"))
        or any(repo_root.rglob("*.sln"))
        or any(repo_root.rglob("*.csproj"))
    ):
        lang = "csharp"
    elif (
        any(repo_root.rglob("*.cpp"))
        or any(repo_root.rglob("*.cc"))
        or any(repo_root.rglob("*.cxx"))
        or any(repo_root.rglob("*.hpp"))
        or any(repo_root.rglob("*.hxx"))
    ):
        lang = "cpp"
    else:
        lang = "unknown"

    validation_command = get_default_validation_command(lang, repo_root)

    result = apply_patch_plan(
        repo_path,
        plan,
        validation_command=validation_command,
    )

    # Combine all per-op diffs into one block so the existing Diff tab can render it.
    combined_diff = "\n\n".join(d for d in result.get("diffs", []) if d)
    summary = result.get("message") or ""
    if not result.get("success"):
        failed = result.get("failed_op") or {}
        idx = result.get("failed_op_index")
        err = result.get("error") or "unknown"
        summary = (
            f"Plan failed at op #{idx}: {err}\n"
            f"Failed op: {json.dumps(failed, ensure_ascii=False)[:200]}\n"
            f"Rollback performed: {result.get('rollback_performed')}"
        )

    return {
        "success": result.get("success", False),
        "message": summary,
        "diff": combined_diff,
        "validation": result.get("validation_output", ""),
        "applied_ops": result.get("applied_ops", []),
        "rollback_performed": result.get("rollback_performed", False),
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
        kind = request.form.get("kind", "bug").strip().lower()
        if kind not in {"bug", "debt", "idea", "research"}:
            return {"error": f"unknown kind: {kind}"}
        title = request.form.get("title", "").strip()
        hint = request.form.get("hint", "").strip()
        if not title:
            return {"error": "title is required"}
        items = dream_artifacts.append_to_queue(repo_path, {
            "kind": kind, "title": title, "hint": hint,
        })
        return {"queue": items}

    return {"error": f"unknown action: {action}"}


@app.route("/dream/run", methods=["POST"])
def dream_run_route():
    """Phase 2: kicks the run on a background thread and returns immediately.

    Poll /dream/status to follow progress. `dream_mode` selects Dream V2
    behaviour (`plan_only` default / `patch_if_safe` / `research`).
    """
    repo_path = request.form.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    patch_style = normalize_patch_style(request.form.get("patch_style"))
    dream_mode = request.form.get("dream_mode", "plan_only")

    try:
        return start_overnight_async(
            repo_path,
            patch_style=patch_style,
            dream_mode=dream_mode,
        )
    except Exception as e:
        return {"error": f"start_overnight_async failed: {e}"}


@app.route("/dream/status", methods=["GET"])
def dream_status_route():
    return get_run_state()


@app.route("/dream/list", methods=["GET"])
def dream_list_route():
    repo_path = request.values.get("repo_path", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    latest = dream_artifacts.latest_report_dir(repo_path)
    if not latest:
        return {"error": "No dream report found yet."}

    try:
        data = json.loads((latest / "list.json").read_text(encoding="utf-8"))
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
    """Full content of one historical dream run, by date (YYYY-MM-DD)."""
    repo_path = request.values.get("repo_path", "").strip()
    date = request.values.get("date", "").strip()
    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}
    if not date:
        return {"error": "date is required (YYYY-MM-DD)"}

    report_dir = dream_artifacts.dreams_root(repo_path) / date
    if not report_dir.is_dir():
        return {"error": f"no report for date: {date}"}
    return dream_artifacts.read_report(report_dir)


@app.route("/dream/apply", methods=["POST"])
def dream_apply_route():
    """Apply selected dream items to the real repo. One commit per item.

    `selection`: '1', '1,2', or 'all'.
    """
    from patching.patch_plan_executor import apply_patch_plan
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

        # Apply to real repo and validate again, even though it passed in sandbox.
        language = inspect_repo_inventory(repo_path).get("primary_language", "unknown")
        validation_command = get_default_validation_command(language, Path(repo_path))

        result = apply_patch_plan(
            repo_path,
            plan,
            validation_command=validation_command or None,
        )
        if not result.get("success"):
            results.append({
                "idx": idx, "title": title,
                "status": "apply_failed",
                "message": (result.get("message") or "")[:200],
            })
            continue

        # Stage only the paths this plan touched, then commit.
        touched = sorted({
            (op.get("relative_path") or op.get("file") or "")
            for op in plan
            if isinstance(op, dict) and (op.get("relative_path") or op.get("file"))
        })
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

@app.route("/session/<session_id>")
def load_session(session_id):
    sessions = load_sessions()
    current = find_session(session_id)

    return render_template(
        "index.html",
        sessions=sessions,
        current=current,
        result=current.get("result", {}) if current else {},
    )

@app.route("/generate_candidates", methods=["POST"])
def generate_candidates():
    control_json = request.form["control"]

    try:
        control = json.loads(control_json)
    except Exception:
        return {"error": "Invalid control JSON"}

    prompts = [
        ("gemini_default", build_control_prompt(control, "Generate the best safe patch.")),
        ("gemini_minimal", build_control_prompt(control, "Generate the smallest possible patch.")),
        ("deepseek_review", build_control_prompt(control, "Generate an alternative conservative patch.")),
    ]

    candidates = []

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
        "candidates": candidates
    }

@app.route("/test_patch", methods=["POST"])
def test_patch():
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form["patch"]

    try:
        parsed = json.loads(patch_json)

        if isinstance(parsed.get("patch_candidate"), dict):
            patch = parsed["patch_candidate"]
        else:
            patch = parsed

        if "patched_snippet" not in patch:
            return {
                "success": False,
                "message": "No patch_candidate found. Expected top-level patch_candidate or direct patch object.",
                "diff": "",
                "validation": "",
            }
    except Exception:
        return {"error": "Invalid patch JSON"}

    if not repo_path or not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_repo = Path(temp_dir) / "repo"
        shutil.copytree(
            repo_path,
            temp_repo,
            ignore=shutil.ignore_patterns(
                "target",
                ".git",
                ".agent",
                "__pycache__",
                ".pytest_cache",
                ".mypy_cache",
                "node_modules",
                "dist",
                "build",
                ".venv",
                "venv",
                ".env",
                ".env.*",
            ),
        )

        executor = Executor(
            project_root=str(temp_repo),
            rollback_on_validation_fail=True,
        )

        lang = _detect_patch_language(patch)
        validation_command = get_default_validation_command(lang, temp_repo)

        result = executor.run(
            patch=patch,
            language=lang,
            validation_command=validation_command,
            dry_run_only=True,
        )

        return {
            "message": result.message,
            "diff": result.diff,
            "validation": result.validation_output,
            "success": result.success,
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
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)