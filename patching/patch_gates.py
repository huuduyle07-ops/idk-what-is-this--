from __future__ import annotations

import json
import re
from pathlib import Path

from agents.gemini_client import run_gemini_request
from core.agent_state import AgentState
from core.validator import validate_patch_plan_grounding
from database.memory import save_engineering_memory

SCHEMA_HINT = """
{
  "summary": "...",
  "issues": [],
  "patch_candidate": null | {
    "file": "...",
    "relative_path": "...",
    "target_node_name": "...",
    "target_node_kind": "function|class",
    "target_snippet": "...",
    "patched_snippet": "..."
  },
  "patch_plan": null | [
    {
      "op": "replace_snippet",
      "relative_path": "...",
      "target_snippet": "...",
      "patched_snippet": "..."
    },
    {
      "op": "create_file",
      "relative_path": "...",
      "content": "..."
    }
  ],
  "confidence": 0.0,
  "needs_escalation": false
}
""".strip()

def _go_packages_used(snippet: str) -> list[str]:
    packages: list[str] = []

    if "fmt." in (snippet or ""):
        packages.append("fmt")

    if "errors." in (snippet or ""):
        packages.append("errors")

    return packages


def _go_has_import(text: str, package: str) -> bool:
    return (
        f'import "{package}"' in text
        or re.search(rf'import\s*\([^)]*"{re.escape(package)}"[^)]*\)', text, flags=re.S) is not None
    )


def _build_go_import_patch_op(relative_path: str, text: str, missing: list[str]) -> dict | None:
    if not missing:
        return None

    # Existing import block:
    block_match = re.search(r'import\s*\(\n(?P<body>.*?)\n\)', text, flags=re.S)
    if block_match:
        target = block_match.group(0)
        existing = re.findall(r'"([^"]+)"', target)

        packages = []
        for pkg in existing + missing:
            if pkg not in packages:
                packages.append(pkg)

        patched = "import (\n" + "".join(f'\t"{pkg}"\n' for pkg in packages) + ")"

        return {
            "op": "replace_snippet",
            "relative_path": relative_path,
            "target_snippet": target,
            "patched_snippet": patched,
        }

    # Existing single import:
    single_match = re.search(r'import\s+"([^"]+)"', text)
    if single_match:
        target = single_match.group(0)
        existing_pkg = single_match.group(1)

        packages = []
        for pkg in [existing_pkg] + missing:
            if pkg not in packages:
                packages.append(pkg)

        if len(packages) == 1:
            patched = f'import "{packages[0]}"'
        else:
            patched = "import (\n" + "".join(f'\t"{pkg}"\n' for pkg in packages) + ")"

        return {
            "op": "replace_snippet",
            "relative_path": relative_path,
            "target_snippet": target,
            "patched_snippet": patched,
        }

    # No import yet: insert after package line.
    package_match = re.search(r"(?m)^package\s+\w+\s*$", text)
    if not package_match:
        return None

    target = package_match.group(0)

    if len(missing) == 1:
        patched = f'{target}\n\nimport "{missing[0]}"'
    else:
        patched = (
            target
            + "\n\nimport (\n"
            + "".join(f'\t"{pkg}"\n' for pkg in missing)
            + ")"
        )

    return {
        "op": "replace_snippet",
        "relative_path": relative_path,
        "target_snippet": target,
        "patched_snippet": patched,
    }


def promote_go_missing_import_candidate_to_patch_plan(state: AgentState) -> None:
    block = state.json_block or {}

    # Do not touch real patch plans.
    if isinstance(block.get("patch_plan"), list) and block["patch_plan"]:
        return

    patch = block.get("patch_candidate")
    if not isinstance(patch, dict):
        return

    relative_path = patch.get("relative_path") or patch.get("file") or ""
    if not relative_path.endswith(".go"):
        return

    patched_snippet = patch.get("patched_snippet") or ""
    needed = _go_packages_used(patched_snippet)
    if not needed:
        return

    if not state.repo_path:
        return

    path = Path(state.repo_path) / relative_path
    if not path.exists():
        return

    text = path.read_text(encoding="utf-8", errors="replace")

    missing = [pkg for pkg in needed if not _go_has_import(text, pkg)]
    if not missing:
        return

    target_snippet = patch.get("target_snippet") or ""
    if not target_snippet or target_snippet not in text:
        return

    import_op = _build_go_import_patch_op(relative_path, text, missing)
    if not import_op:
        return

    function_op = {
        "op": "replace_snippet",
        "relative_path": relative_path,
        "target_snippet": target_snippet,
        "patched_snippet": patched_snippet,
    }

    block["patch_candidate"] = None
    block["patch_plan"] = [import_op, function_op]
    block["confidence"] = min(float(block.get("confidence", 0.85) or 0.85), 0.85)
    block["needs_escalation"] = False

    print(
        "🧩 Promoted Go patch_candidate to patch_plan because missing import(s) were required: "
        + ", ".join(missing)
    )

    state.json_block = block
    
