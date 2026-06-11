from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

REPORT_DIR = PROJECT_ROOT / ".agent" / "reports"
PROPOSAL_ROOT = PROJECT_ROOT / ".agent" / "proposals"
BENCH_DIR = PROJECT_ROOT / ".agent" / "benchmarks"
CASES_DIR = PROJECT_ROOT / "benchmarks" / "cases"

ALLOWED_VALIDATION_TOOLS = {
    "python",
    "python3",
    "py",
    "node",
    "npm",
    "npx",
    "go",
    "cargo",
    "rustc",
    "g++",
    "gcc",
    "make",
    "echo",
}
FORBIDDEN_PATH_PARTS = {".agent", ".git", "node_modules", "target", ".venv", "venv"}
SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".tsx",
    ".go",
    ".rs",
    ".cpp",
    ".c",
    ".h",
    ".hpp",
    ".html",
    ".css",
    ".json",
    ".md",
}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def _latest_plan() -> Path | None:
    if not REPORT_DIR.is_dir():
        return None
    plans = sorted(
        REPORT_DIR.glob("background_dream_plan_*.json"),
        key=lambda p: p.stat().st_mtime,
    )
    return plans[-1] if plans else None


def _is_inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _resolve_source_report(value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = BENCH_DIR / candidate.name
    try:
        candidate = candidate.resolve()
    except Exception:
        return None
    if not _is_inside(candidate, BENCH_DIR):
        return None
    if not candidate.name.startswith("benchmark_report_") or candidate.suffix != ".json":
        return None
    return candidate if candidate.is_file() else None


def _find_report_result(report: dict[str, Any], case_name: str) -> dict[str, Any] | None:
    for result in report.get("results") or []:
        if isinstance(result, dict) and result.get("name") == case_name:
            return result
    return None


def _case_file_from_report_result(result: dict[str, Any] | None) -> Path | None:
    if not result:
        return None
    raw = str(result.get("case_file") or "").strip()
    if not raw:
        return None
    try:
        candidate = Path(raw).resolve()
    except Exception:
        return None
    if not _is_inside(candidate, CASES_DIR):
        return None
    return candidate if candidate.is_file() and candidate.name == "case.json" else None


def _case_file_by_name(case_name: str) -> Path | None:
    for path in CASES_DIR.rglob("case.json"):
        data = _load_json(path)
        if data and data.get("name") == case_name:
            return path
    return None


def _load_case_metadata(case_name: str, report: dict[str, Any]) -> tuple[Path, dict[str, Any]] | None:
    result = _find_report_result(report, case_name)
    case_file = _case_file_from_report_result(result) or _case_file_by_name(case_name)
    if case_file is None:
        return None
    data = _load_json(case_file)
    if not data or data.get("name") != case_name:
        return None
    return case_file, data


def _split_validation_command(command: str) -> tuple[list[list[str]], str | None]:
    command = (command or "").strip()
    if not command:
        return [], "validation command is empty"

    segments: list[list[str]] = []
    for raw_segment in command.split("&&"):
        raw_segment = raw_segment.strip()
        if not raw_segment:
            return [], "empty validation command segment"
        try:
            args = shlex.split(raw_segment, posix=(os.name != "nt"))
        except ValueError as exc:
            return [], f"could not parse validation command: {exc}"
        if not args:
            return [], "empty validation command segment"
        tool = Path(args[0]).name.lower()
        if tool.endswith(".exe"):
            tool = tool[:-4]
        if tool not in ALLOWED_VALIDATION_TOOLS:
            return [], f"validation tool is not whitelisted: {args[0]}"
        segments.append(args)
    return segments, None


def _validation_env() -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env.setdefault("PYTHONUNBUFFERED", "1")

    try:
        from core.validator import _native_toolchain_env

        native_env = _native_toolchain_env()
        if native_env:
            env.update(native_env)
            env["PYTHONUTF8"] = "1"
            env["PYTHONIOENCODING"] = "utf-8"
            env.setdefault("PYTHONUNBUFFERED", "1")
    except Exception:
        pass

    return env


def _run_validation_command(command: str, cwd: Path, timeout_sec: int) -> dict[str, Any]:
    segments, issue = _split_validation_command(command)
    started = time.time()
    output_parts: list[str] = []
    completed_segments: list[dict[str, Any]] = []

    if issue:
        return {
            "ok": False,
            "validation_ok": False,
            "command": command,
            "error": issue,
            "duration_sec": 0.0,
            "segments": [],
            "output": "",
        }

    env = _validation_env()
    for args in segments:
        elapsed = time.time() - started
        remaining_raw = timeout_sec - elapsed
        if remaining_raw <= 0:
            return {
                "ok": False,
                "validation_ok": False,
                "command": command,
                "error": f"validation timeout after {timeout_sec}s",
                "duration_sec": round(time.time() - started, 2),
                "segments": completed_segments,
                "output": "\n".join(output_parts).strip(),
            }
        remaining = max(1, int(remaining_raw))

        display_args = list(args)
        run_args = list(args)
        tool = Path(run_args[0]).name.lower()
        if tool in {"python", "python3", "py"}:
            run_args[0] = sys.executable
        if tool == "echo":
            echoed = " ".join(run_args[1:])
            output_parts.append(echoed)
            completed_segments.append(
                {"args": display_args, "returncode": 0, "duration_sec": 0.0}
            )
            continue

        segment_started = time.time()
        try:
            completed = subprocess.run(
                run_args,
                cwd=cwd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=remaining,
                check=False,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout if isinstance(exc.stdout, str) else ""
            stderr = exc.stderr if isinstance(exc.stderr, str) else ""
            output_parts.append((stdout or "") + (stderr or ""))
            return {
                "ok": False,
                "validation_ok": False,
                "command": command,
                "error": f"validation segment timed out after {remaining}s",
                "duration_sec": round(time.time() - started, 2),
                "segments": completed_segments,
                "output": "\n".join(output_parts).strip(),
            }
        except Exception as exc:
            return {
                "ok": False,
                "validation_ok": False,
                "command": command,
                "error": f"validation execution error: {exc}",
                "duration_sec": round(time.time() - started, 2),
                "segments": completed_segments,
                "output": "\n".join(output_parts).strip(),
            }

        output_parts.append((completed.stdout or "") + (completed.stderr or ""))
        segment_record = {
            "args": display_args,
            "actual_args": run_args,
            "returncode": completed.returncode,
            "duration_sec": round(time.time() - segment_started, 2),
        }
        completed_segments.append(segment_record)

        if completed.returncode != 0:
            return {
                "ok": False,
                "validation_ok": False,
                "command": command,
                "error": f"validation segment failed with exit {completed.returncode}",
                "duration_sec": round(time.time() - started, 2),
                "segments": completed_segments,
                "output": "\n".join(output_parts).strip(),
            }

    return {
        "ok": True,
        "validation_ok": True,
        "command": command,
        "error": None,
        "duration_sec": round(time.time() - started, 2),
        "segments": completed_segments,
        "output": "\n".join(output_parts).strip(),
    }


def _safe_rel_path(raw: Any) -> str | None:
    text = str(raw or "").strip().replace("\\", "/")
    if not text or text.startswith("/"):
        return None
    parts = [part for part in text.split("/") if part]
    if not parts or any(part == ".." for part in parts):
        return None
    if any(part.lower() in FORBIDDEN_PATH_PARTS for part in parts):
        return None
    return "/".join(parts)


def _plan_paths(plan: list[dict[str, Any]]) -> list[str]:
    paths: list[str] = []
    for op in plan:
        rel = _safe_rel_path(op.get("relative_path") or op.get("file"))
        if rel and rel not in paths:
            paths.append(rel)
    return paths


def _metadata_path_issue(plan: list[dict[str, Any]], case: dict[str, Any]) -> str | None:
    paths = _plan_paths(plan)
    if not paths:
        return "patch proposal has no clear relative target path"

    forbidden = {
        str(path).replace("\\", "/")
        for path in (case.get("forbidden_changed_files") or [])
    }
    touched_forbidden = [path for path in paths if path in forbidden]
    if touched_forbidden:
        return f"patch proposal touches forbidden benchmark files: {touched_forbidden}"

    expected = {
        str(path).replace("\\", "/")
        for path in (case.get("expected_changed_files") or [])
    }
    if expected:
        outside_expected = [path for path in paths if path not in expected]
        if outside_expected:
            return f"patch proposal touches files outside expected benchmark files: {outside_expected}"

    return None


def _patch_payload_to_plan(payload: dict[str, Any]) -> tuple[list[dict[str, Any]] | None, str | None]:
    plan = payload.get("patch_plan")
    if isinstance(plan, list) and plan:
        normalized_plan: list[dict[str, Any]] = []
        for op in plan:
            if not isinstance(op, dict):
                return None, "patch_plan contains a non-object operation"
            normalized_plan.append(dict(op))
        return normalized_plan, None

    candidate = payload.get("patch_candidate")
    if isinstance(candidate, dict):
        rel = _safe_rel_path(candidate.get("relative_path") or candidate.get("file"))
        if not rel:
            return None, "patch_candidate has no safe relative path"
        target = candidate.get("target_snippet")
        patched = candidate.get("patched_snippet")
        if not isinstance(target, str) or not isinstance(patched, str):
            return None, "patch_candidate target_snippet/patched_snippet must be strings"
        return [
            {
                "op": "replace_snippet",
                "relative_path": rel,
                "target_snippet": target,
                "patched_snippet": patched,
            }
        ], None

    return None, "model did not return patch_plan or patch_candidate"


def _iter_context_files(temp_repo: Path, case: dict[str, Any]) -> list[Path]:
    preferred: list[Path] = []
    for rel in (case.get("expected_changed_files") or []) + (case.get("forbidden_changed_files") or []):
        safe = _safe_rel_path(rel)
        if not safe:
            continue
        path = temp_repo / safe
        if path.is_file() and path not in preferred:
            preferred.append(path)

    all_files: list[Path] = []
    for path in temp_repo.rglob("*"):
        if not path.is_file():
            continue
        try:
            rel_parts = path.relative_to(temp_repo).parts
        except ValueError:
            continue
        if any(part.lower() in FORBIDDEN_PATH_PARTS for part in rel_parts):
            continue
        if path.suffix.lower() not in SOURCE_EXTENSIONS:
            continue
        if path not in preferred:
            all_files.append(path)

    return preferred + sorted(all_files)[:12]


def _file_context(temp_repo: Path, case: dict[str, Any], max_chars: int = 30000) -> str:
    chunks: list[str] = []
    used = 0
    for path in _iter_context_files(temp_repo, case):
        rel = path.relative_to(temp_repo).as_posix()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        chunk = f"\n--- FILE: {rel} ---\n{text[:5000]}\n"
        if used + len(chunk) > max_chars:
            break
        chunks.append(chunk)
        used += len(chunk)
    return "".join(chunks)


def _generate_patch_payload(
    *,
    temp_repo: Path,
    item: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any] | None, str]:
    from agents.gemini_client import run_gemini_request_2
    from core.json_utils import extract_json_block

    prompt = f"""You are generating a patch proposal inside an isolated temporary benchmark repo.
Do not modify any real repository. Return JSON only.

Background plan item:
{json.dumps(item, indent=2, ensure_ascii=False)}

Benchmark case metadata:
- name: {case.get("name")}
- language: {case.get("language")}
- category: {case.get("category")}
- expected_changed_files: {case.get("expected_changed_files") or []}
- forbidden_changed_files: {case.get("forbidden_changed_files") or []}
- validation_command: fixed by metadata; do not include or invent commands

Benchmark prompt:
{case.get("prompt") or ""}

Repository files:
{_file_context(temp_repo, case)}

Return ONLY valid JSON in this shape:
{{
  "summary": "short explanation",
  "patch_candidate": null,
  "patch_plan": [
    {{
      "op": "replace_snippet",
      "relative_path": "path/from/repo/root",
      "target_snippet": "verbatim existing snippet",
      "patched_snippet": "replacement snippet"
    }}
  ],
  "needs_human_review": true
}}

Rules:
- Use either patch_candidate or patch_plan, not both.
- Prefer one replace_snippet operation against an expected_changed_files path.
- Do not touch forbidden_changed_files.
- Do not create files unless the benchmark prompt explicitly allows it.
- If no safe patch can be proposed, set patch_candidate=null and patch_plan=null.
- Never include shell commands from your own output.
"""
    raw = run_gemini_request_2(prompt=prompt, repo_path=str(temp_repo)) or ""
    parsed = extract_json_block(raw)
    return (parsed if isinstance(parsed, dict) else None), raw


def _slug(text: str, fallback: str = "item") -> str:
    safe = []
    for ch in text.lower():
        if ch.isalnum():
            safe.append(ch)
        elif safe and safe[-1] != "-":
            safe.append("-")
    value = "".join(safe).strip("-")
    return value[:60] or fallback


def _copy_case_repo(case_file: Path, destination_parent: Path) -> Path:
    source = case_file.parent / "buggy_repo"
    if not source.is_dir():
        raise FileNotFoundError(f"benchmark case has no buggy_repo: {source}")
    target = destination_parent / "repo"
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(
            ".git",
            ".agent",
            "__pycache__",
            ".pytest_cache",
            "node_modules",
            "target",
            "dist",
            "build",
            ".venv",
            "venv",
        ),
    )
    return target


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _maybe_create_lesson_candidate(
    *,
    item_dir: Path,
    item: dict[str, Any],
    apply_result: dict[str, Any],
    validation: dict[str, Any],
    create_lesson_candidates: bool,
) -> dict[str, Any]:
    if not create_lesson_candidates:
        return {}
    if item.get("human_approved_for_proposal") is not True:
        return {}
    if apply_result.get("success") is not True:
        return {}
    if validation.get("validation_ok") is not True:
        return {}

    source_report = str(item_dir)
    from core.lesson_store import find_lesson_by_source_report

    existing = find_lesson_by_source_report("patch_proposal", source_report)
    if existing:
        return {
            "lesson_candidate_created": False,
            "lesson_already_exists": True,
            "lesson_message": "lesson already exists",
            "lesson_id": existing.get("id"),
            "lesson_status": existing.get("status"),
        }

    from scripts.create_lesson_from_proposal import create_lesson_from_proposal

    lesson = create_lesson_from_proposal(item_dir)
    if lesson.get("already_exists"):
        return {
            "lesson_candidate_created": False,
            "lesson_already_exists": True,
            "lesson_message": "lesson already exists",
            "lesson_id": lesson.get("id"),
            "lesson_status": lesson.get("status"),
        }
    return {
        "lesson_candidate_created": True,
        "lesson_already_exists": False,
        "lesson_id": lesson.get("id"),
        "lesson_status": lesson.get("status"),
    }


