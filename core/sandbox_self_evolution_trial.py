"""AUTO.1a — Sandbox Self-Evolution Trial Contract (report-only).

Defines and scores a *single* sandbox self-evolution attempt before any real
repository, remote git branch, chat approval, or external coding agent is given
more power. It answers one question with deterministic rules:

    "Would this self-improvement attempt be safe to try in a disposable
     sandbox, and would the result be reviewable by a human afterwards?"

Core principle: **self-evolution may be tested in a sandbox; self-approval is
forbidden.**

This module is pure and report-only. It takes plain values (a phase
description, an automation level, an allowed-file set, a validation plan, a
budget tier) and returns plain dicts plus operator-readable Markdown. It never:
  - launches a model or an external coding agent,
  - edits the real repository, pushes, merges, or opens a PR,
  - runs validation or the benchmark runner,
  - runs Dream or Project Evolution, makes a network call, promotes a lesson,
    imports a proposal, or launches a worker.

The CLI wrapper (``scripts/create_sandbox_self_evolution_trial.py``) is the only
piece that writes the trial artifact to disk.
"""
from __future__ import annotations

from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "sandbox_self_evolution_trial"

#: Ordered automation levels this contract defines and scores. AUTO.1a only
#: *defines and scores* these levels — it never executes any of them.
AUTOMATION_LEVELS: tuple[str, ...] = (
    "LOCAL_0_OBSERVE",
    "LOCAL_1_PREPARE",
    "SANDBOX_2_DRAFT_PATCH",
    "REMOTE_3_DRAFT_PR",
    "AUTO_4_AUTO_MERGE",
)

#: The five scored dimensions, in display order.
SCORE_DIMENSIONS: tuple[str, ...] = (
    "safety",
    "scope_control",
    "validation_plan",
    "budget",
    "reviewability",
)

#: Budget tiers, least to most powerful.
BUDGET_TIERS: tuple[str, ...] = (
    "local_only",
    "cheap_api_allowed",
    "strong_model_requires_approval",
)

#: Paths a self-evolution attempt may never include in its allowed-file set.
FORBIDDEN_FILES: tuple[str, ...] = (".env", ".git", ".agent/private", "secrets")

#: The single recommended next action a trial can carry.
NEXT_SAFE_STEPS: tuple[str, ...] = (
    "keep_report_only",
    "create_worker_assignment",
    "run_sandbox_trial_manually",
    "request_human_approval_for_external_model",
    "blocked_until_scope_is_narrowed",
    "blocked_until_validation_is_declared",
)

SELF_EVOLUTION_GUARDRAIL_NOTE = (
    "Sandbox Self-Evolution Trial is report-only: it defines and scores whether "
    "a self-improvement attempt would be safe to try in a disposable sandbox. "
    "It does not run self-evolution, launch a model or external coding agent, "
    "edit the real repository, push, merge, open a PR, run validation or the "
    "benchmark runner, run Dream or Project Evolution, make a network call, "
    "promote a lesson, import a proposal, or launch a worker. Self-evolution "
    "may be tested in a sandbox; self-approval is forbidden."
)


# ── Automation-level metadata ─────────────────────────────────────────────────
#
# ``is_implementation`` marks a level that would produce edits/a patch and so
# must declare a narrow file scope and a validation plan. ``implies_*`` marks
# what a level would do to the *real* world — these drive the safety score; the
# tool itself never performs any of them.