def retry_structured_patch_json(state: AgentState, bad_answer: str) -> str:
    control = state.control_result or {}
    patch_intent = control.get("patch_intent") or {}
    source_snippet = patch_intent.get("source_snippet") or ""

    related = control.get("related_snippets") or []
    related_block = "\n\n".join(
        f"--- {s.get('file')} / {s.get('symbol', '')} ---\n{s.get('snippet', '')}"
        for s in related[:5]
        if s.get("snippet")
    )

    prompt = f"""
You returned a response that could not be parsed as JSON.

Return ONLY valid JSON for this coding agent.
No markdown. No explanation.

The previous response was invalid or unsafe for one of these reasons:
- It could not be parsed as JSON, OR
- The patch_candidate was structurally incomplete, OR
- target_snippet was not copied byte-exactly from source, OR
- patched_snippet was not a complete compilable replacement.

Rules:
- target_snippet MUST be copied exactly from the source context below.
- Do not normalize whitespace in target_snippet.
- Do not remove or add newlines in target_snippet.
- patched_snippet must be a complete compilable replacement.
- If replacing a full function, include the full closing delimiter/braces.
- Do not omit the final closing brace.
- For Go: if patched_snippet uses fmt.Errorf or errors.New and the file lacks the needed import, return patch_plan that adds the import and replaces the function.
- If the user allows patch_plan for imports, prefer patch_plan over patch_candidate.
- For patch_plan, every operation MUST use "op".
- Use "op": "replace_snippet" for replacing existing code.
- Use "relative_path", not "file".
- Do NOT use "action": "replace".
- Do NOT use "file" inside patch_plan operations.
Required shape:
{SCHEMA_HINT}

Original user request:
{state.user_input}

Exact CONTROL source_snippet:
{source_snippet or "<none>"}

Related source snippets:
{related_block or "<none>"}

Previous invalid response:
{bad_answer}
""".strip()

    return run_gemini_request(prompt, state.file_paths if state.file_paths else None)

def normalize_patch_plan_schema(state: AgentState) -> None:
    block = state.json_block or {}
    plan = block.get("patch_plan")

    if not isinstance(plan, list):
        return

    changed = False

    for op in plan:
        if not isinstance(op, dict):
            continue

        # Repair common LLM drift:
        # {"file": "...", "action": "replace", ...}
        # -> {"op": "replace_snippet", "relative_path": "...", ...}
        if not op.get("op") and op.get("action") == "replace":
            op["op"] = "replace_snippet"
            changed = True

        if not op.get("relative_path") and op.get("file"):
            op["relative_path"] = op["file"]
            changed = True

        # Optional cleanup so downstream schema is clean
        if "action" in op:
            op.pop("action", None)
            changed = True

        if "file" in op and op.get("relative_path"):
            op.pop("file", None)
            changed = True

    if changed:
        print("🧩 Normalized patch_plan schema before grounding.")
        state.json_block = block

def patch_candidate_structural_issue(block: dict | None, language: str) -> str:
    if not block:
        return ""

    patch = block.get("patch_candidate")
    if not isinstance(patch, dict):
        return ""

    patched = patch.get("patched_snippet") or ""
    lang = (language or "").lower().strip()

    brace_langs = {
        "rust", "rs",
        "go", "golang",
        "cpp", "c++", "cxx",
        "javascript", "js", "typescript", "ts",
        "csharp", "cs", "c#",
        "java",
    }

    if lang in brace_langs:
        if patched.count("{") != patched.count("}"):
            return "patched_snippet has unbalanced braces; it may be an incomplete function."

    return ""


