"""HARDEN.3 - Safe Validation / MCP Approval Enforcement Audit.

This module is report-only. It statically inspects local Python source files for
validation execution, MCP/tool-style artifact actions, janitor/apply/delete
paths, and approval-sensitive fields. It never imports audited application
modules, never calls route handlers, never invokes MCP tools, never runs
validation or benchmarks, never applies patches, never launches workers, never
contacts the network, and never writes anything except its audit artifacts.
"""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPORT_KIND = "safe_validation_mcp_approval_audit"
JSON_NAME = "safe_validation_mcp_approval_audit.json"
MD_NAME = "safe_validation_mcp_approval_audit.md"

STATUS_PASS = "pass"
STATUS_WARN = "pass_with_warnings"
STATUS_FAIL = "fail"

DEFAULT_TARGET_DIRS: tuple[str, ...] = (
    "core",
    "scripts",
    "web",
    "mcp_server",
    "patching",
)

SELF_AUDIT_EXCLUDED_PATHS: tuple[str, ...] = (
    "core/safe_validation_mcp_approval_audit.py",
    "scripts/create_safe_validation_mcp_approval_audit.py",
)

SAFE_METHODS: tuple[str, ...] = ("GET", "HEAD", "OPTIONS")
MUTATING_METHODS: tuple[str, ...] = ("POST", "PUT", "PATCH", "DELETE")

VALIDATION_TOKENS: tuple[str, ...] = (
    "validation",
    "validate",
    "validator",
)

MCP_TOKENS: tuple[str, ...] = (
    "mcp",
    "tool_registry",
    "artifact_write",
    "import_worker_run",
    "validate_imported_worker_proposal",
)

JANITOR_TOKENS: tuple[str, ...] = (
    "janitor",
    "cleanup",
    "delete",
    "archive",
    "apply_patch",
    "dream_apply",
    "apply_compose",
    "apply_to_env",
    "apply-env",
    "apply_env",
    "compose-apply",
    "compose_apply",
    "replay",
)

APPROVAL_FIELDS: tuple[str, ...] = (
    "human_approval_required",
    "requires_human_approval",
    "human_approved_for_proposal",
    "apply_allowed",
    "worker_launch_allowed",
    "auto_merge",
    "self_approval",
    "self_approval_allowed",
    "eligible_for_auto_merge",
    "approval_status",
    "confirm_token",
    "confirm",
)

RISKY_TRUE_APPROVAL_FIELDS: tuple[str, ...] = (
    "apply_allowed",
    "worker_launch_allowed",
    "auto_merge",
    "self_approval",
    "self_approval_allowed",
    "eligible_for_auto_merge",
)

EXECUTION_SINK_NAMES: tuple[str, ...] = (
    "subprocess.run",
    "subprocess.Popen",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "os.system",
    "shutil.rmtree",
    "Path.unlink",
    "unlink",
    "rmtree",
    "apply_patch",
    "apply_patch_from_json",
    "run_patch_plan_with_artifacts",
    "run_safe_validation_command",
    "_run_validation_command",
    "run_validation_command",
)

SAFE_VALIDATION_EVIDENCE: tuple[str, ...] = (
    "validate_safe_validation_command",
    "SafeValidationCommand",
    "run_safe_validation_command",
    "validation_command_safety_issue",
    "_split_validation_command",
    "shell=False",
)

MCP_GATE_EVIDENCE: tuple[str, ...] = (
    "is_tool_allowed",
    "_EXTRA_WRITE_TOOLS",
    "mcp_exposable",
    "requires_human_approval",
    "record_mcp_invocation",
    "_validate_imported_proposal_input",
    "_validate_worker_run_import_input",
    "list_exposed_tool_names",
    "TemporaryDirectory",
    "temp clone",
    "Never modifies the real repo",
    "Review it before",
)

JANITOR_GATE_EVIDENCE: tuple[str, ...] = (
    "CONFIRM_TOKEN",
    "confirm_token",
    "confirm !=",
    "confirm=",
    "should_allow_mutation",
    "WEB_AUTH_TOKEN",
    "before_request",
    "human-triggered",
    "human action",
    "TemporaryDirectory",
    "sandbox",
    "temp clone",
    "_rmtree_contained",
    "relative_to",
    "_validate_replay_id",
)

