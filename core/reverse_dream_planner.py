"""Phase 11.5 — Reverse Dream / Adversarial Replay (dry-run planning layer).

A *pure*, read-only planner that proposes which past lessons/patches would be
worth attacking in a **future** adversarial replay ("Reverse Dream"), and emits a
safe, structured plan describing why and what a future run *would* check.

It never attacks anything. Concretely:

  * ``build_reverse_dream_plan`` / ``format_reverse_dream_plan_markdown`` are pure
    (they take an already-loaded list and never touch the store);
  * ``load_reverse_dream_plan`` is the only store-aware entry — it *reads* lessons
    via ``lesson_store.list_lessons`` and never mutates anything;
  * nothing here runs Dream, the mutation oracle, benchmarks, patching, or a
    model, and nothing creates/promotes/blocks/merges a lesson — including
    anti-lessons. Existing anti-lessons may be *referenced* as supporting
    evidence, never created.

Reverse Dream is **not enabled**: there is no runner here and no flag that turns
one on. Every emitted target carries the contract explicitly
(``allowed_actions == ["report_only"]`` plus a ``blocked_actions`` list). Future
execution must be gated behind explicit operator approval and a default-off
config flag introduced in a later phase.
"""
from __future__ import annotations

from typing import Any

from core import lesson_duplicates, lesson_store
from core.lesson_store import (
    KIND_ANTI_LESSON,
    KIND_LESSON,
    _now_iso,
    is_anti_lesson,
)


PLAN_TITLE = "Reverse Dream / Adversarial Replay Plan (dry run)"

# The explicit dry-run statement required by the spec; rendered in the Markdown
# and exposed as ``plan["guardrail"]``.
DRY_RUN_GUARDRAIL = (
    "This is a dry-run plan. It does not run Dream, mutation oracle, benchmarks, "
    "models, patching, or anti-lesson creation."
)

ALLOWED_ACTIONS = ("report_only",)
BLOCKED_ACTIONS = (
    "run_dream",
    "run_mutation_oracle",
    "create_anti_lesson",
    "patch",
    "benchmark",
    "model_call",
)

_HIGH_CONFIDENCE = 0.7
_BROAD_PATCH_LINES = 50
_BROAD_PATCH_FILES = 3
_DEFAULT_MAX_ITEMS = 10

# Human-readable phrasing for each deterministic risk signal.
_RISK_SIGNAL_LABELS = {
    "active_knowledge": "active knowledge the agent currently relies on",
    "high_confidence": "high-confidence lesson that may be over-trusted",
    "has_related_anti_lesson": "has a related anti-lesson describing a tempting wrong pattern",
    "anti_lesson_duplicate_warning": "related anti-lessons carry duplicate warnings",
    "broad_patch": "backed by a broad/large patch that may have side effects",
    "passed_validation": "passed validation once — re-check it still holds",
    "weak_or_missing_validation_context": "weak evidence or missing validation context",
}

# What a *future* adversarial run would check for each signal (suggestions only).
_SUGGESTED_CHECKS = {
    "active_knowledge": (
        "Schedule a future Reverse Dream run to confirm this active lesson "
        "survives adversarial mutation."
    ),
    "high_confidence": "Probe for a counterexample the high confidence may be hiding.",
    "has_related_anti_lesson": (
        "Replay the related anti-lesson's tempting wrong pattern against this lesson."
    ),
    "anti_lesson_duplicate_warning": (
        "Reconcile the duplicate anti-lessons before any future adversarial run."
    ),
    "broad_patch": "Mutate the broad patched region and confirm the lesson still holds.",
    "passed_validation": (
        "Re-run the original validation under adversarial conditions in a future "
        "Reverse Dream."
    ),
    "weak_or_missing_validation_context": (
        "Gather stronger validation evidence before trusting this lesson."
    ),
}

# Stable signal order for deterministic output.
_SIGNAL_ORDER = (
    "active_knowledge",
    "high_confidence",
    "has_related_anti_lesson",
    "anti_lesson_duplicate_warning",
    "broad_patch",
    "passed_validation",
    "weak_or_missing_validation_context",
)


# ── small pure helpers ───────────────────────────────────────────────────────


def _candidate(record: dict) -> dict:
    cand = record.get("candidate") if isinstance(record, dict) else None
    return cand if isinstance(cand, dict) else {}


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [v.strip() for v in value if isinstance(v, str) and v.strip()]


def _scope_of(record: dict) -> str:
    return "repo" if record.get("scope") == "repo" else "global"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _active(record: dict) -> bool:
    return record.get("active_knowledge_allowed") is True