def patch_candidate_missing_go_import(state: AgentState) -> str:
    block = state.json_block or {}
    patch = block.get("patch_candidate")
    if not isinstance(patch, dict):
        return ""

    rel = patch.get("relative_path") or patch.get("file") or ""
    patched = patch.get("patched_snippet") or ""

    if not rel.endswith(".go"):
        return ""

    needed_imports = []
    if "fmt." in patched:
        needed_imports.append("fmt")
    if "errors." in patched:
        needed_imports.append("errors")

    if not needed_imports or not state.repo_path:
        return ""

    path = Path(state.repo_path) / rel
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8", errors="replace")

    missing = []
    for pkg in needed_imports:
        has_import = (
            f'import "{pkg}"' in text
            or re.search(rf'import\s*\([^)]*"{pkg}"[^)]*\)', text, flags=re.S)
        )
        if not has_import:
            missing.append(pkg)

    if missing:
        packages = ", ".join(f'"{p}"' for p in missing)
        return (
            f"patched_snippet uses Go package(s) {packages}, but target file does not import them. "
            "Use patch_plan to add the missing import(s) in the same file and replace the function, "
            "or avoid those packages."
        )

    return ""


def collect_patch_repair_reasons(state: AgentState) -> list[str]:
    reasons: list[str] = []

    structural_issue = patch_candidate_structural_issue(
        state.json_block,
        state.language,
    )
    if structural_issue:
        reasons.append("STRUCTURAL ERROR:\n" + structural_issue)

    import_issue = patch_candidate_missing_go_import(state)
    if import_issue:
        reasons.append("IMPORT ERROR:\n" + import_issue)

    return reasons


def control_missing_source_snippet(state: AgentState) -> bool:
    if not state.is_project_input or not state.control_result:
        return False

    patch_intent = state.control_result.get("patch_intent") or {}
    return not bool(patch_intent.get("source_snippet"))


def get_confidence_and_escalation(json_block: dict | None) -> tuple[float, bool]:
    if not json_block:
        return 0.0, True

    try:
        confidence = float(json_block.get("confidence", 0.0))
    except Exception:
        confidence = 0.0

    confidence = max(0.0, min(1.0, confidence))
    needs_escalation = bool(json_block.get("needs_escalation", False))
    return confidence, needs_escalation


def reject_ungrounded_patch(state: AgentState) -> None:
    if not state.json_block or not state.repo_path:
        return

    plan = state.json_block.get("patch_plan")
    if isinstance(plan, list) and plan:
        state.json_block["patch_candidate"] = None
        errors = validate_patch_plan_grounding(state.repo_path, plan)
        if errors:
            state.json_block["patch_plan_rejected"] = True
            state.json_block["patch_plan_errors"] = errors
            state.json_block["needs_escalation"] = True
            state.json_block["confidence"] = 0.0

            issues = state.json_block.get("issues") or []
            issues.insert(0, {
                "severity": "high",
                "type": "policy",
                "file": "",
                "symbol": "",
                "reason": "patch_plan failed grounding/safety checks before apply.",
                "fix": "Use existing files/snippets, avoid invented APIs/modules, and implement behavior instead of comment-only changes.",
            })
            state.json_block["issues"] = issues
            save_engineering_memory(
                session_id=state.session_id,
                memory_type="bug_pattern",
                value=(
                    "Patch plan grounding/safety failed: "
                    + "; ".join(errors[:3])
                ),
                importance=4,
                project_tag=state.project_tag,
            )

        return

    patch = state.json_block.get("patch_candidate")
    if not isinstance(patch, dict):
        return

    rel = patch.get("relative_path") or patch.get("file")
    target = patch.get("target_snippet") or ""

    if not rel or not target.strip():
        patch["rejected"] = True
        patch["reject_reason"] = "Patch missing file or target_snippet."
        state.json_block["needs_escalation"] = True
        state.json_block["confidence"] = 0.0
        return

    repo = Path(state.repo_path).resolve()
    path = (repo / rel).resolve()

    try:
        path.relative_to(repo)
    except ValueError:
        patch["rejected"] = True
        patch["reject_reason"] = "Patch target outside repo."
        state.json_block["needs_escalation"] = True
        state.json_block["confidence"] = 0.0
        return

    if not path.exists():
        patch["rejected"] = True
        patch["reject_reason"] = f"Patch file does not exist: {rel}"
        state.json_block["needs_escalation"] = True
        state.json_block["confidence"] = 0.0
        return

    text = path.read_text(encoding="utf-8", errors="replace")

    if target not in text:
        recovered = ""
        control = state.control_result or {}
        patch_intent = control.get("patch_intent") or {}

        candidate_source = patch_intent.get("source_snippet") or ""
        if candidate_source and candidate_source in text:
            recovered = candidate_source

        if recovered:
            print("⚠️ target_snippet drift detected; recovered exact source_snippet from CONTROL.")
            patch["target_snippet"] = recovered
            state.json_block["confidence"] = min(
                float(state.json_block.get("confidence", 0.0) or 0.0),
                0.85,
            )
            return

        patch["rejected"] = True
        patch["reject_reason"] = "target_snippet does not exist in target file."
        state.json_block["needs_escalation"] = True
        state.json_block["confidence"] = 0.0


