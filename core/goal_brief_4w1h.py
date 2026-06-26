"""UX.5 — Goal Brief 4W1H Simplifier (report-only, preview-only).

Turns a Goal Brief into a structured 4W1H frame:
  What       — What should change?
  Why        — Why is this change needed?
  Where      — Where should the change happen?
  When stop  — When should C.A.T.T.U.S stop?
  How        — How should the result be validated?

UX.5 simplifies task intake only.  UX.5 does not dispatch execution, start
runs, call models, apply patches, run validation or benchmarks, contact
network services, launch workers, mutate the repo, push, merge, or open PRs.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

# ── Public constants ──────────────────────────────────────────────────────────
REPORT_KIND             = "goal_brief_4w1h_preview"
PREVIEW_STATUS_READY    = "ready_for_review"
PREVIEW_STATUS_NEEDS    = "needs_more_input"
PREVIEW_STATUS_BLOCKED  = "blocked"
GUARDRAIL_NOTE = (
    "UX.5 is preview-only.  It simplifies task intake and scores field "
    "completeness.  It does not execute goals, dispatch tasks, contact "
    "any external service, or grant any execution authority."
)

# ── Canonical 4W1H field IDs ──────────────────────────────────────────────────
CANONICAL_FIELDS = ("what", "why", "where", "when_stop", "how_validate")

# ── Scoring weights ───────────────────────────────────────────────────────────
_SCORE = {"strong": 20, "present": 15, "weak": 8, "missing": 0}

# ── Classification thresholds (chars stripped) ────────────────────────────────
_WEAK_MAX_LEN   = 15   # ≤15 → weak
_STRONG_MIN_LEN = 60   # >60 → strong (unless vague / field-specific fail)

# ── Vague-term sets ───────────────────────────────────────────────────────────
_VAGUE_EXACT: frozenset[str] = frozenset({
    "fix", "fix it", "do it", "do", "better", "stuff", "etc", "idk",
    "tbd", "...", "???", "broken", "it's broken", "things", "something",
    "anything", "everything", "somewhere", "anywhere", "everywhere",
    "yes", "no", "ok", "okay", "sure", "todo", "n/a", "na", "dunno",
})

# ── Discussion / exploration signals ─────────────────────────────────────────
_DISCUSSION_SIGNALS = (
    "how should we",
    "what should we",
    "what do you think",
    "what approach",
    "should we",
    "discuss",
    "brainstorm",
    "explore",
    "trade-off",
    "considerations",
    "thoughts on",
    "opinions on",
)

# ── Clarifying questions by field ─────────────────────────────────────────────
_CLARIFYING: dict[str, str] = {
    "what": (
        "What exactly should change? "
        "Be specific about the feature, fix, or behavior."
    ),
    "why": (
        "Why is this change needed now? "
        "What problem does it solve or what goal does it serve?"
    ),
    "where": (
        "Where should C.A.T.T.U.S focus first? "
        "Name a file, module, UI area, route, or workflow."
    ),
    "when_stop": (
        "What boundary tells C.A.T.T.U.S to stop? "
        "Name a scope limit, max phase, or done condition."
    ),
    "how_validate": (
        "How should the operator verify the result? "
        "Name a test, benchmark, artifact, or review step."
    ),
}

# ── Allowed / forbidden next steps ───────────────────────────────────────────
_ALLOWED_NEXT_STEPS: list[str] = [
    "review_goal_brief",
    "answer_clarifying_questions",
    "revise_goal_brief",
    "open_instant_run_preview",
    "open_commander_contract_preview",
    "save_as_frame_context",
]

_FORBIDDEN_NEXT_STEPS: list[str] = [
    "auto_dispatch",
    "auto_apply_patch",
    "auto_run_validation",
    "auto_run_benchmark",
    "auto_call_model",
    "auto_launch_worker",
    "auto_merge",
    "auto_push",
    "remote_execute",
    "bypass_human_approval",
]

# ── Guardrails ────────────────────────────────────────────────────────────────
_GUARDRAILS: dict[str, bool] = {
    "preview_only":                     True,
    "goal_brief_execution_implemented": False,
    "router_dispatch_implemented":      False,
    "new_route_added":                  False,
    "mutation_route_added":             False,
    "backend_execution_changed":        False,
    "task_execution_performed":         False,
    "agent_launched":                   False,
    "model_call_performed":             False,
    "patch_applied":                    False,
    "validation_run":                   False,
    "benchmark_run_performed":          False,
    "network_call_performed":           False,
    "database_write_performed":         False,
    "worker_launch_performed":          False,
    "repo_mutation_performed":          False,
    "merge_performed":                  False,
}

_BOUNDARIES: list[str] = [
    "UX.5 simplifies task intake only.",
    "UX.5 does not dispatch execution.",
    "UX.5 does not start runs.",
    "UX.5 does not call models.",
    "UX.5 does not apply patches.",
    "UX.5 does not run validation.",
    "UX.5 does not run benchmarks.",
    "UX.5 does not contact network services.",
    "UX.5 does not launch workers.",
    "UX.5 does not mutate the repo.",
    "UX.5 does not push, merge, or open PRs.",
]

_BRIEF_POLICY: list[str] = [
    "Operators submit a Goal Brief before each run.",
    "The brief should cover all five 4W1H dimensions.",
    "Incomplete briefs trigger clarifying questions.",
    "Completion score is advisory; operators may proceed with partial briefs.",
    "Recommended mode hint is deterministic and does not bind the operator.",
]

_UI_CONTRACT: dict[str, Any] = {
    "placeholder_only": True,
    "read_only": True,
    "no_execution": True,
    "label": "4W1H Goal Brief",
    "description": (
        "The 4W1H Goal Brief panel is a read-only preview simplifier.  "
        "It does not implement execution; human confirmation is required "
        "before any run."
    ),
}

_NEXT_UX_STEPS: list[str] = [
    "UX.6 — Evidence Card Layout: surface per-run evidence in operator-readable card format.",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Field-specific quality helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _is_vague(value: str) -> bool:
    v = value.strip().lower()
    if v in _VAGUE_EXACT:
        return True
    words = v.split()
    if len(words) <= 2 and len(v) <= 12:
        return True
    return False


def _where_has_location_hint(value: str) -> bool:
    v = value.lower()
    return (
        "/" in v
        or any(ext in v for ext in (".py", ".js", ".ts", ".html", ".css", ".json", ".yaml", ".yml"))
        or any(kw in v for kw in (
            "core/", "web/", "tests/", "scripts/", "docs/", "module",
            "route", "endpoint", "component", "ui ", "api", "class",
        ))
    )


def _how_validate_has_check(value: str) -> bool:
    v = value.lower()
    return any(kw in v for kw in (
        "pytest", "test", "check", "verify", "benchmark", "assert",
        "review", "report", "-q", "--check", "pass", "inspect",
        "screenshot", "audit", "scan", "lint",
    ))


def _when_stop_has_boundary(value: str) -> bool:
    v = value.lower()
    return any(kw in v for kw in (
        "when", "until", "all", "pass", "done", "complete", "finish",
        "stop", "max", "limit", "phase", "approved", "signed",
    ))


# ═══════════════════════════════════════════════════════════════════════════════
# Core public API
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_goal_brief(raw: dict) -> dict:
    """Return a canonical brief dict with all required keys populated."""
    raw = raw or {}
    fields = dict(raw.get("fields") or {})
    for fid in CANONICAL_FIELDS:
        if fid not in fields:
            fields[fid] = ""
    return {
        "brief_id":      str(raw.get("brief_id") or uuid.uuid4()),
        "created_at":    str(raw.get("created_at") or ""),
        "repo_path":     str(raw.get("repo_path") or "."),
        "raw_text":      str(raw.get("raw_text") or ""),
        "fields":        fields,
        "constraints":   list(raw.get("constraints") or []),
        "risk_notes":    list(raw.get("risk_notes") or []),
        "examples":      list(raw.get("examples") or []),
        "non_goals":     list(raw.get("non_goals") or []),
        "operator_notes": list(raw.get("operator_notes") or []),
    }


def classify_field_status(field_id: str, value: Any) -> str:
    """Return 'strong', 'present', 'weak', or 'missing' for a single field value."""
    if value is None or str(value).strip() == "":
        return "missing"

    v    = str(value).strip()
    vlen = len(v)

    if _is_vague(v):
        return "weak"

    # Field-specific quality gates (run before length check)
    if field_id == "where" and not _where_has_location_hint(v):
        return "weak"
    if field_id == "how_validate" and vlen < _STRONG_MIN_LEN and not _how_validate_has_check(v):
        return "weak"
    if field_id == "when_stop" and vlen < _STRONG_MIN_LEN and not _when_stop_has_boundary(v):
        return "weak"

    if vlen <= _WEAK_MAX_LEN:
        return "weak"
    if vlen >= _STRONG_MIN_LEN:
        return "strong"
    return "present"


def score_goal_brief(brief: dict) -> int:
    """Return a 0–100 completeness score for a normalized brief."""
    fields = brief.get("fields", {})
    total  = 0
    for fid in CANONICAL_FIELDS:
        status  = classify_field_status(fid, fields.get(fid))
        total  += _SCORE[status]
    return total


def find_missing_fields(brief: dict) -> list[str]:
    """Return field IDs whose status is 'missing'."""
    fields = brief.get("fields", {})
    return [
        fid for fid in CANONICAL_FIELDS
        if classify_field_status(fid, fields.get(fid)) == "missing"
    ]


def find_weak_fields(brief: dict) -> list[str]:
    """Return field IDs whose status is 'weak'."""
    fields = brief.get("fields", {})
    return [
        fid for fid in CANONICAL_FIELDS
        if classify_field_status(fid, fields.get(fid)) == "weak"
    ]


def generate_clarifying_questions(brief: dict) -> list[str]:
    """Return deterministic clarifying questions for missing and weak fields."""
    missing = set(find_missing_fields(brief))
    weak    = set(find_weak_fields(brief))
    return [
        _CLARIFYING[fid]
        for fid in CANONICAL_FIELDS
        if fid in missing or fid in weak
    ]


def build_simplified_goal_brief(brief: dict) -> dict[str, str]:
    """Return a concise 4W1H dict from a normalized brief."""
    fields = brief.get("fields", {})
    return {
        fid: (str(fields.get(fid) or "")).strip() or "(not specified)"
        for fid in CANONICAL_FIELDS
    }


def recommend_mode_hint(brief: dict) -> str:
    """Return a deterministic mode hint: instant_run_preview, commander_contract_preview, clarify, or chat."""
    fields = brief.get("fields", {})
    what   = (fields.get("what") or "").strip().lower()
    why    = (fields.get("why")  or "").strip().lower()

    # Discussion / exploration check takes priority
    if any(sig in what for sig in _DISCUSSION_SIGNALS) or \
       any(sig in why  for sig in _DISCUSSION_SIGNALS):
        return "chat"

    sc         = score_goal_brief(brief)
    risk_notes = brief.get("risk_notes", [])

    if sc < 60:
        return "clarify"
    if sc >= 80:
        return "commander_contract_preview" if risk_notes else "instant_run_preview"
    return "clarify"


# ═══════════════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════════════

def _build_brief_preview(raw_brief: dict) -> dict:
    brief         = normalize_goal_brief(raw_brief)
    field_statuses = {
        fid: classify_field_status(fid, brief["fields"].get(fid))
        for fid in CANONICAL_FIELDS
    }
    missing   = find_missing_fields(brief)
    weak      = find_weak_fields(brief)
    sc        = score_goal_brief(brief)
    questions = generate_clarifying_questions(brief)
    simplified= build_simplified_goal_brief(brief)
    hint      = recommend_mode_hint(brief)
    status    = PREVIEW_STATUS_READY if sc >= 80 else PREVIEW_STATUS_NEEDS
    return {
        "brief_id":              brief["brief_id"],
        "field_statuses":        field_statuses,
        "completion_score":      sc,
        "missing_fields":        missing,
        "weak_fields":           weak,
        "risk_flags":            list(brief.get("risk_notes", [])),
        "clarifying_questions":  questions,
        "simplified_goal_brief": simplified,
        "operator_summary": (
            f"Completion: {sc}/100.  "
            f"Suggested next: {hint.replace('_', ' ')}."
        ),
        "recommended_mode_hint": hint,
        "allowed_next_steps":    list(_ALLOWED_NEXT_STEPS),
        "forbidden_next_steps":  list(_FORBIDDEN_NEXT_STEPS),
        "warnings":              [],
        "blockers":              [],
        "guardrails":            dict(_GUARDRAILS),
        "preview_status":        status,
    }


def _aggregate_field_counts(
    brief_previews: list[dict], key: str
) -> dict[str, int]:
    counts: dict[str, int] = {fid: 0 for fid in CANONICAL_FIELDS}
    for bp in brief_previews:
        for fid in bp.get(key, []):
            counts[fid] = counts.get(fid, 0) + 1
    return counts


def _aggregate_mode_counts(brief_previews: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for bp in brief_previews:
        hint = bp.get("recommended_mode_hint", "unknown")
        counts[hint] = counts.get(hint, 0) + 1
    return counts


# ── Demo briefs ───────────────────────────────────────────────────────────────
_DEMO_BRIEFS: list[dict] = [
    {
        "brief_id":  "demo-strong",
        "created_at": "2026-06-26",
        "repo_path":  ".",
        "fields": {
            "what": (
                "Add UX.5 Goal Brief 4W1H Simplifier to the CATTUS operator cockpit "
                "to give operators a structured, actionable task intake form"
            ),
            "why": (
                "Operators struggle to describe tasks clearly before a run, causing "
                "incomplete or failed runs that waste time and budget for the team"
            ),
            "where": (
                "core/goal_brief_4w1h.py, scripts/create_goal_brief_4w1h_preview.py, "
                "tests/test_goal_brief_4w1h.py, docs/roadmap/phase_registry.json"
            ),
            "when_stop": (
                "When all 33 prescribed tests pass and the phase registry validates "
                "UX.5 as complete with status equals complete and registry is valid"
            ),
            "how_validate": (
                "python -m pytest tests/test_goal_brief_4w1h.py -q "
                "and python scripts/validate_phase_registry.py --registry docs/roadmap/phase_registry.json --json"
            ),
        },
    },
    {
        "brief_id":  "demo-weak",
        "created_at": "2026-06-26",
        "repo_path":  ".",
        "fields": {
            "what": "fix stuff",
            "why":  "broken",
        },
    },
    {
        "brief_id":   "demo-commander",
        "created_at": "2026-06-26",
        "repo_path":  ".",
        "risk_notes": ["high_complexity", "many_files", "cross_team"],
        "fields": {
            "what": (
                "Full migration of the session management layer from cookie-based "
                "to JWT across all services and deployment environments"
            ),
            "why": (
                "Cookie-based sessions do not support the new horizontal scaling "
                "architecture and fail under load beyond the current capacity limit"
            ),
            "where": (
                "web/, core/, scripts/, tests/, all service endpoints, "
                "configuration files, and deployment scripts across all environments"
            ),
            "when_stop": (
                "When all services use JWT, all existing session tests are updated and passing, "
                "and a security review is signed off by the security team lead"
            ),
            "how_validate": (
                "python -m pytest tests/ -k session -q and security audit report "
                "and load test confirming no session errors under peak traffic volume"
            ),
        },
    },
    {
        "brief_id":  "demo-discussion",
        "created_at": "2026-06-26",
        "repo_path":  ".",
        "fields": {
            "what": (
                "How should we approach the Goal Brief UX to best support operators "
                "planning large multi-phase tasks across many files?"
            ),
            "why": (
                "We want to explore trade-off options before committing to a design "
                "direction so we discuss all constraints with the team first"
            ),
        },
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Report builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_goal_brief_4w1h_preview(
    repo_path: str = ".",
    briefs: list[dict] | None = None,
    created_at: str | None = None,
    preview_id: str | None = None,
    demo: bool = False,
    ui_placeholder_added: bool = True,
) -> dict:
    """Build a 4W1H Goal Brief preview report.  Returns a report dict."""
    if demo:
        briefs = list(_DEMO_BRIEFS)

    source_briefs = list(briefs or [])
    brief_previews = [_build_brief_preview(b) for b in source_briefs]

    missing_field_counts = _aggregate_field_counts(brief_previews, "missing_fields")
    weak_field_counts    = _aggregate_field_counts(brief_previews, "weak_fields")
    recommended_mode_counts = _aggregate_mode_counts(brief_previews)
    total_questions = sum(len(bp["clarifying_questions"]) for bp in brief_previews)

    if brief_previews:
        min_score = min(bp["completion_score"] for bp in brief_previews)
        preview_status = PREVIEW_STATUS_READY if min_score >= 80 else PREVIEW_STATUS_NEEDS
        avg_score = round(
            sum(bp["completion_score"] for bp in brief_previews) / len(brief_previews), 1
        )
    else:
        preview_status = PREVIEW_STATUS_NEEDS
        avg_score = 0.0

    return {
        "report_kind":            REPORT_KIND,
        "preview_id":             str(preview_id or uuid.uuid4()),
        "created_at":             str(created_at or ""),
        "repo_path":              str(repo_path),
        "preview_status":         preview_status,
        "brief_count":            len(brief_previews),
        "brief_previews":         brief_previews,
        "average_completion_score": avg_score,
        "missing_field_counts":   missing_field_counts,
        "weak_field_counts":      weak_field_counts,
        "recommended_mode_counts": recommended_mode_counts,
        "clarifying_question_count": total_questions,
        "brief_policy":           list(_BRIEF_POLICY),
        "ui_contract":            dict(_UI_CONTRACT),
        "next_ux_steps":          list(_NEXT_UX_STEPS),
        "warnings":               [],
        "blockers":               [],
        "guardrails":             dict(_GUARDRAILS),
        "boundaries":             list(_BOUNDARIES),
        "guardrail_note":         GUARDRAIL_NOTE,
        "ui_placeholder_added":   ui_placeholder_added,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Markdown renderer
# ═══════════════════════════════════════════════════════════════════════════════

def render_goal_brief_4w1h_markdown(report: dict) -> str:
    lines: list[str] = []
    pid    = report.get("preview_id", "")
    status = report.get("preview_status", "")
    bc     = report.get("brief_count", 0)
    avg    = report.get("average_completion_score", 0)

    lines += [
        f"# Goal Brief 4W1H Preview",
        "",
        "## Summary",
        "",
        f"- **Preview ID**: {pid}",
        f"- **Preview status**: {status}",
        f"- **Brief count**: {bc}",
        f"- **Average completeness score**: {avg}/100",
        f"- **Clarifying questions**: {report.get('clarifying_question_count', 0)}",
        "",
    ]

    # ── Brief Previews ──────────────────────────────────────────────────────
    lines += ["## Brief Previews", ""]
    for bp in report.get("brief_previews", []):
        bid   = bp.get("brief_id", "?")
        sc    = bp.get("completion_score", 0)
        hint  = bp.get("recommended_mode_hint", "?")
        lines += [
            f"### Brief `{bid}`",
            "",
            f"- **Score**: {sc}/100",
            f"- **Mode hint**: {hint}",
            f"- **Status**: {bp.get('preview_status', '?')}",
            "",
        ]

    # ── 4W1H Field Status ───────────────────────────────────────────────────
    lines += ["## 4W1H Field Status", ""]
    for bp in report.get("brief_previews", []):
        bid = bp.get("brief_id", "?")
        lines.append(f"### `{bid}` field statuses")
        lines.append("")
        lines.append("| Field | Status |")
        lines.append("|-------|--------|")
        for fid, st in (bp.get("field_statuses") or {}).items():
            lines.append(f"| {fid} | {st} |")
        lines.append("")

    # ── Missing Fields ──────────────────────────────────────────────────────
    lines += ["## Missing Fields", ""]
    mfc = report.get("missing_field_counts") or {}
    if any(v > 0 for v in mfc.values()):
        for fid, cnt in mfc.items():
            if cnt > 0:
                lines.append(f"- `{fid}`: missing in {cnt} brief(s)")
    else:
        lines.append("No missing fields.")
    lines.append("")

    # ── Weak Fields ─────────────────────────────────────────────────────────
    lines += ["## Weak Fields", ""]
    wfc = report.get("weak_field_counts") or {}
    if any(v > 0 for v in wfc.values()):
        for fid, cnt in wfc.items():
            if cnt > 0:
                lines.append(f"- `{fid}`: weak in {cnt} brief(s)")
    else:
        lines.append("No weak fields.")
    lines.append("")

    # ── Clarifying Questions ─────────────────────────────────────────────────
    lines += ["## Clarifying Questions", ""]
    for bp in report.get("brief_previews", []):
        qs = bp.get("clarifying_questions", [])
        if qs:
            bid = bp.get("brief_id", "?")
            lines.append(f"### `{bid}` questions")
            lines.append("")
            for q in qs:
                lines.append(f"- {q}")
            lines.append("")

    # ── Simplified Goal Briefs ───────────────────────────────────────────────
    lines += ["## Simplified Goal Briefs", ""]
    for bp in report.get("brief_previews", []):
        bid  = bp.get("brief_id", "?")
        simp = bp.get("simplified_goal_brief") or {}
        lines += [f"### `{bid}` simplified", ""]
        for fid in CANONICAL_FIELDS:
            label = fid.replace("_", " ").title()
            lines.append(f"- **{label}**: {simp.get(fid, '(not specified)')}")
        lines.append("")

    # ── Recommended Mode Hints ───────────────────────────────────────────────
    lines += ["## Recommended Mode Hints", ""]
    rmc = report.get("recommended_mode_counts") or {}
    for hint, cnt in sorted(rmc.items()):
        lines.append(f"- `{hint}`: {cnt}")
    lines.append("")

    # ── Brief Policy ─────────────────────────────────────────────────────────
    lines += ["## Brief Policy", ""]
    for item in report.get("brief_policy", []):
        lines.append(f"- {item}")
    lines.append("")

    # ── UI Contract ──────────────────────────────────────────────────────────
    lines += ["## UI Contract", ""]
    uc = report.get("ui_contract") or {}
    lines.append(uc.get("description", "(none)"))
    lines.append("")

    # ── Next UX Steps ────────────────────────────────────────────────────────
    lines += ["## Next UX Steps", ""]
    for step in report.get("next_ux_steps", []):
        lines.append(f"- {step}")
    lines.append("")

    # ── Warnings ─────────────────────────────────────────────────────────────
    lines += ["## Warnings", ""]
    warnings = report.get("warnings") or []
    lines += ([f"- {w}" for w in warnings] if warnings else ["No warnings."])
    lines.append("")

    # ── Blockers ─────────────────────────────────────────────────────────────
    lines += ["## Blockers", ""]
    blockers = report.get("blockers") or []
    lines += ([f"- {b}" for b in blockers] if blockers else ["No blockers."])
    lines.append("")

    # ── Guardrails ───────────────────────────────────────────────────────────
    lines += ["## Guardrails", ""]
    for k, v in (report.get("guardrails") or {}).items():
        lines.append(f"- `{k}`: {v}")
    lines.append("")

    # ── Boundaries ───────────────────────────────────────────────────────────
    lines += ["## Boundaries", ""]
    for b in report.get("boundaries", []):
        lines.append(f"- {b}")
    lines.append("")

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Artifact writer
# ═══════════════════════════════════════════════════════════════════════════════

def write_goal_brief_4w1h_artifacts(report: dict, output_root: str) -> dict:
    """Write JSON + Markdown artifacts.  Returns {ok, json_path, md_path}."""
    out_dir  = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "goal_brief_4w1h_preview.json"
    md_path   = out_dir / "goal_brief_4w1h_preview.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_goal_brief_4w1h_markdown(report), encoding="utf-8")

    return {
        "ok":        True,
        "json_path": str(json_path),
        "md_path":   str(md_path),
    }
