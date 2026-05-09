from __future__ import annotations
import sys
import os
from pathlib import Path
import json
from typing import Any, Dict, List, Optional
# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from config import TEACHING_RULES
from core.router import should_allow_ai_language_guess


# =========================
# REUSABLE PROMPT FRAGMENTS
# =========================

PROJECT_LEVEL_BEHAVIOR = """\
Project-level behavior:
- Use PROJECT MAP → SYMBOLS → DEPENDENCY/CALL CHAIN → CODE in that order.
- Group findings by module. Prefer architectural risks over style.
- Do not assume one file is enough."""

ANALYSIS_PLAN = """\
Analysis Plan: module → symbol → dependency → code."""

MEMORY_RULE = (
    "Avoid repeating past failures. Prefer strategies similar to successful fixes."
)

REVIEWER_SCHEMA = """\
{
  "summary": "...",
  "issues": [
    {"severity": "low|medium|high", "type": "bug|logic|design|style|architecture|test",
     "file": "...", "symbol": "...", "reason": "...", "fix": "..."}
  ],
  "patch_candidate": {
    "file": "...", "relative_path": "...",
    "target_node_name": "...", "target_node_kind": "function|class",
    "target_snippet": "...", "patched_snippet": "..."
  },
  "confidence": 0.0,
  "needs_escalation": false
}"""

PLANNER_SCHEMA = """\
{
  "goal": "...",
  "subtasks": [
    {"id": "S1", "action": "inspect|edit|test|refactor|validate",
     "targets": ["file"], "reason": "...", "expected_outcome": "..."}
  ],
  "risks": ["..."],
  "missing_context": ["..."],
  "confidence": 0.0
}"""
PATCH_RESPONSE_SCHEMA = """
Return JSON:
{
  "summary": "...",
  "issues": [...],
  "patch_candidate": null | {...},
  "patch_plan": null | [
    {"op": "create_file", "relative_path": "...", "content": "..."},
    {"op": "replace_snippet", "relative_path": "...", "target_snippet": "...", "patched_snippet": "..."}
  ],
  "confidence": 0.0,
  "needs_escalation": false
}
"""
# Hard cap on retrieved context to keep prompts bounded.
MAX_CONTEXT_CHARS = 12000

PATCH_OUTPUT_RULE="""
- For single-file edits to an existing file, use patch_candidate.
- For new files, multi-file edits, or API/signature changes across files, use patch_plan.
- Output either patch_candidate or patch_plan, not both.
- If using patch_plan, set patch_candidate to null.
- In safe_minimal, do not create files and do not use patch_plan.
- In balanced/vibe, patch_plan is allowed when the user asks for feature work.
For patch_candidate:
- target_snippet must be copied verbatim from provided source context.
- patched_snippet must preserve existing fields/behavior unless the user explicitly asks to remove them.
- Do not rewrite the function from memory.
"""

SCOUT_PROMPT = """
You are a repo scout. Do not write code. Do not propose patches.

Given the user request and repo inventory/symbol list, identify which files and symbols are likely needed.

User request:
{query}

Repo files:
{files}

Repo symbols:
{symbols}

OUTPUT FORMAT — STRICT:
- Return ONLY valid JSON.
- Do NOT use Markdown.
- Do NOT wrap the JSON in ```json or ``` fences.
- Do NOT include any explanation, preface, or trailing text before or after the JSON.
- The first character of your response MUST be `{{` and the last character MUST be `}}`.

Schema:
{{
  "request_type": "bug_fix | feature_extension | refactor | unknown",
  "target_concepts": ["..."],
  "likely_files": ["relative/path.ext"],
  "likely_symbols": ["file.ext::symbol"],
  "reason": "short reason"
}}

Rules:
- Do not invent files or symbols not present in the inventory.
- For feature work, include entrypoint, command handler, data model, and persistence layer if present.
- Prefer symbols directly related to the requested action.
"""

def _task_context_block(t: dict, language: str) -> str:
    return (
        f"Task: intent={t['intent']} | complexity={t['complexity']} | "
        f"input={t['input_mode']} | mode={t['mode']} | lang={language} | "
        f"project={t['is_project_input']} | repo={t['repo_path']}"
    )


