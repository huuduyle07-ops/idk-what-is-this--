from __future__ import annotations

import json
import os
from typing import Optional

from core.agent_memory import build_memory_block
from core.agent_state import AgentState
from core.code_parse import analyze_code_structure
from core.code_dna import dna_to_prompt_block, get_or_compute_dna
from core.control_engine import (
    build_related_snippets,
    clear_graph_cache,
    run_control_structured,
)
from core.feature_context import maybe_enrich_with_scout
from core.indexer import index_repository
from core.pipeline import maybe_retrieve_context
from core.preflight import run_preflight_validation
from core.project_tag import build_project_tag
from core.repo_librarian import (
    detect_repo_language,
    load_phantom_limb_report,
)
from core.router import classify_task, detect_input_mode, detect_language
from core.security import is_safe_path
from core.validation_command import extract_user_validation_command
from database.memory import (
    create_session,
    create_task_run,
    get_engineering_memory,
    get_recent_messages,
    memory_note_exists,
    save_artifact,
    save_engineering_memory,
    save_message,
)

HUMAN_MODES = {"tutor", "explainer"}
AGENT_MODES = {"reviewer", "planner"}


def ask_entrypoint() -> str:
    """Pick how the user will drive the run.

    - 'web'      → launch the Flask UI (good for file picking + clean UI)
    - 'terminal' → keep using the CLI (good for mode picking + watching the pipeline)
    """
    while True:
        choice = input(
            "🚪 Entry point [web/terminal] (web = browser UI, terminal = CLI): "
        ).strip().lower()
        if choice in {"web", "w"}:
            return "web"
        if choice in {"terminal", "cli", "t"}:
            return "terminal"
        print("Please choose either: web or terminal")


def ask_interface() -> str:
    while True:
        interface = input("🧭 Choose interface [human/agent]: ").strip().lower()
        if interface in {"human", "agent"}:
            return interface
        print("Please choose either: human or agent")


def ask_mode(interface: str) -> Optional[str]:
    """Returns the chosen mode, or None if the user wants to go back."""
    valid = HUMAN_MODES if interface == "human" else AGENT_MODES
    if interface == "human":
        prompt = "🧭 Choose mode [tutor/explainer] (or 'back' to change interface): "
    else:
        prompt = "🧭 Choose mode [reviewer/planner] (or 'back' to change interface): "
    while True:
        mode = input(prompt).strip().lower()
        if mode in {"back", "b"}:
            return None
        if mode in valid:
            return mode
        print(f"Please choose one of: {', '.join(sorted(valid))} (or 'back')")


def ask_interface_and_mode() -> tuple[str, str]:
    """Loops until the user has confirmed both interface and mode."""
    while True:
        interface = ask_interface()
        mode = ask_mode(interface)
        if mode is not None:
            return interface, mode
        print("↩️  Going back to interface selection.\n")


def load_safe_file_paths(raw_text: str) -> list[str]:
    raw_paths = [p.strip() for p in raw_text.split("|") if p.strip()]
    safe_paths: list[str] = []
    repo_path = raw_paths[0] if len(raw_paths) == 1 and os.path.isdir(raw_paths[0]) else None
    allowed_roots = [repo_path] if repo_path else []

    for path in raw_paths:
        if not is_safe_path(path, allowed_roots=allowed_roots):
            print(f"🛑 Security Block: Access to '{path}' is restricted or outside project.")
            continue

        if os.path.isdir(path):
            print(f"📁 Project detected: {path}")
            return [path]
        else:
            safe_paths.append(path)
    return safe_paths


