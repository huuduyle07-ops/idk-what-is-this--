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


def time_budget_exceeded(state: AgentState) -> bool:
    return (time.time() - state.started_at) > state.time_budget_sec
