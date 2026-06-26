"""UX.4 — Create Mixed Mode Intent Router Preview (CLI).

Builds a report-only preview that classifies user text into one of six intent
modes (chat / instant_run / continue_from_frame / commander_plan / clarify /
reject_or_defer) using deterministic signal matching.

UX.4 predicts intent only. It does not dispatch execution, start runs, call
models, apply patches, run validation or benchmarks, contact network services,
launch workers, mutate the repo, push, merge, or open PRs.

Usage:
    python scripts/create_mixed_mode_intent_router_preview.py \\
        --repo-path . \\
        --input "what does this error mean?" \\
        --demo --json
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

from core.mixed_mode_intent_router import (  # noqa: E402
    GUARDRAIL_NOTE,
    PREVIEW_STATUS_READY,
    REPORT_KIND,
    build_mixed_mode_router_preview,
    write_mixed_mode_router_artifacts,
)

DEFAULT_REPO_PATH   = "."
DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "ux" / "mixed_mode_intent_router")


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    return str(raw)


def run_create_mixed_mode_intent_router_preview(
    *,
    repo_path: str = DEFAULT_REPO_PATH,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    preview_id: str | None = None,
    created_at: str | None = None,
    inputs: list[dict[str, Any]] | None = None,
    input_texts: list[str] | None = None,
    input_json: str | None = None,
    demo: bool = False,
) -> dict[str, Any]:
    """Build and write the UX.4 router preview. Returns {ok, json_path, md_path, report}."""
    created_iso = _resolve_created_at(created_at)

    # Resolve inputs: explicit list > input_texts > input_json > demo
    resolved_inputs: list[dict[str, Any]] | None = inputs
    if resolved_inputs is None and input_texts:
        resolved_inputs = [{"user_text": t} for t in input_texts]
    if resolved_inputs is None and input_json:
        try:
            raw = json.loads(input_json)
            resolved_inputs = raw if isinstance(raw, list) else [raw]
        except json.JSONDecodeError:
            resolved_inputs = []

    report = build_mixed_mode_router_preview(
        repo_path=repo_path,
        inputs=resolved_inputs,
        created_at=created_iso,
        preview_id=preview_id,
        demo=demo,
        ui_placeholder_added=True,
    )

    artifacts = write_mixed_mode_router_artifacts(report, output_root)
    return {**artifacts, "report": report}


def _print_summary(result: dict[str, Any]) -> None:
    report = result["report"]
    counts = report.get("mode_counts", {})
    print("UX.4 — Mixed Mode Intent Router Preview")
    print("=" * 40)
    print(f"Preview id      : {report.get('preview_id')}")
    print(f"Repo path       : {report.get('repo_path')}")
    print(f"Preview status  : {report.get('preview_status')}")
    print(f"Input count     : {report.get('input_count', 0)}")
    print(f"Ambiguous       : {len(report.get('ambiguous_inputs', []))}")
    print(f"Rejected/def    : {len(report.get('rejected_or_deferred_inputs', []))}")
    print(f"Mode counts     : {counts}")
    print(f"JSON            : {result.get('json_path')}")
    print(f"Markdown        : {result.get('md_path')}")
    print()
    print("Routing results:")
    for r in report.get("routing_results", []):
        mode = r.get("predicted_mode", "?")
        conf = r.get("confidence", "?")
        text = r.get("input_text", "")[:60]
        print(f"  [{mode}:{conf}] {text!r}")
    print()
    print("Boundaries (UX.4 does not):")
    for b in report.get("boundaries", []):
        print(f"  {b}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="UX.4 — Create Mixed Mode Intent Router Preview (report-only)"
    )
    parser.add_argument("--repo-path",    default=DEFAULT_REPO_PATH)
    parser.add_argument("--output-root",  default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--preview-id",   default=None)
    parser.add_argument("--created-at",   default=None)
    parser.add_argument(
        "--input", dest="inputs", action="append", default=None,
        metavar="TEXT", help="User input text to classify (repeatable)",
    )
    parser.add_argument(
        "--input-json", default=None,
        help="JSON array of router input dicts",
    )
    parser.add_argument("--demo",  action="store_true", default=False)
    parser.add_argument("--json",  dest="json_out", action="store_true", default=False)

    args = parser.parse_args(argv)

    result = run_create_mixed_mode_intent_router_preview(
        repo_path=args.repo_path,
        output_root=args.output_root,
        preview_id=args.preview_id,
        created_at=args.created_at,
        input_texts=args.inputs,
        input_json=args.input_json,
        demo=args.demo,
    )

    if args.json_out:
        report = result["report"]
        summary = {
            "report_kind":   report.get("report_kind", REPORT_KIND),
            "preview_id":    report.get("preview_id"),
            "preview_status": report.get("preview_status"),
            "input_count":   report.get("input_count", 0),
            "mode_counts":   report.get("mode_counts", {}),
            "ambiguous_count":   len(report.get("ambiguous_inputs", [])),
            "rejected_count":    len(report.get("rejected_or_deferred_inputs", [])),
            "json_path":     result.get("json_path"),
            "md_path":       result.get("md_path"),
        }
        print(json.dumps(summary, indent=2))
    else:
        _print_summary(result)

    return 0


if __name__ == "__main__":
    sys.exit(main())
