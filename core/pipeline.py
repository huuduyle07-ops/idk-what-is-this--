from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

from agents.deepseek_client import run_deepseek_review
from agents.gemini_client import run_gemini_request
from config import (
    AUTO_PATCH_ENABLED,
    DEBATE_LOOPS,
    MAX_REVIEW_AGENTS,
    PATCH_LOOP_MAX,
    ROLLBACK_ON_VALIDATION_FAIL,
)
from core.agent_memory import refresh_agent_context, refresh_memory_block
from core.agent_state import AgentState, time_budget_exceeded
from core.control_engine import build_control_prompt, build_control_prompt_human
from core.executor import Executor, ExecutionResult
from core.json_utils import extract_json_block
from core.project_tag import build_project_tag
from core.prompter import (
    build_control_patch_recheck_prompt,
    build_prompt,
    build_re_patch_prompt,
    build_refine_prompt,
    build_replan_prompt,
    build_subtask_execution_prompt,
    build_deepseek_review,
)
from core.retriever import retrieve_context
from core.router import should_auto_patch, should_use_retriever
from core.run_lifecycle import run_patch_plan_with_artifacts
from core.security import is_safe_path
from core.self_correct_loop import run_self_correct_loop
from core.validation_command import (
    extract_user_validation_command,
    get_default_validation_command,
)
from database.memory import (
    get_tooling_profile,
    save_artifact,
    save_engineering_memory,
    save_patch_attempt,
    upsert_tooling_profile,
)
from patching.patch_gates import (
    _enforce_safe_minimal,
    control_missing_source_snippet,
    get_confidence_and_escalation,
    reject_schema_drift,
)
from policy.decision_helper import build_patch_policy


def maybe_retrieve_context(
    user_input: str,
    primary_file: Optional[str],
    task_info: dict,
    file_paths: list[str],
) -> str:
    repo_path = task_info.get("repo_path") or "."
    if primary_file and should_use_retriever(primary_file, task_info):
        print("🧠 Step 0: Retrieving relevant code/document context...")
        return retrieve_context(user_input, primary_file, repo_path=repo_path)
    if len(file_paths) == 1 and os.path.isdir(file_paths[0]):
        print("🧠 Project-level CONTROL retrieval...")
        return ""
    return ""


def run_draft_pipeline(state: AgentState) -> str:
    refresh_memory_block(state)
    if state.is_project_input and state.control_result:
        state.control_result["patch_style"] = state.task_info.get(
            "patch_style",
            "safe_minimal"
        )
        state.control_result["code_dna_mode"] = (
            "ignore" if state.task_info.get("ignore_repo_dna") else "match"
        )

        if state.interface == "agent":
            prompt = build_control_prompt(
                control_result=state.control_result,
                user_query=state.user_input,
                repo_path=state.repo_path,
            )
        else:
            prompt = build_control_prompt_human(
                control_result=state.control_result,
                user_query=state.user_input,
            )
    else:
        prompt = build_prompt(
            user_input=state.user_input,
            mode=state.mode,
            audience=state.interface,
            task_type=state.task_type,
            language=state.language,
            input_mode=state.input_mode,
            code_analysis=state.code_analysis,
            context_data=state.context_data,
            history_block=state.history_block,
            memory_block=state.memory_block,
            task_info=state.task_info,
        )

    if state.control_result:
        print("🐛 DEBUG related snippet files before prompt:")
        print([
            s.get("file")
            for s in state.control_result.get("related_snippets", [])
        ])

        debug_dir = Path(".agent")
        debug_dir.mkdir(exist_ok=True)
        (debug_dir / "debug_last_control_prompt.txt").write_text(
            prompt,
            encoding="utf-8"
        )
    print("👉 Step 1: Gemini is drafting...")
    response = run_gemini_request(prompt, state.file_paths if state.file_paths else None)

    if response.strip().startswith("AGENT_ERROR:"):
        raise RuntimeError(response)

    return response


