"""Phase 14.5 — Failure Taxonomy Data-Derivation Report (read-only).

Scans existing project artifacts (benchmark reports, lessons, anti-lessons,
Dream artifacts, proposals, worker runs) and derives candidate failure
categories. Report-only: never modifies any artifact, changes benchmark
scoring, generates or applies patches, promotes lessons, calls any model or
API, writes a database, spawns subprocesses, makes network calls, or affects
any runtime behavior.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


# ── Proposed taxonomy enum ────────────────────────────────────────────────────

DERIVATION_CATEGORIES: tuple[str, ...] = (
    "toolchain_environment",
    "security_tool_or_permission",
    "validation_command_gap",
    "wrong_file_or_decoy",
    "forbidden_file_or_scope_violation",
    "missing_import_or_dependency",
    "async_or_lifecycle_bug",
    "state_mutation_or_side_effect",
    "data_validation_or_boundary",
    "root_cause_multifile",
    "false_positive_no_patch",
    "insufficient_evidence",
    "unknown",
)

DERIVATION_GUARDRAIL_NOTE = (
    "Phase 14.5 failure taxonomy derivation report is read-only: it scans "
    "existing artifacts and proposes a taxonomy. It does not modify any "
    "artifact, change benchmark scoring, generate or apply patches, run "
    "validation, promote lessons, run Dream automation, call any model or API, "
    "write a database, spawn subprocesses, make network calls, or affect any "
    "runtime behavior."
)

_IGNORED_DIR_NAMES = frozenset({
    ".git", "__pycache__", ".pytest_cache", "tmp", "tmp_tests",
    ".venv", "venv", "node_modules",
})

# Benchmark case category → derivation category (deterministic, exact-match)
_BENCH_CATEGORY_TO_DERIVATION: dict[str, str] = {
    "async_error": "async_or_lifecycle_bug",
    "side_effect": "state_mutation_or_side_effect",
    "missing_import": "missing_import_or_dependency",
    "logic_validation": "data_validation_or_boundary",
    "boundary_logic": "data_validation_or_boundary",
    "multi_file_root_cause": "root_cause_multifile",
}

_SECURITY_MARKERS: tuple[str, ...] = (
    "anti-virus", "antivirus", "security tool", "blocked executable",
    "blocked by", "evo-gen", "quarantine", "threat detected",
    "access is denied",
)
_TOOLCHAIN_MARKERS: tuple[str, ...] = (
    "command not found", "is not recognized as an internal",
    "executable file not found", "executable not found",
    "compiler not found", "python was not found",
    "node not available", "npm not available", "g++ not available",
    "gcc not available", "cargo not available", "go not available",
    "dotnet not available", "missing tools:", "missing toolchain",
    "dll load failed",
)
_MISSING_IMPORT_MARKERS: tuple[str, ...] = (
    "no module named", "modulenotfounderror", "importerror",
    "cannot find module", "module not found",
)
_VALIDATION_COMMAND_MARKERS: tuple[str, ...] = (
    "could not run validation", "validation command failed to start",
    "failed to start validation", "invalid validation command",
)


# ── JSON helpers ──────────────────────────────────────────────────────────────

def _safe_load_json(path: Path) -> Any:
    """Load JSON from a file, returning None on any read or parse error."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _path_is_ignored(path: Path) -> bool:
    return any(part in _IGNORED_DIR_NAMES for part in path.parts)


# ── Artifact scanning ─────────────────────────────────────────────────────────

def _scan_benchmark_reports(
    repo_path: Path,
) -> tuple[list[dict[str, Any]], int]:
    """Return (case_dicts, reports_scanned_count). Never raises."""
    bench_dir = repo_path / ".agent" / "benchmarks"
    if not bench_dir.is_dir():
        return [], 0
    cases: list[dict[str, Any]] = []
    reports_count = 0
    for path in sorted(bench_dir.glob("benchmark_report_*.json")):
        data = _safe_load_json(path)
        if not isinstance(data, dict):
            continue
        reports_count += 1
        for key in ("results", "case_results", "cases"):
            value = data.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        case = dict(item)
                        case["_source_report"] = path.name
                        cases.append(case)
                break
    return cases, reports_count