def _confidence(record: dict) -> float:
    """Best-effort confidence: top-level ``confidence`` → ``evaluation.score`` →
    ``candidate.confidence``. Returns 0.0 when none are numeric."""
    top = record.get("confidence")
    if _is_number(top):
        return float(top)
    evaluation = record.get("evaluation")
    if isinstance(evaluation, dict) and _is_number(evaluation.get("score")):
        return float(evaluation["score"])
    cand = _candidate(record)
    if _is_number(cand.get("confidence")):
        return float(cand["confidence"])
    return 0.0


def _diff_changed_lines(cand: dict) -> int | None:
    stats = cand.get("diff_stats") or cand.get("diff_stat") or cand.get("diffstat")
    if isinstance(stats, dict):
        for key in ("changed_lines", "changed", "total", "line_count"):
            if _is_number(stats.get(key)):
                return int(stats[key])
    for key in (
        "diff_changed_lines",
        "diff_line_count",
        "diff_lines",
        "diff_size",
        "changed_lines",
    ):
        if _is_number(cand.get(key)):
            return int(cand[key])
    return None


def _diff_present(cand: dict) -> bool:
    if _diff_changed_lines(cand) is not None:
        return True
    return any(key in cand for key in ("diff", "patch_diff", "diffs", "diff_stats"))


def _files_count(cand: dict) -> int:
    for key in ("files_touched", "files", "changed_files"):
        value = cand.get(key)
        if isinstance(value, list):
            return len([x for x in value if x])
    return 0


def _patch_is_broad(cand: dict) -> bool:
    changed = _diff_changed_lines(cand)
    if changed is not None and changed >= _BROAD_PATCH_LINES:
        return True
    return _files_count(cand) >= _BROAD_PATCH_FILES


def _has_evidence(cand: dict) -> bool:
    return bool(_str_list(cand.get("evidence_refs")) or _str_list(cand.get("related_lesson_ids")))


def _has_validation_context(cand: dict) -> bool:
    return "validation_ok" in cand or _files_count(cand) > 0 or _diff_present(cand)


def _passed_validation(cand: dict) -> bool:
    if cand.get("validation_ok") is True:
        return True
    if cand.get("validation_passed") is True:
        return True
    if cand.get("passed") is True:
        return True
    for key in ("benchmark", "proposal", "validation"):
        sub = cand.get(key)
        if isinstance(sub, dict) and (sub.get("passed") is True or sub.get("validation_ok") is True):
            return True
    return False


# ── cross-record relationships (anti-lessons as supporting evidence) ──────────


def _duplicate_anti_ids(anti: list[dict]) -> set[str]:
    """Anti-lesson ids that carry a duplicate signal (explicit ``duplicate_of`` or
    membership in a detected duplicate group). Read-only; never writes a link."""
    ids: set[str] = set()
    for a in anti:
        if a.get("duplicate_of") and isinstance(a.get("id"), str):
            ids.add(a["id"])
    try:
        for group in lesson_duplicates.find_duplicate_groups(anti):
            for lid in group.get("lesson_ids", []):
                if isinstance(lid, str):
                    ids.add(lid)
    except Exception:
        pass
    return ids


def _related_anti_map(normals: list[dict], anti: list[dict]) -> dict[str, list[dict]]:
    """Map normal-lesson id → related anti-lessons, in both reference directions:
    an anti-lesson naming the normal in ``related_lesson_ids``, or the normal
    naming the anti-lesson."""
    out: dict[str, list[dict]] = {}
    seen: dict[str, set[str]] = {}
    for n in normals:
        nid = n.get("id")
        if isinstance(nid, str):
            out[nid] = []
            seen[nid] = set()

    def _add(nid: str, a: dict) -> None:
        aid = a.get("id")
        if nid in out and isinstance(aid, str) and aid not in seen[nid]:
            out[nid].append(a)
            seen[nid].add(aid)

    # anti -> normal
    for a in anti:
        for rid in _str_list(_candidate(a).get("related_lesson_ids")):
            _add(rid, a)
    # normal -> anti
    anti_by_id = {a.get("id"): a for a in anti if isinstance(a.get("id"), str)}
    for n in normals:
        nid = n.get("id")
        if not isinstance(nid, str):
            continue
        for rid in _str_list(_candidate(n).get("related_lesson_ids")):
            a = anti_by_id.get(rid)
            if a is not None:
                _add(nid, a)
    return out


