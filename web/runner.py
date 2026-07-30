from __future__ import annotations

import json
import os, uuid
import re
from pathlib import Path
from typing import Any

from core.agent_state import AgentState
from core.code_dna import dna_to_prompt_block, get_or_compute_dna
from core.credential_redaction import redact_credentials
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
from core.postprocess_gates import run_postprocess_gate_battery
from core.harness_modes import (
    HarnessModeDecision,
    decide_harness_mode,
    format_harness_deny_message,
)
from core.preflight import run_preflight_validation
from core.project_tag import build_project_tag
from core.repo_librarian import (
    load_phantom_limb_report,
)
from core.repository_inventory import create_repository_inventory
from core.runtime_environment import (
    build_runtime_environment_state,
    describe_runtime_environment,
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
    retry_structured_patch_json,
    promote_ts_duplicate_import_candidate_to_patch_plan,
    promote_ts_missing_import_candidate_to_patch_plan,
)
from core.source_snippet_fallback import hydrate_control_source_from_scout
from core.mirror_tunnel_shadow_live_trace import maybe_write_shadow_live_trace
from core.run_progress_snapshot_shadow_writer import (
    is_run_progress_shadow_writer_enabled,
    normalize_run_id,
    safe_update_run_progress_snapshot_shadow,
    safe_write_run_progress_snapshot,
)
from web.mcp_inspector_processes import stop_mcp_inspectors


_WINDOWS_PATH_HINT_RE = re.compile(r"[A-Za-z]:[\\/][^\s\"'<>|]+")
_RUN_PROGRESS_SNAPSHOT_ROOT = Path(__file__).resolve().parent.parent
_EARLY_APPLICATION_ERROR_CATEGORY = "application_error"


def run_web_app(flask_app, **run_kwargs) -> None:
    try:
        flask_app.run(**run_kwargs)
    finally:
        stopped = stop_mcp_inspectors()
        if stopped:
            print(f"Stopped {stopped} MCP Inspector process tree(s).")

def launch_web(host: str | None = None, port: int = 5000, open_browser: bool = True) -> None:
    """Spin up the Flask UI (web/app.py). Imports lazily to avoid a hard
    Flask dependency on every CLI run."""
    host = host or os.getenv("WEB_HOST", "127.0.0.1")
    if os.getenv("APP_ENV") == "docker":
        open_browser = False
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

    run_web_app(app, host=host, port=port, debug=False, use_reloader=False)


def _request_path_hint(query: str) -> str:
    match = _WINDOWS_PATH_HINT_RE.search(query or "")
    return match.group(0) if match else ""


def _request_path_hint_or_repo(query: str, repo_path: str | None) -> str:
    return _request_path_hint(query) or str(repo_path or "").strip()


def _control_target_path(control_result: dict | None) -> str:
    if not isinstance(control_result, dict):
        return ""
    patch_intent = control_result.get("patch_intent") or {}
    if isinstance(patch_intent, dict):
        for key in ("relative_path", "file", "target_file"):
            value = patch_intent.get(key)
            if value:
                return str(value)
    top = control_result.get("top_hypothesis") or {}
    symbol = top.get("symbol") if isinstance(top, dict) else ""
    if isinstance(symbol, str) and "::" in symbol:
        return symbol.split("::", 1)[0]
    return ""


def _control_source_text(control_result: dict | None) -> str:
    if not isinstance(control_result, dict):
        return ""
    patch_intent = control_result.get("patch_intent") or {}
    if isinstance(patch_intent, dict):
        source = patch_intent.get("source_snippet")
        if isinstance(source, str) and source.strip():
            return source
    for related in control_result.get("related_snippets") or []:
        if isinstance(related, dict):
            snippet = related.get("snippet")
            if isinstance(snippet, str) and snippet.strip():
                return snippet
    return ""