def _process_item(
    *,
    item: dict[str, Any],
    idx: int,
    run_dir: Path,
    validation_timeout_sec: int,
    create_lesson_candidates: bool = False,
) -> dict[str, Any]:
    case_name = str(item.get("case_name") or "").strip()
    item_dir = run_dir / f"{idx:02d}-{_slug(case_name)}"
    item_dir.mkdir(parents=True, exist_ok=True)
    _write_json(item_dir / "item.json", item)

    source_report = _resolve_source_report(item.get("source_benchmark_report"))
    if source_report is None:
        return {"case_name": case_name, "status": "skipped", "reason": "missing or unsafe source benchmark report"}

    report = _load_json(source_report)
    if report is None:
        return {"case_name": case_name, "status": "skipped", "reason": "source benchmark report could not be parsed"}

    if not case_name or _find_report_result(report, case_name) is None:
        return {"case_name": case_name, "status": "skipped", "reason": "target case is not present in source report"}

    loaded_case = _load_case_metadata(case_name, report)
    if loaded_case is None:
        return {"case_name": case_name, "status": "skipped", "reason": "could not resolve benchmark case metadata"}
    case_file, case = loaded_case
    _write_json(item_dir / "case.json", case)

    validation_command = str(case.get("validation_command") or "").strip()
    _segments, validation_issue = _split_validation_command(validation_command)
    if validation_issue:
        return {"case_name": case_name, "status": "skipped", "reason": validation_issue}

    with tempfile.TemporaryDirectory(prefix="patch-proposal-", ignore_cleanup_errors=True) as temp_dir:
        temp_root = Path(temp_dir)
        temp_repo = _copy_case_repo(case_file, temp_root)

        payload, raw = _generate_patch_payload(temp_repo=temp_repo, item=item, case=case)
        (item_dir / "raw_model_response.txt").write_text(raw, encoding="utf-8")

        if not isinstance(payload, dict):
            return {
                "case_name": case_name,
                "status": "proposal_failed",
                "reason": "model did not return parseable JSON",
            }

        _write_json(item_dir / "patch_proposal.json", payload)
        plan, plan_issue = _patch_payload_to_plan(payload)
        if plan_issue or plan is None:
            return {"case_name": case_name, "status": "proposal_skipped", "reason": plan_issue}

        metadata_issue = _metadata_path_issue(plan, case)
        if metadata_issue:
            return {"case_name": case_name, "status": "proposal_blocked", "reason": metadata_issue}

        from core.run_lifecycle import run_patch_plan_with_artifacts

        apply_result = run_patch_plan_with_artifacts(
            str(temp_repo),
            plan,
            validation_command=None,
            user_query=str(item.get("title") or case.get("prompt") or case_name),
            control_result={"item": item, "case": case, "proposal": payload},
            source="proposal_queue",
        )
        _write_json(item_dir / "apply_result.json", apply_result)
        diff_text = "\n\n".join(str(diff) for diff in (apply_result.get("diffs") or []) if diff)
        (item_dir / "diff.patch").write_text(diff_text, encoding="utf-8")

        if not apply_result.get("success"):
            return {
                "case_name": case_name,
                "status": "proposal_apply_failed",
                "reason": apply_result.get("error") or apply_result.get("message") or "patch did not apply",
            }

        validation = _run_validation_command(
            validation_command,
            cwd=temp_repo,
            timeout_sec=max(1, validation_timeout_sec),
        )
        _write_json(item_dir / "validation.json", validation)
        (item_dir / "validation.log").write_text(validation.get("output") or "", encoding="utf-8")

        proposal_md = build_proposal_markdown(
            case_name=case_name,
            case=case,
            payload=payload,
            plan=plan,
            validation=validation,
            validation_command=validation_command,
            source_report_name=source_report.name,
            diff_text=diff_text,
        )
        (item_dir / "proposal.md").write_text(proposal_md, encoding="utf-8")

        result = {
            "case_name": case_name,
            "status": "proposal_validated" if validation.get("validation_ok") else "proposal_validation_failed",
            "validation_ok": validation.get("validation_ok"),
            "artifact_dir": str(item_dir),
            "changed_files": _plan_paths(plan),
        }
        if validation.get("validation_ok") is True:
            try:
                result.update(
                    _maybe_create_lesson_candidate(
                        item_dir=item_dir,
                        item=item,
                        apply_result=apply_result,
                        validation=validation,
                        create_lesson_candidates=create_lesson_candidates,
                    )
                )
            except Exception as exc:
                result.update(
                    {
                        "lesson_candidate_created": False,
                        "lesson_error": f"{type(exc).__name__}: {exc}",
                    }
                )
        return result