def _run_one_review_round(state: AgentState, current_answer: str) -> Optional[str]:
    """One pass of: DeepSeek critique → Gemini refine.

    Returns the refined answer, or None if any step errored.
    """
    deepseek_prompt = build_deepseek_review(
        state.user_input,
        state.mode,
        current_answer,
        state.language,
        state.task_type,
        task_info=state.task_info,
    )
    deepseek_review = run_deepseek_review(deepseek_prompt)
    if "AGENT_ERROR:" in deepseek_review:
        return None

    refine_prompt = build_refine_prompt(
        state.user_input,
        state.mode,
        state.interface,
        current_answer,
        deepseek_review,
        state.language,
        state.task_type,
        task_info=state.task_info,
    )
    refined = run_gemini_request(
        refine_prompt,
        state.file_paths if state.file_paths else None,
    )
    if "AGENT_ERROR:" in refined:
        return None
    return refined


def run_review_pipeline(state: AgentState, current_answer: str) -> str:
    if control_missing_source_snippet(state):
        print("🛑 CONTROL source_snippet missing → skipping review/refine to avoid hallucinated patch")
        return current_answer

    preflight = {}
    if state.control_result:
        preflight = state.control_result.get("preflight_validation") or {}

    if (
        state.is_project_input
        and preflight.get("ran")
        and preflight.get("ok") is False
        and preflight.get("category") in {
            "build_error",
            "syntax_error",
            "runtime_error",
            "assertion_failure",
            "test_failure",
            "validation_environment_failed",
            "missing_toolchain",
            "missing_dependency",
            "validation_environment",
            "import_error",
        }
    ):
        print("🧪 Preflight failed → skipping review/refine to preserve compiler-grounded patch")
        return current_answer

    draft_json = extract_json_block(current_answer)
    draft_confidence, draft_needs_escalation = get_confidence_and_escalation(draft_json)
    if (
        state.is_project_input
        and draft_json
        and (
            draft_json.get("patch_plan")
            or draft_json.get("patch_candidate")
        )
    ):
        print("🛡️ Project patch JSON found → skipping review/refine to preserve grounded patch")
        return current_answer

    complexity = state.task_info.get("complexity", "simple")
    intent = state.task_info.get("intent", state.task_type)

    is_project_level = (
        complexity == "extreme" or
        intent in {"architecture_planning", "workflow_orchestration"}
    )

    if complexity == "extreme" and (
        is_project_level or draft_confidence < 0.65 or draft_needs_escalation
    ):
        print(f"🤼 Extreme Task detected: Starting AI {DEBATE_LOOPS}-round Debate Loop...")
        for loop_idx in range(DEBATE_LOOPS):
            print(f"🔄 Debate Round {loop_idx + 1}...")
            refined = _run_one_review_round(state, current_answer)
            if refined is None:
                break
            current_answer = refined
        return current_answer

    if complexity == "complex":
        if draft_confidence >= 0.8 and not draft_needs_escalation and not is_project_level:
            print("⚡ Draft confidence is high. Skipping extra review.")
            return current_answer

        print("🔧 Complex Task detected: Running standard review pipeline...")
        refined = _run_one_review_round(state, current_answer)
        if refined is not None:
            return refined

    return current_answer


