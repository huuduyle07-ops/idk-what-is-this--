from __future__ import annotations

import json
import os
import re
import time
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Mapping, Optional

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
from core.authoritative_binding_context import (
    AuthoritativeBindingContext,
)
from core.author_escalation_admission import admit_author_escalation
from core.analysis_evidence import (
    AnalysisEvidence,
    build_analysis_answer_prompt,
    collect_analysis_evidence,
)
from core.live_task_routing import (
    WORKFLOW_ANALYSIS_ANSWER,
    WORKFLOW_CLARIFICATION,
    route_is_read_only,
)
from core.control_engine import (
    authoring_context_for_control_result,
    build_control_prompt,
    build_control_prompt_human,
    control_has_grounded_patch_candidate,
    enforce_control_grounding_on_payload,
    localization_value,
    payload_is_eligible_for_patch_safety_handoff,
    refresh_control_safety,
)
from core.defect_probe import (
    derive_control_defect_probe_contract,
    reproduced_probe_target,
    resolve_control_defect_probe,
)
from core.candidate_defect_probe import (
    candidate_defect_closure_is_current,
    evaluate_candidate_defect_closure,
)
from core.paired_defect_probe import evaluate_paired_defect_closure
from core.behavioral_matrix import evaluate_behavioral_closure
from core.check_oracle_assessment import (
    assess_selected_check_oracles,
    describe_check_oracle_assessment,
)
from core.candidate_mutation_effect import (
    describe_candidate_mutation_effect,
    evaluate_candidate_mutation_effect,
    payload_rejected_as_exact_no_op,
    reject_exact_no_op_candidate,
)
from core.candidate_revision import (
    MAX_REVISION_CALLS_PER_RUN,
    OUTCOME_REVISED_CANDIDATE_PRODUCED,
    OUTCOME_REVISED_CANDIDATE_REJECTED,
    OUTCOME_REVISED_CANDIDATE_VERIFIED,
    OUTCOME_REVISION_OUTPUT_INVALID,
    OUTCOME_REVISION_UNAVAILABLE,
    CandidateRevisionReceipt,
    assess_candidate_revision,
    describe_candidate_revision,
    not_eligible_receipt,
    parse_revised_candidate,
    revision_evidence_is_current,
)
from core.candidate_presentation import (
    GENERATION_INITIAL,
    GENERATION_REVISION,
    CandidateAuthoredFields,
    bind_final_candidate_presentation,
    capture_candidate_authored_fields,
    describe_candidate_presentation,
    install_candidate_presentation,
    superseded_candidate_history,
)
from core.candidate_verification import (
    candidate_verification_is_current,
    describe_candidate_verification,
    evaluate_candidate_verification,
    verification_profile_for_basis,
)
from core.candidate_sandbox_validation import (
    CANDIDATE_VALIDATION_INCONCLUSIVE,
    CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED,
    SANDBOX_APPLY_NOT_ATTEMPTED,
    CandidateSandboxValidation,
    candidate_fingerprint_from_payload,
    candidate_plan_from_payload,
    candidate_validation_is_current,
    describe_candidate_validation,
    validate_candidate_in_sandbox,
)
from core.execution_outcome_telemetry import (
    AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
    AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE,
    DENIED_AUTO_PATCH_DISABLED,
    DENIED_AUTO_PATCH_POLICY_DECLINED,
    DENIED_CANDIDATE_REJECTED,
    DENIED_HUMAN_APPROVAL_REQUIRED,
    DENIED_MISSING_SOURCE_SNIPPET,
    DENIED_NEEDS_ESCALATION,
    DENIED_NO_CHANGE_REQUESTED,
    DENIED_NO_PATCH_BASIS_HANDOFF,
    DENIED_PATCH_BASIS_NOT_ACCEPTED,
    DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD,
    DENIED_PATCH_SAFETY_BLOCKED,
    DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE,
    DENIED_TIME_BUDGET_EXCEEDED,
    attach_execution_telemetry,
    authorized_execution,
    final_state_observation,
    no_execution,
    observe_named_paths,
    plan_execution_receipt,
    plan_pre_mutation_refusal,
    single_file_execution_receipt,
    single_file_pre_mutation_refusal,
)
from core.execution_eligibility_policy import (
    PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
    describe_execution_eligibility,
    evaluate_execution_eligibility,
)
from core.human_apply_authorization import (
    PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
    build_human_apply_review_receipt,
)
from core.executor import Executor, ExecutionResult
from core.json_utils import extract_json_block
from core.patch_basis import (
    PATCH_BASIS_EXPLICIT_CHANGE_REQUEST,
    PATCH_BASIS_GROUNDED_DEFECT,
    normalize_patch_basis,
)
from core.project_tag import build_project_tag
from core.pre_execution_change_intent import (
    intent_emission_directive,
    is_pre_execution_change_intent_enabled,
    safe_capture_pre_execution_change_intent,
)
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
from core.patch_safety import evaluate_patch_safety
from core.security import is_safe_path
from core.self_correct_loop import run_self_correct_loop
from core.strict_envelope_emission import (
    PROVIDER_GOOGLE,
    apply_strict_emission_to_prompt,
    is_strict_envelope_emission_enabled,
    patch_plan_is_the_declared_shape,
    safe_observe_strict_envelope_emission,
    strict_emission_client_kwargs,
    strict_emission_directive,
)
from core.targeted_repository_validation import (
    CATEGORY_TARGETED_VALIDATION_UNAVAILABLE,
    build_targeted_validation_request,
    describe_targeted_validation,
    targeted_validation_is_current,
    validate_targeted_candidate,
)
from core.worker_patch_envelope import (
    is_strict_worker_patch_envelope_shadow_enabled,
    safe_compare_strict_and_legacy,
)
from core.validation_command import (
    extract_user_validation_command,
    get_default_validation_command,
)
from core.validation_outcome import (
    is_compiler_grounded_category,
    is_executed_failure_evidence,
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


def _analysis_evidence_for_state(state: AgentState) -> AnalysisEvidence:
    """Acquire the read-only route's bounded document evidence exactly once."""
    evidence = state.analysis_evidence
    if isinstance(evidence, AnalysisEvidence):
        return evidence
    route = state.live_route or {}
    evidence = collect_analysis_evidence(
        state.repo_path,
        requested_paths=[str(item) for item in route.get("requested_paths") or []],
        subjects=[str(item) for item in route.get("subjects") or []],
        # ANALYSIS.EVIDENCE.LIVE.1 — the preserved obligations decide the
        # evidence profile.  Read off the route that was already computed.
        obligations=[str(item) for item in route.get("obligations") or []],
        # ANALYSIS.MULTIROOT.LIVE.1 — a second repository is readable only on the
        # analysis workflow, and only when the user explicitly named it.
        analysis_only=route.get("selected_workflow") == WORKFLOW_ANALYSIS_ANSWER,
    )
    state.analysis_evidence = evidence
    return evidence


def _analysis_context_for_human(state: AgentState) -> str:
    """Fold the acquired documents into the human modes' retrieved context."""
    from core.analysis_evidence import render_analysis_evidence_block

    evidence = _analysis_evidence_for_state(state)
    block = render_analysis_evidence_block(evidence)
    oop_review = _oop_review_block_for_state(state, evidence)
    if oop_review:
        block += "\n\n" + oop_review
    existing = state.context_data or ""
    return f"{existing}\n\n{block}".strip() if existing else block


def _oop_review_block_for_state(state: AgentState, evidence: AnalysisEvidence) -> str:
    """Present a bounded 1C review from files this read-only route already read."""
    from core.input_understanding import understand_request
    from core.oop_semantic_review import (
        render_oop_semantic_review, review_acquired_java_evidence,
    )

    reviews = review_acquired_java_evidence(
        evidence=evidence, repository_root=state.repo_path,
        task_contract=understand_request(state.user_input))
    return "\n\n".join(render_oop_semantic_review(item) for item in reviews)


def build_analysis_prompt_for_state(state: AgentState) -> str:
    """Build the answer prompt for a read-only route, acquiring evidence once.

    WAITER.LIVE.1.  This is the road an architecture question takes instead of
    the patch road: bounded document evidence, a natural-language answer, and no
    replacement snippet anywhere in sight.
    """
    evidence = _analysis_evidence_for_state(state)
    route = state.live_route or {}
    prompt = build_analysis_answer_prompt(
        user_query=state.user_input,
        evidence=evidence,
        obligations=route.get("obligations") or (),
        repo_path=state.repo_path,
        memory_block=state.memory_block,
        history_block=state.history_block,
        clarification=route.get("selected_workflow") == WORKFLOW_CLARIFICATION,
    )
    # CTX.OOP.1C consumes only Java files already selected by the read-only
    # analysis route. Its typed review is computed before the existing answer
    # call; a patch candidate and an additional model call are unnecessary.
    oop_review = _oop_review_block_for_state(state, evidence)
    if oop_review:
        prompt += "\n\n" + oop_review
        prompt += ("\nPreserve the separation between structural facts, possible semantic "
                   "concerns, and questions only the user can settle. "
                   "Present only the observations in this typed review. "
                   "Do not call a semantic observation a proven defect or propose a patch.")
    return prompt


def run_draft_pipeline(state: AgentState) -> str:
    refresh_memory_block(state)

    # WAITER.LIVE.1 — a read-only order answers from repository evidence.  It
    # never reaches the CONTROL patch prompt, and CONTROL was never run for it.
    # The prompt changes; the single model call below does not.
    analysis_route = state.is_project_input and route_is_read_only(state.live_route)
    analysis_prompt = ""
    if analysis_route:
        if state.interface == "agent":
            print(
                "🧭 WAITER: analysis route — answering from bounded repository evidence"
            )
            analysis_prompt = build_analysis_prompt_for_state(state)
        else:
            # Human tutor/explainer modes keep their own teaching prompt; the
            # acquired documents simply become their retrieved context.
            state.context_data = _analysis_context_for_human(state)

    if analysis_prompt:
        prompt = analysis_prompt
    elif state.is_project_input and state.control_result:
        state.control_result["patch_style"] = state.task_info.get(
            "patch_style",
            "safe_minimal"
        )
        state.control_result["code_dna_mode"] = (
            "ignore" if state.task_info.get("ignore_repo_dna") else "match"
        )

        if state.interface == "agent":
            state.candidate_authoring_context = authoring_context_for_control_result(
                state.control_result, repo_path=state.repo_path,
            )
            prompt = build_control_prompt(
                control_result=state.control_result,
                user_query=state.user_input,
                repo_path=state.repo_path,
                authoring_context=state.candidate_authoring_context,
            )
            if (state.control_result.get("repair_scope") or {}).get("status") == "complete":
                from core.repair_intent import author_escalation_directive
                prompt += "\n\n" + author_escalation_directive(state.control_result["repair_scope"])
            if state.control_result.get("repair_scope"):
                state.candidate_authoring_context = authoring_context_for_control_result(
                    state.control_result, repo_path=state.repo_path,
                )
            # WORKER.DECL.2A.1: ask this one already-scheduled draft call for
            # the strict one-object envelope, but only where the existing patch
            # policy already declares a patch_plan as the shape it wants.  Under
            # safe_minimal a plan is forbidden and under balanced a
            # patch_candidate is preferred, so those styles keep the legacy
            # request untouched and are recorded as `legacy_prompt`.
            state.strict_envelope_transport = strict_emission_directive(
                PROVIDER_GOOGLE,
                patch_plan_is_declared_shape=patch_plan_is_the_declared_shape(
                    state.control_result.get("patch_style")
                ),
            )
            state.strict_envelope_transport = intent_emission_directive(
                state.strict_envelope_transport
            )
            prompt = apply_strict_emission_to_prompt(
                prompt, state.strict_envelope_transport
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
    response = run_gemini_request(
        prompt,
        state.file_paths if state.file_paths else None,
        **strict_emission_client_kwargs(state.strict_envelope_transport),
    )

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
    # WORKER.DECL.2A.1: `refined` replaces the draft, so the response
    # `finalize_answer` measures came from *this* call — which was never asked
    # for the strict envelope. Drop the draft's transport label rather than
    # crediting the refine response to an experiment it did not run under.
    state.strict_envelope_transport = None
    return refined


def run_review_pipeline(state: AgentState, current_answer: str) -> str:
    # WAITER.LIVE.1 — the review/refine loop is patch-oriented: it critiques a
    # candidate and rewrites it.  A read-only answer has no candidate, so the
    # loop can only pull the answer towards a patch nobody asked for.  Skipping
    # it also removes model calls from this route rather than adding any.
    if route_is_read_only(state.live_route):
        return current_answer

    # An unresolved author escalation is terminal for candidate review.  The
    # deterministic admission in finalize_answer will quarantine its bytes.
    drafted = extract_json_block(current_answer)
    if isinstance(drafted, dict) and not admit_author_escalation(drafted).admitted:
        return current_answer

    if control_missing_source_snippet(state):
        print("🛑 CONTROL source_snippet missing → skipping review/refine to avoid hallucinated patch")
        return current_answer

    preflight = {}
    if state.control_result:
        preflight = state.control_result.get("preflight_validation") or {}

    # OPS.VALIDATE.1 — only a failure a runner actually observed in the code
    # may skip the review pass.  A missing toolchain, an absent test runner or a
    # suite that collected nothing establishes no defect, so it must not buy the
    # patch the trust that genuine compiler/test evidence buys.
    if (
        state.is_project_input
        and preflight.get("ran")
        and preflight.get("ok") is False
        and is_executed_failure_evidence(preflight.get("category"))
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

    if res_json.get("blocked") is True or res_json.get("status") == "blocked":
        res_json["status"] = "blocked"
        res_json["summary"] = str(
            res_json.get("blocker_reason") or "The author reported a blocked subtask."
        )
        return attach_execution_telemetry(res_json, no_execution(DENIED_NEEDS_ESCALATION))

    if subtask.get("action") == "edit" and res_json.get("patch_candidate"):
        # Planner steps run before maybe_run_auto_patch. Enforce the same
        # mutation switch and read-only route at this actual write boundary;
        # a generated plan or candidate does not override either restriction.
        denied_reason = ""
        if not AUTO_PATCH_ENABLED:
            denied_reason = DENIED_AUTO_PATCH_DISABLED
            refusal = "Automatic patching is disabled (AUTO_PATCH_ENABLED=false)."
        elif not state.live_route or route_is_read_only(state.live_route):
            denied_reason = DENIED_NO_CHANGE_REQUESTED
            refusal = "The task has no change-authorizing route."
        elif res_json.get("needs_escalation") is True:
            denied_reason = DENIED_NEEDS_ESCALATION
            refusal = "The author requested escalation."
        if denied_reason:
            res_json.update(
                status="blocked", blocked=True, blocker_reason=denied_reason,
                summary=f"{refusal} The proposed edit was not applied; dependent steps are paused.",
                approval_ready=False, needs_escalation=True,
            )
            return attach_execution_telemetry(res_json, no_execution(denied_reason))

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
                **patch_res.rollback_payload_fields(),
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

        if result.get("status") == "blocked":
            print(f"⏸️ Plan paused: {result.get('summary')}")
            break

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

    if any(s.get("status") == "blocked" for s in state.completed_subtasks):
        # Preserve the proposal even without DB persistence. Keep it scoped to
        # its subtask; it is not a top-level executable/approved patch payload.
        return json.dumps({
            "goal": state.mission_goal,
            "status": "blocked",
            "summary": "\n".join(summary_lines),
            "subtasks": state.completed_subtasks,
            "remaining_subtasks": remaining_plan,
            "confidence": 0.0,
            "needs_escalation": True,
        }, ensure_ascii=False, indent=2)

    return "\n".join(summary_lines)


def _safe_minimal_authoritative_binding_inputs(
    state: AgentState,
) -> tuple[AuthoritativeBindingContext | None, str]:
    """Resolve one CONTROL-bound baseline for the candidate gate.

    No target discovery happens here.  The candidate must name the exact file
    and function CONTROL already localized; otherwise safe_minimal receives no
    context and retains its legacy conservative behavior.
    """

    block = state.json_block
    candidate = block.get("patch_candidate") if isinstance(block, dict) else None
    if not isinstance(candidate, dict) or not state.repo_path:
        return None, ""
    control = state.control_result or {}
    intent = control.get("patch_intent") or {}
    source_path = str(
        intent.get("relative_path")
        or intent.get("file")
        or intent.get("target_file")
        or ""
    ).replace("\\", "/")
    target_symbol = str(
        intent.get("target_symbol")
        or str(intent.get("target_symbol_full") or "").rsplit("::", 1)[-1]
        or ""
    ).strip()
    candidate_path = str(
        candidate.get("relative_path") or candidate.get("file") or ""
    ).replace("\\", "/")
    candidate_symbol = str(
        candidate.get("target_node_name") or candidate.get("target_symbol") or ""
    ).strip()
    if (
        not source_path
        or not target_symbol
        or candidate_path != source_path
        or candidate_symbol != target_symbol
        or str(candidate.get("target_node_kind") or "").strip().lower()
        != "function"
    ):
        return None, ""
    authoring = state.candidate_authoring_context
    if authoring is None:
        authoring = authoring_context_for_control_result(control, repo_path=state.repo_path)
        state.candidate_authoring_context = authoring
    if (authoring.source_path != source_path or authoring.target_symbol != target_symbol
            or authoring.source_snippet != str(intent.get("source_snippet") or "")):
        return None, ""
    return authoring.binding_inputs(state.repo_path)


def _enforce_measured_authoring_scope(state: AgentState) -> None:
    from core.authoring_repair_scope import AuthoringScopeError, enforce_authoring_scope

    if not isinstance(state.json_block, dict):
        return
    authoring = state.candidate_authoring_context
    try:
        if authoring is None and (state.control_result or {}).get("repair_scope"):
            authoring = authoring_context_for_control_result(state.control_result, repo_path=state.repo_path)
            state.candidate_authoring_context = authoring
        if authoring is not None:
            if authoring.authoring_repair_scope is not None:
                authoring.authoring_repair_scope.assert_current(
                    (state.control_result or {}).get("preflight_validation") or {})
            enforce_authoring_scope(authoring, state.json_block)
    except AuthoringScopeError as exc:
        state.json_block.update(patch_candidate=None, patch_plan=None, needs_escalation=True,
                                authoring_scope_status=exc.reason)


def finalize_answer(state: AgentState, answer: str) -> None:
    from core.session_io import strip_json_from_text  # avoid circular import

    state.final_answer = answer
    state.json_block = extract_json_block(answer)
    # ANSWER.COHERENCE.LIVE.1 — what this authoring response said about its
    # own candidate, recorded before any gate below can narrow the payload.
    # A revision replaces the candidate and this record together.
    state.candidate_presentation = capture_candidate_authored_fields(
        state.json_block, generation=GENERATION_INITIAL
    )
    state.human_answer = strip_json_from_text(answer)

    # WORKER.DECL.2A: one response, two parsers.  The legacy payload above is
    # and stays authoritative; this only records what a strict one-object
    # envelope parser would have made of the same text.  Default off.
    emission_enabled = is_strict_envelope_emission_enabled()
    intent_enabled = is_pre_execution_change_intent_enabled()
    if is_strict_worker_patch_envelope_shadow_enabled() or emission_enabled:
        state.worker_patch_response = safe_compare_strict_and_legacy(
            answer, state.json_block
        )

    # WORKER.DECL.2A.1: label that measurement with the transport strategy the
    # draft call was asked for.  Adoption telemetry only — nothing below reads
    # it, and the legacy `state.json_block` above stays the applied payload.
    if emission_enabled:
        state.strict_envelope_emission = safe_observe_strict_envelope_emission(
            state.strict_envelope_transport, state.worker_patch_response
        )
    if intent_enabled:
        state.pre_execution_intent_capture = (
            safe_capture_pre_execution_change_intent(
                answer, state.strict_envelope_transport
            )
        )

    if state.json_block and not state.human_answer:
        state.human_answer = json.dumps(state.json_block, ensure_ascii=False, indent=2)

    # REPAIR.INTENT.ADMIT.1: an author-requested escalation is terminal for
    # candidate admission.  Preserve its raw output in a separate receipt;
    # neither span/scope nor PATCH.MINIMAL may see it as an active candidate.
    if isinstance(state.json_block, dict):
        admission = admit_author_escalation(state.json_block, raw_response=answer)
        if not admission.admitted:
            state.json_block.update(
                patch_candidate=None, patch_plan=None,
                author_escalation_status=admission.status,
                author_escalation_reason=admission.reason,
                author_escalation_receipt=admission.quarantine_receipt(),
                write_authority=False, execution_authorized=False,
                human_review_eligible=False, approval_ready=False,
            )
            state.candidate_presentation = None
            return

    reject_schema_drift(state)
    _enforce_measured_authoring_scope(state)
    # PATCH.MINIMAL.LIVE.1 §6/§8 — the exact mutation-effect check sits ahead of
    # the candidate-shape preflight, because a candidate that changes zero bytes
    # is not a patch whose shape is worth judging.  The two reasons stay
    # separate: this one is "no effect", ``safe_minimal``'s is "unsafe or
    # non-minimal", and the Round-7 candidate was structurally minimal.
    _record_candidate_mutation_effect(state)
    binding_context, authoritative_source = (
        _safe_minimal_authoritative_binding_inputs(state)
    )
    _enforce_safe_minimal(
        state,
        authoritative_binding_context=binding_context,
        authoritative_source=authoritative_source,
    )

    if state.candidate_authoring_context is not None and isinstance(state.json_block, dict):
        state.json_block.update(state.candidate_authoring_context.as_telemetry())

_FUNCTION_KEYWORD_PREFIXES = (
    "func ",
    "pub fn ", "pub(crate) fn ", "pub async fn ", "async fn ", "fn ",
    "def ", "async def ",
    "function ", "async function ",
    "export function ", "export async function ",
    "export default function ", "export default async function ",
)


def _first_nonblank_line(text: str) -> str:
    return next((ln for ln in text.splitlines() if ln.strip()), "")


def _looks_like_complete_function(snippet: str, target_node_name: str = "") -> bool:
    first_line = _first_nonblank_line(snippet).strip()
    if not first_line:
        return False
    if first_line.startswith(_FUNCTION_KEYWORD_PREFIXES):
        return True
    if target_node_name:
        return (
            re.search(rf"\b{re.escape(target_node_name)}\s*\(", first_line) is not None
            and "{" in snippet
        )
    return False


def _indent_of(line: str) -> str:
    return line[: len(line) - len(line.lstrip(" \t"))]


def _apply_indent_if_needed(lines: list[str], indent: str) -> list[str]:
    first = next((ln for ln in lines if ln.strip()), "")
    if not first or first.startswith((" ", "\t")):
        return lines
    return [(indent + ln if ln.strip() else ln) for ln in lines]


def _graft_statement_level_patch_into_function(target: str, patched: str) -> str | None:
    """Turn a model's statement-level replacement into a whole-function patch.

    This handles the common reviewer-output shape where target_snippet is the
    entire function, but patched_snippet contains only the corrected trailing
    return statement. The executor should still receive a whole-function patch.
    """
    patched_lines = patched.splitlines()
    patched_nonblank = [ln for ln in patched_lines if ln.strip()]
    if not patched_nonblank:
        return None

    # If the patch already has braces or a declaration, it is not a simple
    # statement-level replacement; leave it for the normal executor gates.
    if _looks_like_complete_function(patched) or any(ln.strip() == "}" for ln in patched_lines):
        return None

    target_lines = target.splitlines()
    if not target_lines:
        return None

    search_end = len(target_lines)
    for i in range(len(target_lines) - 1, -1, -1):
        if target_lines[i].strip() == "}":
            search_end = i
            break

    statement_idx = None
    for i in range(search_end - 1, -1, -1):
        stripped = target_lines[i].strip()
        if stripped.startswith("return ") or stripped == "return;":
            statement_idx = i
            break
    if statement_idx is None:
        return None

    start_idx = statement_idx
    comment_prefixes = ("//", "#")
    if (
        patched_nonblank[0].lstrip().startswith(comment_prefixes)
        and statement_idx > 0
        and target_lines[statement_idx - 1].strip().startswith(comment_prefixes)
    ):
        start_idx = statement_idx - 1

    indent = _indent_of(target_lines[start_idx] or target_lines[statement_idx])
    final_patch_lines = _apply_indent_if_needed(patched_lines, indent)
    merged = target_lines[:start_idx] + final_patch_lines + target_lines[statement_idx + 1 :]
    return "\n".join(merged)


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
    target_node_name = patch.get("target_node_name") or ""
    target_is_complete = _looks_like_complete_function(target, target_node_name)
    patched_is_complete = _looks_like_complete_function(patched, target_node_name)

    if target_is_complete and not patched_is_complete and (target == source or target in source):
        full_patched = _graft_statement_level_patch_into_function(target, patched)
        if full_patched:
            patch["patched_snippet"] = full_patched
            patch["__normalized_from_statement_level_patch"] = True
            print("🧩 Normalized statement-level function patch to full target_snippet")
        return

    if target_is_complete:
        return

    # C/C++/Java/C#-style: declaration is `<type/qualifiers> name(args) {`
    # with no anchor keyword. Treat as already-complete if the declared
    # `target_node_name` appears followed by `(` on the first non-blank
    # line and the snippet has an opening brace.
    if target_node_name:
        first_line = next((ln.strip() for ln in target.splitlines() if ln.strip()), "")
        if re.search(rf"\b{re.escape(target_node_name)}\s*\(", first_line) and "{" in target:
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

    if state.is_project_input and state.control_result:
        if not control_has_grounded_patch_candidate(state.control_result):
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

    control = refresh_control_safety(state.control_result or {})
    patch_intent = control.get("patch_intent") or {}
    grounded_file = (
        patch_intent.get("relative_path")
        or patch_intent.get("file")
        or patch_intent.get("target_file")
        or ""
    )
    return rel.replace("\\", "/") == str(grounded_file).replace("\\", "/")


def _patch_payload_target_files(block: dict | None) -> list[str]:
    if not isinstance(block, dict):
        return []
    targets: list[str] = []
    candidate = block.get("patch_candidate")
    if isinstance(candidate, dict):
        target = candidate.get("relative_path") or candidate.get("file") or ""
        if target:
            targets.append(str(target))
    plan = block.get("patch_plan")
    if isinstance(plan, list):
        for operation in plan:
            if not isinstance(operation, dict):
                continue
            target = operation.get("relative_path") or operation.get("file") or ""
            if target:
                targets.append(str(target))
    return targets


def _repository_relative_target(project_root: Path, target: Any) -> str:
    """Render one executor-reported target as a repository-relative path.

    The executor reports absolute paths; the bounded observer only accepts
    canonical repository-relative spellings.  A target outside the project root
    — or one that cannot be resolved at all — comes back empty, so it is
    dropped from the observation set rather than silently observed somewhere
    else.
    """

    if not target:
        return ""
    try:
        return Path(str(target)).resolve().relative_to(project_root.resolve()).as_posix()
    except (OSError, ValueError):
        return ""


def _record_no_execution(
    state: AgentState,
    denied_reason: str,
    *,
    human_approval_required_for_execution: bool = True,
) -> None:
    """EXEC.AUTH.LIVE.1 — record that no mutation was authorized or attempted.

    Called on every path out of :func:`maybe_run_auto_patch` that does not
    reach an executor, so the operator-visible payload states the absence of a
    write as a fact rather than leaving it to be inferred from the absence of a
    field.  It writes telemetry keys only: no gate is consulted, no decision is
    revisited, and removing this call changes nothing about what the run does.
    """

    attach_execution_telemetry(
        state.json_block,
        no_execution(
            denied_reason,
            human_approval_required_for_execution=(
                human_approval_required_for_execution
            ),
        ),
    )


def _record_authorized_execution(
    state: AgentState,
    *,
    authority_source: str,
    receipt: Any,
    before: Any,
    project_root: Path,
    observed_paths: list[str],
    pre_mutation_refusal: str = "",
) -> None:
    """EXEC.AUTH.LIVE.1 — record what an authorized execution actually did.

    The "after" window is taken here, at the terminal boundary: every apply,
    every rollback and the one validation have finished.  Both windows cover
    exactly the paths the operation named — the payload's own targets plus any
    target the executor itself reported — so this observes the operation, never
    the repository.

    ``pre_mutation_refusal`` is the one case that is *not* an outcome: the apply
    path's own safety gates run before it writes anything, and a refusal there
    means this mutation was never authorized, however willing the policy above
    it was.  §12 — the harmful test-edit candidate — is exactly that case.
    """

    if pre_mutation_refusal:
        _record_no_execution(state, pre_mutation_refusal)
        return

    after = observe_named_paths(project_root, observed_paths)
    attach_execution_telemetry(
        state.json_block,
        authorized_execution(
            authority_source=authority_source,
            receipt=receipt,
            observation=final_state_observation(before, after),
        ),
    )


def _record_human_apply_review(
    state: AgentState,
    *,
    project_root: Path,
    patch_safety: Mapping[str, Any],
    policy_profile: str,
) -> None:
    """Freeze the exact state the existing Apply action will later target."""

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return
    additional_paths: list[str] = []
    probe = (state.control_result or {}).get("defect_probe") or {}
    binding = probe.get("target_binding") if isinstance(probe, Mapping) else None
    if isinstance(binding, Mapping) and binding.get("file"):
        additional_paths.append(str(binding["file"]))
    try:
        receipt = build_human_apply_review_receipt(
            payload=block,
            repo_path=project_root,
            patch_safety_verdict=patch_safety,
            policy_profile=policy_profile,
            additional_source_paths=additional_paths,
        )
    except (OSError, TypeError, ValueError) as exc:
        # Eligibility remains what EXEC.POLICY established.  A review state that
        # cannot be frozen simply cannot authorize later; Apply will fail closed
        # rather than regenerating evidence here.
        block["human_apply_review_unavailable_reason"] = type(exc).__name__
        return
    telemetry = receipt.as_payload_fields()
    block.update(telemetry)
    state.patch_policy.update(telemetry)


def _record_patch_safety_handoff(
    state: AgentState,
    policy: Any,
    project_root: Path,
    validation_command: str | None = None,
) -> bool:
    """Run the existing path-safety review without acquiring write authority.

    This is the last point at which an explicit-change candidate is stable: the
    payload here is exactly what the human is handed for approval, and nothing
    downstream rewrites it.  OPS.PATCH.2 therefore validates *this* candidate —
    after patch safety, never before it, and never a draft an earlier refinement
    has already replaced.
    """

    targets = _patch_payload_target_files(state.json_block)
    patch_safety = evaluate_patch_safety(targets, project_root=project_root)
    handoff = {
        "patch_basis": policy.patch_basis,
        "patch_basis_accepted": policy.patch_basis_accepted,
        "target_source_grounded": bool(
            (state.json_block or {}).get("target_source_grounded")
        ),
        "patch_safety": patch_safety,
        "auto_apply_allowed": policy.auto_apply_allowed,
        "human_approval_required": policy.human_approval_required,
        "write_authority": False,
        "patch_application_authority": False,
    }
    state.patch_policy = handoff
    if isinstance(state.json_block, dict):
        state.json_block.update(handoff)
        state.json_block["patch_safety_passed"] = bool(patch_safety.get("ok"))
        if not patch_safety.get("ok"):
            state.json_block["eligible_for_patch_safety_handoff"] = False
            state.json_block["patch_safety_blocked"] = True
            state.json_block["needs_escalation"] = True
    # EXEC.AUTH.LIVE.1 — this whole function is the *no execution authority*
    # branch: it is reached only when ``auto_apply_allowed`` is false, and its
    # product is a candidate for a human to read.  Sandbox validation below may
    # change how good that candidate looks; it never changes this fact (§29).
    _record_no_execution(
        state,
        (
            DENIED_PATCH_SAFETY_BLOCKED
            if not patch_safety.get("ok")
            else DENIED_HUMAN_APPROVAL_REQUIRED
        ),
    )
    if not patch_safety.get("ok"):
        # OPS.PATCH.2 §26: a candidate the safety gate rejected is never
        # materialized "just to see what happens" — safety denial stays denial,
        # and a denied candidate is not approval-ready either.
        _record_no_candidate_validation(
            state,
            approval_ready=False,
            reason=(
                "Candidate validation was not attempted: existing patch safety "
                "blocked the candidate before any sandbox materialization."
            ),
        )
        _record_execution_eligibility(
            state,
            policy,
            patch_safety=patch_safety,
        )
        state.auto_patch_result = "Patch authored, but blocked by existing patch safety."
        print(
            "🛑 Patch basis accepted, but existing patch safety blocks review/apply: "
            + "; ".join(patch_safety.get("reasons") or [])
        )
        return False

    # DEFECT.PROBE.LIVE.2 supplies an immutable post-candidate observation for
    # the bounded large-repository route, and DEFECT.PROBE.LIVE.3 pairs it with
    # whatever deterministic behavior-preservation counter-case the typed fact
    # supports.  It remains an evidence producer; EXEC.POLICY.LIVE.1 below only
    # consumes the resulting receipt.
    _record_candidate_defect_closure(
        state,
        policy,
        project_root,
        patch_safety=patch_safety,
    )

    # OPS.VALIDATE.3 is evidence only.  It runs after the existing safety gate
    # and its result is deliberately ignored by this function's authority and
    # handoff decisions.  In particular, a pass cannot turn this no-authority
    # branch into an execution branch.
    _record_targeted_repository_validation(
        state,
        policy,
        project_root,
        patch_safety=patch_safety,
    )

    # EXEC.POLICY.LIVE.1 reduces the existing facts after oracle-role
    # classification.  It does not feed any execution branch and cannot change
    # the no-authorization receipt recorded above.
    _record_execution_eligibility(
        state,
        policy,
        patch_safety=patch_safety,
    )

    validated = _record_candidate_sandbox_validation(
        state,
        policy,
        project_root,
        validation_command=validation_command,
    )
    if validated is not None:
        if validated.passed:
            _record_human_apply_review(
                state,
                project_root=project_root,
                patch_safety=patch_safety,
                policy_profile=PROFILE_EXPLICIT_CHANGE_MANUAL_REVIEW,
            )
        return validated.passed

    if (state.json_block or {}).get("human_review_eligible") is True:
        _record_human_apply_review(
            state,
            project_root=project_root,
            patch_safety=patch_safety,
            policy_profile=PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW,
        )
        state.auto_patch_result = (
            "Eligible for human review; not applied. The exact candidate and "
            "evidence receipt are bound for the existing manual Apply action."
        )
    else:
        state.auto_patch_result = (
            "Patch authored and source-grounded; patch safety passed. "
            "Write authorization and human approval are still required."
        )
    print(
        "🧭 Legitimate patch basis and exact targets passed patch safety; "
        "automatic write is not authorized. Human approval is still required."
    )
    return True


#: Every key OPS.PATCH.2 writes onto a payload.  They are dropped together the
#: moment the candidate they describe stops being the candidate on the table.
_CANDIDATE_VALIDATION_KEYS: tuple[str, ...] = (
    "candidate_validation_status",
    "candidate_validation_category",
    "candidate_validation_command",
    "candidate_validation_fingerprint",
    "candidate_validation_inconclusive_reason",
    "candidate_validation_reviewable",
    "candidate_validation_output_excerpt",
    "candidate_validation_timings",
    "baseline_validation_status",
    "baseline_validation_category",
    "sandbox_apply_status",
    "sandbox_apply_error",
    "sandbox_failed_op_index",
    "approval_ready",
)

#: Candidate-bound OPS.VALIDATE.3 facts.  They become stale together, while the
#: independent full-validation and defect-probe receipts remain untouched.
_TARGETED_VALIDATION_KEYS: tuple[str, ...] = (
    "targeted_validation_status",
    "targeted_validation_category",
    "checks_selected",
    "checks_executed",
    "selected_check_count",
    "selected_checks",
    "selection_complete",
    "selection_reason",
    "selection_provenance",
    "baseline_targeted_outcome",
    "baseline_targeted_category",
    "baseline_concrete_cases",
    "candidate_concrete_cases",
    "targeted_oracle_source_unchanged",
    "baseline_checks_executed",
    "candidate_targeted_outcome",
    "candidate_targeted_category",
    "candidate_checks_executed",
    "targeted_validation_budget",
    "candidate_fingerprint",
    "targeted_check_set_fingerprint",
    "targeted_validation_reason",
    "targeted_validation_timings",
    "pre_patch_probe_result",
    "targeted_validation_sandbox_cleanup_ok",
    "baseline_python_bytecode_cache_isolated",
    "candidate_python_bytecode_cache_isolated",
    "targeted_validation_authority_effect",
    "targeted_validation_model_calls",
    "targeted_validation_network_calls",
    "targeted_validation_selection_traversals",
    "full_validation_outcome",
    "full_validation_category",
    "check_oracle_assessment_status",
    "check_oracle_assessment_reason",
    "check_oracle_assessments",
    "check_oracle_probe_fingerprint",
    "check_oracle_check_set_fingerprint",
    "check_oracle_candidate_fingerprint",
    "check_oracle_role_counts",
    "check_oracle_evidence_matrix",
    "check_oracle_timings",
    "check_oracle_authority_effect",
    "check_oracle_model_calls",
    "check_oracle_network_calls",
    "check_oracle_repository_traversals",
)

#: Candidate-bound DEFECT.PROBE.LIVE.2 facts.  Full validation, targeted
#: validation, the pre-patch reproduction receipt, patch basis and authority
#: are intentionally absent from this group.
_CANDIDATE_DEFECT_PROBE_KEYS: tuple[str, ...] = (
    "probe_fingerprint",
    "candidate_fingerprint",
    "pre_probe_result",
    "pre_probe_observed",
    "post_probe_result",
    "post_probe_observed",
    "expected_behavior_basis",
    "defect_closure_status",
    "defect_closure_reason",
    "sandbox_only",
    "candidate_probe_apply_status",
    "candidate_probe_sandbox_cleanup_ok",
    "candidate_probe_timings",
    "candidate_probe_authority_effect",
    # DEFECT.PROBE.LIVE.3 paired facts.  Same candidate binding, so they are
    # discarded on the same refinement rather than surviving next to a plan
    # they were never measured against.
    "paired_probe_phase_id",
    "paired_probe_schema_version",
    "paired_status",
    "primary_case",
    "preservation_oracle_status",
    "preservation_oracle_reason",
    "preservation_cases",
    "paired_probe_timings",
    "paired_probe_authority_effect",
    # DEFECT.PROBE.LIVE.4 matrix facts.  Same candidate binding again: the
    # matrix measured one exact candidate and goes stale with it.
    "behavioral_matrix_phase_id",
    "behavioral_matrix_schema_version",
    "behavioral_matrix_status",
    "behavioral_matrix_subject_kind",
    "behavioral_matrix_case_count",
    "behavioral_matrix_cases",
    "behavioral_matrix_rejection_reasons",
    "behavioral_matrix_timings",
    "behavioral_matrix_authority_effect",
    "behavioral_matrix",
)

# Candidate-bound EXEC.POLICY.LIVE.1 reduction.  It contains no independent
# evidence and is therefore discarded whenever the candidate it assessed is
# no longer current.
_EXECUTION_ELIGIBILITY_KEYS: tuple[str, ...] = (
    "execution_eligibility_phase_id",
    "execution_eligibility_schema_version",
    "execution_eligibility_profile",
    "execution_eligibility_status",
    "execution_eligibility_profiles",
    "human_review_eligible",
    "eligibility_requirements_satisfied",
    "eligibility_unsatisfied_requirements",
    "eligibility_blocking_reasons",
    "accepted_evidence_conflicts",
    "accepted_limitations",
    "execution_eligibility_candidate_fingerprint",
    "execution_eligibility_probe_fingerprint",
    "execution_eligibility_targeted_validation_fingerprint",
    "execution_eligibility_patch_safety_binding",
    "evidence_freshness",
    "execution_eligibility_authority_effect",
    "execution_eligibility_auto_apply_effect",
    "execution_eligibility_model_calls",
    "execution_eligibility_network_calls",
    "execution_eligibility_repository_traversals",
    "execution_eligibility_validation_calls",
    "execution_eligibility_retrieval_calls",
    "execution_eligibility_evaluation_seconds",
)


#: Candidate-bound CANDIDATE.VERIFY.LIVE.1 facts.  The receipt describes one
#: exact candidate, so it is discarded with the evidence it reduced rather than
#: surviving next to a candidate it never measured (§14).
_CANDIDATE_VERIFICATION_KEYS: tuple[str, ...] = (
    "candidate_verification_phase_id",
    "candidate_verification_schema_version",
    "candidate_verification_status",
    "candidate_verification_profile",
    "candidate_verification_candidate_fingerprint",
    "candidate_verification_sandbox_status",
    "candidate_verification_patch_safety_status",
    "candidate_verification_paired_probe_status",
    "candidate_verification_targeted_validation_status",
    "candidate_verification_oracle_status",
    "candidate_verification_components",
    "candidate_verification_rejection_reasons",
    "candidate_verification_accepted_limitations",
    "candidate_verification_probe_fingerprint",
    "candidate_verification_targeted_check_set_fingerprint",
    "candidate_verification_patch_safety_binding",
    "candidate_verification_receipt",
    "candidate_verification_fingerprint",
    "candidate_review_ready",
    "candidate_visible_for_debugging",
    "candidate_verification_needs_escalation",
    "candidate_verification_execution_authorized",
    "candidate_verification_final_repository_changed",
    "candidate_verification_authority_effect",
    "candidate_verification_auto_apply_effect",
    "candidate_verification_model_calls",
    "candidate_verification_network_calls",
    "candidate_verification_repository_mutations",
    "candidate_verification_timings",
    "candidate_verification_mutation_enabled",
)


#: Candidate-bound PATCH.MINIMAL.LIVE.1 facts.  They describe one exact
#: candidate's mutation effect and go stale with it, like every other
#: candidate-bound receipt above.
_CANDIDATE_EFFECT_KEYS: tuple[str, ...] = (
    "candidate_effect_phase_id",
    "candidate_effect_schema_version",
    "candidate_effect_status",
    "candidate_effect_rejection_reason",
    "candidate_effect_candidate_fingerprint",
    "candidate_effect_authored",
    "candidate_effect_accepted",
    "candidate_effect_operations",
    "candidate_effect_receipt",
    "candidate_effect_fingerprint",
    "candidate_effect_evaluation_seconds",
    "candidate_effect_model_calls",
    "candidate_effect_network_calls",
    "candidate_effect_repository_reads",
    "candidate_effect_repository_mutations",
    "candidate_effect_rejected_candidate",
    "exact_no_op_operation_count",
    "mutating_operation_count",
    "undetermined_operation_count",
)

#: Candidate-bound PATCH.MINIMAL.LIVE.2 facts.  ``safe_minimal`` writes them
#: when it classifies one exact candidate's identifier delta, so they describe
#: that candidate's bytes and no other.
_CANDIDATE_NOVELTY_KEYS: tuple[str, ...] = (
    "candidate_novelty_phase_id",
    "candidate_novelty_schema_version",
    "candidate_novelty_language",
    "candidate_novelty_language_supported",
    "candidate_novelty_candidate_shape",
    "candidate_novelty_containing_functions",
    "candidate_novelty_classification",
    "candidate_novelty_local_binding_names",
    "candidate_novelty_local_binding_count",
    "candidate_novelty_findings",
    "candidate_novelty_caps",
    "candidate_novelty_novel_identifiers",
    "candidate_novelty_unexplained_identifiers",
    "candidate_novelty_admitted",
    "candidate_novelty_reason",
    "candidate_novelty_blocking_reasons",
    "candidate_novelty_receipt",
    "candidate_novelty_fingerprint",
    "candidate_novelty_candidate_fingerprint",
    "candidate_novelty_classification_seconds",
    "candidate_novelty_model_calls",
    "candidate_novelty_network_calls",
    "candidate_novelty_repository_reads",
    "candidate_novelty_repository_mutations",
    "bounded_local_novelty_allowed",
    "authoritative_binding_context_phase_id",
    "authoritative_binding_context_schema_version",
    "authoritative_binding_context_current",
    "authoritative_binding_context",
    "authoritative_binding_context_construction_seconds",
    "authoritative_binding_context_model_calls",
    "authoritative_binding_context_network_calls",
    "authoritative_binding_context_repository_traversals",
    "authoritative_binding_context_repository_mutations",
    "authoritative_binding_context_reused_names",
    "immutable_result_return_type_proof_seconds",
    "immutable_result_field_lookup_seconds",
)


#: Run-bound PATCH.AUTHOR.LIVE.1 facts.  Unlike every group above these do NOT
#: go stale with the candidate: the receipt records that the single revision
#: opportunity was spent and on which prior candidate, and that record has to
#: outlive the candidate it replaced, or the budget stops being auditable.
_CANDIDATE_REVISION_KEYS: tuple[str, ...] = (
    "candidate_revision_phase_id",
    "candidate_revision_schema_version",
    "candidate_revision_eligible",
    "candidate_revision_attempted",
    "candidate_revision_trigger",
    "candidate_revision_attempt_count",
    "candidate_revision_outcome",
    "candidate_revision_ineligible_reasons",
    "candidate_revision_previous_candidate_fingerprint",
    "candidate_revision_revised_candidate_fingerprint",
    "candidate_revision_evidence_fingerprint",
    "candidate_revision_counterexample_count",
    "candidate_revision_preserved_case_count",
    "candidate_revision_output_rejection_reason",
    "candidate_revision_provider",
    "candidate_revision_model",
    "candidate_revision_author_selection",
    "candidate_revision_latency_seconds",
    "candidate_revision_evidence_seconds",
    "candidate_revision_input_chars",
    "candidate_revision_output_chars",
    "candidate_revision_present",
    "candidate_revision_model_calls",
    "candidate_revision_model_call_budget_consumed",
    "candidate_revision_model_call_budget_remaining",
    "candidate_revision_network_calls",
    "candidate_revision_retrieval_calls",
    "candidate_revision_repository_traversals",
    "candidate_revision_repository_mutations",
    "candidate_revision_reviewer_calls",
    "candidate_revision_authority_effect",
    "candidate_revision_receipt",
    "candidate_revision_previous_candidate",
)

#: ANSWER.COHERENCE.LIVE.1 — which candidate the final answer presents, and
#: whether every author-facing field was bound to it.  Written once the
#: candidate lifecycle is terminal; it names one exact candidate and goes
#: stale with it, like every candidate-bound receipt above.
_CANDIDATE_PRESENTATION_KEYS: tuple[str, ...] = (
    "candidate_presentation_phase_id",
    "candidate_presentation_schema_version",
    "final_candidate_fingerprint",
    "final_candidate_generation",
    "candidate_presentation_coherent",
    "candidate_presentation_authored_fields",
    "candidate_presentation_model_confidence",
    "candidate_presentation_model_needs_escalation",
    "candidate_presentation_incoherence_reasons",
)


def _record_candidate_mutation_effect(state: AgentState) -> Any | None:
    """PATCH.MINIMAL.LIVE.1 — the exact mutation-effect gate.

    One byte comparison over the bounded target/replacement representation the
    candidate pipeline already holds.  Nothing is re-read from the repository,
    and the check is cheap enough that Round 7's ~3.65 s candidate sandbox plus
    ~4.29 s paired probe on a candidate that changed nothing become zero.

    A candidate with any real mutation effect leaves here untouched and
    continues into the existing minimality, safety and verification semantics.
    An exact no-op is rejected here and never reaches them, because there is
    nothing for them to measure.
    """

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return None

    plan = candidate_plan_from_payload(block)
    if not plan:
        # §9 — a rejection recorded earlier in this run is not overwritten with
        # "not_applicable" by the very absence it created, and a payload that
        # never carried a candidate is not annotated with a measurement of
        # nothing.  A refinement that authors a *new* candidate re-enters the
        # branch below and is measured again on its own bytes.
        return None

    effect = evaluate_candidate_mutation_effect(
        plan, candidate_fingerprint=candidate_fingerprint_from_payload(block)
    )
    if not reject_exact_no_op_candidate(block, effect):
        # Mutating or undetermined: record the measurement and change nothing.
        telemetry = effect.as_telemetry()
        block.update(telemetry)
        if isinstance(state.patch_policy, dict):
            state.patch_policy.update(telemetry)
        return effect

    if isinstance(state.patch_policy, dict):
        state.patch_policy.update(effect.as_telemetry())
    message = describe_candidate_mutation_effect(effect)
    state.auto_patch_result = message
    state.final_answer = json.dumps(block, ensure_ascii=False, indent=2)
    state.human_answer = state.final_answer
    print(f"🛡️ PATCH.MINIMAL: rejecting candidate — {effect.rejection_reason}")
    print(f"🧭 {message}")
    return effect


def _drop_stale_candidate_validation(state: AgentState) -> None:
    """Discard a validation result that no longer describes this candidate.

    OPS.PATCH.2 §21: a refinement that rewrites the plan invalidates the earlier
    result, and there is no path by which the old ``passed`` may be silently
    reused.  Dropping the keys — rather than leaving them next to a plan they do
    not match — means a reader who finds no candidate-validation metadata knows
    the current candidate has not been validated, instead of finding a verdict
    that belongs to a candidate nobody is being asked to approve.
    """

    block = state.json_block
    if not isinstance(block, dict):
        return
    if (
        "candidate_validation_status" in block
        and not candidate_validation_is_current(block)
    ):
        for key in _CANDIDATE_VALIDATION_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _CANDIDATE_VALIDATION_KEYS:
                state.patch_policy.pop(key, None)

    if (
        "defect_closure_status" in block
        and not candidate_defect_closure_is_current(
            block,
            candidate_plan_from_payload(block),
        )
    ):
        for key in _CANDIDATE_DEFECT_PROBE_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _CANDIDATE_DEFECT_PROBE_KEYS:
                state.patch_policy.pop(key, None)

    if (
        "targeted_validation_status" in block
        and not targeted_validation_is_current(
            block,
            candidate_plan_from_payload(block),
        )
    ):
        for key in _TARGETED_VALIDATION_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _TARGETED_VALIDATION_KEYS:
                state.patch_policy.pop(key, None)

    current_candidate = candidate_fingerprint_from_payload(block)
    recorded_effect_candidate = str(
        block.get("candidate_effect_candidate_fingerprint") or ""
    )
    if (
        recorded_effect_candidate
        and recorded_effect_candidate != current_candidate
        and not payload_rejected_as_exact_no_op(block)
    ):
        # PATCH.MINIMAL.LIVE.1 §12 — the effect receipt describes one exact
        # candidate's bytes.  A refinement takes it with the candidate it
        # measured.  A recorded *rejection* is exempt: it is the reason the
        # payload now carries no candidate at all, so dropping it here would
        # erase the only record of what happened.
        for key in _CANDIDATE_EFFECT_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _CANDIDATE_EFFECT_KEYS:
                state.patch_policy.pop(key, None)

    recorded_novelty_candidate = str(
        block.get("candidate_novelty_candidate_fingerprint") or ""
    )
    if (
        recorded_novelty_candidate
        and recorded_novelty_candidate != current_candidate
        and block.get("candidate_novelty_admitted") is not False
    ):
        # PATCH.MINIMAL.LIVE.2 — the novelty classification describes one
        # exact candidate's identifier delta, so a refined candidate takes it
        # with the bytes it measured.  A recorded *rejection* is exempt for the
        # same reason PATCH.MINIMAL.LIVE.1's is: it is the record of why the
        # payload now carries no candidate at all.
        for key in _CANDIDATE_NOVELTY_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _CANDIDATE_NOVELTY_KEYS:
                state.patch_policy.pop(key, None)

    if "candidate_verification_status" in block and not (
        candidate_verification_is_current(block, current_candidate)
    ):
        for key in _CANDIDATE_VERIFICATION_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _CANDIDATE_VERIFICATION_KEYS:
                state.patch_policy.pop(key, None)

    recorded_eligibility_candidate = str(
        block.get("execution_eligibility_candidate_fingerprint") or ""
    )
    if (
        recorded_eligibility_candidate
        and recorded_eligibility_candidate != current_candidate
    ):
        for key in _EXECUTION_ELIGIBILITY_KEYS:
            block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            for key in _EXECUTION_ELIGIBILITY_KEYS:
                state.patch_policy.pop(key, None)


def _record_candidate_defect_closure(
    state: AgentState,
    policy: Any,
    project_root: Path,
    *,
    patch_safety: Mapping[str, Any],
) -> Any | None:
    """DEFECT.PROBE.LIVE.2/.3/.4 narrow production evidence adapter.

    This records the exact-candidate paired probe fact and nothing else.  No
    execution-policy branch reads the result.

    The route, exact source and reproduced independent probe gate the sandbox.
    Whole-suite pass/fail/timeout does not replace this behavioral question. What
    runs inside it is now the defect case together with whatever deterministic
    preservation counter-cases the typed behavior fact supports.  A task whose
    subject has no preservation adapter records exactly what it recorded before.

    DEFECT.PROBE.LIVE.4 changed what runs inside that one sandbox again, and
    still not when.  A subject with a deterministic behavioral matrix is probed
    across every bounded case the matrix declares — the primary claim, its
    depth-variant generalization, and both preservation cases — and the matrix
    reduction is what the receipt reports.  A subject with no matrix reaches
    DEFECT.PROBE.LIVE.3 exactly as before.
    """

    if normalize_patch_basis(policy.patch_basis) != PATCH_BASIS_GROUNDED_DEFECT:
        return None
    if patch_safety.get("ok") is not True:
        return None
    control = state.control_result or {}
    route = state.live_route or control.get("live_route") or {}
    preflight = control.get("preflight_validation") or {}
    pre_probe = control.get("defect_probe") or {}
    if route.get("selected_workflow") != "defect_repair_patch":
        return None
    if reproduced_probe_target(pre_probe) is None:
        return None
    resolution = resolve_control_defect_probe(control)
    contract = resolution.contract
    if contract is None:
        return None
    plan = candidate_plan_from_payload(state.json_block)
    if not plan:
        return None

    try:
        result = evaluate_behavioral_closure(
            repo_path=project_root,
            candidate_plan=plan,
            probe_contract=contract,
            pre_probe_receipt=pre_probe,
            patch_safety=patch_safety,
            behavior_fact=resolution.behavior_fact,
            expected_candidate_fingerprint=candidate_fingerprint_from_payload(
                state.json_block
            ),
        )
        telemetry = result.as_telemetry()
        telemetry.pop("phase_id", None)
        telemetry.pop("schema_version", None)
    except Exception as exc:  # evidence unavailability cannot change authority
        return None

    state.patch_policy.update(telemetry)
    if isinstance(state.json_block, dict):
        state.json_block.update(telemetry)
    print(
        "🔬 DEFECT.PROBE.LIVE.2 candidate closure: "
        f"{result.closure.pre_probe_result} → {result.defect_closure_status}"
    )
    print(
        "🧪 DEFECT.PROBE.LIVE.3 paired oracle: "
        f"{result.paired_status} (preservation oracle "
        f"{result.preservation_oracle_status})"
    )
    matrix_status = getattr(result, "matrix_status", "")
    if matrix_status:
        print(
            "🧮 DEFECT.PROBE.LIVE.4 behavioral matrix: "
            f"{matrix_status} over {len(result.cases)} bounded cases"
        )
    print(
        "🧭 Defect closure evidence does not rewrite repository validation or "
        "execution authorization."
    )
    return result


def _record_no_candidate_validation(
    state: AgentState,
    *,
    approval_ready: bool,
    reason: str,
) -> None:
    """Say plainly that no candidate validation established anything.

    Absence of a result is never a pass, so the payload carries ``inconclusive``
    with its reason rather than leaving the key off and letting a reader assume
    the candidate had been checked.
    """

    telemetry = {
        "candidate_validation_status": CANDIDATE_VALIDATION_INCONCLUSIVE,
        "candidate_validation_category": CATEGORY_CANDIDATE_VALIDATION_NOT_ATTEMPTED,
        "candidate_validation_command": "",
        "candidate_validation_fingerprint": candidate_fingerprint_from_payload(
            state.json_block
        ),
        "candidate_validation_inconclusive_reason": reason,
        "candidate_validation_reviewable": True,
        "sandbox_apply_status": SANDBOX_APPLY_NOT_ATTEMPTED,
        "approval_ready": approval_ready,
    }
    state.patch_policy.update(telemetry)
    if isinstance(state.json_block, dict):
        state.json_block.update(telemetry)


def _record_targeted_repository_validation(
    state: AgentState,
    policy: Any,
    project_root: Path,
    *,
    patch_safety: Mapping[str, Any],
) -> Any | None:
    """OPS.VALIDATE.3 production trigger and telemetry adapter.

    The trigger is intentionally narrow: defect repair, a reproduced
    independently-oracled probe, an exact localized target, a safe exact
    candidate, and the already-loaded operation graph.  The result is recorded
    but never read to grant or widen execution authority in this phase.
    """

    if normalize_patch_basis(policy.patch_basis) != PATCH_BASIS_GROUNDED_DEFECT:
        return None
    if not patch_safety.get("ok"):
        return None
    control = state.control_result or {}
    route = state.live_route or control.get("live_route") or {}
    preflight = control.get("preflight_validation") or {}
    probe = control.get("defect_probe") or {}
    target = reproduced_probe_target(probe)
    if route.get("selected_workflow") != "defect_repair_patch":
        return None
    if target is None:
        return None

    plan = candidate_plan_from_payload(state.json_block)
    if not plan:
        return None
    target_file = str(target.get("file") or "")
    target_symbol = str(target.get("symbol") or "")
    target_full = f"{target_file}::{target_symbol}" if target_file and target_symbol else ""
    if not target_full:
        return None

    try:
        request = build_targeted_validation_request(
            repo_path=project_root,
            candidate_plan=plan,
            graph=state.repository_graph,
            changed_symbols=(target_full,),
            preserved_user_command=extract_user_validation_command(state.user_input),
        )
        result = validate_targeted_candidate(
            repo_path=project_root,
            candidate_plan=plan,
            request=request,
            pre_patch_probe_result=str(probe.get("probe_result") or ""),
        )
        telemetry = result.as_telemetry()
        telemetry.update(
            {
                # These copy the whole-suite facts; they do not replace the
                # authoritative preflight receipt or reinterpret its outcome.
                "full_validation_outcome": preflight.get("outcome"),
                "full_validation_category": preflight.get("category"),
            }
        )
    except Exception as exc:  # evidence failure must not change execution policy
        telemetry = {
            "targeted_validation_status": "inconclusive",
            "targeted_validation_category": CATEGORY_TARGETED_VALIDATION_UNAVAILABLE,
            "targeted_validation_reason": (
                "targeted validation infrastructure was unavailable: "
                f"{type(exc).__name__}"
            ),
            "candidate_fingerprint": candidate_fingerprint_from_payload(state.json_block),
            "checks_selected": [],
            "checks_executed": [],
            "selected_check_count": 0,
            "selected_checks": [],
            "selection_complete": False,
            "selection_reason": "targeted validation request could not be constructed",
            "selection_provenance": [],
            "baseline_targeted_outcome": "targeted_validation_not_run",
            "candidate_targeted_outcome": "targeted_validation_not_run",
            "pre_patch_probe_result": str(probe.get("probe_result") or ""),
            "full_validation_outcome": preflight.get("outcome"),
            "full_validation_category": preflight.get("category"),
            "targeted_validation_authority_effect": "none",
            "targeted_validation_model_calls": 0,
            "targeted_validation_network_calls": 0,
            "targeted_validation_selection_traversals": 0,
        }
        result = None

    oracle_receipt = None
    if result is not None:
        try:
            contract = derive_control_defect_probe_contract(control)
            if contract is not None:
                oracle_receipt = assess_selected_check_oracles(
                    repo_path=project_root,
                    probe_contract=contract,
                    targeted_validation=result,
                    defect_closure=(
                        state.json_block
                        if isinstance(state.json_block, Mapping)
                        else {}
                    ),
                    full_validation=preflight,
                )
                telemetry.update(oracle_receipt.as_telemetry())
        except Exception as exc:
            # Oracle-role evidence is additive.  Its unavailability must never
            # replace the targeted validation facts already recorded above.
            telemetry.update(
                {
                    "check_oracle_assessment_status": "unavailable",
                    "check_oracle_assessment_reason": (
                        "existing-check role classification was unavailable: "
                        f"{type(exc).__name__}"
                    ),
                    "check_oracle_assessments": [],
                    "check_oracle_authority_effect": "none",
                    "check_oracle_model_calls": 0,
                    "check_oracle_network_calls": 0,
                    "check_oracle_repository_traversals": 0,
                }
            )

    state.patch_policy.update(telemetry)
    if isinstance(state.json_block, dict):
        state.json_block.update(telemetry)
    if result is not None:
        print(
            "🧪 OPS.VALIDATE.3 targeted repository validation: "
            f"{result.status} — {describe_targeted_validation(result)}"
        )
        if oracle_receipt is not None:
            print(
                "🔎 VALIDATE.ORACLE.LIVE.1 existing-check roles: "
                + describe_check_oracle_assessment(oracle_receipt)
            )
    else:
        print(
            "❔ OPS.VALIDATE.3 targeted repository validation: inconclusive — "
            + str(telemetry.get("targeted_validation_reason") or "unavailable")
        )
    print(
        "🧭 Full repository validation and execution authorization are unchanged "
        "by targeted evidence."
    )
    return result


def _record_execution_eligibility(
    state: AgentState,
    policy: Any,
    *,
    patch_safety: Mapping[str, Any],
) -> Any | None:
    """EXEC.POLICY.LIVE.1 — pure reduction over already-recorded receipts.

    This adapter assembles immutable facts already present in the live state,
    times the pure reducer, and attaches telemetry.  It never calls an evidence
    producer and no authorization branch reads its result.
    """

    if normalize_patch_basis(policy.patch_basis) != PATCH_BASIS_GROUNDED_DEFECT:
        return None
    block = state.json_block if isinstance(state.json_block, dict) else {}
    control = state.control_result or {}
    route = state.live_route or control.get("live_route") or {}
    preflight = control.get("preflight_validation") or {}
    pre_probe = control.get("defect_probe") or {}
    candidate_fingerprint = candidate_fingerprint_from_payload(block)
    safety_receipt = dict(patch_safety) if isinstance(patch_safety, Mapping) else {}
    safety_receipt["candidate_fingerprint"] = candidate_fingerprint

    evidence = {
        "task_route": route,
        "patch_basis": policy.patch_basis,
        "source_target_grounded": block.get("target_source_grounded"),
        "candidate_fingerprint": candidate_fingerprint,
        "patch_safety": safety_receipt,
        "full_validation": preflight,
        "pre_probe": pre_probe,
        # The three producer receipts are flat on the live payload.  Supplying
        # the same mapping under typed names does not rewrite any field.
        "candidate_defect_closure": block,
        "targeted_validation": block,
        "oracle_assessment": block,
        "execution_authorization": block,
    }
    started = time.perf_counter()
    report = evaluate_execution_eligibility(evidence)
    elapsed = round(time.perf_counter() - started, 6)
    telemetry = report.as_telemetry()
    telemetry["execution_eligibility_evaluation_seconds"] = elapsed
    state.patch_policy.update(telemetry)
    block.update(telemetry)

    bounded = report.assessment_for(PROFILE_BOUNDED_EVIDENCE_HUMAN_REVIEW)
    print(
        "⚖️ EXEC.POLICY.LIVE.1 bounded human-review eligibility: "
        f"{bounded.eligibility_status} — {describe_execution_eligibility(report)}"
    )
    print(
        "🧭 Eligibility grants no execution authority and does not widen "
        "automatic apply policy."
    )
    return report


def _record_candidate_sandbox_validation(
    state: AgentState,
    policy: Any,
    project_root: Path,
    *,
    validation_command: str | None,
) -> CandidateSandboxValidation | None:
    """OPS.PATCH.2 — prove the FINAL explicit-change candidate before handoff.

    Scoped exactly as the phase is scoped: ``explicit_change_request`` only.  A
    ``grounded_defect`` reaching the same handoff — a low-confidence fix, or any
    fix under the ``vibe`` style — keeps its existing behaviour untouched, and
    the already-working defect auto-apply path never arrives here at all.

    Returns ``None`` when the gate does not apply, so the caller keeps its
    original wording for those routes.
    """

    if normalize_patch_basis(policy.patch_basis) != PATCH_BASIS_EXPLICIT_CHANGE_REQUEST:
        return None

    plan = candidate_plan_from_payload(state.json_block)
    if not plan:
        _record_no_candidate_validation(
            state,
            approval_ready=False,
            reason=(
                "Candidate validation was not attempted: the payload carried no "
                "materializable patch candidate."
            ),
        )
        return None

    baseline = (state.control_result or {}).get("preflight_validation")
    result = validate_candidate_in_sandbox(
        project_root,
        plan,
        validation_command=validation_command,
        baseline_validation=baseline,
    )

    telemetry = result.as_telemetry()
    state.patch_policy.update(telemetry)
    if isinstance(state.json_block, dict):
        state.json_block.update(telemetry)
        if not result.passed:
            # Still reviewable — the diagnostics are the point — but not a
            # candidate anything may present as ready to approve.
            state.json_block["eligible_for_patch_safety_handoff"] = False
            state.json_block["needs_escalation"] = True

    if result.output_excerpt:
        state.validation_output = result.output_excerpt

    message = describe_candidate_validation(result)
    state.auto_patch_result = message
    icon = "🧪" if result.passed else ("🛑" if result.failed else "❔")
    print(f"{icon} OPS.PATCH.2 candidate validation: {result.status} — {message}")
    if result.failed and result.apply_error:
        print(f"   sandbox apply error: {result.apply_error}")
    if result.output_excerpt and not result.passed:
        print(result.output_excerpt)
    print(
        "🧭 Automatic write remains unauthorized for an explicit change; "
        "human approval is still required."
    )
    return result


def _record_candidate_verification(
    state: AgentState,
    policy: Any,
    *,
    patch_safety: Mapping[str, Any],
) -> Any | None:
    """CANDIDATE.VERIFY.LIVE.1 — reduce this run's evidence into one verdict.

    Pure adapter: it assembles receipts that are already on the live payload,
    times the pure reducer and attaches additive telemetry.  It calls no
    evidence producer, runs no command, and grants nothing.

    The one thing it does beyond recording is fail closed.  A candidate whose
    verification is not ``verified`` may not be *presented* as ready to approve,
    so ``needs_escalation`` is raised and ``human_review_eligible`` is narrowed
    to false.  Narrowing only ever removes readiness — EXEC.POLICY.LIVE.1 stays
    byte-identical and no eligibility this layer did not already have is
    created.
    """

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return None
    plan = candidate_plan_from_payload(block)
    if not plan:
        return None

    control = state.control_result or {}
    preflight = control.get("preflight_validation") or {}
    pre_probe = control.get("defect_probe") or {}
    candidate_fingerprint = candidate_fingerprint_from_payload(block)
    safety_receipt = dict(patch_safety) if isinstance(patch_safety, Mapping) else {}
    safety_receipt.setdefault("candidate_fingerprint", candidate_fingerprint)

    started = time.perf_counter()
    receipt = evaluate_candidate_verification(
        {
            "policy_profile": verification_profile_for_basis(policy.patch_basis),
            "patch_basis": policy.patch_basis,
            "candidate_fingerprint": candidate_fingerprint,
            "candidate_target_paths": _patch_payload_target_files(block),
            "patch_safety": safety_receipt,
            "pre_probe": pre_probe,
            "full_validation": preflight,
            # The three producer receipts are flat on the live payload.
            # Supplying the same mapping under typed names does not rewrite any
            # field, exactly as EXEC.POLICY.LIVE.1 already does.
            "candidate_defect_closure": block,
            "targeted_validation": block,
            "oracle_assessment": block,
            "candidate_sandbox_validation": block,
        }
    )
    telemetry = receipt.as_telemetry()
    telemetry["candidate_verification_timings"] = {
        **telemetry.get("candidate_verification_timings", {}),
        "verification_reduction_sec": round(time.perf_counter() - started, 6),
    }
    telemetry["candidate_verification_mutation_enabled"] = bool(AUTO_PATCH_ENABLED)
    state.patch_policy.update(telemetry)
    block.update(telemetry)

    if not receipt.verified:
        # §11/§12 — rejected, inconclusive, unavailable, stale and invalid all
        # fail closed.  A preservation regression can never be review-ready.
        block["needs_escalation"] = True
        block["human_review_eligible"] = False
        block["approval_ready"] = False
        issues = block.get("issues")
        if not isinstance(issues, list):
            issues = []
        if not any(
            isinstance(issue, dict) and issue.get("type") == "candidate_verification"
            for issue in issues
        ):
            issues[0:0] = receipt.as_issues()
        block["issues"] = issues

    icon = "🔒" if receipt.verified else "🛑"
    print(
        f"{icon} CANDIDATE.VERIFY.LIVE.1 candidate verification: {receipt.status} — "
        + describe_candidate_verification(receipt)
    )
    print(
        "🧭 Candidate verification is evidence about the candidate; it grants no "
        "execution authority and does not widen automatic apply."
    )
    return receipt


def _verify_authored_candidate_without_mutation(state: AgentState) -> Any | None:
    """CANDIDATE.VERIFY.LIVE.1 §1–§3 — the read-only branch of the lifecycle.

    ``AUTO_PATCH_ENABLED`` controls mutation.  It used to control verification
    too, because :func:`maybe_run_auto_patch` returned here before any evidence
    producer ran, and the authored candidate was still shown to a human with no
    receipt of any kind.  This function is the piece that used to be skipped:
    the same producers the mutation-enabled handoff already runs, in the same
    order, on a disposable sandbox copy — never the real repository.

    Nothing in it can acquire authority.  There is no executor call, no apply
    path and no authority setter; the caller records the unchanged
    ``auto_patch_disabled`` denial immediately afterwards.
    """

    if AUTO_PATCH_ENABLED:
        raise RuntimeError(
            "read-only candidate verification is the mutation-disabled branch"
        )
    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return None

    control = state.control_result or {}
    if state.is_project_input and control:
        if state.live_route and not control.get("live_route"):
            control["live_route"] = state.live_route
        control = refresh_control_safety(control)
        state.control_result = control

    project_root = Path(state.repo_path) if state.repo_path else Path.cwd()

    verification = _run_read_only_candidate_lifecycle(
        state, project_root=project_root
    )

    # PATCH.AUTHOR.LIVE.1 — the one place a rejected candidate may be handed
    # back to its author.  What comes out is the verification of whichever
    # candidate is finally on the table: Candidate0's when no revision was
    # warranted, possible or usable, and Candidate1's when one was authored and
    # then re-verified in full by the same lifecycle above.
    verification = _maybe_revise_rejected_candidate(
        state, project_root=project_root, verification=verification
    )
    # ANSWER.COHERENCE.LIVE.1 — the candidate lifecycle is terminal here, so
    # this is where the final answer is bound to exactly one candidate.
    _record_candidate_presentation(state)

    state.auto_patch_result = _read_only_verification_message(verification)
    revision = getattr(state, "candidate_revision", None)
    if isinstance(revision, CandidateRevisionReceipt) and revision.attempted:
        state.auto_patch_result = (
            f"{state.auto_patch_result} {describe_candidate_revision(revision)}."
        )
    return verification


def _run_read_only_candidate_lifecycle(
    state: AgentState, *, project_root: Path
) -> Any | None:
    """One complete pass of the read-only candidate gate and verification.

    Lifted unchanged out of :func:`_verify_authored_candidate_without_mutation`
    so PATCH.AUTHOR.LIVE.1 can run it a second time on a revised candidate
    without a second implementation of the order.  The producers, their
    sequence and their arguments are byte-for-byte what they were; the only
    difference is that the body now has a name.
    """

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return None

    # §4/§14 — evidence bound to a candidate that has since been rewritten is
    # dropped before anything is measured, so the fingerprint below names the
    # exact bytes that are about to be verified.
    _drop_stale_candidate_validation(state)
    if not candidate_plan_from_payload(block):
        # Nothing was authored, so there is nothing to verify and nothing is
        # claimed.  The payload is left exactly as it was found.
        return None

    control = state.control_result or {}
    # Selected here, not by the caller: this is where the original body chose
    # it, after the guard above, so a payload with nothing to verify still
    # reads nothing off the state to choose a command it will never run.
    validation_command = (
        extract_user_validation_command(state.user_input)
        or get_default_validation_command(state.language, project_root)
        or None
    )
    writer_confidence, _needs_escalation = get_confidence_and_escalation(
        state.json_block
    )
    # §22 — ``writer_confidence`` reaches the existing policy builder because
    # that is where it has always been read.  It is not an input to the
    # verification verdict, and a high value cannot rescue rejected evidence.
    policy = build_patch_policy(
        state.task_info.get("patch_style") or state.patch_style or "safe_minimal",
        language=state.language,
        patch_confidence=writer_confidence,
        defect_grounded=control_has_grounded_patch_candidate(control),
        patch_basis=block.get("patch_basis"),
        has_validation_command=bool(validation_command),
    )

    # §2 — the invariants this branch holds regardless of what the evidence
    # says.  They are written before any producer runs, so no later failure can
    # leave the payload implying authority.
    read_only_facts = {
        "patch_basis": policy.patch_basis,
        "patch_basis_accepted": policy.patch_basis_accepted,
        "auto_apply_allowed": False,
        "write_authority": False,
        "patch_application_authority": False,
        "human_approval_required": True,
    }
    state.patch_policy.update(read_only_facts)
    block.update(read_only_facts)

    targets = _patch_payload_target_files(block)
    patch_safety = evaluate_patch_safety(targets, project_root=project_root)
    block["patch_safety"] = patch_safety
    block["patch_safety_passed"] = bool(patch_safety.get("ok"))
    state.patch_policy["patch_safety"] = patch_safety
    if not patch_safety.get("ok"):
        # OPS.PATCH.2 §26 — a candidate existing patch safety refused is never
        # materialized "just to see what happens", with or without the switch.
        block["eligible_for_patch_safety_handoff"] = False
        block["patch_safety_blocked"] = True
        _record_no_candidate_validation(
            state,
            approval_ready=False,
            reason=(
                "Candidate validation was not attempted: existing patch safety "
                "blocked the candidate before any sandbox materialization."
            ),
        )
    else:
        # §1 lifecycle order: exact candidate sandbox, then the paired probe,
        # then targeted validation and its oracle roles.  Each of these is the
        # existing producer, called exactly as the mutation-enabled handoff
        # calls it; none of them writes to the real repository.
        _record_candidate_sandbox_validation(
            state,
            policy,
            project_root,
            validation_command=validation_command,
        )
        _record_candidate_defect_closure(
            state,
            policy,
            project_root,
            patch_safety=patch_safety,
        )
        _record_targeted_repository_validation(
            state,
            policy,
            project_root,
            patch_safety=patch_safety,
        )

    # §1 — the verification receipt is formed from that evidence, and only then
    # does execution policy read it.
    verification = _record_candidate_verification(
        state, policy, patch_safety=patch_safety
    )
    _record_execution_eligibility(state, policy, patch_safety=patch_safety)
    if verification is not None and not verification.verified:
        # §12/§13 — the narrowing is re-applied after EXEC.POLICY writes its own
        # telemetry, so an unverified candidate cannot come out the far side
        # holding an eligibility the frozen Apply path would honour.
        block["human_review_eligible"] = False
        block["needs_escalation"] = True

    # §13/§15 — no approval-ready receipt is frozen here, for any verification
    # status.  EXEC.APPROVAL.LIVE.1's ``human_apply_review`` exists to let a
    # later human Apply authorize a *mutation*, and this branch is the one where
    # mutation is switched off; emitting one would re-conflate exactly the two
    # things this phase separates.  The frozen Apply path already refuses a
    # grounded-defect candidate that carries no such receipt, so a candidate
    # verified here — let alone a rejected one — cannot become an authorized
    # write.  Binding is by narrowing above, not by a second approval artifact.

    return verification


#: §17 — every candidate-bound receipt group.  Candidate1 earns all of them
#: again from nothing; not one of Candidate0's may authorize it.
_CANDIDATE_BOUND_RECEIPT_GROUPS: tuple[tuple[str, ...], ...] = (
    _CANDIDATE_VALIDATION_KEYS,
    _TARGETED_VALIDATION_KEYS,
    _CANDIDATE_DEFECT_PROBE_KEYS,
    _EXECUTION_ELIGIBILITY_KEYS,
    _CANDIDATE_VERIFICATION_KEYS,
    _CANDIDATE_EFFECT_KEYS,
    _CANDIDATE_NOVELTY_KEYS,
    _CANDIDATE_PRESENTATION_KEYS,
)

#: The derived readiness flags those receipts wrote.  They are decisions about
#: Candidate0 and are cleared with it, so Candidate1's own verification is what
#: sets them — in either direction — rather than inheriting a verdict.
_CANDIDATE_BOUND_READINESS_KEYS: tuple[str, ...] = (
    "patch_safety",
    "patch_safety_passed",
    "patch_safety_blocked",
    "eligible_for_patch_safety_handoff",
    "approval_ready",
    "human_review_eligible",
    "candidate_review_ready",
    "candidate_visible_for_debugging",
    "needs_escalation",
)


def _revision_author_configuration() -> tuple[str, str]:
    """§14 — the same authoring provider/model configuration as the draft call.

    Read from the same place :func:`run_draft_pipeline` reads it, so there is
    no path by which a revision quietly reaches a bigger model, a reviewer
    model or a different provider.
    """

    from config import MODELS

    return "google", (MODELS[0] if MODELS else "")


def _call_revision_provider(state: AgentState, prompt: str) -> str:
    """The single additional provider call PATCH.AUTHOR.LIVE.1 may make.

    One request, one authoring role, no retry and no fallback to a second
    request: §2 caps the count, §14 fixes the role and §45 says infrastructure
    failure consumes the opportunity instead of opening a loop.

    No files are attached.  The revision request is self-contained by
    construction — preserved task, exact target, authoritative original source,
    the rejected bytes and the measured cases — so re-uploading the draft
    call's attachments would add network without adding information (§13/§44).
    Tests replace this function to drive the lifecycle deterministically.
    """

    return run_gemini_request(
        prompt, None, **strict_emission_client_kwargs(state.strict_envelope_transport)
    )


def _record_candidate_revision(
    state: AgentState, receipt: CandidateRevisionReceipt
) -> CandidateRevisionReceipt:
    """Attach the bounded revision receipt and remember the spent budget."""

    state.candidate_revision = receipt
    telemetry = receipt.as_telemetry()
    state.patch_policy.update(telemetry)
    if isinstance(state.json_block, dict):
        state.json_block.update(telemetry)
    return receipt


def _recorded_candidate_presentation(
    state: AgentState,
) -> CandidateAuthoredFields | None:
    """The run's record of who authored the candidate now on the payload."""

    record = getattr(state, "candidate_presentation", None)
    return record if isinstance(record, CandidateAuthoredFields) else None


def _record_candidate_presentation(state: AgentState) -> Any | None:
    """ANSWER.COHERENCE.LIVE.1 — bind the final answer to one candidate.

    The generation comes from the revision receipt, the identity from the
    lifecycle receipts, and the author-facing fields from the run's record
    of that candidate's author.  Nothing here writes a readiness flag, an
    authority flag or ``needs_escalation``; a presentation that cannot be
    bound withholds the author's account instead of guessing whose it is.
    """

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return None
    revision = getattr(state, "candidate_revision", None)
    revised = bool(
        isinstance(revision, CandidateRevisionReceipt)
        and revision.revised_candidate_present
    )
    presentation = bind_final_candidate_presentation(
        block,
        author=_recorded_candidate_presentation(state),
        revised_candidate_present=revised,
        revised_candidate_fingerprint=(
            revision.revised_candidate_fingerprint if revised else ""
        ),
        payload_candidate_fingerprint=(
            candidate_fingerprint_from_payload(block)
            if candidate_plan_from_payload(block)
            else None
        ),
    )
    if presentation is None:
        return None
    block.update(presentation.as_telemetry())
    print(
        ("🧷 " if presentation.coherent else "🛑 ")
        + "ANSWER.COHERENCE.LIVE.1 final answer: "
        + describe_candidate_presentation(presentation)
    )
    return presentation


def _revision_attempts_already_made(state: AgentState) -> int:
    """§2/§37 — the budget counter, read from the run rather than the payload."""

    previous = getattr(state, "candidate_revision", None)
    if isinstance(previous, CandidateRevisionReceipt):
        return previous.attempt_count
    return 0


def _drop_candidate_bound_receipts(state: AgentState) -> None:
    """§17 — remove every receipt and readiness flag Candidate0 earned."""

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return
    for group in _CANDIDATE_BOUND_RECEIPT_GROUPS:
        for key in group:
            block.pop(key, None)
            if isinstance(state.patch_policy, dict):
                state.patch_policy.pop(key, None)
    for key in _CANDIDATE_BOUND_READINESS_KEYS:
        block.pop(key, None)
        if isinstance(state.patch_policy, dict):
            state.patch_policy.pop(key, None)
    issues = block.get("issues")
    if isinstance(issues, list):
        block["issues"] = [
            issue
            for issue in issues
            if not (
                isinstance(issue, dict)
                and issue.get("type") in {"candidate_verification", "candidate_effect"}
            )
        ]


def _maybe_revise_rejected_candidate(
    state: AgentState, *, project_root: Path, verification: Any | None
) -> Any | None:
    """PATCH.AUTHOR.LIVE.1 — at most one evidence-bound author revision.

    The model proposes, the deterministic harness rejects, and when — and only
    when — that rejection carries behavioral counterevidence bound to this
    exact candidate, the same authoring role is asked once for a corrected
    candidate against the ORIGINAL authoritative source.  Candidate1 then
    re-enters the frozen pipeline from the top and earns every receipt again.

    This function decides nothing about correctness.  It cannot mark a
    candidate verified, cannot widen ``safe_minimal``, cannot change a
    validation budget and cannot grant authority; the value it returns is
    whatever :func:`_run_read_only_candidate_lifecycle` concluded.
    """

    block = state.json_block if isinstance(state.json_block, dict) else None
    if block is None:
        return verification
    if _revision_attempts_already_made(state) >= MAX_REVISION_CALLS_PER_RUN:
        # §2/§37 — the opportunity is spent, and its receipt is terminal.  Not
        # overwriting it is the whole point: replacing it with a fresh "not
        # eligible, the budget is gone" record would erase the count that makes
        # the budget hold, and a third pass would find an unspent one.
        return verification

    considered = (
        bool(candidate_plan_from_payload(block))
        or bool(block.get("candidate_effect_status"))
        or block.get("candidate_novelty_admitted") is False
    )
    if not considered:
        # The payload never carried a candidate and none was ever measured or
        # refused.  Annotating it with a decision about a candidate that does
        # not exist would be the mistake PATCH.MINIMAL.LIVE.1 §9 declines to
        # make.  A candidate the no-op or safe_minimal gate *removed* is the
        # opposite case: something was decided, and §34/§35 want that visible.
        return verification

    control = state.control_result or {}
    route = state.live_route or control.get("live_route") or {}
    patch_intent = control.get("patch_intent") or {}
    pre_probe = control.get("defect_probe") or {}
    candidate = block.get("patch_candidate")
    candidate = candidate if isinstance(candidate, Mapping) else {}
    original_source = str(patch_intent.get("source_snippet") or "")
    target_file = str(
        patch_intent.get("relative_path") or patch_intent.get("target_file") or ""
    ).replace("\\", "/").strip("/")
    target_symbol = str(patch_intent.get("target_symbol") or "")
    candidate_fingerprint = candidate_fingerprint_from_payload(block)

    run_identity = f"{state.session_id}:{state.task_run_id}:{state.started_at}"
    started = time.perf_counter()
    assessment = assess_candidate_revision(
        {
            "task_route": route,
            "patch_basis": normalize_patch_basis(block.get("patch_basis")),
            "payload": block,
            "patch_safety": block.get("patch_safety") or {},
            "pre_probe": pre_probe,
            "candidate_fingerprint": candidate_fingerprint,
            "rejected_target_snippet": str(candidate.get("target_snippet") or ""),
            "rejected_patched_snippet": str(candidate.get("patched_snippet") or ""),
            "target_file": target_file,
            "target_symbol": target_symbol,
            "original_source": original_source,
            "preserved_task": state.user_input,
            "revision_attempts_already_made": _revision_attempts_already_made(state),
            "run_identity": run_identity,
        }
    )
    evidence_seconds = round(time.perf_counter() - started, 6)

    if not assessment.eligible:
        # §28/§34/§35/§36 — the zero-model-call outcome, recorded rather than
        # left silent so a reader can see the trigger was evaluated.
        # ``previous_candidate_fingerprint`` names the candidate a revision
        # replaced, and nothing was replaced here, so it stays empty.  Which
        # candidate was declined is already on the payload, under the effect
        # and verification receipts that named it.
        receipt = replace(
            not_eligible_receipt(assessment), evidence_seconds=evidence_seconds
        )
        _record_candidate_revision(state, receipt)
        print(
            "🧾 PATCH.AUTHOR.LIVE.1 candidate revision: "
            + describe_candidate_revision(receipt)
        )
        return verification

    evidence = assessment.evidence
    if not revision_evidence_is_current(
        evidence,
        candidate_fingerprint=candidate_fingerprint,
        original_source=original_source,
        target_file=target_file,
        target_symbol=target_symbol,
        preserved_task=state.user_input,
        payload=block,
        run_identity=run_identity,
    ):
        # §19 — a receipt whose binding moved between construction and use is
        # not revised from.  No model call is spent on stale evidence.
        _record_candidate_revision(
            state,
            CandidateRevisionReceipt(
                eligible=True,
                attempted=False,
                outcome=OUTCOME_STALE,
                trigger=assessment.trigger,
                previous_candidate_fingerprint=candidate_fingerprint,
                evidence_fingerprint=evidence.evidence_fingerprint,
                counterexample_count=evidence.counterexample_count,
                preserved_case_count=len(evidence.preserved_cases),
                evidence_seconds=evidence_seconds,
            ),
        )
        return verification

    # PATCH.AUTHOR.LIVE.2 — the same authoring contract the initial draft was
    # given, from the same accessor, because the provider call is stateless and
    # a contract it was shown in an earlier call is a contract it does not have.
    authoring = state.candidate_authoring_context or authoring_context_for_control_result(
        control, repo_path=state.repo_path,
    )
    current_binding, current_source, current_raw = authoring.source_inputs(state.repo_path)
    authoring = replace(authoring, binding_context=current_binding,
                        authoritative_source=current_source, oop_source_bytes=current_raw)
    contract = authoring.contract
    prompt = authoring.revision_prompt(evidence)
    provider, model = _revision_author_configuration()
    print(
        "✍️ PATCH.AUTHOR.LIVE.1 requesting one verification-guided revision on "
        f"{evidence.counterexample_count} deterministic counterexample(s)"
    )

    call_started = time.perf_counter()
    try:
        response = _call_revision_provider(state, prompt)
    except Exception as exc:  # §45 — bounded failure, never a retry loop
        response = f"AGENT_ERROR: {type(exc).__name__}"
    latency = round(time.perf_counter() - call_started, 6)

    revised = parse_revised_candidate(response, evidence, authoring_context=authoring)
    base = CandidateRevisionReceipt(
        eligible=True,
        attempted=True,
        attempt_count=1,
        outcome=OUTCOME_REVISED_CANDIDATE_PRODUCED,
        trigger=assessment.trigger,
        previous_candidate_fingerprint=evidence.rejected_candidate_fingerprint,
        evidence_fingerprint=evidence.evidence_fingerprint,
        counterexample_count=evidence.counterexample_count,
        preserved_case_count=len(evidence.preserved_cases),
        provider=provider,
        model=model,
        author_selection="same_as_initial_draft",
        latency_seconds=latency,
        evidence_seconds=evidence_seconds,
        input_chars=len(prompt),
        output_chars=len(response if isinstance(response, str) else ""),
        # PATCH.AUTHOR.LIVE.2 §33 — which authoring contract this call was
        # held to, by identity.  The contract text itself is not recorded.
        authoring_contract_version=contract.version,
        authoring_contract_fingerprint=contract.fingerprint,
        revision_contract_present=True,
        authoring_scope_fingerprint=authoring.scope_fingerprint,
        concrete_counterexample_count=evidence.concrete_counterexample_count,
        concrete_counterexample_bytes=evidence.concrete_counterexample_bytes,
    )

    if not revised.accepted:
        # §20 — no reformat request, no repair prompt, no second call.
        receipt = replace(
            base,
            outcome=(
                OUTCOME_REVISION_UNAVAILABLE
                if revised.unavailable
                else OUTCOME_REVISION_OUTPUT_INVALID
            ),
            output_rejection_reason=revised.rejection_reason,
        )
        _record_candidate_revision(state, receipt)
        block["needs_escalation"] = True
        block["human_review_eligible"] = False
        block["approval_ready"] = False
        if revised.quarantine_receipt is not None:
            block["candidate_revision_quarantine"] = revised.quarantine_receipt
            block["patch_candidate"] = None
            block["patch_plan"] = None
        print(
            "🛑 PATCH.AUTHOR.LIVE.1 candidate revision: "
            + describe_candidate_revision(receipt)
        )
        return verification

    # §11/§17 — Candidate0 survives only as bounded historical evidence, and
    # every receipt it earned is removed before Candidate1 is measured.
    # ANSWER.COHERENCE.LIVE.1 §3/§27 — that history also keeps what
    # Candidate0's author said and what verification found, labelled as the
    # rejected first generation, because the primary surface below carries
    # Candidate1's account and nobody else's.
    superseded = _recorded_candidate_presentation(state)
    block["candidate_revision_previous_candidate"] = {
        "candidate_fingerprint": evidence.rejected_candidate_fingerprint,
        "relative_path": evidence.target_file,
        "target_node_name": evidence.target_symbol,
        "patched_snippet": evidence.rejected_patched_snippet,
        "status": "rejected_evidence_only",
        **superseded_candidate_history(block, superseded),
    }
    _drop_candidate_bound_receipts(state)
    # ANSWER.COHERENCE.LIVE.1 — Candidate1 and its author's account are one
    # install from one response: the bytes, the §42 confidence (a confidence
    # travels only if this response actually carried one), the summary and
    # the author's own issues.  A field it did not supply stays absent.
    authored = capture_candidate_authored_fields(
        extract_json_block(response),
        generation=GENERATION_REVISION,
        confidence=revised.confidence,
        supersedes=superseded,
    ) or CandidateAuthoredFields(
        generation=GENERATION_REVISION, supersedes=superseded
    )
    install_candidate_presentation(
        block, candidate=revised.candidate, authored=authored
    )
    state.candidate_presentation = authored

    # A fresh candidate has escalated nothing yet.  Candidate0's flag was a
    # decision about Candidate0, and every gate below can raise this one again
    # — a failed revision does so explicitly at the end of this function.
    block["needs_escalation"] = False

    # §16 — Candidate1 is a new candidate: new normalization, then the same two
    # minimality gates ``finalize_answer`` runs on a first draft, then the whole
    # read-only lifecycle again.  Nothing here is skipped or favoured.
    normalize_patch_candidate_with_control_source(state)
    # Read before the gates run: this names the bytes the author returned, so a
    # candidate the no-op gate then removes is still identifiable.
    revised_fingerprint = candidate_fingerprint_from_payload(block)
    _enforce_measured_authoring_scope(state)
    _record_candidate_mutation_effect(state)
    binding_context, authoritative_source = (
        _safe_minimal_authoritative_binding_inputs(state)
    )
    _enforce_safe_minimal(
        state,
        authoritative_binding_context=binding_context,
        authoritative_source=authoritative_source,
    )

    revised_verification = _run_read_only_candidate_lifecycle(
        state, project_root=project_root
    )

    verified = bool(
        revised_verification is not None and revised_verification.verified
    )
    receipt = replace(
        base,
        outcome=(
            OUTCOME_REVISED_CANDIDATE_VERIFIED
            if verified
            else OUTCOME_REVISED_CANDIDATE_REJECTED
        ),
        revised_candidate_fingerprint=revised_fingerprint,
        revised_candidate_present=True,
    )
    _record_candidate_revision(state, receipt)
    if not verified:
        # §31/§27 — a failed revision terminates cleanly, and terminates closed.
        block["needs_escalation"] = True
        block["human_review_eligible"] = False
        block["approval_ready"] = False
    print(
        ("🔒 " if verified else "🛑 ")
        + "PATCH.AUTHOR.LIVE.1 candidate revision: "
        + describe_candidate_revision(receipt)
    )
    print(
        "🧭 A revised candidate is authorship, not authority: it grants no "
        "execution authority and does not widen automatic apply."
    )
    return revised_verification if revised_verification is not None else verification


def _read_only_verification_message(verification: Any | None) -> str:
    """§10 — user-facing wording that can never be read as "ready to apply"."""

    if verification is None:
        return (
            "Automatic patching is disabled (AUTO_PATCH_ENABLED=false); no "
            "repository change was made."
        )
    if verification.verified:
        return (
            "Candidate verification: verified. Automatic patching is disabled "
            "(AUTO_PATCH_ENABLED=false), so nothing was applied and no write "
            "was authorized; human approval is still required."
        )
    return (
        f"Candidate verification: {verification.status}. The candidate below is "
        "shown for inspection only — it is not verified and is not ready to "
        "approve or apply. "
        + describe_candidate_verification(verification)
    )


def maybe_run_auto_patch(state: AgentState, interactive: bool = True) -> None:
    from core.localization_handoff import enforce_payload_target

    enforce_payload_target(
        getattr(state, "control_result", None), getattr(state, "json_block", None),
        live_route=getattr(state, "live_route", None),
    )
    # WAITER.LIVE.1 — a route that requested no change may not become a write,
    # whatever a downstream component produced.
    if route_is_read_only(state.live_route):
        print("🧭 WAITER: read-only route — no repository change was requested.")
        _record_no_execution(state, DENIED_NO_CHANGE_REQUESTED)
        return

    # PATCH.MINIMAL.LIVE.1 §6/§11 — the lifecycle boundary, after target/binding
    # integrity and before either branch.  ``finalize_answer`` already ran this
    # for every payload the writer produced; repeating it here is what makes the
    # invariant hold for a payload that reached the lifecycle another way, and
    # it is one byte comparison, so repeating it costs nothing.  An exact no-op
    # is rejected with its candidate removed, which is why the read-only branch
    # below finds nothing to verify and no producer is entered (§13).
    _record_candidate_mutation_effect(state)

    if not AUTO_PATCH_ENABLED:
        # EXEC.AUTH.LIVE.1 §25: nothing established earlier in the run — patch
        # basis, grounding, sandbox validation, confidence — reaches past this
        # as *authority*.  CANDIDATE.VERIFY.LIVE.1 §3 separates that from
        # evidence: the switch disables mutation, and an already-authored
        # candidate is still verified read-only before it is shown to anyone.
        print(
            "Auto-patch disabled by AUTO_PATCH_ENABLED=false — mutation is off; "
            "an authored candidate is still verified read-only."
        )
        _verify_authored_candidate_without_mutation(state)
        _record_no_execution(state, DENIED_AUTO_PATCH_DISABLED)
        return

    # OPS.PATCH.2 — a candidate-validation result belongs to one exact
    # candidate.  If the payload now carries a different one, the old verdict
    # goes with the old plan rather than travelling forward attached to a plan
    # it never described.
    _drop_stale_candidate_validation(state)

    normalize_patch_candidate_with_control_source(state)
    # PATCH.MINIMAL.LIVE.1 §12 — normalization may broaden a partial body to the
    # full CONTROL source snippet, which changes the candidate's bytes and so
    # its fingerprint.  Re-measuring here keeps the recorded effect bound to the
    # bytes that would actually be applied.  Broadening cannot turn a mutation
    # into a no-op or the reverse — it rewrites both sides the same way — so
    # this re-binds the receipt rather than reopening the verdict.
    _record_candidate_mutation_effect(state)

    control = state.control_result or {}
    if state.is_project_input and control:
        if state.live_route and not control.get("live_route"):
            control["live_route"] = state.live_route
        control = refresh_control_safety(control)
        enforce_payload_target(control, state.json_block, live_route=state.live_route)
        enforce_control_grounding_on_payload(control, state.json_block or {})
        if not payload_is_eligible_for_patch_safety_handoff(state.json_block):
            state.auto_patch_result = (
                "Patch plan blocked by safety gate: no legitimate typed patch "
                "basis with exact grounded targets."
            )
            print(
                "🛑 CONTROL has no legitimate typed patch basis with exact "
                "grounded targets."
            )
            _record_no_execution(state, DENIED_NO_PATCH_BASIS_HANDOFF)
            return

    patch_intent = control.get("patch_intent") or {}

    source_snippet = patch_intent.get("source_snippet")
    print("🐛 DEBUG control source_snippet exists:", bool(source_snippet))

    writer_confidence, needs_escalation = get_confidence_and_escalation(state.json_block)

    top = (state.control_result or {}).get("top_hypothesis") or {}
    localization = localization_value(top)

    if needs_escalation:
        print("🛑 Patch needs escalation → skip patch")
        _record_no_execution(state, DENIED_NEEDS_ESCALATION)
        return

    plan = state.json_block.get("patch_plan")
    style = state.task_info.get("patch_style") or state.patch_style or "safe_minimal"
    scout = (state.control_result or {}).get("scout") or {}
    request_type = scout.get("request_type")

    task_intent = state.task_info.get("intent", "")
    preflight = (state.control_result or {}).get("preflight_validation") or {}

    is_compiler_grounded_fix = bool(
        preflight.get("ran")
        and preflight.get("ok") is False
        and is_compiler_grounded_category(preflight.get("category"))
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

    if isinstance(plan, list) and plan:
        if not is_allowed_patch_plan:
            print("🛑 patch_plan detected but not allowed for this task/style.")
            _record_no_execution(
                state, DENIED_PATCH_STYLE_OR_TASK_NOT_ELIGIBLE
            )
            return
        project_root = Path(state.repo_path) if state.repo_path else Path.cwd()
        explicit_cmd = extract_user_validation_command(state.user_input)
        validation_command = (
            explicit_cmd
            or get_default_validation_command(state.language, project_root)
            or None
        )
        plan_policy = build_patch_policy(
            style,
            language=state.language,
            patch_confidence=writer_confidence,
            defect_grounded=control_has_grounded_patch_candidate(control),
            patch_basis=(state.json_block or {}).get("patch_basis"),
            has_validation_command=bool(validation_command),
        )
        if not plan_policy.patch_basis_accepted:
            state.auto_patch_result = (
                "Patch plan blocked by safety gate: no legitimate typed patch basis."
            )
            print("🛑 Patch plan has no legitimate typed patch basis.")
            _record_no_execution(state, DENIED_PATCH_BASIS_NOT_ACCEPTED)
            return
        if not plan_policy.auto_apply_allowed:
            # OPS.PATCH.2 §10: the candidate sandbox is validated with the
            # command this run already selected through OPS.VALIDATE.1, not one
            # the gate picked for itself.
            _record_patch_safety_handoff(
                state,
                plan_policy,
                Path(state.repo_path) if state.repo_path else Path.cwd(),
                validation_command=validation_command,
            )
            return
        patch_safety = evaluate_patch_safety(
            _patch_payload_target_files(state.json_block),
            project_root=project_root,
        )
        _record_candidate_defect_closure(
            state,
            plan_policy,
            project_root,
            patch_safety=patch_safety,
        )
        _record_targeted_repository_validation(
            state,
            plan_policy,
            project_root,
            patch_safety=patch_safety,
        )
        print("🧩 Grounded patch_plan detected → running patch_plan_executor")
        # EXEC.AUTH.LIVE.1 — this line is the multi-file execution
        # authorization point.  ``plan_policy.auto_apply_allowed`` is the gate
        # that permitted the mutation; everything below merely observes it.
        plan_observed_paths = _patch_payload_target_files(state.json_block)
        plan_before = observe_named_paths(project_root, plan_observed_paths)
        result = run_patch_plan_with_artifacts(
            str(project_root),
            plan,
            validation_command=validation_command,
            user_query=state.user_input,
            control_result=state.control_result,
            source="pipeline",
            worker_patch_response=state.worker_patch_response,
            strict_envelope_emission=state.strict_envelope_emission,
            pre_execution_intent_capture=state.pre_execution_intent_capture,
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
        _record_authorized_execution(
            state,
            authority_source=AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY,
            receipt=plan_execution_receipt(result),
            before=plan_before,
            project_root=project_root,
            observed_paths=plan_observed_paths,
            pre_mutation_refusal=plan_pre_mutation_refusal(result),
        )
        print(result.get("message", ""))
        if result.get("validation_output"):
            print(result.get("validation_output"))

        if result.get("success"):
            print("✅ Patch plan applied + validation passed.")
        else:
            print("🛑 Patch plan failed or rolled back.")
        print(
            "🧾 "
            + str((state.json_block or {}).get("execution_summary") or "")
        )
        return

    low_risk_single_patch = is_low_risk_single_file_patch(state)

    if low_risk_single_patch:
        if writer_confidence < 0.55:
            print(
                f"🛑 Writer patch confidence too low for low-risk patch → skip "
                f"(writer={writer_confidence:.2f}, "
                f"localization_strength={localization:.2f})"
            )
            _record_no_execution(
                state, DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD
            )
            return

        print(
            f"✅ Low-risk single-file patch accepted "
            f"(writer={writer_confidence:.2f}, "
            f"localization_strength={localization:.2f}; localization is non-authoritative)"
        )

    else:
        if writer_confidence < 0.65:
            print(
                f"🛑 Writer patch confidence too low → skip patch "
                f"(writer={writer_confidence:.2f}, "
                f"localization_strength={localization:.2f})"
            )
            _record_no_execution(
                state, DENIED_PATCH_CONFIDENCE_BELOW_THRESHOLD
            )
            return

        if not source_snippet:
            print("🛑 Missing source snippet → skip patch")
            _record_no_execution(state, DENIED_MISSING_SOURCE_SNIPPET)
            return

    confidence = writer_confidence
    auto_policy_ok = should_auto_patch(
        mode=state.mode,
        audience=state.interface,
        confidence=confidence,
        task_info=state.task_info,
    )

    if not auto_policy_ok and not low_risk_single_patch:
        print("⚠️ Auto-patch policy decided to skip patching.")
        _record_no_execution(state, DENIED_AUTO_PATCH_POLICY_DECLINED)
        return

    if not auto_policy_ok and low_risk_single_patch:
        print("⚠️ Global auto-patch policy would skip, but low-risk grounded single-file patch is allowed to continue.")

    current_patch = state.json_block.get("patch_candidate") or dict(state.json_block)

    if current_patch.get("rejected"):
        print(f"🛑 Patch rejected: {current_patch.get('reject_reason')}")
        _record_no_execution(state, DENIED_CANDIDATE_REJECTED)
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
    policy = build_patch_policy(
        style,
        language=state.language,
        patch_confidence=writer_confidence,
        defect_grounded=control_has_grounded_patch_candidate(control),
        patch_basis=(state.json_block or {}).get("patch_basis"),
        has_validation_command=bool(user_validation_cmd),
    )

    # EXEC.AUTH.LIVE.1 §23 — the single-file path has exactly two ways to
    # obtain execution authority, and they are different rules: the style
    # policy's own ``auto_apply_allowed``, or the low-risk grounded
    # single-file rule that is allowed to proceed where the style policy alone
    # would stop.  The payload names whichever one actually applied.
    single_file_authority_source = (
        AUTHORITY_SOURCE_GROUNDED_DEFECT_AUTO_APPLY
        if policy.auto_apply_allowed
        else AUTHORITY_SOURCE_LOW_RISK_SINGLE_FILE
    )

    if not policy.auto_apply_allowed:
        if low_risk_single_patch:
            print(
                f"✅ Patch policy accepted: "
                f"{policy.style}"
            )
        else:
            if policy.patch_basis_accepted:
                _record_patch_safety_handoff(
                    state,
                    policy,
                    project_root,
                    validation_command=user_validation_cmd,
                )
            else:
                print(f"🛑 Patch style policy blocks auto-apply: {policy.style}")
                _record_no_execution(state, DENIED_PATCH_BASIS_NOT_ACCEPTED)
            return

    _record_targeted_repository_validation(
        state,
        policy,
        project_root,
        patch_safety=evaluate_patch_safety(
            _patch_payload_target_files(state.json_block),
            project_root=project_root,
        ),
    )

    state.started_at = time.time()

    if time_budget_exceeded(state):
        print("⏱️ Time budget exceeded → stopping patch loop")
        _record_no_execution(state, DENIED_TIME_BUDGET_EXCEEDED)
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

    # EXEC.AUTH.LIVE.1 — the executor's own typed receipt for each attempt.
    # ``run_self_correct_loop``'s attempt records deliberately do not carry the
    # OPS.VALIDATE.1 categorical outcome, so it is taken here, from the
    # ``ExecutionResult`` itself, rather than re-derived from output text.
    executed_attempts: list[Dict[str, Any]] = []

    def _on_attempt(idx: int, result: ExecutionResult) -> Optional[bool]:
        executed_attempts.append(
            {
                "phase": result.phase,
                **result.rollback_payload_fields(),
                "validation_outcome": result.validation_outcome,
                "target_file": result.target_file,
            }
        )
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

        if result.phase in {"dry_run_blocked", "post_apply_blocked", "patch_safety_blocked"}:
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

    # EXEC.AUTH.LIVE.1 — the single-file execution authorization point.  The
    # "before" window covers the payload's own named target; the executor's
    # reported targets are added afterwards so a re-patched attempt that landed
    # somewhere else is still accounted for rather than silently unobserved.
    single_file_observed_paths = _patch_payload_target_files(state.json_block)
    single_file_before = observe_named_paths(
        project_root, single_file_observed_paths
    )

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

    _record_authorized_execution(
        state,
        authority_source=single_file_authority_source,
        receipt=single_file_execution_receipt(
            executed_attempts,
            success=bool(loop_result.get("success")),
            validation_requested=bool(user_validation_cmd),
        ),
        before=single_file_before,
        project_root=project_root,
        observed_paths=single_file_observed_paths
        + [
            _repository_relative_target(project_root, record.get("target_file"))
            for record in executed_attempts
        ],
        pre_mutation_refusal=single_file_pre_mutation_refusal(executed_attempts),
    )
    print("🧾 " + str((state.json_block or {}).get("execution_summary") or ""))

    if loop_result["success"]:
        print("✅ Executor finished successfully.")
        return

    stop_reason = loop_result.get("stop_reason")
    final_phase = loop_result.get("final_phase")
    if final_phase == "validation_environment_failed":
        print("🛑 Validation was inconclusive: it established neither a pass nor a failure.")
        print("   Not asking AI to rewrite the patch against evidence that does not exist.")
        return
    if stop_reason == "policy_block":
        print("🛑 Patch was blocked by executor policy.")
        return
    print("⚠️ Max patch loops reached.")