def _normalize_text(value: Any, fallback: str = "") -> str:
    if not isinstance(value, str):
        return fallback
    stripped = value.strip()
    return stripped if stripped else fallback


def _format_what_was_wrong(case: dict[str, Any], payload: dict[str, Any]) -> str:
    """Prefer model-reported issues; fall back to the benchmark case prompt.

    The case prompt is the canonical description of the bug in the benchmark
    suite; reusing it gives the human a self-contained explanation instead of
    relying on the model's terse summary.
    """
    issues = payload.get("issues")
    if isinstance(issues, list):
        bullets = [
            f"- {item.strip()}"
            for item in issues
            if isinstance(item, str) and item.strip()
        ]
        if bullets:
            return "\n".join(bullets)

    prompt = _normalize_text(case.get("prompt"))
    if prompt:
        return prompt
    return "_No bug description available — neither `payload.issues` nor `case.prompt` were populated._"


def _format_concept(case: dict[str, Any], lessons: list[dict[str, Any]]) -> str:
    language = _normalize_text(case.get("language"), "unknown")
    category = _normalize_text(case.get("category"), "unknown")
    difficulty = _normalize_text(case.get("difficulty"))

    parts = [f"- Discipline area: `{language}` · `{category}`"]
    if difficulty:
        parts.append(f"- Difficulty: `{difficulty}`")

    if lessons:
        parts.append("")
        parts.append("Active lessons covering this area:")
        for lesson in lessons[:3]:
            title = _normalize_text(lesson.get("title"), "(untitled lesson)")
            summary = _normalize_text(lesson.get("summary"))
            line = f"- **{title}**"
            if summary:
                # Keep one sentence to avoid drowning the proposal.
                first = summary.split(". ")[0].rstrip(".")
                line += f" — {first}."
            parts.append(line)
    return "\n".join(parts)


