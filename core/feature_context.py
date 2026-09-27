from __future__ import annotations

import json
import re
from core.prompter import SCOUT_PROMPT
from core.json_utils import extract_json_block
from pathlib import Path

from core.control_engine import localization_value

def extract_scout_snippets(repo_path: str, scout: dict) -> list[dict]:
    repo = Path(repo_path).resolve()
    snippets = []

    likely_files = scout.get("likely_files") or []

    for rel in likely_files[:6]:
        if not isinstance(rel, str):
            continue

        path = (repo / rel).resolve()

        try:
            path.relative_to(repo)
        except ValueError:
            continue

        if not path.exists() or not path.is_file():
            continue

        text = path.read_text(encoding="utf-8", errors="replace")

        snippets.append({
            "role": "scout_file",
            "source": "scout",
            "file": rel,
            "symbol": "",
            "snippet": text[:5000],
        })

    return snippets

def build_fallback_scout(query: str, control_result: dict) -> dict:
    top = control_result.get("top_hypothesis") or {}
    symbol = top.get("symbol") or ""

    likely_files: list[str] = []
    likely_symbols: list[str] = []

    if "::" in symbol:
        likely_files.append(symbol.split("::", 1)[0])
        likely_symbols.append(symbol)

    top_file = top.get("file")
    if top_file and top_file not in likely_files:
        likely_files.append(top_file)

    for s in control_result.get("related_snippets", []) or []:
        f = s.get("file")
        if f and f not in likely_files:
            likely_files.append(f)

    return {
        "request_type": "unknown",
        "target_concepts": [],
        "likely_files": likely_files,
        "likely_symbols": likely_symbols,
        "reason": "Fallback Scout generated from CONTROL and related snippets because Scout JSON parsing failed.",
    }


def merge_related_snippets(old: list[dict], new: list[dict], limit: int = 8) -> list[dict]:
    merged = []
    seen = set()

    for item in list(old or []) + list(new or []):
        key = (
            item.get("file", ""),
            item.get("symbol", ""),
            item.get("role", ""),
        )

        if key in seen:
            continue

        seen.add(key)
        merged.append(item)

        if len(merged) >= limit:
            break

    return merged

def build_file_inventory(
    repo_path: str,
    *,
    inventory=None,
) -> list[dict]:
    from core.repository_inventory import (
        create_repository_inventory,
        validate_repository_inventory,
    )

    operation_inventory = (
        validate_repository_inventory(repo_path, inventory)
        if inventory is not None
        else create_repository_inventory(repo_path)
    )
    return [
        {"path": entry.relative_path.as_posix()}
        for entry in operation_inventory.indexable_entries[:200]
    ]


def build_symbol_list_from_control_or_graph(repo_path: str) -> list[dict]:
    # MVP: chưa dùng graph → chỉ trả empty
    return []

def query_words(query: str) -> set[str]:
    return {
        w.lower()
        for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", query)
        if len(w) >= 3
    }


def should_call_scout(query: str, control_result: dict) -> bool:
    q = query.lower()
    top = control_result.get("top_hypothesis") or {}
    # Navigation-only trigger: this value decides whether to acquire more
    # context.  It is not defect confidence and grants no patch authority.
    localization = localization_value(top)
    related = control_result.get("related_snippets") or []

    feature_words = [
        "add", "create", "new module", "feature", "pipeline",
        "integrate", "support", "screening", "aml", "fraud",
        "risk", "refactor",
        # Vietnamese
        "thêm", "tạo", "tích hợp", "hỗ trợ", "chống rửa tiền",
        "rủi ro", "gian lận", "sàng lọc", "kiểm tra"
    ]

    is_feature = any(w in q for w in feature_words)

    if is_feature and localization < 0.65:
        return True

    if is_feature and len(related) < 2:
        return True
    
    if is_feature and not top.get("file"):
        return True

    symbol = (top.get("symbol") or "").lower()
    if is_feature and any(noise in symbol for noise in ["get_height", "rotate", "balance"]):
        return True

    return False


def build_scout_prompt(query: str, symbol_list: list[dict], file_inventory: list[dict]) -> str:
    return SCOUT_PROMPT.format(
        query=query,
        symbols=json.dumps(symbol_list[:80], indent=2, ensure_ascii=False),
        files=json.dumps(file_inventory[:80], indent=2, ensure_ascii=False),
    )

def maybe_enrich_with_scout(
    query: str,
    repo_path: str,
    control_result: dict | None,
    force: bool = False,
    *,
    inventory=None,
) -> dict | None:
    """Enrich control_result with Scout's file/symbol picks.

    By default, only fires when `should_call_scout` returns True (heuristic
    aimed at feature-extension queries). Pass `force=True` to bypass the
    heuristic — useful for autonomous flows like the overnight dream where
    we want maximum context regardless of query phrasing.
    """
    from agents.gemini_client import run_gemini_request_2
    print("🧭 SCOUT: checking trigger...")
    if not control_result:
        return control_result

    if not force and not should_call_scout(query, control_result):
        print("🧭 SCOUT: skipped")
        return control_result

    if force:
        print("🧭 SCOUT: forced (dream/autonomous mode)")
    print("🧭 SCOUT: retrieving code...")

    symbol_list = build_symbol_list_from_control_or_graph(repo_path)
    file_inventory = build_file_inventory(
        repo_path,
        inventory=inventory,
    )

    prompt = build_scout_prompt(
        query=query,
        symbol_list=symbol_list,
        file_inventory=file_inventory,
    )

    raw = run_gemini_request_2(
        prompt=prompt,
        repo_path=repo_path,
    )
    print("🧭 SCOUT: parsing...")
    scout = extract_json_block(raw)

    if not isinstance(scout, dict):
        debug_dir = Path(".agent")
        debug_dir.mkdir(exist_ok=True)
        try:
            (debug_dir / "debug_last_scout_raw.txt").write_text(
                raw or "", encoding="utf-8"
            )
            print(
                "🧭 SCOUT: failed to parse JSON. Raw saved to "
                ".agent/debug_last_scout_raw.txt"
            )
        except Exception as exc:
            print(f"🧭 SCOUT: failed to parse JSON. Raw dump failed: {exc}")

        scout = build_fallback_scout(query, control_result)
        control_result["scout"] = scout
        control_result["scout_error"] = "Scout returned invalid JSON; using fallback."
        print("🧭 SCOUT: using fallback from CONTROL context")
    else:
        print("🧭 SCOUT: triggered")
        control_result["scout"] = scout

    scout_snippets = extract_scout_snippets(
        repo_path=repo_path,
        scout=scout,
    )

    old = control_result.get("related_snippets") or []
    control_result["related_snippets"] = merge_related_snippets(
        scout_snippets,
        old,
        limit=4 + len(scout_snippets),
    )
    print("🧭 SCOUT RESULT:")
    print(json.dumps(scout, indent=2, ensure_ascii=False))

    print("🧭 SCOUT SNIPPETS:")
    print([s.get("file") for s in scout_snippets])

    return control_result