_IDENT_RE = re.compile(r"\b[A-Za-z_][A-Za-z_0-9]*\b")
_STRING_OR_COMMENT_RE = re.compile(
    r"//.*?$|/\*.*?\*/|#.*?$|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'",
    re.M | re.S,
)

# Common keywords across supported languages — never count as 'invented'.
_LANGUAGE_KEYWORDS = {
    "if", "else", "elif", "for", "while", "do", "switch", "case", "default",
    "break", "continue", "return", "yield", "throw", "throws", "try", "catch", "finally",
    "true", "false", "null", "None", "True", "False", "nil",
    "var", "let", "const", "function", "def", "fn", "func", "class", "struct", "enum",
    "interface", "trait", "impl", "type", "record", "object",
    "public", "private", "protected", "internal", "static", "final", "abstract", "virtual",
    "override", "sealed", "readonly", "async", "await", "new", "this", "self", "super",
    "void", "int", "float", "double", "bool", "string", "char", "byte", "long", "short",
    "import", "from", "as", "use", "package", "namespace", "using", "module",
    "in", "is", "not", "and", "or", "with",
    "len", "range", "print", "str", "list", "dict", "set", "tuple",
}

# Language-specific built-in identifiers. Without this allowlist the
# safe_minimal gate flags standard things like `Error`, `trim`, `typeof`
# (JS) or `ValueError`, `enumerate` (Python) as "invented identifiers"
# even though they are part of the standard library / language surface.
_LANGUAGE_BUILTINS = {
    "javascript": {
        # Global constructors / namespaces
        "Error", "TypeError", "RangeError", "SyntaxError", "ReferenceError",
        "Promise", "Map", "Set", "WeakMap", "WeakSet", "Symbol",
        "String", "Number", "Boolean", "Array", "Object", "Date", "RegExp",
        "Math", "JSON", "console", "globalThis",
        "undefined", "NaN", "Infinity",
        # Operators that look like identifiers
        "typeof", "instanceof", "delete", "void", "of",
        # Common string methods
        "trim", "split", "slice", "replace", "includes", "indexOf", "lastIndexOf",
        "toLowerCase", "toUpperCase", "startsWith", "endsWith", "match",
        "padStart", "padEnd", "charAt", "charCodeAt",
        # Common array methods
        "push", "pop", "shift", "unshift", "map", "filter", "forEach",
        "find", "findIndex", "some", "every", "reduce", "reduceRight",
        "sort", "reverse", "concat", "flat", "flatMap", "join", "from",
        # Object / property
        "length", "hasOwnProperty", "toString", "valueOf",
        "keys", "values", "entries", "assign", "freeze",
        # Promise methods (overlaps with array.from but harmless in a set union)
        "then", "catch", "finally", "resolve", "reject", "all", "race", "allSettled",
    },
    "python": {
        # Built-in types
        "int", "float", "complex", "str", "bool", "bytes", "bytearray",
        "list", "tuple", "dict", "set", "frozenset", "object",
        # Exceptions
        "Exception", "BaseException",
        "ValueError", "TypeError", "KeyError", "IndexError", "RuntimeError",
        "AttributeError", "NotImplementedError", "StopIteration", "OSError",
        "FileNotFoundError", "PermissionError", "ArithmeticError",
        "ZeroDivisionError", "AssertionError", "ImportError",
        "ModuleNotFoundError", "LookupError",
        # Built-in functions
        "len", "range", "print", "enumerate", "zip",
        "map", "filter", "sorted", "reversed",
        "sum", "min", "max", "abs", "round", "pow", "divmod",
        "any", "all", "isinstance", "issubclass", "type", "repr",
        "hasattr", "getattr", "setattr", "delattr", "dir", "id", "hash",
        "iter", "next", "open", "super", "format", "input", "vars",
    },
}