def _format_watch_pattern(
    case: dict[str, Any],
    plan: list[dict[str, Any]],
    lessons: list[dict[str, Any]],
) -> str:
    parts: list[str] = []

    plan_paths = _plan_paths(plan)
    expected = case.get("expected_changed_files") or []
    forbidden = case.get("forbidden_changed_files") or []

    if plan_paths:
        parts.append("Files touched by this patch — similar bugs often cluster here:")
        for path in plan_paths:
            parts.append(f"- `{path}`")

    if expected:
        parts.append("")
        parts.append("Files the benchmark expects to change (compare your patch against these):")
        for path in expected:
            parts.append(f"- `{path}`")

    if forbidden:
        parts.append("")
        parts.append("Files the benchmark forbids touching (Patch Safety gate covers these at apply time):")
        for path in forbidden:
            parts.append(f"- `{path}`")

    tag_set: set[str] = set()
    for lesson in lessons[:5]:
        tags = lesson.get("tags")
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag.strip():
                    tag_set.add(tag.strip())
    if tag_set:
        parts.append("")
        parts.append("Lesson tags that match this case (search Memory tab → Lessons by these):")
        parts.append(", ".join(f"`{t}`" for t in sorted(tag_set)))

    if not parts:
        return "_No related files or lessons surfaced for this case yet._"
    return "\n".join(parts)


