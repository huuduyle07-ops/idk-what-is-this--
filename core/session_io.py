from __future__ import annotations

import json
import re

from agents.gemini_client import run_gemini_request
from config import OUTPUT_FILE
from core.agent_memory import persist_ai_memory_notes
from core.agent_state import AgentState
from core.localization_handoff import ground_answer_for_display
from core.json_utils import extract_json_block
from core.prompter import build_followup_prompt
from database.memory import save_artifact, save_message
from patching.patch_gates import get_confidence_and_escalation


def append_to_log(title: str, content: str) -> None:
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write("\n" + "#" * 30 + f" {title} " + "#" * 30 + "\n")
        f.write((content or "") + "\n")


def strip_json_from_text(text: str) -> str:
    return re.sub(r"```json\s*\{.*?\}\s*```", "", text, flags=re.DOTALL).strip()


def display_output(human_answer: str, raw_answer: str, json_block: dict | None) -> None:
    if human_answer:
        print("\n🤖 Mentor:")
        print(human_answer)
    else:
        print("\n🤖 Raw:")
        print(raw_answer)

    if json_block:
        print("\n🧠 Structured:")
        print(json.dumps(json_block, indent=2, ensure_ascii=False))


def log_session_result(state: AgentState) -> None:
    append_to_log("--- USER INPUT ---", state.user_input)
    append_to_log("--- FINAL ANSWER ---", state.final_answer)
    if state.auto_patch_result:
        append_to_log("--- AUTO PATCH APPLIED ---", state.auto_patch_result)
    if state.validation_output:
        append_to_log("--- VALIDATION OUTPUT ---", state.validation_output)

    confidence, needs_escalation = get_confidence_and_escalation(state.json_block)
    append_to_log("--- CONFIDENCE ---", str(confidence))
    append_to_log("--- NEEDS ESCALATION ---", str(needs_escalation))


def save_structured_outputs(state: AgentState) -> None:
    if state.json_block:
        save_artifact(
            state.session_id,
            "structured_output",
            json.dumps(state.json_block, ensure_ascii=False),
        )
    save_message(state.session_id, "assistant", state.final_answer)


def handle_followups(state: AgentState) -> None:
    history = [
        {"role": "system", "content": f"Interface={state.interface}; Mode={state.mode}; Language={state.language}"},
        {"role": "user", "content": state.user_input},
        {"role": "assistant", "content": state.human_answer if state.human_answer else state.final_answer},
    ]

    while True:
        user_reply = input("\n👨‍🎓 Your follow-up (or type 'exit'): ").strip()
        if user_reply.lower() == "exit":
            persist_ai_memory_notes(state.session_id, state.project_tag or "")
            print("👋 Session ended.")
            return

        history.append({"role": "user", "content": user_reply})
        save_message(state.session_id, "user", user_reply)

        followup_prompt = build_followup_prompt(
            history=history,
            mode=state.mode,
            audience=state.interface,
            language=state.language,
            task_type=state.task_type,
            code_analysis=state.code_analysis,
            context_data=state.context_data,
            task_info=state.task_info,
        )
        followup_answer = run_gemini_request(
            followup_prompt,
            state.file_paths if state.file_paths else None,
        )

        if "AGENT_ERROR:" in followup_answer:
            print(f"\n❌ Follow-up failed: {followup_answer}")
            continue

        inner_json = extract_json_block(followup_answer)
        safe_answer, inner_human, inner_json, _ = ground_answer_for_display(
            state,
            followup_answer,
            inner_json,
        )

        if inner_human:
            print("\n🤖 Mentor:")
            print(inner_human)
        else:
            print("\n🤖 Mentor (Data):")
            print(safe_answer)

        history.append({"role": "assistant", "content": safe_answer})
        save_message(state.session_id, "assistant", safe_answer)
        append_to_log("--- USER FOLLOW-UP ---", user_reply)
        append_to_log("--- MENTOR FOLLOW-UP ---", safe_answer)

        if inner_json:
            save_artifact(
                state.session_id,
                "followup_structured_output",
                json.dumps(inner_json, ensure_ascii=False),
            )
