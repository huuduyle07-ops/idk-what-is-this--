"""Phase 14.5a — Unknown Failure Category Review (read-only).

Reads a Phase 14.5 failure taxonomy derivation artifact, extracts all
cases mapped to unknown or insufficient_evidence, classifies each into a
review outcome, and proposes targeted rule improvements and new categories.
This is a report-only module — it never modifies any artifact, applies
patches, promotes lessons, calls models, writes a database, spawns
subprocesses, or affects any runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Constants ─────────────────────────────────────────────────────────────────

REVIEW_OUTCOMES: tuple[str, ...] = (
    "candidate_mapping_rule",
    "candidate_new_category",
    "environment_or_tool_noise",
    "insufficient_evidence",
    "leave_unknown",
)

READINESS_VALUES: tuple[str, ...] = (
    "ready",
    "ready_with_unknown_bucket",
    "not_ready",
)

UNKNOWN_REVIEW_GUARDRAIL_NOTE = (
    "Phase 14.5a unknown failure review is read-only: it reads an existing "
    "derivation artifact and proposes rule improvements. It does not modify "
    "any artifact, apply patches, promote lessons, run Dream automation, "
    "call any model or API, write a database, spawn subprocesses, make "
    "network calls, change taxonomy rules in production code, change "
    "benchmark scoring, or affect any runtime behavior."
)

_AUDIT_GLOB = "*_failure-taxonomy-derivation.json"
_AUDIT_DIR = Path(".agent") / "audits"

# Benchmark categories that signal an algorithm/reasoning/logic failure
# (no existing derivation category covers these cleanly)
_ALGORITHM_BENCH_CATS: frozenset[str] = frozenset({
    "algorithm",
    "algorithm_reasoning",
    "logic_error",
    "correctness",
    "callback_dispatch_ambiguity",
    "root_cause_mismatch",
    "null_guard",
    "error_handling",
    "patch_safety",
    "patch_safety_test_deletion_temptation",
    "root_cause_minimal_patch_wrong_abstraction_temptation",
    "root_cause_wrong_file_temptation",
    "validation_gap_minimal_patch",
})

# Benchmark categories that are complex structural tasks (likely need new category)
_COMPLEX_STRUCTURAL_BENCH_CATS: frozenset[str] = frozenset({
    "migration",
    "module_wiring",
    "config_mismatch",
})

# Categories that are noisy environment signals
_ENV_NOISE_BENCH_CATS: frozenset[str] = frozenset({
    "toolchain",
    "environment",
    "security",
    "security_tool",
})

# Case-name substrings → (review_outcome, suggested_existing_category)
_NAME_HINTS: list[tuple[str, str, str]] = [
    ("wrong_file", "candidate_mapping_rule", "wrong_file_or_decoy"),
    ("false_positive", "candidate_mapping_rule", "false_positive_no_patch"),
    ("no_patch", "candidate_mapping_rule", "false_positive_no_patch"),
    ("forbidden", "candidate_mapping_rule", "forbidden_file_or_scope_violation"),
    ("missing_import", "candidate_mapping_rule", "missing_import_or_dependency"),
    ("security", "candidate_mapping_rule", "security_tool_or_permission"),
    ("antivirus", "environment_or_tool_noise", "security_tool_or_permission"),
    ("toolchain", "environment_or_tool_noise", "toolchain_environment"),
]


# ── Artifact loading ──────────────────────────────────────────────────────────

def find_latest_derivation_artifact(repo_path: str | Path = ".") -> Path | None:
    """Return the newest *_failure-taxonomy-derivation.json under .agent/audits/.

    Picks the lexicographically latest name (timestamps sort correctly).
    Never raises.
    """
    audit_dir = Path(repo_path) / _AUDIT_DIR
    if not audit_dir.is_dir():
        return None
    paths = sorted(audit_dir.glob(_AUDIT_GLOB))
    return paths[-1] if paths else None


def load_derivation_artifact(path: str | Path) -> dict[str, Any] | None:
    """Load a Phase 14.5 derivation JSON artifact. Returns None on any error."""
    try:
        raw = Path(path).read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("report_kind") != "failure_taxonomy_derivation":
        return None
    return data


# ── Unknown case extraction ───────────────────────────────────────────────────

def extract_unknown_cases(derivation: dict[str, Any]) -> list[dict[str, Any]]:
    """Return all classified cases whose category is unknown-like or low-confidence.

    Includes:
    - ``assigned_category`` in {unknown, insufficient_evidence}
    - ``confidence`` == "low" (not already caught above but signals review need)

    Items from ``unmapped_cases`` without a full classified entry are also
    folded in, deduplicated by (name, source_report).
    """
    classified = derivation.get("classified_cases") or []
    unmapped = derivation.get("unmapped_cases") or []

    seen: set[tuple[str, str]] = set()
    results: list[dict[str, Any]] = []

    for case in classified:
        if not isinstance(case, dict):
            continue
        cat = str(case.get("assigned_category") or "")
        conf = str(case.get("confidence") or "")
        if cat in ("unknown", "insufficient_evidence") or conf == "low":
            key = (str(case.get("name") or ""), str(case.get("source_report") or ""))
            if key not in seen:
                seen.add(key)
                results.append(dict(case))

    # Fold in unmapped entries not already captured
    for u in unmapped:
        if not isinstance(u, dict):
            continue
        key = (str(u.get("name") or ""), str(u.get("source_report") or ""))
        if key not in seen:
            seen.add(key)
            results.append({
                "name": u.get("name", ""),
                "source_report": u.get("source_report", ""),
                "language": "",
                "bench_category": "",
                "assigned_category": "unknown",
                "confidence": "low",
                "evidence": [],
                "deterministic": False,
            })

    return results


# ── Review classification ─────────────────────────────────────────────────────

def _classify_review_outcome(
    bench_cat: str,
    case_name: str,
    evidence: list[str],
) -> tuple[str, str, str, str | None]:
    """Return (review_outcome, suspected_reason, recommended_action, suggested_category).

    All rules are deterministic. The first matching rule wins.
    ``suggested_category`` is an existing taxonomy category or None.
    """
    name_lower = case_name.lower()
    bench_lower = bench_cat.lower()

    # 1. Environment / tool noise
    if bench_lower in _ENV_NOISE_BENCH_CATS:
        return (
            "environment_or_tool_noise",
            f"benchmark category {bench_cat!r} is an environment/tool signal",
            "environment_issue",
            "security_tool_or_permission",
        )

    # 2. Case name hints (checked before bench category so explicit names take priority)
    for substr, outcome, suggested_cat in _NAME_HINTS:
        if substr in name_lower:
            return (
                outcome,
                f"case name contains {substr!r}",
                "add_mapping_rule" if outcome == "candidate_mapping_rule" else "environment_issue",
                suggested_cat,
            )

    # 3. Algorithm / logic bench category → propose rule extension
    if bench_lower in _ALGORITHM_BENCH_CATS:
        return (
            "candidate_mapping_rule",
            (
                f"benchmark category {bench_cat!r} maps to algorithm/logic failure pattern; "
                "no existing derivation category covers this yet"
            ),
            "add_mapping_rule",
            None,
        )

    # 4. Complex structural bench category → propose new category
    if bench_lower in _COMPLEX_STRUCTURAL_BENCH_CATS:
        return (
            "candidate_new_category",
            (
                f"benchmark category {bench_cat!r} represents a structural/migration task; "
                "no existing derivation category is a close fit"
            ),
            "add_new_category",
            None,
        )

    # 5. No bench category and no evidence
    if not bench_cat and not evidence:
        return (
            "insufficient_evidence",
            "no benchmark category and no failure evidence",
            "needs_manual_review",
            None,
        )

    # 6. Fallthrough — leave unknown
    return (
        "leave_unknown",
        "too rare or ambiguous to categorize safely",
        "leave_unknown",
        None,
    )


def review_unknown_case(case: dict[str, Any]) -> dict[str, Any]:
    """Classify a single unknown case into a review outcome.

    Returns a review entry dict. Input is never mutated.
    """
    bench_cat = str(case.get("bench_category") or "").strip()
    name = str(case.get("name") or "").strip()
    evidence = list(case.get("evidence") or [])

    review_outcome, suspected_reason, recommended_action, suggested_cat = (
        _classify_review_outcome(bench_cat, name, evidence)
    )

    rule_suggestion: dict[str, Any] | None = None
    if review_outcome == "candidate_mapping_rule":
        rule_suggestion = _make_rule_suggestion(bench_cat, name, suggested_cat)

    return {
        "name": name,
        "language": str(case.get("language") or ""),
        "bench_category": bench_cat,
        "source_report": str(case.get("source_report") or ""),
        "assigned_category": str(case.get("assigned_category") or "unknown"),
        "original_confidence": str(case.get("confidence") or "low"),
        "review_outcome": review_outcome,
        "suspected_reason": suspected_reason,
        "recommended_action": recommended_action,
        "suggested_existing_category": suggested_cat,
        "suggested_rule": rule_suggestion,
    }


def _make_rule_suggestion(
    bench_cat: str,
    case_name: str,
    suggested_cat: str | None,
) -> dict[str, Any]:
    """Build a single deterministic rule suggestion dict."""
    name_lower = case_name.lower()

    # Name-based hints (high confidence when name matches)
    for substr, _, cat in _NAME_HINTS:
        if substr in name_lower:
            return {
                "rule_name": f"name_contains_{substr}",
                "target_category": cat,
                "signals": [f"case name contains {substr!r}"],
                "confidence": "medium",
                "deterministic": False,
                "note": (
                    "Case-name rules have medium confidence. Combine with "
                    "failure evidence before promoting to production."
                ),
            }

    # Algorithm/logic bench category → suggest new rule
    if bench_cat in _ALGORITHM_BENCH_CATS:
        return {
            "rule_name": f"benchmark_category_{bench_cat}_algorithm_logic",
            "target_category": "algorithm_or_logic_failure",
            "signals": [f"benchmark case category={bench_cat!r}"],
            "confidence": "medium",
            "deterministic": True,
            "note": (
                "Requires adding 'algorithm_or_logic_failure' to the taxonomy "
                "or mapping to an equivalent existing category."
            ),
        }

    return {
        "rule_name": f"benchmark_category_{bench_cat}",
        "target_category": suggested_cat or "unknown",
        "signals": [f"benchmark case category={bench_cat!r}"],
        "confidence": "low",
        "deterministic": False,
        "note": "Insufficient signal for a high-confidence rule.",
    }


# ── New category proposals ────────────────────────────────────────────────────

def propose_new_categories(
    reviewed_cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Group repeated patterns and propose at most 3 new taxonomy categories.

    Only proposes a category when multiple cases share the same bench_cat
    signal. Never applies them.
    """
    # Group candidate_new_category cases by bench_category
    new_cat_cases: dict[str, list[str]] = {}
    for r in reviewed_cases:
        if r.get("review_outcome") != "candidate_new_category":
            continue
        bc = str(r.get("bench_category") or "other").strip()
        new_cat_cases.setdefault(bc, []).append(str(r.get("name") or ""))

    # Group candidate_mapping_rule cases that have no suggested_existing_category
    # and a consistent bench_cat → these may warrant a new taxonomy entry
    alg_cases: dict[str, list[str]] = {}
    for r in reviewed_cases:
        if r.get("review_outcome") != "candidate_mapping_rule":
            continue
        if r.get("suggested_existing_category"):
            continue
        bc = str(r.get("bench_category") or "").strip()
        if not bc:
            continue
        alg_cases.setdefault(bc, []).append(str(r.get("name") or ""))

    proposals: list[dict[str, Any]] = []

    # Proposal 1: algorithm_or_logic_failure (if algorithm-type bench cats appear)
    alg_matching = sorted(alg_cases.items(), key=lambda kv: -len(kv[1]))
    if alg_matching:
        all_cases = [c for _, cs in alg_matching for c in cs]
        all_cats = [bc for bc, _ in alg_matching]
        proposals.append({
            "category_id": "algorithm_or_logic_failure",
            "reason": (
                "Repeated cases with bench categories "
                + str(all_cats)
                + " share a pattern: the agent failed to produce a correct "
                "fix for an algorithm or logic problem. No existing derivation "
                "category covers this."
            ),
            "matching_unknown_cases": all_cases,
            "why_existing_insufficient": (
                "'unknown' is too broad; "
                "'insufficient_evidence' is inaccurate because evidence exists. "
                "The existing taxonomy has no algorithm/reasoning failure bucket."
            ),
            "confidence": "medium",
        })

    # Proposal 2: complex_task_or_migration (if structural bench cats appear)
    if new_cat_cases:
        all_new_cases = sorted(
            {c for cs in new_cat_cases.values() for c in cs}
        )
        all_new_cats = sorted(new_cat_cases)
        proposals.append({
            "category_id": "complex_task_or_migration",
            "reason": (
                "Bench categories "
                + str(all_new_cats)
                + " represent complex structural tasks "
                "(migrations, module rewiring, config changes) that require "
                "multi-file understanding. No existing derivation category "
                "targets this pattern specifically."
            ),
            "matching_unknown_cases": all_new_cases,
            "why_existing_insufficient": (
                "'root_cause_multifile' focuses on bug root-cause; "
                "'wrong_file_or_decoy' focuses on wrong-target. "
                "Neither captures intentional large-scope refactors or migrations."
            ),
            "confidence": "low",
        })

    return proposals[:3]


