from __future__ import annotations

import json
import os, uuid
from pathlib import Path

from core.agent_state import AgentState
from core.code_dna import dna_to_prompt_block, get_or_compute_dna
from core.control_engine import (
    build_related_snippets,
    clear_graph_cache,
    run_control_structured,
)
from core.feature_context import maybe_enrich_with_scout
from core.indexer import index_repository
from core.pipeline import (
    finalize_answer,
    maybe_run_auto_patch,
    run_draft_pipeline,
    run_review_pipeline,
)
from core.preflight import run_preflight_validation
from core.project_tag import build_project_tag
from core.repo_librarian import (
    detect_repo_language,
    inspect_repo_inventory,
    load_phantom_limb_report,
)
from core.router import classify_task, detect_input_mode, detect_language
from core.validation_command import extract_user_validation_command
from database.memory import (
    create_session,
    get_engineering_memory,
    memory_note_exists,
    save_engineering_memory,
    save_message,
)
from patching.patch_gates import (
    collect_patch_repair_reasons,
    reject_ungrounded_patch,
    retry_structured_patch_json,
    normalize_patch_plan_schema,
    promote_go_missing_import_candidate_to_patch_plan,
)
from core.source_snippet_fallback import hydrate_control_source_from_scout

def launch_web(host: str = "127.0.0.1", port: int = 5000, open_browser: bool = True) -> None:
    """Spin up the Flask UI (web/app.py). Imports lazily to avoid a hard
    Flask dependency on every CLI run."""
    try:
        from web.app import app  # lazy import — Flask only loaded if user picks web
    except ImportError as e:
        print(f"❌ Web UI unavailable: {e}")
        print("   Install Flask: pip install flask")
        return

    url = f"http://{host}:{port}"
    print(f"\n🌐 Starting web UI at {url}")
    print("   (use the browser to pick a folder and enter your query)")
    print("   Press Ctrl+C in this terminal to stop the server.\n")

    if open_browser:
        try:
            import webbrowser
            webbrowser.open(url)
        except Exception:
            pass

    app.run(host=host, port=port, debug=False, use_reloader=False)


