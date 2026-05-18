from __future__ import annotations
from typing import Any, Dict, Optional


def build_patch_intent(issue: Any, symbol: dict, file_path: str) -> Optional[Dict[str, Any]]:
    content = symbol.get("content", "")
    name = symbol.get("name", "unknown")

    issue_text = str(issue)

    if "overwritten before being used" in issue_text:
        return {
            "file": file_path,
            "target_node_name": name,
            "target_node_kind": symbol.get("kind", "function"),
            "issue": issue_text,
            "fix_strategy": "Remove or reorder the overwritten assignment so the previous value is used before being replaced.",
            "source_snippet": content,
        }

    if isinstance(issue, dict) and issue.get("type") == "return_conflict":
        return {
            "file": file_path,
            "target_node_name": name,
            "target_node_kind": symbol.get("kind", "function"),
            "issue": issue.get("reason"),
            "fix_strategy": "Normalize return behavior across branches or make branch-specific return logic explicit.",
            "source_snippet": content,
            "paths": issue.get("paths", []),
        }

    if "Branch condition is trivially" in issue_text:
        return {
            "file": file_path,
            "target_node_name": name,
            "target_node_kind": symbol.get("kind", "function"),
            "issue": issue_text,
            "fix_strategy": "Remove the useless branch or replace the condition with meaningful runtime logic.",
            "source_snippet": content,
        }

    return None