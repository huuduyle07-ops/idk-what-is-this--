"""HARDEN.2 - Web Mutation Surface Audit (report-only).

This module inventories Flask routes, classifies their HTTP methods and risky
route keywords, and checks whether mutating routes are inside the HARDEN.1
central before_request gate. It never calls route handlers and never performs
model calls, patch application, validation, benchmark execution, worker launch,
network access, database writes, or policy/UI changes.
"""
from __future__ import annotations

import ast
import inspect
import json
from pathlib import Path
from typing import Any


REPORT_KIND = "web_mutation_surface_audit"
JSON_NAME = "web_mutation_surface_audit.json"
MD_NAME = "web_mutation_surface_audit.md"

STATUS_PASS = "pass"
STATUS_WARN = "pass_with_warnings"
STATUS_FAIL = "fail"

SAFE_METHODS: tuple[str, ...] = ("GET", "HEAD", "OPTIONS")
MUTATING_METHODS: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE")

HIGH_RISK_KEYWORDS: tuple[str, ...] = (
    "apply",
    "patch",
    "run",
    "benchmark",
    "validate",
    "worker",
    "dream",
    "replay",
    "janitor",
    "upload",
    "delete",
    "archive",
    "compose",
    "env",
    "harness",
    "mcp",
)

ARTIFACT_KEYWORDS: tuple[str, ...] = (
    "upload",
    "archive",
    "compose",
    "create",
    "export",
    "import",
    "promote",
)

DEFAULT_KNOWN_DANGEROUS_ROUTES: tuple[str, ...] = (
    "/apply_patch",
    "/apply_patch_plan",
    "/benchmarks/run",
    "/benchmarks/stop",
    "/dream/apply",
    "/dream/run",
    "/handoffs/run",
    "/harness/controls/apply-env",
    "/harness/controls/compose-apply",
    "/proposals/validate",
    "/replays/janitor/apply",
    "/worker-runs/import",
)

GUARDRAIL_NOTE = (
    "Web Mutation Surface Audit is report-only: it inspects Flask route metadata "
    "and local source registration hints, then writes JSON and Markdown artifacts. "
    "It does not call route handlers, call models, apply patches, run validation, "
    "run benchmarks, launch workers, execute Dream or Replay janitor actions, "
    "contact a network service, write to a database, change auth policy, or change UI behavior."
)

BOUNDARIES: tuple[str, ...] = (
    "HARDEN.2 is report-only.",
    "HARDEN.2 does not call models.",
    "HARDEN.2 does not apply patches.",
    "HARDEN.2 does not run validation.",
    "HARDEN.2 does not run benchmarks.",
    "HARDEN.2 does not launch workers.",
    "HARDEN.2 does not execute Dream actions.",
    "HARDEN.2 does not apply Replay janitor actions.",
    "HARDEN.2 does not contact network services.",
    "HARDEN.2 does not write to a database.",
    "HARDEN.2 does not change routes, auth policy, or UI behavior.",
    "HARDEN.2 writes only its audit artifacts.",
)


def _norm_path(value: Any) -> str:
    return str(value).replace("\\", "/")


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _method_list(methods: Any) -> list[str]:
    values = [str(m).upper() for m in (methods or []) if str(m).strip()]
    return sorted(set(values))


def _method_classification(methods: list[str]) -> str:
    method_set = set(methods)
    mutating = bool(method_set & set(MUTATING_METHODS))
    has_get = "GET" in method_set
    unknown = method_set - set(SAFE_METHODS) - set(MUTATING_METHODS)
    if unknown:
        return "unclear"
    if mutating and has_get:
        return "mixed"
    if mutating:
        return "mutating"
    return "read_only"


def _route_text(rule: str, endpoint: str, view_module: str) -> str:
    return f"{rule} {endpoint} {view_module}".lower().replace("_", "-")


def _risk_keywords(rule: str, endpoint: str = "", view_module: str = "") -> list[str]:
    text = _route_text(rule, endpoint, view_module)
    return [kw for kw in HIGH_RISK_KEYWORDS if kw in text]