def _normal_risk_signals(record: dict, related: list[dict], dup_anti_ids: set[str]) -> list[str]:
    cand = _candidate(record)
    signals: list[str] = []
    if _active(record):
        signals.append("active_knowledge")
    if _confidence(record) >= _HIGH_CONFIDENCE:
        signals.append("high_confidence")
    if related:
        signals.append("has_related_anti_lesson")
        if any(a.get("id") in dup_anti_ids or a.get("duplicate_of") for a in related):
            signals.append("anti_lesson_duplicate_warning")
    if _patch_is_broad(cand):
        signals.append("broad_patch")
    if _passed_validation(cand):
        signals.append("passed_validation")
    if not _has_evidence(cand) and not _has_validation_context(cand):
        signals.append("weak_or_missing_validation_context")
    # Deterministic order.
    return [s for s in _SIGNAL_ORDER if s in signals]


def _reason_to_attack(signals: list[str]) -> str:
    labels = [_RISK_SIGNAL_LABELS[s] for s in signals if s in _RISK_SIGNAL_LABELS]
    if not labels:
        return "No specific risk signal."
    return "Worth attacking later: " + "; ".join(labels) + "."


def _suggested_checks(signals: list[str]) -> list[str]:
    checks: list[str] = []
    for s in signals:
        check = _SUGGESTED_CHECKS.get(s)
        if check and check not in checks:
            checks.append(check)
    if not checks:
        checks.append(
            "Schedule a future Reverse Dream run to adversarially re-check this target."
        )
    return checks


def _build_target(record: dict, signals: list[str], related: list[dict]) -> dict:
    return {
        "target_id": record.get("id"),
        "title": _text(record.get("title")),
        "source": record.get("source"),
        "source_report": record.get("source_report"),
        "scope": _scope_of(record),
        "repo_scope_id": record.get("repo_scope_id"),
        "confidence": _confidence(record),
        "risk_signals": signals,
        "reason_to_attack": _reason_to_attack(signals),
        "suggested_future_checks": _suggested_checks(signals),
        "related_anti_lessons": [
            {
                "id": a.get("id"),
                "title": _text(a.get("title")),
                "status": a.get("status") or "candidate",
                "duplicate_of": a.get("duplicate_of"),
            }
            for a in related
        ],
        "allowed_actions": list(ALLOWED_ACTIONS),
        "blocked_actions": list(BLOCKED_ACTIONS),
    }


def _priority_key(target: dict) -> tuple:
    signals = target.get("risk_signals", [])
    return (
        -len(signals),
        0 if "active_knowledge" in signals else 1,
        -float(target.get("confidence") or 0.0),
        str(target.get("target_id") or ""),
    )


def build_reverse_dream_plan(
    records: list[dict],
    *,
    max_items: int = _DEFAULT_MAX_ITEMS,
    generated_at: str | None = None,
) -> dict:
    """Propose adversarial-replay targets from an already-loaded ``records`` list.

    Primary attack targets are **normal lessons** carrying at least one
    deterministic risk signal. Anti-lessons are never primary targets — they are
    used only as supporting evidence (``related_anti_lessons``) and otherwise
    listed under ``skipped``.

    Pure: never reads the store, never mutates input records, never calls a model
    and never executes anything. See module docstring for the safety contract.
    """
    records = [r for r in (records or []) if isinstance(r, dict)]
    anti = [r for r in records if is_anti_lesson(r)]
    normals = [r for r in records if not is_anti_lesson(r)]

    dup_anti_ids = _duplicate_anti_ids(anti)
    related_map = _related_anti_map(normals, anti)

    candidates: list[dict] = []
    skipped: list[dict] = []

    # Anti-lessons: supporting evidence only, never a primary attack target.
    for a in anti:
        skipped.append({
            "target_id": a.get("id"),
            "title": _text(a.get("title")),
            "kind": KIND_ANTI_LESSON,
            "reason": "anti-lesson — supporting evidence only, not a primary attack target",
        })

    for n in normals:
        related = related_map.get(n.get("id"), [])
        signals = _normal_risk_signals(n, related, dup_anti_ids)
        if not signals:
            skipped.append({
                "target_id": n.get("id"),
                "title": _text(n.get("title")),
                "kind": KIND_LESSON,
                "reason": "no risk signals — not worth attacking",
            })
            continue
        candidates.append(_build_target(n, signals, related))

    candidates.sort(key=_priority_key)

    max_n = max_items if isinstance(max_items, int) and max_items > 0 else _DEFAULT_MAX_ITEMS
    selected = candidates[:max_n]
    for overflow in candidates[max_n:]:
        # Explicit, not silent: capped candidates are recorded under skipped.
        skipped.append({
            "target_id": overflow["target_id"],
            "title": overflow["title"],
            "kind": KIND_LESSON,
            "reason": f"exceeds max_items cap ({max_n})",
        })

    return {
        "title": PLAN_TITLE,
        "generated_at": generated_at,
        "guardrail": DRY_RUN_GUARDRAIL,
        "total_candidates": len(candidates),
        "max_items": max_n,
        "selected_targets": selected,
        "skipped": skipped,
    }