def run_agent_web(
    query: str,
    repo_path: str,
    agent_mode: str = "reviewer",
    project_tag: str = None,
    patch_style: str = None,
    ignore_repo_dna: bool = False,
) -> dict:
    """Web-mode entry point: runs the full agent pipeline against a folder.

    Unlike create_agent_state(), this skips interactive prompts and uses
    sensible defaults (interface=agent, mode=reviewer) so the web UI can drive it.
    """
    is_project_input = bool(repo_path) and os.path.isdir(repo_path)
    interface = "agent"
    mode = agent_mode if agent_mode in {"reviewer", "planner"} else "reviewer"

    inventory = inspect_repo_inventory(repo_path) if is_project_input else None

    if is_project_input and not inventory["ok"]:
        return {
            "answer": (
                "Error: repo_path exists but contains 0 indexable files. "
                "The web upload handler may have created an empty temp repo."
            ),
            "context": json.dumps(inventory, indent=2, ensure_ascii=False),
            "graph": "",
            "state": "",
            "patch": "",
            "validation": "",
            "project_tag": project_tag or "",
        }

    input_mode = detect_input_mode(query)
    if is_project_input:
        language = detect_repo_language(repo_path)
        if language == "unknown":
            language = detect_language(query)
    else:
        language = detect_language(query, repo_path)
    task_info = classify_task(query, mode=mode, language=language, audience=interface)
    task_info["input_mode"] = input_mode
    task_info["is_project_input"] = is_project_input
    task_info["repo_path"] = repo_path
    task_info["patch_style"] = patch_style
    task_info["ignore_repo_dna"] = bool(ignore_repo_dna)

    final_tag = build_project_tag(repo_path, project_tag)

    control_result = None
    if is_project_input:
        try:
            index_result = index_repository(repo_path, project_tag=final_tag)
            clear_graph_cache(repo_path)
            preflight_cmd = extract_user_validation_command(query)

            preflight = run_preflight_validation(
                repo_path=repo_path,
                language=language,
                command=preflight_cmd or None,
            )
            print("🧪 PREFLIGHT:")
            print(json.dumps(preflight, indent=2, ensure_ascii=False))

            control_result = run_control_structured(query, repo_path)
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
                try:
                    eng_mem = get_engineering_memory(
                        query_text=query,
                        limit=5,
                        project_tag=final_tag,
                    )
                except Exception as e:
                    print(f"⚠️ Engineering memory disabled: {e}")
                    eng_mem = []
                control_result["engineering_memory"] = eng_mem

                control_result = maybe_enrich_with_scout(
                    query=query,
                    repo_path=repo_path,
                    control_result=control_result,
                )
                dna_mode = "ignore" if task_info.get("ignore_repo_dna") else "match"
                dna = get_or_compute_dna(repo_path)
                control_result["code_dna"] = dna
                control_result["code_dna_mode"] = dna_mode
                control_result["code_dna_prompt"] = dna_to_prompt_block(dna, mode=dna_mode)

        except Exception as e:
            return {
                "answer": f"Error: indexing/control failed: {e}",
                "context": "",
                "graph": "",
                "state": "",
                "patch": "",
                "validation": "",
                "project_tag": final_tag,
            }

    state = AgentState(
        interface=interface,
        mode=mode,
        user_input=query,
        file_paths=[repo_path] if repo_path else [],
        primary_file=None,
        input_mode=input_mode,
        language=language,
        task_type=task_info.get("intent", "analysis"),
        task_info=task_info,
        repo_path=repo_path if is_project_input else None,
        is_project_input=is_project_input,
        control_result=control_result,
        project_tag=final_tag,
        ignore_repo_dna=bool(ignore_repo_dna),
    )

    try:
        try:
            session_id = create_session(
                mode=mode,
                language=language,
                title=query[:80],
                project_tag=final_tag,
            )
        except Exception as e:
            print(f"⚠️ DB session disabled: {e}")
            session_id = f"no-db-{uuid.uuid4().hex[:8]}"
        state.session_id = session_id
        # Recover exact source_snippet when Tree-sitter/CONTROL cannot localize,
        # but Scout has identified a likely file/symbol.
        if state.control_result and state.control_result.get("scout") and state.repo_path:
            state.control_result = hydrate_control_source_from_scout(
                control_result=state.control_result,
                repo_path=state.repo_path,
                language=state.language or language,
                query=state.user_input,
            )

            patch_intent = state.control_result.get("patch_intent") or {}
            if patch_intent.get("source_snippet"):
                print("✅ CONTROL source_snippet recovered from Scout fallback")

        if state.control_result and state.control_result.get("scout"):
            scout_files = state.control_result["scout"].get("likely_files", [])
            note = (
                "Scout selected likely context files for feature task: "
                + ", ".join(scout_files[:8])
            )

            try:
                should_save_note = not memory_note_exists(
                    "project_context",
                    note,
                    project_tag=state.project_tag,
                )
            except Exception as e:
                print(f"⚠️ DB memory lookup skipped: {e}")
                should_save_note = False

            if should_save_note:
                try:
                    save_engineering_memory(
                        session_id=state.session_id,
                        memory_type="project_context",
                        value=note,
                        importance=3,
                        project_tag=state.project_tag,
                    )
                except Exception as e:
                    print(f"⚠️ DB memory save skipped: {e}")
        draft = run_draft_pipeline(state)
        reviewed = run_review_pipeline(state, draft)
        finalize_answer(state, reviewed)
        promote_go_missing_import_candidate_to_patch_plan(state)

        repair_reasons = collect_patch_repair_reasons(state)
        if repair_reasons:
            print("🔁 Patch issue detected → retrying JSON repair once:")
            for reason in repair_reasons:
                print(reason)

            repaired = retry_structured_patch_json(
                state,
                state.final_answer + "\n\n" + "\n\n".join(repair_reasons),
            )
            finalize_answer(state, repaired)
            promote_go_missing_import_candidate_to_patch_plan(state)

        if state.mode == "reviewer" and not state.json_block:
            print("🔁 No JSON found → retrying structured JSON repair once...")
            repaired = retry_structured_patch_json(state, reviewed)
            finalize_answer(state, repaired)
            promote_go_missing_import_candidate_to_patch_plan(state)

        if not state.json_block:
            debug_dir = Path(".agent")
            debug_dir.mkdir(exist_ok=True)
            (debug_dir / "debug_no_json_answer.txt").write_text(
                reviewed or "",
                encoding="utf-8",
            )
            print("⚠️ No structured patch JSON. Raw answer saved to .agent/debug_no_json_answer.txt")

        normalize_patch_plan_schema(state)
        reject_ungrounded_patch(state)
        if state.json_block:
            state.final_answer = json.dumps(state.json_block, indent=2, ensure_ascii=False)
            state.human_answer = state.final_answer

        print("💾 PATCH RESULT:")
        if state.json_block:
            print(json.dumps(state.json_block, indent=2, ensure_ascii=False))
        else:
            print("No structured patch JSON.")

        maybe_run_auto_patch(state, interactive=False)
        state.session_id = session_id
        try:
            save_message(session_id, "user", query)
            save_message(session_id, "assistant", state.final_answer)
        except Exception as e:
            print(f"⚠️ DB message save skipped: {e}")
        return {
            "answer": state.final_answer,
            "context": state.context_data,
            "graph": json.dumps(state.code_analysis, indent=2),
            "state": state.memory_block,
            "patch": json.dumps(state.json_block, indent=2) if state.json_block else "",
            "validation": state.validation_output or "",
            "project_tag": final_tag,
            "patch_loop_attempts": state.patch_loop_attempts,
            "patch_loop_stop_reason": state.patch_loop_stop_reason,
        }

    except Exception as e:
        return {
            "answer": f"Error: {str(e)}",
            "context": "",
            "graph": "",
            "state": "",
            "patch": "",
            "validation": "",
            "project_tag": final_tag,
            "patch_loop_attempts": 0,
            "patch_loop_stop_reason": None,
        }