def _categories(
    *,
    method_classification: str,
    risk_keywords: list[str],
    text: str,
) -> list[str]:
    cats: list[str] = []
    if method_classification == "read_only":
        cats.append("safe/read-only")
    if method_classification in {"mutating", "mixed"}:
        cats.append("mutating")
    if risk_keywords:
        cats.append("dangerous")
    if any(kw in text for kw in ARTIFACT_KEYWORDS):
        cats.append("artifact-writing")
    if "validate" in text or "validation" in text:
        cats.append("validation-running")
    if "benchmark" in text:
        cats.append("benchmark-running")
    if "worker" in text or "run" in text:
        cats.append("worker-launching")
    if "replay" in text or "janitor" in text:
        cats.append("replay/janitor-related")
    if "mcp" in text:
        cats.append("external-integration-related")
    return _dedupe(cats or ["safe/read-only"])


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _has_function(path: Path, name: str) -> bool:
    src = _read_text(path)
    if not src:
        return False
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return False
    return any(isinstance(node, ast.FunctionDef) and node.name == name for node in ast.walk(tree))


def _before_request_functions(app: Any) -> list[Any]:
    funcs: list[Any] = []
    mapping = getattr(app, "before_request_funcs", {}) or {}
    if isinstance(mapping, dict):
        for values in mapping.values():
            if isinstance(values, list):
                funcs.extend(values)
    return funcs


def _function_source_text(func: Any) -> str:
    try:
        return inspect.getsource(func)
    except (OSError, TypeError):
        return ""


def _auth_gate_summary(app: Any, repo_path: Path) -> dict[str, Any]:
    auth_path = repo_path / "web" / "auth_gate.py"
    app_path = repo_path / "web" / "app.py"
    app_source = _read_text(app_path)
    funcs = _before_request_functions(app)
    func_sources = "\n".join(_function_source_text(fn) for fn in funcs)
    before_names = [getattr(fn, "__name__", "") for fn in funcs]
    before_modules = [getattr(fn, "__module__", "") for fn in funcs]

    source_has_wiring = (
        "before_request" in app_source and "should_allow_mutation" in app_source
    )
    runtime_has_wiring = (
        bool(funcs)
        and (
            "should_allow_mutation" in func_sources
            or any(name == "_web_mutation_gate" for name in before_names)
        )
    )

    gate_module_exists = auth_path.is_file()
    gate_function_detected = _has_function(auth_path, "should_allow_mutation")
    before_request_wiring_detected = bool(runtime_has_wiring)
    central_gate_detected = bool(
        gate_module_exists and gate_function_detected and before_request_wiring_detected
    )

    return {
        "gate_module_path": _norm_path(auth_path),
        "gate_module_exists": gate_module_exists,
        "gate_function_detected": gate_function_detected,
        "before_request_function_count": len(funcs),
        "before_request_function_names": before_names,
        "before_request_function_modules": before_modules,
        "source_wiring_hint_detected": source_has_wiring,
        "before_request_wiring_detected": before_request_wiring_detected,
        "central_gate_detected": central_gate_detected,
    }


def _route_records(app: Any, central_gate_detected: bool) -> list[dict[str, Any]]:
    url_map = getattr(app, "url_map", None)
    iter_rules = getattr(url_map, "iter_rules", None)
    view_functions = getattr(app, "view_functions", {}) or {}
    if not iter_rules:
        return []

    routes: list[dict[str, Any]] = []
    for rule_obj in iter_rules():
        rule = str(getattr(rule_obj, "rule", ""))
        endpoint = str(getattr(rule_obj, "endpoint", ""))
        methods = _method_list(getattr(rule_obj, "methods", set()))
        safe_methods = [m for m in methods if m in SAFE_METHODS]
        mutating_methods = [m for m in methods if m in MUTATING_METHODS]
        method_class = _method_classification(methods)
        view = view_functions.get(endpoint)
        view_module = str(getattr(view, "__module__", ""))
        view_name = str(getattr(view, "__name__", ""))
        text = _route_text(rule, endpoint, view_module)
        keywords = _risk_keywords(rule, endpoint, view_module)
        cats = _categories(
            method_classification=method_class,
            risk_keywords=keywords,
            text=text,
        )

        notes: list[str] = []
        if mutating_methods:
            notes.append("mutating HTTP method")
        if method_class == "mixed":
            notes.append("mixed safe and mutating methods")
        if method_class == "unclear":
            notes.append("method classification unclear")
        if keywords and not mutating_methods and method_class == "read_only":
            notes.append("dangerous-sounding GET-only route")

        if mutating_methods:
            gate_status = "covered" if central_gate_detected else "missing"
        else:
            gate_status = "not_required"

        routes.append(
            {
                "rule": rule,
                "endpoint": endpoint,
                "view_module": view_module,
                "view_name": view_name,
                "methods": methods,
                "safe_methods": safe_methods,
                "mutating_methods": mutating_methods,
                "method_classification": method_class,
                "risk_keywords": keywords,
                "dangerous_sounding": bool(keywords),
                "categories": cats,
                "covered_by_auth_gate": bool(central_gate_detected) if mutating_methods else True,
                "gate_status": gate_status,
                "notes": notes,
            }
        )
    routes.sort(key=lambda item: (item["rule"], item["endpoint"]))
    return routes


