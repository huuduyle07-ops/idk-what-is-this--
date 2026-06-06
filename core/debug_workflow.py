"""Immutable metadata for the normal debug/repair workflow stages.

Safe to import anywhere: this module has no runtime pipeline imports, no
validation/executor hooks, no web/benchmark/lesson dependencies, and no side
effects. It is a contract map only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class DebugWorkflowStage:
    name: str
    description: str
    responsibilities: Tuple[str, ...]
    modules: Tuple[str, ...]
    artifacts: Tuple[str, ...]
    approval: Tuple[str, ...]
    guardrails: Tuple[str, ...]


DEBUG_WORKFLOW_STAGES: tuple[DebugWorkflowStage, ...] = (
    DebugWorkflowStage(
        name="Intake",
        description=(
            "Capture the operator request and per-run constraints before any "
            "context, model, safety, or execution work starts."
        ),
        responsibilities=(
            "Capture repo path and confirm it points at the intended project boundary.",
            "Capture query text exactly as the operator submitted it.",
            "Capture mode/options such as reviewer versus planner, patch style, runtime environment, and repo-DNA preference.",
            "Capture validation intent from explicit validation-command text or inferred language defaults.",
            "Capture per-run toggles such as anti-lesson CONTROL request and harness/runtime options without persisting global behavior.",
        ),
        modules=(
            "web.runner.run_agent_web",
            "cli.interactive",
            "core.router",
            "core.agent_state",
            "core.goal_brief",
            "core.runtime_environment",
        ),
        artifacts=(
            "AgentState task_info and runtime fields",
            "repo_path, user_input, mode, language, patch_style",
            "optional goal_brief.json / goal_brief.md",
            "per-run anti_lesson_control metadata when requested",
        ),
        approval=(
            "Human supplies repo path and query.",
            "Human chooses run mode/options and any per-run toggles.",
            "No patch application approval is granted at intake.",
        ),
        guardrails=(
            "Do not infer permission to write from the presence of a repo path.",
            "Do not persist per-run toggles as global settings.",
            "Do not call models, validation, patching, benchmarks, or lesson mutation from intake metadata.",
        ),
    ),
    DebugWorkflowStage(
        name="Context",
        description=(
            "Assemble repo evidence and advisory memory that can inform a draft "
            "without yet producing or applying a fix."
        ),
        responsibilities=(
            "Run CONTROL prompt assembly inputs: repository inventory, graph walk, hypotheses, patch intent, and related snippets.",
            "Attach Scout snippets and Scout-selected likely files when CONTROL needs more source localization.",
            "Attach graph evidence including weighted nodes, related snippets, and project-map context.",
            "Retrieve active lessons as advisory hints only when lesson retrieval is enabled.",
            "Check optional anti-lesson eligibility without making anti-lessons default active knowledge.",
        ),
        modules=(
            "core.control_engine",
            "core.feature_context",
            "core.source_snippet_fallback",
            "core.indexer",
            "core.repo_librarian",
            "core.lesson_retrieval",
            "core.anti_lesson_control_injection",
            "graph.builder",
            "graph.weights",
        ),
        artifacts=(
            "control_result",
            "CONTROL prompt debug text under .agent/debug_last_control_prompt.txt",
            "related_snippets and scout snippets",
            "active_lessons_injected.json in replay bundles when captured",
            "phantom_limb and preflight context",
        ),
        approval=(
            "Lesson retrieval requires its existing default-off configuration gate.",
            "Anti-lesson CONTROL warnings require the server flag plus the per-run request.",
            "Context collection itself grants no permission to generate or apply a patch.",
        ),
        guardrails=(
            "Do not change CONTROL prompt composition in this metadata slice.",
            "Lessons remain advisory and lowest priority.",
            "Anti-lessons remain default-off and require their two-key gate for CONTROL warnings.",
            "Do not mutate lessons, benchmarks, validation, patch plans, or route behavior while collecting context.",
        ),
    ),
    DebugWorkflowStage(
        name="Proposal",
        description=(
            "Produce and normalize candidate answers or patch shapes while still "
            "treating them as untrusted drafts."
        ),
        responsibilities=(
            "Create the model draft for the operator query.",
            "Separate human-readable answer text from structured JSON when present.",
            "Hold a patch candidate for single-file fixes.",
            "Hold a patch plan for multi-operation fixes.",
            "Track candidate alternatives, retries, repairs, and reviewer output before safety/execution.",
        ),
        modules=(
            "core.pipeline",
            "core.prompter",
            "core.json_utils",
            "patching.patch_gates",
            "patching.patch_planner",
            "patching.patch_synthesizer",
            "agents.gemini_client",
            "agents.deepseek_client",
            "agents.ollama_client",
        ),
        artifacts=(
            "answer text",
            "json_block",
            "patch_candidate",
            "patch_plan",
            "candidate alternatives",
            "model raw response when replay captures it",
        ),
        approval=(
            "Model output is not approval.",
            "Operator approval may be required later depending on route, harness mode, and patch policy.",
            "Proposal artifacts can be reviewed without granting execution rights.",
        ),
        guardrails=(
            "Do not apply proposal output directly.",
            "Do not treat model confidence as safety approval.",
            "Do not change patch generation, model/API routing, CONTROL prompt content, or schema-repair behavior in this contract slice.",
        ),
    ),
    DebugWorkflowStage(
        name="Safety",
        description=(
            "Evaluate whether a proposed patch or validation command is allowed "
            "to proceed to execution."
        ),
        responsibilities=(
            "Run patch safety checks before writes reach the repo or temp clone.",
            "Apply the path traversal guard so patch targets cannot escape the project root.",
            "Block forbidden files and protected directories such as .env, .git, .agent, tests, benchmark definitions, and dependency/build folders.",
            "Run validation command safety checks before shell execution.",
            "Respect harness mode decisions, server/operator gates, and dangerous-write approval boundaries.",
        ),
        modules=(
            "core.patch_safety",
            "core.security",
            "core.validation_command",
            "core.harness_modes",
            "core.harness_controls",
            "policy.decision_helper",
            "web.routes.patch_routes",
        ),
        artifacts=(
            "patch_safety result",
            "harness_mode_decision",
            "validation command safety reason when blocked",
            "blocked_paths and safety reasons",
        ),
        approval=(
            "Human/operator approval is required for dangerous writes and explicit apply actions.",
            "Harness/server gates can block generation or apply even when a proposal exists.",
            "Validation command safety can block execution without asking a model to repair the command.",
        ),
        guardrails=(
            "Do not bypass evaluate_patch_safety.",
            "Do not bypass validation_command_safety_issue.",
            "Do not weaken path traversal, forbidden-file, harness, server, or operator gates.",
            "Do not change validation behavior, route behavior, Docker/subprocess lifecycle, or patch safety behavior in this contract slice.",
        ),
    ),
    DebugWorkflowStage(
        name="Execution",
        description=(
            "Apply an approved patch candidate or plan through the existing "
            "executor boundary and lifecycle wrapper."
        ),
        responsibilities=(
            "Perform patch apply only after the safety stage allows it.",
            "Use the executor for single-file patch candidates.",
            "Use the lifecycle runner around patch plans so evidence is captured.",
            "Preserve the temp clone or sandbox boundary for benchmark, Dream, worker, and imported-proposal flows.",
            "Keep rollback and apply-result semantics owned by the existing execution modules.",
        ),
        modules=(
            "core.executor",
            "patching.patch_engine",
            "patching.patch_plan_executor",
            "core.run_lifecycle",
            "core.sandbox_runner",
            "core.worker_runs",
            "core.sleeping_consultant",
            "benchmarks.run_benchmarks",
        ),
        artifacts=(
            "apply_result.json",
            "diffs",
            "rollback status",
            "patched files",
            "generated artifacts",
            "temporary repo or sandbox output",
        ),
        approval=(
            "Real-repo apply requires the existing route/policy/operator gate.",
            "External workers and Dream run in temp clones unless a later human apply path is explicitly chosen.",
            "Benchmark execution is evaluation, not approval to mutate the source repo.",
        ),
        guardrails=(
            "Do not apply patches from this metadata helper.",
            "Do not change executor, patch engine, lifecycle, sandbox, Docker, subprocess, benchmark, or worker-run behavior.",
            "Do not cross temp clone or sandbox boundaries into the real repo by accident.",
        ),
    ),
    DebugWorkflowStage(
        name="Validation",
        description=(
            "Run or record validation results and classify failures after an "
            "execution attempt."
        ),
        responsibilities=(
            "Capture validation output from the existing validator path.",
            "Record self-correct attempts when the patch loop asks for repair after a failed validation.",
            "Apply failure taxonomy as read-only classification for reports and benchmark display.",
            "Classify environment/toolchain/security-tool failures separately from code failures.",
            "Stop model repair when validation failure is caused by environment/toolchain issues.",
        ),
        modules=(
            "core.validator",
            "core.validation_command",
            "core.self_correct_loop",
            "core.failure_taxonomy",
            "patching.patch_plan_executor",
            "benchmarks.run_benchmarks",
        ),
        artifacts=(
            "validation_output.txt",
            "validation_ok / validation_passed fields",
            "self_correct_attempts.json",
            "failure taxonomy classification",
            "environment/toolchain/security-tool failure fields",
        ),
        approval=(
            "A validation pass is evidence, not automatic permission to promote memory or apply unrelated changes.",
            "Unsafe validation commands are blocked before execution.",
            "Human review is still required where the surrounding route or lesson lifecycle demands it.",
        ),
        guardrails=(
            "Do not change validation command safety.",
            "Do not change validation output classification behavior in this metadata slice.",
            "Do not run validation from the metadata helper.",
            "Do not change benchmark scoring based on failure taxonomy display fields.",
        ),
    ),
    DebugWorkflowStage(
        name="Evidence",
        description=(
            "Persist and display replayable evidence so a human can inspect what "
            "happened without re-running the workflow."
        ),
        responsibilities=(
            "Write replay bundle artifacts for lifecycle-managed runs.",
            "Store and render benchmark report output for evaluation runs.",
            "Expose diff previews for patch review.",
            "Preserve raw JSON for debugging structured responses.",
            "Show presentation evidence pack and run details without making them authoritative.",
        ),
        modules=(
            "core.replay_recorder",
            "core.run_artifacts",
            "core.replay_compare",
            "core.review_pack_generator",
            "core.benchmarks_view",
            "benchmarks.run_benchmarks",
            "scripts.build_presentation_evidence_pack",
            "web.routes.replay_routes",
            "web.app",
        ),
        artifacts=(
            "replay bundle",
            "benchmark report JSON and Markdown",
            "diff",
            "raw JSON",
            "presentation evidence pack",
            "run details",
        ),
        approval=(
            "Evidence is review material, not an apply or promotion decision.",
            "Replay compare is read-only unless a separate cleanup/apply route is explicitly used.",
            "Benchmark reports can seed follow-up queues only through existing explicit flows.",
        ),
        guardrails=(
            "Do not let evidence views execute patches, validation, benchmarks, or models.",
            "Do not change benchmark scoring or report generation behavior in this contract slice.",
            "Do not treat raw JSON or presentation evidence as operator approval.",
        ),
    ),
    DebugWorkflowStage(
        name="Learning",
        description=(
            "Turn reviewed evidence into optional advisory memory through the "
            "existing manual lesson lifecycle."
        ),
        responsibilities=(
            "Create lesson candidates only from evidence-bearing proposals or benchmark reports.",
            "Store anti-lessons as counter-knowledge that remains default-off unless explicitly gated elsewhere.",
            "Keep lesson promotion and blocking as explicit human/operator actions.",
            "Record dogfood reports as evidence about whether memory features should change.",
            "Preserve default-off memory behavior for lesson retrieval, anti-lessons, and experimental tie-breakers.",
        ),
        modules=(
            "core.lesson_auto_candidates",
            "core.lesson_store",
            "core.lesson_retrieval",
            "core.lesson_quality",
            "core.anti_lessons",
            "core.anti_lesson_retrieval_shadow",
            "core.anti_lesson_control_injection",
            "core.anti_lesson_dogfood",
            "scripts.create_lesson_from_proposal",
            "scripts.seed_lessons_from_benchmark",
        ),
        artifacts=(
            "lesson candidates",
            "active lessons",
            "blocked lessons",
            "anti-lessons",
            "dogfood reports",
            "lesson promotion/blocking records",
        ),
        approval=(
            "Human promotion is required before a candidate lesson becomes active retrieval knowledge.",
            "Human blocking is required to move lessons into blocked status.",
            "Anti-lesson CONTROL warnings require the default-off server flag plus the per-run checkbox.",
        ),
        guardrails=(
            "Do not promote, block, merge, create, or mutate lessons from the metadata helper.",
            "Do not change lesson retrieval or anti-lesson behavior in this contract slice.",
            "Do not make anti-lessons default-on.",
            "Do not let learning artifacts override user intent, repo state, validation, or patch safety.",
        ),
    ),
)


def get_debug_workflow_stages() -> tuple[DebugWorkflowStage, ...]:
    return DEBUG_WORKFLOW_STAGES


def canonical_stage_names() -> tuple[str, ...]:
    return tuple(stage.name for stage in DEBUG_WORKFLOW_STAGES)
