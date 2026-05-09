from __future__ import annotations

import json
import re


def _find_balanced_json_objects(text: str) -> list[str]:
    results: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        if text[i] != "{":
            i += 1
            continue
        depth = 0
        in_string = False
        escape = False
        start = i
        while i < n:
            ch = text[i]
            if in_string:
                if escape:
                    escape = False
                elif ch == "\\":
                    escape = True
                elif ch == '"':
                    in_string = False
            else:
                if ch == '"':
                    in_string = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        results.append(text[start:i + 1])
                        i += 1
                        break
            i += 1
        else:
            break
    return results


def extract_json_block(text: str) -> dict | None:
    if not text:
        return None

    fenced = re.findall(r"```json\s*(.*?)\s*```", text, re.DOTALL)
    for block in fenced:
        for candidate in _find_balanced_json_objects(block):
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                continue

    for candidate in _find_balanced_json_objects(text):
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            continue
    return None