_LEVEL_INFO: dict[str, dict[str, Any]] = {
    "LOCAL_0_OBSERVE": {
        "rank": 0,
        "summary": "read-only checks and report generation only; no edits",
        "implies_repo_mutation": False,
        "implies_push": False,
        "implies_merge": False,
        "is_implementation": False,
        "is_sandbox_draft": False,
        "implemented": True,
        "forbidden": False,
    },
    "LOCAL_1_PREPARE": {
        "rank": 1,
        "summary": "create planning artifacts only; no code edits",
        "implies_repo_mutation": False,
        "implies_push": False,
        "implies_merge": False,
        "is_implementation": False,
        "is_sandbox_draft": False,
        "implemented": True,
        "forbidden": False,
    },
    "SANDBOX_2_DRAFT_PATCH": {
        "rank": 2,
        "summary": (
            "may create a proposed patch inside a disposable sandbox only; "
            "the real repository stays untouched"
        ),
        "implies_repo_mutation": False,
        "implies_push": False,
        "implies_merge": False,
        "is_implementation": True,
        "is_sandbox_draft": True,
        "implemented": True,
        "forbidden": False,
    },
    "REMOTE_3_DRAFT_PR": {
        "rank": 3,
        "summary": (
            "future only: may open a PR on a disposable branch after checks; "
            "not implemented in AUTO.1a"
        ),
        "implies_repo_mutation": False,
        "implies_push": True,
        "implies_merge": False,
        "is_implementation": True,
        "is_sandbox_draft": False,
        "implemented": False,
        "forbidden": False,
    },
    "AUTO_4_AUTO_MERGE": {
        "rank": 4,
        "summary": "forbidden: an automatic merge is never allowed",
        "implies_repo_mutation": True,
        "implies_push": True,
        "implies_merge": True,
        "is_implementation": True,
        "is_sandbox_draft": False,
        "implemented": False,
        "forbidden": True,
    },
}

#: Conservative fallback for an unrecognized level: cannot be reasoned about, so
#: it is treated as an implementation level and fails the safety score.
_UNKNOWN_LEVEL_INFO: dict[str, Any] = {
    "rank": -1,
    "summary": "unknown automation level",
    "implies_repo_mutation": False,
    "implies_push": False,
    "implies_merge": False,
    "is_implementation": True,
    "is_sandbox_draft": False,
    "implemented": False,
    "forbidden": False,
    "unknown": True,
}


def _level_info(level: str) -> dict[str, Any]:
    return _LEVEL_INFO.get(level, _UNKNOWN_LEVEL_INFO)


# ── Small helpers ─────────────────────────────────────────────────────────────

def _as_str_list(value: Any) -> list[str]:
    """Coerce ``None`` / str / list-of-anything into a clean ``list[str]``."""
    if value is None:
        return []
    if isinstance(value, str):
        items: list[Any] = [value]
    elif isinstance(value, (list, tuple)):
        items = list(value)
    else:
        return []
    out: list[str] = []
    for item in items:
        text = str(item).strip()
        if text:
            out.append(text)
    return out


_GLOB_CHARS = set("*?[]")
_BROAD_FILE_COUNT = 10


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip().strip("/").lower()


def _is_broad_entry(path: str) -> bool:
    """An entry is broad if it is a glob, a directory, or a whole-tree marker."""
    text = path.strip()
    if not text or text in (".", "..", "/", "./"):
        return True
    if any(ch in _GLOB_CHARS for ch in text):
        return True
    if text.endswith("/") or text.endswith("\\"):
        return True
    return False


def _is_broad_scope(allowed_files: list[str]) -> bool:
    if len(allowed_files) > _BROAD_FILE_COUNT:
        return True
    return any(_is_broad_entry(path) for path in allowed_files)


def _targets_forbidden(allowed_files: list[str]) -> bool:
    """True if any allowed path is, or sits under, a protected path."""
    forbidden = [_normalize_path(item) for item in FORBIDDEN_FILES]
    for entry in allowed_files:
        norm = _normalize_path(entry)
        parts = norm.split("/")
        for bad in forbidden:
            if norm == bad or norm.startswith(bad + "/") or bad in parts:
                return True
    return False


