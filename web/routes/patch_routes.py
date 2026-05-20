from __future__ import annotations

import json
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from flask import Blueprint, request

from core.executor import Executor
from core.patch_safety import evaluate_patch_safety
from core.run_lifecycle import run_patch_plan_with_artifacts
from core.validation_command import get_default_validation_command
from web.patch_helpers import (
    backup_key_for_path,
    detect_patch_language,
    detect_repo_language,
    patch_plan_files,
)


bp = Blueprint("patch_routes", __name__)
BACKUP_DIR = Path(__file__).resolve().parent.parent / "backups"
BACKUP_DIR.mkdir(exist_ok=True)


def _risk_dict(result) -> dict | None:
    risk = getattr(result, "risk", None)
    if not risk:
        return None
    return {
        "level": risk.level,
        "score": risk.score,
        "reasons": list(risk.reasons or []),
    }


@bp.route("/apply_patch", methods=["POST"])
def apply_patch():
    repo_path = request.form.get("repo_path", "")
    patch_json = request.form["patch"]
    apply_policy = request.form.get("apply_policy", "ask")
    max_backups = 7

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
    patch_safety = evaluate_patch_safety([target_file], project_root=repo_root)
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            "patch_safety": patch_safety,
        }

    file_path = (repo_root / target_file).resolve()
    try:
        file_path.relative_to(repo_root)
    except ValueError:
        return {
            "success": False,
            "message": "Unsafe patch target: file is outside repo.",
            "diff": "",
            "validation": "",
            "patch_safety": patch_safety,
        }, 400

    safe_path = backup_key_for_path(target_file)
    backup_path = BACKUP_DIR / f"{safe_path}_{datetime.now().timestamp()}.bak"

    if file_path.exists():
        backup_path.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")

    backups = sorted(BACKUP_DIR.glob(f"{safe_path}_*.bak"), reverse=True)
    for old in backups[max_backups:]:
        old.unlink()

    executor = Executor(
        project_root=repo_path,
        rollback_on_validation_fail=True,
    )

    lang = detect_patch_language(patch)
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
        "risk": _risk_dict(result),
        "validation_command": validation_command or "",
        "patch_safety": patch_safety,
    }


@bp.route("/test_patch", methods=["POST"])
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

    target_file = patch.get("relative_path") or patch.get("file") or ""
    patch_safety = evaluate_patch_safety(
        [target_file],
        project_root=Path(repo_path).resolve(),
    )
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            "patch_safety": patch_safety,
        }

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

        lang = detect_patch_language(patch)
        validation_command = get_default_validation_command(lang, temp_repo)

        result = executor.run(
            patch=patch,
            language=lang,
            validation_command=validation_command,
            dry_run_only=False,
        )

        return {
            "message": result.message,
            "diff": result.diff,
            "validation": result.validation_output,
            "success": result.success,
            "risk": _risk_dict(result),
            "validation_command": validation_command or "",
            "patch_safety": patch_safety,
        }


@bp.route("/test_patch_plan", methods=["POST"])
def test_patch_plan():
    """Dry-run a multi-op patch_plan in a temp clone, then validate."""
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

    patch_safety = evaluate_patch_safety(
        patch_plan_files(plan),
        project_root=Path(repo_path).resolve(),
    )
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch plan blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            "patch_safety": patch_safety,
        }

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

        lang = detect_repo_language(temp_repo)
        validation_command = get_default_validation_command(lang, temp_repo)

        result = run_patch_plan_with_artifacts(
            str(temp_repo),
            plan,
            validation_command=validation_command,
            user_query=request.form.get("query", ""),
            control_result={"route": "test_patch_plan"},
            source="web_test_patch_plan",
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
            "risk": None,
            "validation_command": validation_command or "",
            "patch_safety": patch_safety,
        }


@bp.route("/apply_patch_plan", methods=["POST"])
def apply_patch_plan_route():
    """Apply a multi-op patch_plan (used by balanced/vibe styles)."""
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
    patch_safety = evaluate_patch_safety(
        patch_plan_files(plan),
        project_root=repo_root,
    )
    if not patch_safety["ok"]:
        return {
            "success": False,
            "message": "Patch plan blocked by safety gate: " + "; ".join(patch_safety["reasons"]),
            "diff": "",
            "validation": "",
            "risk": None,
            "validation_command": "",
            "patch_safety": patch_safety,
        }

    lang = detect_repo_language(repo_root)
    validation_command = get_default_validation_command(lang, repo_root)

    result = run_patch_plan_with_artifacts(
        repo_path,
        plan,
        validation_command=validation_command,
        user_query=request.form.get("query", ""),
        control_result={"route": "apply_patch_plan"},
        source="web_apply_patch_plan",
    )

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
        "risk": None,
        "validation_command": validation_command or "",
        "patch_safety": patch_safety,
    }
