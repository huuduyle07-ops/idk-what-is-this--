import re
from pathlib import Path
from typing import Optional

from core.control_engine import refresh_control_safety


def _find_matching_brace(text: str, open_idx: int) -> Optional[int]:
    depth = 0
    for i in range(open_idx, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    return None

def _candidate_names_from_scout(scout: dict, query: str = "") -> list[str]:
    raw = []

    for symbol in scout.get("likely_symbols") or []:
        raw.append(symbol.split("::")[-1])

    raw.extend(scout.get("target_concepts") or [])

    reason = scout.get("reason") or ""
    raw.append(reason)
    raw.append(query)

    names = []
    seen = set()

    for chunk in raw:
        for token in re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", str(chunk)):
            low = token.lower()
            if low in {
                "the", "and", "or", "to", "from", "within", "logic",
                "validation", "state", "updates", "function", "file",
                "cart", "inventory", "stock", "quantity",
            }:
                continue
            if low not in seen:
                seen.add(low)
                names.append(token)

    return names

def extract_symbol_snippet_from_text(text: str, language: str, symbol_name: str) -> Optional[str]:
    name = symbol_name.split("::")[-1]

    if language == "go":
        pattern = rf"\bfunc\s+{re.escape(name)}\s*\("
    elif language == "rust":
        pattern = rf"\b(?:pub\s+)?fn\s+{re.escape(name)}\s*\("
    elif language == "python":
        pattern = rf"(?m)^def\s+{re.escape(name)}\s*\("
    elif language in {"javascript", "js", "typescript", "ts"}:
        pattern = rf"\b(?:export\s+)?function\s+{re.escape(name)}\s*\("
    elif language in {"cpp", "c++", "c"}:
        pattern = rf"\b[A-Za-z_][\w:<>,\s*&]*\s+{re.escape(name)}\s*\("
    else:
        return None

    match = re.search(pattern, text)
    if not match:
        return None

    if language in {"go", "rust", "javascript", "js", "typescript", "ts", "cpp", "c++", "c"}:
        open_idx = text.find("{", match.start())
        if open_idx == -1:
            return None
        end_idx = _find_matching_brace(text, open_idx)
        if end_idx is None:
            return None
        return text[match.start():end_idx].strip()

    if language == "python":
        lines = text[match.start():].splitlines()
        if not lines:
            return None
        out = [lines[0]]
        for line in lines[1:]:
            if line and not line.startswith((" ", "\t")):
                break
            out.append(line)
        return "\n".join(out).strip()

    return None


def hydrate_control_source_from_scout(
    control_result: dict,
    repo_path: str,
    language: str,
    query: str = "",
) -> dict:
    if not isinstance(control_result, dict):
        return control_result

    patch_intent = control_result.get("patch_intent")
    if not isinstance(patch_intent, dict):
        patch_intent = {}
        control_result["patch_intent"] = patch_intent

    if patch_intent.get("source_snippet"):
        return control_result

    scout = control_result.get("scout")
    if not isinstance(scout, dict):
        return control_result

    top = control_result.get("top_hypothesis")
    if not isinstance(top, dict):
        top = {}
        control_result["top_hypothesis"] = top

    patch_intent = control_result.setdefault("patch_intent", {})
    if patch_intent.get("source_snippet"):
        return control_result

    scout = control_result.get("scout") or {}
    likely_symbols = scout.get("likely_symbols") or []
    likely_files = scout.get("likely_files") or []

    candidates = []

    for symbol in likely_symbols:
        if "::" in symbol:
            rel_path, _ = symbol.split("::", 1)
            candidates.append((rel_path, symbol))

    for rel_path in likely_files:
        candidates.append((rel_path, ""))

    candidate_names = _candidate_names_from_scout(scout, query=query)

    for rel_path, symbol in candidates:
        path = Path(repo_path) / rel_path
        if not path.exists() or not path.is_file():
            continue

        text = path.read_text(encoding="utf-8", errors="replace")

        snippet = None

        if symbol:
            snippet = extract_symbol_snippet_from_text(text, language, symbol)

        if not snippet:
            for name in candidate_names:
                snippet = extract_symbol_snippet_from_text(text, language, name)
                if snippet:
                    symbol = f"{rel_path}::{name}"
                    break

        # Last resort: only use full file if it is small.
        if not snippet and len(text) < 12000:
            snippet = text.strip()
            symbol = rel_path

        if snippet:
            patch_intent["target_file"] = rel_path
            patch_intent["symbol"] = symbol or rel_path
            patch_intent["source_snippet"] = snippet

            top["symbol"] = symbol or rel_path
            # Exact source acquisition improves context, not defect evidence or
            # patch authority.  CONTROL's safety projection keeps the candidate
            # localization-only unless executed failure evidence binds to it.
            return refresh_control_safety(control_result)

    return control_result