# Map common aliases / legacy spellings to a canonical family key.
# Anything not in this map falls through to a direct lookup.
_LANGUAGE_FAMILY_ALIASES = {
    "js": "javascript",
    "javascript": "javascript",
    "node": "javascript",
    "nodejs": "javascript",
    # TypeScript shares JS's standard library surface for safe_minimal purposes.
    "ts": "javascript",
    "typescript": "javascript",
    "py": "python",
    "python": "python",
}


def _identifiers_in(snippet: str) -> set[str]:
    cleaned = _STRING_OR_COMMENT_RE.sub(" ", snippet or "")
    return set(_IDENT_RE.findall(cleaned))


_PLANNER_KEYS = {"goal", "subtasks", "risks", "missing_context"}


def reject_schema_drift(state: AgentState) -> None:
    """Reject planner-shaped JSON in reviewer mode and patch_plan in safe_minimal.

    Defense in depth: even when the prompt's schema lock is honored most of the
    time, the model still occasionally returns planner JSON (`{goal, subtasks}`)
    in reviewer mode, which leaves the pipeline with no patch_candidate. This
    guard rewrites such output to a clean policy-rejection block instead of
    silently producing zero-confidence noise.
    """
    block = state.json_block
    if not block:
        return

    # 1. Reviewer mode but model returned planner schema
    if state.mode == "reviewer" and any(k in block for k in _PLANNER_KEYS):
        new_block = {
            "summary": "Model returned planner-style JSON in reviewer mode.",
            "issues": [{
                "severity": "high",
                "type": "policy",
                "file": "",
                "symbol": "",
                "reason": (
                    "Reviewer mode requires patch_candidate JSON, but the model "
                    "returned goal/subtasks (planner schema)."
                ),
                "fix": (
                    "Retry with reviewer schema lock or switch to planner mode "
                    "intentionally."
                ),
            }],
            "patch_candidate": None,
            "confidence": 0.0,
            "needs_escalation": True,
        }
        state.json_block = new_block
        state.final_answer = json.dumps(new_block, ensure_ascii=False, indent=2)
        state.human_answer = state.final_answer
        return

    # 2. safe_minimal must never carry a patch_plan (defense in depth alongside
    #    _enforce_safe_minimal, which adds a more detailed issue entry).
    style = state.task_info.get("patch_style") or state.patch_style or "safe_minimal"
    if style == "safe_minimal" and block.get("patch_plan"):
        block["patch_plan"] = None
        block["patch_candidate"] = None
        block["confidence"] = 0.0
        block["needs_escalation"] = True
        state.json_block = block
        state.final_answer = json.dumps(block, ensure_ascii=False, indent=2)
        state.human_answer = state.final_answer


