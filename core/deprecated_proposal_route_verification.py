"""Phase A.14 - Deprecated Proposal Route Verification.

Report-only verification for the legacy/manual route:
    /lessons/create-candidate-from-proposal

The verifier uses deterministic repository text scans and Python AST parsing.
It does not import Flask, model clients, DB modules, benchmark runners, lesson
writers, patch executors, or subprocess. It writes only JSON/Markdown audit
artifacts when explicitly asked.
"""
from __future__ import annotations

import ast
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERIFICATION_VERSION = "A.14"
ROUTE_PATH = "/lessons/create-candidate-from-proposal"
ROUTE_FUNCTION = "lessons_create_candidate_from_proposal_route"
ROUTE_FILE = "web/app.py"
ROUTE_METHODS = ["POST"]

CLASS_ACTIVE_CALLER_FOUND = "active_caller_found"
CLASS_TEST_ONLY = "test_only"
CLASS_DOCS_ONLY = "docs_only"
CLASS_MANUAL_LEGACY_SURFACE = "manual_legacy_surface"
CLASS_UNUSED_BUT_SAFE = "unused_but_safe"
CLASS_UNSAFE_NEEDS_FIX = "unsafe_needs_fix"

REC_KEEP = "keep"
REC_KEEP_AND_DOCUMENT = "keep_and_document"
REC_FREEZE = "freeze"
REC_FREEZE_AND_DEPRECATE_LATER = "freeze_and_deprecate_later"
REC_FIX_BEFORE_FREEZE = "fix_before_freeze"
REC_CUT_LATER_AFTER_DEPRECATION_WINDOW = "cut_later_after_deprecation_window"

_IGNORE_DIR_PARTS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "tmp",
    "tmp_tests",
    ".venv",
    "venv",
    "node_modules",
}
_SELF_RELATIVE_FILES = {
    "core/deprecated_proposal_route_verification.py",
    "scripts/verify_deprecated_proposal_route.py",
}
_REFERENCE_ONLY_FILES = {
    "core/lesson_entry_audit.py",
    "core/proposal_lesson_consolidation_plan.py",
    "scripts/create_lesson_entry_audit.py",
    "scripts/create_proposal_lesson_consolidation_plan.py",
}
_PROPOSAL_BYPASS_MARKERS = (
    "maybe_create_lesson_candidate_from_proposal",
    "seed_lessons_from_proposals",
)

_UI_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("fetch", re.compile(r"\bfetch\s*\(\s*['\"]" + re.escape(ROUTE_PATH))),
    ("form_action", re.compile(r"\baction\s*=\s*['\"]" + re.escape(ROUTE_PATH))),
    ("data_attribute", re.compile(r"\bdata-[\w-]+\s*=\s*['\"]" + re.escape(ROUTE_PATH))),
    (
        "js_constant",
        re.compile(r"\b(?:const|let|var)\s+\w+\s*=\s*['\"]" + re.escape(ROUTE_PATH)),
    ),
)


def _repo_path(repo_path: str | Path | None) -> Path:
    return Path(repo_path or Path.cwd()).resolve()


