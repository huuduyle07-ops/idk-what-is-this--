from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
from typing import Dict, List, Any


from core.treesitter_parse import parse_code_with_treesitter

def _find_matches(pattern: str, text: str) -> List[str]:
    return list(dict.fromkeys(re.findall(pattern, text, flags=re.MULTILINE)))


def _line_count(text: str) -> int:
    if not text.strip():
        return 0
    return len(text.splitlines())


def _safe_preview(text: str, max_lines: int = 12) -> str:
    lines = text.splitlines()
    if len(lines) <= max_lines:
        return text
    return "\n".join(lines[:max_lines])


def _build_framework_hints(code: str, language: str, imports: List[str]) -> List[str]:
    text = code.lower()
    hints: List[str] = []

    if language == "csharp":
        if "monobehaviour" in text or "using unityengine" in text:
            hints.append("unity")
        if any(x in code for x in ["Update()", "Start()", "Awake()", "FixedUpdate()"]):
            hints.append("unity_lifecycle")

    if language == "rust":
        if "Commands" in code and "Query" in code:
            hints.append("bevy_ecs")
        if "Res<" in code or "ResMut<" in code:
            hints.append("bevy_resources")
        if "Component" in code:
            hints.append("ecs_component")

    if language in {"typescript", "javascript", "typescript/javascript"}:
        if "useState" in code or "useEffect" in code:
            hints.append("react")
        if "export default" in code:
            hints.append("default_export")

    if language == "python":
        if "pytest" in text or any("pytest" in imp.lower() for imp in imports):
            hints.append("pytest")
        if "unittest" in text or any("unittest" in imp.lower() for imp in imports):
            hints.append("unittest")
        if "if __name__ == '__main__':" in code or 'if __name__ == "__main__":' in code:
            hints.append("cli_entry")

    if language == "html":
        hints.append("markup")

    if language == "css":
        hints.append("stylesheet")

    return hints


def _build_entry_hints(code: str, language: str, functions: List[Dict[str, Any]]) -> List[str]:
    hints: List[str] = []
    text = code.lower()

    if language == "python":
        if "if __name__ == '__main__':" in code or 'if __name__ == "__main__":' in code:
            hints.append("__main__ block")
        if any(f["name"] == "main" for f in functions):
            hints.append("main() function")

    if language == "csharp":
        lifecycle = {"Start", "Update", "Awake", "FixedUpdate"}
        found = [f["name"] for f in functions if f["name"] in lifecycle]
        if found:
            hints.append("unity lifecycle: " + ", ".join(found))

    if language == "rust":
        if any(f["name"] == "main" for f in functions):
            hints.append("main() function")
        if "App::new" in code or ".add_systems" in code or ".add_plugins" in code:
            hints.append("app builder / engine entry flow")

    if language in {"typescript", "javascript", "typescript/javascript"}:
        if "export default" in code:
            hints.append("default export")
        if "createRoot(" in code or "ReactDOM.render" in code:
            hints.append("frontend entry render")

    return hints


def _normalize_ts_nodes(data: dict, language: str) -> Dict[str, Any]:
    functions: List[Dict[str, Any]] = []
    classes: List[Dict[str, Any]] = []
    symbols: List[Dict[str, Any]] = []

    nodes = data.get("symbols", [])
    imports = data.get("imports", [])
    calls = data.get("calls", [])

    for node in nodes:
        kind = node.get("kind", "unknown")
        name = node.get("name", "unknown")
        content = node.get("content", "")

        symbol = {
            "kind": kind,
            "name": name,
            "line_count": _line_count(content),
            "preview": _safe_preview(content),
        }
        symbols.append(symbol)

        if kind == "function":
            functions.append({
                "name": name,
                "content": content,
                "line_count": _line_count(content),
                "preview": _safe_preview(content),
            })
        elif kind in ["class", "struct", "enum", "trait", "interface"]:
            classes.append({
                "name": name,
                "content": content,
                "line_count": _line_count(content),
                "preview": _safe_preview(content),
            })

    framework_hints = _build_framework_hints(
        code="\n\n".join(node.get("content", "") for node in nodes),
        language=language,
        imports=imports,
    )

    return {
        "language": language,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "symbols": symbols,
        "calls": calls,
        "framework_hints": framework_hints,
        "entry_hints": _build_entry_hints(
            code="\n\n".join(node.get("content", "") for node in nodes),
            language=language,
            functions=functions,
        ),
        "notes": [],
        "raw": data,
    }


def analyze_code_structure(code: str, language: str = "unknown") -> dict:
    language = (language or "unknown").lower()

    # 1. Primary path: direct Tree-sitter import
    try:
        data = parse_code_with_treesitter(code, language)
        if data and data.get("symbols"):
            return _normalize_ts_nodes(data, language)
    except Exception as e:
        # If import or execution fails, fall back to regex
        pass

    # 2. Minimal fallback regex analysis
    return _fallback_regex_analysis(code, language)


def _fallback_regex_analysis(code: str, language: str) -> Dict[str, Any]:
    # Simplified fallback that works for most languages
    function_patterns = [
        r"def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"fn\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(",
        r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\([^;]*\)\s*\{",
    ]
    class_patterns = [
        r"class\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"struct\s+([A-Za-z_][A-Za-z0-9_]*)",
        r"interface\s+([A-Za-z_][A-Za-z0-9_]*)",
    ]
    
    found_functions = []
    for p in function_patterns:
        found_functions.extend(_find_matches(p, code))
    
    found_classes = []
    for p in class_patterns:
        found_classes.extend(_find_matches(p, code))

    functions = [{"name": n, "content": "", "line_count": 0, "preview": ""} for n in dict.fromkeys(found_functions)]
    classes = [{"name": n, "content": "", "line_count": 0, "preview": ""} for n in dict.fromkeys(found_classes)]

    return {
        "language": language,
        "functions": functions,
        "classes": classes,
        "imports": [],
        "symbols": [{"kind": "unknown", "name": f["name"], "line_count": 0, "preview": ""} for f in functions],
        "framework_hints": [],
        "entry_hints": [],
        "notes": ["Using minimal regex fallback."],
    }