def load_reverse_dream_plan(
    *,
    repo_path: str | None = None,
    scope: str | None = None,
    repo_scope_id: str | None = None,
    include_global: bool = True,
    max_items: int = _DEFAULT_MAX_ITEMS,
    generated_at: str | None = None,
) -> dict:
    """Read lessons from the store and build a Reverse Dream dry-run plan.

    The only store-aware entry point. It performs a single READ
    (``lesson_store.list_lessons``) in the requested scope and delegates to the
    pure ``build_reverse_dream_plan``. It never writes.
    """
    lessons = lesson_store.list_lessons(
        repo_path=repo_path,
        include_global=include_global,
        scope=scope,
        repo_scope_id=repo_scope_id,
    )
    return build_reverse_dream_plan(
        lessons,
        max_items=max_items,
        generated_at=generated_at if generated_at is not None else _now_iso(),
    )


# ── Markdown ─────────────────────────────────────────────────────────────────


def _md_escape_cell(value: Any) -> str:
    text = value if isinstance(value, str) else ("" if value is None else str(value))
    return text.replace("|", "\\|").replace("\n", " ").strip()


def _truncate(text: str, limit: int = 80) -> str:
    text = (text or "").strip()
    if len(text) > limit:
        return text[: limit - 1].rstrip() + "…"
    return text


def format_reverse_dream_plan_markdown(plan: dict) -> str:
    """Render a Reverse Dream ``plan`` dict as Markdown (pure)."""
    if not isinstance(plan, dict):
        plan = {}
    selected = plan.get("selected_targets") or []
    skipped = plan.get("skipped") or []

    lines: list[str] = []
    lines.append(f"# {plan.get('title') or PLAN_TITLE}")
    lines.append("")
    lines.append(f"_generated_at: {plan.get('generated_at') or '(not recorded)'}_")
    lines.append("")
    lines.append(f"> {plan.get('guardrail') or DRY_RUN_GUARDRAIL}")
    lines.append("")
    lines.append(f"- total candidate targets: {plan.get('total_candidates', len(selected))}")
    lines.append(
        f"- selected for this plan: {len(selected)} "
        f"(max_items={plan.get('max_items', len(selected))})"
    )
    lines.append(f"- skipped: {len(skipped)}")
    lines.append("")

    lines.append(f"## Selected targets ({len(selected)})")
    lines.append("")
    if selected:
        lines.append("| target_id | title | source | risk signals |")
        lines.append("| --- | --- | --- | --- |")
        for t in selected:
            lines.append(
                "| {id} | {title} | {source} | {signals} |".format(
                    id=_md_escape_cell(t.get("target_id")),
                    title=_md_escape_cell(_truncate(t.get("title", ""))),
                    source=_md_escape_cell(t.get("source") or "—"),
                    signals=_md_escape_cell(", ".join(t.get("risk_signals", [])) or "—"),
                )
            )
        lines.append("")
        for t in selected:
            heading = _truncate(t.get("title", "") or str(t.get("target_id") or "target"))
            lines.append(f"### {_md_escape_cell(heading)}")
            lines.append("")
            lines.append(f"- target_id: `{t.get('target_id')}`")
            lines.append(f"- reason_to_attack: {t.get('reason_to_attack', '')}")
            lines.append(f"- risk signals: {', '.join(t.get('risk_signals', [])) or '—'}")
            related = t.get("related_anti_lessons") or []
            if related:
                rel = ", ".join(f"`{a.get('id')}`" for a in related)
                lines.append(f"- related anti-lessons (supporting evidence): {rel}")
            lines.append("- suggested future adversarial checks:")
            for check in t.get("suggested_future_checks", []):
                lines.append(f"  - {check}")
            lines.append(f"- allowed actions: {', '.join(t.get('allowed_actions', []))}")
            lines.append(f"- blocked actions: {', '.join(t.get('blocked_actions', []))}")
            lines.append("")
    else:
        lines.append("_No targets selected — nothing looks worth attacking right now._")
        lines.append("")

    lines.append("## Blocked actions (enforced — this is a dry run)")
    lines.append("")
    for action in BLOCKED_ACTIONS:
        lines.append(f"- `{action}` — not performed")
    lines.append("")
    lines.append(DRY_RUN_GUARDRAIL)

    return "\n".join(lines).rstrip() + "\n"
