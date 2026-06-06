import os
import re
import shutil
import subprocess, sys
import shlex
from pathlib import Path
from typing import Tuple, Dict, Optional
from dataclasses import dataclass

from core.validation_command import validation_command_safety_issue
# Compilers whose runtime DLLs frequently collide with Anaconda's bundled
# mingw-w64 stubs (or other parallel installs) on Windows. When we see one of
# these on PATH, we prepend its install dir to PATH for the child process so
# the freshly-built binary loads the matching libstdc++/libgcc/libwinpthread
# instead of crashing with NTSTATUS 0xC0000005 at startup due to ABI drift.
_NATIVE_COMPILERS = ("g++", "gcc", "clang++", "clang")

@dataclass(frozen=True)
class GroundingResult:
    is_grounded: bool
    reason: str
    matched_file: str | None = None
    matched_snippet: str | None = None


# Phase 12.9 — the single human-readable rejection message for an ungrounded
# patch candidate. Kept here (next to GroundingResult) so every gate that
# rejects a hallucinated target_snippet reports the exact same wording.
UNGROUNDED_PATCH_CANDIDATE_WARNING = (
    "Rejected ungrounded patch candidate: target_snippet was not found in source."
)


def source_snippet_exists(snippet: str, source_text: str) -> bool:
    """True iff `snippet` appears verbatim (exact substring) in `source_text`.

    Quote-only grounding primitive: no whitespace normalization, no fuzzy
    matching. An empty snippet or empty source is never grounded. This is the
    single substring check every candidate/plan grounding builds on, so the
    "copied byte-exactly from source" rule cannot drift between gates.
    """
    if not snippet or not source_text:
        return False
    return snippet in source_text


def _candidate_field(candidate, key):
    if candidate is None:
        return None
    if isinstance(candidate, dict):
        return candidate.get(key)
    return getattr(candidate, key, None)


def _candidate_target_snippet(candidate) -> str:
    return _candidate_field(candidate, "target_snippet") or ""


def _candidate_file(candidate) -> "str | None":
    return (
        _candidate_field(candidate, "relative_path")
        or _candidate_field(candidate, "file")
        or _candidate_field(candidate, "file_path")
        or None
    )


def _iter_source_texts(source_text_or_files):
    """Normalize the accepted source shapes into (path, text) pairs.

    Accepts a single source string, a {path: text} mapping, an iterable of
    (path, text) pairs, or an iterable of plain source strings.
    """
    src = source_text_or_files
    if src is None:
        return
    if isinstance(src, str):
        yield (None, src)
        return
    if isinstance(src, dict):
        for path, text in src.items():
            if isinstance(text, str):
                yield (path, text)
        return
    try:
        iterator = iter(src)
    except TypeError:
        return
    for item in iterator:
        if isinstance(item, str):
            yield (None, item)
        elif (
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[1], str)
        ):
            yield (item[0], item[1])


def validate_patch_candidate_grounding(candidate, source_text_or_files) -> GroundingResult:
    """Quote-ground a single patch candidate's target_snippet.

    `candidate` is a patch_candidate dict (or any object exposing
    `target_snippet` / `relative_path` / `file`). `source_text_or_files` is the
    real source to ground against — the target file's text *or* retrieved
    source context — given as a string, a {path: text} mapping, or an iterable
    of (path, text) pairs / plain source strings.

    `is_grounded` is True only when target_snippet is an EXACT substring of one
    of the provided sources. We prefer exact quote grounding over any
    semantic/fuzzy guessing.
    """
    target = _candidate_target_snippet(candidate)
    if not target.strip():
        return GroundingResult(False, "patch_candidate missing target_snippet")

    for path, text in _iter_source_texts(source_text_or_files):
        if source_snippet_exists(target, text):
            return GroundingResult(
                True,
                "target_snippet found verbatim in source",
                matched_file=path or _candidate_file(candidate),
                matched_snippet=target,
            )

    return GroundingResult(False, UNGROUNDED_PATCH_CANDIDATE_WARNING)