def _scan_lesson_records(repo_path: Path) -> list[dict[str, Any]]:
    """Scan all lesson JSON files. Never raises."""
    lessons_dir = repo_path / ".agent" / "lessons"
    if not lessons_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(lessons_dir.rglob("*.json")):
        if _path_is_ignored(path):
            continue
        data = _safe_load_json(path)
        if isinstance(data, dict) and isinstance(data.get("id"), str):
            d = dict(data)
            d["_source_path"] = str(path.relative_to(repo_path))
            results.append(d)
    return results


def _scan_dream_artifacts(repo_path: Path) -> list[dict[str, Any]]:
    """Scan Dream run artifacts. Never raises."""
    dreams_dir = repo_path / ".agent" / "dreams"
    if not dreams_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(dreams_dir.rglob("*.json")):
        if _path_is_ignored(path):
            continue
        data = _safe_load_json(path)
        source = str(path.relative_to(repo_path))
        if isinstance(data, dict):
            d = dict(data)
            d["_source_path"] = source
            results.append(d)
        elif isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    d = dict(item)
                    d["_source_path"] = source
                    results.append(d)
    return results


def _scan_proposal_artifacts(repo_path: Path) -> list[dict[str, Any]]:
    """Scan proposal queue artifacts. Never raises."""
    proposals_dir = repo_path / ".agent" / "proposals"
    if not proposals_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(proposals_dir.rglob("*.json")):
        if _path_is_ignored(path):
            continue
        data = _safe_load_json(path)
        if isinstance(data, dict):
            d = dict(data)
            d["_source_path"] = str(path.relative_to(repo_path))
            results.append(d)
    return results


def _scan_worker_artifacts(repo_path: Path) -> list[dict[str, Any]]:
    """Scan worker run artifacts. Never raises."""
    workers_dir = repo_path / ".agent" / "worker_runs"
    if not workers_dir.is_dir():
        return []
    results: list[dict[str, Any]] = []
    for path in sorted(workers_dir.rglob("*.json")):
        if _path_is_ignored(path):
            continue
        data = _safe_load_json(path)
        if isinstance(data, dict):
            d = dict(data)
            d["_source_path"] = str(path.relative_to(repo_path))
            results.append(d)
    return results


# ── Signal inventory ──────────────────────────────────────────────────────────

def _case_text(case: dict[str, Any]) -> str:
    """Return lowercase text blob from a benchmark case result."""
    parts: list[str] = []
    for key in (
        "validation", "validation_output", "error_text", "stderr",
        "stdout", "toolchain_issue", "agent_validation",
    ):
        value = case.get(key)
        if isinstance(value, str):
            parts.append(value)
    vs = case.get("validation_summary")
    if isinstance(vs, dict):
        for k in ("validation_output_tail", "agent_validation_tail"):
            v = vs.get(k)
            if isinstance(v, str):
                parts.append(v)
    return "\n".join(parts).lower()


