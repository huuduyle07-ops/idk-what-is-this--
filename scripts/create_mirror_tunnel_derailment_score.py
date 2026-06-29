#!/usr/bin/env python
"""Create a MIRROR.2 Mirror Tunnel Derailment Score Report.

This CLI reads an existing MIRROR.1 trace contract and writes report-only
``mirror_tunnel_derailment_score.json`` / ``mirror_tunnel_derailment_score.md``
artifacts. It never calls models, embeddings, semantic APIs, validation,
benchmarks, MCP tools, workers, Docker/subprocess commands, Dream actions,
Replay janitor actions, network services, databases, route/auth code, or any
execution blocker.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.mirror_tunnel_derailment_score import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_TRACE_PATH,
    build_mirror_tunnel_derailment_score,
    load_trace_contract,
    render_mirror_tunnel_derailment_json,
    write_mirror_tunnel_derailment_score,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def _resolve_trace_path(repo_path: str, raw_trace: str) -> Path:
    repo_root = Path(repo_path or ".").expanduser().resolve()
    candidate = Path(raw_trace or DEFAULT_TRACE_PATH).expanduser()
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.2: score drift from a MIRROR.1 trace contract using "
            "deterministic report-only heuristics. No model, embedding, semantic "
            "API, validation, benchmark, worker, MCP, Docker/subprocess, network, "
            "database, route, auth, patch, or blocking action is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument(
        "--trace",
        default=str(DEFAULT_TRACE_PATH),
        help="MIRROR.1 trace contract JSON path.",
    )
    parser.add_argument("--score-id", default=None, help="Optional deterministic score id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Output directory for the JSON and Markdown artifacts.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Build the report without writing artifacts.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when the trace file is unreadable and only a blocked report can be produced.",
    )
    return parser


def create_score_result(args: argparse.Namespace) -> dict:
    created_at = _resolve_created_at(args.created_at)
    if args.dry_run:
        trace_path = _resolve_trace_path(args.repo_path, args.trace)
        trace = load_trace_contract(trace_path)
        report = build_mirror_tunnel_derailment_score(
            trace=trace,
            trace_path=str(trace_path),
            score_id=args.score_id,
            created_at=created_at,
        )
        return {
            "ok": True,
            "dry_run": True,
            "status": report["verdict"],
            "report": report,
            "markdown": "",
        }

    result = write_mirror_tunnel_derailment_score(
        trace_path=args.trace,
        repo_path=args.repo_path,
        output_root=args.output_root,
        score_id=args.score_id,
        created_at=created_at,
    )
    result["dry_run"] = False
    return result


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.2 - Mirror Tunnel Derailment Score")
    print("=" * 44)
    print(f"Score id     : {report.get('score_id', '')}")
    print(f"Trace id     : {report.get('trace_id', '')}")
    print(f"Verdict      : {report.get('verdict', '')}")
    print(f"Score        : {report.get('overall_derailment_score', 'not_scored')}")
    print(f"Next action  : {report.get('recommended_next_action', '')}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")
    reasons = report.get("insufficient_reasons") if isinstance(report.get("insufficient_reasons"), list) else []
    if reasons:
        print("Insufficient :")
        for reason in reasons:
            print(f"  - {reason}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = create_score_result(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if not args.allow_blocked_report:
            print(f"MIRROR.2 blocked: {exc}", file=sys.stderr)
            return 1
        result = write_mirror_tunnel_derailment_score(
            trace_path=args.trace,
            repo_path=args.repo_path,
            output_root=args.output_root,
            score_id=args.score_id,
            created_at=_resolve_created_at(args.created_at),
        )
        result["dry_run"] = False

    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    if args.json:
        if args.dry_run:
            print(render_mirror_tunnel_derailment_json(report), end="")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)

    if result.get("status") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