def _native_toolchain_env() -> Optional[dict]:
    """Return an env dict with the native compiler's bin dir prepended to PATH,
    or None when no fix is needed (non-Windows, or no compiler on PATH)."""
    if sys.platform != "win32":
        return None
    for tool in _NATIVE_COMPILERS:
        found = shutil.which(tool)
        if not found:
            continue
        tool_dir = str(Path(found).resolve().parent)
        current_path = os.environ.get("PATH", "")
        first_segment = current_path.split(os.pathsep)[0] if current_path else ""
        if first_segment.lower() == tool_dir.lower():
            return None
        env = os.environ.copy()
        env["PATH"] = tool_dir + os.pathsep + current_path
        return env
    return None


def _looks_like_go_validation_command(command: str) -> bool:
    return re.match(r"^\s*(?:go|go\.exe)\b", command or "", flags=re.IGNORECASE) is not None


def _validation_command_env(command: str, cwd: str) -> Optional[dict]:
    env = _native_toolchain_env()

    if sys.platform != "win32" or not _looks_like_go_validation_command(command):
        return env

    env = dict(env) if env is not None else os.environ.copy()
    try:
        go_root = Path(cwd) / ".agent" / "validation_go"
        tmp_dir = go_root / "tmp"
        cache_dir = go_root / "cache"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cache_dir.mkdir(parents=True, exist_ok=True)
        env["GOTMPDIR"] = str(tmp_dir)
        env["GOCACHE"] = str(cache_dir)
    except OSError:
        pass
    return env


def run_validation_command(command: str, cwd: str, timeout: int = 30) -> tuple[bool, str]:
    if not command:
        return True, ""

    # Phase 13.6 — shared shell chokepoint. Every validation command (user text,
    # hardcoded default, or DB/profile-derived) flows through here before the
    # shell sees it, so this is the one place to screen for destructive ops. With
    # shell=True below, an unscreened command would run verbatim — so refuse here
    # and never execute it.
    issue = validation_command_safety_issue(command)
    if issue:
        return False, f"❌ Validation command blocked for safety: {issue}"

    try:
        is_windows = sys.platform == "win32"

        shell_executable = None
        if not is_windows:
            shell_executable = "/bin/bash" if Path("/bin/bash").exists() else "/bin/sh"

        result = subprocess.run(
            command,
            cwd=cwd,
            shell=True,
            executable=shell_executable,
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
            env=_validation_command_env(command, cwd),
        )

        output = (result.stdout or "") + (result.stderr or "")
        return result.returncode == 0, output.strip()

    except subprocess.TimeoutExpired as e:
        output = ((e.stdout or "") + (e.stderr or "")) if hasattr(e, "stdout") else ""
        return False, f"❌ Validation Timeout after {timeout}s\n{output}"

    except Exception as e:
        return False, f"❌ Execution Error: {e}"

SOURCE_EXTENSIONS = {
    ".py", ".rs", ".js", ".jsx", ".ts", ".tsx", ".go", ".java",
    ".c", ".h", ".cpp", ".hpp", ".cs", ".php", ".rb", ".swift",
    ".kt", ".kts", ".lua", ".dart",
}

SKIP_SOURCE_DIRS = {
    ".git", ".agent", "__pycache__", ".pytest_cache", ".mypy_cache",
    "target", "node_modules", "dist", "build", ".venv", "venv",
}

RUST_ALLOWED_BARE_CALLS = {
    # control/keywords captured by the simple regex
    "if", "for", "while", "loop", "match", "return",
    # common std/debug/test helpers and constructors/macros without the !
    "println", "eprintln", "print", "format", "vec", "panic", "assert",
    "assert_eq", "assert_ne", "dbg", "todo", "unimplemented",
    "Some", "None", "Ok", "Err", "String", "Vec", "HashMap", "HashSet",
    "BTreeMap", "BTreeSet", "Option", "Result", "Box", "Default",
}

INVENTION_PRONE_PREFIXES = (
    "get_", "set_", "update_", "fetch_", "load_", "save_", "find_",
    "lookup_", "run_", "build_", "create_", "validate_", "check_",
    "is_", "has_", "maybe_", "ensure_", "apply_",
)

generic_data_structure_files = {
    "avl.rs",
    "tree.rs",
    "graph.rs",
    "heap.rs",
    "stack.rs",
    "queue.rs",
}