APPROVAL_GATE_EVIDENCE: tuple[str, ...] = (
    "CONFIRM_TOKEN",
    "confirm_token",
    "confirm !=",
    "confirm=",
    "requires_human_approval",
    "human_approval_required",
    "human_approved_for_proposal",
    "approval_required",
    "approval_status",
    "Chat approval is not merge authority",
    "self_approval_allowed\": False",
    "eligible_for_auto_merge\": False",
    "auto_merge_allowed\": False",
    "apply_allowed\": False",
    "worker_launch_allowed\": False",
)

GUARDRAIL_NOTE = (
    "Safe Validation / MCP Approval Enforcement Audit is report-only: it reads "
    "local Python source files, extracts route/function metadata, and writes JSON "
    "and Markdown artifacts. It does not import audited application modules, call "
    "route handlers, invoke MCP tools, call models, apply patches, run validation, "
    "run benchmarks, launch workers, execute Dream or Replay janitor actions, "
    "contact network services, write to a database, change routes, change auth "
    "policy, or change UI behavior."
)

BOUNDARIES: tuple[str, ...] = (
    "HARDEN.3 is report-only.",
    "HARDEN.3 does not call models.",
    "HARDEN.3 does not apply patches.",
    "HARDEN.3 does not run validation.",
    "HARDEN.3 does not run benchmarks.",
    "HARDEN.3 does not invoke MCP tools.",
    "HARDEN.3 does not launch workers.",
    "HARDEN.3 does not execute Dream actions.",
    "HARDEN.3 does not apply Replay janitor actions.",
    "HARDEN.3 does not contact network services.",
    "HARDEN.3 does not write to a database.",
    "HARDEN.3 does not change routes, auth policy, or UI behavior.",
    "HARDEN.3 writes only its audit artifacts.",
)

RECOMMENDED_NEXT_PHASE = (
    "HARDEN.CLOSE - Hardening Branch Checkpoint / manual operator review of "
    "HARDEN.1-HARDEN.3 evidence"
)


@dataclass(frozen=True)
class SourceFile:
    path: Path
    rel_path: str
    text: str
    tree: ast.AST | None

    @property
    def lines(self) -> list[str]:
        return self.text.splitlines()


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


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _parse_source(path: Path, repo: Path) -> SourceFile:
    text = _read_text(path)
    try:
        tree: ast.AST | None = ast.parse(text)
    except SyntaxError:
        tree = None
    return SourceFile(
        path=path,
        rel_path=_relative_path(path, repo),
        text=text,
        tree=tree,
    )


def _relative_path(path: Path, repo: Path) -> str:
    try:
        return path.resolve().relative_to(repo.resolve()).as_posix()
    except (ValueError, OSError):
        return _norm_path(path)


def _iter_python_files(repo: Path, target_dirs: tuple[str, ...] | list[str]) -> list[Path]:
    paths: list[Path] = []
    for dirname in target_dirs:
        root = repo / dirname
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.py")):
            rel = _relative_path(path, repo)
            if rel in SELF_AUDIT_EXCLUDED_PATHS:
                continue
            parts = {part.lower() for part in path.parts}
            if "__pycache__" in parts or ".venv" in parts or "venv" in parts:
                continue
            paths.append(path)
    return paths


def _literal_str(node: ast.AST | None) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return ""


