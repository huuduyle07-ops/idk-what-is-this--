#!/usr/bin/env python
"""Phase 6.4a: turn a validated patch proposal into a lesson candidate.

Manual CLI: read artifacts from .agent/proposals/<run>/<item>/ and call
core.lesson_store.save_candidate_lesson(). Never modifies the real repo,
never applies a patch, never auto-promotes a lesson, never auto-runs on
every benchmark or Dream item.

Example:
    python scripts/create_lesson_from_proposal.py \\
        --proposal-dir .agent/proposals/20260517_034554/01-cpp-account-interest
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
_REQUIRED_FILES = (
    "item.json",
    "case.json",
    "patch_proposal.json",
    "apply_result.json",
    "validation.json",
)

# Keep lesson record compact: never embed full validation logs or huge diffs.
_MAX_SUMMARY_CHARS = 600


def _default_proposals_root() -> Path:
    """Return the canonical `<repo_root>/.agent/proposals/` directory."""
    repo_root = Path(__file__).resolve().parent.parent
    return (repo_root / ".agent" / "proposals").resolve()


def _resolve_proposal_dir(raw: str, *, proposals_root: Path | None = None) -> Path:
    """Resolve and validate a user-supplied proposal_dir.

    Path-traversal guard: the resolved directory must live under
    `<repo_root>/.agent/proposals/` (or the explicit `proposals_root`).
    """
    if not raw or not str(raw).strip():
        raise ValueError("--proposal-dir is required")
    root = (proposals_root or _default_proposals_root()).resolve()
    candidate = Path(raw).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as e:
        raise ValueError(
            f"--proposal-dir must live inside {root}: got {candidate}"
        ) from e
    if not candidate.is_dir():
        raise ValueError(
            f"--proposal-dir does not exist or is not a directory: {candidate}"
        )
    return candidate


def _read_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON in {path.name}: {e}") from e
    if not isinstance(data, dict):
        raise ValueError(f"{path.name} must be a JSON object, got {type(data).__name__}")
    return data


def _load_artifacts(proposal_dir: Path) -> dict:
    missing = [name for name in _REQUIRED_FILES if not (proposal_dir / name).is_file()]
    if missing:
        raise FileNotFoundError(
            f"missing required artifacts in {proposal_dir.name}: {', '.join(missing)}"
        )
    artifacts: dict = {}
    for name in _REQUIRED_FILES:
        artifacts[name] = _read_json(proposal_dir / name)
    return artifacts


def _extract_changed_files(apply_result: dict, proposal: dict) -> list[str]:
    files: list[str] = []
    applied_ops = apply_result.get("applied_ops")
    if isinstance(applied_ops, list):
        for op in applied_ops:
            if isinstance(op, dict):
                rel = op.get("relative_path") or op.get("file")
                if isinstance(rel, str) and rel.strip():
                    files.append(rel)
    if not files:
        plan = proposal.get("patch_plan")
        if isinstance(plan, list):
            for op in plan:
                if isinstance(op, dict):
                    rel = op.get("relative_path") or op.get("file")
                    if isinstance(rel, str) and rel.strip():
                        files.append(rel)
    seen: set[str] = set()
    out: list[str] = []
    for f in files:
        if f not in seen:
            seen.add(f)
            out.append(f)
    return out


def _compute_diff_stats(diffs: list) -> dict:
    added = 0
    removed = 0
    for d in diffs or []:
        if not isinstance(d, str):
            continue
        for line in d.splitlines():
            if line.startswith("+++") or line.startswith("---"):
                continue
            if line.startswith("+"):
                added += 1
            elif line.startswith("-"):
                removed += 1
    return {"added": added, "removed": removed}


def _determine_patch_kind(proposal: dict) -> str:
    if proposal.get("patch_plan"):
        return "patch_plan"
    if proposal.get("patch_candidate"):
        return "patch_candidate"
    return "unknown"


def _truncate(text: str, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _build_candidate(artifacts: dict) -> dict:
    item = artifacts["item.json"]
    case = artifacts["case.json"]
    proposal = artifacts["patch_proposal.json"]
    apply_result = artifacts["apply_result.json"]
    validation = artifacts["validation.json"]

    changed_files = _extract_changed_files(apply_result, proposal)
    diff_stats = _compute_diff_stats(apply_result.get("diffs") or [])
    patch_kind = _determine_patch_kind(proposal)

    forbidden = case.get("forbidden_changed_files") or []
    expected = case.get("expected_changed_files") or []
    touched_forbidden = sorted(set(changed_files) & set(forbidden))
    missing_expected = sorted(set(expected) - set(changed_files))

    validation_ok = bool(validation.get("validation_ok") or validation.get("ok"))
    rollback = bool(apply_result.get("rollback_performed"))

    case_name = item.get("case_name") or case.get("name") or ""
    language = item.get("language") or case.get("language") or ""
    category = item.get("category") or case.get("category") or ""
    summary = _truncate(proposal.get("summary") or "", _MAX_SUMMARY_CHARS)

    return {
        "validation_ok": validation_ok,
        "touched_forbidden_files": touched_forbidden,
        "missing_expected_files": missing_expected,
        "patch_kind": patch_kind,
        "rollback_happened": rollback,
        "changed_files": changed_files,
        "diff_stats": diff_stats,
        "case_name": case_name,
        "language": language,
        "category": category,
        "summary": summary,
    }


def _generate_title(case_name: str, summary: str) -> str:
    if case_name:
        return f"Patch proposal: {case_name}"
    head = (summary or "Patch proposal lesson").split(".")[0]
    return _truncate(head, 80) or "Patch proposal lesson"


def create_lesson_from_proposal(
    proposal_dir: Path,
    *,
    repo_path: str | None = None,
    allow_failed: bool = False,
) -> dict:
    """Build a lesson candidate from a proposal directory and persist it.

    By default, refuses if `apply_result.success` is false OR
    `validation.validation_ok` is false. Pass `allow_failed=True` to save
    the lesson anyway — `lesson_quality` will typically mark it `blocked`
    (validation_ok=false → block) or push to needs_human_review.

    Read-only on the proposal directory. Never modifies the real repo.
    """
    artifacts = _load_artifacts(proposal_dir)
    candidate = _build_candidate(artifacts)

    apply_success = bool(artifacts["apply_result.json"].get("success"))
    validation_ok = candidate["validation_ok"]

    if (not apply_success or not validation_ok) and not allow_failed:
        raise RuntimeError(
            "proposal failed validation or apply; refusing to create lesson. "
            f"Pass --allow-failed to override "
            f"(apply_success={apply_success}, validation_ok={validation_ok})."
        )

    # Lazy import: keeps the path-traversal helper testable without
    # requiring lesson_store to be importable (e.g., during CI without DB).
    from core.lesson_store import save_candidate_lesson

    return save_candidate_lesson(
        candidate,
        source="patch_proposal",
        source_report=str(proposal_dir),
        case_name=candidate.get("case_name") or None,
        title=_generate_title(
            candidate.get("case_name") or "",
            candidate.get("summary") or "",
        ),
        summary=candidate.get("summary") or "",
        repo_path=repo_path,
    )


def _main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Create a lesson candidate from a validated patch proposal artifact.",
    )
    parser.add_argument(
        "--proposal-dir",
        required=True,
        help="Path to .agent/proposals/<run>/<item>/ directory.",
    )
    parser.add_argument(
        "--repo-path",
        default=None,
        help=(
            "Optional analyzed repo path; scopes the lesson to "
            ".agent/<project_tag>/lessons/. Defaults to the global "
            ".agent/lessons/ when omitted."
        ),
    )
    parser.add_argument(
        "--allow-failed",
        action="store_true",
        help=(
            "Save the lesson even if validation/apply failed. Default "
            "refuses; lesson_quality will usually mark these as blocked."
        ),
    )
    args = parser.parse_args(argv)

    try:
        proposal_dir = _resolve_proposal_dir(args.proposal_dir)
    except ValueError as e:
        print(f"[create_lesson] error: {e}", file=sys.stderr)
        return 2

    try:
        lesson = create_lesson_from_proposal(
            proposal_dir,
            repo_path=args.repo_path,
            allow_failed=args.allow_failed,
        )
    except FileNotFoundError as e:
        print(f"[create_lesson] error: {e}", file=sys.stderr)
        return 1
    except RuntimeError as e:
        print(f"[create_lesson] refused: {e}", file=sys.stderr)
        return 3
    except Exception as e:
        print(
            f"[create_lesson] unexpected {type(e).__name__}: {e}",
            file=sys.stderr,
        )
        return 4

    print(f"saved lesson: id={lesson.get('id')}")
    print(f"  status={lesson.get('status')}")
    print(f"  active_knowledge_allowed={lesson.get('active_knowledge_allowed')}")
    promotion = (lesson.get("evaluation") or {}).get("promotion")
    print(f"  evaluation.promotion={promotion}")
    return 0


if __name__ == "__main__":
    sys.exit(_main(sys.argv[1:]))
