from __future__ import annotations

import json
import sys

from cli.interactive import ask_entrypoint, create_agent_state
from config import WELCOME
from core.localization_handoff import ground_state_answer
from core.credential_redaction import redact_credentials
from core.json_utils import extract_json_block
from core.live_task_routing import route_is_read_only
from core.pipeline import (
    finalize_answer,
    maybe_run_auto_patch,
    run_draft_pipeline,
    run_planner_pipeline,
    run_review_pipeline,
)
from core.postprocess_gates import run_postprocess_gate_battery
from core.session_io import (
    display_output,
    handle_followups,
    log_session_result,
    save_structured_outputs,
)
from database.memory import finish_task_run, init_db
from web.runner import launch_web
from patching.patch_gates import (
    get_confidence_and_escalation,
    retry_structured_patch_json,
    promote_ts_duplicate_import_candidate_to_patch_plan,
    promote_ts_missing_import_candidate_to_patch_plan,
)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass


def main() -> None:
    try:
        init_db()
    except Exception as e:
        print(
            "Warning: Database initialization failed: "
            f"{redact_credentials(e)}"
        )
        print("Continuing without database. Some features may not work.")

    if len(sys.argv) > 1 and sys.argv[1] == "--index":
        from core.indexer import index_repository
        path = sys.argv[2] if len(sys.argv) > 2 else "."
        index_repository(path)
        return

    print(WELCOME.strip())

    if len(sys.argv) > 1 and sys.argv[1] in {"--web", "-w"}:
        entrypoint = "web"
    elif len(sys.argv) > 1 and sys.argv[1] in {"--terminal", "--cli", "-t"}:
        entrypoint = "terminal"
    else:
        entrypoint = ask_entrypoint()

    if entrypoint == "web":
        launch_web()
        return

    state = create_agent_state()
    if not state:
        return

    try:
        draft = run_draft_pipeline(state)
    except RuntimeError as e:
        if state.task_run_id:
            finish_task_run(
                task_run_id=state.task_run_id,
                status="failed",
                confidence=0.0,
                needs_escalation=True,
            )
        print(f"\n❌ Pipeline Halted: Step 1 failed.\n{e}")
        return

    reviewed = run_review_pipeline(state, draft)

    # WAITER.LIVE.1 — mode is not task identity.  "planner" plus an architecture
    # question is still an architecture question, and a read-only route never
    # enters the plan-execution pipeline.
    if state.mode == "planner" and not route_is_read_only(state.live_route):
        plan_json = extract_json_block(reviewed)
        if plan_json:
            reviewed = run_planner_pipeline(state, plan_json)

    finalize_answer(state, reviewed)
    run_postprocess_gate_battery(
        state,
        reviewed_answer=reviewed,
        retry_structured_patch_json_fn=retry_structured_patch_json,
        finalize_answer_fn=finalize_answer,
        mode_label="cli",
    )
    maybe_run_auto_patch(state)
    # ANSWER.GROUND.LIVE.1 runs only after the authority/execution path has
    # terminated. It changes the display/persistence copy, never the decision.
    ground_state_answer(state)

    print("💾 PATCH RESULT:")
    if state.json_block:
        print(json.dumps(state.json_block, indent=2, ensure_ascii=False))
    else:
        print("No structured patch JSON.")

    confidence, needs_escalation = get_confidence_and_escalation(state.json_block)

    run_status = "succeeded"
    if state.mode == "planner" and state.completed_subtasks:
        # The last completed step describes why the plan stopped. Earlier
        # failed attempts may have been recovered by a successful replan.
        last_status = state.completed_subtasks[-1].get("status")
        if last_status in {"blocked", "failed"}:
            run_status = last_status

    finish_task_run(
        task_run_id=state.task_run_id,
        status=run_status,
        confidence=confidence,
        needs_escalation=needs_escalation,
    )

    log_session_result(state)
    display_output(state.human_answer, state.final_answer, state.json_block)
    save_structured_outputs(state)
    handle_followups(state)


if __name__ == "__main__":
    main()
