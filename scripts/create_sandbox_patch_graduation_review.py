"""AUTO.1d — Create a Sandbox Patch Graduation Review (CLI).

Reads a sandbox patch candidate evaluation artifact (the AUTO.1c report) and
decides whether the candidate is eligible for human review. Writes a graduation
review artifact next to the source evaluation when possible, otherwise under a
folder named for the review id.

This tool is review-only. It does not apply patches, run validation, run a
benchmark check, call a model, write to the real repo, push, merge, open a PR,
or contact a remote git host / chat service / external automation. Human
approval is required before any real repo change.

Usage:
    python scripts/create_sandbox_patch_graduation_review.py \\
        --evaluation .agent/self_evolution_trials/<id>/patch_candidate_evaluation.json
    python scripts/create_sandbox_patch_graduation_review.py \\
        --evaluation candidate_eval.json --review-id rev-1 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.sandbox_patch_graduation_review import (  # noqa: E402
    GRADUATION_GUARDRAIL_NOTE,
    build_graduation_review,
    render_graduation_review_markdown,
)

DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "self_evolution_trials"
JSON_NAME = "patch_graduation_review.json"
MD_NAME = "patch_graduation_review.md"


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_review_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'review'}_patch-graduation-review"


def _load_evaluation(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_output_dir(
    *, output_root: str | None, evaluation_path: str | None, out_id: str
) -> Path:
    if output_root:
        return Path(output_root) / out_id
    if evaluation_path:
        parent = Path(evaluation_path).parent
        if parent.is_dir():
            return parent
    return DEFAULT_OUTPUT_SUBPATH / out_id


def run_create_sandbox_patch_graduation_review(
    *,
    evaluation_path: str,
    review_id: str | None = None,
    created_at: str | float | None = None,
    output_root: str | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Read the evaluation artifact, build the review, and write JSON + Markdown."""
    created_iso = _resolve_created_at(created_at)
    final_review_id = review_id or _default_review_id(created_iso)
    evaluation = _load_evaluation(evaluation_path)

    record = build_graduation_review(
        evaluation=evaluation,
        source_evaluation_path=str(evaluation_path or ""),
        review_id=final_review_id,
        created_at=created_iso,
    )

    out_id = str(record.get("trial_id") or final_review_id)
    out_dir = _resolve_output_dir(
        output_root=output_root, evaluation_path=evaluation_path, out_id=out_id
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_graduation_review_markdown(record), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "record": record}


def _print_summary(result: dict[str, Any]) -> None:
    record = result["record"]
    print("AUTO.1d — Sandbox Patch Graduation Review")
    print("=" * 46)
    print(f"Review id         : {record.get('review_id')}")
    print(f"Trial id          : {record.get('trial_id')}")
    print(f"Source evaluation : {record.get('source_evaluation_path') or '(inline)'}")
    print(f"Source verdict    : {record.get('source_verdict') or '(none)'}")
    print(f"Graduation verdict: {record.get('graduation_verdict')}")
    print(f"Next step         : {record.get('recommended_next_step')}")
    blockers = record.get("blockers") or []
    if blockers:
        print("Blockers          :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = record.get("warnings") or []
    if warnings:
        print("Warnings          :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON              : {result['json_path']}")
    print(f"Markdown          : {result['md_path']}")
    print(f"\n> {GRADUATION_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1d: read a sandbox patch candidate evaluation artifact and decide "
            "whether the candidate is eligible for human review. Review-only — it "
            "does not apply patches, run validation, run a benchmark check, or call "
            "a model."
        )
    )
    parser.add_argument(
        "--evaluation",
        required=True,
        help="Path to an AUTO.1c patch candidate evaluation JSON artifact.",
    )
    parser.add_argument("--review-id", default=None, help="Deterministic review id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--output-root", default=None, help="Override the artifact root.")
    parser.add_argument("--json", action="store_true", help="Print the record JSON.")
    args = parser.parse_args(argv)

    result = run_create_sandbox_patch_graduation_review(
        evaluation_path=args.evaluation,
        review_id=args.review_id,
        created_at=args.created_at,
        output_root=args.output_root,
        json_out=args.json,
    )

    if not result["ok"]:
        print(f"Error: {result.get('error', 'unknown error')}")
        return 1

    if args.json:
        print(json.dumps(result["record"], indent=2, ensure_ascii=False))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
