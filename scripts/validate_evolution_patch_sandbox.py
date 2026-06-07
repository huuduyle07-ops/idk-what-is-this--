from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[1])
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from core.project_evolution_sandbox_validation import write_project_evolution_sandbox_validation_artifacts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a read-only Project Evolution sandbox validation report.",
    )
    parser.add_argument("--repo-path", required=True, help="Repository root containing .agent/project_evolution artifacts.")
    parser.add_argument("--approval-path", required=True, help="Path to an approval JSON record under .agent/project_evolution/approvals/.")
    parser.add_argument("--patch-draft-package-path", required=True, help="Path to a patch draft package JSON record under .agent/project_evolution/patch_drafts/.")
    parser.add_argument("--patch-candidates-path", required=True, help="Path to a patch candidates JSON record under .agent/project_evolution/patch_candidates/.")
    parser.add_argument("--patch-text-draft-path", required=True, help="Path to a patch text draft JSON record under .agent/project_evolution/patch_text_drafts/.")
    parser.add_argument(
        "--backend",
        default="temp_clone",
        choices=("temp_clone", "docker_ubuntu"),
        help="Sandbox backend to validate in.",
    )
    parser.add_argument(
        "--validation-command",
        default=None,
        help="Optional validation command to screen and report.",
    )
    parser.add_argument(
        "--max-timeout",
        type=int,
        default=300,
        help="Maximum validation timeout in seconds.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = write_project_evolution_sandbox_validation_artifacts(
        repo_path=args.repo_path,
        approval_path=args.approval_path,
        patch_draft_package_path=args.patch_draft_package_path,
        patch_candidates_path=args.patch_candidates_path,
        patch_text_draft_path=args.patch_text_draft_path,
        backend=args.backend,
        validation_command=args.validation_command,
        max_timeout=args.max_timeout,
    )
    record = result["record"]
    if record.get("status") == "error":
        print(f"error: {record['error']['message']}", file=sys.stderr)
        return 1

    print(f"json_path: {result['json_path']}")
    print(f"md_path: {result['md_path']}")
    print(f"backend: {record['backend']}")
    print(f"backend_available: {record['backend_available']}")
    print(f"apply_result_status: {record['apply_result']['status']}")
    print(f"validation_result_status: {record['validation_result']['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