def load_code_source(user_input: str, primary_file: Optional[str]) -> str:
    if not primary_file or not is_safe_path(primary_file):
        return user_input
    try:
        with open(primary_file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception:
        return user_input


def create_agent_state() -> AgentState | None:
    interface, mode = ask_interface_and_mode()

    patch_style = input("Patch style [safe_minimal/balanced/vibe] (Enter = safe_minimal): ").strip() or "safe_minimal"
    ignore_repo_dna_raw = input("Ignore repo DNA? [y/N] (Enter = match repo style): ").strip().lower()
    ignore_repo_dna = ignore_repo_dna_raw in {"y", "yes", "1", "true"}

    user_input = input("\n👨‍🎓 Enter your question / code / task: ").strip()
    if not user_input or user_input.lower() == "exit":
        print("Session ended.")
        return None

    file_paths_raw = input("📄 Optional file/folder paths (separate by |) [Enter to skip]: ").strip()
    file_paths = load_safe_file_paths(file_paths_raw)
    primary_file = file_paths[0] if file_paths else None
    is_project_input = len(file_paths) == 1 and os.path.isdir(file_paths[0])
    repo_path = file_paths[0] if is_project_input else None

    user_tag = input("Project tag (optional, Enter to auto-detect): ").strip()
    project_tag = build_project_tag(repo_path, user_tag)

    index_result = {}
    if is_project_input and repo_path:
        print(f"🧭 Indexing project before retrieval... [tag={project_tag}]")
        index_result = index_repository(repo_path, project_tag=project_tag)

    input_mode = detect_input_mode(user_input)
    if is_project_input and repo_path:
        language = detect_repo_language(repo_path)
        if language == "unknown":
            language = detect_language(user_input)
    else:
        language = detect_language(user_input, primary_file)

    task_info = classify_task(
        user_input,
        mode=mode,
        language=language,
        audience=interface,
    )
    task_info["input_mode"] = input_mode
    task_info["is_project_input"] = is_project_input
    task_info["repo_path"] = repo_path
    task_info["patch_style"] = patch_style
    task_info["ignore_repo_dna"] = ignore_repo_dna

    task_type = task_info["intent"]

    if is_project_input:
        code_source = ""
        code_analysis = {}
    else:
        code_source = load_code_source(user_input, primary_file)
        code_analysis = analyze_code_structure(code_source, language=language)

    session_id = create_session(
        mode=mode,
        language=language,
        title=user_input[:80],
        project_tag=project_tag,
    )
    save_message(session_id, "user", user_input)

    context_data = maybe_retrieve_context(user_input, primary_file, task_info, file_paths)
    control_result = None
    if is_project_input and repo_path:
        preflight_cmd = extract_user_validation_command(user_input)
        preflight = run_preflight_validation(
            repo_path=repo_path,
            language=language,
            command=preflight_cmd or None,
        )
        print("🧪 PREFLIGHT:")
        print(json.dumps(preflight, indent=2, ensure_ascii=False))
        clear_graph_cache(repo_path)
        control_result = run_control_structured(user_input, repo_path)
        if control_result:
            control_result["phantom_limb"] = (
                index_result.get("phantom_limb")
                or load_phantom_limb_report(repo_path)
            )
            control_result["preflight_validation"] = preflight
            control_result["related_snippets"] = build_related_snippets(
                control_result,
                repo_path,
            )

        eng_mem = get_engineering_memory(query_text=user_input, limit=5, project_tag=project_tag)

        if control_result:
            control_result["engineering_memory"] = eng_mem
            control_result = maybe_enrich_with_scout(
                query=user_input,
                repo_path=repo_path,
                control_result=control_result,
            )
            dna_mode = "ignore" if task_info.get("ignore_repo_dna") else "match"
            dna = get_or_compute_dna(repo_path)
            control_result["code_dna"] = dna
            control_result["code_dna_mode"] = dna_mode
            control_result["code_dna_prompt"] = dna_to_prompt_block(dna, mode=dna_mode)
            if control_result.get("scout"):
                scout_files = control_result["scout"].get("likely_files", [])
                note = (
                    "Scout selected likely context files for feature task: "
                    + ", ".join(scout_files[:8])
                )

                if not memory_note_exists("project_context", note, project_tag=project_tag):
                    save_engineering_memory(
                        session_id=session_id,
                        memory_type="project_context",
                        value=note,
                        importance=3,
                        project_tag=project_tag,
                    )

    save_artifact(session_id, "code_analysis", json.dumps(code_analysis, ensure_ascii=False))
    save_artifact(session_id, "retrieved_context", context_data or "")

    recent_messages = get_recent_messages(session_id, limit=6)
    history_block = "\n\n".join(f"{m['role'].upper()}:\n{m['content']}" for m in recent_messages)
    memory_block = build_memory_block(user_input, file_paths, interface, mode, project_tag)

    task_run_id = create_task_run(
        session_id=session_id,
        audience=interface,
        mode=mode,
        intent=task_info.get("intent", task_type),
        complexity=task_info.get("complexity", "unknown"),
        input_mode=task_info.get("input_mode", input_mode),
        language=language,
        user_input=user_input,
    )

    return AgentState(
        interface=interface,
        mode=mode,
        user_input=user_input,
        file_paths=file_paths,
        primary_file=primary_file,
        input_mode=input_mode,
        language=language,
        task_type=task_type,
        task_info=task_info,
        session_id=session_id,
        code_source=code_source,
        code_analysis=code_analysis,
        context_data=context_data,
        history_block=history_block,
        memory_block=memory_block,
        task_run_id=task_run_id,
        is_project_input=is_project_input,
        repo_path=repo_path,
        control_result=control_result,
        project_tag=project_tag,
        ignore_repo_dna=ignore_repo_dna,
    )
