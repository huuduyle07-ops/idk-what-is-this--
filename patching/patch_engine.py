from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple, Dict, Any, List
import shutil
import re

from core.security import is_safe_path
from core.treesitter_parse import parse_code_with_treesitter


def _is_inside(child: Path, parent: Path) -> bool:
    """True iff `child` is the same as or nested below `parent` (after resolve)."""
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False


def find_target_file(project_root: str, file_name: str) -> Optional[Path]:
    """Locate a target file inside project_root.

    Hard rules:
      - Reject absolute or traversal-y file_name early.
      - Resolved candidate MUST live inside project_root.
      - rglob fallback only succeeds if there is exactly ONE match — otherwise
        we refuse to guess (safer than patching the wrong file).
    """
    root = Path(project_root).resolve()

    if not file_name:
        return None

    # 1. Reject absolute paths and traversal escapes up front.
    raw = Path(file_name)
    if raw.is_absolute():
        print(f"🛑 Refusing absolute file_name: {file_name}")
        return None

    # 2. Direct join. After resolve(), candidate MUST still be inside root.
    try:
        candidate = (root / file_name).resolve()
        if _is_inside(candidate, root) and candidate.is_file():
            return candidate
    except Exception:
        pass

    # 3. rglob fallback — only when there is exactly ONE match.
    matches = [p for p in root.rglob(raw.name) if p.is_file() and _is_inside(p, root)]
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        names = [str(m.relative_to(root)) for m in matches[:5]]
        print(
            f"⚠️ Ambiguous file name '{file_name}': found {len(matches)} matches: {names}. "
            "Refusing to guess — pass an unambiguous relative_path."
        )
        return None
    return None


def backup_file(file_path: Path) -> Path:
    backup_path = file_path.with_suffix(file_path.suffix + ".bak")
    shutil.copy2(file_path, backup_path)
    return backup_path


def restore_backup(file_path: Path, backup_path: Path) -> None:
    shutil.copy2(backup_path, file_path)


def cleanup_backup(backup_path: Path) -> None:
    if backup_path.exists():
        backup_path.unlink()


def _indent_of(line: str) -> str:
    m = re.match(r"^(\s*)", line)
    return m.group(1) if m else ""