def execute_subtask(state: AgentState, subtask: dict) -> dict:
    query_text = f"{subtask.get('action')} {' '.join(subtask.get('targets', []))} {subtask.get('reason', '')}"
    refresh_memory_block(state, query_text=query_text)
    print(f"\n⚡ Executing Subtask: {subtask.get('id', '?')} - {subtask.get('action', 'unknown')}")

    targets = subtask.get("targets", [])
    current_context = ""
    for t in targets:
        if is_safe_path(t):
            try:
                with open(t, "r", encoding="utf-8", errors="replace") as f:
                    current_context += f"\n--- File: {t} ---\n{f.read()}\n"
            except Exception:
                pass

    history_str = "\n".join(f"- {s.get('id')}: {s.get('summary')}" for s in state.completed_subtasks)
    sub_prompt = build_subtask_execution_prompt(
        goal=state.mission_goal,
        subtask=subtask,
        history_block=history_str,
        context_data=current_context,
        language=state.language,
        code_analysis=state.code_analysis,
        memory_block=state.memory_block,
    )

    response = run_gemini_request(sub_prompt)
    res_json = extract_json_block(response)
    if not res_json:
        return {"status": "failed", "summary": "AI returned invalid JSON"}
    res_json["id"] = subtask.get("id")

    if subtask.get("action") == "edit" and res_json.get("patch_candidate"):
        print(f"🛠️ Applying patch for {res_json['patch_candidate'].get('file')}...")
        project_root = Path(state.repo_path) if state.repo_path else Path.cwd()
        executor = Executor(
            project_root=str(project_root),
            rollback_on_validation_fail=ROLLBACK_ON_VALIDATION_FAIL
        )

        patch_res = executor.run(
            patch=res_json["patch_candidate"],
            language=state.language,
            validation_command=get_default_validation_command(state.language, project_root)
        )

        res_json["status"] = "success" if patch_res.success else "failed"
        res_json["summary"] = patch_res.message

        save_patch_attempt(
            task_run_id=state.task_run_id,
            session_id=state.session_id,
            target_file=patch_res.target_file,
            matched_by=patch_res.matched_by,
            phase=patch_res.phase,
            risk_level=patch_res.risk.level if patch_res.risk else None,
            risk_score=patch_res.risk.score if patch_res.risk else None,
            diff=patch_res.diff,
            validation_ok=patch_res.validation_ok,
            validation_output=patch_res.validation_output,
            rollback_performed=patch_res.rollback_performed,
            failure_category=None,
            failure_reason=None,
            project_tag=state.project_tag,
            patch_payload=res_json["patch_candidate"],
            oracle_strength=getattr(patch_res, "oracle_strength", None),
            oracle_tested=getattr(patch_res, "oracle_tested", None),
            oracle_killed=getattr(patch_res, "oracle_killed", None),
        )

        if not patch_res.success:
            failure_report = patch_res.get_failure_report() if hasattr(patch_res, "get_failure_report") else patch_res.message
            return {
                "id": subtask.get("id"),
                "status": "failed",
                "summary": failure_report,
                "raw": patch_res.message,
            }
        else:
            refresh_agent_context(state, str(patch_res.target_file))

    return res_json


def replan_from_failure(state: AgentState, failed_subtask: dict, failure_report: str) -> list[dict]:
    refresh_memory_block(state)
    prompt = build_replan_prompt(
        goal=state.mission_goal,
        original_plan=state.plan,
        completed_subtasks=state.completed_subtasks,
        failed_subtask=failed_subtask,
        failure_report=failure_report,
        language=state.language,
        memory_block=state.memory_block,
        task_info=state.task_info,
    )
    response = run_gemini_request(prompt)
    if "AGENT_ERROR:" in response:
        return []
    res_json = extract_json_block(response)
    if res_json and "subtasks" in res_json:
        return res_json["subtasks"]
    return []