# ── Readiness recommendation ──────────────────────────────────────────────────

def compute_readiness_recommendation(
    total: int,
    counts: dict[str, int],
) -> str:
    """Return a Phase 14.6 readiness recommendation.

    ``counts`` maps review_outcome → count.
    """
    if total == 0:
        return "ready"

    leave_unknown = counts.get("leave_unknown", 0)
    new_cat = counts.get("candidate_new_category", 0)
    can_map = counts.get("candidate_mapping_rule", 0)
    env_noise = counts.get("environment_or_tool_noise", 0)
    insuf = counts.get("insufficient_evidence", 0)

    # Not ready if taxonomy has too many genuine gaps
    if new_cat >= 3:
        return "not_ready"

    # Not ready if most cases are truly ambiguous with no path forward
    if leave_unknown > total * 0.5 and can_map < total * 0.3:
        return "not_ready"

    # Not ready if insufficient evidence dominates and we can't reason about cases
    if insuf > total * 0.7:
        return "not_ready"

    # Ready with unknown bucket if mappable + noise is the majority
    if (can_map + env_noise) >= total * 0.5:
        return "ready_with_unknown_bucket"

    # Any remaining unknowns that can potentially be mapped → conservative ready
    if can_map > 0 or env_noise > 0:
        return "ready_with_unknown_bucket"

    return "not_ready"


