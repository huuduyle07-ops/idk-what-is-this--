#!/usr/bin/env python
"""Create a MIRROR.3 Claim-vs-Diff Mirror Check.

This CLI reads an existing MIRROR.1 trace contract, an optional MIRROR.2 score
report, and optional explicit evidence artifacts. It writes report-only
``mirror_tunnel_claim_diff_check.json`` / ``mirror_tunnel_claim_diff_check.md``
artifacts. It never calls models, embeddings, semantic APIs, validation,
benchmarks, MCP tools, workers, Docker/subprocess commands, Dream actions,
Replay janitor actions, network services, databases, route/auth code, patch
application, or any execution blocker.
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

from core.mirror_tunnel_claim_diff_check import (  # noqa: E402
    DEFAULT_OUTPUT_ROOT,
    DEFAULT_TRACE_PATH,
    build_mirror_tunnel_claim_diff_check,
    render_mirror_tunnel_claim_diff_json,
    write_mirror_tunnel_claim_diff_check,
)
from core.mirror_tunnel_claim_diff_check import (  # noqa: E402
    _load_explicit_artifacts,
    _load_json_object,
    _resolve_input_path,
)


DEFAULT_REPO_PATH = "."


def _resolve_created_at(raw: str | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).replace(microsecond=0).isoformat()
    return str(raw)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "MIRROR.3: compare claims against diff, validation, benchmark, and "
            "artifact evidence using deterministic report-only heuristics. No "
            "model, embedding, semantic API, validation, benchmark, worker, MCP, "
            "Docker/subprocess, network, database, route, auth, patch, or "
            "blocking action is performed."
        )
    )
    parser.add_argument("--repo-path", default=DEFAULT_REPO_PATH, help="Repository root.")
    parser.add_argument("--trace", default=str(DEFAULT_TRACE_PATH), help="MIRROR.1 trace contract JSON path.")
    parser.add_argument("--score", default="", help="Optional MIRROR.2 derailment score JSON path.")
    parser.add_argument("--patch-json", default="", help="Optional patch metadata JSON artifact.")
    parser.add_argument("--diff", default="", help="Optional diff text artifact.")
    parser.add_argument("--validation-json", default="", help="Optional validation JSON/text artifact.")
    parser.add_argument("--benchmark-json", default="", help="Optional benchmark JSON/text artifact.")
    parser.add_argument("--final-answer-file", default="", help="Optional final answer text artifact.")
    parser.add_argument("--worker-reply-file", default="", help="Optional worker reply text artifact.")
    parser.add_argument("--check-id", default=None, help="Optional deterministic check id.")
    parser.add_argument("--created-at", default=None, help="Optional deterministic created-at timestamp.")
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT), help="Output directory for artifacts.")
    parser.add_argument("--dry-run", action="store_true", help="Build the report without writing artifacts.")
    parser.add_argument("--json", action="store_true", help="Print deterministic JSON.")
    parser.add_argument(
        "--allow-blocked-report",
        action="store_true",
        help="Exit 0 even when an input artifact is blocked or unreadable.",
    )
    return parser


def create_check_result(args: argparse.Namespace) -> dict:
    created_at = _resolve_created_at(args.created_at)
    if args.dry_run:
        repo_root = Path(args.repo_path or ".").expanduser().resolve()
        trace_file = _resolve_input_path(repo_root, args.trace, required=True)
        score_file = _resolve_input_path(repo_root, args.score, required=False)
        artifact_paths = {
            "patch_json": _resolve_input_path(repo_root, args.patch_json, required=False),
            "diff": _resolve_input_path(repo_root, args.diff, required=False),
            "validation_json": _resolve_input_path(repo_root, args.validation_json, required=False),
            "benchmark_json": _resolve_input_path(repo_root, args.benchmark_json, required=False),
            "final_answer_file": _resolve_input_path(repo_root, args.final_answer_file, required=False),
            "worker_reply_file": _resolve_input_path(repo_root, args.worker_reply_file, required=False),
        }
        trace = _load_json_object(trace_file, "trace contract")
        score = _load_json_object(score_file, "derailment score") if score_file else {}
        report = build_mirror_tunnel_claim_diff_check(
            trace=trace,
            score=score,
            explicit_artifacts=_load_explicit_artifacts(artifact_paths),
            trace_path=str(trace_file),
            score_path=str(score_file or ""),
            check_id=args.check_id,
            created_at=created_at,
        )
        return {"ok": True, "dry_run": True, "status": report["overall_claim_support"], "report": report, "markdown": ""}

    result = write_mirror_tunnel_claim_diff_check(
        repo_path=args.repo_path,
        trace_path=args.trace,
        score_path=args.score or None,
        patch_json_path=args.patch_json or None,
        diff_path=args.diff or None,
        validation_json_path=args.validation_json or None,
        benchmark_json_path=args.benchmark_json or None,
        final_answer_file=args.final_answer_file or None,
        worker_reply_file=args.worker_reply_file or None,
        output_root=args.output_root,
        check_id=args.check_id,
        created_at=created_at,
    )
    result["dry_run"] = False
    return result


def _print_text(result: dict) -> None:
    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    print("MIRROR.3 - Claim-vs-Diff Mirror Check")
    print("=" * 42)
    print(f"Check id     : {report.get('check_id', '')}")
    print(f"Trace id     : {report.get('trace_id', '')}")
    print(f"Support      : {report.get('overall_claim_support', '')}")
    print(f"Next action  : {report.get('recommended_next_action', '')}")
    if result.get("json_path"):
        print(f"JSON         : {result.get('json_path')}")
    if result.get("md_path"):
        print(f"Markdown     : {result.get('md_path')}")


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = create_check_result(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if not args.allow_blocked_report:
            print(f"MIRROR.3 blocked: {exc}", file=sys.stderr)
            return 1
        result = write_mirror_tunnel_claim_diff_check(
            repo_path=args.repo_path,
            trace_path=args.trace,
            score_path=args.score or None,
            patch_json_path=args.patch_json or None,
            diff_path=args.diff or None,
            validation_json_path=args.validation_json or None,
            benchmark_json_path=args.benchmark_json or None,
            final_answer_file=args.final_answer_file or None,
            worker_reply_file=args.worker_reply_file or None,
            output_root=args.output_root,
            check_id=args.check_id,
            created_at=_resolve_created_at(args.created_at),
        )
        result["dry_run"] = False

    report = result.get("report") if isinstance(result.get("report"), dict) else {}
    if args.json:
        if args.dry_run:
            print(render_mirror_tunnel_claim_diff_json(report), end="")
        else:
            print(json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_text(result)

    if result.get("status") == "blocked" and not args.allow_blocked_report:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