def _literal_bool(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _literal_methods(node: ast.AST | None) -> list[str]:
    if node is None:
        return ["GET"]
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return sorted(
            {
                value.upper()
                for value in (_literal_str(item) for item in node.elts)
                if value
            }
        )
    value = _literal_str(node)
    return [value.upper()] if value else []


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = _call_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    return ""


def _call_tail(name: str) -> str:
    return name.rsplit(".", 1)[-1] if name else ""


def _function_text(source: SourceFile, node: ast.AST) -> str:
    start = max(0, int(getattr(node, "lineno", 1)) - 1)
    end = int(getattr(node, "end_lineno", getattr(node, "lineno", 1)) or start + 1)
    return "\n".join(source.lines[start:end])


def _source_label(source: SourceFile, node: ast.AST) -> str:
    name = str(getattr(node, "name", "<module>"))
    return f"{source.rel_path}::{name}"


def _has_any(text: str, tokens: tuple[str, ...] | list[str]) -> bool:
    lower = text.lower()
    return any(token.lower() in lower for token in tokens)


def _matched_tokens(text: str, tokens: tuple[str, ...] | list[str]) -> list[str]:
    lower = text.lower()
    return [token for token in tokens if token.lower() in lower]


def _field_literal_state(text: str, field: str) -> str:
    quoted = rf"['\"]{re.escape(field)}['\"]\s*:\s*(True|False)"
    assigned = rf"\b{re.escape(field)}\s*=\s*(True|False)"
    for pattern in (quoted, assigned):
        match = re.search(pattern, text)
        if match:
            return str(match.group(1)).lower()
    mentioned = rf"(?<![A-Za-z0-9_]){re.escape(field)}(?![A-Za-z0-9_])"
    return "mentioned" if re.search(mentioned, text) else ""


def _approval_field_states(text: str) -> dict[str, str]:
    states: dict[str, str] = {}
    for field in APPROVAL_FIELDS:
        state = _field_literal_state(text, field)
        if state:
            states[field] = state
    return states


def _call_records(node: ast.AST) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        name = _call_name(child.func)
        tail = _call_tail(name)
        shell_value = None
        for kw in child.keywords:
            if kw.arg == "shell":
                shell_value = _literal_bool(kw.value)
                break
        records.append(
            {
                "name": name,
                "tail": tail,
                "lineno": int(getattr(child, "lineno", 0) or 0),
                "shell_true": shell_value is True,
                "shell_false": shell_value is False,
            }
        )
    return records


def _execution_sinks(records: list[dict[str, Any]]) -> list[str]:
    sinks: list[str] = []
    for record in records:
        name = str(record.get("name") or "")
        tail = str(record.get("tail") or "")
        for sink in EXECUTION_SINK_NAMES:
            if name == sink or tail == sink:
                sinks.append(sink)
    return _dedupe(sinks)


def _route_from_decorator(
    decorator: ast.AST,
    *,
    source: SourceFile,
    function_name: str,
) -> dict[str, Any] | None:
    if not isinstance(decorator, ast.Call):
        return None
    func_name = _call_name(decorator.func)
    attr = _call_tail(func_name)
    rule = _literal_str(decorator.args[0]) if decorator.args else ""
    if attr in {"get", "post", "put", "patch", "delete"}:
        methods = [attr.upper()]
    elif attr == "route":
        method_node = None
        for kw in decorator.keywords:
            if kw.arg == "methods":
                method_node = kw.value
                break
        methods = _literal_methods(method_node)
    else:
        return None
    if not rule:
        return None
    return _route_record(
        source=source,
        rule=rule,
        methods=methods,
        function_name=function_name,
        lineno=int(getattr(decorator, "lineno", 0) or 0),
    )


def _route_record(
    *,
    source: SourceFile,
    rule: str,
    methods: list[str],
    function_name: str,
    lineno: int,
) -> dict[str, Any]:
    methods = sorted({str(method).upper() for method in methods if str(method).strip()})
    if not methods:
        methods = ["GET"]
    mutating = [method for method in methods if method in MUTATING_METHODS]
    safe = [method for method in methods if method in SAFE_METHODS]
    unknown = [method for method in methods if method not in SAFE_METHODS + MUTATING_METHODS]
    text = f"{rule} {function_name} {source.rel_path}".lower().replace("_", "-")
    risk_keywords = [
        token
        for token in (
            "apply",
            "patch",
            "run",
            "validate",
            "worker",
            "dream",
            "replay",
            "janitor",
            "delete",
            "archive",
            "compose",
            "env",
            "mcp",
        )
        if token in text
    ]
    if unknown:
        method_class = "unclear"
    elif mutating and safe:
        method_class = "mixed"
    elif mutating:
        method_class = "mutating"
    else:
        method_class = "read_only"
    return {
        "surface_id": f"{source.rel_path}::{function_name}:{lineno}",
        "path": source.rel_path,
        "line": lineno,
        "rule": rule,
        "methods": methods,
        "safe_methods": safe,
        "mutating_methods": mutating,
        "method_classification": method_class,
        "function_name": function_name,
        "risk_keywords": risk_keywords,
        "dangerous_sounding": bool(risk_keywords),
    }


def _routes_for_source(source: SourceFile) -> list[dict[str, Any]]:
    if source.tree is None:
        return []
    routes: list[dict[str, Any]] = []
    for node in ast.walk(source.tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                route = _route_from_decorator(
                    decorator,
                    source=source,
                    function_name=node.name,
                )
                if route:
                    routes.append(route)
        elif isinstance(node, ast.Call) and _call_tail(_call_name(node.func)) == "add_url_rule":
            rule = _literal_str(node.args[0]) if node.args else ""
            method_node = None
            function_name = ""
            for kw in node.keywords:
                if kw.arg == "methods":
                    method_node = kw.value
                elif kw.arg == "view_func":
                    function_name = _call_name(kw.value)
            if rule:
                routes.append(
                    _route_record(
                        source=source,
                        rule=rule,
                        methods=_literal_methods(method_node),
                        function_name=function_name,
                        lineno=int(getattr(node, "lineno", 0) or 0),
                    )
                )
    routes.sort(key=lambda item: (item["path"], item["line"], item["rule"]))
    return routes


def _harden1_static_gate_detected(repo: Path) -> bool:
    app_text = _read_text(repo / "web" / "app.py")
    auth_text = _read_text(repo / "web" / "auth_gate.py")
    return bool(
        "before_request" in app_text
        and "should_allow_mutation" in app_text
        and "def should_allow_mutation" in auth_text
    )


def _route_lookup(routes: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    lookup: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for route in routes:
        key = (str(route.get("path") or ""), str(route.get("function_name") or ""))
        lookup.setdefault(key, []).append(route)
    return lookup


def _gate_evidence(
    *,
    text: str,
    file_text: str,
    route_records: list[dict[str, Any]],
    harden1_gate_detected: bool,
) -> list[str]:
    combined = text + "\n" + file_text
    evidence: list[str] = []
    for token in SAFE_VALIDATION_EVIDENCE:
        if token in combined:
            evidence.append(token)
    for token in MCP_GATE_EVIDENCE:
        if token in combined:
            evidence.append(token)
    for token in JANITOR_GATE_EVIDENCE:
        if token in combined:
            evidence.append(token)
    for token in APPROVAL_GATE_EVIDENCE:
        if token in combined:
            evidence.append(token)
    if harden1_gate_detected and any(route.get("mutating_methods") for route in route_records):
        evidence.append("HARDEN.1 before_request auth gate")
    return _dedupe(evidence)


def _signals(
    *,
    source: SourceFile,
    node: ast.AST,
    text: str,
    calls: list[dict[str, Any]],
    routes: list[dict[str, Any]],
    approval_fields: dict[str, str],
) -> list[str]:
    label = _source_label(source, node).lower().replace("_", "-")
    route_text = " ".join(str(route.get("rule") or "") for route in routes).lower()
    signals: list[str] = []
    if _has_any(label + "\n" + text, VALIDATION_TOKENS):
        signals.append("validation_keyword")
    if _has_any(label + "\n" + route_text, MCP_TOKENS) or source.rel_path.startswith("mcp_server/"):
        signals.append("mcp_or_tool_keyword")
    if _has_any(label, JANITOR_TOKENS) or any(route.get("risk_keywords") for route in routes):
        signals.append("janitor_apply_cleanup_keyword")
    if any(record.get("name") == "subprocess.run" for record in calls):
        signals.append("subprocess_run")
    if any(record.get("name") == "subprocess.Popen" for record in calls):
        signals.append("subprocess_popen")
    if any(record.get("shell_true") for record in calls):
        signals.append("shell_true")
    if any(record.get("shell_false") for record in calls):
        signals.append("shell_false")
    if any(str(record.get("tail")) in {"rmtree", "unlink"} for record in calls):
        signals.append("delete_call")
    if any(sink in _execution_sinks(calls) for sink in ("apply_patch", "run_patch_plan_with_artifacts")):
        signals.append("apply_like_call")
    if approval_fields:
        signals.append("approval_field")
    if routes:
        signals.append("route")
    return _dedupe(signals)


def _surface_base(
    *,
    source: SourceFile,
    node: ast.AST,
    text: str,
    routes: list[dict[str, Any]],
    harden1_gate_detected: bool,
) -> dict[str, Any]:
    calls = _call_records(node)
    approval_fields = _approval_field_states(text)
    evidence = _gate_evidence(
        text=text,
        file_text=source.text,
        route_records=routes,
        harden1_gate_detected=harden1_gate_detected,
    )
    return {
        "surface_id": _source_label(source, node),
        "path": source.rel_path,
        "line": int(getattr(node, "lineno", 0) or 0),
        "function_name": str(getattr(node, "name", "<module>")),
        "routes": routes,
        "signals": _signals(
            source=source,
            node=node,
            text=text,
            calls=calls,
            routes=routes,
            approval_fields=approval_fields,
        ),
        "execution_sinks": _execution_sinks(calls),
        "approval_fields": approval_fields,
        "gate_evidence": evidence,
        "gate_status": "needs_manual_review",
        "notes": [],
    }


def _is_validation_surface(surface: dict[str, Any]) -> bool:
    signals = set(surface.get("signals") or [])
    sinks = set(surface.get("execution_sinks") or [])
    evidence = set(surface.get("gate_evidence") or [])
    route_text = " ".join(str(route.get("rule") or "") for route in surface.get("routes") or [])
    return bool(
        "validation_keyword" in signals
        and (
            sinks
            or evidence & set(SAFE_VALIDATION_EVIDENCE)
            or "validate" in route_text.lower()
        )
    )


def _is_mcp_surface(surface: dict[str, Any]) -> bool:
    return bool("mcp_or_tool_keyword" in set(surface.get("signals") or []))


def _is_janitor_surface(surface: dict[str, Any]) -> bool:
    signals = set(surface.get("signals") or [])
    sinks = set(surface.get("execution_sinks") or [])
    return bool(
        "janitor_apply_cleanup_keyword" in signals
        or "delete_call" in signals
        or sinks & {"apply_patch", "run_patch_plan_with_artifacts", "shutil.rmtree", "unlink", "rmtree"}
    )


def _is_approval_surface(surface: dict[str, Any]) -> bool:
    return bool(surface.get("approval_fields"))


def _classify_validation(surface: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    signals = set(surface.get("signals") or [])
    evidence = set(surface.get("gate_evidence") or [])
    sinks = set(surface.get("execution_sinks") or [])
    notes: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    has_safety = bool(evidence & set(SAFE_VALIDATION_EVIDENCE))
    has_subprocess = bool({"subprocess.run", "run_validation_command", "_run_validation_command"} & sinks)

    if "shell_true" in signals and not has_safety:
        blockers.append(
            f"raw validation execution lacks safe validation/command safety gate: {surface['surface_id']}"
        )
        return "blocked", notes, blockers
    if has_subprocess and not has_safety:
        warnings.append(
            f"validation subprocess surface needs manual review: {surface['surface_id']}"
        )
        notes.append("subprocess validation surface without direct safe-validation evidence")
        return "needs_manual_review", notes + warnings, []
    if "shell_true" in signals and has_safety:
        warnings.append(
            f"legacy shell validation appears guarded but needs manual review: {surface['surface_id']}"
        )
        notes.append("shell=True retained behind command safety screening")
        return "needs_manual_review", notes + warnings, []
    notes.append("safe validation or command-safety evidence detected")
    return "guarded", notes, []


def _classify_mcp(surface: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    evidence = set(surface.get("gate_evidence") or [])
    sinks = set(surface.get("execution_sinks") or [])
    notes: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    has_gate = bool(evidence & set(MCP_GATE_EVIDENCE)) or bool(
        evidence & {"HARDEN.1 before_request auth gate"}
    )
    dangerous_apply = bool(sinks & {"apply_patch", "run_patch_plan_with_artifacts"})

    if dangerous_apply and not has_gate:
        blockers.append(
            f"MCP/tool surface can apply/import/validate without detectable approval boundary: {surface['surface_id']}"
        )
        return "blocked", notes, blockers
    if has_gate:
        notes.append("MCP/tool allowlist, audit, human-approval, or sandbox evidence detected")
        return "guarded", notes, []
    warnings.append(f"MCP/tool surface needs manual approval-boundary review: {surface['surface_id']}")
    return "needs_manual_review", warnings, []


def _classify_janitor(surface: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    signals = set(surface.get("signals") or [])
    evidence = set(surface.get("gate_evidence") or [])
    sinks = set(surface.get("execution_sinks") or [])
    ident = str(surface.get("surface_id") or "").lower()
    notes: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    has_gate = bool(evidence & set(JANITOR_GATE_EVIDENCE)) or "HARDEN.1 before_request auth gate" in evidence
    delete_like = bool(signals & {"delete_call"} or sinks & {"shutil.rmtree", "unlink", "rmtree"})
    route_like = bool(surface.get("routes"))
    high_risk_delete = delete_like and (
        route_like
        or "janitor" in ident
        or "replay" in ident
        or "apply" in ident
        or ident.startswith("mcp_server/")
        or ident.startswith("web/")
    )

    if high_risk_delete and not has_gate:
        blockers.append(
            f"delete/apply cleanup path lacks confirmation or auth evidence: {surface['surface_id']}"
        )
        return "blocked", notes, blockers
    if delete_like and not has_gate:
        warnings.append(
            f"internal delete/cleanup helper needs manual containment review: {surface['surface_id']}"
        )
        return "needs_manual_review", warnings, []
    if has_gate:
        notes.append("confirmation token, auth gate, human trigger, or containment evidence detected")
        return "guarded", notes, []
    warnings.append(f"dangerous-sounding apply/cleanup surface needs manual review: {surface['surface_id']}")
    return "needs_manual_review", warnings, []


def _classify_approval(surface: dict[str, Any]) -> tuple[str, list[str], list[str]]:
    fields = surface.get("approval_fields") or {}
    evidence = set(surface.get("gate_evidence") or [])
    notes: list[str] = []
    warnings: list[str] = []
    blockers: list[str] = []
    risky_true = [
        field
        for field in RISKY_TRUE_APPROVAL_FIELDS
        if fields.get(field) == "true"
    ]
    if risky_true:
        blockers.append(
            "approval-sensitive field appears enabled without external human gate: "
            f"{surface['surface_id']} ({', '.join(risky_true)})"
        )
        return "blocked", notes, blockers
    if fields.get("human_approval_required") == "false" and (
        "apply" in str(surface.get("surface_id", "")).lower()
        or "worker" in str(surface.get("surface_id", "")).lower()
    ):
        blockers.append(
            f"approval-sensitive field human_approval_required is false on dangerous surface: {surface['surface_id']}"
        )
        return "blocked", notes, blockers
    if evidence & set(APPROVAL_GATE_EVIDENCE):
        notes.append("approval policy evidence detected")
        return "guarded", notes, []
    warnings.append(f"approval field exists but enforcement is indirect: {surface['surface_id']}")
    return "needs_manual_review", warnings, []


def _merge_status(current: str, candidate: str) -> str:
    order = {"guarded": 0, "needs_manual_review": 1, "blocked": 2}
    return candidate if order.get(candidate, 0) > order.get(current, 0) else current


def _collect_surfaces(
    sources: list[SourceFile],
    routes: list[dict[str, Any]],
    *,
    harden1_gate_detected: bool,
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    route_by_func = _route_lookup(routes)
    all_surfaces: list[dict[str, Any]] = []
    warnings: list[str] = []
    blockers: list[str] = []
    for source in sources:
        if source.tree is None:
            continue
        for node in ast.walk(source.tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            local_routes = route_by_func.get((source.rel_path, node.name), [])
            text = _function_text(source, node)
            surface = _surface_base(
                source=source,
                node=node,
                text=text,
                routes=local_routes,
                harden1_gate_detected=harden1_gate_detected,
            )
            categories: list[str] = []
            combined_notes: list[str] = []
            status = "guarded"

            if _is_validation_surface(surface):
                categories.append("validation")
                s_status, notes, found_blockers = _classify_validation(surface)
                status = _merge_status(status, s_status)
                combined_notes.extend(notes)
                blockers.extend(found_blockers)
                if s_status == "needs_manual_review":
                    warnings.extend(notes)
            if _is_mcp_surface(surface):
                categories.append("mcp")
                s_status, notes, found_blockers = _classify_mcp(surface)
                status = _merge_status(status, s_status)
                combined_notes.extend(notes)
                blockers.extend(found_blockers)
                if s_status == "needs_manual_review":
                    warnings.extend(notes)
            if _is_janitor_surface(surface):
                categories.append("janitor_or_cleanup")
                s_status, notes, found_blockers = _classify_janitor(surface)
                status = _merge_status(status, s_status)
                combined_notes.extend(notes)
                blockers.extend(found_blockers)
                if s_status == "needs_manual_review":
                    warnings.extend(notes)
            if _is_approval_surface(surface):
                categories.append("approval_gate")
                s_status, notes, found_blockers = _classify_approval(surface)
                status = _merge_status(status, s_status)
                combined_notes.extend(notes)
                blockers.extend(found_blockers)
                if s_status == "needs_manual_review":
                    warnings.extend(notes)

            if not categories:
                continue
            surface["categories"] = _dedupe(categories)
            surface["gate_status"] = status
            surface["notes"] = _dedupe(combined_notes)
            all_surfaces.append(surface)
    all_surfaces.sort(key=lambda item: (item["path"], item["line"], item["function_name"]))
    return all_surfaces, _dedupe(warnings), _dedupe(blockers)


def _audited_file_records(routes: list[dict[str, Any]], surfaces: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_path: dict[str, dict[str, Any]] = {}
    for route in routes:
        path = str(route.get("path") or "")
        record = by_path.setdefault(path, {"path": path, "route_count": 0, "surface_count": 0, "categories": []})
        record["route_count"] += 1
        if route.get("dangerous_sounding"):
            record["categories"].append("route")
    for surface in surfaces:
        path = str(surface.get("path") or "")
        record = by_path.setdefault(path, {"path": path, "route_count": 0, "surface_count": 0, "categories": []})
        record["surface_count"] += 1
        record["categories"].extend(surface.get("categories") or [])
    records = []
    for record in by_path.values():
        record["categories"] = _dedupe(list(record.get("categories") or []))
        records.append(record)
    records.sort(key=lambda item: item["path"])
    return records


def _guardrails() -> dict[str, bool]:
    return {
        "report_only": True,
        "model_call_performed": False,
        "patch_applied": False,
        "validation_run": False,
        "benchmark_run_performed": False,
        "mcp_invocation_performed": False,
        "worker_launch_performed": False,
        "dream_execution_performed": False,
        "replay_janitor_apply_performed": False,
        "network_call_performed": False,
        "database_write_performed": False,
        "route_behavior_changed": False,
        "auth_policy_changed": False,
        "ui_behavior_changed": False,
    }


def build_safe_validation_mcp_approval_audit(
    *,
    repo_path: str | Path = ".",
    report_id: str = "",
    created_at: str = "",
    target_dirs: tuple[str, ...] | list[str] = DEFAULT_TARGET_DIRS,
) -> dict[str, Any]:
    """Build the HARDEN.3 audit report using static source inspection only."""
    repo = Path(repo_path)
    sources = [_parse_source(path, repo) for path in _iter_python_files(repo, target_dirs)]
    harden1_gate_detected = _harden1_static_gate_detected(repo)
    routes: list[dict[str, Any]] = []
    for source in sources:
        routes.extend(_routes_for_source(source))
    routes.sort(key=lambda item: (item["path"], item["line"], item["rule"]))

    surfaces, warnings, blockers = _collect_surfaces(
        sources,
        routes,
        harden1_gate_detected=harden1_gate_detected,
    )

    validation_surfaces = [surface for surface in surfaces if "validation" in surface["categories"]]
    mcp_surfaces = [surface for surface in surfaces if "mcp" in surface["categories"]]
    janitor_surfaces = [surface for surface in surfaces if "janitor_or_cleanup" in surface["categories"]]
    approval_surfaces = [surface for surface in surfaces if "approval_gate" in surface["categories"]]

    if not validation_surfaces:
        warnings.append("no validation execution surfaces were detected by the audit")
    if not mcp_surfaces:
        warnings.append("no MCP/tool-style surfaces were detected by the audit")
    if not janitor_surfaces:
        warnings.append("no janitor/apply/delete cleanup surfaces were detected by the audit")
    if not approval_surfaces:
        warnings.append("no approval-sensitive fields were detected by the audit")

    warnings = _dedupe(warnings)
    blockers = _dedupe(blockers)

    if blockers:
        verdict = STATUS_FAIL
        reason = f"{len(blockers)} blocker(s) found"
    elif warnings:
        verdict = STATUS_WARN
        reason = f"{len(warnings)} warning(s) require manual review"
    else:
        verdict = STATUS_PASS
        reason = "all detected powerful surfaces are inventoried and have clear gate evidence"

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": GUARDRAIL_NOTE,
        "report_id": str(report_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": _norm_path(repo),
        "verdict": verdict,
        "verdict_reason": reason,
        "harden1_static_gate_detected": harden1_gate_detected,
        "audited_file_count": len(sources),
        "audited_files": _audited_file_records(routes, surfaces),
        "audited_routes": routes,
        "audited_functions": [
            {
                "surface_id": surface["surface_id"],
                "path": surface["path"],
                "line": surface["line"],
                "function_name": surface["function_name"],
                "categories": surface["categories"],
                "gate_status": surface["gate_status"],
            }
            for surface in surfaces
        ],
        "validation_surfaces": validation_surfaces,
        "mcp_surfaces": mcp_surfaces,
        "janitor_or_cleanup_surfaces": janitor_surfaces,
        "approval_gate_surfaces": approval_surfaces,
        "surface_counts": {
            "validation": len(validation_surfaces),
            "mcp": len(mcp_surfaces),
            "janitor_or_cleanup": len(janitor_surfaces),
            "approval_gate": len(approval_surfaces),
            "routes": len(routes),
            "functions": len(surfaces),
        },
        "warnings": warnings,
        "blockers": blockers,
        "guardrails": _guardrails(),
        "boundaries": list(BOUNDARIES),
        "recommended_next_phase": RECOMMENDED_NEXT_PHASE,
    }


def _surface_table(lines: list[str], title: str, surfaces: list[dict[str, Any]]) -> None:
    lines.extend([f"## {title}", ""])
    if not surfaces:
        lines.extend(["_None._", ""])
        return
    lines.extend(
        [
            "| Status | Path | Function | Line | Signals | Gate evidence | Notes |",
            "|---|---|---:|---:|---|---|---|",
        ]
    )
    for surface in surfaces:
        lines.append(
            "| {status} | `{path}` | `{fn}` | {line} | {signals} | {evidence} | {notes} |".format(
                status=_md(surface.get("gate_status", "")),
                path=_md(surface.get("path", "")),
                fn=_md(surface.get("function_name", "")),
                line=surface.get("line", 0),
                signals=_md(", ".join(surface.get("signals") or [])),
                evidence=_md(", ".join(surface.get("gate_evidence") or [])),
                notes=_md("; ".join(surface.get("notes") or [])),
            )
        )
    lines.append("")


def _list_section(lines: list[str], title: str, items: list[str]) -> None:
    lines.extend([f"## {title}", ""])
    if items:
        lines.extend(f"- {_md(item)}" for item in items)
    else:
        lines.append("_None._")
    lines.append("")


def render_safe_validation_mcp_approval_audit_markdown(report: dict[str, Any]) -> str:
    """Render the HARDEN.3 report as operator-readable Markdown."""
    lines: list[str] = [
        "# Safe Validation / MCP Approval Enforcement Audit",
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
        f"- **HARDEN.1 static gate detected:** {str(bool(report.get('harden1_static_gate_detected'))).lower()}",
        f"- **Recommended next phase:** `{_md(report.get('recommended_next_phase') or '')}`",
        "",
        "| Surface | Count |",
        "|---|---:|",
    ]
    counts = report.get("surface_counts") or {}
    for key in ("routes", "functions", "validation", "mcp", "janitor_or_cleanup", "approval_gate"):
        lines.append(f"| {_md(key)} | {counts.get(key, 0)} |")
    lines.append("")

    lines.extend(["## Audited Files", ""])
    files = report.get("audited_files") or []
    if files:
        lines.extend(["| Path | Routes | Surfaces | Categories |", "|---|---:|---:|---|"])
        for item in files:
            lines.append(
                f"| `{_md(item.get('path', ''))}` | {item.get('route_count', 0)} | "
                f"{item.get('surface_count', 0)} | {_md(', '.join(item.get('categories') or []))} |"
            )
    else:
        lines.append("_None._")
    lines.append("")

    lines.extend(["## Audited Routes", ""])
    routes = report.get("audited_routes") or []
    if routes:
        lines.extend(["| Methods | Rule | Function | Path | Risk keywords |", "|---|---|---|---|---|"])
        for route in routes:
            lines.append(
                "| {methods} | `{rule}` | `{fn}` | `{path}` | {risk} |".format(
                    methods=_md(",".join(route.get("methods") or [])),
                    rule=_md(route.get("rule", "")),
                    fn=_md(route.get("function_name", "")),
                    path=_md(route.get("path", "")),
                    risk=_md(", ".join(route.get("risk_keywords") or [])),
                )
            )
    else:
        lines.append("_None._")
    lines.append("")

    _surface_table(lines, "Validation Surfaces", list(report.get("validation_surfaces") or []))
    _surface_table(lines, "MCP Surfaces", list(report.get("mcp_surfaces") or []))
    _surface_table(lines, "Janitor / Cleanup Surfaces", list(report.get("janitor_or_cleanup_surfaces") or []))
    _surface_table(lines, "Approval Gate Surfaces", list(report.get("approval_gate_surfaces") or []))

    _list_section(lines, "Warnings", list(report.get("warnings") or []))
    _list_section(lines, "Blockers", list(report.get("blockers") or []))

    lines.extend(["## Boundaries", ""])
    for boundary in report.get("boundaries") or list(BOUNDARIES):
        lines.append(f"- {_md(boundary)}")
    lines.append("")
    return "\n".join(lines) + "\n"


def write_safe_validation_mcp_approval_audit(
    *,
    repo_path: str | Path,
    output_dir: str | Path,
    report_id: str = "",
    created_at: str = "",
    target_dirs: tuple[str, ...] | list[str] = DEFAULT_TARGET_DIRS,
) -> dict[str, Any]:
    """Build the audit and write its JSON and Markdown artifacts."""
    report = build_safe_validation_mcp_approval_audit(
        repo_path=repo_path,
        report_id=report_id,
        created_at=created_at,
        target_dirs=target_dirs,
    )
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True, sort_keys=True),
        encoding="utf-8",
    )
    md_path.write_text(render_safe_validation_mcp_approval_audit_markdown(report), encoding="utf-8")
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "report": report,
    }