application_flow_names = {
    "change_name",
    "save_to_csv",
    "load_from_csv",
    "execute_mission",
}

FEATURE_TERMS = re.compile(
    r"\b(aml|anti[-_ ]?money|blacklist|sanction|screening|launder|fraud)\b",
    re.IGNORECASE,
)

DATA_STRUCTURE_FILE_RE = re.compile(
    r"(^|/|\\)(avl|trie|tree|heap|queue|stack|graph|linked[_-]?list)\.",
    re.IGNORECASE,
)


def _is_source_file(path: Path) -> bool:
    return path.suffix.lower() in SOURCE_EXTENSIONS


def _iter_repo_source_files(repo: Path):
    for path in repo.rglob("*"):
        if not path.is_file() or not _is_source_file(path):
            continue
        if any(part in SKIP_SOURCE_DIRS for part in path.parts):
            continue
        yield path


def _read_repo_source_text(repo: Path) -> str:
    chunks = []
    for path in _iter_repo_source_files(repo):
        try:
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
        except OSError:
            continue
    return "\n".join(chunks)


def _collect_defined_symbols(text: str) -> set[str]:
    """Collect symbols that are already defined in repo text or inside the plan."""
    symbols: set[str] = set()

    patterns = [
        # Python
        r"\bdef\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"\bclass\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        # Rust
        r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"\b(?:struct|enum|trait|mod|type)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        r"\b(?:const|static)\s+([A-Za-z_][A-Za-z0-9_]*)\b",
        # JS/TS
        r"\bfunction\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"\b(?:const|let|var)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_][A-Za-z0-9_]*)\s*=>",
        # Go / Java / C-like functions, conservative
        r"\bfunc\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
    ]
    for pattern in patterns:
        symbols.update(re.findall(pattern, text))
    return symbols


def _collect_rust_modules(repo: Path, repo_text: str, plan: list[dict]) -> set[str]:
    modules = set(re.findall(r"\b(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", repo_text))

    src_dir = repo / "src"
    if src_dir.exists():
        for path in src_dir.glob("*.rs"):
            if path.name != "main.rs":
                modules.add(path.stem)

    for op in plan:
        rel = op.get("relative_path") or op.get("file") or ""
        rel_path = Path(rel)
        if rel_path.suffix == ".rs" and rel_path.parts and rel_path.parts[0] == "src":
            if rel_path.name != "main.rs":
                modules.add(rel_path.stem)
        content = op.get("content") or op.get("patched_snippet") or ""
        modules.update(re.findall(r"\b(?:pub\s+)?mod\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", content))

    return modules


