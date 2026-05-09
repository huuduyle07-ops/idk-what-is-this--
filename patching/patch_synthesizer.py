from __future__ import annotations
from typing import Dict, Any, List


def _base_patch(intent: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "file": intent.get("file"),
        "relative_path": intent.get("relative_path"),
        "target_node_name": intent.get("target_node_name"),
        "target_node_kind": intent.get("target_node_kind", "function"),
        "target_snippet": intent.get("source_snippet", ""),
        "issue": intent.get("issue", ""),
    }

def score_patch(patch):
    score = 0
    strategy = patch.get("strategy", "")
    if strategy == "remove_last_assignment":
        score += 3
    elif strategy == "swap_assignments":
        patched = patch.get("patched_snippet", "")
        lines = [l.strip() for l in patched.splitlines() if l.strip()]

        bad_return_order = any(
            lines[i].startswith("return") and "=" in lines[i + 1]
            for i in range(len(lines) - 1)
        )

        if bad_return_order:
            score -= 2
        else:
            score += 2
    elif strategy == "normalize_return_behavior":
        score += 2
    # Penalize TODO (low confidence)
    if "TODO" in patch.get("patched_snippet", ""):
        score -= 1

    # shorter patch = safer
    score -= len(patch.get("patched_snippet", "")) * 0.001

    return score

def _is_safe_swap(lines):
    if len(lines) < 2:
        return False

    l1 = lines[-2].strip()
    l2 = lines[-1].strip()

    # không swap nếu có return
    if "return" in l1 or "return" in l2:
        return False

    # không swap nếu phụ thuộc biến
    if "=" in l1 and "=" in l2:
        var1 = l1.split("=")[0].strip()
        var2 = l2.split("=")[0].strip()

        if var1 in l2 or var2 in l1:
            return False

    return True

def build_patch_candidate(intent: Dict[str, Any]) -> Dict[str, Any]:
    candidates = build_patch_candidates(intent)
    candidates.sort(key=score_patch, reverse=True)
    if candidates:
        return candidates[0]

    base = _base_patch(intent)
    base["patched_snippet"] = base["target_snippet"]
    return base

def _remove_last_assignment_line(lines: list[str]) -> list[str]:
    for i in range(len(lines) - 1, -1, -1):
        stripped = lines[i].strip()
        if "=" in stripped and not stripped.startswith(("if ", "while ", "for ")):
            return lines[:i] + lines[i+1:]
    return lines

def build_patch_candidates(intent: Dict[str, Any]) -> List[Dict[str, Any]]:
    snippet = intent.get("source_snippet", "")
    issue = str(intent.get("issue", "")).lower()

    if not snippet.strip():
        return []

    candidates = []
    

    if "overwritten" in issue:
        # Strategy 1: remove last overwrite
        lines = snippet.splitlines()
        if len(lines) >= 2:
            patch1 = _base_patch(intent)
            patch1.update({
                "strategy": "remove_last_assignment",
                "patched_snippet": "\n".join(_remove_last_assignment_line(lines)),
            })
            candidates.append(patch1)

        # Strategy 2: swap assignment order
        if len(lines) >= 2 and _is_safe_swap(lines):
            swapped = lines[:-2] + [lines[-1], lines[-2]]
            patch2 = _base_patch(intent)
            patch2.update({
                "strategy": "swap_assignments",
                "patched_snippet": "\n".join(swapped),
            })
            candidates.append(patch2)

        # Strategy 3: mark overwrite for LLM refinement
        fixed = lines[:]
        if fixed:
            fixed[-1] = "# TODO: review overwrite before applying\n" + fixed[-1]

        patch3 = _base_patch(intent)
        patch3.update({
            "strategy": "mark_overwrite",
            "patched_snippet": "\n".join(fixed),
        })
        candidates.append(patch3)

    if "return value differs" in issue or "return_conflict" in issue:
        patch4 = _base_patch(intent)
        patch4.update({
            "strategy": "normalize_return_behavior",
            "patched_snippet": snippet,
            "note": "Needs LLM refinement: return behavior differs across branches.",
        })
        candidates.append(patch4)
        patch5 = _base_patch(intent)
        patch5.update({
            "strategy": "force_single_return",
            "patched_snippet": snippet + "\n# TODO: unify return value",
        })   
        candidates.append(patch5)

    if "trivially" in issue or "branch condition" in issue:
        patch6 = _base_patch(intent)
        patch6.update({
            "strategy": "remove_or_simplify_useless_branch",
            "patched_snippet": snippet,
            "note": "Needs LLM refinement: branch may be useless.",
        })
        candidates.append(patch6)

    return candidates