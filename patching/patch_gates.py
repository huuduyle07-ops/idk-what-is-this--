from __future__ import annotations

import ast
import json
import re
import textwrap
from pathlib import Path

from agents.gemini_client import run_gemini_request
from core.agent_state import AgentState
from core.authoritative_binding_context import (
    AuthoritativeBindingContext,
    resolve_authoritative_candidate_bindings,
)
from core.local_binding_novelty import (
    classify_candidate_novelty,
    describe_candidate_novelty,
)
from core.validator import validate_patch_plan_grounding
from database.memory import save_engineering_memory
from patching.patch_grounding import enforce_patch_candidate_grounding

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


# --- Phase 12.5h: TS/JS duplicate-import promotion ---

_TS_JS_SUFFIXES = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}

_TS_NAMED_IMPORT_RE = re.compile(
    r'^[ \t]*import\s*\{\s*(?P<named>[^}]+?)\s*\}\s*from\s*[\'"](?P<module>[^\'"]+)[\'"]\s*;?\s*$',
    re.MULTILINE,
)


def _ts_extract_named_imports(text: str) -> list[dict]:
    """Return all `import { ... } from "M"` statements found in text.

    Each entry has: line (full source line, no trailing newline), module,
    named (list of imported specifier names).
    """
    results: list[dict] = []
    for match in _TS_NAMED_IMPORT_RE.finditer(text or ""):
        named_raw = match.group("named") or ""
        named = [n.strip() for n in named_raw.split(",") if n.strip()]
        if not named:
            continue
        results.append({
            "line": match.group(0).rstrip(),
            "module": match.group("module"),
            "named": named,
        })
    return results


def _remove_import_line(snippet: str, line: str) -> str:
    """Remove the import line plus its trailing newline; idempotent.

    Conservative: only removes byte-exact occurrences so we never corrupt
    surrounding code that incidentally shares text.
    """
    if not line or not snippet:
        return snippet
    cleaned = snippet.replace(line + "\n", "")
    if cleaned == snippet:
        cleaned = snippet.replace(line, "")
    return cleaned


def promote_ts_duplicate_import_candidate_to_patch_plan(state: AgentState) -> None:
    """Repair TS/JS patch_candidates that would create duplicate imports.

    Symptom this fixes: model emits a patched_snippet that begins with
    `import { addCents, multiplyCents } from "./money.ts"` but the target
    file already has `import { addCents } from "./money.ts"`. Applying the
    snippet verbatim would yield two import statements binding the same
    name (`addCents`) and Node would refuse the file with
    "Identifier 'X' has already been declared".

    Mirror of `promote_go_missing_import_candidate_to_patch_plan` for the
    opposite failure mode: instead of adding a missing import, we merge a
    duplicate one. Output is a 2+ op patch_plan that:
      - replaces the existing file-level import line with a merged version
        containing the union of specifiers, and
      - replaces the function with the patched_snippet minus the now-redundant
        import line.

    Safety: read-only inspection of the file the patch already targets; no
    new paths accepted; respects an existing patch_plan (caller wins);
    leaves drifted target_snippet alone for the grounding-recovery path.
    """
    block = state.json_block or {}

    # Do not touch real patch plans the model produced itself.
    if isinstance(block.get("patch_plan"), list) and block["patch_plan"]:
        return

    patch = block.get("patch_candidate")
    if not isinstance(patch, dict):
        return

    rel = patch.get("relative_path") or patch.get("file") or ""
    if Path(rel).suffix.lower() not in _TS_JS_SUFFIXES:
        return

    if not state.repo_path:
        return

    path = Path(state.repo_path) / rel
    if not path.exists():
        return

    target_snippet = patch.get("target_snippet") or ""
    patched_snippet = patch.get("patched_snippet") or ""
    if not target_snippet or not patched_snippet:
        return

    text = path.read_text(encoding="utf-8", errors="replace")
    if target_snippet not in text:
        # Let reject_ungrounded_patch (and the Phase 12.5g grounding
        # recovery) handle drift before we promote anything.
        return

    snippet_imports = _ts_extract_named_imports(patched_snippet)
    if not snippet_imports:
        return

    file_imports_by_module: dict[str, dict] = {}
    for imp in _ts_extract_named_imports(text):
        # First occurrence per module wins — that's the line we'd merge into.
        file_imports_by_module.setdefault(imp["module"], imp)

    plan_ops: list[dict] = []
    cleaned_snippet = patched_snippet
    affected_modules: list[str] = []

    for snippet_imp in snippet_imports:
        module = snippet_imp["module"]
        existing = file_imports_by_module.get(module)
        if existing is None:
            # Snippet imports a module the file does not yet import — no
            # duplicate risk. Leave it for the normal apply path.
            continue

        existing_named = list(dict.fromkeys(existing["named"]))
        snippet_named = list(dict.fromkeys(snippet_imp["named"]))
        new_specifiers = [n for n in snippet_named if n not in existing_named]

        if not new_specifiers:
            # Pure duplicate (snippet redeclares only names already imported).
            # Strip the redundant import line; no import-edit op needed.
            cleaned_snippet = _remove_import_line(cleaned_snippet, snippet_imp["line"])
            affected_modules.append(module)
            continue

        merged_named = existing_named + new_specifiers
        new_import_line = (
            "import { " + ", ".join(merged_named) + f' }} from "{module}";'
        )
        plan_ops.append({
            "op": "replace_snippet",
            "relative_path": rel,
            "target_snippet": existing["line"],
            "patched_snippet": new_import_line,
        })
        cleaned_snippet = _remove_import_line(cleaned_snippet, snippet_imp["line"])
        affected_modules.append(module)

    if not affected_modules:
        return

    cleaned_snippet = cleaned_snippet.lstrip("\n")

    function_op = {
        "op": "replace_snippet",
        "relative_path": rel,
        "target_snippet": target_snippet,
        "patched_snippet": cleaned_snippet,
    }

    block["patch_candidate"] = None
    block["patch_plan"] = plan_ops + [function_op]
    block["confidence"] = min(float(block.get("confidence", 0.85) or 0.85), 0.85)
    block["needs_escalation"] = False

    print(
        "🧩 Promoted TS/JS patch_candidate to patch_plan: deduplicated import(s) "
        + f"from {', '.join(affected_modules)} to avoid duplicate-binding SyntaxError."
    )

    state.json_block = block


