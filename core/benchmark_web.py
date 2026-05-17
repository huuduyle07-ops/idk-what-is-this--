from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.gemini_client import run_gemini_request_2
from benchmarks import run_benchmarks as benchmark_runner
from core.brain_stamp import collect_brain_stamp
from core.json_utils import extract_json_block
from core.repo_librarian import build_repo_manifest
from core.validation_command import get_default_validation_command


BENCHMARKS_ROOT = benchmark_runner.PROJECT_ROOT / "benchmarks"
CASES_ROOT = BENCHMARKS_ROOT / "cases"
REPORTS_ROOT = benchmark_runner.PROJECT_ROOT / ".agent" / "benchmarks"

_RUN_LOCK = threading.Lock()
_STATE_LOCK = threading.Lock()
_RUN_STATE: dict[str, Any] = {
    "status": "idle",
    "started_at": None,
    "completed_at": None,
    "report_path": None,
    "markdown_path": None,
    "total_items": 0,
    "current_idx": 0,
    "current_name": "",
    "cases_done": [],
    "error": None,
    "stop_requested": False,
    "options": {},
}

_CASE_SLUG_RE = re.compile(r"[^a-z0-9_]+")
_IGNORE_COPY = shutil.ignore_patterns(
    ".git",
    ".agent",
    ".claude",
    ".devcontainer",
    ".tmp",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
    ".env",
    ".env.*",
    "*.egg-info",
)
_IGNORE_CHANGED_PATH_PARTS = {
    ".git",
    ".agent",
    ".claude",
    ".devcontainer",
    ".tmp",
    ".vscode",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
}
_MAIN_FILE_CANDIDATES_BY_LANGUAGE = {
    "python": ("main.py", "app.py", "src/main.py", "src/app.py"),
    "javascript": (
        "main.js",
        "index.js",
        "app.js",
        "src/main.js",
        "src/index.js",
        "src/app.js",
    ),
    "typescript": (
        "main.ts",
        "index.ts",
        "app.ts",
        "src/main.ts",
        "src/index.ts",
        "src/app.ts",
    ),
    "cpp": ("main.cpp", "src/main.cpp"),
    "c": ("main.c", "src/main.c"),
    "go": ("main.go", "cmd/main.go"),
    "rust": ("src/main.rs", "src/lib.rs"),
    "csharp": ("Program.cs", "src/Program.cs"),
    "java": ("Main.java", "src/Main.java"),
}
_CENTRAL_FILE_NAMES = {
    "main.py",
    "app.py",
    "main.js",
    "index.js",
    "app.js",
    "main.ts",
    "index.ts",
    "app.ts",
    "main.cpp",
    "main.c",
    "main.go",
    "main.rs",
    "lib.rs",
    "program.cs",
    "main.java",
}


def get_benchmark_state() -> dict[str, Any]:
    with _STATE_LOCK:
        return {**_RUN_STATE, "cases_done": list(_RUN_STATE["cases_done"])}


def _set_state(**kwargs: Any) -> None:
    with _STATE_LOCK:
        _RUN_STATE.update(kwargs)


def _reset_state(total: int, options: dict[str, Any]) -> None:
    with _STATE_LOCK:
        _RUN_STATE.update(
            {
                "status": "running",
                "started_at": datetime.now().isoformat(timespec="seconds"),
                "completed_at": None,
                "report_path": None,
                "markdown_path": None,
                "total_items": total,
                "current_idx": 0,
                "current_name": "",
                "cases_done": [],
                "error": None,
                "stop_requested": False,
                "options": dict(options),
            }
        )


def request_benchmark_stop() -> dict[str, Any]:
    with _STATE_LOCK:
        if _RUN_STATE["status"] != "running":
            return {"stopped": False, "reason": "no benchmark run in progress"}
        if _RUN_STATE["stop_requested"]:
            return {"stopped": True, "reason": "stop already requested"}
        _RUN_STATE["stop_requested"] = True
        return {"stopped": True, "reason": "will stop after current case"}