# ── Main review builder ───────────────────────────────────────────────────────

def build_unknown_review(
    derivation: dict[str, Any],
    *,
    source_path: str = "",
) -> dict[str, Any]:
    """Build the complete unknown-case review from a derivation artifact dict.

    Input is never mutated. Never raises for expected failure modes.
    """
    unknown_cases = extract_unknown_cases(derivation)
    reviewed: list[dict[str, Any]] = [review_unknown_case(c) for c in unknown_cases]

    outcome_counts: dict[str, int] = {}
    for r in reviewed:
        oc = r.get("review_outcome", "leave_unknown")
        outcome_counts[oc] = outcome_counts.get(oc, 0) + 1

    can_map_existing = sum(
        1 for r in reviewed
        if r.get("review_outcome") == "candidate_mapping_rule"
        and r.get("suggested_existing_category")
    )
    need_new_cat = outcome_counts.get("candidate_new_category", 0)
    leave_unk = outcome_counts.get("leave_unknown", 0)
    need_evidence = outcome_counts.get("insufficient_evidence", 0)

    proposed_categories = propose_new_categories(reviewed)

    suggested_rules: list[dict[str, Any]] = []
    seen_rules: set[str] = set()
    for r in reviewed:
        sr = r.get("suggested_rule")
        if sr and isinstance(sr, dict):
            rname = str(sr.get("rule_name") or "")
            if rname and rname not in seen_rules:
                seen_rules.add(rname)
                suggested_rules.append(sr)

    total = len(reviewed)
    readiness = compute_readiness_recommendation(total, outcome_counts)

    # Ordered outcome counts
    ordered_counts = {oc: outcome_counts.get(oc, 0) for oc in REVIEW_OUTCOMES}

    return {
        "report_kind": "failure_unknown_review",
        "guardrail_note": UNKNOWN_REVIEW_GUARDRAIL_NOTE,
        "source_derivation_artifact": source_path,
        "source_derivation_summary": {
            k: v
            for k, v in (derivation.get("summary") or {}).items()
        },
        "summary": {
            "total_unknown_cases_reviewed": total,
            "outcome_counts": ordered_counts,
            "can_map_to_existing_category": can_map_existing,
            "need_new_category": need_new_cat,
            "leave_unknown": leave_unk,
            "need_better_evidence": need_evidence,
            "suggested_rule_count": len(suggested_rules),
            "proposed_new_category_count": len(proposed_categories),
            "phase_14_6_readiness": readiness,
        },
        "reviewed_cases": reviewed,
        "suggested_rules": suggested_rules,
        "proposed_new_categories": proposed_categories,
    }