def _context_is_degraded(control_result: dict | None) -> bool:
    if not isinstance(control_result, dict):
        return False
    return any(
        bool(control_result.get(key))
        for key in (
            "index_degraded",
            "context_degraded",
            "degraded_context",
            "source_context_degraded",
        )
    )


def _grounding_failed(json_block: dict | None) -> bool:
    if not isinstance(json_block, dict):
        return False
    if json_block.get("patch_plan_rejected"):
        return True
    candidate = json_block.get("patch_candidate")
    if not isinstance(candidate, dict):
        return False
    if candidate.get("grounding_error"):
        return True
    reason = str(candidate.get("reject_reason") or "").lower()
    return bool(candidate.get("rejected")) and (
        "ground" in reason
        or "quote" in reason
        or "target_snippet does not exist" in reason
        or "not found" in reason
    )


def _harness_debug(decision: HarnessModeDecision) -> str:
    return json.dumps(
        {"harness_mode_decision": decision.to_dict()},
        indent=2,
        ensure_ascii=False,
    )


def _harness_payload(decision: HarnessModeDecision) -> dict:
    return {
        "harness_mode": decision.mode,
        "harness_mode_decision": decision.to_dict(),
        "harness_warnings": list(decision.warnings),
    }


def _harness_block_answer(decision: HarnessModeDecision) -> str:
    hard_deny = format_harness_deny_message(decision)
    if hard_deny:
        return hard_deny

    lines = [
        f"Harness mode: {decision.mode}",
        decision.reason,
    ]
    if decision.warnings:
        lines.append("Warnings:")
        lines.extend(f"- {warning}" for warning in decision.warnings)
    return "\n".join(lines)


def _write_debug_no_json_answer(_state: AgentState, reviewed_answer: str) -> None:
    debug_dir = Path(".agent")
    debug_dir.mkdir(exist_ok=True)
    (debug_dir / "debug_no_json_answer.txt").write_text(
        reviewed_answer or "",
        encoding="utf-8",
    )
    print("⚠️ No structured patch JSON. Raw answer saved to .agent/debug_no_json_answer.txt")


def _maybe_write_web_shadow_live_trace(
    *,
    result: dict,
    query: str,
    repo_path: str,
    session_id: Any,
    control_result: dict | None,
    patch_or_diff: Any,
    validation_evidence: Any,
    final_answer: Any,
) -> dict:
    maybe_write_shadow_live_trace(
        repo_path=repo_path or ".",
        run_id=str(session_id or ""),
        user_intent=query,
        control_prompt=control_result,
        patch_or_diff=patch_or_diff,
        validation_evidence=validation_evidence,
        final_answer=final_answer,
        boundary="web.runner.run_agent_web.final_result",
    )
    return result


def _maybe_write_run_progress_snapshot_shadow(
    *,
    result: dict,
    session_id: Any,
    mode: str,
    outcome: str,
    safe_error_category: str | None = None,
) -> dict:
    """Observe one terminal result without changing the result returned to the UI."""
    try:
        metadata = {
            "mode": mode,
            "source_component": "web.runner",
            "result_type": "terminal_error" if outcome == "error" else "terminal_response",
        }
        if outcome == "error" and safe_error_category:
            metadata["error_category"] = safe_error_category
        safe_write_run_progress_snapshot(
            session_id,
            repo_root=_RUN_PROGRESS_SNAPSHOT_ROOT,
            outcome=outcome,
            metadata=metadata,
        )
    except Exception:
        # The writer is an optional shadow observer.  Preserve the original run
        # result even if a future implementation unexpectedly fails here.
        pass
    return result


def _new_run_progress_shadow_run_id() -> str:
    """Create one internal safe ID only when the default-off writer is enabled."""
    return f"run_{uuid.uuid4().hex}" if is_run_progress_shadow_writer_enabled() else ""