def _stop_requested() -> bool:
    with _STATE_LOCK:
        return bool(_RUN_STATE.get("stop_requested"))


def _record_case_done(result: dict[str, Any]) -> None:
    status = "skipped" if result.get("skipped") else "passed" if result.get("success") else "failed"
    with _STATE_LOCK:
        _RUN_STATE["cases_done"].append(
            {
                "name": result.get("name"),
                "status": status,
                "duration_sec": result.get("duration_sec", 0),
                "language": result.get("language"),
                "category": result.get("category"),
                "difficulty": result.get("difficulty"),
                "toolchain_issue": result.get("toolchain_issue"),
                "error": result.get("error"),
            }
        )


def _case_record(case_file: Path) -> dict[str, Any]:
    try:
        case = benchmark_runner.load_case(case_file)
    except Exception as e:
        return {
            "id": case_file.parent.name,
            "name": case_file.parent.name,
            "folder": case_file.parent.name,
            "case_file": str(case_file),
            "ok": False,
            "error": f"{type(e).__name__}: {e}",
            "language": "unknown",
            "category": "uncategorized",
            "difficulty": "unknown",
        }

    name = case.get("name") or case_file.parent.name
    return {
        "id": name,
        "name": name,
        "folder": case_file.parent.name,
        "case_file": str(case_file),
        "ok": True,
        "language": case.get("language") or "unknown",
        "category": case.get("category") or "uncategorized",
        "difficulty": case.get("difficulty") or "unknown",
        "validation_command": case.get("validation_command") or "",
        "prompt": case.get("prompt") or "",
    }


def list_benchmark_cases() -> list[dict[str, Any]]:
    case_files = benchmark_runner.discover_case_files(CASES_ROOT)
    return [_case_record(path) for path in case_files]


def _selected_case_files(selected_cases: list[str] | None = None) -> list[Path]:
    all_files = benchmark_runner.discover_case_files(CASES_ROOT)
    if not selected_cases:
        return all_files

    wanted = {str(item).strip() for item in selected_cases if str(item).strip()}
    out: list[Path] = []
    for case_file in all_files:
        record = _case_record(case_file)
        aliases = {
            str(record.get("id") or ""),
            str(record.get("name") or ""),
            str(record.get("folder") or ""),
            str(Path(str(record.get("case_file") or "")).parent.name),
        }
        if aliases & wanted:
            out.append(case_file)
    return out


def _report_output_dir(repo_path: str | None) -> Path:
    if repo_path:
        return Path(repo_path).resolve() / ".agent" / "benchmarks"
    return REPORTS_ROOT


def _run_one_case(
    case_file: Path,
    *,
    skip_toolchain_failures: bool,
    retry_failed: int,
) -> dict[str, Any]:
    case_label = case_file.parent.name
    try:
        case = benchmark_runner.load_case(case_file)
        case_name = case.get("name") or case_label
        missing = (
            benchmark_runner.detect_missing_tools(case)
            if skip_toolchain_failures
            else []
        )
        if missing:
            return {
                "name": case_name,
                "success": False,
                "skipped": True,
                "skip_reason": "toolchain",
                "toolchain_issue": f"missing tools: {', '.join(missing)}",
                "case_file": str(case_file),
                "language": case.get("language"),
                "difficulty": case.get("difficulty"),
                "category": case.get("category", "uncategorized"),
                "duration_sec": 0.0,
                "changed_files": [],
                "missing_expected_files": [],
                "touched_forbidden_files": [],
                "validation_output": "",
                "patch_kind": "skipped",
                "rollback_happened": False,
                "agent_answer": "",
                "agent_validation": "",
                "attempts": 1,
                "flaky": False,
                "retry_results": [],
            }
        result = benchmark_runner._run_case_with_capture(case_file, capture=True)
    except Exception as e:
        result = {
            "name": case_label,
            "success": False,
            "error": repr(e),
            "case_file": str(case_file),
        }

    if retry_failed > 0 and benchmark_runner._should_retry(result):
        attempts_log = [benchmark_runner._retry_attempt_snapshot(result, attempt=1)]
        for attempt in range(2, retry_failed + 2):
            retry_result = benchmark_runner._run_case_with_capture(case_file, capture=True)
            attempts_log.append(
                benchmark_runner._retry_attempt_snapshot(retry_result, attempt=attempt)
            )
            result = retry_result
            if retry_result.get("success"):
                break
        result["attempts"] = len(attempts_log)
        result["flaky"] = bool(result.get("success")) and any(
            not attempt["success"] for attempt in attempts_log
        )
        result["retry_results"] = attempts_log
    else:
        result.setdefault("attempts", 1)
        result.setdefault("flaky", False)
        result.setdefault("retry_results", [])

    return result