def _relative_posix(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _is_ignored(path: Path, root: Path) -> bool:
    rel = _relative_posix(path, root)
    parts = set(Path(rel).parts)
    if parts & _IGNORE_DIR_PARTS:
        return True
    return rel.startswith(".agent/audits/")


def _iter_text_files(root: Path, starts: list[Path] | None = None) -> list[Path]:
    files: list[Path] = []
    stack = list(starts or [root])
    while stack:
        current = stack.pop()
        if _is_ignored(current, root):
            continue
        if current.is_file():
            files.append(current)
            continue
        try:
            children = sorted(current.iterdir(), key=lambda p: p.name)
        except OSError:
            continue
        for path in children:
            if _is_ignored(path, root):
                continue
            if path.is_dir():
                stack.append(path)
            elif path.is_file():
                files.append(path)
    return sorted(files, key=lambda p: _relative_posix(p, root))


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _line_matches(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = _relative_posix(path, root)
    if rel in _SELF_RELATIVE_FILES:
        return []

    matches: list[dict[str, Any]] = []
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return matches

    for lineno, line in enumerate(lines, start=1):
        if ROUTE_PATH in line:
            matches.append(
                {
                    "file": rel,
                    "line": lineno,
                    "pattern": "route_path",
                    "text": line.strip()[:240],
                }
            )
        if ROUTE_FUNCTION in line:
            matches.append(
                {
                    "file": rel,
                    "line": lineno,
                    "pattern": "function_name",
                    "text": line.strip()[:240],
                }
            )
    return matches


def _ui_matches(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = _relative_posix(path, root)
    matches: list[dict[str, Any]] = []
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return matches

    for lineno, line in enumerate(lines, start=1):
        for pattern_name, pattern in _UI_PATTERNS:
            if pattern.search(line):
                matches.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "pattern": pattern_name,
                        "text": line.strip()[:240],
                    }
                )
    return matches


def _bypass_reference_matches(path: Path, root: Path) -> list[dict[str, Any]]:
    rel = _relative_posix(path, root)
    if rel in _SELF_RELATIVE_FILES:
        return []

    matches: list[dict[str, Any]] = []
    try:
        lines = _read_text(path).splitlines()
    except OSError:
        return matches
    for lineno, line in enumerate(lines, start=1):
        for marker in _PROPOSAL_BYPASS_MARKERS:
            if marker in line:
                matches.append(
                    {
                        "file": rel,
                        "line": lineno,
                        "pattern": marker,
                        "text": line.strip()[:240],
                    }
                )
    return matches


def _category_for(rel: str) -> str | None:
    parts = Path(rel).parts
    if not parts:
        return None
    first = parts[0]
    if first == "tests":
        return "tests"
    if first == "web" and len(parts) >= 2 and parts[1] in {"templates", "static"}:
        return "ui"
    if first in {"scripts", "core"}:
        return "scripts_core"
    if first == "docs" or rel in {"README.md", "SETUP.md"}:
        return "docs"
    return None


def scan_route_callers(repo_path: str | Path) -> dict[str, list[dict[str, Any]]]:
    """Scan repo text for route callers and route mentions.

    The main caller buckets intentionally exclude generated audit artifacts and
    known static audit source modules. Those reference files are useful context,
    but they are not runtime or UI callers of the route.
    """
    root = _repo_path(repo_path)
    callers: dict[str, list[dict[str, Any]]] = {
        "ui": [],
        "tests": [],
        "scripts_core": [],
        "docs": [],
        "bypass_candidate_references": [],
        "reference_only_mentions": [],
    }

    starts = [
        root / "web" / "templates",
        root / "web" / "static",
        root / "tests",
        root / "scripts",
        root / "core",
        root / "docs",
        root / "README.md",
        root / "SETUP.md",
    ]
    starts = [path for path in starts if path.exists()]

    for path in _iter_text_files(root, starts):
        rel = _relative_posix(path, root)
        category = _category_for(rel)
        if category is None:
            continue

        if category == "ui":
            callers["ui"].extend(_ui_matches(path, root))
            continue

        matches = _line_matches(path, root)
        if not matches:
            if category == "scripts_core":
                callers["bypass_candidate_references"].extend(
                    _bypass_reference_matches(path, root)
                )
            continue

        if category == "scripts_core" and rel in _REFERENCE_ONLY_FILES:
            callers["reference_only_mentions"].extend(matches)
            continue
        callers[category].extend(matches)

    for key in callers:
        callers[key] = sorted(
            callers[key],
            key=lambda m: (m.get("file", ""), int(m.get("line", 0)), m.get("pattern", "")),
        )
    return callers


def _literal_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_string_list(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.List, ast.Tuple)):
        values: list[str] = []
        for elt in node.elts:
            value = _literal_string(elt)
            if value:
                values.append(value)
        return values
    value = _literal_string(node)
    return [value] if value else []