def collect_signal_inventory(
    cases: list[dict[str, Any]],
    lessons: list[dict[str, Any]],
    dream_artifacts: list[dict[str, Any]],
    proposal_artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Collect all distinct signals found across artifact types."""
    failure_kinds: set[str] = set()
    bench_categories: set[str] = set()
    bench_languages: set[str] = set()
    lesson_tags: set[str] = set()
    lesson_statuses: set[str] = set()
    lesson_promotion_types: set[str] = set()
    dream_statuses: set[str] = set()
    patch_blocker_codes: set[str] = set()
    proposal_statuses: set[str] = set()

    for case in cases:
        lang = str(case.get("language") or "").strip()
        if lang:
            bench_languages.add(lang)
        cat = str(case.get("category") or "").strip()
        if cat:
            bench_categories.add(cat)
        fk = str(case.get("failure_kind") or "").strip()
        if fk:
            failure_kinds.add(fk)

    for lesson in lessons:
        status = str(lesson.get("status") or "").strip()
        if status:
            lesson_statuses.add(status)
        tags = lesson.get("tags") or []
        if isinstance(tags, list):
            for tag in tags:
                if isinstance(tag, str) and tag:
                    lesson_tags.add(tag)
        evaluation = lesson.get("evaluation") or {}
        if isinstance(evaluation, dict):
            promo = str(evaluation.get("promotion") or "").strip()
            if promo:
                lesson_promotion_types.add(promo)

    for artifact in dream_artifacts:
        status = str(artifact.get("status") or "").strip()
        if status:
            dream_statuses.add(status)
        for b in (artifact.get("patch_blockers") or []):
            if isinstance(b, dict):
                code = str(b.get("code") or "").strip()
                if code:
                    patch_blocker_codes.add(code)
        for item in (artifact.get("items") or []):
            if not isinstance(item, dict):
                continue
            s = str(item.get("status") or "").strip()
            if s:
                dream_statuses.add(s)
            for b in (item.get("patch_blockers") or []):
                if isinstance(b, dict):
                    code = str(b.get("code") or "").strip()
                    if code:
                        patch_blocker_codes.add(code)

    for prop in proposal_artifacts:
        status = str(prop.get("status") or "").strip()
        if status:
            proposal_statuses.add(status)

    return {
        "failure_kinds": sorted(failure_kinds),
        "benchmark_case_categories": sorted(bench_categories),
        "benchmark_languages": sorted(bench_languages),
        "lesson_tags_sample": sorted(lesson_tags)[:50],
        "lesson_statuses": sorted(lesson_statuses),
        "lesson_promotion_types": sorted(lesson_promotion_types),
        "dream_statuses": sorted(dream_statuses),
        "patch_blocker_codes": sorted(patch_blocker_codes),
        "proposal_statuses": sorted(proposal_statuses),
    }


# ── Classification rules ──────────────────────────────────────────────────────

def classify_benchmark_case(
    case: dict[str, Any],
) -> tuple[str, str, str, list[str], bool]:
    """Classify a benchmark case result into a derivation category.

    Returns ``(category, rule_name, confidence, evidence_list, is_deterministic)``.
    Rules are evaluated in priority order; the first match wins. The case dict
    is never mutated.
    """
    text = _case_text(case)
    bench_cat = str(case.get("category") or "").strip().lower()
    forbidden = [f for f in (case.get("touched_forbidden_files") or []) if f]
    changed = {str(f) for f in (case.get("changed_files") or [])}
    expected = {str(f) for f in (case.get("expected_changed_files") or [])}

    # 1. Security tool / OS policy blocked execution (highest priority)
    sec_hits = [m for m in _SECURITY_MARKERS if m in text]
    if sec_hits or str(case.get("failure_kind") or "") == "security_tool":
        evidence = [f"text contains {m!r}" for m in sec_hits]
        if str(case.get("failure_kind") or "") == "security_tool":
            evidence.append("failure_kind=security_tool")
        return "security_tool_or_permission", "security_marker_in_output", "high", evidence, True

    # 2. Toolchain / environment error
    tool_hits = [m for m in _TOOLCHAIN_MARKERS if m in text]
    if (
        tool_hits
        or case.get("environment_error") is True
        or str(case.get("failure_kind") or "") in ("toolchain", "environment")
    ):
        evidence = [f"text contains {m!r}" for m in tool_hits]
        if case.get("environment_error") is True:
            evidence.append("environment_error=True")
        fk = str(case.get("failure_kind") or "")
        if fk in ("toolchain", "environment"):
            evidence.append(f"failure_kind={fk!r}")
        return "toolchain_environment", "toolchain_marker_in_output", "high", evidence, True

    # 3. Validation command could not run
    cmd_hits = [m for m in _VALIDATION_COMMAND_MARKERS if m in text]
    if (
        case.get("validation_command_ok") is False
        or str(case.get("validation_status") or "").lower() == "error"
        or cmd_hits
    ):
        evidence: list[str] = []
        if case.get("validation_command_ok") is False:
            evidence.append("validation_command_ok=False")
        if str(case.get("validation_status") or "").lower() == "error":
            evidence.append("validation_status=error")
        evidence += [f"text contains {m!r}" for m in cmd_hits]
        return "validation_command_gap", "validation_command_failure_signal", "high", evidence, True

    # 4. Forbidden file touched
    if forbidden:
        return (
            "forbidden_file_or_scope_violation",
            "touched_forbidden_files",
            "high",
            [f"touched_forbidden_files: {forbidden}"],
            True,
        )

    # 5. No patch expected
    if case.get("expects_patch") is False or case.get("no_patch_expected") is True:
        return (
            "false_positive_no_patch",
            "no_patch_expected_flag",
            "high",
            ["expects_patch=False or no_patch_expected=True"],
            True,
        )

    # 6. Patch landed in wrong files
    if expected and changed and changed.isdisjoint(expected):
        return (
            "wrong_file_or_decoy",
            "changed_files_disjoint_from_expected",
            "high",
            [f"changed={sorted(changed)}, expected={sorted(expected)}"],
            True,
        )

    # 7. Benchmark case category — deterministic lookup
    if bench_cat in _BENCH_CATEGORY_TO_DERIVATION:
        deriv_cat = _BENCH_CATEGORY_TO_DERIVATION[bench_cat]
        return (
            deriv_cat,
            f"benchmark_category_{bench_cat}",
            "high",
            [f"benchmark case category={bench_cat!r}"],
            True,
        )

    # 8. Missing import — heuristic
    if any(m in text for m in _MISSING_IMPORT_MARKERS):
        return (
            "missing_import_or_dependency",
            "import_error_in_output",
            "medium",
            ["import or dependency error in validation output"],
            False,
        )

    # 9. No validation signal present
    if case.get("validation_ok") is None and not bench_cat:
        return (
            "insufficient_evidence",
            "missing_classification_signals",
            "low",
            ["no validation_ok signal and no benchmark category match"],
            False,
        )

    return "unknown", "no_matching_rule", "low", ["no classification rule matched"], False


# ── Mapping rules table ───────────────────────────────────────────────────────

def _build_mapping_rules(
    observed_bench_categories: set[str],
) -> list[dict[str, Any]]:
    """Build the mapping rules section for the derivation report."""

    def _rule(
        name: str,
        category: str,
        signals: list[str],
        confidence: str,
        deterministic: bool,
        examples: list[str],
    ) -> dict[str, Any]:
        return {
            "rule_name": name,
            "category": category,
            "signals_used": signals,
            "example_artifacts": examples,
            "confidence": confidence,
            "deterministic": deterministic,
        }

    rules: list[dict[str, Any]] = [
        _rule(
            "security_marker_in_output",
            "security_tool_or_permission",
            [
                "validation text contains antivirus/security/access-denied markers",
                "failure_kind=security_tool",
            ],
            "high", True,
            [".agent/benchmarks/ cases with 'Access is denied' in agent_validation_tail"],
        ),
        _rule(
            "toolchain_marker_in_output",
            "toolchain_environment",
            [
                "environment_error=True",
                "failure_kind=toolchain or environment",
                "validation text contains toolchain/executable markers",
                "dll load failed",
            ],
            "high", True,
            [".agent/benchmarks/ cases with missing compiler or tool"],
        ),
        _rule(
            "validation_command_failure_signal",
            "validation_command_gap",
            [
                "validation_command_ok=False",
                "validation_status=error",
                "validation command failure markers in text",
            ],
            "high", True,
            [],
        ),
        _rule(
            "touched_forbidden_files",
            "forbidden_file_or_scope_violation",
            ["touched_forbidden_files non-empty"],
            "high", True,
            [],
        ),
        _rule(
            "no_patch_expected_flag",
            "false_positive_no_patch",
            ["expects_patch=False", "no_patch_expected=True"],
            "high", True,
            [],
        ),
        _rule(
            "changed_files_disjoint_from_expected",
            "wrong_file_or_decoy",
            ["changed_files ∩ expected_changed_files = ∅"],
            "high", True,
            [],
        ),
    ]

    for bench_cat in sorted(_BENCH_CATEGORY_TO_DERIVATION):
        deriv_cat = _BENCH_CATEGORY_TO_DERIVATION[bench_cat]
        observed = bench_cat in observed_bench_categories
        rules.append(_rule(
            f"benchmark_category_{bench_cat}",
            deriv_cat,
            [f"benchmark case category={bench_cat!r}"],
            "high", True,
            [
                f"any case with category={bench_cat!r}"
                + (" (observed)" if observed else " (not observed in scanned reports)")
            ],
        ))

    rules += [
        _rule(
            "import_error_in_output",
            "missing_import_or_dependency",
            ["ModuleNotFoundError / ImportError / 'no module named' in validation output"],
            "medium", False,
            [],
        ),
        _rule(
            "missing_classification_signals",
            "insufficient_evidence",
            ["validation_ok=None and no benchmark category match"],
            "low", False,
            [],
        ),
        _rule(
            "no_matching_rule",
            "unknown",
            ["no prior rule matched"],
            "low", False,
            [],
        ),
    ]
    return rules


# ── Recommendations ───────────────────────────────────────────────────────────

def _build_recommendations() -> list[dict[str, str]]:
    return [
        {
            "phase": "Phase 14.6",
            "action": (
                "Store `failure_category` metadata on new benchmark reports and "
                "lesson records only. Do not retroactively rewrite existing "
                "artifacts. Apply only to reports generated after taxonomy validation."
            ),
        },
        {
            "phase": "Phase 14.7",
            "action": (
                "Add a category trend display to the benchmark report view. "
                "Show how failure categories shift across runs. "
                "Display-only; no scoring changes."
            ),
        },
        {
            "phase": "Phase 14.8",
            "action": (
                "Optional category-aware retrieval experiment: try boosting "
                "lessons whose failure_category matches the current case's "
                "category. Gate behind an experiment flag. Do not use in "
                "production until Phase 14.7 trend analysis validates taxonomy stability."
            ),
        },
        {
            "phase": "Guardrail",
            "action": (
                "Do not use category-aware retrieval in production until the "
                "taxonomy is validated by at least two full benchmark cycles "
                "showing stable category distributions."
            ),
        },
    ]


# ── Case pass/fail check ──────────────────────────────────────────────────────

def _case_clearly_passed(case: dict[str, Any]) -> bool:
    for key in ("success", "passed", "ok", "correct"):
        if case.get(key) is True:
            return True
    status = str(case.get("status") or "").lower()
    return status in {"pass", "passed", "ok", "success"}


# ── Main derivation report builder ────────────────────────────────────────────

def derive_taxonomy_report(
    repo_path: str | Path = ".",
) -> dict[str, Any]:
    """Build the complete derivation report dict from existing artifacts.

    Scans .agent/ artifacts, classifies failing benchmark cases into the
    proposed taxonomy, and returns the report as a plain dict. Never modifies
    any file or artifact.
    """
    root = Path(repo_path).resolve()

    cases, reports_count = _scan_benchmark_reports(root)
    lessons = _scan_lesson_records(root)
    dream_artifacts = _scan_dream_artifacts(root)
    proposal_artifacts = _scan_proposal_artifacts(root)
    worker_artifacts = _scan_worker_artifacts(root)

    anti_lessons = [l for l in lessons if l.get("status") == "blocked"]
    active_lessons = [l for l in lessons if l.get("status") == "active"]
    candidate_lessons = [l for l in lessons if l.get("status") == "candidate"]

    signal_inventory = collect_signal_inventory(
        cases, lessons, dream_artifacts, proposal_artifacts
    )

    classified: list[dict[str, Any]] = []
    unmapped: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for case in cases:
        if _case_clearly_passed(case):
            continue
        name = str(case.get("name") or "").strip() or "unnamed"
        category, rule, confidence, evidence, deterministic = classify_benchmark_case(case)
        counts[category] = counts.get(category, 0) + 1
        entry: dict[str, Any] = {
            "name": name,
            "source_report": case.get("_source_report", ""),
            "language": str(case.get("language") or ""),
            "bench_category": str(case.get("category") or ""),
            "assigned_category": category,
            "rule_applied": rule,
            "confidence": confidence,
            "evidence": evidence,
            "deterministic": deterministic,
        }
        classified.append(entry)
        if category in ("unknown", "insufficient_evidence"):
            unmapped.append({
                "name": name,
                "source_report": case.get("_source_report", ""),
                "reason": f"rule={rule}, evidence={evidence}",
            })

    observed_bench_cats = set(signal_inventory["benchmark_case_categories"])
    mapping_rules = _build_mapping_rules(observed_bench_cats)
    recommendations = _build_recommendations()

    ordered_counts = {
        cat: counts[cat]
        for cat in DERIVATION_CATEGORIES
        if cat in counts
    }

    return {
        "report_kind": "failure_taxonomy_derivation",
        "guardrail_note": DERIVATION_GUARDRAIL_NOTE,
        "summary": {
            "total_benchmark_reports_scanned": reports_count,
            "total_cases_scanned": len(cases),
            "total_failing_cases_classified": len(classified),
            "total_lesson_records_scanned": len(lessons),
            "total_active_lessons": len(active_lessons),
            "total_candidate_lessons": len(candidate_lessons),
            "total_anti_lesson_records_scanned": len(anti_lessons),
            "total_dream_artifacts_scanned": len(dream_artifacts),
            "total_proposal_artifacts_scanned": len(proposal_artifacts),
            "total_worker_artifacts_scanned": len(worker_artifacts),
            "candidate_categories_proposed": len(DERIVATION_CATEGORIES),
            "categories_with_matches": len(ordered_counts),
            "unmapped_case_count": len(unmapped),
        },
        "signal_inventory": signal_inventory,
        "candidate_taxonomy": list(DERIVATION_CATEGORIES),
        "mapping_rules": mapping_rules,
        "classified_cases": classified,
        "counts_by_category": ordered_counts,
        "unmapped_cases": unmapped,
        "recommendations": recommendations,
    }


# ── Markdown rendering ────────────────────────────────────────────────────────

def render_derivation_markdown(report: dict[str, Any]) -> str:
    """Render the derivation report dict as read-only Markdown."""
    lines = [
        "# Failure Taxonomy Data-Derivation Report (Phase 14.5)",
        "",
        f"> {report.get('guardrail_note', DERIVATION_GUARDRAIL_NOTE)}",
        "",
        "_Read-only report: classification and taxonomy proposal only. "
        "Nothing is acted upon._",
        "",
        "---",
        "",
        "## 1. Summary",
        "",
    ]
    summary = report.get("summary") or {}
    for key, value in summary.items():
        label = key.replace("_", " ").title()
        lines.append(f"- {label}: {value}")
    lines.append("")

    # 2. Signal inventory
    lines += ["## 2. Existing Signal Inventory", ""]
    inv = report.get("signal_inventory") or {}
    for key, value in inv.items():
        label = key.replace("_", " ").title()
        if isinstance(value, list):
            lines.append(f"**{label}:**")
            lines.append(", ".join(str(v) for v in value) if value else "_(none found)_")
            lines.append("")
        else:
            lines.append(f"- {label}: {value}")
    lines.append("")

    # 3. Candidate taxonomy
    lines += ["## 3. Candidate Taxonomy", ""]
    for cat in (report.get("candidate_taxonomy") or []):
        lines.append(f"- `{cat}`")
    lines.append("")

    # 4. Mapping rules
    lines += [
        "## 4. Mapping Rules",
        "",
        "| Rule | Category | Signals | Confidence | Deterministic |",
        "|---|---|---|---|---|",
    ]
    for rule in (report.get("mapping_rules") or []):
        signals = "; ".join(rule.get("signals_used") or [])
        det = "yes" if rule.get("deterministic") else "no"
        lines.append(
            f"| `{rule.get('rule_name')}` "
            f"| {rule.get('category')} "
            f"| {_md(signals)} "
            f"| {rule.get('confidence')} "
            f"| {det} |"
        )
    lines.append("")

    # 5. Unmapped cases
    lines += ["## 5. Unmapped Cases", ""]
    unmapped = report.get("unmapped_cases") or []
    if unmapped:
        lines += ["| Case | Source | Reason |", "|---|---|---|"]
        for u in unmapped:
            lines.append(
                f"| `{_md(u.get('name', ''))}` "
                f"| {_md(u.get('source_report', ''))} "
                f"| {_md(u.get('reason', ''))} |"
            )
    else:
        lines.append("_No unmapped cases._")
    lines.append("")

    # 6. Category counts
    lines += ["## 6. Counts by Category", ""]
    counts = report.get("counts_by_category") or {}
    if counts:
        for cat, count in counts.items():
            lines.append(f"- `{cat}`: {count}")
    else:
        lines.append("_No failing cases classified._")
    lines.append("")

    # 7. Recommendations
    lines += ["## 7. Recommendations", ""]
    for rec in (report.get("recommendations") or []):
        lines.append(f"### {rec.get('phase', '')}")
        lines.append("")
        lines.append(rec.get("action", ""))
        lines.append("")

    return "\n".join(lines) + "\n"


def _md(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")