def _md(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


# ── Deterministic scorers ─────────────────────────────────────────────────────

def _score_safety(info: dict[str, Any], self_approval_allowed: bool) -> tuple[str, str]:
    reasons: list[str] = []
    if info.get("unknown"):
        reasons.append("unknown automation level cannot be reasoned about safely")
    if self_approval_allowed:
        reasons.append("self-approval is allowed, which is forbidden")
    if info["forbidden"]:
        reasons.append("automation level is forbidden (auto-merge)")
    if info["implies_repo_mutation"]:
        reasons.append("automation level implies a real-repository mutation")
    if info["implies_merge"]:
        reasons.append("automation level implies a merge")
    if info["implies_push"]:
        reasons.append("automation level implies a push or remote PR")
    if reasons:
        return "fail", "; ".join(reasons)
    if info["is_sandbox_draft"]:
        return (
            "warn",
            "sandbox draft-patch level may create a proposed patch inside a "
            "disposable sandbox only",
        )
    return "pass", "read-only / planning level does not mutate the real repository"


def _score_scope(info: dict[str, Any], allowed_files: list[str]) -> tuple[str, str]:
    if not info["is_implementation"]:
        return (
            "pass",
            "observe / planning level does not edit files, so a file scope is "
            "not required",
        )
    if _targets_forbidden(allowed_files):
        return (
            "fail",
            "allowed_files names a protected path; remove forbidden paths before "
            "any trial",
        )
    if not allowed_files:
        return (
            "fail",
            "an implementation / draft-patch level must declare a narrow "
            "allowed_files set, but none was given",
        )
    if _is_broad_scope(allowed_files):
        return (
            "warn",
            "allowed_files is broad (globs, directories, or too many entries); "
            "narrow it before a sandbox trial",
        )
    return "pass", "allowed_files is a narrow, explicit set"


def _score_validation(
    info: dict[str, Any], validation_commands: list[str]
) -> tuple[str, str]:
    if not info["is_implementation"]:
        return "pass", "observe / planning level does not need a validation plan"
    if not validation_commands:
        return (
            "warn",
            "no validation command is declared for an implementation / "
            "draft-patch level",
        )
    return "pass", "a validation command is declared for the sandbox trial"


def _score_budget(tier: str) -> tuple[str, str]:
    if tier == "local_only":
        return "pass", "local-only budget needs no external model"
    if tier == "cheap_api_allowed":
        return (
            "warn",
            "cheap-API budget allows a low-cost external model; confirm the cost "
            "ceiling first",
        )
    if tier == "strong_model_requires_approval":
        return (
            "warn",
            "strong-model budget needs explicit human approval before any "
            "external model is used",
        )
    return "warn", "unrecognized budget tier; treat it as needing human approval"


def _score_reviewability(
    info: dict[str, Any],
    *,
    human_approval_required: bool,
    eligible_for_auto_merge: bool,
    missing_critical_fields: list[str],
) -> tuple[str, str]:
    if info["forbidden"] or info["implies_merge"] or eligible_for_auto_merge:
        return "fail", "auto-merge would bypass human review"
    if missing_critical_fields:
        return (
            "warn",
            "trial is missing fields needed for human review: "
            + ", ".join(missing_critical_fields),
        )
    if human_approval_required:
        return "pass", "human approval is required and auto-merge is disabled"
    return "warn", "human approval is not marked as required"


# ── Verdict + next safe step ──────────────────────────────────────────────────

def _verdict(scores: dict[str, str], missing_critical_fields: list[str]) -> str:
    values = list(scores.values())
    if any(value == "fail" for value in values):
        return "blocked"
    warnings = sum(1 for value in values if value == "warn")
    if warnings >= 2 or missing_critical_fields:
        return "not_eligible_for_review"
    return "eligible_for_review"


def _next_safe_step(
    level: str,
    info: dict[str, Any],
    scores: dict[str, str],
    budget_tier: str,
) -> str:
    if info["forbidden"] or info.get("unknown") or scores["safety"] == "fail":
        return "keep_report_only"
    if scores["scope_control"] == "fail":
        return "blocked_until_scope_is_narrowed"
    if scores["validation_plan"] == "warn":
        return "blocked_until_validation_is_declared"
    if scores["scope_control"] == "warn":
        return "blocked_until_scope_is_narrowed"
    if budget_tier == "strong_model_requires_approval":
        return "request_human_approval_for_external_model"
    if level == "SANDBOX_2_DRAFT_PATCH":
        return "run_sandbox_trial_manually"
    if level == "LOCAL_1_PREPARE":
        return "create_worker_assignment"
    return "keep_report_only"


# ── Block builders ────────────────────────────────────────────────────────────

def _budget_block(tier: str) -> dict[str, Any]:
    return {
        "tier": tier,
        # local-only and strong-tier both keep external models off until a human
        # approves; only the explicit cheap-API tier pre-allows a low-cost model.
        "external_model_allowed": tier == "cheap_api_allowed",
        "strong_model_requires_approval": True,
    }


def _level_status(info: dict[str, Any]) -> str:
    if info["forbidden"]:
        return "forbidden"
    if not info["implemented"]:
        return "future_not_implemented"
    return "defined"


def _automation_level_catalog() -> list[dict[str, Any]]:
    catalog: list[dict[str, Any]] = []
    for level in AUTOMATION_LEVELS:
        info = _LEVEL_INFO[level]
        catalog.append(
            {
                "level": level,
                "rank": info["rank"],
                "summary": info["summary"],
                "status": _level_status(info),
            }
        )
    return catalog


def _boundaries() -> dict[str, bool]:
    return {
        "runs_self_evolution": False,
        "launches_models_or_agents": False,
        "edits_real_repo": False,
        "pushes_or_merges_or_opens_pr": False,
        "runs_validation_or_benchmarks": False,
        "allows_self_approval": False,
    }


# ── Record builder ────────────────────────────────────────────────────────────

def build_sandbox_self_evolution_trial(
    *,
    phase_id: str = "",
    phase_title: str = "",
    phase_summary: str = "",
    automation_level: str = "LOCAL_0_OBSERVE",
    allowed_files: Any = None,
    validation_commands: Any = None,
    budget_tier: str = "local_only",
    self_approval_allowed: bool = False,
    repo_path: str = "",
    trial_id: str = "",
    created_at: str = "",
) -> dict[str, Any]:
    """Build the complete, deterministic trial-contract record.

    All inputs are plain values; nothing on disk is read or written here. The
    returned dict carries the phase, the chosen automation level, the guardrail
    booleans, the five-dimension scorecard, a verdict, and one recommended next
    safe step. The input is never mutated.
    """
    level = str(automation_level or "").strip()
    info = _level_info(level)
    allowed = _as_str_list(allowed_files)
    validations = _as_str_list(validation_commands)
    tier = str(budget_tier or "").strip() or "local_only"
    self_approval = bool(self_approval_allowed)

    phase = {
        "id": str(phase_id or "").strip(),
        "title": str(phase_title or "").strip(),
        "summary": str(phase_summary or "").strip(),
    }
    missing_critical_fields: list[str] = []
    if not phase["id"]:
        missing_critical_fields.append("phase.id")
    if not phase["title"]:
        missing_critical_fields.append("phase.title")

    # These two are policy constants for this contract, not inputs: a human is
    # always the approver, and auto-merge is never eligible.
    human_approval_required = True
    eligible_for_auto_merge = False

    safety = _score_safety(info, self_approval)
    scope = _score_scope(info, allowed)
    validation = _score_validation(info, validations)
    budget = _score_budget(tier)
    reviewability = _score_reviewability(
        info,
        human_approval_required=human_approval_required,
        eligible_for_auto_merge=eligible_for_auto_merge,
        missing_critical_fields=missing_critical_fields,
    )

    scores = {
        "safety": safety[0],
        "scope_control": scope[0],
        "validation_plan": validation[0],
        "budget": budget[0],
        "reviewability": reviewability[0],
    }
    score_reasons = {
        "safety": safety[1],
        "scope_control": scope[1],
        "validation_plan": validation[1],
        "budget": budget[1],
        "reviewability": reviewability[1],
    }

    verdict = _verdict(scores, missing_critical_fields)
    next_step = _next_safe_step(level, info, scores, tier)
    eligible_for_human_review = verdict == "eligible_for_review"

    return {
        "report_kind": REPORT_KIND,
        "guardrail_note": SELF_EVOLUTION_GUARDRAIL_NOTE,
        "trial_id": str(trial_id or ""),
        "created_at": str(created_at or ""),
        "repo_path": str(repo_path or ""),
        "phase": phase,
        "automation_level": level,
        "automation_level_summary": info["summary"],
        "automation_levels": _automation_level_catalog(),
        # A self-evolution attempt is only ever tested inside a disposable
        # sandbox, so a sandbox is always required.
        "sandbox_required": True,
        "real_repo_modified": False,
        "push_performed": False,
        "merge_performed": False,
        "model_call_performed": False,
        "worker_launch_performed": False,
        "validation_run_by_tool": False,
        "benchmark_run_by_tool": False,
        "human_approval_required": human_approval_required,
        "self_approval_allowed": self_approval,
        "eligible_for_human_review": eligible_for_human_review,
        "eligible_for_auto_merge": eligible_for_auto_merge,
        "allowed_files": allowed,
        "forbidden_files": list(FORBIDDEN_FILES),
        "validation_commands": validations,
        "budget": _budget_block(tier),
        "score": scores,
        "score_reasons": score_reasons,
        "missing_critical_fields": missing_critical_fields,
        "verdict": verdict,
        "next_safe_step": next_step,
        "boundaries": _boundaries(),
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

_NEXT_STEP_EXPLAIN: dict[str, str] = {
    "keep_report_only": (
        "Keep this as a report only. Do not give the attempt more power yet."
    ),
    "create_worker_assignment": (
        "Turn the prepared plan into a Worker Assignment route card for a "
        "human-run worker."
    ),
    "run_sandbox_trial_manually": (
        "A human may run this sandbox trial manually in a disposable copy, then "
        "review the result before anything else."
    ),
    "request_human_approval_for_external_model": (
        "Ask a human to approve the external model budget before going further."
    ),
    "blocked_until_scope_is_narrowed": (
        "Blocked: narrow allowed_files to an explicit, small set first."
    ),
    "blocked_until_validation_is_declared": (
        "Blocked: declare at least one validation command first."
    ),
}


def render_sandbox_self_evolution_trial_markdown(record: dict[str, Any]) -> str:
    """Render the trial contract as operator-readable, report-only Markdown."""
    phase = record.get("phase") or {}
    budget = record.get("budget") or {}
    scores = record.get("score") or {}
    reasons = record.get("score_reasons") or {}

    lines: list[str] = [
        "# Sandbox Self-Evolution Trial",
        "",
        f"> {record.get('guardrail_note', SELF_EVOLUTION_GUARDRAIL_NOTE)}",
        "",
        "_Report-only: this defines and scores a sandbox self-evolution attempt. "
        "Nothing is run, launched, applied, pushed, or merged._",
        "",
        "---",
        "",
    ]

    # Summary
    phase_id = phase.get("id") or "(none)"
    phase_title = phase.get("title") or "(untitled)"
    phase_summary = phase.get("summary") or ""
    lines += ["## Summary", ""]
    lines.append(f"- **Phase:** `{_md(phase_id)}` — {_md(phase_title)}")
    if phase_summary:
        lines.append(f"  - {_md(phase_summary)}")
    lines.append(
        f"- **Automation level:** `{_md(record.get('automation_level', ''))}` — "
        f"{_md(record.get('automation_level_summary', ''))}"
    )
    lines.append(f"- **Verdict:** `{_md(record.get('verdict', ''))}`")
    lines.append(
        "- **Human approval required:** "
        f"{str(record.get('human_approval_required', True)).lower()}"
    )
    lines.append(
        "- **External model allowed:** "
        f"{str(budget.get('external_model_allowed', False)).lower()}"
    )
    lines.append(
        "- **Sandbox required:** "
        f"{str(record.get('sandbox_required', True)).lower()}"
    )
    lines.append("")

    # Scorecard
    lines += ["## Scorecard", ""]
    lines.append("| Dimension | Result | Reason |")
    lines.append("|---|---|---|")
    for dimension in SCORE_DIMENSIONS:
        result = scores.get(dimension, "")
        reason = reasons.get(dimension, "")
        lines.append(f"| {dimension} | {result} | {_md(reason)} |")
    lines.append("")

    # Automation levels — documented, never executed.
    lines += ["## Automation Levels (defined, not executed)", ""]
    lines.append("| Level | Status | Meaning |")
    lines.append("|---|---|---|")
    for entry in record.get("automation_levels") or []:
        lines.append(
            f"| `{_md(entry.get('level', ''))}` | {_md(entry.get('status', ''))} "
            f"| {_md(entry.get('summary', ''))} |"
        )
    lines.append("")

    # Boundaries
    lines += ["## Boundaries", ""]
    lines += [
        "- This trial does not run self-evolution.",
        "- This trial does not launch models or external agents.",
        "- This trial does not edit the real repo.",
        "- This trial does not push, merge, or open PRs.",
        "- This trial does not run validation or benchmarks.",
        "- Self-approval is forbidden.",
        "",
    ]

    # Next safe step
    next_step = record.get("next_safe_step", "")
    lines += ["## Next Safe Step", ""]
    lines.append(f"- **Recommended:** `{_md(next_step)}`")
    explain = _NEXT_STEP_EXPLAIN.get(str(next_step))
    if explain:
        lines.append(f"  - {explain}")
    if record.get("missing_critical_fields"):
        lines.append(
            "  - Missing fields: " + ", ".join(record["missing_critical_fields"])
        )
    lines.append("")

    return "\n".join(lines) + "\n"