def _route_decorator_info(node: ast.FunctionDef) -> tuple[str, list[str]] | None:
    for dec in node.decorator_list:
        if not isinstance(dec, ast.Call):
            continue
        func = dec.func
        is_route = (
            isinstance(func, ast.Attribute)
            and func.attr == "route"
        ) or (
            isinstance(func, ast.Name)
            and func.id == "route"
        )
        if not is_route or not dec.args:
            continue
        path = _literal_string(dec.args[0])
        if path != ROUTE_PATH:
            continue
        methods: list[str] = []
        for keyword in dec.keywords:
            if keyword.arg == "methods":
                methods = _literal_string_list(keyword.value)
        return path, methods or ["GET"]
    return None


def detect_route_definition(repo_path: str | Path) -> dict[str, Any]:
    root = _repo_path(repo_path)
    file_path = root / ROUTE_FILE
    result: dict[str, Any] = {
        "defined": False,
        "file": ROUTE_FILE,
        "function_name": None,
        "http_methods": [],
        "path": ROUTE_PATH,
        "line": None,
    }
    if not file_path.is_file():
        result["error"] = "route file missing"
        return result

    try:
        tree = ast.parse(_read_text(file_path), filename=str(file_path))
    except SyntaxError as e:
        result["error"] = f"syntax error: {e}"
        return result

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        info = _route_decorator_info(node)
        if info is None:
            continue
        path, methods = info
        return {
            "defined": True,
            "file": ROUTE_FILE,
            "function_name": node.name,
            "http_methods": methods,
            "path": path,
            "line": node.lineno,
        }
    return result


def _route_function_node(repo_path: str | Path) -> ast.FunctionDef | None:
    root = _repo_path(repo_path)
    path = root / ROUTE_FILE
    if not path.is_file():
        return None
    try:
        tree = ast.parse(_read_text(path), filename=str(path))
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == ROUTE_FUNCTION:
            return node
    return None