def _build_report(
    results: list[dict[str, Any]],
    *,
    duration_sec: float,
    options: dict[str, Any],
) -> dict[str, Any]:
    passed = sum(1 for item in results if item.get("success"))
    skipped = sum(1 for item in results if item.get("skipped"))
    total = len(results)
    failed = max(0, total - passed - skipped)
    flaky = sum(1 for item in results if item.get("flaky"))
    runnable = total - skipped

    return {
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "flaky": flaky,
        "total": total,
        "success_rate": (passed / runnable) if runnable else 0,
        "duration_sec": round(duration_sec, 2),
        "filters": {
            "case": None,
            "selected_cases": options.get("selected_cases") or [],
            "language": None,
            "category": None,
            "difficulty": None,
            "limit": None,
            "fast": bool(options.get("fast")),
            "turbo": bool(options.get("turbo")),
            "web": True,
        },
        "groups": {
            "language": benchmark_runner.group_results(results, "language"),
            "category": benchmark_runner.group_results(results, "category"),
            "difficulty": benchmark_runner.group_results(results, "difficulty"),
        },
        "models_used": benchmark_runner._aggregate_models(results),
        "total_fallbacks": sum(
            item.get("fallback_count", 0) for item in results if not item.get("skipped")
        ),
        "self_corrected_count": sum(
            1 for item in results if not item.get("skipped") and item.get("self_corrected")
        ),
        **benchmark_runner._duration_aggregates(results),
        "results": results,
        "brain_stamp": collect_brain_stamp(benchmark_runner.PROJECT_ROOT),
    }


def _write_report(report: dict[str, Any], repo_path: str | None, markdown: bool) -> tuple[Path, Path | None]:
    out_dir = _report_output_dir(repo_path)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = int(time.time())
    out_path = out_dir / f"benchmark_report_{ts}.json"
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    md_path: Path | None = None
    if markdown:
        md_path = out_dir / f"benchmark_report_{ts}.md"
        benchmark_runner.write_markdown_report(report, md_path)

    return out_path, md_path