def _truncate_context(text: str, limit: int = MAX_CONTEXT_CHARS) -> str:
    if not text:
        return "None"
    if len(text) <= limit:
        return text
    head = limit - 200
    return text[:head] + f"\n\n... [truncated {len(text) - head} chars] ..."


# =========================
# UTIL
# =========================

def format_history(history: List[Dict[str, str]], limit: int = 10) -> str:
    relevant = history[-limit:]
    return "\n\n".join(
        f"{item['role'].upper()}:\n{item['content']}"
        for item in relevant
    )


def _compact_code_analysis(code_analysis: dict) -> str:
    """Render a tight, line-based summary of code_analysis.

    Switched from indented JSON dump to a one-line-per-section plain text
    format — same information density, ~3-4x fewer tokens. Caps were also
    lowered (20/30 → 12/15) since values past the top hits rarely affect AI
    output for review/refine prompts.
    """
    if not code_analysis:
        return "None"

    def _names(items, key="name", limit=12):
        out = []
        for it in (items or [])[:limit]:
            if isinstance(it, dict):
                out.append(str(it.get(key, "?")))
            else:
                out.append(str(it))
        return out

    lang = code_analysis.get("language") or "unknown"
    functions = _names(code_analysis.get("functions"), limit=12)
    classes = _names(code_analysis.get("classes"), limit=12)
    imports = (code_analysis.get("imports") or [])[:15]
    symbols = code_analysis.get("symbols") or []
    sym_summary = [f"{s.get('kind','?')}:{s.get('name','?')}" for s in symbols[:15] if isinstance(s, dict)]
    fw = (code_analysis.get("framework_hints") or [])[:5]
    entry = (code_analysis.get("entry_hints") or [])[:5]

    lines = [f"lang={lang}"]
    if functions: lines.append(f"functions: {', '.join(functions)}")
    if classes:   lines.append(f"classes: {', '.join(classes)}")
    if imports:   lines.append(f"imports: {', '.join(imports)}")
    if sym_summary: lines.append(f"symbols: {', '.join(sym_summary)}")
    if fw:        lines.append(f"framework: {', '.join(fw)}")
    if entry:     lines.append(f"entry: {', '.join(entry)}")
    return "\n".join(lines)


def _task_fields(task_info: Optional[dict]) -> dict:
    task_info = task_info or {}
    return {
        "intent": task_info.get("intent", "unknown"),
        "complexity": task_info.get("complexity", "unknown"),
        "input_mode": task_info.get("input_mode", "unknown"),
        "audience": task_info.get("audience", "unknown"),
        "mode": task_info.get("mode", "unknown"),
        "language": task_info.get("language", "unknown"),
        "is_project_input": task_info.get("is_project_input", False),
        "repo_path": task_info.get("repo_path", ""),
    }


# =========================
# MAIN PROMPT
# =========================