def run_planner_pipeline(state: AgentState, initial_plan: dict) -> str:
    state.mission_goal = initial_plan.get("goal", state.user_input)
    state.plan = initial_plan.get("subtasks", [])
    print(f"\n📋 Multi-step Plan Created: {len(state.plan)} steps.")

    remaining_plan = list(state.plan)
    state.completed_subtasks = []
    replan_budget = 1
    last_replan_steps = []
    state.failed_patterns = []

    while remaining_plan:
        subtask = remaining_plan.pop(0)
        print(f"\n🚀 Running subtask {subtask.get('id')}: {subtask.get('action')}")

        result = execute_subtask(state, subtask)

        state.completed_subtasks.append(result)
        save_artifact(
            state.session_id,
            "subtask_result",
            json.dumps(result, ensure_ascii=False)
        )

        if result.get("status") != "failed":
            continue

        print(f"❌ Subtask failed: {result.get('summary')}")

        if replan_budget > 0:
            print("🧠 Attempting replanning...")

            failure_key = (
                subtask.get("action"),
                result.get("summary", "")[:80]
            )

            if failure_key in state.failed_patterns:
                print("⚠️ Repeated failure pattern. Skipping replan.")
                break

            state.failed_patterns.append(failure_key)

            new_steps = replan_from_failure(
                state,
                failed_subtask=subtask,
                failure_report=result.get("summary", "Unknown error"),
            )

            if new_steps:
                print(f"🔁 Replan successful: {len(new_steps)} new steps")
                remaining_plan = new_steps + remaining_plan
                last_replan_steps = new_steps
                replan_budget -= 1
                continue

        print("🛑 No valid replan. Halting.")
        break

    if last_replan_steps:
        save_artifact(
            state.session_id,
            "replan",
            json.dumps(last_replan_steps, ensure_ascii=False)
        )

    summary_lines = [f"Mission Goal: {state.mission_goal}", ""]
    for s in state.completed_subtasks:
        status = (s.get("status") or "unknown").upper()
        summary_lines.append(f"[{s.get('id')}] {status}: {s.get('summary')}")

    return "\n".join(summary_lines)


def finalize_answer(state: AgentState, answer: str) -> None:
    from core.session_io import strip_json_from_text  # avoid circular import

    state.final_answer = answer
    state.json_block = extract_json_block(answer)
    state.human_answer = strip_json_from_text(answer)

    if state.json_block and not state.human_answer:
        state.human_answer = json.dumps(state.json_block, ensure_ascii=False, indent=2)

    reject_schema_drift(state)
    _enforce_safe_minimal(state)

def normalize_patch_candidate_with_control_source(state: AgentState) -> None:
    if not state.json_block:
        return

    patch = state.json_block.get("patch_candidate")
    if not isinstance(patch, dict):
        return

    if patch.get("target_node_kind") != "function":
        return

    control = state.control_result or {}
    patch_intent = control.get("patch_intent") or {}
    source = patch_intent.get("source_snippet") or ""

    if not source:
        return

    target = patch.get("target_snippet") or ""
    patched = patch.get("patched_snippet") or ""

    if not target or not patched:
        return

    # Already full-function enough. Skip the rewrite when the AI's snippet
    # already looks like a complete named function — broadening to the
    # control's source_snippet only helps when the AI returned a partial
    # body, and otherwise risks introducing whitespace/newline drift
    # between `source` and the actual file bytes (which makes the
    # downstream literal apply silently miss).
    target_stripped = target.strip()
    function_keyword_prefixes = (
        "func ",
        "pub fn ", "pub(crate) fn ", "pub async fn ", "async fn ", "fn ",
        "def ", "async def ",
        "function ", "async function ",
        "export function ", "export async function ",
        "export default function ", "export default async function ",
    )
    if target_stripped.startswith(function_keyword_prefixes):
        return

    # C/C++/Java/C#-style: declaration is `<type/qualifiers> name(args) {`
    # with no anchor keyword. Treat as already-complete if the declared
    # `target_node_name` appears followed by `(` on the first non-blank
    # line and the snippet has an opening brace.
    target_node_name = patch.get("target_node_name") or ""
    if target_node_name:
        import re as _re
        first_line = next((ln.strip() for ln in target.splitlines() if ln.strip()), "")
        if _re.search(rf"\b{_re.escape(target_node_name)}\s*\(", first_line) and "{" in target:
            return

    if target not in source:
        return

    full_patched = source.replace(target, patched, 1)

    patch["target_snippet"] = source
    patch["patched_snippet"] = full_patched
    patch["__normalized_from_partial_body"] = True

    print("🧩 Normalized partial function patch to full CONTROL source_snippet")

