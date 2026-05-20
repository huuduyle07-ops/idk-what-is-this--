#!/usr/bin/env python
"""Phase 7.1 — CLI to create a bounded handoff note without the web UI.

Wraps `core.handoff_notes.create_handoff_note`. Never executes any external
agent. Never modifies the real repo. Default behavior writes a single .md
file under `<AI-project>/.agent/handoffs/`.

Example:
    python scripts/create_handoff_note.py \\
        --title "Fix flaky fixtures" \\
        --worker codex \\
        --task-type proposal_only \\
        --allowed-file core/foo.py \\
        --validation-command "python -m pytest tests/test_foo.py -v"
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core import handoff_notes


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Create a bounded handoff note for an external coding agent.",
    )
    p.add_argument("--title", required=True)
    p.add_argument("--worker", required=True, choices=sorted(handoff_notes.VALID_WORKERS))
    p.add_argument(
        "--task-type", required=True, choices=sorted(handoff_notes.VALID_TASK_TYPES)
    )
    p.add_argument("--repo-path", default=None)
    p.add_argument("--allowed-file", action="append", default=[])
    p.add_argument("--forbidden-file", action="append", default=[])
    p.add_argument("--validation-command", default=None)
    p.add_argument("--context-summary", default="")
    p.add_argument("--expected-output", default="")
    p.add_argument("--extra-safety-rule", action="append", default=[])
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        result = handoff_notes.create_handoff_note(
            title=args.title,
            intended_worker=args.worker,
            task_type=args.task_type,
            repo_path=args.repo_path,
            allowed_files=args.allowed_file or None,
            forbidden_files=args.forbidden_file or None,
            validation_command=args.validation_command,
            context_summary=args.context_summary,
            expected_output=args.expected_output,
            extra_safety_rules=args.extra_safety_rule or None,
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    print(f"created handoff note: {result['path']}")
    print(f"slug: {result['slug']}")
    print(f"status: {result['meta']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())