def _lookup_active_lessons(case: dict[str, Any]) -> list[dict[str, Any]]:
    """Best-effort lesson retrieval; silent on failure so proposal.md still writes."""
    try:
        from core.lesson_retrieval import find_active_lessons

        return find_active_lessons(
            case_name=_normalize_text(case.get("name")) or None,
            language=_normalize_text(case.get("language")) or None,
            category=_normalize_text(case.get("category")) or None,
            limit=5,
        )
    except Exception:
        return []


def build_proposal_markdown(
    *,
    case_name: str,
    case: dict[str, Any],
    payload: dict[str, Any],
    plan: list[dict[str, Any]],
    validation: dict[str, Any],
    validation_command: str,
    source_report_name: str,
    diff_text: str,
) -> str:
    """Render a tutor-style proposal.md.

    Pulls from artifacts already on disk:
      - case.prompt          → "What was wrong"
      - payload.summary      → "Why this patch works"
      - case.language/category, active lessons → "Concept to learn"
      - plan paths, expected/forbidden files, lesson tags → "Patterns to watch for"
      - diff_text            → "Diff"

    No LLM calls. If a section has no data it shows a clear muted message
    instead of being silently omitted, so a human reader knows what is
    missing.
    """
    lessons = _lookup_active_lessons(case)

    language = _normalize_text(case.get("language"), "unknown")
    category = _normalize_text(case.get("category"), "unknown")
    difficulty = _normalize_text(case.get("difficulty"), "unknown")
    summary = _normalize_text(payload.get("summary"), "_No summary provided by the model._")
    validation_ok = validation.get("validation_ok")
    validation_label = "✓ passed" if validation_ok is True else (
        "✗ failed" if validation_ok is False else "(not run)"
    )

    lines: list[str] = []

    # Header — keeps the existing fields readable at the top, but reformatted
    # so the explanation sections below are the focus.
    lines.append(f"# Patch Proposal: {case_name}")
    lines.append("")
    lines.append(
        f"> `{language}` · `{category}` · `{difficulty}` · "
        f"validation `{validation_command}` → {validation_label}"
    )
    lines.append(f"> Source benchmark report: `{source_report_name}`")
    lines.append("> Apply policy: proposal only; human approval is still required.")
    lines.append("")

    lines.append("## What was wrong")
    lines.append("")
    lines.append(_format_what_was_wrong(case, payload))
    lines.append("")

    lines.append("## Why this patch works")
    lines.append("")
    lines.append(summary)
    lines.append("")

    lines.append("## Concept to learn")
    lines.append("")
    lines.append(_format_concept(case, lessons))
    lines.append("")

    lines.append("## Similar patterns to watch for")
    lines.append("")
    lines.append(_format_watch_pattern(case, plan, lessons))
    lines.append("")

    lines.append("## Diff")
    lines.append("")
    lines.append("```diff")
    lines.append(diff_text or "(no diff)")
    lines.append("```")
    lines.append("")

    return "\n".join(lines)