def _normalize_nonempty_lines(text: str) -> List[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _first_nonempty_line(text: str) -> str:
    for line in text.splitlines():
        if line.strip():
            return line
    return ""

def _normalize_code(text: str) -> str:
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def _looks_like_whole_node(snippet: str, name: str, kind: str, language: str) -> bool:
    first = _first_nonempty_line(snippet).strip()

    if kind == "function":
        if language == "python":
            return bool(re.match(rf"def\s+{re.escape(name)}\s*\(", first))
        if language in {"csharp", "cpp", "javascript", "typescript"}:
            return bool(re.search(rf"\b{re.escape(name)}\s*\(", first)) and "{" in snippet
        if language == "rust":
            # Rust function header may carry pub / pub(crate) / async / unsafe / extern modifiers.
            return bool(re.search(rf"\bfn\s+{re.escape(name)}\s*[<(]", first)) and "{" in snippet

    if kind == "class":
        return bool(re.search(rf"\bclass\s+{re.escape(name)}\b", first))

    return False

def _apply_indent_to_snippet(snippet: str, base_indent: str) -> str:
    """
    Only apply base_indent if the snippet seems to be unindented.
    If the first line already has indentation, trust the LLM's structure.
    """
    lines = snippet.splitlines()
    if not lines:
        return snippet
        
    first_line = ""
    for l in lines:
        if l.strip():
            first_line = l
            break
            
    if not first_line or first_line[0] in (" ", "\t"):
        # Already indented or empty, don't force base_indent on every line
        return snippet

    result = []
    for line in lines:
        if not line.strip():
            result.append(line)
        else:
            result.append(base_indent + line)
    return "\n".join(result)


def _score_fuzzy_candidate(
    original_lines: List[str],
    start_idx: int,
    target_lines_stripped: List[str],
) -> Tuple[int, int]:
    """
    Attempts to match target_lines_stripped against original_lines starting at start_idx.
    Skips empty lines in original_lines if they don't match.
    Returns (score, consumed_line_count).
    """
    curr_orig = start_idx
    is_first_target = True

    for target_line in target_lines_stripped:
        while curr_orig < len(original_lines):
            line = original_lines[curr_orig].strip()
            matched = (line == target_line)
            # Rescue path for the FIRST target line: accept it when it appears
            # as a token-boundary suffix of the original line. This handles
            # the case where the LLM dropped a leading modifier from
            # target_snippet (e.g. emitted `function foo(...)` against a file
            # that has `async function foo(...)`). patched_snippet carries the
            # correct header — the AI wrote what the function *should* look
            # like — so replacing the matched range with patched_snippet
            # stays semantically correct. We require a whitespace separator
            # between the dropped prefix and the target content to avoid
            # mid-token matches like `Foo` matching inside `MyFoo`.
            if (
                not matched
                and is_first_target
                and target_line
                and line.endswith(target_line)
            ):
                remainder = line[: -len(target_line)]
                if remainder.endswith((" ", "\t")) and remainder.strip():
                    matched = True
            if matched:
                curr_orig += 1
                is_first_target = False
                break
            elif not line:
                curr_orig += 1
                continue
            else:
                return -10**9, 0
        else:
            return -10**9, 0

    total_consumed = curr_orig - start_idx
    score = 100
    # Penalty for skipping too many lines
    score -= (total_consumed - len(target_lines_stripped)) * 2

    return score, total_consumed

def apply_patch_from_json(project_root: str, patch: dict) -> Dict[str, Any]:
    """
    Returns:
    {
        "success": bool,
        "target_file": Path | None,
        "old_snippet": str | None,
        "new_snippet": str | None,
        "backup_path": Path | None,
        "matched_by": "ast" | "fuzzy" | "literal" | None,
        "target_node_name": str | None,
        "target_node_kind": str | None,
    }
    """
    file_name = patch.get("file")
    relative_path = patch.get("relative_path")
    target_snippet = patch.get("target_snippet")
    patched_snippet = patch.get("patched_snippet")
    target_node_name = patch.get("target_node_name")
    target_node_kind = patch.get("target_node_kind", "function")
    language = patch.get("language", "python")

    result = {
        "success": False,
        "target_file": None,
        "old_snippet": None,
        "new_snippet": None,
        "backup_path": None,
        "matched_by": None,
        "target_node_name": target_node_name,
        "target_node_kind": target_node_kind,
    }

    if not target_snippet or not patched_snippet:
        return result

    root = Path(project_root).resolve()
    target_file = None

    if relative_path and relative_path != "<relative path if known>":
        candidate = (root / relative_path).resolve()
        if _is_inside(candidate, root) and candidate.exists() and candidate.is_file():
            target_file = candidate

    if not target_file and file_name:
        target_file = find_target_file(project_root, file_name)

    if not target_file or not target_file.is_file():
        return result

    # Security gate: ensure resolved path stays inside project root
    if not is_safe_path(str(target_file), allowed_roots=[str(root)]):
        print(f"🛑 Security: patch target '{target_file}' is outside project or blacklisted.")
        return result

    # Read raw bytes once and decode WITHOUT universal-newline translation.
    # `Path.read_text()` collapses CRLF→LF, but `read_bytes()` keeps CRLF —
    # so feeding tree-sitter the LF text while slicing the CRLF bytes
    # offsets every newline by one byte and lands the AST splice mid-line.
    # Decoding the raw bytes ourselves keeps both views consistent.
    code_bytes = target_file.read_bytes()
    original_text = code_bytes.decode("utf-8", "replace")
    newline = "\r\n" if "\r\n" in original_text else "\n"

    # =========================
    # 0. EXACT LITERAL REPLACE
    # =========================
    # If the LLM provided an exact target_snippet, trust that first.
    # This is safer than AST slicing for simple edits because tree-sitter
    # offsets can become fragile across encodings/newlines/parser quirks.
    #
    # Guard against mid-line substring matches: `target_snippet` of
    # "function checkout(...)" finds a substring inside
    # "async function checkout(...)" and a blind .replace() would yield
    # "async async function checkout(...)" (a real failure mode for the
    # js_async_missing_await benchmark when the LLM drops a leading
    # modifier). Require the match to be line-aligned — i.e. the chars
    # between the line start and the match must be whitespace only.
    # Indented method definitions still qualify because the prefix is
    # entirely whitespace.
    idx = original_text.find(target_snippet)
    if idx != -1:
        line_start = original_text.rfind("\n", 0, idx) + 1
        prefix = original_text[line_start:idx]
        if not prefix.strip():
            backup_path = backup_file(target_file)
            new_text = original_text.replace(target_snippet, patched_snippet, 1)

            with target_file.open("w", encoding="utf-8", newline=newline) as f:
                f.write(new_text)

            result.update({
                "success": True,
                "target_file": target_file,
                "old_snippet": target_snippet,
                "new_snippet": patched_snippet,
                "backup_path": backup_path,
                "matched_by": "literal",
            })
            return result

    # =========================
    # 1. AST PATCH
    # =========================
    if target_node_name:
        try:
            data = parse_code_with_treesitter(original_text, language)
            if isinstance(data, list):
                nodes = data
            else:
                nodes = data.get("symbols", [])
        except Exception:
            nodes = []

        ast_candidates = [
            node for node in nodes
            if node.get("name") == target_node_name
            and node.get("kind") == target_node_kind
        ]

        if ast_candidates:
            node = ast_candidates[0]

            code_bytes = target_file.read_bytes()
            node_content = code_bytes[node["start"]:node["end"]].decode("utf-8", "replace")

            node_content_norm = _normalize_code(node_content)
            target_norm = _normalize_code(target_snippet)
            patched_is_whole_node = _looks_like_whole_node(
                patched_snippet,
                target_node_name,
                target_node_kind,
                language,
            )

            # If target_snippet is only a statement, do NOT replace the whole AST node.
            # Fall through to fuzzy/literal matching instead.
            if target_norm == node_content_norm or patched_is_whole_node:
                backup_path = backup_file(target_file)

                orig_indent = _indent_of(_first_nonempty_line(node_content))
                final_patched = _apply_indent_to_snippet(patched_snippet, orig_indent)

                new_bytes = (
                    code_bytes[:node["start"]]
                    + final_patched.encode("utf-8")
                    + code_bytes[node["end"]:]
                )
                target_file.write_bytes(new_bytes)

                result.update({
                    "success": True,
                    "target_file": target_file,
                    "old_snippet": node_content,
                    "new_snippet": final_patched,
                    "backup_path": backup_path,
                    "matched_by": "ast",
                })
                return result

            print(
                "⚠️ AST match found, but patch is statement-level. "
                "Falling back to fuzzy/literal matching."
            )
        
    # =========================
    # 2. FUZZY MATCH
    # =========================
    target_lines_raw = target_snippet.splitlines()
    target_lines_stripped = _normalize_nonempty_lines(target_snippet)
    if not target_lines_stripped:
        return result

    original_lines = original_text.splitlines()
    candidates: List[Tuple[int, int, int]] = [] # score, match_start, consumed_count

    for i in range(len(original_lines)):
        score, consumed = _score_fuzzy_candidate(
            original_lines=original_lines,
            start_idx=i,
            target_lines_stripped=target_lines_stripped,
        )
        if score > -10**8:
            candidates.append((score, i, consumed))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        _, match_start, consumed_count = candidates[0]

        backup_path = backup_file(target_file)

        first_orig_line = original_lines[match_start] if match_start < len(original_lines) else ""
        original_indent = _indent_of(first_orig_line)
        final_snippet = _apply_indent_to_snippet(patched_snippet, original_indent)

        final_snippet_lines = final_snippet.splitlines()

        result_lines = (
            original_lines[:match_start]
            + final_snippet_lines
            + original_lines[match_start + consumed_count:]
        )

        with target_file.open("w", encoding="utf-8", newline=newline) as f:
            f.write(newline.join(result_lines))
            if original_text.endswith(("\n", "\r")):
                f.write(newline)

        result.update({
            "success": True,
            "target_file": target_file,
            "old_snippet": target_snippet,
            "new_snippet": final_snippet,
            "backup_path": backup_path,
            "matched_by": "fuzzy",
        })
        return result

    return result