def _call_names(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                names.add(func.id)
            elif isinstance(func, ast.Attribute):
                names.add(func.attr)
    return names


def _assigned_attributes(node: ast.AST | None) -> set[str]:
    if node is None:
        return set()
    names: set[str] = set()
    for child in ast.walk(node):
        if isinstance(child, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
            targets = child.targets if isinstance(child, ast.Assign) else [child.target]
            for target in targets:
                if isinstance(target, ast.Attribute):
                    names.add(target.attr)
                elif isinstance(target, ast.Name):
                    names.add(target.id)
    return names


def analyze_route_safety(repo_path: str | Path) -> dict[str, Any]:
    """Return route safety evidence without importing runtime modules."""
    root = _repo_path(repo_path)
    route_node = _route_function_node(root)
    route_calls = _call_names(route_node)
    route_assigns = _assigned_attributes(route_node)

    lesson_auto_path = root / "core" / "lesson_auto_candidates.py"
    seeder_path = root / "scripts" / "seed_lessons_from_proposals.py"
    create_path = root / "scripts" / "create_lesson_from_proposal.py"

    lesson_auto_text = _read_text(lesson_auto_path) if lesson_auto_path.is_file() else ""
    seeder_text = _read_text(seeder_path) if seeder_path.is_file() else ""
    create_text = _read_text(create_path) if create_path.is_file() else ""

    route_delegates_to_p5 = "maybe_create_lesson_candidate_from_proposal" in route_calls
    route_passes_enabled_true = False
    if route_node is not None:
        for child in ast.walk(route_node):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if not isinstance(func, ast.Name) or func.id != "maybe_create_lesson_candidate_from_proposal":
                continue
            route_passes_enabled_true = any(
                keyword.arg == "enabled"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
                for keyword in child.keywords
            )

    inherited_a13_path = (
        "seed_lessons_from_proposals" in lesson_auto_text
        and "PROPOSAL_SOURCE = \"proposal_artifact\"" in lesson_auto_text
    )
    creates_proposal_artifact_records = (
        "SOURCE = \"proposal_artifact\"" in seeder_text
        or "CANONICAL_PROPOSAL_SOURCE = \"proposal_artifact\"" in create_text
    )
    creates_source_key_records = (
        "source_key" in seeder_text
        and "_proposal_source_hash" in seeder_text
    )
    preserves_legacy_duplicate_detection = (
        "find_lesson_by_source_report" in seeder_text
        and "patch_proposal" in seeder_text
    ) or (
        "find_lesson_by_source_report" in create_text
        and "LEGACY_PATCH_PROPOSAL_SOURCE" in create_text
    )
    no_direct_lesson_write_in_route = route_calls.isdisjoint(
        {"save_candidate_lesson", "save_raw_lesson_record", "promote_lesson"}
    )
    does_not_write_active_directly = (
        "LESSON_AUTO_ACTIVE" not in route_assigns
        and "active" not in route_calls
        and no_direct_lesson_write_in_route
    )
    lesson_auto_active_guard_inherited = (
        "LESSON_AUTO_ACTIVE = False" in seeder_text
        and "save_candidate_lesson" in seeder_text
    ) or (
        "LESSON_AUTO_ACTIVE = False" in create_text
        and "save_candidate_lesson" in create_text
    )
    does_not_bypass_lesson_auto_active_guard = (
        route_delegates_to_p5
        and route_passes_enabled_true
        and lesson_auto_active_guard_inherited
    )

    checks = {
        "route_delegates_to_p5": route_delegates_to_p5,
        "route_passes_enabled_true": route_passes_enabled_true,
        "inherited_a13_path": inherited_a13_path,
        "creates_proposal_artifact_records": creates_proposal_artifact_records,
        "creates_source_key_records": creates_source_key_records,
        "preserves_legacy_duplicate_detection": preserves_legacy_duplicate_detection,
        "does_not_write_active_directly": does_not_write_active_directly,
        "does_not_bypass_lesson_auto_active_guard": does_not_bypass_lesson_auto_active_guard,
        "no_direct_lesson_write_in_route": no_direct_lesson_write_in_route,
    }
    safe = all(checks.values())
    return {
        "safe": safe,
        "checks": checks,
        "summary": (
            "Route delegates to core.lesson_auto_candidates."
            "maybe_create_lesson_candidate_from_proposal, which inherits the A.13"
            " proposal_artifact/source_key path and legacy patch_proposal/source_report"
            " duplicate detection. The route itself performs no lesson write,"
            " promotion, direct active write, model call, patch apply, DB import, or"
            " subprocess call."
            if safe
            else "One or more route safety checks failed; inspect checks for details."
        ),
    }


def classify_route(
    *,
    route_defined: bool,
    callers: dict[str, list[dict[str, Any]]],
    safety: dict[str, Any],
) -> str:
    if not route_defined or not safety.get("safe"):
        return CLASS_UNSAFE_NEEDS_FIX
    if callers.get("ui") or callers.get("scripts_core"):
        return CLASS_ACTIVE_CALLER_FOUND
    if callers.get("tests") and callers.get("docs"):
        return CLASS_MANUAL_LEGACY_SURFACE
    if callers.get("tests"):
        return CLASS_TEST_ONLY
    if callers.get("docs"):
        return CLASS_DOCS_ONLY
    return CLASS_UNUSED_BUT_SAFE


def recommendation_for(classification: str) -> str:
    if classification == CLASS_ACTIVE_CALLER_FOUND:
        return REC_KEEP_AND_DOCUMENT
    if classification in {CLASS_TEST_ONLY, CLASS_MANUAL_LEGACY_SURFACE}:
        return REC_FREEZE_AND_DEPRECATE_LATER
    if classification == CLASS_DOCS_ONLY:
        return REC_KEEP_AND_DOCUMENT
    if classification == CLASS_UNUSED_BUT_SAFE:
        return REC_FREEZE
    if classification == CLASS_UNSAFE_NEEDS_FIX:
        return REC_FIX_BEFORE_FREEZE
    return REC_KEEP


def _count_callers(callers: dict[str, list[dict[str, Any]]]) -> dict[str, int]:
    return {
        "ui": len(callers.get("ui", [])),
        "tests": len(callers.get("tests", [])),
        "scripts_core": len(callers.get("scripts_core", [])),
        "docs": len(callers.get("docs", [])),
        "bypass_candidate_references": len(callers.get("bypass_candidate_references", [])),
        "reference_only_mentions": len(callers.get("reference_only_mentions", [])),
    }


def build_report(repo_path: str | Path | None = None) -> dict[str, Any]:
    root = _repo_path(repo_path)
    route = detect_route_definition(root)
    callers = scan_route_callers(root)
    safety = analyze_route_safety(root)
    classification = classify_route(
        route_defined=bool(route.get("defined")),
        callers=callers,
        safety=safety,
    )
    recommendation = recommendation_for(classification)

    return {
        "verification_version": VERIFICATION_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_path": str(root),
        "route": route,
        "callers": callers,
        "caller_counts": _count_callers(callers),
        "safety": safety,
        "classification": classification,
        "recommendation": recommendation,
        "guardrails": {
            "report_only": True,
            "no_route_deletion": True,
            "no_route_rename": True,
            "no_runtime_behavior_change": True,
            "no_lesson_creation": True,
            "no_promotion": True,
            "no_model_call": True,
            "no_patch_apply": True,
            "no_flask_import": True,
            "no_db_import": True,
            "no_subprocess": True,
        },
    }


def _format_matches(matches: list[dict[str, Any]]) -> list[str]:
    if not matches:
        return ["- none"]
    lines: list[str] = []
    for match in matches:
        lines.append(
            f"- `{match['file']}:{match['line']}` "
            f"({match['pattern']}): {match.get('text', '')}"
        )
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    route = report["route"]
    callers = report["callers"]
    safety = report["safety"]
    counts = report["caller_counts"]

    lines: list[str] = [
        "# Deprecated Proposal Route Verification",
        "",
        f"Generated: {report['generated_at']}",
        f"Version: `{report['verification_version']}`",
        f"Repo path: `{report.get('repo_path')}`",
        "",
        "## Route Definition",
        "",
        f"- Path: `{route['path']}`",
        f"- Defined: `{route['defined']}`",
        f"- File: `{route.get('file')}`",
        f"- Function: `{route.get('function_name')}`",
        f"- HTTP methods: `{route.get('http_methods')}`",
        f"- Line: `{route.get('line')}`",
        "",
        "## Caller Scan",
        "",
        f"- UI callers: `{counts['ui']}`",
        f"- Test callers: `{counts['tests']}`",
        f"- Scripts/core callers: `{counts['scripts_core']}`",
        f"- Docs mentions: `{counts['docs']}`",
        f"- Scripts/core bypass references: `{counts['bypass_candidate_references']}`",
        f"- Reference-only mentions: `{counts['reference_only_mentions']}`",
        "",
        "### UI",
        "",
        *_format_matches(callers.get("ui", [])),
        "",
        "### Tests",
        "",
        *_format_matches(callers.get("tests", [])),
        "",
        "### Scripts/Core",
        "",
        *_format_matches(callers.get("scripts_core", [])),
        "",
        "### Docs",
        "",
        *_format_matches(callers.get("docs", [])),
        "",
        "### Scripts/Core Bypass References",
        "",
        *_format_matches(callers.get("bypass_candidate_references", [])),
        "",
        "### Reference-Only Mentions",
        "",
        *_format_matches(callers.get("reference_only_mentions", [])),
        "",
        "## Safety",
        "",
        f"- Safe: `{safety['safe']}`",
        f"- Summary: {safety['summary']}",
        "",
    ]
    for key, value in safety["checks"].items():
        lines.append(f"- `{key}`: `{value}`")

    lines += [
        "",
        "## Classification",
        "",
        f"- Classification: **{report['classification']}**",
        f"- Recommendation: **{report['recommendation']}**",
        "- No deletion in A.14.",
        "",
        "## Guardrails",
        "",
    ]
    for key, value in report["guardrails"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.append("")
    return "\n".join(lines)


def write_artifacts(
    report: dict[str, Any],
    *,
    audits_root: str | Path,
) -> dict[str, str]:
    root = Path(audits_root)
    root.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    stem = f"{ts}_deprecated-proposal-route-verification"

    json_path = root / f"{stem}.json"
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    md_path = root / f"{stem}.md"
    md_path.write_text(render_markdown(report), encoding="utf-8")

    return {"json": str(json_path), "markdown": str(md_path)}
