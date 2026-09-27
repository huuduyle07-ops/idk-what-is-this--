from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from config import CONTROL_TIME_BUDGET_SEC


@dataclass
class AgentState:
    interface: str
    mode: str
    user_input: str
    file_paths: list[str]
    primary_file: Optional[str]
    input_mode: str
    language: str
    task_type: str
    task_info: dict = field(default_factory=dict)
    session_id: int = 0
    code_source: str = ""
    code_analysis: dict = field(default_factory=dict)
    context_data: str = ""
    history_block: str = ""
    memory_block: str = ""
    current_answer: str = ""
    final_answer: str = ""
    json_block: Optional[dict[str, Any]] = None
    human_answer: str = ""
    auto_patch_result: Optional[str] = None
    validation_output: Optional[str] = None
    task_run_id: Optional[int] = None
    plan: list[dict] = field(default_factory=list)
    completed_subtasks: list[dict] = field(default_factory=list)
    mission_goal: str = ""
    is_project_input: bool = False
    repo_path: Optional[str] = None
    project_tag: str = None
    failed_patterns: list[tuple] = field(default_factory=list)
    control_result: Optional[dict[str, Any]] = None
    # PATCH.AUTHOR.LIVE.3: same baseline proof for draft, revision and gate.
    candidate_authoring_context: Optional[Any] = None
    started_at: float = field(default_factory=time.time)
    time_budget_sec: int = CONTROL_TIME_BUDGET_SEC
    patch_style: str = "safe_minimal"
    ignore_repo_dna: bool = False
    patch_policy: dict[str, Any] = field(default_factory=dict)
    patch_loop_attempts: int = 0
    patch_loop_stop_reason: Optional[str] = None
    runtime_environment: str = "auto"
    runtime_environment_custom_name: str = ""
    runtime_environment_notes: str = ""
    harness_mode: str = "normal_patch"
    harness_mode_decision: dict[str, Any] = field(default_factory=dict)
    # WAITER.LIVE.1: the deterministic task-shape route this run was assigned,
    # before any indexing, preflight validation or CONTROL localization.  An
    # empty mapping means no route was recorded, which every consumer reads as
    # "fail closed" rather than "carry on as before".
    live_route: dict[str, Any] = field(default_factory=dict)
    # Bounded document evidence acquired for a read-only route.  None on every
    # change route, where CONTROL supplies the context instead.
    analysis_evidence: Optional[Any] = None
    # ANSWER.GROUND.LIVE.1: operation-scoped evidence already acquired by the
    # active run.  The answer boundary reads these objects; it never rebuilds a
    # graph, queries an index, or traverses the repository to verify a name.
    repository_inventory: Optional[Any] = None
    repository_graph: Optional[Any] = None
    answer_grounding_evidence_current: Optional[bool] = None
    answer_entity_grounding: Optional[dict[str, Any]] = None
    # WORKER.DECL.2A shadow measurement of the final worker response: how the
    # strict one-object envelope parser and the legacy extractor each read it.
    # Observation only, populated only under the default-off flag.
    worker_patch_response: Optional[Any] = None
    # WORKER.DECL.2A.1: which output-transport strategy the draft call was
    # asked for, and how the response it produced was read.  Both stay None
    # unless the default-off emission experiment is enabled; neither is read by
    # any branch that selects, authorises or applies a patch.
    strict_envelope_transport: Optional[Any] = None
    strict_envelope_emission: Optional[Any] = None
    # WORKER.DECL.2B: frozen v2 intent from that same response.  It is shadow
    # telemetry only and never becomes the executable patch plan.
    pre_execution_intent_capture: Optional[Any] = None

    # PATCH.AUTHOR.LIVE.1 - the bounded receipt for this run's single
    # verification-guided author revision, and with it the budget counter.
    # It lives on the run rather than the payload because the payload's
    # candidate is exactly the thing a revision replaces.
    candidate_revision: Optional[Any] = None

    # ANSWER.COHERENCE.LIVE.1 - the account the author of the candidate now
    # on the payload gave of it, recorded when its response was parsed.  A
    # revision replaces the candidate and this record together, so every
    # author-facing field of the final answer names one candidate.
    candidate_presentation: Optional[Any] = None


def time_budget_exceeded(state: AgentState) -> bool:
    return (time.time() - state.started_at) > state.time_budget_sec