# --- Phase 12.5i: TS/JS missing-import repair ---

_TS_EXPORT_DECL_RE = re.compile(
    r"(?m)^[ \t]*export\s+"
    r"(?:async\s+)?"
    r"(?:abstract\s+)?"
    r"(?:function|const|class|type|interface|enum|let|var)\s+"
    r"(?P<name>[A-Za-z_$][\w$]*)"
)

_TS_EXPORT_LIST_RE = re.compile(
    r"(?m)^[ \t]*export\s*\{(?P<body>[^}]+)\}"
)


def _ts_extract_named_exports(text: str) -> set[str]:
    """Return the set of names exported by `text` via named-export syntax.

    Handles:
      - export function/const/class/type/interface/enum/let/var NAME
      - export async function NAME
      - export abstract class NAME
      - export { A, B, C }
      - export { A as B }            (public name is B)
      - export { A } from "./mod"    (re-export)

    Skips `export default` because it has no named-import surface, and skips
    `export *` because it is an opaque passthrough.
    """
    if not text:
        return set()
    exports: set[str] = set()
    for match in _TS_EXPORT_DECL_RE.finditer(text):
        exports.add(match.group("name"))
    for match in _TS_EXPORT_LIST_RE.finditer(text):
        for raw in match.group("body").split(","):
            item = raw.strip()
            if not item:
                continue
            if " as " in item:
                _, alias = item.rsplit(" as ", 1)
                alias = alias.strip()
                if alias:
                    exports.add(alias)
            else:
                exports.add(item)
    return exports


def _resolve_inside_repo(repo_root: Path, rel: str) -> Path | None:
    """Resolve `rel` against `repo_root`. Returns None if it escapes the repo
    or the input is malformed. Required by the path-traversal rule.
    """
    if not rel:
        return None
    raw = Path(rel)
    if raw.is_absolute():
        return None
    try:
        resolved = (repo_root / rel).resolve()
    except Exception:
        return None
    try:
        resolved.relative_to(repo_root)
    except ValueError:
        return None
    return resolved