def _enforce_safe_minimal(state: AgentState) -> None:
    """For safe_minimal style, reject patches that introduce identifiers not
    present in the source. Replaces patch_candidate with null + needs_escalation
    instead of letting the user see an invented-API patch.

    Also rejects any patch_plan entirely — safe_minimal is single-file only.
    """
    style = state.task_info.get("patch_style") or state.patch_style or "safe_minimal"
    if style != "safe_minimal":
        return

    block = state.json_block or {}

    # 1. Reject patch_plan entirely — safe_minimal cannot create files or
    #    coordinate multi-file changes.
    plan = block.get("patch_plan")
    if isinstance(plan, list) and plan:
        op_count = len(plan)
        print(f"🛡️ safe_minimal gate: rejecting patch_plan ({op_count} ops not allowed)")
        block["patch_plan"] = None
        block["confidence"] = min(float(block.get("confidence", 0.0) or 0.0), 0.2)
        block["needs_escalation"] = True
        issues = block.get("issues") or []
        issues.insert(0, {
            "severity": "high",
            "type": "policy",
            "file": "",
            "symbol": "",
            "reason": (
                f"safe_minimal mode rejected patch_plan with {op_count} ops. "
                "Multi-file or new-file changes require balanced or vibe style."
            ),
            "fix": "Switch vibecoding style to balanced or vibe, or break the change into single-file patches.",
        })
        block["issues"] = issues
        state.json_block = block
        state.final_answer = json.dumps(block, ensure_ascii=False, indent=2)
        state.human_answer = state.final_answer
        return  # short-circuit — don't fall through to candidate check

    candidate = block.get("patch_candidate")
    if not isinstance(candidate, dict):
        return

    target = candidate.get("target_snippet") or ""
    patched = candidate.get("patched_snippet") or ""
    if not target or not patched:
        return

    lang = (state.language or "").lower().strip()
    family = _LANGUAGE_FAMILY_ALIASES.get(lang, lang)
    builtins = _LANGUAGE_BUILTINS.get(family, set())

    allowed = _identifiers_in(target) | _LANGUAGE_KEYWORDS | builtins
    used = _identifiers_in(patched)
    new_idents = sorted(used - allowed)
    if new_idents:
        print(f"🛡️ safe_minimal gate: rejecting patch — invented identifiers: {new_idents}")
        block["patch_candidate"] = None
        block["confidence"] = min(float(block.get("confidence", 0.0) or 0.0), 0.2)
        block["needs_escalation"] = True

        issues = block.get("issues") or []
        issues.insert(0, {
           "severity": "high",
            "type": "policy",
            "file": candidate.get("file") or candidate.get("relative_path") or "",
            "symbol": candidate.get("target_node_name") or "",
            "reason": (
                f"safe_minimal mode rejected the AI's patch because it introduced identifiers "
                f"not present in the source: {new_idents}."
            ),
            "fix": "Provide more context or use balanced/vibe mode.",
        })
        block["issues"] = issues
        state.json_block = block
        state.final_answer = json.dumps(block, ensure_ascii=False, indent=2)
        state.human_answer = state.final_answer
        return

    if _looks_like_noop_patch(target, patched):
        print("🛡️ safe_minimal gate: rejecting patch — patched function appears to be no-op")
        block["patch_candidate"] = None
        block["confidence"] = min(float(block.get("confidence", 0.0) or 0.0), 0.2)
        block["needs_escalation"] = True

        issues = block.get("issues") or []
        issues.insert(0, {
            "severity": "high",
            "type": "policy",
            "file": candidate.get("file") or candidate.get("relative_path") or "",
            "symbol": candidate.get("target_node_name") or "",
            "reason": (
                "safe_minimal mode rejected the patch because the patched function "
                "appears to only compute a local value without using it. This is likely "
                "a no-op patch."
            ),
            "fix": "Provide more context or use balanced/vibe mode for a broader design fix.",
        })
        block["issues"] = issues
        state.json_block = block
        state.final_answer = json.dumps(block, ensure_ascii=False, indent=2)
        state.human_answer = state.final_answer


def _looks_like_noop_patch(target: str, patched: str) -> bool:
    """
    Conservative no-op detector:
    reject patches that leave a function body with only local declarations
    and no state mutation, no call, no return, no throw.
    """
    body = patched or ""

    meaningful_patterns = [
        r"\breturn\b",
        r"\bthrow\b",
        r"\w+\s*\.\s*\w+\s*=",     # object.field = ...
        r"\w+\s*\[\s*.*?\s*\]\s*=", # arr[i] = ...
        r"\w+\s*=",                # assignment
        r"\w+\s*\(",               # call
    ]

    has_meaningful_action = any(re.search(p, body) for p in meaningful_patterns)

    # Local declaration only, e.g. `float velocity = ...;`
    local_decl_only = bool(re.search(
        r"\b(?:var|int|float|double|bool|string|Vector\d|Player)\s+\w+\s*=",
        body
    ))

    has_field_assignment = bool(re.search(r"\w+\s*\.\s*\w+\s*=", body))
    has_call = bool(re.search(r"\w+\s*\.\s*\w+\s*\(", body))
    has_return_or_throw = bool(re.search(r"\b(return|throw)\b", body))

    return local_decl_only and not has_field_assignment and not has_call and not has_return_or_throw