def build_current_run_progress_snapshot_association(
    run_id: Any,
    *,
    writer_enabled: bool | None = None,
) -> dict[str, Any]:
    """Build safe, advisory-only metadata for the browser's current run.

    The browser receives a validated slug, never a snapshot path.  This helper
    does not look up, create, or update a snapshot and cannot affect execution.
    """
    enabled = is_run_progress_shadow_writer_enabled() if writer_enabled is None else bool(writer_enabled)
    raw_run_id = str(run_id or "").strip()
    snapshot_id = ""
    warnings: list[str] = []

    if enabled and raw_run_id:
        try:
            snapshot_id = normalize_run_id(raw_run_id)
        except ValueError:
            warnings.append("unsafe_snapshot_id_rejected")

    available = bool(enabled and snapshot_id)
    if available:
        status = "current_run_snapshot_associated_with_warnings"
        notice = (
            "Snapshot associated for this run. It may be loaded manually; "
            "availability does not imply success, validation, or approval."
        )
        warnings.append("association_available_after_run_response")
    elif enabled and raw_run_id:
        status = "current_run_snapshot_invalid"
        notice = "Progress snapshot association is unavailable because its ID was not safe to expose."
    else:
        status = "current_run_snapshot_unavailable"
        notice = (
            "Progress snapshot unavailable because shadow progress writing was disabled."
            if not enabled
            else "Progress snapshot unavailable for this run."
        )

    return {
        "association_status": status,
        "snapshot_id": snapshot_id or None,
        "snapshot_available": available,
        "writer_enabled": enabled,
        "association_mode": "advisory",
        "source_run_result": True,
        "safe_for_loader": available,
        "warnings": warnings,
        "blocked_reasons": [],
        "runtime_result_changed": False,
        "runtime_authority": False,
        "action_triggered": False,
        "actions_available": [],
        "notice": notice,
        "recommended_next_phase": {
            "phase_id": "UX.LIVE.6",
            "title": "Manual Run Progress Refresh",
        },
    }


def _attach_current_run_progress_snapshot_association(
    result: dict,
    run_id: Any,
    *,
    writer_enabled: bool | None = None,
) -> dict:
    """Attach optional discoverability metadata without altering existing payloads."""
    association = build_current_run_progress_snapshot_association(
        run_id,
        writer_enabled=writer_enabled,
    )
    result.update(
        {
            "run_progress_snapshot_id": association["snapshot_id"],
            "run_progress_available": association["snapshot_available"],
            "run_progress_writer_enabled": association["writer_enabled"],
            "run_progress_association_mode": association["association_mode"],
            "run_progress_notice": association["notice"],
        }
    )
    return result


def _maybe_update_run_progress_snapshot_shadow(
    *,
    run_id: str,
    mode: str,
    stage_id: str,
) -> None:
    """Observe a real boundary without allowing progress to control execution."""
    if not run_id:
        return
    try:
        safe_update_run_progress_snapshot_shadow(
            run_id,
            stage_id=stage_id,
            repo_root=_RUN_PROGRESS_SNAPSHOT_ROOT,
            source_component="web.runner",
            mode=mode,
        )
    except Exception:
        pass