def _literal_str(node: ast.AST) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _literal_methods(node: ast.AST | None) -> list[str]:
    if node is None:
        return ["GET"]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values = [_literal_str(elt) for elt in node.elts]
        return _method_list(values)
    value = _literal_str(node)
    return _method_list([value]) if value else []


def _route_def_from_call(node: ast.Call, function_name: str = "") -> dict[str, Any] | None:
    attr = getattr(node.func, "attr", "")
    if attr not in {"route", "add_url_rule"}:
        return None
    rule = _literal_str(node.args[0]) if node.args else ""
    methods_node: ast.AST | None = None
    for kw in node.keywords:
        if kw.arg == "methods":
            methods_node = kw.value
            break
    methods = _literal_methods(methods_node)
    return {
        "rule": rule,
        "methods": methods,
        "function_name": function_name,
        "risk_keywords": _risk_keywords(rule, function_name, ""),
    }


def _static_route_defs(path: Path) -> list[dict[str, Any]]:
    src = _read_text(path)
    if not src:
        return []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    defs: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    route_def = _route_def_from_call(dec, node.name)
                    if route_def:
                        defs.append(route_def)
        elif isinstance(node, ast.Call):
            route_def = _route_def_from_call(node)
            if route_def:
                defs.append(route_def)
    return defs


def _module_name(path: Path, repo_path: Path) -> str:
    try:
        rel = path.resolve().relative_to(repo_path.resolve())
    except ValueError:
        rel = path
    return ".".join(rel.with_suffix("").parts)


def _uninspected_route_modules(repo_path: Path, inspected_modules: set[str]) -> list[dict[str, Any]]:
    web_root = repo_path / "web"
    if not web_root.is_dir():
        return []
    records: list[dict[str, Any]] = []
    for path in sorted(web_root.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        route_defs = _static_route_defs(path)
        if not route_defs:
            continue
        module = _module_name(path, repo_path)
        if module in inspected_modules:
            continue
        dangerous_defs = []
        for route_def in route_defs:
            method_class = _method_classification(route_def.get("methods") or [])
            if method_class in {"mutating", "mixed"} or route_def.get("risk_keywords"):
                dangerous_defs.append(route_def)
        records.append(
            {
                "module": module,
                "path": _norm_path(path),
                "route_count": len(route_defs),
                "dangerous_or_mutating_route_count": len(dangerous_defs),
                "route_defs": route_defs,
            }
        )
    return records


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "ui_behavior_changed": False,
    }