def build_prompt(
    user_input: str,
    mode: str,
    audience: str,
    task_type: str,
    language: str,
    input_mode: str,
    code_analysis: dict,
    context_data: str,
    history_block: str,
    memory_block: str,
    task_info: Optional[dict] = None,
) -> str:
    analysis_block = _compact_code_analysis(code_analysis)
    t = _task_fields(task_info)
    framework_hints = code_analysis.get("framework_hints", [])
    entry_hints = code_analysis.get("entry_hints", [])

    context_data = context_data or ""

    if t.get("is_project_input"):
        context_data = (
            "Treat this as a project-level task. "
            "Order: PROJECT MAP → SYMBOLS → DEPENDENCY → CODE → STATE.\n\n"
            + (context_data or "")
        )

    context_data = _truncate_context(context_data)

    # -------------------------
    # HUMAN MODES
    # -------------------------
    if audience == "human":
        if mode == "tutor":
            role_block = (
                "You are a coding mentor. Teach step by step; start with one hint, "
                "at most one guiding question. Do not dump the full solution unless asked."
            )
        else:  # explainer
            role_block = (
                "You are a technical explainer. Be clear and direct. "
                "Explain why the code/design works this way and the tradeoffs."
            )

        return f"""\
{TEACHING_RULES}

{_task_context_block(t, language)} | audience=human
{MEMORY_RULE}

{role_block}

PATCH OUTPUT RULE:
{PROJECT_LEVEL_BEHAVIOR}

{ANALYSIS_PLAN}

Code signals: framework={framework_hints or "None"} | entry={entry_hints or "None"}

User input:
{user_input}

Retrieved context:
{context_data}

Code analysis summary:
{analysis_block}

Recent history:
{history_block or "None"}

Memory:
{memory_block or "None"}

If you don't know something, say so — do not hallucinate.""".strip()

    # -------------------------
    # AGENT MODES
    # -------------------------
    if audience == "agent":
        patch_style = (task_info or {}).get("patch_style", "safe_minimal")

        if patch_style in {"balanced", "vibe"}:
            schema = PATCH_RESPONSE_SCHEMA
        else:
            schema = REVIEWER_SCHEMA        
        if mode == "reviewer":
            return f"""\
You are a strict code reviewer in an agentic system.
{MEMORY_RULE}

Rules: Return ONLY valid JSON. No teaching tone, no questions, no fluff.
Be conservative; prefer minimal edits. If task is multi-file/architectural, set needs_escalation=true.
If retrieved context has PATCH INTENT, use it as grounding (convert source_snippet → target_snippet, smallest safe edit).
{should_allow_ai_language_guess(language)}

JSON shape:
{schema}

{PROJECT_LEVEL_BEHAVIOR}

{PATCH_OUTPUT_RULE}

{_task_context_block(t, language)} | framework={framework_hints or "None"} | entry={entry_hints or "None"}
{ANALYSIS_PLAN}

User input:
{user_input}

Retrieved context:
{context_data}

Code analysis summary:
{analysis_block}

Memory:
{memory_block or "None"}""".strip()

        if mode == "planner":
            return f"""\
You are a planning AI in an agentic system.
{MEMORY_RULE}
If memory contains bug_pattern about imports → insert an "inspect imports" step before editing.
If memory shows successful_fix via AST → prefer AST edits over raw string replacement.

Rules: Return ONLY valid JSON. Practical, scoped, execution-aware. Small inspect/edit/test steps.
Reflect uncertainty in missing_context and confidence.
{should_allow_ai_language_guess(language)}

JSON shape:
{PLANNER_SCHEMA}

{PROJECT_LEVEL_BEHAVIOR}

PATCH OUTPUT RULE: 
{PATCH_OUTPUT_RULE}

{_task_context_block(t, language)} | framework={framework_hints or "None"} | entry={entry_hints or "None"}
{ANALYSIS_PLAN}

User input:
{user_input}

Retrieved context:
{context_data}

Code analysis summary:
{analysis_block}

Memory:
{memory_block or "None"}""".strip()

    return "Invalid prompt configuration."


# =========================
# REVIEW / REFINE
# =========================

def build_deepseek_review(
    user_input: str,
    mode: str,
    gemini_draft: str,
    language: str,
    task_type: str,
    task_info: Optional[dict] = None,
) -> str:
    t = _task_fields(task_info)

    return f"""\
You are a strict reviewer for another model's coding response.
Check: correctness, mode fit, vagueness/risk, intent/complexity respect, framework fit.

{PROJECT_LEVEL_BEHAVIOR}

{_task_context_block(t, language)}
{ANALYSIS_PLAN}

User input:
{user_input}

Draft to review:
{gemini_draft}""".strip()