def build_unknown_review_from_empty() -> dict[str, Any]:
    """Return a minimal report when no derivation artifact is available."""
    return {
        "report_kind": "failure_unknown_review",
        "guardrail_note": UNKNOWN_REVIEW_GUARDRAIL_NOTE,
        "source_derivation_artifact": None,
        "source_derivation_summary": {},
        "no_input": True,
        "summary": {
            "total_unknown_cases_reviewed": 0,
            "outcome_counts": {oc: 0 for oc in REVIEW_OUTCOMES},
            "can_map_to_existing_category": 0,
            "need_new_category": 0,
            "leave_unknown": 0,
            "need_better_evidence": 0,
            "suggested_rule_count": 0,
            "proposed_new_category_count": 0,
            "phase_14_6_readiness": "not_ready",
        },
        "reviewed_cases": [],
        "suggested_rules": [],
        "proposed_new_categories": [],
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def render_unknown_review_markdown(review: dict[str, Any]) -> str:
    """Render the review report as read-only Markdown."""
    lines = [
        "# Unknown Failure Category Review (Phase 14.5a)",
        "",
        f"> {review.get('guardrail_note', UNKNOWN_REVIEW_GUARDRAIL_NOTE)}",
        "",
        "_Read-only report: review and proposals only. Nothing is acted upon._",
        "",
        "---",
        "",
    ]

    if review.get("no_input"):
        lines += [
            "## No Input",
            "",
            "No Phase 14.5 failure taxonomy derivation artifact was found.",
            "Run `scripts/create_failure_taxonomy_derivation_report.py --repo-path .` first.",
            "",
        ]
        return "\n".join(lines) + "\n"

    src = review.get("source_derivation_artifact") or "_unknown_"
    lines += [f"**Source derivation artifact:** `{src}`", ""]

    # 1. Summary
    lines += ["## 1. Summary", ""]
    summary = review.get("summary") or {}
    lines.append(f"- Total unknown cases reviewed: {summary.get('total_unknown_cases_reviewed', 0)}")
    lines.append(f"- Phase 14.6 readiness: **{summary.get('phase_14_6_readiness', 'not_ready')}**")
    lines.append("")
    lines += ["**Outcome counts:**", ""]
    for oc, count in (summary.get("outcome_counts") or {}).items():
        lines.append(f"- `{oc}`: {count}")
    lines.append("")
    lines.append(f"- Can map to existing category: {summary.get('can_map_to_existing_category', 0)}")
    lines.append(f"- Need new category: {summary.get('need_new_category', 0)}")
    lines.append(f"- Leave unknown: {summary.get('leave_unknown', 0)}")
    lines.append(f"- Need better evidence: {summary.get('need_better_evidence', 0)}")
    lines.append(f"- Suggested rules: {summary.get('suggested_rule_count', 0)}")
    lines.append(f"- Proposed new categories: {summary.get('proposed_new_category_count', 0)}")
    lines.append("")

    # 2. Reviewed cases
    lines += ["## 2. Reviewed Unknown Cases", ""]
    reviewed = review.get("reviewed_cases") or []
    if reviewed:
        lines += [
            "| Case | Lang | Bench Cat | Outcome | Recommended Action |",
            "|---|---|---|---|---|",
        ]
        for r in reviewed:
            lines.append(
                f"| `{_md(r.get('name', ''))}` "
                f"| {_md(r.get('language', ''))} "
                f"| `{_md(r.get('bench_category', ''))}` "
                f"| {r.get('review_outcome', '')} "
                f"| {r.get('recommended_action', '')} |"
            )
        lines.append("")

        lines += ["### Detail per case", ""]
        for r in reviewed:
            lines.append(f"#### `{r.get('name', '')}`")
            lines.append("")
            lines.append(f"- Source: `{r.get('source_report', '')}`")
            lines.append(f"- Language: {r.get('language', '')}")
            lines.append(f"- Bench category: `{r.get('bench_category', '') or '(none)'}`")
            lines.append(f"- Assigned category: `{r.get('assigned_category', '')}`")
            lines.append(f"- Original confidence: {r.get('original_confidence', '')}")
            lines.append(f"- Review outcome: **{r.get('review_outcome', '')}**")
            lines.append(f"- Suspected reason: {r.get('suspected_reason', '')}")
            lines.append(f"- Recommended action: `{r.get('recommended_action', '')}`")
            if r.get("suggested_existing_category"):
                lines.append(f"- Suggested existing category: `{r['suggested_existing_category']}`")
            sr = r.get("suggested_rule")
            if sr:
                lines.append(f"- Suggested rule: `{sr.get('rule_name', '')}` → "
                             f"`{sr.get('target_category', '')}` "
                             f"(confidence: {sr.get('confidence', '')})")
            lines.append("")
    else:
        lines += ["_No unknown cases to review._", ""]

    # 3. Suggested rule improvements
    lines += ["## 3. Suggested Rule Improvements", ""]
    rules = review.get("suggested_rules") or []
    if rules:
        lines += [
            "| Rule | Target Category | Confidence | Deterministic |",
            "|---|---|---|---|",
        ]
        for rule in rules:
            det = "yes" if rule.get("deterministic") else "no"
            lines.append(
                f"| `{rule.get('rule_name', '')}` "
                f"| `{rule.get('target_category', '')}` "
                f"| {rule.get('confidence', '')} "
                f"| {det} |"
            )
        lines.append("")
        lines.append("_These are proposals only. No rule has been applied._")
        lines.append("")
        for rule in rules:
            lines.append(f"**`{rule.get('rule_name', '')}`**")
            lines.append(f"- Target: `{rule.get('target_category', '')}`")
            lines.append(f"- Signals: {'; '.join(rule.get('signals') or [])}")
            if rule.get("note"):
                lines.append(f"- Note: {rule['note']}")
            lines.append("")
    else:
        lines += ["_No rule improvements proposed._", ""]

    # 4. Proposed new categories
    lines += ["## 4. Proposed New Categories", ""]
    new_cats = review.get("proposed_new_categories") or []
    if new_cats:
        lines.append(
            "_These are proposals only. Do not add to taxonomy until validated._"
        )
        lines.append("")
        for cat in new_cats:
            lines.append(f"### `{cat.get('category_id', '')}`")
            lines.append("")
            lines.append(f"- **Reason:** {cat.get('reason', '')}")
            lines.append(f"- **Matching cases:** {cat.get('matching_unknown_cases', [])}")
            lines.append(f"- **Why existing categories insufficient:** {cat.get('why_existing_insufficient', '')}")
            lines.append(f"- **Confidence:** {cat.get('confidence', '')}")
            lines.append("")
    else:
        lines += ["_No new categories proposed._", ""]

    # 5. Phase 14.6 readiness
    lines += ["## 5. Phase 14.6 Readiness", ""]
    readiness = summary.get("phase_14_6_readiness", "not_ready")
    readiness_notes = {
        "ready": (
            "All unknowns are resolved or acceptable. "
            "The taxonomy can be used in Phase 14.6 without modifications."
        ),
        "ready_with_unknown_bucket": (
            "Most unknowns can be mapped or are acceptable noise. "
            "Proceed with Phase 14.6, keeping 'unknown' as a valid bucket. "
            "Do not force-map remaining cases."
        ),
        "not_ready": (
            "Too many unknowns lack a clear path forward, or the taxonomy has "
            "too many gaps. Address proposed rules/categories before Phase 14.6."
        ),
    }
    lines.append(f"**Recommendation: `{readiness}`**")
    lines.append("")
    lines.append(readiness_notes.get(readiness, ""))
    lines.append("")

    return "\n".join(lines) + "\n"


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