def _compute_ts_module_specifier(target_file: Path, sibling_file: Path) -> str | None:
    """Build a `./...`-style ES module specifier that points from
    `target_file` at `sibling_file`. Only handles same-directory siblings
    (deliberately conservative — matches the "local sibling modules" scope).

    Preserves the sibling's actual file extension so the result matches the
    repo's existing import style (e.g. `./money.ts` rather than `./money`).
    """
    try:
        rel = sibling_file.relative_to(target_file.parent)
    except ValueError:
        return None
    parts = rel.as_posix()
    if not parts or parts.startswith(".."):
        return None
    return "./" + parts


def _first_nonblank_line(text: str) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line
    return ""


def _strip_import_alias(name: str) -> str:
    """`foo as bar` → `bar`; `foo` → `foo`. The local binding is what matters."""
    if " as " in name:
        _, alias = name.rsplit(" as ", 1)
        return alias.strip()
    return name.strip()


def promote_ts_missing_import_candidate_to_patch_plan(state: AgentState) -> None:
    """Repair TS/JS patch_candidates that use a name they did not import.

    Symptom this fixes: model returns a clean function-only patched_snippet
    (no top-of-file import line) that references e.g. `multiplyCents`, but
    the target file's existing imports only cover `addCents`. Applying the
    snippet verbatim crashes Node at runtime with
    "ReferenceError: multiplyCents is not defined".

    Mirror of `promote_ts_duplicate_import_candidate_to_patch_plan` for the
    opposite failure mode: instead of merging a colliding import, we add a
    missing one when a sibling module actually exports the new name. Output
    is a 2+ op patch_plan that:
      - merges the missing specifier into the existing import line when the
        file already imports something from the same module, OR
      - inserts a fresh top-level named import when the file has no import
        from that module yet, AND
      - replaces the function with the unchanged patched_snippet.

    Safety:
      - read-only inspection of files inside repo_path,
      - refuses paths that resolve outside repo_root (path-traversal guard),
      - respects an existing patch_plan (caller wins),
      - leaves drifted target_snippet alone for the grounding-recovery path,
      - never invents an import for a name no local module exports.
    """
    block = state.json_block or {}

    if isinstance(block.get("patch_plan"), list) and block["patch_plan"]:
        return

    patch = block.get("patch_candidate")
    if not isinstance(patch, dict):
        return

    rel = patch.get("relative_path") or patch.get("file") or ""
    if Path(rel).suffix.lower() not in _TS_JS_SUFFIXES:
        return

    if not state.repo_path:
        return

    repo_root = Path(state.repo_path).resolve()
    target_path = _resolve_inside_repo(repo_root, rel)
    if target_path is None or not target_path.is_file():
        return

    target_snippet = patch.get("target_snippet") or ""
    patched_snippet = patch.get("patched_snippet") or ""
    if not target_snippet or not patched_snippet:
        return

    try:
        file_text = target_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return

    if target_snippet not in file_text:
        return

    target_idents = _identifiers_in(target_snippet)
    patched_idents = _identifiers_in(patched_snippet)
    js_builtins = _LANGUAGE_BUILTINS.get("javascript", set())
    new_idents = patched_idents - target_idents - _LANGUAGE_KEYWORDS - js_builtins
    if not new_idents:
        return

    snippet_imports = _ts_extract_named_imports(patched_snippet)
    for imp in snippet_imports:
        for raw_name in imp["named"]:
            new_idents.discard(_strip_import_alias(raw_name))

    file_imports = _ts_extract_named_imports(file_text)
    for imp in file_imports:
        for raw_name in imp["named"]:
            new_idents.discard(_strip_import_alias(raw_name))

    if not new_idents:
        return

    target_dir = target_path.parent
    try:
        target_dir.relative_to(repo_root)
    except ValueError:
        return

    siblings: list[Path] = []
    for ext in _TS_JS_SUFFIXES:
        try:
            siblings.extend(target_dir.glob(f"*{ext}"))
        except Exception:
            continue

    exports_by_module: dict[str, set[str]] = {}
    for sibling in siblings:
        try:
            sib_resolved = sibling.resolve()
        except Exception:
            continue
        if sib_resolved == target_path:
            continue
        try:
            sib_resolved.relative_to(repo_root)
        except ValueError:
            continue
        if not sib_resolved.is_file():
            continue
        try:
            sib_text = sib_resolved.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        exports = _ts_extract_named_exports(sib_text)
        if not exports:
            continue
        module = _compute_ts_module_specifier(target_path, sib_resolved)
        if module is None:
            continue
        exports_by_module[module] = exports

    if not exports_by_module:
        return

    module_to_new_names: dict[str, list[str]] = {}
    for ident in sorted(new_idents):
        for module in sorted(exports_by_module.keys()):
            if ident in exports_by_module[module]:
                module_to_new_names.setdefault(module, []).append(ident)
                break

    if not module_to_new_names:
        return

    file_imports_by_module: dict[str, dict] = {}
    for imp in file_imports:
        file_imports_by_module.setdefault(imp["module"], imp)

    plan_ops: list[dict] = []
    matched_idents: list[str] = []

    for module in sorted(module_to_new_names.keys()):
        names = module_to_new_names[module]
        if not names:
            continue
        existing = file_imports_by_module.get(module)
        if existing is not None:
            existing_named = list(dict.fromkeys(existing["named"]))
            additions = [n for n in names if n not in existing_named]
            if not additions:
                continue
            merged_named = existing_named + additions
            new_line = (
                "import { " + ", ".join(merged_named) + f' }} from "{module}";'
            )
            plan_ops.append({
                "op": "replace_snippet",
                "relative_path": rel,
                "target_snippet": existing["line"],
                "patched_snippet": new_line,
            })
            matched_idents.extend(additions)
        else:
            anchor = _first_nonblank_line(file_text)
            if not anchor or anchor not in file_text:
                continue
            new_line = (
                "import { " + ", ".join(names) + f' }} from "{module}";'
            )
            plan_ops.append({
                "op": "replace_snippet",
                "relative_path": rel,
                "target_snippet": anchor,
                "patched_snippet": new_line + "\n" + anchor,
            })
            matched_idents.extend(names)

    if not plan_ops:
        return

    function_op = {
        "op": "replace_snippet",
        "relative_path": rel,
        "target_snippet": target_snippet,
        "patched_snippet": patched_snippet,
    }

    block["patch_candidate"] = None
    block["patch_plan"] = plan_ops + [function_op]
    block["confidence"] = min(float(block.get("confidence", 0.85) or 0.85), 0.85)
    block["needs_escalation"] = False

    print(
        "🧩 Promoted TS/JS patch_candidate to patch_plan: added missing import(s) for "
        + ", ".join(sorted(set(matched_idents)))
        + "."
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


def _language_for_relpath(rel: str) -> str:
    """Map a repo-relative file path to a TREESITTER_LANG_MAP key.

    Returns "" for unknown extensions so the caller can short-circuit.
    """
    suffix = Path(rel).suffix.lower()
    if not suffix:
        return ""
    from config import LANGUAGE_MAP

    return LANGUAGE_MAP.get(suffix, "") or ""


def _ground_target_via_symbol_lookup(*, rel: str, text: str, target_node_name: str) -> str:
    """Re-ground target_snippet using symbol lookup.

    Read-only. Only inspects `text`, which is the already-validated content
    of the file the patch targets — no new paths are accepted, so the
    repo-traversal guard upstream still applies.

    Tries tree-sitter first (precise, language-aware) and falls back to a
    conservative regex matcher when tree-sitter is unavailable for the
    language. Returns the symbol's actual body if found *and* present
    verbatim in `text`, otherwise the empty string.
    """
    if not target_node_name or not text:
        return ""
    body = _ground_via_treesitter(rel, text, target_node_name)
    if body:
        return body
    return _ground_via_regex(rel, text, target_node_name)


def _ground_via_treesitter(rel: str, text: str, target_node_name: str) -> str:
    language = _language_for_relpath(rel)
    if not language:
        return ""
    try:
        from core.treesitter_parse import parse_code_with_treesitter

        parsed = parse_code_with_treesitter(text, language)
    except Exception:
        return ""
    for sym in parsed.get("symbols") or []:
        if sym.get("name") != target_node_name:
            continue
        content = sym.get("content") or ""
        if content and content in text:
            return content
    return ""


_BRACE_SUFFIXES = {
    ".js", ".jsx", ".mjs", ".cjs",
    ".ts", ".tsx",
    ".go",
    ".rs",
    ".c", ".h", ".cpp", ".cxx", ".cc", ".hpp", ".hxx",
    ".cs", ".java", ".kt",
}


def _ground_via_regex(rel: str, text: str, target_node_name: str) -> str:
    suffix = Path(rel).suffix.lower()
    if suffix == ".py":
        return _extract_python_def(text, target_node_name)
    if suffix in _BRACE_SUFFIXES:
        return _extract_brace_function(text, target_node_name)
    return ""


def _extract_brace_function(text: str, name: str) -> str:
    """Find a brace-delimited function/method by name and return its full span.

    Conservative: requires the name to appear immediately followed by `(` on
    exactly one declaration-shaped line. Returns "" on ambiguity so the
    recovery falls through cleanly to grounding_error.
    """
    pattern = re.compile(
        r"(?m)^([ \t]*)\S[^\n]*\b" + re.escape(name) + r"\s*\([^\n]*$"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return ""
    match = matches[0]
    decl_start = match.start()
    brace_idx = text.find("{", match.end())
    if brace_idx == -1:
        return ""
    depth = 0
    i = brace_idx
    while i < len(text):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[decl_start : i + 1]
        i += 1
    return ""


def _extract_python_def(text: str, name: str) -> str:
    """Find a top-level `def NAME(` block and return its full source span."""
    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)def\s+" + re.escape(name) + r"\s*\("
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        return ""
    match = matches[0]
    decl_start = match.start()
    indent_len = len(match.group("indent"))
    nl = text.find("\n", match.end())
    pos = len(text) if nl == -1 else nl + 1
    while pos < len(text):
        line_end = text.find("\n", pos)
        if line_end == -1:
            line_end = len(text)
        line = text[pos:line_end]
        if line.strip():
            leading = len(line) - len(line.lstrip(" \t"))
            if leading <= indent_len:
                return text[decl_start:pos].rstrip("\n")
        pos = line_end + 1 if line_end < len(text) else len(text)
    return text[decl_start:].rstrip("\n")


def _grounding_excerpt(text: str, target_node_name: str, *, context_lines: int = 4) -> str:
    """Return a short excerpt around the first occurrence of target_node_name.

    Used in grounding_error so escalation has a useful diagnostic instead of
    just "snippet not found". Empty string when nothing matches.
    """
    if not target_node_name or not text or target_node_name not in text:
        return ""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if target_node_name in line:
            start = max(0, index - context_lines)
            end = min(len(lines), index + context_lines + 1)
            return "\n".join(lines[start:end])
    return ""


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
        # Recovery 1 (existing): replace target_snippet with CONTROL's exact
        # source_snippet if it actually appears in the target file.
        control = state.control_result or {}
        patch_intent = control.get("patch_intent") or {}
        candidate_source = patch_intent.get("source_snippet") or ""
        if candidate_source and candidate_source in text:
            print("⚠️ target_snippet drift detected; recovered exact source_snippet from CONTROL.")
            patch["target_snippet"] = candidate_source
            state.json_block["confidence"] = min(
                float(state.json_block.get("confidence", 0.0) or 0.0),
                0.85,
            )
            return

        # Recovery 2 (Phase 12.5g): re-ground via tree-sitter symbol lookup.
        # If the model gave us a real target_node_name and that symbol exists
        # in the actual target file, replace target_snippet with the symbol's
        # actual body. Read-only and only consults the file the patch already
        # targets (no new paths accepted), so traversal safety is unchanged.
        target_node_name = (patch.get("target_node_name") or "").strip()
        recovered_body = ""
        if target_node_name:
            recovered_body = _ground_target_via_symbol_lookup(
                rel=rel,
                text=text,
                target_node_name=target_node_name,
            )
        if recovered_body:
            print(
                f"🩹 target_snippet drift recovered via symbol lookup "
                f"for {target_node_name!r} in {rel}."
            )
            patch["target_snippet"] = recovered_body
            state.json_block["confidence"] = min(
                float(state.json_block.get("confidence", 0.0) or 0.0),
                0.75,
            )
            return

        # Both recoveries failed — emit an explicit grounding_error so the
        # escalation step has something to act on instead of a silent reject.
        tried = ["control_source_snippet"]
        if target_node_name:
            tried.append("symbol_lookup")
        patch["rejected"] = True
        patch["reject_reason"] = "target_snippet does not exist in target file."
        patch["grounding_error"] = {
            "kind": "snippet_drift_unresolved",
            "tried": tried,
            "target_node_name": target_node_name,
            "file_excerpt": _grounding_excerpt(text, target_node_name),
        }
        state.json_block["needs_escalation"] = True
        state.json_block["confidence"] = 0.0


def _safe_repo_file_text(repo_path: str, rel: str) -> "str | None":
    """Read `rel` from `repo_path`, but only if it stays inside the repo.

    Read-only and traversal-guarded — same boundary rule as the other gates.
    Returns None when the path is unsafe, missing, or unreadable.
    """
    if not repo_path or not rel:
        return None
    repo = Path(repo_path).resolve()
    try:
        path = (repo / rel).resolve()
        path.relative_to(repo)
    except (ValueError, OSError):
        return None
    if not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _gather_candidate_grounding_sources(state: AgentState, candidate: dict) -> list:
    """Collect real source text to quote-ground a patch_candidate against.

    Sources = the on-disk target file (when present and inside the repo) plus
    retrieved CONTROL context (patch_intent.source_snippet and any
    related_snippets). Each entry is a (path, text) pair.
    """
    sources: list = []

    rel = candidate.get("relative_path") or candidate.get("file") or ""
    if state.repo_path and rel:
        text = _safe_repo_file_text(state.repo_path, rel)
        if text is not None:
            sources.append((rel, text))

    control = state.control_result or {}
    patch_intent = control.get("patch_intent") or {}
    source_snippet = patch_intent.get("source_snippet")
    if isinstance(source_snippet, str) and source_snippet:
        sources.append((patch_intent.get("target_file") or rel or None, source_snippet))

    for related in control.get("related_snippets") or []:
        if not isinstance(related, dict):
            continue
        snippet = related.get("snippet")
        if isinstance(snippet, str) and snippet:
            sources.append((related.get("file"), snippet))

    return sources


def reject_ungrounded_candidate_quotes(state: AgentState) -> None:
    """Phase 12.9 — quote-only grounding for patch_candidate.

    Defense-in-depth layered on top of `reject_ungrounded_patch`: a
    hallucinated target_snippet must never surface as a valid candidate in the
    final patch result. The candidate is grounded against the on-disk target
    file (when available) AND retrieved source context; if target_snippet is
    not an exact substring of any real source, the candidate is marked invalid,
    patch_plan is nulled, confidence / control confidence are lowered, and a
    clear warning is recorded.

    Preserves existing behavior for valid exact snippets, and no-ops when there
    is no real source to ground against (so it never invents new rejections).
    """
    block = state.json_block
    if not isinstance(block, dict):
        return

    candidate = block.get("patch_candidate")
    if not isinstance(candidate, dict):
        return

    sources = _gather_candidate_grounding_sources(state, candidate)
    if not sources:
        # Nothing real to check against — leave the primary gate's verdict alone
        # rather than rejecting an unprovable candidate.
        return

    result = enforce_patch_candidate_grounding(block, sources)

    if not result.is_grounded:
        # CONTROL.SAFETY.LIVE.1: patch quote failure demotes the model patch,
        # not localization.  The ranked candidate may remain the best place to
        # inspect even though this particular patch was ungrounded.
        return


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


def _identifiers_in(snippet: str, *, language: str = "") -> set[str]:
    if language == "python":
        try:
            tree = ast.parse(textwrap.dedent(snippet or ""))
        except (SyntaxError, ValueError):
            # Unsupported fragments retain the conservative lexical check.
            pass
        else:
            identifiers: set[str] = set()
            for node in ast.walk(tree):
                # These AST fields are identifier-bearing syntax, including
                # expressions inside formatted strings. Literal text and string
                # prefixes never become identifiers or hide a callable.
                for field in ("id", "attr", "arg", "name", "rest"):
                    value = getattr(node, field, None)
                    if isinstance(value, str):
                        identifiers.update(value.split("."))
                if isinstance(node, ast.ImportFrom) and node.module:
                    identifiers.update(node.module.split("."))
                if isinstance(node, ast.alias) and node.asname:
                    identifiers.add(node.asname)
                if isinstance(node, (ast.Global, ast.Nonlocal)):
                    identifiers.update(node.names)
            return identifiers
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


def _enforce_safe_minimal(
    state: AgentState,
    *,
    authoritative_binding_context: AuthoritativeBindingContext | None = None,
    authoritative_source: str = "",
) -> None:
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

    # PATCH.MINIMAL.LIVE.3 — the candidate cannot create its own baseline.
    # Only a context built from the authoritative pre-candidate file and still
    # matching that whole-file identity, target path, target symbol and target
    # snippet participates.  Missing or stale context is exactly the legacy
    # conservative environment.
    context_current = False
    if authoritative_binding_context is not None:
        context_current = authoritative_binding_context.is_current_for(
            authoritative_source=authoritative_source,
            source_path=(
                candidate.get("relative_path") or candidate.get("file") or ""
            ),
            target_symbol=(
                candidate.get("target_node_name")
                or candidate.get("target_symbol")
                or ""
            ),
            target_snippet=target,
        )
        block.update(
            authoritative_binding_context.as_telemetry(current=context_current)
        )
    effective_binding_context = (
        authoritative_binding_context if context_current else None
    )

    allowed = _identifiers_in(target, language=family) | _LANGUAGE_KEYWORDS | builtins
    used = _identifiers_in(patched, language=family)
    lexical_delta = used - allowed
    authoritative_names = frozenset(
        resolve_authoritative_candidate_bindings(
            effective_binding_context, patched_snippet=patched
        )
        if effective_binding_context is not None
        else frozenset()
    ) & lexical_delta
    if effective_binding_context is not None:
        block["authoritative_binding_context_reused_names"] = sorted(
            authoritative_names
        )
    new_idents = sorted(lexical_delta - authoritative_names)

    # PATCH.MINIMAL.LIVE.2 — a lexically new identifier is not by itself
    # evidence that the candidate expanded what the program can reach.  Before
    # rejecting the delta, classify it structurally: a name the same candidate
    # binds as a local of the one existing function it edits is bounded local
    # implementation novelty, and everything else — imports, definitions,
    # parameters, globals, attribute stores, novel members and callables —
    # keeps the previous conservative treatment.  Classification decides
    # eligibility for candidate verification only.  It is not a correctness
    # verdict, and it grants no review, approval or execution authority.
    novelty = None
    if new_idents:
        # Local import: the fingerprint primitive lives next to the sandbox and
        # is only needed on the path that actually classifies something.
        from core.candidate_sandbox_validation import (
            candidate_fingerprint_from_payload,
        )

        novelty = classify_candidate_novelty(
            target_snippet=target,
            patched_snippet=patched,
            language=family,
            allowed_identifiers=allowed | authoritative_names,
            target_node_kind=str(candidate.get("target_node_kind") or ""),
            target_node_name=str(candidate.get("target_node_name") or ""),
            authoritative_binding_context=effective_binding_context,
        )
        block.update(
            novelty.as_telemetry(
                candidate_fingerprint=candidate_fingerprint_from_payload(block),
                novel_identifiers=new_idents,
            )
        )

    if new_idents and novelty is not None and novelty.admits(new_idents):
        # Admitted, and nothing more: the candidate survives this gate and goes
        # on to the same verification it always faced.
        print(
            f"🛡️ safe_minimal gate: {novelty.primary_reason} — "
            f"{sorted(novelty.local_binding_names)} bound inside "
            f"{list(novelty.containing_functions)}"
        )
        print(f"🧭 {describe_candidate_novelty(novelty)}")
    elif new_idents:
        reason_code = novelty.rejection_reason(new_idents) if novelty else ""
        unexplained = (
            list(novelty.unexplained_identifiers(new_idents))
            if novelty
            else list(new_idents)
        ) or list(new_idents)
        print(
            f"🛡️ safe_minimal gate: rejecting patch — {reason_code}: "
            f"{unexplained}"
        )
        block["patch_candidate"] = None
        block["confidence"] = min(float(block.get("confidence", 0.0) or 0.0), 0.2)
        block["needs_escalation"] = True

        issues = block.get("issues") or []
        issues.insert(0, {
           "severity": "high",
            "type": "policy",
            "file": candidate.get("file") or candidate.get("relative_path") or "",
            "symbol": candidate.get("target_node_name") or "",
            "novelty_reason": reason_code,
            "reason": (
                f"safe_minimal mode rejected the AI's patch as {reason_code}: "
                f"{unexplained} "
                f"{'is' if len(unexplained) == 1 else 'are'} not present in the "
                "source and not a bounded local binding of the existing "
                "function being edited."
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