def start_benchmark_run_async(
    *,
    repo_path: str | None,
    selected_cases: list[str] | None = None,
    fast: bool = True,
    turbo: bool = False,
    skip_toolchain_failures: bool = True,
    retry_failed: int = 0,
    markdown: bool = True,
) -> dict[str, Any]:
    if not _RUN_LOCK.acquire(blocking=False):
        return {"error": "A benchmark run is already in progress."}

    if fast:
        benchmark_runner.apply_fast_env()
    if turbo:
        benchmark_runner.apply_turbo_env()

    case_files = _selected_case_files(selected_cases)
    if not case_files:
        _RUN_LOCK.release()
        return {"error": "No matching benchmark cases found."}

    options = {
        "repo_path": repo_path,
        "selected_cases": selected_cases or [],
        "fast": fast,
        "turbo": turbo,
        "skip_toolchain_failures": skip_toolchain_failures,
        "retry_failed": retry_failed,
        "markdown": markdown,
    }
    _reset_state(len(case_files), options)

    def _runner() -> None:
        started = time.time()
        results: list[dict[str, Any]] = []
        try:
            for idx, case_file in enumerate(case_files, start=1):
                if _stop_requested():
                    break
                record = _case_record(case_file)
                _set_state(
                    current_idx=idx,
                    current_name=record.get("name") or case_file.parent.name,
                )
                result = _run_one_case(
                    case_file,
                    skip_toolchain_failures=skip_toolchain_failures,
                    retry_failed=retry_failed,
                )
                results.append(result)
                _record_case_done(result)

            report = _build_report(
                results,
                duration_sec=time.time() - started,
                options=options,
            )
            report_path, md_path = _write_report(report, repo_path, markdown)
            _set_state(
                status="stopped" if _stop_requested() else "done",
                completed_at=datetime.now().isoformat(timespec="seconds"),
                current_idx=0,
                current_name="",
                report_path=str(report_path),
                markdown_path=str(md_path) if md_path else None,
            )
        except Exception as e:
            _set_state(
                status="failed",
                error=f"{type(e).__name__}: {e}",
                completed_at=datetime.now().isoformat(timespec="seconds"),
                current_idx=0,
                current_name="",
            )
        finally:
            _RUN_LOCK.release()

    threading.Thread(target=_runner, daemon=True, name="benchmark-runner").start()
    return {"started": True, "total_items": len(case_files)}


