import re
from pathlib import Path
from typing import Optional


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


def extract_symbol_snippet_from_text(text: str, language: str, symbol_name: str) -> Optional[str]:
    name = symbol_name.split("::")[-1]

    if language == "go":
        pattern = rf"\bfunc\s+{re.escape(name)}\s*\("
    elif language == "rust":
        pattern = rf"\b(?:pub\s+)?fn\s+{re.escape(name)}\s*\("
    elif language == "python":
        pattern = rf"(?m)^def\s+{re.escape(name)}\s*\("
    else:
        return None

    match = re.search(pattern, text)
    if not match:
        return None

    if language in {"go", "rust"}:
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


def hydrate_control_source_from_scout(control_result: dict, repo_path: str, language: str) -> dict:
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

    for rel_path, symbol in candidates:
        path = Path(repo_path) / rel_path
        if not path.exists() or not path.is_file():
            continue

        text = path.read_text(encoding="utf-8", errors="replace")

        snippet = None
        if symbol:
            snippet = extract_symbol_snippet_from_text(text, language, symbol)

        if not snippet and len(text) < 12000:
            snippet = text.strip()

        if snippet:
            patch_intent["target_file"] = rel_path
            patch_intent["source_snippet"] = snippet

            top = control_result.setdefault("top_hypothesis", {})
            if symbol:
                top["symbol"] = symbol
            else:
                top["symbol"] = rel_path
            top["confidence"] = max(float(top.get("confidence") or 0.0), 0.55)
            top["recommended_action"] = "patch"

            return control_result

    return control_result