def build_refine_prompt(
    user_input: str,
    mode: str,
    audience: str,
    gemini_draft: str,
    deepseek_review: str,
    language: str,
    task_type: str,
    task_info: Optional[dict] = None,
) -> str:
    t = _task_fields(task_info)

    if audience == "agent":
        patch_style = (task_info or {}).get("patch_style", "safe_minimal")
        
        if mode == "reviewer":
            schema = PATCH_RESPONSE_SCHEMA if patch_style in {"balanced", "vibe"} else REVIEWER_SCHEMA
        else:
            schema = PLANNER_SCHEMA
        return f"""\
You are refining a machine-readable coding response.

Rules: Return ONLY valid JSON. Respect original intent/complexity. Concise, actionable.
Reflect low confidence honestly.

Reviewer-mode schema lock:
- You are in reviewer mode, not planner mode.
- Do NOT return goal, subtasks, risks, missing_context, or any planner-shaped JSON.
- If mode=reviewer, return the reviewer/patch JSON schema only.
- If source context includes a function snippet, produce patch_candidate instead of a plan.
- In safe_minimal, patch_plan is forbidden. Use patch_candidate or set patch_candidate=null.

{PROJECT_LEVEL_BEHAVIOR}

{PATCH_OUTPUT_RULE}

Grounding rules:
- If the initial draft contains a valid patch_candidate with a target_snippet copied from source, preserve that target_snippet unless it is clearly wrong.
- Never replace target_snippet with code from memory.
- If you cannot verify target_snippet from provided context, set patch_candidate=null, confidence=0.0, needs_escalation=true.
- patched_snippet must preserve existing fields/behavior unless the user explicitly asks to remove them.

{_task_context_block(t, language)} | task_type={task_type}
{ANALYSIS_PLAN}

Required JSON shape:
{schema}

Original user input:
{user_input}

Initial draft:
{gemini_draft}

Reviewer feedback:
{deepseek_review}""".strip()

    return f"""\
{TEACHING_RULES}

Refine the answer for a human user.
Rules: Clear and helpful. Respect the mode. Not verbose. Use review feedback to improve.

{PROJECT_LEVEL_BEHAVIOR}

{_task_context_block(t, language)}
{ANALYSIS_PLAN}

Original user input:
{user_input}

Initial draft:
{gemini_draft}

Reviewer feedback:
{deepseek_review}""".strip()


# =========================
# FOLLOW-UP
# =========================

def build_followup_prompt(
    history: List[Dict[str, str]],
    mode: str,
    audience: str,
    language: str,
    task_type: str,
    code_analysis: dict,
    context_data: str,
    task_info: Optional[dict] = None,
) -> str:
    convo = format_history(history)
    t = _task_fields(task_info)
    analysis_block = _compact_code_analysis(code_analysis)

    context_data = _truncate_context(context_data)

    if audience == "agent":
        schema = REVIEWER_SCHEMA if mode == "reviewer" else PLANNER_SCHEMA
        return f"""\
Continue processing the conversation as an agent-facing coding component.

Rules: Return ONLY valid JSON. Preserve continuity. Respect mode/intent. No filler.

{PROJECT_LEVEL_BEHAVIOR}

{_task_context_block(t, language)}

Required JSON shape:
{schema}

Conversation:
{convo}

Code analysis summary:
{analysis_block}

Retrieved context:
{context_data}""".strip()

    human_mode_rule = (
        "Teach progressively; avoid full answer too early."
        if mode == "tutor"
        else "Explain clearly and directly."
    )

    return f"""\
{TEACHING_RULES}

Continue the conversation. Preserve continuity, respect the mode, do not restart.
{human_mode_rule}

{PROJECT_LEVEL_BEHAVIOR}

{_task_context_block(t, language)}

Conversation:
{convo}

Code analysis summary:
{analysis_block}

Retrieved context:
{context_data}""".strip()


# =========================
# MEMORY
# =========================

def build_memory_extraction_prompt(transcript: str) -> str:
    return f"""
You are extracting durable memory for a coding agent system.

Only extract long-term useful memory.
Do NOT extract temporary details.
Return at most 3 items.

Allowed categories:
- learning_style
- project_context
- tooling_command
- repo_convention
- bug_pattern
- successful_fix

Return ONLY valid JSON:
[
  {{
    "category": "project_context",
    "note": "User is building an agentic coding system for game/dev workflows.",
    "importance": 3
  }}
]

Transcript:
{transcript}
""".strip()


# =========================
# PATCH RECHECK
# =========================

def build_patch_recheck_prompt(issues: list[str], patched_snippet: str) -> str:
    return f"""
You are checking whether a proposed patch should be revised.

Return ONLY valid JSON:
{{
  "target_snippet": "...",
  "patched_snippet": "...",
  "issue": "...",
  "risk": "low|medium|high",
  "confidence": 0.0,
  "needs_escalation": false
}}

Rules:
- Focus on correcting the patch.
- Be conservative if the patch still looks risky.
- Reflect validation feedback if provided in the issues list.

Issues:
{issues}

Patched snippet:
{patched_snippet}
""".strip()


