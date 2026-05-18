from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from agents.gemini_client import run_gemini_request
from config import LANGUAGE_MAP
from core.agent_state import AgentState
from core.code_parse import analyze_code_structure
from core.prompter import build_memory_extraction_prompt
from core.security import is_safe_path
from database.memory import (
    get_engineering_memory,
    get_relevant_memory_notes,
    get_session_messages,
    get_tooling_context,
    memory_note_exists,
    save_memory_note,
)


def extract_memory_notes_with_ai(session_id: int) -> list[dict]:
    messages = get_session_messages(session_id, limit=30)
    transcript = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in messages)
    prompt = build_memory_extraction_prompt(transcript)

    raw = run_gemini_request(prompt).strip()
    if raw.startswith("AGENT_ERROR:"):
        return []

    raw = raw.replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            cleaned: list[dict] = []
            for item in data[:3]:
                if not isinstance(item, dict):
                    continue
                category = str(item.get("category", "")).strip()
                note = str(item.get("note", "")).strip()
                importance = int(item.get("importance", 1))
                if category and note:
                    cleaned.append(
                        {
                            "category": category,
                            "note": note,
                            "importance": max(1, min(5, importance)),
                        }
                    )
            return cleaned
    except Exception:
        pass
    return []


def refresh_agent_context(state: AgentState, changed_file_path: Optional[str] = None) -> None:
    """Updates state after code changes or for new retrieval."""
    if changed_file_path and os.path.isfile(changed_file_path):
        allowed_roots = [state.repo_path] if state.repo_path else None
        if not is_safe_path(changed_file_path, allowed_roots=allowed_roots):
            return

        try:
            if state.primary_file and os.path.abspath(changed_file_path) == os.path.abspath(state.primary_file):
                with open(changed_file_path, "r", encoding="utf-8", errors="replace") as f:
                    state.code_source = f.read()

            ext = Path(changed_file_path).suffix.lower()
            lang = LANGUAGE_MAP.get(ext, "unknown")
            try:
                with open(changed_file_path, "r", encoding="utf-8", errors="replace") as f:
                    file_text = f.read()
            except Exception:
                file_text = ""
            new_analysis = analyze_code_structure(file_text, lang)

            repo_abs = os.path.abspath(state.repo_path) if state.repo_path else os.getcwd()
            rel_path = os.path.relpath(os.path.abspath(changed_file_path), repo_abs)

            if "files" not in state.code_analysis:
                state.code_analysis["files"] = {}
            state.code_analysis["files"][rel_path] = new_analysis
            print(f"🔄 Context refreshed for: {rel_path}")
        except Exception as e:
            print(f"⚠️ Warning: Could not refresh context for {changed_file_path}: {e}")

    refresh_memory_block(state)


def refresh_memory_block(state: AgentState, query_text: Optional[str] = None) -> None:
    state.memory_block = build_memory_block(
        query_text or state.user_input,
        state.file_paths,
        state.interface,
        state.mode,
        state.project_tag,
    )


def persist_ai_memory_notes(session_id: int, project_tag: str) -> None:
    notes = extract_memory_notes_with_ai(session_id)
    for item in notes:
        if not memory_note_exists(item["category"], item["note"], project_tag=project_tag):
            save_memory_note(
                session_id=session_id,
                category=item["category"],
                note=item["note"],
                importance=item["importance"],
                project_tag=project_tag,
            )


def build_memory_block(user_input, file_paths, interface, mode, project_tag):
    is_project_input = len(file_paths) == 1 and os.path.isdir(file_paths[0])

    if is_project_input:
        return ""

    memories = []
    eng_mem = get_engineering_memory(
        query_text=user_input,
        limit=5,
        project_tag=project_tag
    )
    if eng_mem:
        memories.append("=== Engineering Memory ===")
        for m in eng_mem:
            weight = m.get("importance", 1)

            if weight >= 4:
                prefix = "🔥"
            elif weight >= 3:
                prefix = "⚠️"
            else:
                prefix = "-"

            memories.append(f"{prefix} {m['memory_type']}: {m['value']}")

    if interface == "agent" or mode in {"reviewer", "planner"}:
        tool_mem = get_tooling_context(query_text=user_input, limit=3, project_tag=project_tag)
        if tool_mem:
            memories.append("\n=== Tooling ===")
            for t in tool_mem:
                memories.append(f"- [{t.get('category', 'tooling')}] {t.get('note') or t.get('value')}")

    else:
        user_mem = get_relevant_memory_notes(query_text=user_input, limit=3)
        if user_mem:
            memories.append("\n=== User Memory ===")
            for u in user_mem:
                memories.append(f"- {u['note']}")

    return "\n".join(memories)
