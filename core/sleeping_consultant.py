from __future__ import annotations

import json
import shutil
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

from core.control_engine import run_control_structured, build_control_prompt
from core.feature_context import maybe_enrich_with_scout
from core.json_utils import extract_json_block
from agents.gemini_client import run_gemini_request_2
from patching.patch_plan_executor import apply_patch_plan
from core import dream_artifacts


# ============================================================
# Phase 2 — async run state
# ============================================================
# A single dream run can be in flight at a time. _RUN_LOCK is the gate;
# _RUN_STATE is what /dream/status returns to the UI poller.
_RUN_LOCK = threading.Lock()
_STATE_LOCK = threading.Lock()
_RUN_STATE: dict = {
    "status": "idle",          # idle | running | done | failed
    "started_at": None,        # iso timestamp
    "completed_at": None,      # iso timestamp
    "report_dir": None,        # str path
    "patch_style": None,
    "total_items": 0,
    "current_idx": 0,          # 1-based; 0 = nothing in flight
    "current_kind": "",
    "current_title": "",
    "items_done": [],          # list of {idx, kind, title, status}
    "error": None,             # str when status=failed
}


def get_run_state() -> dict:
    """Snapshot of the current/last dream run, for /dream/status polling."""
    with _STATE_LOCK:
        return {**_RUN_STATE, "items_done": list(_RUN_STATE["items_done"])}


def _set_state(**kwargs) -> None:
    with _STATE_LOCK:
        _RUN_STATE.update(kwargs)


def _reset_state_for_run(total: int, patch_style: str, report_dir: Path) -> None:
    with _STATE_LOCK:
        _RUN_STATE.update({
            "status": "running",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "completed_at": None,
            "report_dir": str(report_dir),
            "patch_style": patch_style,
            "total_items": total,
            "current_idx": 0,
            "current_kind": "",
            "current_title": "",
            "items_done": [],
            "error": None,
        })


def _record_item_done(item_result: dict) -> None:
    with _STATE_LOCK:
        _RUN_STATE["items_done"].append({
            "idx": item_result.get("idx"),
            "kind": item_result.get("kind"),
            "title": item_result.get("title"),
            "status": item_result.get("status"),
        })


_IGNORE = shutil.ignore_patterns(
    "target", ".git", ".agent", "__pycache__", ".pytest_cache",
    ".mypy_cache", "node_modules", "dist", "build", ".venv", "venv",
    ".env", ".envrc", "env", ".DS_Store", "*.egg-info",".gitignore", ".env*"
)


def _validation_command(temp_repo: Path) -> str | None:
    """Best-effort lightweight validation. Returns None when nothing reasonable."""
    if (temp_repo / "Cargo.toml").exists():
        return "cargo check --quiet"
    if (temp_repo / "go.mod").exists():
        return "go build ./..."
    if (temp_repo / "pyproject.toml").exists() or any(temp_repo.glob("*.py")):
        return "python -m compileall -q ."
    return None


def _build_patch_query(item: dict) -> str:
    title = item.get("title", "untitled")
    hint = item.get("hint", "")
    kind = item.get("kind", "bug")
    if hint:
        return f"[{kind}] {title} — Hint: {hint}"
    return f"[{kind}] {title}"


def _generate_patch_plan(
    repo_path: str,
    item: dict,
    feedback: str | None = None,
) -> tuple[dict | None, str]:
    """Run Control + Scout + Gemini once. Returns (parsed_dict, raw_response)."""
    query = _build_patch_query(item)
    if feedback:
        query = (
            f"{query}\n\n"
            f"PREVIOUS ATTEMPT FAILED VALIDATION. Feedback:\n{feedback}\n"
            f"Revise the patch_plan accordingly."
        )

    control = run_control_structured(query, repo_path)
    # Force Scout in dream mode — bug/debt queries don't trigger the default
    # heuristic, leaving CONTROL without source snippets and the model
    # correctly refusing to invent a patch ("no exact source_snippet").
    control = maybe_enrich_with_scout(query, repo_path, control, force=True) or control

    prompt = build_control_prompt(control, f"Generate patch_plan for: {query}")
    raw = run_gemini_request_2(prompt=prompt, repo_path=repo_path)
    parsed = extract_json_block(raw)
    return parsed, (raw or "")