def build_web_mutation_surface_audit(
    *,
    app: Any,
    repo_path: str | Path = ".",
    report_id: str = "",
    created_at: str = "",
    known_dangerous_routes: tuple[str, ...] | list[str] = DEFAULT_KNOWN_DANGEROUS_ROUTES,
) -> dict[str, Any]:
    """Build the HARDEN.2 audit report from a Flask app object.

    The function inspects route metadata and local source files only. It never
    calls route handlers or executes stored validation/benchmark/worker paths.
    """
    repo = Path(repo_path)
    auth_gate = _auth_gate_summary(app, repo)
    central_gate_detected = bool(auth_gate.get("central_gate_detected"))
    routes = _route_records(app, central_gate_detected)
    route_rules = {route["rule"] for route in routes}
    inspected_modules = {
        route["view_module"] for route in routes if str(route.get("view_module") or "").startswith("web")
    }
    uninspected = _uninspected_route_modules(repo, inspected_modules)

    blockers: list[str] = []
    warnings: list[str] = []

    if not auth_gate["gate_module_exists"]:
        blockers.append("HARDEN.1 auth gate module web/auth_gate.py is missing")
    elif not auth_gate["gate_function_detected"]:
        blockers.append("HARDEN.1 auth gate function should_allow_mutation is missing")
    if not auth_gate["before_request_wiring_detected"]:
        blockers.append("HARDEN.1 before_request gate wiring is not detectable")

    uncovered_mutating = [
        route for route in routes if route["mutating_methods"] and not route["covered_by_auth_gate"]
    ]
    for route in uncovered_mutating:
        blockers.append(f"mutating route {route['rule']} appears outside the central auth gate")

    dangerous_get_only = [
        route
        for route in routes
        if route["dangerous_sounding"] and not route["mutating_methods"] and route["method_classification"] == "read_only"
    ]
    for route in dangerous_get_only:
        warnings.append(f"dangerous-sounding GET-only route needs manual review: {route['rule']}")

    unclear_dangerous = [
        route
        for route in routes
        if route["dangerous_sounding"] and route["method_classification"] == "unclear"
    ]
    for route in unclear_dangerous:
        warnings.append(f"dangerous-sounding route has unclear methods: {route['rule']}")

    mixed = [route for route in routes if route["method_classification"] == "mixed"]
    for route in mixed:
        warnings.append(f"route has mixed safe/mutating methods: {route['rule']}")

    for module in uninspected:
        msg = f"route module {module['module']} defines routes but is outside the app.url_map audit surface"
        if module["dangerous_or_mutating_route_count"]:
            blockers.append(msg)
        else:
            warnings.append(msg)

    missing_known = [str(rule) for rule in known_dangerous_routes if str(rule) not in route_rules]
    for rule in missing_known:
        blockers.append(f"known dangerous route missing from route map: {rule}")

    blockers = _dedupe(blockers)
    warnings = _dedupe(warnings)

    if blockers:
        verdict = STATUS_FAIL
        reason = f"{len(blockers)} blocker(s) found"
    elif warnings:
        verdict = STATUS_WARN
        reason = f"{len(warnings)} warning(s) require manual review"
    else:
        verdict = STATUS_PASS
        reason = "all mutating routes are inventoried and covered by the central gate"

    route_counts = {
        "total": len(routes),
        "read_only": sum(1 for route in routes if route["method_classification"] == "read_only"),
        "mutating": sum(1 for route in routes if route["mutating_methods"]),
        "mixed": len(mixed),
        "dangerous": sum(1 for route in routes if route["dangerous_sounding"]),
        "dangerous_get_only": len(dangerous_get_only),
        "dangerous_unclear_method": len(unclear_dangerous),
        "covered_mutating": sum(
            1 for route in routes if route["mutating_methods"] and route["covered_by_auth_gate"]
        ),
        "uncovered_mutating": len(uncovered_mutating),
        "uninspected_route_modules": len(uninspected),
    }

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm_path(repo),
        "verdict": verdict,
        "verdict_reason": reason,
        "auth_gate": auth_gate,
        "route_counts": route_counts,
        "routes": routes,
        "dangerous_get_only_routes": dangerous_get_only,
        "dangerous_unclear_method_routes": unclear_dangerous,
        "mixed_method_routes": mixed,
        "uninspected_route_modules": uninspected,
        "known_dangerous_routes_checked": list(known_dangerous_routes),
        "known_dangerous_missing": missing_known,
        "guardrails": _guardrails(),
        "warnings": warnings,
        "blockers": blockers,
        "boundaries": list(BOUNDARIES),
    }