def is_low_risk_single_file_patch(state: AgentState) -> bool:
    if not state.json_block:
        return False

    if state.json_block.get("patch_plan"):
        return False

    patch = state.json_block.get("patch_candidate")
    if not isinstance(patch, dict):
        return False

    writer_confidence, needs_escalation = get_confidence_and_escalation(state.json_block)
    if writer_confidence < 0.75 or needs_escalation:
        return False

    rel = patch.get("relative_path") or patch.get("file") or ""
    target = patch.get("target_snippet") or ""
    patched = patch.get("patched_snippet") or ""

    if not rel or not target or not patched:
        return False

    if not state.repo_path:
        return False

    path = os.path.join(state.repo_path, rel)

    if not is_safe_path(path, allowed_roots=[state.repo_path]):
        return False

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except OSError:
        return False

    if target not in text:
        return False

    scout = (state.control_result or {}).get("scout") or {}
    scout_files = set(scout.get("likely_files") or [])

    top = (state.control_result or {}).get("top_hypothesis") or {}
    symbol = top.get("symbol") or ""
    control_file = symbol.split("::", 1)[0] if "::" in symbol else ""

    return rel in scout_files or rel == control_file


def maybe_run_auto_patch(state: AgentState, interactive: bool = True) -> None:
    if not AUTO_PATCH_ENABLED:
        print("Auto-patch disabled by AUTO_PATCH_ENABLED=false.")
        return

    normalize_patch_candidate_with_control_source(state)

    confidence, _ = get_confidence_and_escalation(state.json_block)

    control = state.control_result or {}
    top = control.get("top_hypothesis") or {}
    patch_intent = control.get("patch_intent") or {}

    action = top.get("recommended_action", "")
    source_snippet = patch_intent.get("source_snippet")
    print("🐛 DEBUG control source_snippet exists:", bool(source_snippet))

    writer_confidence, needs_escalation = get_confidence_and_escalation(state.json_block)

    top = (state.control_result or {}).get("top_hypothesis") or {}
    try:
        control_confidence = float(top.get("confidence", 0.0))
    except Exception:
        control_confidence = 0.0

    combined_confidence = (writer_confidence + control_confidence) / 2

    if needs_escalation:
        print("🛑 Patch needs escalation → skip patch")
        return

    plan = state.json_block.get("patch_plan")
    style = state.task_info.get("patch_style") or state.patch_style or "safe_minimal"
    scout = (state.control_result or {}).get("scout") or {}
    request_type = scout.get("request_type")

    task_intent = state.task_info.get("intent", "")
    preflight = (state.control_result or {}).get("preflight_validation") or {}

    is_compiler_grounded_fix = (
        preflight.get("ran")
        and preflight.get("ok") is False
        and preflight.get("category") in {
            "build_error",
            "syntax_error",
            "import_error",
            "missing_dependency",
        }
    )

    is_allowed_patch_plan = (
        isinstance(plan, list)
        and bool(plan)
        and style in {"balanced", "vibe"}
        and (
            request_type in {"feature_extension", "bug_fix", "refactor"}
            or task_intent in {"bug_fix", "feature_add", "refactor", "debug_error_log"}
            or is_compiler_grounded_fix
        )
    )

    if action in {"collect_more_evidence", "explore"} and is_allowed_patch_plan:
        print("⚠️ CONTROL wanted more evidence, but Scout produced a grounded patch_plan; continuing.")

    if isinstance(plan, list) and plan:
        if not is_allowed_patch_plan:
            print("🛑 patch_plan detected but not allowed for this task/style.")
            return
        project_root = Path(state.repo_path) if state.repo_path else Path.cwd()
        explicit_cmd = extract_user_validation_command(state.user_input)
        validation_command = (
            explicit_cmd
            or get_default_validation_command(state.language, project_root)
            or None
        )
        print("🧩 Grounded patch_plan detected → running patch_plan_executor")
        result = run_patch_plan_with_artifacts(
            str(project_root),
            plan,
            validation_command=validation_command,
            user_query=state.user_input,
            control_result=state.control_result,
            source="pipeline",
        )
        combined_diff = "\n\n".join(result.get("diffs", []) or [])
        try:
            save_patch_attempt(
                task_run_id=state.task_run_id,
                session_id=state.session_id,
                target_file="patch_plan",
                matched_by="patch_plan_executor",
                phase="validated" if result.get("success") else "patch_plan_failed",
                risk_level=None,
                risk_score=None,
                diff=combined_diff,
                validation_ok=result.get("success"),
                validation_output=result.get("validation_output", ""),
                rollback_performed=result.get("rollback_performed", False),
                failure_category=None,
                failure_reason=None,
                project_tag=state.project_tag,
                patch_payload={"patch_plan": plan},
            )
        except Exception as e:
            print(f"⚠️ DB patch_attempt save skipped: {e}")
        state.validation_output = result.get("validation_output", "")
        state.auto_patch_result = result.get("message", "")
        print(result.get("message", ""))
        if result.get("validation_output"):
            print(result.get("validation_output"))

        if result.get("success"):
            print("✅ Patch plan applied + validation passed.")
        else:
            print("🛑 Patch plan failed or rolled back.")
        return

    low_risk_single_patch = is_low_risk_single_file_patch(state)

    if low_risk_single_patch:
        if combined_confidence < 0.55:
            print(
                f"🛑 Combined confidence too low for low-risk patch → skip "
                f"(writer={writer_confidence:.2f}, control={control_confidence:.2f}, "
                f"combined={combined_confidence:.2f})"
            )
            return

        print(
            f"✅ Low-risk single-file patch accepted "
            f"(writer={writer_confidence:.2f}, control={control_confidence:.2f}, "
            f"combined={combined_confidence:.2f})"
        )

    else:
        if combined_confidence < 0.65:
            print(
                f"🛑 Combined confidence too low → skip patch "
                f"(writer={writer_confidence:.2f}, control={control_confidence:.2f}, "
                f"combined={combined_confidence:.2f})"
            )
            return

        if not source_snippet:
            print("🛑 Missing source snippet → skip patch")
            return

        if action in {"collect_more_evidence", "explore"}:
            print(f"🛑 CONTROL action = {action} → skip patch")
            return

    auto_policy_ok = should_auto_patch(
        mode=state.mode,
        audience=state.interface,
        confidence=confidence,
        task_info=state.task_info,
    )

    if not auto_policy_ok and not low_risk_single_patch:
        print("⚠️ Auto-patch policy decided to skip patching.")
        return

    if not auto_policy_ok and low_risk_single_patch:
        print("⚠️ Global auto-patch policy would skip, but low-risk grounded single-file patch is allowed to continue.")

    current_patch = state.json_block.get("patch_candidate") or dict(state.json_block)

    if current_patch.get("rejected"):
        print(f"🛑 Patch rejected: {current_patch.get('reject_reason')}")
        return

    project_root = Path(state.repo_path) if state.repo_path else Path.cwd()
    project_tag = state.project_tag or build_project_tag(state.repo_path)
    try:
        tooling = get_tooling_profile(project_tag, state.language)
    except Exception as e:
        print(f"⚠️ DB tooling profile lookup skipped: {e}")
        tooling = {}

    explicit_cmd = extract_user_validation_command(state.user_input)

    default_cmd = (
        explicit_cmd
        or tooling.get("test_command")
        or tooling.get("build_command")
        or get_default_validation_command(state.language, project_root)
    )

    user_validation_cmd: Optional[str] = default_cmd or None

    style = state.task_info.get("patch_style", "safe_minimal")
    policy_confidence = combined_confidence if low_risk_single_patch else control_confidence
    policy = build_patch_policy(
        style,
        language=state.language,
        control_confidence=policy_confidence,
        has_validation_command=bool(user_validation_cmd),
    )

    if not policy.auto_apply_allowed:
        if low_risk_single_patch:
            print(
                f"✅ Patch policy accepted: "
                f"{policy.style}"
            )
        else:
            print(f"🛑 Patch style policy blocks auto-apply: {policy.style}")
            return

    state.started_at = time.time()

    if time_budget_exceeded(state):
        print("⏱️ Time budget exceeded → stopping patch loop")
        return

    if interactive and state.interface != "agent":
        entered = input(f"\n🧪 Validation command [Enter = {default_cmd}]: ").strip()
        user_validation_cmd = entered if entered else default_cmd
    else:
        user_validation_cmd = default_cmd

    if user_validation_cmd and user_validation_cmd != tooling.get("test_command"):
        try:
            upsert_tooling_profile(
                project_tag=project_tag,
                language=state.language,
                test_command=user_validation_cmd,
            )
        except Exception as e:
            print(f"⚠️ DB tooling profile save skipped: {e}")
        tooling["test_command"] = user_validation_cmd

    def _on_attempt(idx: int, result: ExecutionResult) -> Optional[bool]:
        print(f"\n🔁 Patch Loop {idx}/{PATCH_LOOP_MAX}")
        state.auto_patch_result = result.message
        try:
            save_patch_attempt(
                task_run_id=state.task_run_id,
                session_id=state.session_id,
                target_file=result.target_file,
                matched_by=result.matched_by,
                phase=result.phase,
                risk_level=result.risk.level if result.risk else None,
                risk_score=result.risk.score if result.risk else None,
                diff=result.diff,
                validation_ok=result.validation_ok,
                validation_output=result.validation_output,
                rollback_performed=result.rollback_performed,
                failure_category=(result.failure_info or {}).get("category") if result.failure_info else None,
                failure_reason=(result.failure_info or {}).get("reason") if result.failure_info else None,
                project_tag=state.project_tag,
                patch_payload=current_patch_holder["patch"],
                oracle_strength=getattr(result, "oracle_strength", None),
                oracle_tested=getattr(result, "oracle_tested", None),
                oracle_killed=getattr(result, "oracle_killed", None),
            )
        except Exception as e:
            print(f"⚠️ DB patch_attempt save skipped: {e}")
        print(f"🔎 Executor phase: {result.phase}")
        print(result.message)

        if result.matched_by:
            print(f"🧩 Match source: {result.matched_by}")
        if result.risk:
            print(f"⚠️ Risk: {result.risk.level} (score={result.risk.score})")
            for reason in result.risk.reasons:
                print(f"  - {reason}")
        if result.diff:
            print("\n📌 Patch diff preview:")
            print(result.diff)
            state.auto_patch_result = result.diff
        if result.validation_output:
            print("\n🧪 Validation output:")
            print(result.validation_output)
            state.validation_output = result.validation_output

        if result.phase == "validation_environment_failed":
            save_engineering_memory(
                session_id=state.session_id,
                memory_type="validation_environment_issue",
                value=(
                    f"{result.failure_info.get('category')}: "
                    f"{result.failure_info.get('reason')}"
                ),
                project_tag=state.project_tag,
            )
            refresh_memory_block(state)
            return None

        if result.success:
            save_engineering_memory(
                session_id=state.session_id,
                memory_type="successful_fix",
                value=f"{result.target_file} fixed via {result.matched_by}",
                project_tag=state.project_tag,
            )
            refresh_memory_block(state)
            return None

        if result.phase in {"dry_run_blocked", "post_apply_blocked"}:
            save_engineering_memory(
                session_id=state.session_id,
                memory_type="bug_pattern",
                value=f"Patch blocked ({result.phase}) for {result.target_file}",
                project_tag=state.project_tag,
            )
            refresh_memory_block(state)
            return None

        if getattr(result, "failure_info", None):
            save_engineering_memory(
                session_id=state.session_id,
                memory_type="bug_pattern",
                value=f"{result.failure_info.get('category')}: {result.failure_info.get('reason')}",
                project_tag=state.project_tag,
            )
            refresh_memory_block(state)
        return None

    def _re_patch_fn(result: ExecutionResult, _default_prompt: str) -> Optional[Dict[str, Any]]:
        if time_budget_exceeded(state):
            print("⏱️ Time budget exceeded → stopping patch loop")
            return None

        print("🧠 Asking AI to fix previous patch...")
        failed_patch = current_patch_holder["patch"]

        issues_for_recheck = [failed_patch.get("issue", "unknown issue")]
        if getattr(result, "failure_info", None):
            issues_for_recheck.append(f"Validation category: {result.failure_info.get('category')}")
            issues_for_recheck.append(f"Why: {result.failure_info.get('reason')}")
            issues_for_recheck.append(f"Hint: {result.failure_info.get('hint')}")
        if result.matched_by:
            issues_for_recheck.append(f"Patch was applied via: {result.matched_by}")

        if state.control_result:
            failure_report = (
                result.get_failure_report()
                if hasattr(result, "get_failure_report")
                else result.message
            )
            recheck_prompt = build_control_patch_recheck_prompt(
                control_result=state.control_result,
                failed_patch=failed_patch,
                failure_report=failure_report,
                validation_output=result.validation_output or "",
            )
        else:
            recheck_prompt = build_re_patch_prompt(
                failed_patch=failed_patch,
                failure_info=getattr(result, "failure_info", None),
                validation_output=result.validation_output or "",
                target_file=result.target_file,
                matched_by=result.matched_by,
                extra_hints=issues_for_recheck,
                project_tag=state.project_tag,
            )

        agents = [
            ("deepseek", run_deepseek_review),
            ("gemini", run_gemini_request),
        ]
        agent_results = []
        for name, fn in agents[:MAX_REVIEW_AGENTS]:
            try:
                resp = fn(recheck_prompt)
                if "AGENT_ERROR:" in resp:
                    continue
                parsed = extract_json_block(resp)
                if parsed:
                    agent_results.append((name, parsed))
            except Exception:
                continue

        if not agent_results:
            print("❌ No valid patch from any agent")
            return None

        best_name, best_patch = max(agent_results, key=lambda x: x[1].get("confidence", 0.0))
        print(f"🧠 Selected patch from: {best_name}")

        new_conf, _ = get_confidence_and_escalation(best_patch)
        if new_conf < 0.3:
            print("⚠️ Confidence too low → stopping loop")
            return None

        if state.control_result:
            best_patch["__control_patch_intent"] = state.control_result.get("patch_intent")
        current_patch_holder["patch"] = best_patch
        return best_patch

    current_patch_holder = {"patch": current_patch}

    loop_result = run_self_correct_loop(
        project_root=str(project_root),
        initial_patch=current_patch,
        language=state.language,
        re_patch_fn=_re_patch_fn,
        on_attempt=_on_attempt,
        validation_command=user_validation_cmd or "",
        max_attempts=PATCH_LOOP_MAX,
        rollback_on_validation_fail=ROLLBACK_ON_VALIDATION_FAIL,
        project_tag=state.project_tag,
    )

    state.patch_loop_attempts = len(loop_result.get("attempts", []))
    state.patch_loop_stop_reason = loop_result.get("stop_reason")

    if loop_result["success"]:
        print("✅ Executor finished successfully.")
        return

    stop_reason = loop_result.get("stop_reason")
    final_phase = loop_result.get("final_phase")
    if final_phase == "validation_environment_failed":
        print("🛑 Validation failed because the environment/toolchain is missing.")
        print("   Not asking AI to rewrite the patch.")
        return
    if stop_reason == "policy_block":
        print("🛑 Patch was blocked by executor policy.")
        return
    print("⚠️ Max patch loops reached.")