def _slugify_case_name(value: str) -> str:
    text = (value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = _CASE_SLUG_RE.sub("_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:80] or "new_benchmark_case"


def _split_paths(value: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for part in re.split(r"[\n,]+", value or ""):
        item = part.strip().replace("\\", "/")
        if not item or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return _dedupe_case_paths(out)


def _path_is_safe_case_path(rel_path: str) -> bool:
    item = (rel_path or "").strip().replace("\\", "/")
    if (
        not item
        or item.startswith("/")
        or item.startswith("../")
        or re.match(r"^[A-Za-z]:", item)
    ):
        return False
    parts = [part for part in item.split("/") if part]
    if not parts or ".." in parts:
        return False
    if any(part in _IGNORE_CHANGED_PATH_PARTS for part in parts):
        return False
    if any(part.endswith(".egg-info") for part in parts):
        return False
    return True


def _dedupe_case_paths(paths: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for path in paths:
        item = (path or "").strip().replace("\\", "/")
        if not _path_is_safe_case_path(item) or item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def _git_lines(source_repo: Path, args: list[str], *, timeout: float = 5.0) -> list[str]:
    try:
        proc = subprocess.run(
            ["git", "-c", "core.quotepath=false", "-C", str(source_repo), *args],
            capture_output=True,
            check=False,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if proc.returncode != 0:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def _git_changed_files(source_repo: Path) -> list[str]:
    if not _git_lines(source_repo, ["rev-parse", "--is-inside-work-tree"]):
        return []

    tracked = _git_lines(source_repo, ["ls-files"])
    paths = []
    paths.extend(_git_lines(source_repo, ["diff", "--name-only"]))
    paths.extend(_git_lines(source_repo, ["diff", "--cached", "--name-only"]))
    if tracked:
        paths.extend(_git_lines(source_repo, ["ls-files", "--others", "--exclude-standard"]))
    return _dedupe_case_paths(paths)


def _fallback_expected_files(
    source_repo: Path,
    language: str,
    manifest: dict[str, Any],
) -> list[str]:
    lang = (language or "").lower().strip()
    for candidate in _MAIN_FILE_CANDIDATES_BY_LANGUAGE.get(lang, ()):
        if (source_repo / candidate).is_file():
            return [candidate]

    indexable_files = [
        rel
        for rel in (manifest.get("indexable_files") or manifest.get("sample_indexable_files") or [])
        if isinstance(rel, str) and _path_is_safe_case_path(rel)
    ]
    for rel in indexable_files:
        if Path(rel.replace("\\", "/")).name.lower() in _CENTRAL_FILE_NAMES:
            return [rel.replace("\\", "/")]
    if len(indexable_files) == 1:
        return [indexable_files[0].replace("\\", "/")]
    return []


def infer_case_defaults(source_repo_path: str, user_prompt: str = "") -> dict[str, Any]:
    source_repo = Path(source_repo_path).expanduser().resolve()
    if not source_repo.is_dir():
        return {"ok": False, "error": f"source repo is not a directory: {source_repo}"}

    manifest = build_repo_manifest(str(source_repo))
    if not manifest.get("ok"):
        return {"ok": False, "error": manifest.get("reason") or "repo is not indexable"}

    language = manifest.get("primary_language") or "unknown"
    changed_files = _git_changed_files(source_repo)
    fallback_files = _fallback_expected_files(source_repo, language, manifest)
    inferred_expected = changed_files or fallback_files
    validation = get_default_validation_command(language, source_repo) or ""
    slug = _slugify_case_name(source_repo.name)
    prompt = (user_prompt or f"Fix the bug in {source_repo.name}.").strip()
    if validation and "Validation command:" not in prompt:
        prompt += f"\n\nValidation command: {validation}"

    return {
        "ok": True,
        "name": slug,
        "language": language,
        "category": "uncategorized",
        "difficulty": "medium",
        "validation_command": validation,
        "expected_changed_files": inferred_expected,
        "expected_changed_files_source": (
            "git_diff" if changed_files else "central_file_fallback" if fallback_files else "none"
        ),
        "forbidden_changed_files": [],
        "prompt": prompt,
        "manifest": {
            "files_total": manifest.get("files_total"),
            "indexable_count": manifest.get("indexable_count"),
            "languages": manifest.get("languages"),
            "sample_files": manifest.get("sample_files"),
            "sample_indexable_files": manifest.get("sample_indexable_files"),
        },
    }


def _coerce_metadata_json(data: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    out = dict(fallback)
    for key in (
        "name",
        "language",
        "category",
        "difficulty",
        "validation_command",
        "prompt",
    ):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            out[key] = value.strip()

    for key in ("expected_changed_files", "forbidden_changed_files"):
        value = data.get(key)
        if isinstance(value, list):
            paths = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    paths.append(item.strip().replace("\\", "/"))
            out[key] = _dedupe_case_paths(paths)

    if out.get("difficulty") not in {"easy", "medium", "hard"}:
        out["difficulty"] = fallback.get("difficulty", "medium")
    return out


def _llm_case_metadata(
    *,
    source_repo: Path,
    fallback: dict[str, Any],
    user_prompt: str,
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    prompt = f"""
You are the requirements clerk for a benchmark case for an AI coding agent.
Return ONLY JSON with these keys:
name, language, category, difficulty, validation_command, expected_changed_files,
forbidden_changed_files, prompt.

Difficulty must be one of: easy, medium, hard.
Category should be short snake_case, for example logic_validation, async_flow,
import_export, data_integrity, boundary_check, accessibility, performance.

The benchmark copies the source repo into benchmarks/cases/<language>/<case>/buggy_repo.
The human intent may be rough, incomplete, or informal. Rewrite it into a strict
benchmark prompt with concrete requirements, constraints, and expected behavior.
Use repo-relative paths. Treat fallback expected_changed_files as evidence from
the web patch/git diff when present. Preserve those files unless the manifest
proves they are wrong. Do not invent expected/forbidden files without evidence.
Keep validation_command aligned with the repo's default test command unless the
human intent clearly gives a better command.

User's benchmark intent:
{user_prompt or "(none provided)"}

Current fallback metadata:
{json.dumps(fallback, indent=2)}

Repo manifest:
{json.dumps({
    "primary_language": manifest.get("primary_language"),
    "languages": manifest.get("languages"),
    "sample_files": manifest.get("sample_files"),
    "sample_indexable_files": manifest.get("sample_indexable_files"),
}, indent=2)}
"""
    sample_files = [
        str(source_repo / rel)
        for rel in (manifest.get("sample_indexable_files") or [])[:8]
        if isinstance(rel, str) and (source_repo / rel).is_file()
    ]
    raw = run_gemini_request_2(
        prompt=prompt,
        repo_path=str(source_repo),
        file_paths=sample_files,
    )
    if raw.startswith("AGENT_ERROR:"):
        return fallback, raw
    parsed = extract_json_block(raw)
    if not isinstance(parsed, dict):
        return fallback, "LLM did not return parseable JSON"
    return _coerce_metadata_json(parsed, fallback), None


def create_benchmark_case_from_repo(
    *,
    source_repo_path: str,
    case_name: str,
    user_prompt: str,
    validation_command: str,
    expected_changed_files: str,
    forbidden_changed_files: str,
    use_llm: bool = True,
    overwrite: bool = False,
) -> dict[str, Any]:
    source_repo = Path(source_repo_path).expanduser().resolve()
    if not source_repo.is_dir():
        return {"ok": False, "error": f"source repo is not a directory: {source_repo}"}

    manifest = build_repo_manifest(str(source_repo))
    if not manifest.get("ok"):
        return {"ok": False, "error": manifest.get("reason") or "repo is not indexable"}

    language = manifest.get("primary_language") or "unknown"
    validation = validation_command.strip() or (
        get_default_validation_command(language, source_repo) or ""
    )
    expected_files = (
        _split_paths(expected_changed_files)
        or _git_changed_files(source_repo)
        or _fallback_expected_files(source_repo, language, manifest)
    )
    slug = _slugify_case_name(case_name or source_repo.name)
    fallback = {
        "name": slug,
        "language": language,
        "category": "uncategorized",
        "difficulty": "medium",
        "agent_mode": "reviewer",
        "patch_style": "balanced",
        "validation_command": validation,
        "expected_changed_files": expected_files,
        "forbidden_changed_files": _split_paths(forbidden_changed_files),
        "prompt": (user_prompt or f"Fix the bug in {source_repo.name}.").strip(),
    }
    if validation and "Validation command:" not in fallback["prompt"]:
        fallback["prompt"] += f"\n\nValidation command: {validation}"

    llm_warning = None
    metadata = fallback
    if use_llm:
        metadata, llm_warning = _llm_case_metadata(
            source_repo=source_repo,
            fallback=fallback,
            user_prompt=user_prompt,
            manifest=manifest,
        )

    metadata.setdefault("agent_mode", "reviewer")
    metadata.setdefault("patch_style", "balanced")
    metadata["name"] = _slugify_case_name(str(metadata.get("name") or slug))
    metadata["language"] = _slugify_case_name(str(metadata.get("language") or language))
    metadata["category"] = _slugify_case_name(str(metadata.get("category") or "uncategorized"))
    if metadata.get("difficulty") not in {"easy", "medium", "hard"}:
        metadata["difficulty"] = "medium"

    dest_dir = CASES_ROOT / metadata["language"] / metadata["name"]
    buggy_repo = dest_dir / "buggy_repo"
    if dest_dir.exists() and not overwrite:
        return {
            "ok": False,
            "error": f"benchmark case already exists: {dest_dir}",
            "case_dir": str(dest_dir),
        }
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    dest_dir.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source_repo, buggy_repo, ignore=_IGNORE_COPY)

    case_json = {
        "name": metadata["name"],
        "language": metadata["language"],
        "category": metadata["category"],
        "difficulty": metadata["difficulty"],
        "agent_mode": metadata.get("agent_mode", "reviewer"),
        "patch_style": metadata.get("patch_style", "balanced"),
        "validation_command": metadata.get("validation_command", ""),
        "expected_changed_files": metadata.get("expected_changed_files", []),
        "forbidden_changed_files": metadata.get("forbidden_changed_files", []),
        "prompt": metadata.get("prompt", ""),
    }
    (dest_dir / "case.json").write_text(
        json.dumps(case_json, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return {
        "ok": True,
        "case_dir": str(dest_dir),
        "case_file": str(dest_dir / "case.json"),
        "buggy_repo": str(buggy_repo),
        "case": case_json,
        "llm_warning": llm_warning,
    }