def render_web_mutation_surface_audit_markdown(report: dict[str, Any]) -> str:
    """Render the audit report as compact operator-readable Markdown."""
    lines: list[str] = [
        "# Web Mutation Surface Audit",
        "",
        f"> {report.get('guardrail_note', GUARDRAIL_NOTE)}",
        "",
        "## Summary",
        "",
        f"- **Report id:** `{_md(report.get('report_id') or '(none)')}`",
        f"- **Created at:** `{_md(report.get('created_at') or '(none)')}`",
        f"- **Repo path:** `{_md(report.get('repo_path') or '(none)')}`",
        f"- **Verdict:** `{_md(report.get('verdict') or '(none)')}`",
        f"- **Reason:** {_md(report.get('verdict_reason') or '(none)')}",
        "",
    ]

    counts = report.get("route_counts") or {}
    lines += [
        "| Count | Value |",
        "|---|---:|",
    ]
    for key in (
        "total",
        "read_only",
        "mutating",
        "mixed",
        "dangerous",
        "dangerous_get_only",
        "dangerous_unclear_method",
        "covered_mutating",
        "uncovered_mutating",
        "uninspected_route_modules",
    ):
        lines.append(f"| {_md(key)} | {counts.get(key, 0)} |")
    lines.append("")

    gate = report.get("auth_gate") or {}
    lines += [
        "## HARDEN.1 Gate",
        "",
        f"- **Module exists:** {str(bool(gate.get('gate_module_exists'))).lower()}",
        f"- **Function detected:** {str(bool(gate.get('gate_function_detected'))).lower()}",
        f"- **Before-request wiring detected:** {str(bool(gate.get('before_request_wiring_detected'))).lower()}",
        f"- **Central gate detected:** {str(bool(gate.get('central_gate_detected'))).lower()}",
        "",
        "## Route Inventory",
        "",
        "| Method class | Methods | Rule | Endpoint | Categories | Gate | Notes |",
        "|---|---|---|---|---|---|---|",
    ]
    for route in report.get("routes") or []:
        lines.append(
            "| {method_class} | {methods} | `{rule}` | `{endpoint}` | {cats} | {gate} | {notes} |".format(
                method_class=_md(route.get("method_classification", "")),
                methods=_md(",".join(route.get("methods") or [])),
                rule=_md(route.get("rule", "")),
                endpoint=_md(route.get("endpoint", "")),
                cats=_md(", ".join(route.get("categories") or [])),
                gate=_md(route.get("gate_status", "")),
                notes=_md("; ".join(route.get("notes") or [])),
            )
        )
    lines.append("")

    def _section(title: str, items: list[str]) -> None:
        lines.extend([f"## {title}", ""])
        if items:
            lines.extend(f"- {_md(item)}" for item in items)
        else:
            lines.append("_None._")
        lines.append("")

    _section("Warnings", list(report.get("warnings") or []))
    _section("Blockers", list(report.get("blockers") or []))

    uninspected = report.get("uninspected_route_modules") or []
    lines.extend(["## Uninspected Route Modules", ""])
    if uninspected:
        lines.extend(["| Module | Route count | Risky route count | Path |", "|---|---:|---:|---|"])
        for module in uninspected:
            lines.append(
                f"| `{_md(module.get('module', ''))}` | {module.get('route_count', 0)} | "
                f"{module.get('dangerous_or_mutating_route_count', 0)} | `{_md(module.get('path', ''))}` |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Boundaries", ""])
    for boundary in report.get("boundaries") or list(BOUNDARIES):
        lines.append(f"- {_md(boundary)}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_web_mutation_surface_audit(
    *,
    app: Any,
    repo_path: str | Path,
    output_dir: str | Path,
    report_id: str = "",
    created_at: str = "",
    known_dangerous_routes: tuple[str, ...] | list[str] = DEFAULT_KNOWN_DANGEROUS_ROUTES,
) -> dict[str, Any]:
    """Build the audit and write its JSON and Markdown artifacts."""
    report = build_web_mutation_surface_audit(
        app=app,
        repo_path=repo_path,
        report_id=report_id,
        created_at=created_at,
        known_dangerous_routes=known_dangerous_routes,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(render_web_mutation_surface_audit_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