def build_re_patch_prompt(
    failed_patch: Dict[str, Any],
    failure_info: Optional[Dict[str, str]] = None,
    validation_output: str = "",
    target_file: Optional[str] = None,
    matched_by: Optional[str] = None,
    extra_hints: Optional[List[str]] = None,
    log_char_limit: int = 1000,
) -> str:
    """Precision-Double-Tap re-patch prompt.

    Surfaces the classified failure so attempt-2 fixes the *fix*, not re-guesses
    from scratch. Truncates the validation log to keep token cost predictable
    on smaller models (Gemma, etc.).
    """
    info = failure_info or {}
    log = (validation_output or "").strip()
    if log_char_limit > 0 and len(log) > log_char_limit:
        log = log[:log_char_limit] + f"\n... [truncated {len(log) - log_char_limit} chars]"

    hint_lines = []
    if info.get("hint"):
        hint_lines.append(f"- Classifier hint: {info['hint']}")
    if matched_by:
        hint_lines.append(f"- Previous match source: {matched_by} (prefer a more exact target_snippet if this was 'literal' or 'fuzzy').")
    for h in (extra_hints or []):
        if h:
            hint_lines.append(f"- {h}")
    hint_block = "\n".join(hint_lines) if hint_lines else "- (no extra hints)"

    failed_target = failed_patch.get("target_snippet", "") or ""
    failed_patched = failed_patch.get("patched_snippet", "") or ""
    failed_issue = failed_patch.get("issue", "") or ""

    return f"""
You are repairing a patch that already failed once. Do not start over — fix the previous attempt.

### PREVIOUS FAILURE
- File: {target_file or failed_patch.get('file') or failed_patch.get('relative_path') or '(unknown)'}
- Error category: {info.get('category', 'unknown')}
- Reason: {info.get('reason', 'unknown')}
- Original issue: {failed_issue}

### FAILED PATCH (target_snippet → patched_snippet)
TARGET (must still match the file exactly):
{failed_target}

PATCHED (this is what broke):
{failed_patched}

### VALIDATION LOG (truncated to {log_char_limit} chars)
{log or '<empty>'}

### FIX HINTS
{hint_block}

### RULES
- Keep `target_snippet` byte-exact so it still matches the file. Only change it if the previous match was risky (literal/fuzzy) and you can make it more precise.
- Rewrite `patched_snippet` to address the classified failure above. Do not repeat the same broken pattern.
- Stay minimal: do not introduce unrelated edits, new files, or invented APIs.
- If the failure is environmental (missing toolchain) or you cannot fix it, set "needs_escalation": true.

Return ONLY valid JSON:
{{
  "file": "...",
  "relative_path": "...",
  "target_snippet": "...",
  "patched_snippet": "...",
  "issue": "...",
  "risk": "low|medium|high",
  "confidence": 0.0,
  "needs_escalation": false
}}
""".strip()

# =========================
# SUBTASK EXECUTION
# =========================

def build_subtask_execution_prompt(
    goal: str,
    subtask: dict,
    history_block: str,
    context_data: str,
    language: str,
    code_analysis: dict,
    memory_block: str
) -> str:
    analysis_block = _compact_code_analysis(code_analysis)
    
    return f"""
You are an execution agent performing one step of a multi-file plan.

MISSION GOAL: {goal}

CURRENT SUBTASK:
- Action: {subtask.get("action")}
- Targets: {subtask.get("targets")}
- Reason: {subtask.get("reason")}
- Expected: {subtask.get("expected_outcome")}

Rules:
- Return ONLY valid JSON.
- If the action is 'edit', return a 'patch_candidate' block.
- If the action is 'inspect', provide a summary of what you found.
- If you encounter a blocker, set 'blocked=true' and explain why.
{should_allow_ai_language_guess(language)}

Return this JSON shape:
{{
  "status": "success|failed|blocked",
  "summary": "Result of this specific step",
  "patch_candidate": {{
    "file": "...",
    "target_snippet": "...",
    "patched_snippet": "...",
    "issue": "..."
  }},
  "blocked": false,
  "blocker_reason": null
}}

Context from previous steps:
{history_block}

Current file context:
{context_data}

Code analysis summary:
{analysis_block}

Relevant memory:
{memory_block}
""".strip()