def _generate_plan_analysis(repo_path: str, item: dict) -> tuple[dict | None, str]:
    """Fallback: ask the model for a structured plan without requiring a patch_plan.

    Called when the main attempt did not produce a valid patch_plan list.
    Returns (parsed_dict, raw_response).
    """
    query = _build_patch_query(item)
    kind = item.get("kind", "bug")

    prompt = f"""You are a senior engineer doing a planning pass on a software task.
Do NOT write any code patch. Your only job is to analyse the task and return a plan.

Task: {query}

Return ONLY valid JSON — no markdown fences, no extra text:
{{
  "status": "planned",
  "item_type": "{kind}",
  "priority": "high|medium|low",
  "problem_summary": "clear one-sentence description of the problem or goal",
  "likely_files": ["relative/path/to/file.py"],
  "recommended_steps": ["step 1", "step 2"],
  "safe_to_patch_now": false,
  "patch_style_required": "safe_minimal|balanced|vibe|none",
  "validation_commands": ["python -m pytest tests/"],
  "risks": ["risk 1"]
}}

Be specific — reference real file paths and symbols when you can.
"""
    raw = run_gemini_request_2(prompt=prompt, repo_path=repo_path)
    parsed = extract_json_block(raw)
    return parsed, (raw or "")


def _run_patch_item(
    repo_path: str,
    item: dict,
    idx: int,
    retry_per_item: int,
    item_dir_path: Path,
) -> dict:
    """bug / debt — generate a patch_plan, validate it in a fresh sandbox."""
    item_dir_path.mkdir(parents=True, exist_ok=True)
    feedback: str | None = None

    for attempt in range(1 + max(0, retry_per_item)):
        patch, raw = _generate_patch_plan(repo_path, item, feedback=feedback)
        (item_dir_path / f"raw_model_attempt{attempt + 1}.txt").write_text(
            raw, encoding="utf-8",
        )

        if not isinstance(patch, dict):
            feedback = "Model did not return valid JSON."
            continue

        plan = patch.get("patch_plan")
        if not isinstance(plan, list) or not plan:
            # Model returned something (single-op patch or explanation) but no
            # patch_plan list. Save what we got, then ask for a structured plan.
            (item_dir_path / "patch.json").write_text(
                json.dumps(patch, indent=2, ensure_ascii=False) if isinstance(patch, dict) else str(patch),
                encoding="utf-8",
            )
            plan_data, plan_raw = _generate_plan_analysis(repo_path, item)
            (item_dir_path / "plan_analysis.json").write_text(
                json.dumps(plan_data, indent=2, ensure_ascii=False) if isinstance(plan_data, dict) else plan_raw,
                encoding="utf-8",
            )
            summary = ""
            if isinstance(plan_data, dict):
                summary = plan_data.get("problem_summary", "") or ""
            return {
                **item, "idx": idx,
                "status": "planned_no_patch",
                "summary": (summary or "Plan created; no patch generated.")[:200],
                "item_dir_name": item_dir_path.name,
            }

        # Fresh sandbox per attempt — failed apply never contaminates next item.
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            temp_repo = Path(temp_dir) / "repo"
            shutil.copytree(repo_path, temp_repo, ignore=_IGNORE)

            validation = _validation_command(temp_repo)
            result = apply_patch_plan(
                str(temp_repo), plan, validation_command=validation,
            )

        # Persist artifacts regardless of success
        (item_dir_path / "patch_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        diff_text = "\n\n".join(d for d in result.get("diffs", []) if d)
        (item_dir_path / "diff.txt").write_text(diff_text, encoding="utf-8")
        (item_dir_path / "validation.log").write_text(
            result.get("validation_output", "") or "",
            encoding="utf-8",
        )

        if result.get("success"):
            return {
                **item, "idx": idx,
                "status": "ready_to_apply",
                "summary": (result.get("message") or "Validated in sandbox.")[:200],
                "item_dir_name": item_dir_path.name,
                "ops_count": len(plan),
            }

        # Capture feedback for the next attempt ("voice through whisper")
        feedback = (
            (result.get("message") or "") + "\n\n"
            + (result.get("error") or "") + "\n\n"
            + (result.get("validation_output") or "")
        ).strip()[:1500]

    return {
        **item, "idx": idx,
        "status": "rejected",
        "summary": (feedback or "Patch failed validation after all attempts.")[:200],
        "item_dir_name": item_dir_path.name,
    }


def _run_idea_item(
    repo_path: str,
    item: dict,
    idx: int,
    item_dir_path: Path,
) -> dict:
    """idea — markdown design note only, no patch attempt."""
    item_dir_path.mkdir(parents=True, exist_ok=True)

    title = item.get("title", "untitled")
    hint = item.get("hint", "")
    prompt = (
        f"You are an unconstrained research engineer. Brainstorm aggressively.\n\n"
        f"Idea: {title}\n"
        f"Hint: {hint}\n\n"
        f"Write a markdown design note. Cover:\n"
        f"1. What this could become.\n"
        f"2. 3-5 concrete first-step changes (file paths welcome).\n"
        f"3. 1-2 wildcard/crazy variants worth exploring.\n"
        f"4. Risks / what would kill this idea.\n"
        f"Be specific. Reference real symbols/paths when you can. No code patches."
    )

    raw = run_gemini_request_2(prompt=prompt, repo_path=repo_path) or ""
    (item_dir_path / "design.md").write_text(raw, encoding="utf-8")

    return {
        **item, "idx": idx,
        "status": "idea_written",
        "summary": raw[:200].replace("\n", " "),
        "item_dir_name": item_dir_path.name,
    }


def _run_plan_only_item(
    repo_path: str,
    item: dict,
    idx: int,
    item_dir_path: Path,
) -> dict:
    """Generate a structured plan for any item type without attempting a patch.

    Used for idea items when patch_style != 'vibe', or as an explicit
    plan-only pass for debt/bug items that need triage before patching.
    """
    item_dir_path.mkdir(parents=True, exist_ok=True)
    plan_data, plan_raw = _generate_plan_analysis(repo_path, item)
    (item_dir_path / "plan_analysis.json").write_text(
        json.dumps(plan_data, indent=2, ensure_ascii=False) if isinstance(plan_data, dict) else plan_raw,
        encoding="utf-8",
    )
    summary = ""
    if isinstance(plan_data, dict):
        summary = plan_data.get("problem_summary", "") or ""
    return {
        **item, "idx": idx,
        "status": "planned_no_patch",
        "summary": (summary or "Plan created; no patch generated.")[:200],
        "item_dir_name": item_dir_path.name,
    }


def run_overnight(
    repo_path: str,
    patch_style: str = "balanced",
    time_budget_sec: int = 6 * 3600,
    retry_per_item: int = 1,
) -> dict:
    """Run the dream queue. The original repo is never touched.

    Each item is run in a fresh temp clone. Results land in
    .agent/dreams/<YYYY-MM-DD>/. The user picks which to apply later via the
    web UI.
    """
    repo_path = str(Path(repo_path).resolve())
    if not Path(repo_path).is_dir():
        return {"error": f"repo_path is not a directory: {repo_path}"}

    queue = dream_artifacts.read_queue(repo_path)
    if not queue:
        return {"error": "Queue is empty. Add items first."}

    report_dir = dream_artifacts.today_dir(repo_path)
    report_dir.mkdir(parents=True, exist_ok=True)

    # Snapshot the queue used for this run
    (report_dir / "queue.json").write_text(
        json.dumps(queue, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(
        f"💤 DREAM: starting run | items={len(queue)} | "
        f"style={patch_style} | report_dir={report_dir}",
        flush=True,
    )
    _reset_state_for_run(total=len(queue), patch_style=patch_style, report_dir=report_dir)

    start = time.time()
    results: list[dict] = []

    for idx, item in enumerate(queue, start=1):
        if time.time() - start > time_budget_sec:
            print(
                f"💤 DREAM: [{idx}/{len(queue)}] skipped — time budget exceeded",
                flush=True,
            )
            skipped = {
                **item, "idx": idx,
                "status": "skipped_time_budget",
                "summary": "Time budget exceeded.",
            }
            results.append(skipped)
            _record_item_done(skipped)
            continue

        kind = (item.get("kind") or "").lower()
        title = item.get("title", "")
        item_path = dream_artifacts.item_dir(report_dir, idx, title)

        _set_state(current_idx=idx, current_kind=kind, current_title=title)

        print(
            f"💤 DREAM: [{idx}/{len(queue)}] {kind} → {title!r} → {item_path.name}",
            flush=True,
        )
        item_started = time.time()

        try:
            if kind == "idea":
                if patch_style != "vibe":
                    # Not vibe — generate a plan instead of skipping entirely.
                    print(
                        f"💤 DREAM: [{idx}/{len(queue)}] idea → plan-only (patch_style={patch_style!r})",
                        flush=True,
                    )
                    results.append(_run_plan_only_item(repo_path, item, idx, item_path))
                else:
                    results.append(_run_idea_item(repo_path, item, idx, item_path))
            else:
                results.append(_run_patch_item(
                    repo_path=repo_path,
                    item=item,
                    idx=idx,
                    retry_per_item=retry_per_item,
                    item_dir_path=item_path,
                ))
        except Exception as e:
            item_path.mkdir(parents=True, exist_ok=True)
            (item_path / "error.txt").write_text(
                f"{type(e).__name__}: {e}", encoding="utf-8",
            )
            print(
                f"💤 DREAM: [{idx}/{len(queue)}] error — {type(e).__name__}: {e}",
                flush=True,
            )
            results.append({
                **item, "idx": idx,
                "status": "error",
                "summary": f"{type(e).__name__}: {e}",
                "item_dir_name": item_path.name,
            })

        last_status = results[-1].get("status", "?")
        _record_item_done(results[-1])
        print(
            f"💤 DREAM: [{idx}/{len(queue)}] done in {time.time() - item_started:.1f}s — status={last_status}",
            flush=True,
        )

    print(
        f"💤 DREAM: run complete in {time.time() - start:.1f}s — wrote {report_dir / 'morning_report.txt'}",
        flush=True,
    )

    # Write outputs
    dream_artifacts.write_report_markdown(report_dir, results)
    (report_dir / "list.json").write_text(
        json.dumps({
            "items": results,
            "patch_style": patch_style,
            "completed_at": datetime.now().isoformat(timespec="seconds"),
        }, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "report_dir": str(report_dir),
        "items": results,
    }


def start_overnight_async(
    repo_path: str,
    patch_style: str = "balanced",
    time_budget_sec: int = 6 * 3600,
    retry_per_item: int = 1,
) -> dict:
    """Kick a dream run on a background daemon thread.

    Returns immediately with `{started: True}` on success, or
    `{error: "already running"}` if a run is already in flight. Poll
    /dream/status (or call get_run_state()) to follow progress.

    Daemon thread caveat: if the Flask process is killed (or hot-reloaded
    on file change in dev mode) the run dies with it. For overnight use,
    don't edit Python files in the project while the run is going.
    """
    if not _RUN_LOCK.acquire(blocking=False):
        return {"error": "A dream run is already in progress."}

    def _runner() -> None:
        try:
            result = run_overnight(
                repo_path=repo_path,
                patch_style=patch_style,
                time_budget_sec=time_budget_sec,
                retry_per_item=retry_per_item,
            )
            if result.get("error"):
                _set_state(
                    status="failed",
                    error=result["error"],
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                )
            else:
                _set_state(
                    status="done",
                    completed_at=datetime.now().isoformat(timespec="seconds"),
                    current_idx=0,
                    current_kind="",
                    current_title="",
                )
        except Exception as e:  # belt-and-braces; run_overnight already catches per-item
            _set_state(
                status="failed",
                error=f"{type(e).__name__}: {e}",
                completed_at=datetime.now().isoformat(timespec="seconds"),
            )
        finally:
            _RUN_LOCK.release()

    threading.Thread(target=_runner, daemon=True, name="dream-runner").start()
    return {"started": True}
