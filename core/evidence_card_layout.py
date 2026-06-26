"""UX.6 — Evidence Card Layout (report-only, preview-only).

Builds operator-facing evidence cards that summarise:
  what changed · what evidence exists · what validation says
  what benchmark says · what risks remain · what the human should do next

UX.6 is a preview-only evidence layout phase.  UX.6 does not create new
evidence, dispatch execution, start runs, call AI services, apply patches,
run validation or benchmarks, contact network services, launch workers,
mutate the repo, push, merge, or open PRs.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

# ── Public constants ──────────────────────────────────────────────────────────
REPORT_KIND            = "evidence_card_layout_preview"
PREVIEW_STATUS_READY   = "ready_for_review"
PREVIEW_STATUS_NEEDS   = "needs_more_input"
PREVIEW_STATUS_BLOCKED = "blocked"
GUARDRAIL_NOTE = (
    "UX.6 is preview-only.  It formats evidence cards for operator review.  "
    "It does not create evidence, execute tasks, call external services, or "
    "grant any execution authority."
)

# ── Canonical card types ──────────────────────────────────────────────────────
CANONICAL_CARD_TYPES = (
    "answer_summary",
    "patch_summary",
    "changed_files",
    "validation_summary",
    "benchmark_summary",
    "risk_summary",
    "human_review",
    "next_action",
)

REQUIRED_CARD_TYPES = (
    "answer_summary",
    "patch_summary",
    "validation_summary",
    "risk_summary",
    "human_review",
    "next_action",
)

# ── Valid enumerations ────────────────────────────────────────────────────────
VALID_STATUSES       = frozenset({"pass", "warn", "fail", "missing", "info", "blocked"})
VALID_PRIORITIES     = frozenset({"high", "medium", "low"})
VALID_DISPLAY_GROUPS = frozenset({"result", "change", "checks", "risk", "decision"})

# ── Operator decision values ──────────────────────────────────────────────────
DECISION_READY     = "ready_for_human_review"
DECISION_NEEDS     = "needs_more_evidence"
DECISION_BLOCKED   = "blocked_by_failed_check"
DECISION_INSUFF    = "insufficient_information"

# ── Guardrails ────────────────────────────────────────────────────────────────
_GUARDRAILS: dict[str, bool] = {
    "preview_only":                 True,
    "evidence_layout_only":         True,
    "new_evidence_created":         False,
    "router_dispatch_implemented":  False,
    "new_route_added":              False,
    "mutation_route_added":         False,
    "backend_execution_changed":    False,
    "task_execution_performed":     False,
    "agent_launched":               False,
    "ai_service_call_performed":    False,
    "patch_applied":                False,
    "validation_run":               False,
    "benchmark_run_performed":      False,
    "network_call_performed":       False,
    "database_write_performed":     False,
    "worker_launch_performed":      False,
    "repo_mutation_performed":      False,
    "merge_performed":              False,
}

_BOUNDARIES: list[str] = [
    "UX.6 is a preview-only evidence layout phase.",
    "UX.6 does not create new evidence.",
    "UX.6 does not dispatch execution.",
    "UX.6 does not start runs.",
    "UX.6 does not call AI services.",
    "UX.6 does not apply patches.",
    "UX.6 does not run validation.",
    "UX.6 does not run benchmarks.",
    "UX.6 does not contact network services.",
    "UX.6 does not launch workers.",
    "UX.6 does not mutate the repo.",
    "UX.6 does not push, merge, or open PRs.",
]

_LAYOUT_POLICY: list[str] = [
    "Evidence cards are read-only summaries generated from existing run artifacts.",
    "Each card presents one dimension of evidence (answer, patch, checks, risk, review).",
    "Card status is advisory; the operator makes the final approval decision.",
    "Missing cards surface gaps in evidence that the operator should investigate.",
    "High-priority cards should be reviewed before approving.",
]

_UI_CONTRACT: dict[str, Any] = {
    "placeholder_only": True,
    "read_only":        True,
    "no_execution":     True,
    "label":            "Evidence Cards",
    "description": (
        "The Evidence Cards panel is a read-only layout.  "
        "Evidence creation and execution are not implemented here.  "
        "Human confirmation is required before any run."
    ),
}

_NEXT_UX_STEPS: list[str] = [
    "UX.7 — Cockpit Review / UX Branch Checkpoint: audit and freeze the UX.1-UX.6 arc.",
]


# ═══════════════════════════════════════════════════════════════════════════════
# Card normalizer
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_evidence_card(raw: dict) -> dict:
    """Return a canonical evidence card dict with all required keys populated."""
    raw = raw or {}
    return {
        "card_id":          str(raw.get("card_id") or uuid.uuid4()),
        "card_type":        str(raw.get("card_type") or "info"),
        "title":            str(raw.get("title") or ""),
        "status":           str(raw.get("status") or "info"),
        "summary":          str(raw.get("summary") or ""),
        "details":          list(raw.get("details") or []),
        "evidence_refs":    list(raw.get("evidence_refs") or []),
        "missing_evidence": list(raw.get("missing_evidence") or []),
        "risk_flags":       list(raw.get("risk_flags") or []),
        "operator_action":  str(raw.get("operator_action") or ""),
        "priority":         str(raw.get("priority") or "medium"),
        "display_group":    str(raw.get("display_group") or "result"),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Default card set
# ═══════════════════════════════════════════════════════════════════════════════

def build_default_evidence_cards(
    repo_path: str = ".",
    created_at: str | None = None,
) -> list[dict]:
    """Return a normalized set of default placeholder evidence cards."""
    raw: list[dict] = [
        {
            "card_id":          "default-answer",
            "card_type":        "answer_summary",
            "title":            "Answer Summary",
            "status":           "info",
            "summary":          "No task has been run yet.  This is a placeholder card.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": ["Run output not yet available."],
            "risk_flags":       [],
            "operator_action":  "Run a task and review the run output.",
            "priority":         "medium",
            "display_group":    "result",
        },
        {
            "card_id":          "default-patch",
            "card_type":        "patch_summary",
            "title":            "Patch Summary",
            "status":           "info",
            "summary":          "No patch has been applied.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": ["Patch diff not available."],
            "risk_flags":       [],
            "operator_action":  "Review the diff after a task run completes.",
            "priority":         "high",
            "display_group":    "change",
        },
        {
            "card_id":          "default-validation",
            "card_type":        "validation_summary",
            "title":            "Validation Summary",
            "status":           "info",
            "summary":          "No checks have been run.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": ["Test results not available."],
            "risk_flags":       [],
            "operator_action":  "Run tests and review the results.",
            "priority":         "high",
            "display_group":    "checks",
        },
        {
            "card_id":          "default-risk",
            "card_type":        "risk_summary",
            "title":            "Risk Summary",
            "status":           "info",
            "summary":          "No risk assessment available.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": ["Risk assessment not yet performed."],
            "risk_flags":       [],
            "operator_action":  "Review risks before approving.",
            "priority":         "medium",
            "display_group":    "risk",
        },
        {
            "card_id":          "default-human-review",
            "card_type":        "human_review",
            "title":            "Human Review",
            "status":           "info",
            "summary":          "Human review pending.  No task has been run yet.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": [],
            "risk_flags":       [],
            "operator_action":  "Review all cards and approve or reject.",
            "priority":         "high",
            "display_group":    "decision",
        },
        {
            "card_id":          "default-next-action",
            "card_type":        "next_action",
            "title":            "Next Action",
            "status":           "info",
            "summary":          "Run a task to generate evidence cards.",
            "details":          [],
            "evidence_refs":    [],
            "missing_evidence": [],
            "risk_flags":       [],
            "operator_action":  "Start a task run using the operator cockpit.",
            "priority":         "medium",
            "display_group":    "decision",
        },
    ]
    return [normalize_evidence_card(c) for c in raw]


# ═══════════════════════════════════════════════════════════════════════════════
# Aggregators
# ═══════════════════════════════════════════════════════════════════════════════

def summarize_card_counts(cards: list[dict]) -> dict[str, int]:
    """Return count by card_type."""
    counts: dict[str, int] = {}
    for card in cards:
        ct = card.get("card_type") or "unknown"
        counts[ct] = counts.get(ct, 0) + 1
    return counts


def summarize_status_counts(cards: list[dict]) -> dict[str, int]:
    """Return count by card status."""
    counts: dict[str, int] = {}
    for card in cards:
        st = card.get("status") or "info"
        counts[st] = counts.get(st, 0) + 1
    return counts


def find_missing_evidence_cards(cards: list[dict]) -> list[str]:
    """Return required card_type IDs that are absent or have status 'missing'."""
    present = {
        c.get("card_type")
        for c in cards
        if c.get("status") != "missing"
    }
    return [ct for ct in REQUIRED_CARD_TYPES if ct not in present]


def find_high_priority_cards(cards: list[dict]) -> list[dict]:
    """Return cards with priority == 'high'."""
    return [c for c in cards if c.get("priority") == "high"]


def build_operator_decision_summary(cards: list[dict]) -> str:
    """Return a deterministic operator decision: one of four outcomes."""
    if not cards:
        return DECISION_INSUFF
    for card in cards:
        if card.get("status") in ("fail", "blocked"):
            return DECISION_BLOCKED
    if find_missing_evidence_cards(cards):
        return DECISION_NEEDS
    return DECISION_READY


# ═══════════════════════════════════════════════════════════════════════════════
# Demo card set
# ═══════════════════════════════════════════════════════════════════════════════

_DEMO_CARDS: list[dict] = [
    {
        "card_id":          "demo-answer",
        "card_type":        "answer_summary",
        "title":            "Answer Summary",
        "status":           "pass",
        "summary":          "Added UX.5 Goal Brief 4W1H Simplifier to the CATTUS operator cockpit.",
        "details": [
            "New module: core/goal_brief_4w1h.py",
            "New script: scripts/create_goal_brief_4w1h_preview.py",
            "57 tests added and passing.",
        ],
        "evidence_refs":    [".agent/ux/goal_brief_4w1h/goal_brief_4w1h_preview.json"],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Review the simplified Goal Brief and confirm the scoring logic.",
        "priority":         "high",
        "display_group":    "result",
    },
    {
        "card_id":          "demo-patch",
        "card_type":        "patch_summary",
        "title":            "Patch Summary",
        "status":           "pass",
        "summary":          "2 new files added.  No existing files modified except registry and roadmap.",
        "details": [
            "core/goal_brief_4w1h.py (new)",
            "scripts/create_goal_brief_4w1h_preview.py (new)",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Review the diff and confirm no unintended changes.",
        "priority":         "high",
        "display_group":    "change",
    },
    {
        "card_id":          "demo-changed-files",
        "card_type":        "changed_files",
        "title":            "Changed Files",
        "status":           "info",
        "summary":          "7 files changed: core, scripts, tests, registry, web, and roadmap.",
        "details": [
            "core/goal_brief_4w1h.py (new)",
            "scripts/create_goal_brief_4w1h_preview.py (new)",
            "tests/test_goal_brief_4w1h.py (new)",
            "docs/roadmap/phase_registry.json (updated)",
            "tests/test_phase_registry.py (updated)",
            "tests/test_phase_picker.py (updated)",
            "web/templates/index.html (updated)",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Verify each changed file matches the expected scope.",
        "priority":         "medium",
        "display_group":    "change",
    },
    {
        "card_id":          "demo-validation",
        "card_type":        "validation_summary",
        "title":            "Validation Summary",
        "status":           "pass",
        "summary":          "All 57 UX.5 tests pass.  Full suite 4409/4409 passing.",
        "details": [
            "python -m pytest tests/test_goal_brief_4w1h.py -q: 57 passed",
            "python -m pytest -q: 4409 passed",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Run the test suite independently to confirm results.",
        "priority":         "high",
        "display_group":    "checks",
    },
    {
        "card_id":          "demo-benchmark",
        "card_type":        "benchmark_summary",
        "title":            "Benchmark Summary",
        "status":           "info",
        "summary":          "No benchmark required for this phase (report-only, no patch applied).",
        "details":          [],
        "evidence_refs":    [],
        "missing_evidence": ["Benchmark not applicable for report-only phases."],
        "risk_flags":       [],
        "operator_action":  "No benchmark action required for report-only phases.",
        "priority":         "low",
        "display_group":    "checks",
    },
    {
        "card_id":          "demo-risk",
        "card_type":        "risk_summary",
        "title":            "Risk Summary",
        "status":           "pass",
        "summary":          "No risks identified.  Phase is report-only with no execution authority.",
        "details": [
            "No network calls performed.",
            "No external service calls performed.",
            "No patches applied.",
            "No repo mutations performed.",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Confirm guardrails are all False before approving.",
        "priority":         "medium",
        "display_group":    "risk",
    },
    {
        "card_id":          "demo-human-review",
        "card_type":        "human_review",
        "title":            "Human Review",
        "status":           "warn",
        "summary":          "Human review pending.  All evidence collected; awaiting operator sign-off.",
        "details": [
            "Review the answer summary for correctness.",
            "Review the diff for unintended changes.",
            "Confirm all tests pass in your environment.",
            "Check risk flags are cleared.",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Approve or reject this task based on the evidence above.",
        "priority":         "high",
        "display_group":    "decision",
    },
    {
        "card_id":          "demo-next-action",
        "card_type":        "next_action",
        "title":            "Next Action",
        "status":           "info",
        "summary":          "Ready for operator review and approval.",
        "details": [
            "1. Review all evidence cards above.",
            "2. Confirm the test suite passes in your environment.",
            "3. Approve, request changes, or defer.",
        ],
        "evidence_refs":    [],
        "missing_evidence": [],
        "risk_flags":       [],
        "operator_action":  "Approve, request changes, or defer.",
        "priority":         "medium",
        "display_group":    "decision",
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Report builder
# ═══════════════════════════════════════════════════════════════════════════════

def build_evidence_card_layout_preview(
    repo_path: str = ".",
    cards: list[dict] | None = None,
    created_at: str | None = None,
    preview_id: str | None = None,
    demo: bool = False,
    ui_placeholder_added: bool = True,
) -> dict:
    """Build an Evidence Card Layout preview report.  Returns a report dict."""
    if demo:
        cards = list(_DEMO_CARDS)

    source_cards  = list(cards or [])
    norm_cards    = [normalize_evidence_card(c) for c in source_cards]

    card_counts   = summarize_card_counts(norm_cards)
    status_counts = summarize_status_counts(norm_cards)
    missing       = find_missing_evidence_cards(norm_cards)
    high_priority = find_high_priority_cards(norm_cards)
    decision      = build_operator_decision_summary(norm_cards)

    if decision == DECISION_BLOCKED:
        preview_status = PREVIEW_STATUS_BLOCKED
    elif decision in (DECISION_NEEDS, DECISION_INSUFF):
        preview_status = PREVIEW_STATUS_NEEDS
    else:
        preview_status = PREVIEW_STATUS_READY

    return {
        "report_kind":              REPORT_KIND,
        "preview_id":               str(preview_id or uuid.uuid4()),
        "created_at":               str(created_at or ""),
        "repo_path":                str(repo_path),
        "preview_status":           preview_status,
        "cards":                    norm_cards,
        "card_counts":              card_counts,
        "status_counts":            status_counts,
        "missing_evidence_cards":   missing,
        "high_priority_cards":      [c["card_id"] for c in high_priority],
        "operator_decision_summary": decision,
        "layout_policy":            list(_LAYOUT_POLICY),
        "ui_contract":              dict(_UI_CONTRACT),
        "next_ux_steps":            list(_NEXT_UX_STEPS),
        "warnings":                 [],
        "blockers":                 [],
        "guardrails":               dict(_GUARDRAILS),
        "boundaries":               list(_BOUNDARIES),
        "guardrail_note":           GUARDRAIL_NOTE,
        "ui_placeholder_added":     ui_placeholder_added,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Markdown renderer
# ═══════════════════════════════════════════════════════════════════════════════

def render_evidence_card_layout_markdown(report: dict) -> str:
    lines: list[str] = []
    pid      = report.get("preview_id", "")
    status   = report.get("preview_status", "")
    decision = report.get("operator_decision_summary", "")
    nc       = len(report.get("cards", []))

    lines += [
        "# Evidence Card Layout Preview",
        "",
        "## Summary",
        "",
        f"- **Preview ID**: {pid}",
        f"- **Preview status**: {status}",
        f"- **Card count**: {nc}",
        f"- **Operator decision**: {decision}",
        "",
    ]

    # ── Evidence Cards ──────────────────────────────────────────────────────
    lines += ["## Evidence Cards", ""]
    for card in report.get("cards", []):
        cid   = card.get("card_id", "?")
        ctype = card.get("card_type", "?")
        cst   = card.get("status", "?")
        cpri  = card.get("priority", "?")
        ctitle= card.get("title", "")
        csum  = card.get("summary", "")
        cact  = card.get("operator_action", "")
        lines += [
            f"### `{cid}` — {ctitle}",
            "",
            f"- **Type**: `{ctype}`",
            f"- **Status**: {cst}",
            f"- **Priority**: {cpri}",
            f"- **Summary**: {csum}",
        ]
        details = card.get("details", [])
        if details:
            lines.append("- **Details**:")
            for d in details:
                lines.append(f"  - {d}")
        lines.append(f"- **Action**: {cact}")
        lines.append("")

    # ── Card Counts ──────────────────────────────────────────────────────────
    lines += ["## Card Counts", ""]
    for ct, count in sorted((report.get("card_counts") or {}).items()):
        lines.append(f"- `{ct}`: {count}")
    lines.append("")

    # ── Status Counts ────────────────────────────────────────────────────────
    lines += ["## Status Counts", ""]
    for st, count in sorted((report.get("status_counts") or {}).items()):
        lines.append(f"- `{st}`: {count}")
    lines.append("")

    # ── Missing Evidence ─────────────────────────────────────────────────────
    lines += ["## Missing Evidence", ""]
    miss = report.get("missing_evidence_cards") or []
    lines += ([f"- `{m}`" for m in miss] if miss else ["No missing evidence cards."])
    lines.append("")

    # ── High Priority Cards ──────────────────────────────────────────────────
    lines += ["## High Priority Cards", ""]
    hi = report.get("high_priority_cards") or []
    lines += ([f"- `{h}`" for h in hi] if hi else ["No high-priority cards."])
    lines.append("")

    # ── Operator Decision Summary ────────────────────────────────────────────
    lines += ["## Operator Decision Summary", "", f"**{decision}**", ""]

    # ── Layout Policy ────────────────────────────────────────────────────────
    lines += ["## Layout Policy", ""]
    for p in report.get("layout_policy", []):
        lines.append(f"- {p}")
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

def write_evidence_card_layout_artifacts(report: dict, output_root: str) -> dict:
    """Write JSON + Markdown artifacts.  Returns {ok, json_path, md_path}."""
    out_dir  = Path(output_root)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "evidence_card_layout_preview.json"
    md_path   = out_dir / "evidence_card_layout_preview.md"

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_evidence_card_layout_markdown(report), encoding="utf-8")

    return {
        "ok":        True,
        "json_path": str(json_path),
        "md_path":   str(md_path),
    }