def build_replan_prompt(
    goal: str,
    original_plan: list[dict],
    completed_subtasks: list[dict],
    failed_subtask: dict,
    failure_report: str,
    language: str,
    memory_block: str,
    task_info: Optional[dict] = None,
) -> str:
    return f"""
You are replanning after a failure in an agentic coding system.
When you see past failures, you MUST avoid repeating them.
When you see successful fixes, you SHOULD prefer similar strategies.

Rules:
- Return ONLY valid JSON.
- Do NOT repeat the same failed approach.
- Adjust strategy based on failure.
- Keep steps small and executable.
- Prefer safe, incremental fixes.
{should_allow_ai_language_guess(language)}

Return JSON:
{{
  "goal": "...",
  "subtasks": [
    {{
      "id": "R1",
      "action": "inspect|edit|test|refactor|validate",
      "targets": ["file"],
      "reason": "..."
    }}
  ],
  "risks": ["..."],
  "missing_context": ["..."],
  "confidence": 0.0
}}

Goal:
{goal}

Original plan:
{original_plan}

Completed subtasks:
{completed_subtasks}

Failed subtask:
{failed_subtask}

Failure report:
{failure_report}

Language: 
{language}

Relevant engineering memory:
{memory_block}
"""

# =========================
# CONFLICT RESOLUTION
# =========================

def build_conflict_resolution_prompt(
    target_file: str,
    original_snippet: str,
    patched_snippet: str,
    current_file_content: str,
    language: str
) -> str:
    return f"""
You are a conflict resolution AI inside an agentic coding system.
A proposed patch failed to apply because the target file has drifted (modified by another process or agent).

Your task is to perform a 3-way merge and produce a cleanly resolved patch that can be safely applied to the CURRENT file content.

Rules:
- Return ONLY valid JSON.
- Provide a `patch_candidate` that specifies exactly how to edit the CURRENT file content to include the changes intended by the patched_snippet.
- `target_snippet` must exist EXACTLY in the current file content.
- `patched_snippet` should be the new intended code for that section.

Return this JSON shape:
{{
  "summary": "Explanation of how the conflict was resolved",
  "patch_candidate": {{
    "file": "{target_file}",
    "target_snippet": "...",
    "patched_snippet": "...",
    "issue": "conflict resolution"
  }}
}}

File: {target_file}
Language: {language}

ORIGINAL INTENDED PATCH:
--- TARGET ---
{original_snippet}
--- PATCHED ---
{patched_snippet}

CURRENT FILE CONTENT:
{current_file_content}
""".strip()

def build_control_patch_recheck_prompt(
    control_result: dict,
    failed_patch: dict,
    failure_report: str,
    validation_output: str = "",
) -> str:
    patch_intent = control_result.get("patch_intent") or {}
    top = control_result.get("top_hypothesis") or {}

    return f"""
You are repairing a failed patch inside a CONTROL-driven coding agent.

CONTROL HYPOTHESIS:
{json.dumps(top, ensure_ascii=False, indent=2)}

PATCH INTENT:
{json.dumps(patch_intent, ensure_ascii=False, indent=2)}

FAILED PATCH:
{json.dumps(failed_patch, ensure_ascii=False, indent=2)}

ENGINEERING MEMORY:
{json.dumps(control_result.get("engineering_memory", []), indent=2)}

FAILURE REPORT:
{failure_report}

VALIDATION OUTPUT:
{validation_output}

Rules:
- Return ONLY valid JSON.
- Do NOT change target file unless CONTROL evidence is clearly wrong.
- Use PATCH INTENT source_snippet as the grounding source.
- If previous patch failed because literal/fuzzy match was risky, make target_snippet more exact.
- If validation failed, fix logic while keeping the edit minimal.
- If source_snippet is empty, set needs_escalation=true.
- Do not invent files, symbols, APIs, or unrelated edits.
- Avoid repeating failed patterns from memory
- Prefer strategies from successful_fix

Return JSON:
{{
  "summary": "...",
  "issues": [
    {{
      "severity": "low|medium|high",
      "type": "bug|logic|design|style|architecture|test",
      "file": "...",
      "symbol": "...",
      "reason": "...",
      "fix": "..."
    }}
  ],
  "patch_candidate": {{
    "file": "...",
    "relative_path": "...",
    "target_node_name": "...",
    "target_node_kind": "function|class",
    "target_snippet": "...",
    "patched_snippet": "..."
  }},
  "confidence": 0.0,
  "needs_escalation": false
}}
""".strip()