def render_summary_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# Patch Proposal Queue",
        "",
        f"- Created at: `{summary.get('created_at')}`",
        f"- Source plan: `{summary.get('source_plan')}`",
        f"- Max items: `{summary.get('max_items')}`",
        f"- Processed: `{len(summary.get('processed') or [])}`",
        f"- Skipped: `{len(summary.get('skipped') or [])}`",
        "- Real repo modified: `False`",
        "- Apply policy: proposal only; human approval required.",
        "",
        "## Processed",
        "",
    ]
    processed = summary.get("processed") or []
    if not processed:
        lines.append("- No items processed.")
    else:
        for item in processed:
            lesson_bits = ""
            if item.get("lesson_already_exists"):
                lesson_bits = (
                    f" - lesson already exists: `{item.get('lesson_id')}` "
                    f"({item.get('lesson_status')})"
                )
            elif item.get("lesson_candidate_created"):
                lesson_bits = (
                    f" - lesson created: `{item.get('lesson_id')}` "
                    f"({item.get('lesson_status')})"
                )
            elif item.get("lesson_error"):
                lesson_bits = f" - lesson error: `{item.get('lesson_error')}`"
            lines.append(f"- `{item.get('case_name')}`: `{item.get('status')}`{lesson_bits}")
    lines.extend(["", "## Skipped", ""])
    skipped = summary.get("skipped") or []
    if not skipped:
        lines.append("- No skipped items.")
    else:
        for item in skipped:
            lines.append(f"- `{item.get('case_name') or 'unknown'}`: {item.get('reason')}")
    if summary.get("brain_stamp"):
        stamp = summary["brain_stamp"]
        lines.extend(
            [
                "",
                "## Brain Stamp",
                "",
                f"- Git SHA: `{stamp.get('git_sha') or 'unknown'}`",
                f"- Branch: `{stamp.get('git_branch') or 'unknown'}`",
                f"- Dirty: `{stamp.get('git_dirty')}` ({stamp.get('git_dirty_summary') or 'unknown'})",
                f"- Prompt/config hash: `{stamp.get('prompt_config_hash') or 'none'}`",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate gated patch proposal artifacts from a background Dream plan."
    )
    parser.add_argument("--max-items", type=int, default=1)
    parser.add_argument("--plan", help="Optional background_dream_plan_*.json path.")
    parser.add_argument("--validation-timeout-sec", type=int, default=60)
    parser.add_argument(
        "--create-lesson-candidates",
        action="store_true",
        help=(
            "After a human-approved proposal applies and validates in the "
            "isolated benchmark repo, create an idempotent candidate lesson "
            "from its proposal artifacts."
        ),
    )
    args = parser.parse_args()

    plan_path = Path(args.plan).resolve() if args.plan else _latest_plan()
    if plan_path is None or not plan_path.is_file():
        print(f"No background_dream_plan_*.json found in {REPORT_DIR}.")
        return 1

    plan = _load_json(plan_path)
    if plan is None:
        print(f"Could not parse plan JSON: {plan_path}")
        return 1

    PROPOSAL_ROOT.mkdir(parents=True, exist_ok=True)
    run_dir = PROPOSAL_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S")
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = PROPOSAL_ROOT / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=False)

    items = [item for item in (plan.get("items") or []) if isinstance(item, dict)]
    safe_items = [item for item in items if item.get("human_approved_for_proposal") is True]
    max_items = max(0, args.max_items)

    summary: dict[str, Any] = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "source_plan": str(plan_path),
        "max_items": max_items,
        "brain_stamp": plan.get("brain_stamp") or {},
        "processed": [],
        "skipped": [],
        "policy": {
            "real_repo_modified": False,
            "automatic_apply": False,
            "approval_required": True,
            "validation_source": "benchmark case metadata only",
            "create_lesson_candidates": bool(args.create_lesson_candidates),
        },
    }

    for item in items:
        if item.get("human_approved_for_proposal") is True:
            continue
        summary["skipped"].append(
            {
                "case_name": item.get("case_name"),
                "kind": item.get("kind"),
                "reason": "human_approved_for_proposal is not explicitly true",
            }
        )

    for idx, item in enumerate(safe_items[:max_items], start=1):
        try:
            result = _process_item(
                item=item,
                idx=idx,
                run_dir=run_dir,
                validation_timeout_sec=args.validation_timeout_sec,
                create_lesson_candidates=args.create_lesson_candidates,
            )
        except Exception as exc:
            result = {
                "case_name": item.get("case_name"),
                "status": "proposal_error",
                "reason": repr(exc),
            }
        summary["processed"].append(result)
        print(f"{result.get('case_name')}: {result.get('status')}")
        if result.get("lesson_already_exists"):
            print(
                "  lesson already exists: "
                f"id={result.get('lesson_id')} status={result.get('lesson_status')}"
            )
        elif result.get("lesson_candidate_created"):
            print(
                "  created lesson: "
                f"id={result.get('lesson_id')} status={result.get('lesson_status')}"
            )
        elif result.get("lesson_error"):
            print(f"  lesson error: {result.get('lesson_error')}")

    if len(safe_items) > max_items:
        for item in safe_items[max_items:]:
            summary["skipped"].append(
                {
                    "case_name": item.get("case_name"),
                    "kind": item.get("kind"),
                    "reason": "beyond --max-items limit",
                }
            )

    _write_json(run_dir / "summary.json", summary)
    (run_dir / "summary.md").write_text(render_summary_markdown(summary), encoding="utf-8")

    print(f"Patch proposal queue artifacts: {run_dir}")
    print(f"Processed: {len(summary['processed'])}")
    print(f"Skipped: {len(summary['skipped'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
