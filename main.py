from __future__ import annotations

import json
import sys

from cli.interactive import ask_entrypoint, create_agent_state
from config import WELCOME
from core.json_utils import extract_json_block
from core.pipeline import (
    finalize_answer,
    maybe_run_auto_patch,
    run_draft_pipeline,
    run_planner_pipeline,
    run_review_pipeline,
)
from core.session_io import (
    display_output,
    handle_followups,
    log_session_result,
    save_structured_outputs,
)
from database.memory import finish_task_run, init_db
from web.runner import launch_web
from patching.patch_gates import (
    collect_patch_repair_reasons,
    get_confidence_and_escalation,
    reject_ungrounded_patch,
    retry_structured_patch_json,
    normalize_patch_plan_schema,
    promote_go_missing_import_candidate_to_patch_plan,
    promote_ts_duplicate_import_candidate_to_patch_plan,
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
        print(f"Warning: Database initialization failed: {e}")
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

    if state.mode == "planner":
        plan_json = extract_json_block(reviewed)
        if plan_json:
            reviewed = run_planner_pipeline(state, plan_json)

    finalize_answer(state, reviewed)
    promote_go_missing_import_candidate_to_patch_plan(state)
    promote_ts_duplicate_import_candidate_to_patch_plan(state)
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
    promote_ts_duplicate_import_candidate_to_patch_plan(state)

    if state.mode == "reviewer" and not state.json_block:
        print("🔁 No JSON found → retrying structured JSON repair once...")
        repaired = retry_structured_patch_json(state, reviewed)
        finalize_answer(state, repaired)
        promote_go_missing_import_candidate_to_patch_plan(state)
    promote_ts_duplicate_import_candidate_to_patch_plan(state)

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

    maybe_run_auto_patch(state)

    confidence, needs_escalation = get_confidence_and_escalation(state.json_block)

    finish_task_run(
        task_run_id=state.task_run_id,
        status="succeeded",
        confidence=confidence,
        needs_escalation=needs_escalation,
    )

    log_session_result(state)
    display_output(state.human_answer, state.final_answer, state.json_block)
    save_structured_outputs(state)
    handle_followups(state)


if __name__ == "__main__":
    main()