def _strip_comments_and_ws(text: str) -> str:
    """Remove common comments + whitespace to detect comment-only patch ops."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r"#.*", "", text)
    return re.sub(r"\s+", "", text)


def _op_text(op: dict) -> str:
    return op.get("patched_snippet") or op.get("content") or ""


def _validate_comment_only_feature_ops(plan: list[dict]) -> list[str]:
    errors: list[str] = []
    for i, op in enumerate(plan):
        if op.get("op") != "replace_snippet":
            continue
        target = op.get("target_snippet") or ""
        patched = op.get("patched_snippet") or ""
        if not target or not patched:
            continue
        if not FEATURE_TERMS.search(patched):
            continue
        if _strip_comments_and_ws(target) == _strip_comments_and_ws(patched):
            errors.append(
                f"op #{i}: feature/security change appears to be comment-only; "
                "implement behavior, not just comments."
            )
    return errors


def _validate_rust_crate_paths(
    repo: Path,
    plan: list[dict],
    existing_symbols: set[str],
    patch_symbols: set[str],
    rust_modules: set[str],
) -> list[str]:
    errors: list[str] = []
    available_symbols = existing_symbols | patch_symbols

    for i, op in enumerate(plan):
        patched = _op_text(op)
        if not patched:
            continue

        if "crate::main::" in patched:
            errors.append(
                f"op #{i}: suspicious Rust path crate::main::...; main.rs is an entrypoint, "
                "not a stable module API. Create/import a real module instead."
            )

        # Examples captured: crate::agent::Agent, crate::aml::is_blacklisted
        for match in re.finditer(
            r"\bcrate::([A-Za-z_][A-Za-z0-9_]*(?:::[A-Za-z_][A-Za-z0-9_]*)*)\b",
            patched,
        ):
            parts = match.group(1).split("::")
            first = parts[0]
            last = parts[-1]

            if first == "main":
                # already reported above
                continue

            if first not in rust_modules and first not in available_symbols:
                errors.append(
                    f"op #{i}: possible invented Rust module/path: crate::{match.group(1)} "
                    f"(module/root symbol '{first}' is not found in repo or patch_plan)."
                )
                continue

            # If this is a function-like path call, require the called symbol to exist
            # either in the repo or inside the patch_plan.
            tail = patched[match.end(): match.end() + 2]
            if tail.startswith("(") and last not in available_symbols:
                errors.append(
                    f"op #{i}: possible invented Rust function/API: crate::{match.group(1)}() "
                    f"('{last}' is not defined in repo or patch_plan)."
                )

    return errors


def _validate_bare_helper_calls(
    plan: list[dict],
    existing_symbols: set[str],
    patch_symbols: set[str],
) -> list[str]:
    """Catch AI-invented helper calls without flagging every std/library call."""
    errors: list[str] = []
    available_symbols = existing_symbols | patch_symbols | RUST_ALLOWED_BARE_CALLS

    for i, op in enumerate(plan):
        patched = _op_text(op)
        if not patched:
            continue

        for match in re.finditer(r"(?<![\.:])\b([A-Za-z_][A-Za-z0-9_]*)\s*\(", patched):
            name = match.group(1)
            prefix = patched[max(0, match.start() - 20): match.start()]

            # Skip definitions and common language/control constructs.
            if re.search(r"\b(fn|def|function|class|struct|enum|trait|impl)\s+$", prefix):
                continue
            if name in available_symbols:
                continue
            if not name.startswith(INVENTION_PRONE_PREFIXES):
                continue

            errors.append(
                f"op #{i}: possible invented helper call '{name}()'; "
                "define it in patch_plan or use an existing repo symbol."
            )

    return errors


def _validate_domain_leakage_into_data_structures(repo: Path, plan: list[dict]) -> list[str]:
    """Prevent feature code being hidden inside unrelated utility data structures."""
    errors: list[str] = []

    for i, op in enumerate(plan):
        rel = op.get("relative_path") or op.get("file") or ""
        patched = _op_text(op)
        if not rel or not patched or not FEATURE_TERMS.search(patched):
            continue
        if not DATA_STRUCTURE_FILE_RE.search(rel.replace("\\", "/")):
            continue

        before_text = ""
        path = (repo / rel).resolve()
        if path.exists():
            try:
                before_text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                before_text = ""

        if not FEATURE_TERMS.search(before_text):
            if not _is_allowed_app_flow_patch(repo, rel, op):
                errors.append(
                    f"op #{i}: suspicious domain leakage into generic data-structure file '{rel}'. "
                    "Do not use AVL/trie/tree utilities as AML/blacklist storage unless the repo already shows that purpose."
                )
            else:
                continue

    return errors

def _nearest_rust_function_before(text: str, idx: int) -> str:
    matches = list(
        re.finditer(
            r"\bfn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
            text[:idx],
        )
    )
    if not matches:
        return ""
    return matches[-1].group(1)


def _is_allowed_app_flow_patch(repo: Path, relative_path: str, op: dict) -> bool:
    path = relative_path.replace("\\", "/").lower()

    # src/trie.rs trong repo test này không chỉ là data structure;
    # nó cũng chứa Account flow như change_name/save_to_csv.
    if not path.endswith("src/trie.rs"):
        return False

    target = op.get("target_snippet") or ""
    patched = _op_text(op)

    # Fast path: nếu function name xuất hiện trực tiếp trong snippet.
    for name in application_flow_names:
        if name in target or name in patched:
            return True

    # Robust path: target_snippet nằm trong function nào của file gốc?
    file_path = (repo / relative_path).resolve()
    if not file_path.exists() or not target:
        return False

    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    idx = text.find(target)
    if idx < 0:
        return False

    fn_name = _nearest_rust_function_before(text, idx)
    return fn_name in application_flow_names
    
def validate_patch_plan_no_obvious_inventions(repo_path_or_plan, plan_or_repo_text=None) -> list[str]:
    """Heuristic guard for AI-invented APIs inside patch_plan.

    Preferred call shape:
        validate_patch_plan_no_obvious_inventions(repo_path, plan)

    Backward-compatible legacy shape:
        validate_patch_plan_no_obvious_inventions(plan, repo_text)
    """
    if isinstance(repo_path_or_plan, (str, Path)) and isinstance(plan_or_repo_text, list):
        repo = Path(repo_path_or_plan).resolve()
        plan = plan_or_repo_text
        repo_text = _read_repo_source_text(repo)
    elif isinstance(repo_path_or_plan, list) and isinstance(plan_or_repo_text, str):
        # Legacy mode: no repo path, so path/module checks are less precise.
        repo = Path.cwd().resolve()
        plan = repo_path_or_plan
        repo_text = plan_or_repo_text
    else:
        return ["validate_patch_plan_no_obvious_inventions: invalid arguments"]

    patch_text = "\n".join(_op_text(op) for op in plan if isinstance(op, dict))
    existing_symbols = _collect_defined_symbols(repo_text)
    patch_symbols = _collect_defined_symbols(patch_text)
    rust_modules = _collect_rust_modules(repo, repo_text, plan)

    errors: list[str] = []
    errors.extend(_validate_rust_crate_paths(repo, plan, existing_symbols, patch_symbols, rust_modules))
    errors.extend(_validate_bare_helper_calls(plan, existing_symbols, patch_symbols))
    errors.extend(_validate_comment_only_feature_ops(plan))
    errors.extend(_validate_domain_leakage_into_data_structures(repo, plan))
    return errors


def validate_patch_plan_grounding(repo_path: str, plan: list[dict]) -> list[str]:
    repo = Path(repo_path).resolve()
    errors = []

    for i, op in enumerate(plan):
        rel = op.get("relative_path", "")
        path = (repo / rel).resolve()

        try:
            path.relative_to(repo)
        except ValueError:
            errors.append(f"op #{i}: path outside repo: {rel}")
            continue

        if op.get("op") == "replace_snippet":
            if not path.exists():
                errors.append(f"op #{i}: replace target file does not exist: {rel}")
                continue

            text = path.read_text(encoding="utf-8", errors="replace")
            target = op.get("target_snippet", "")

            if target not in text:
                errors.append(f"op #{i}: target_snippet not found in {rel}")

        elif op.get("op") == "create_file":
            if path.exists():
                errors.append(f"op #{i}: create_file target already exists: {rel}")

        else:
            errors.append(f"op #{i}: unknown op: {op.get('op')}")

    if not errors:
        # Only run the semantic/invention guard after basic path/snippet checks pass.
        # This keeps error reports focused and avoids scanning nonsense ops.
        errors.extend(validate_patch_plan_no_obvious_inventions(repo, plan))

    return errors

def classify_validation_output(output: str) -> Dict[str, str]:
    text = (output or "").lower()

    if (
        "no .net sdks were found" in text
        or "download a .net sdk" in text
        or "the application 'test' does not exist" in text
    ):
        return {
            "category": "missing_toolchain",
            "reason": "The validation command requires the .NET SDK, but no .NET SDK is installed or available in PATH.",
            "hint": "Install the .NET SDK, change the validation command, or run without validation for this tiny test repo.",
        }
    if (
        "'go' is not recognized" in text
        or "go: command not found" in text
        or "'npm' is not recognized" in text
        or "npm: command not found" in text
        or "the system cannot find the file specified" in text
        ):
        return {
            "category": "missing_toolchain",
            "reason": "The validation command could not run because the required CLI tool is missing from PATH.",
            "hint": "Restart the terminal/Flask app after installing the tool, or add the tool to PATH.",
        }

    if not text:
        return {
            "category": "unknown",
            "reason": "No validation output.",
            "hint": "Validation command returned no useful output."
        }

    if "fork/exec" in text and (
        "access is denied" in text or "permission denied" in text
    ):
        return {
            "category": "validation_environment",
            "reason": "The validation command could not execute the compiled child process.",
            "hint": "Use repo-local build/cache directories or check OS permissions for temporary executables.",
        }

    # Rust runtime panic — catch before generic test_failure so the hint is specific.
    if "panicked at" in text and ("thread 'main'" in text or "thread '" in text):
        return {
            "category": "test_failure",
            "reason": "Rust runtime validation panicked.",
            "hint": "Read the panic message and fix the behavior checked in main.rs.",
        }
    
    # Go runtime panic has a distinctive format that doesn't always include "panicked at", so catch it with a heuristic.
    if "panic:" in text and "goroutine" in text:
        return {
            "category": "test_failure",
            "reason": "Go runtime validation panicked.",
            "hint": "Read the panic message and fix the behavior checked in main.go.",
        }
    if re.search(r"\bundefined:\s+\w+", text):
        return {
            "category": "build_error",
            "reason": "Go compilation failed due to an undefined symbol.",
            "hint": "Check missing imports, missing functions, or misspelled identifiers.",
        }
    # C / C++ compile and runtime specifics
    if (
        "undefined reference to" in text
        or "ld returned" in text
        or "collect2.exe" in text
        or "cannot find -l" in text
    ):
        return {
            "category": "build_error",
            "reason": "C/C++ linking failed.",
            "hint": "Check missing source files, missing libraries, or unresolved function definitions.",
        }

    if (
        "fatal error:" in text
        and (
            "no such file or directory" in text
            or "file not found" in text
        )
    ):
        return {
            "category": "import_error",
            "reason": "C/C++ include file is missing.",
            "hint": "Check #include paths, header filenames, or build command source files.",
        }

    if re.search(r"error: ['‘]?[a-zA-Z_][a-zA-Z0-9_]*['’]? was not declared in this scope", text):
        return {
            "category": "build_error",
            "reason": "C/C++ compilation failed due to an undeclared identifier.",
            "hint": "Check missing declarations, wrong names, missing includes, or scope issues.",
        }

    if "segmentation fault" in text or "access violation" in text:
        return {
            "category": "runtime_error",
            "reason": "Native program crashed at runtime.",
            "hint": "Check invalid memory access, null pointers, invalid references, or unsafe indexing.",
        }

    # C# / dotnet specifics
    if re.search(r"\berror cs\d+", text):
        return {
            "category": "build_error",
            "reason": "C# compilation failed.",
            "hint": "Check the CS error code, missing using statements, signatures, or type mismatches.",
        }

    if "unhandled exception" in text and "system." in text:
        return {
            "category": "runtime_error",
            "reason": "C# program threw an unhandled exception.",
            "hint": "Check the exception type, stack trace, object state, and method arguments.",
        }

    if "no test is available" in text or "total tests: 0" in text:
        return {
            "category": "test_failure",
            "reason": "C# test runner found no runnable tests.",
            "hint": "Check test project setup, test framework package, or validation command.",
        }

    # JavaScript / TypeScript / Node specifics
    if (
        "syntaxerror:" in text
        or "unexpected token" in text
        or "unexpected end of input" in text
    ):
        return {
            "category": "syntax_error",
            "reason": "JavaScript/TypeScript syntax error.",
            "hint": "Check missing braces, commas, parentheses, or malformed syntax.",
        }

    if (
        "referenceerror:" in text
        or "is not defined" in text
    ):
        return {
            "category": "runtime_error",
            "reason": "JavaScript/TypeScript used an undefined variable or symbol.",
            "hint": "Check missing imports, misspelled identifiers, or variable scope.",
        }

    if (
        "typeerror:" in text
        or "cannot read properties of undefined" in text
        or "cannot read property" in text
        or "is not a function" in text
    ):
        return {
            "category": "runtime_error",
            "reason": "JavaScript/TypeScript runtime type error.",
            "hint": "Check object shape, null/undefined values, function calls, and data flow.",
        }

    if "cannot find module" in text or "err_module_not_found" in text:
        return {
            "category": "import_error",
            "reason": "JavaScript/TypeScript module import failed.",
            "hint": "Check package installation, import path, file extension, or module format.",
        }

    if re.search(r"\berror ts\d+", text):
        return {
            "category": "build_error",
            "reason": "TypeScript compilation failed.",
            "hint": "Check the TS error code, type annotations, imports, or config.",
        }

    # Python specifics
    if (
        "syntaxerror:" in text
        or "indentationerror:" in text
        or "taberror:" in text
    ):
        return {
            "category": "syntax_error",
            "reason": "Python syntax or indentation error.",
            "hint": "Check indentation, missing colons, unmatched brackets, or malformed syntax.",
        }

    if "modulenotfounderror:" in text or "importerror:" in text:
        return {
            "category": "import_error",
            "reason": "Python import failed.",
            "hint": "Check module name, package installation, import path, or virtual environment.",
        }

    if (
        "nameerror:" in text
        or "attributeerror:" in text
        or "typeerror:" in text
        or "keyerror:" in text
        or "indexerror:" in text
        or "valueerror:" in text
    ):
        return {
            "category": "runtime_error",
            "reason": "Python runtime error.",
            "hint": "Check variable names, object attributes, argument types, indexes, keys, or values.",
        }

    if "assertionerror:" in text or re.search(r"\bassert .*failed", text):
        return {
            "category": "assertion_failure",
            "reason": "Python assertion failed.",
            "hint": "Inspect the expected behavior and the logic under test.",
        }
    syntax_patterns = [
        r"SyntaxError",
        r"IndentationError",
        r"unexpected indent",
        r"invalid syntax",
        r"ParseError",
    ]
    import_patterns = [
        r"ImportError",
        r"ModuleNotFoundError",
        r"cannot import name",
        r"No module named",
    ]
    assertion_patterns = [
        r"AssertionError",
        r"assert .* failed",
        r"Expected:.*Actual:",
        r"FAILED .*::.*",
    ]
    type_patterns = [
        r"TypeError",
        r"AttributeError",
        r"NameError",
        r"KeyError",
        r"IndexError",
        r"ValueError",
        r"NullReferenceException",
        r"ReferenceError",
    ]
    test_patterns = [
        r"FAILED",
        r"ERROR at setup",
        r"collected .* item[s]?",
        r"Ran \d+ tests?",
    ]
    build_patterns = [
        r"Build FAILED",
        r"Compilation failed",
        r"error CS\d+",
        r"error: could not compile",
        r"linker command failed",
    ]

    def matches(patterns):
        return any(re.search(p, text, flags=re.IGNORECASE) for p in patterns)

    if matches(syntax_patterns):
        return {
            "category": "syntax_error",
            "reason": "Code has syntax/parsing issues.",
            "hint": "Repair structure, indentation, or malformed syntax before logic changes."
        }

    if matches(import_patterns):
        return {
            "category": "import_error",
            "reason": "Missing or broken import/module dependency.",
            "hint": "Check imports, module names, package availability, or moved symbols."
        }

    if matches(assertion_patterns):
        return {
            "category": "assertion_failure",
            "reason": "Behavior does not match expected test outcome.",
            "hint": "Inspect test expectation and business logic, not just syntax."
        }

    if matches(build_patterns):
        return {
            "category": "build_error",
            "reason": "Compilation/build step failed.",
            "hint": "Check compile errors, signatures, missing symbols, and type mismatches."
        }

    if matches(type_patterns):
        return {
            "category": "runtime_error",
            "reason": "Execution failed due to runtime/type-related issue.",
            "hint": "Check object state, null/None access, arguments, and data shape."
        }

    if matches(test_patterns):
        return {
            "category": "test_failure",
            "reason": "Tests failed but root cause is not yet classified.",
            "hint": "Inspect failing test names and stack trace for the first real error."
        }

    return {
        "category": "unknown",
        "reason": "Could not classify validation output confidently.",
        "hint": "Fallback to manual inspection of the first error block."
    }

def run_tests():
    try:
        result = subprocess.run(
            ["pytest"],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
    except Exception:
        return False

def basic_check(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        compile(content, file_path, 'exec')
        return True
    except Exception:
        return False