def run_agent_web(
    query: str,
    repo_path: str,
    agent_mode: str = "reviewer",
    project_tag: str = None,
    patch_style: str = None,
    ignore_repo_dna: bool = False,
    runtime_environment: str = "auto",
    runtime_environment_custom_name: str = "",
    runtime_environment_notes: str = "",
) -> dict:
    """Web-mode entry point: runs the full agent pipeline against a folder.

    Unlike create_agent_state(), this skips interactive prompts and uses
    sensible defaults (interface=agent, mode=reviewer) so the web UI can drive it.
    """
    is_project_input = bool(repo_path) and os.path.isdir(repo_path)
    interface = "agent"
    mode = agent_mode if agent_mode in {"reviewer", "planner"} else "reviewer"
    runtime_state = build_runtime_environment_state(
        runtime_environment,
        custom_name=runtime_environment_custom_name,
        notes=runtime_environment_notes,
    )
    runtime_description = describe_runtime_environment(
        runtime_state["runtime_environment"],
        runtime_state["runtime_environment_custom_name"],
        runtime_state["runtime_environment_notes"],
    )
    base_harness_decision = decide_harness_mode(
        repo_root=repo_path or ".",
        runtime_environment=runtime_state["runtime_environment"],
        request_path=_request_path_hint_or_repo(query, repo_path),
        source_context_present=True,
    )
    if not base_harness_decision.can_generate_patch:
        return {
            "answer": _harness_block_answer(base_harness_decision),
            "context": "",
            "graph": "",
            "state": _harness_debug(base_harness_decision),
            "patch": "",
            "validation": "",
            "project_tag": project_tag or "",
            "patch_loop_attempts": 0,
            "patch_loop_stop_reason": None,
            **runtime_state,
            "runtime_environment_description": runtime_description,
            **_harness_payload(base_harness_decision),
        }

    operation_inventory = (
        create_repository_inventory(repo_path)
        if is_project_input
        else None
    )
    inventory = (
        operation_inventory.summary()
        if operation_inventory is not None
        else None
    )

    if is_project_input and not inventory["ok"]:
        empty_delta_shadow = None
        try:
            index_repository(
                repo_path,
                project_tag=project_tag,
                inventory=operation_inventory,
            )
        except Exception as exc:
            candidate_shadow = getattr(exc, "delta_shadow", None)
            if isinstance(candidate_shadow, dict):
                empty_delta_shadow = candidate_shadow
        empty_repo_decision = decide_harness_mode(
            repo_root=repo_path,
            runtime_environment=runtime_state["runtime_environment"],
            request_path=_request_path_hint_or_repo(query, repo_path),
            source_context_present=False,
        )
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
            **(
                {"delta_shadow": empty_delta_shadow}
                if isinstance(empty_delta_shadow, dict)
                else {}
            ),
            **runtime_state,
            "runtime_environment_description": runtime_description,
            **_harness_payload(empty_repo_decision),
        }

    input_mode = detect_input_mode(query)
    if is_project_input:
        language = inventory["primary_language"]
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
    task_info.update(runtime_state)
    task_info["runtime_environment_description"] = runtime_description

    final_tag = build_project_tag(repo_path, project_tag)
    print(f"Runtime environment: {runtime_description}")

    control_result = None
    delta_shadow = None
    if is_project_input:
        try:
            clear_graph_cache(repo_path)
            index_result = index_repository(
                repo_path,
                project_tag=final_tag,
                inventory=operation_inventory,
                include_operation_artifacts=True,
            )
            if isinstance(index_result.get("delta_shadow"), dict):
                delta_shadow = index_result["delta_shadow"]
            operation_artifacts = index_result.get(
                "_operation_artifacts",
                {},
            )
            program_graph = operation_artifacts.get("program_graph")
            operation_dna = operation_artifacts.get("code_dna")
            preflight_cmd = extract_user_validation_command(query)

            preflight = run_preflight_validation(
                repo_path=repo_path,
                language=language,
                command=preflight_cmd or None,
                inventory=operation_inventory,
            )
            print("🧪 PREFLIGHT:")
            print(json.dumps(preflight, indent=2, ensure_ascii=False))

            control_result = run_control_structured(
                query,
                repo_path,
                inventory=operation_inventory,
                graph=program_graph,
            )
            if control_result:
                control_result["phantom_limb"] = (
                    index_result.get("phantom_limb")
                    or load_phantom_limb_report(repo_path)
                )
                if isinstance(
                    index_result.get("delta_shadow"),
                    dict,
                ):
                    control_result["delta_shadow"] = (
                        index_result["delta_shadow"]
                    )
                control_result["preflight_validation"] = preflight
                control_result["related_snippets"] = build_related_snippets(
                    control_result,
                    repo_path,
                    graph=program_graph,
                    inventory=operation_inventory,
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
                    inventory=operation_inventory,
                )
                dna_mode = "ignore" if task_info.get("ignore_repo_dna") else "match"
                dna = (
                    operation_dna
                    if isinstance(operation_dna, dict)
                    else get_or_compute_dna(
                        repo_path,
                        inventory=operation_inventory,
                    )
                )
                control_result["code_dna"] = dna
                control_result["code_dna_mode"] = dna_mode
                control_result["code_dna_prompt"] = dna_to_prompt_block(dna, mode=dna_mode)
                control_result["runtime_environment"] = dict(runtime_state)
                control_result["runtime_environment_description"] = runtime_description

        except Exception as e:
            safe_error = redact_credentials(e)
            return {
                "answer": (
                    "Error: indexing/control failed: "
                    f"{safe_error}"
                ),
                "context": "",
                "graph": "",
                "state": "",
                "patch": "",
                "validation": "",
                "project_tag": final_tag,
                **(
                    {"delta_shadow": delta_shadow}
                    if isinstance(delta_shadow, dict)
                    else {}
                ),
                **runtime_state,
                "runtime_environment_description": runtime_description,
                **_harness_payload(base_harness_decision),
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
        runtime_environment=runtime_state["runtime_environment"],
        runtime_environment_custom_name=runtime_state["runtime_environment_custom_name"],
        runtime_environment_notes=runtime_state["runtime_environment_notes"],
        harness_mode=base_harness_decision.mode,
        harness_mode_decision=base_harness_decision.to_dict(),
    )

    shadow_run_id = ""
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
        shadow_run_id = _new_run_progress_shadow_run_id()
        _maybe_update_run_progress_snapshot_shadow(
            run_id=shadow_run_id,
            mode=mode,
            stage_id="request_received",
        )
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

        pre_generation_decision = decide_harness_mode(
            repo_root=state.repo_path or repo_path or ".",
            runtime_environment=state.runtime_environment,
            request_path=_request_path_hint_or_repo(query, repo_path),
            target_path=_control_target_path(state.control_result),
            source_text=_control_source_text(state.control_result),
            index_degraded=_context_is_degraded(state.control_result),
            patch_gates_passed=True,
        )
        state.harness_mode = pre_generation_decision.mode
        state.harness_mode_decision = pre_generation_decision.to_dict()
        if not pre_generation_decision.can_generate_patch:
            answer = _harness_block_answer(pre_generation_decision)
            try:
                save_message(session_id, "user", query)
                save_message(session_id, "assistant", answer)
            except Exception as e:
                print(f"âš ï¸ DB message save skipped: {e}")
            result = {
                "answer": answer,
                "context": json.dumps(state.control_result or {}, indent=2, ensure_ascii=False),
                "graph": json.dumps(state.code_analysis, indent=2),
                "state": _harness_debug(pre_generation_decision),
                "patch": "",
                "validation": "",
                "project_tag": final_tag,
                **(
                    {"delta_shadow": delta_shadow}
                    if isinstance(delta_shadow, dict)
                    else {}
                ),
                "patch_loop_attempts": state.patch_loop_attempts,
                "patch_loop_stop_reason": state.patch_loop_stop_reason,
                **runtime_state,
                "runtime_environment_description": runtime_description,
                **_harness_payload(pre_generation_decision),
            }
            _maybe_write_run_progress_snapshot_shadow(
                result=result,
                session_id=shadow_run_id,
                mode=mode,
                outcome="error",
                safe_error_category=_EARLY_APPLICATION_ERROR_CATEGORY,
            )
            return result

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
        _maybe_update_run_progress_snapshot_shadow(
            run_id=shadow_run_id,
            mode=mode,
            stage_id="model_response_received",
        )
        reviewed = run_review_pipeline(state, draft)
        finalize_answer(state, reviewed)
        run_postprocess_gate_battery(
            state,
            reviewed_answer=reviewed,
            retry_structured_patch_json_fn=retry_structured_patch_json,
            finalize_answer_fn=finalize_answer,
            on_missing_json_after_retries_fn=_write_debug_no_json_answer,
            mode_label="web",
        )
        grounding_failed = _grounding_failed(state.json_block)
        post_gate_decision = decide_harness_mode(
            repo_root=state.repo_path or repo_path or ".",
            runtime_environment=state.runtime_environment,
            request_path=_request_path_hint_or_repo(query, repo_path),
            target_path=_control_target_path(state.control_result),
            source_text=_control_source_text(state.control_result),
            grounding_failed=grounding_failed,
            index_degraded=_context_is_degraded(state.control_result),
            patch_gates_passed=not grounding_failed,
        )
        state.harness_mode = post_gate_decision.mode
        state.harness_mode_decision = post_gate_decision.to_dict()
        if state.json_block:
            state.final_answer = json.dumps(state.json_block, indent=2, ensure_ascii=False)
            state.human_answer = state.final_answer

        print("💾 PATCH RESULT:")
        if state.json_block:
            print(json.dumps(state.json_block, indent=2, ensure_ascii=False))
        else:
            print("No structured patch JSON.")

        if post_gate_decision.can_apply_patch:
            maybe_run_auto_patch(state, interactive=False)
        else:
            print(f"Harness mode blocks apply: {post_gate_decision.mode}")
        state.session_id = session_id
        try:
            save_message(session_id, "user", query)
            save_message(session_id, "assistant", state.final_answer)
        except Exception as e:
            print(f"⚠️ DB message save skipped: {e}")
        result = {
            "answer": state.final_answer,
            "context": state.context_data,
            "graph": json.dumps(state.code_analysis, indent=2),
            "state": _harness_debug(post_gate_decision) + "\n\n" + (state.memory_block or ""),
            "patch": json.dumps(state.json_block, indent=2) if state.json_block else "",
            "validation": state.validation_output or "",
            "project_tag": final_tag,
            **(
                {"delta_shadow": delta_shadow}
                if isinstance(delta_shadow, dict)
                else {}
            ),
            "patch_loop_attempts": state.patch_loop_attempts,
            "patch_loop_stop_reason": state.patch_loop_stop_reason,
            **runtime_state,
            "runtime_environment_description": runtime_description,
            **_harness_payload(post_gate_decision),
        }
        _attach_current_run_progress_snapshot_association(
            result,
            shadow_run_id,
            writer_enabled=is_run_progress_shadow_writer_enabled(),
        )
        _maybe_write_run_progress_snapshot_shadow(
            result=result,
            session_id=shadow_run_id,
            mode=mode,
            outcome="success",
        )
        return _maybe_write_web_shadow_live_trace(
            result=result,
            query=query,
            repo_path=state.repo_path or repo_path or ".",
            session_id=session_id,
            control_result=state.control_result,
            patch_or_diff=state.json_block or {},
            validation_evidence=state.validation_output or "",
            final_answer=state.final_answer,
        )

    except Exception as e:
        safe_error = redact_credentials(e)
        result = {
            "answer": f"Error: {safe_error}",
            "context": "",
            "graph": "",
            "state": "",
            "patch": "",
            "validation": "",
            "project_tag": final_tag,
            **(
                {"delta_shadow": delta_shadow}
                if isinstance(delta_shadow, dict)
                else {}
            ),
            "patch_loop_attempts": 0,
            "patch_loop_stop_reason": None,
            **runtime_state,
            "runtime_environment_description": runtime_description,
            **_harness_payload(base_harness_decision),
        }
        _attach_current_run_progress_snapshot_association(
            result,
            shadow_run_id,
            writer_enabled=is_run_progress_shadow_writer_enabled(),
        )
        return _maybe_write_run_progress_snapshot_shadow(
            result=result,
            session_id=shadow_run_id,
            mode=mode,
            outcome="error",
        )
