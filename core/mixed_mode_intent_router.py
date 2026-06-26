"""UX.4 — Mixed Mode Intent Router Preview (report-only).

Predicts the user's intended mode (chat / instant_run / continue_from_frame /
commander_plan / clarify / reject_or_defer) from text and context using
deterministic signal matching.

Core principle: UX.4 predicts user intent only. It does not dispatch execution,
start runs, call models, apply patches, run validation or benchmarks, contact
network services, launch workers, mutate the repo, push, merge, or open PRs.

This module is stdlib-only and pure apart from ``write_mixed_mode_router_artifacts``
(which writes two report files). All analysis functions are side-effect-free.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REPORT_KIND = "mixed_mode_intent_router_preview"

#: Ordered mode identifiers — priority order for conflict resolution docs.
MODES: tuple[str, ...] = (
    "chat",
    "instant_run",
    "continue_from_frame",
    "commander_plan",
    "clarify",
    "reject_or_defer",
)

CONFIDENCE_HIGH   = "high"
CONFIDENCE_MEDIUM = "medium"
CONFIDENCE_LOW    = "low"

PREVIEW_STATUS_READY       = "ready_for_review"
PREVIEW_STATUS_NEEDS_INPUT = "needs_more_input"
PREVIEW_STATUS_BLOCKED     = "blocked"

JSON_NAME = "mixed_mode_intent_router_preview.json"
MD_NAME   = "mixed_mode_intent_router_preview.md"

GUARDRAIL_NOTE = (
    "Mixed Mode Intent Router Preview is a deterministic preview only. "
    "UX.4 predicts user intent only. It does not dispatch execution, start runs, "
    "call models, apply patches, run validation or benchmarks, contact network "
    "services, launch workers, mutate the repo, push, merge, or open PRs. "
    "Human review and explicit confirmation are required before any action."
)

_BOUNDARIES: tuple[str, ...] = (
    "UX.4 predicts user intent only.",
    "UX.4 does not dispatch execution.",
    "UX.4 does not start runs.",
    "UX.4 does not call models.",
    "UX.4 does not apply patches.",
    "UX.4 does not run validation.",
    "UX.4 does not run benchmarks.",
    "UX.4 does not contact network services.",
    "UX.4 does not launch workers.",
    "UX.4 does not mutate the repo.",
    "UX.4 does not push, merge, or open PRs.",
)


# ── Routing signal tables ─────────────────────────────────────────────────────

_CHAT_SIGNALS: tuple[str, ...] = (
    "what is", "what does", "what are", "what was",
    "why ", "why?", "explain", "should we", "is this good",
    "brainstorm", "compare ", "review this idea", "teach me",
    "how does", "difference between", "any thoughts",
    "what do you think", "could you describe", "help me understand",
)

_INSTANT_RUN_SIGNALS: tuple[str, ...] = (
    "implement", "fix ", "create ", "update ",
    "write tests", "small change",
    "add a ", "add the ", "add an ",
    "write a test", "write the test",
    "rename ", "delete ", "remove ",
)

_CONTINUE_SIGNALS: tuple[str, ...] = (
    "continue from", "resume", "previous run", "old frame",
    "that run", "from history", "use previous context",
)

_COMMANDER_SIGNALS: tuple[str, ...] = (
    "big task", "multi-step", "commander",
    "architecture", "migration", "many files",
    "full redesign", "refactor whole", "large-scale",
    "entire codebase", "autonomous project",
)

_REJECT_SIGNALS: tuple[str, ...] = (
    "auto apply", "auto push", "auto deploy",
    "bypass", "without asking", "without approval",
    "ignore safety", "skip approval", "skip review",
    "hidden background", "remote execute", "no approval needed",
    "deploy automatically", "autonomous execution",
)

_HIGH_COMPLEXITY_HINTS: frozenset[str] = frozenset({
    "high_complexity", "many_files", "high_risk",
    "complex", "large_scope", "enterprise", "cross_team",
})


# ── Per-mode next steps ───────────────────────────────────────────────────────

_ALLOWED_NEXT_STEPS: dict[str, list[str]] = {
    "chat":                ["answer_in_chat", "ask_followup_if_needed"],
    "instant_run":         ["show_instant_run_preview", "request_human_confirmation"],
    "continue_from_frame": ["open_frame_review", "show_reusable_context", "request_continuation_mode"],
    "commander_plan":      ["create_commander_contract_preview", "estimate_scope", "request_human_approval"],
    "clarify":             ["ask_clarifying_question"],
    "reject_or_defer":     ["explain_boundary", "suggest_safe_alternative"],
}

_FORBIDDEN_NEXT_STEPS: list[str] = [
    "auto_dispatch",
    "auto_apply_patch",
    "auto_run_validation",
    "auto_run_benchmark",
    "auto_call_model",
    "auto_launch_agent",
    "auto_merge",
    "auto_push",
    "remote_execute",
    "bypass_human_approval",
]

_UI_ACTIONS: dict[str, str] = {
    "chat":                "show_normal_chat_composer",
    "instant_run":         "show_instant_run_preview",
    "continue_from_frame": "open_continue_from_frame_review_panel",
    "commander_plan":      "create_commander_contract_preview",
    "clarify":             "ask_focused_clarification_question",
    "reject_or_defer":     "show_safety_boundary_explanation",
}

_MODE_DESCRIPTIONS: dict[str, str] = {
    "chat":                "User asks for explanation, advice, brainstorming, review, or discussion.",
    "instant_run":         "User asks to implement a small bounded change.",
    "continue_from_frame": "User refers to a previous run or frame and wants to continue from it.",
    "commander_plan":      "User asks for a large, risky, multi-step, multi-file, or strategic task.",
    "clarify":             "User intent is ambiguous or missing required scope.",
    "reject_or_defer":     "Input is unsafe, too broad, or would bypass approved guardrails.",
}


# ── Small helpers ─────────────────────────────────────────────────────────────

def _short_id(seed: str) -> str:
    return hashlib.sha1(seed.encode()).hexdigest()[:8]


# ── Input normalisation ───────────────────────────────────────────────────────

def normalize_router_input(raw: dict[str, Any]) -> dict[str, Any]:
    """Return a fully populated router input from a raw dict (pure, no I/O)."""
    ri: dict[str, Any] = dict(raw)
    ri.setdefault("input_id", _short_id(str(raw)))
    ri.setdefault("created_at", "")
    ri.setdefault("user_text", "")
    ri.setdefault("repo_path", ".")
    ri.setdefault("available_context", [])
    ri.setdefault("referenced_frame_id", "")
    ri.setdefault("risk_hints", [])
    ri.setdefault("operator_preferences", {})
    ri["user_text"] = str(ri["user_text"])
    return ri


# ── Scoring engine ────────────────────────────────────────────────────────────

def _score(text_lower: str, ri: dict[str, Any]) -> dict[str, int]:
    """Compute mode scores from text signals and context. Pure, no I/O."""
    scores: dict[str, int] = {m: 0 for m in MODES}

    # Reject/defer — a single match is decisive; skip all other scoring
    for sig in _REJECT_SIGNALS:
        if sig in text_lower:
            scores["reject_or_defer"] += 10
            break

    if scores["reject_or_defer"] > 0:
        return scores

    # Frame ID presence → strong continue-from-frame bias
    if ri.get("referenced_frame_id"):
        scores["continue_from_frame"] += 5

    # Continue text signals (accumulate; multiple matches strengthen confidence)
    for sig in _CONTINUE_SIGNALS:
        if sig in text_lower:
            scores["continue_from_frame"] += 3

    # Commander text signals (first match contributes)
    for sig in _COMMANDER_SIGNALS:
        if sig in text_lower:
            scores["commander_plan"] += 3
            break

    # High-complexity risk hints boost commander plan above normal implementation signals
    if ri.get("risk_hints"):
        if set(ri["risk_hints"]) & _HIGH_COMPLEXITY_HINTS:
            scores["commander_plan"] += 4

    # Chat signals (first match contributes)
    for sig in _CHAT_SIGNALS:
        if sig in text_lower:
            scores["chat"] += 3
            break

    # Instant-run signals (first match contributes)
    for sig in _INSTANT_RUN_SIGNALS:
        if sig in text_lower:
            scores["instant_run"] += 3
            break

    return scores


def _matched_signals(text_lower: str, ri: dict[str, Any]) -> list[str]:
    """Return list of matched signal descriptor strings. Pure, no I/O."""
    matched: list[str] = []

    for sig in _REJECT_SIGNALS:
        if sig in text_lower:
            matched.append(f"reject_signal:{sig!r}")
            break

    for sig in _CONTINUE_SIGNALS:
        if sig in text_lower:
            matched.append(f"continue_signal:{sig!r}")

    for sig in _COMMANDER_SIGNALS:
        if sig in text_lower:
            matched.append(f"commander_signal:{sig!r}")
            break

    for sig in _CHAT_SIGNALS:
        if sig in text_lower:
            matched.append(f"chat_signal:{sig!r}")
            break

    for sig in _INSTANT_RUN_SIGNALS:
        if sig in text_lower:
            matched.append(f"instant_run_signal:{sig!r}")
            break

    if ri.get("referenced_frame_id"):
        matched.append(f"referenced_frame_id:{ri['referenced_frame_id']!r}")

    if ri.get("risk_hints"):
        high = set(ri["risk_hints"]) & _HIGH_COMPLEXITY_HINTS
        if high:
            matched.append(f"high_complexity_hints:{','.join(sorted(high))}")

    return matched


def _decide(text_stripped: str, scores: dict[str, int]) -> tuple[str, str]:
    """Return (predicted_mode, confidence) from pre-computed scores."""
    # Reject wins immediately over everything
    if scores["reject_or_defer"] > 0:
        return "reject_or_defer", CONFIDENCE_HIGH

    # Too short / blank → clarify
    if len(text_stripped) < 10:
        return "clarify", CONFIDENCE_HIGH

    # No signals from any mode → clarify
    total = sum(v for k, v in scores.items() if k not in ("reject_or_defer", "clarify"))
    if total == 0:
        return "clarify", CONFIDENCE_MEDIUM

    # Sort non-reject, non-clarify modes by descending score
    # Python stable sort preserves MODES insertion order on ties
    candidates = sorted(
        [(m, s) for m, s in scores.items() if m not in ("reject_or_defer", "clarify")],
        key=lambda x: -x[1],
    )
    best_mode, best_score = candidates[0]
    second_score = candidates[1][1] if len(candidates) > 1 else 0

    # Two positive modes tied → conflict → clarify
    if best_score > 0 and second_score > 0 and second_score >= best_score:
        return "clarify", CONFIDENCE_MEDIUM

    if best_score > 0:
        return best_mode, CONFIDENCE_HIGH if best_score >= 5 else CONFIDENCE_MEDIUM

    return "clarify", CONFIDENCE_LOW


def _build_reasons(
    mode: str,
    matched: list[str],
    text_stripped: str,
    scores: dict[str, int],
) -> list[str]:
    reasons: list[str] = []
    if mode == "reject_or_defer":
        reasons.append("Input contains signals indicating an unsafe or unapproved autonomous action.")
    elif mode == "clarify":
        if len(text_stripped) < 10:
            reasons.append("Input is too short to determine intent.")
        elif any("chat_signal" in s for s in matched) and any("instant_run_signal" in s for s in matched):
            reasons.append("Conflicting signals: input matches both chat and implementation patterns.")
        else:
            reasons.append("No clear mode signal found; clarification is needed.")
    elif mode == "continue_from_frame":
        reasons.append("Input references a previous run, frame, or history context.")
    elif mode == "commander_plan":
        reasons.append("Input indicates a large, multi-step, or high-complexity task.")
    elif mode == "chat":
        reasons.append("Input is a question, discussion, or request for explanation.")
    elif mode == "instant_run":
        reasons.append("Input is a bounded implementation or fix request.")
    if matched:
        reasons.append(f"Matched signals: {', '.join(matched)}")
    return reasons


# ── Classifier ────────────────────────────────────────────────────────────────

def classify_mixed_mode_intent(router_input: dict[str, Any]) -> dict[str, Any]:
    """Classify user intent into a predicted mode. Pure, no I/O."""
    text         = router_input.get("user_text", "")
    text_lower   = text.lower()
    text_stripped = text.strip()

    scores  = _score(text_lower, router_input)
    matched = _matched_signals(text_lower, router_input)
    mode, confidence = _decide(text_stripped, scores)
    reasons = _build_reasons(mode, matched, text_stripped, scores)

    return {
        "router_id":            _short_id(f"{mode}:{text[:40]}:{router_input.get('input_id','')}"),
        "created_at":           router_input.get("created_at", ""),
        "repo_path":            router_input.get("repo_path", "."),
        "input_text":           text,
        "predicted_mode":       mode,
        "confidence":           confidence,
        "reasons":              reasons,
        "matched_signals":      matched,
        "missing_information":  (
            ["Clear action verb, target file/module, or task scope"]
            if mode == "clarify" else []
        ),
        "required_confirmations": [
            "Human approval required before any execution or mutation.",
        ],
        "allowed_next_steps":   list(_ALLOWED_NEXT_STEPS.get(mode, [])),
        "forbidden_next_steps": list(_FORBIDDEN_NEXT_STEPS),
        "suggested_ui_action":  _UI_ACTIONS.get(mode, ""),
        "warnings":             [],
        "guardrails":           _guardrails(),
    }


# ── Guardrails ────────────────────────────────────────────────────────────────

def _guardrails(ui_placeholder_added: bool = False) -> dict[str, Any]:
    return {
        "preview_only":                True,
        "router_dispatch_implemented": False,
        "ui_placeholder_added":        ui_placeholder_added,
        "new_route_added":             False,
        "mutation_route_added":        False,
        "backend_execution_changed":   False,
        "task_execution_performed":    False,
        "agent_launched":              False,
        "model_call_performed":        False,
        "patch_applied":               False,
        "validation_run":              False,
        "benchmark_run_performed":     False,
        "network_call_performed":      False,
        "database_write_performed":    False,
        "worker_launch_performed":     False,
        "repo_mutation_performed":     False,
        "merge_performed":             False,
    }


# ── Mode count summarizer ─────────────────────────────────────────────────────

def summarize_mode_counts(results: list[dict[str, Any]]) -> dict[str, int]:
    """Return mode → count map from classification results. Pure, no I/O."""
    counts: dict[str, int] = {m: 0 for m in MODES}
    for r in results:
        m = r.get("predicted_mode", "clarify")
        if m in counts:
            counts[m] += 1
    return counts


# ── Demo inputs ───────────────────────────────────────────────────────────────

_DEMO_INPUTS: list[dict[str, Any]] = [
    {"user_text": "what does this error mean?"},
    {"user_text": "implement UX.5 Goal Brief simplifier"},
    {"user_text": "continue from the previous run"},
    {"user_text": "plan a full architecture migration"},
    {"user_text": "ok"},
    {"user_text": "auto apply and push without asking me"},
]


# ── Report builder ────────────────────────────────────────────────────────────

def build_mixed_mode_router_preview(
    *,
    repo_path: str = ".",
    inputs: list[dict[str, Any]] | None = None,
    created_at: str = "",
    preview_id: str | None = None,
    demo: bool = False,
    ui_placeholder_added: bool = False,
) -> dict[str, Any]:
    """Build the UX.4 router preview report (pure, no I/O)."""
    pid = preview_id or _short_id(f"mmr:{repo_path}:{created_at}")

    raw_inputs = _DEMO_INPUTS if demo else (inputs or [])
    normalized = [normalize_router_input(ri) for ri in raw_inputs]
    results    = [classify_mixed_mode_intent(ri) for ri in normalized]

    mode_counts = summarize_mode_counts(results)
    ambiguous   = [r for r in results if r["predicted_mode"] == "clarify"]
    rejected    = [r for r in results if r["predicted_mode"] == "reject_or_defer"]

    warnings: list[str] = []
    if not raw_inputs:
        warnings.append("No inputs provided; report contains no routing results.")

    return {
        "report_kind":               REPORT_KIND,
        "preview_id":                pid,
        "created_at":                created_at,
        "repo_path":                 repo_path,
        "preview_status":            PREVIEW_STATUS_READY,
        "input_count":               len(results),
        "routing_results":           results,
        "mode_counts":               mode_counts,
        "ambiguous_inputs":          ambiguous,
        "rejected_or_deferred_inputs": rejected,
        "routing_policy": {
            "description": (
                "Deterministic signal-based routing from user text and context to "
                "intended mode. Reject/defer always takes priority. Tied modes escalate "
                "to clarify. No floating-point scoring; all weights are integers."
            ),
            "priority_order":      list(MODES),
            "reject_first":        True,
            "conflict_resolution": (
                "When two modes score equally (both > 0), route to clarify."
            ),
            "mode_descriptions":   _MODE_DESCRIPTIONS,
        },
        "ui_contract": {
            "mode_to_ui_action":       dict(_UI_ACTIONS),
            "note": (
                "UX.4 predicts intent; the operator confirms before any action is taken. "
                "Auto-dispatch is never triggered by the router."
            ),
            "auto_dispatch_forbidden": True,
        },
        "next_ux_steps": [
            "UX.5 — Goal Brief 4W1H Simplifier: structure task goals as Who/What/When/Why/How.",
            "UX.6 — Evidence Card Layout: surface evidence from past runs in structured card view.",
        ],
        "warnings":      warnings,
        "blockers":      [],
        "guardrails":    _guardrails(ui_placeholder_added=ui_placeholder_added),
        "guardrail_note": GUARDRAIL_NOTE,
        "boundaries":    list(_BOUNDARIES),
    }


# ── Markdown renderer ─────────────────────────────────────────────────────────

def render_mixed_mode_router_markdown(report: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Mixed Mode Intent Router Preview")
    lines.append(f"\n**Preview ID:** {report.get('preview_id')}  ")
    lines.append(f"**Created:** {report.get('created_at')}  ")
    lines.append(f"**Preview Status:** {report.get('preview_status')}  ")
    lines.append(f"**Repo:** {report.get('repo_path')}\n")

    lines.append("## Summary")
    lines.append(
        "UX.4 classifies user intent into a predicted mode using deterministic signal "
        "matching. The router is a preview only — it does not dispatch execution, start "
        "runs, or take any action. Human confirmation is required before any action.\n"
    )

    lines.append("## Routing Results")
    results = report.get("routing_results", [])
    if results:
        lines.append("| Input | Predicted Mode | Confidence | Signals |")
        lines.append("| --- | --- | --- | --- |")
        for r in results:
            text = r.get("input_text", "")[:60].replace("|", "\\|")
            mode = r.get("predicted_mode", "")
            conf = r.get("confidence", "")
            sigs = "; ".join(r.get("matched_signals", []))[:80]
            lines.append(f"| {text} | `{mode}` | {conf} | {sigs} |")
    else:
        lines.append("_No inputs provided._")
    lines.append("")

    lines.append("## Mode Counts")
    for mode, count in report.get("mode_counts", {}).items():
        lines.append(f"- `{mode}`: {count}")
    lines.append("")

    lines.append("## Ambiguous Inputs")
    ambiguous = report.get("ambiguous_inputs", [])
    if ambiguous:
        for a in ambiguous:
            txt     = a.get("input_text", "")[:80]
            reasons = "; ".join(a.get("reasons", []))
            lines.append(f"- `{txt}` — {reasons}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## Rejected or Deferred Inputs")
    rejected = report.get("rejected_or_deferred_inputs", [])
    if rejected:
        for r in rejected:
            txt     = r.get("input_text", "")[:80]
            reasons = "; ".join(r.get("reasons", []))
            lines.append(f"- `{txt}` — {reasons}")
    else:
        lines.append("_None._")
    lines.append("")

    lines.append("## Routing Policy")
    policy = report.get("routing_policy", {})
    lines.append(policy.get("description", ""))
    lines.append(f"\n**Priority order:** {', '.join(policy.get('priority_order', []))}")
    lines.append(f"\n**Conflict resolution:** {policy.get('conflict_resolution', '')}")
    lines.append("\n**Mode descriptions:**")
    for mode, desc in policy.get("mode_descriptions", {}).items():
        lines.append(f"- `{mode}`: {desc}")
    lines.append("")

    lines.append("## UI Contract")
    uc = report.get("ui_contract", {})
    lines.append(uc.get("note", ""))
    lines.append("\n**Mode → UI Action:**")
    for mode, action in uc.get("mode_to_ui_action", {}).items():
        lines.append(f"- `{mode}` → `{action}`")
    lines.append("")

    lines.append("## Next UX Steps")
    for step in report.get("next_ux_steps", []):
        lines.append(f"- {step}")
    lines.append("")

    lines.append("## Warnings")
    warnings = report.get("warnings", [])
    lines.append("\n".join(f"- {w}" for w in warnings) if warnings else "_None._")
    lines.append("")

    lines.append("## Blockers")
    blockers = report.get("blockers", [])
    lines.append("\n".join(f"- {b}" for b in blockers) if blockers else "_None._")
    lines.append("")

    lines.append("## Guardrails")
    for k, v in report.get("guardrails", {}).items():
        lines.append(f"- `{k}` = `{v}`")
    lines.append("")

    lines.append("## Boundaries")
    for b in report.get("boundaries", []):
        lines.append(f"- {b}")
    lines.append("")
    lines.append(f"> {report.get('guardrail_note', '')}")

    return "\n".join(lines)


# ── I/O writer ────────────────────────────────────────────────────────────────

def write_mixed_mode_router_artifacts(
    report: dict[str, Any],
    output_root: str,
) -> dict[str, Any]:
    """Write JSON + Markdown artifacts. Returns {ok, json_path, md_path}."""
    out = Path(output_root)
    out.mkdir(parents=True, exist_ok=True)
    jp = out / JSON_NAME
    mp = out / MD_NAME
    jp.write_text(json.dumps(report, indent=2), encoding="utf-8")
    mp.write_text(render_mixed_mode_router_markdown(report), encoding="utf-8")
    return {"ok": True, "json_path": str(jp), "md_path": str(mp)}
