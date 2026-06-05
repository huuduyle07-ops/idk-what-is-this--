#!/usr/bin/env python
"""Create an evidence-only invariant verification report from local JSON.

Reads one already-written artifact and writes JSON plus Markdown under
``.agent/experiments/``. This CLI does not run validation, benchmarks, models,
patching, lessons, Reverse Dream, mutation oracle, Docker, subprocesses, or
network calls.
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

from core import invariant_verification


REPORT_STEM = "invariant-verification"


class CliError(ValueError):
    """Validation error for user-supplied CLI paths."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create an evidence-only invariant verification report.",
    )
    parser.add_argument("--input-json", required=True, help="Existing local JSON artifact.")
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root that owns .agent/experiments.",
    )
    parser.add_argument("--output-json", default=None, help="Optional output JSON path.")
    parser.add_argument("--output-md", default=None, help="Optional output Markdown path.")
    return parser


def _has_traversal(raw_path: str) -> bool:
    return any(part == ".." for part in Path(raw_path).parts)


def _resolve_raw_path(raw_path: str, repo_path: Path) -> Path:
    if _has_traversal(raw_path):
        raise CliError(f"path traversal is not allowed: {raw_path}")
    path = Path(raw_path)
    if not path.is_absolute():
        path = repo_path / path
    return path.resolve()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _validate_input_json(raw_path: str, repo_path: Path) -> Path:
    path = _resolve_raw_path(raw_path, repo_path)
    if not _is_relative_to(path, repo_path):
        raise CliError(f"input JSON must resolve inside repo path: {path}")
    if not path.exists():
        raise CliError(f"input JSON does not exist: {path}")
    if not path.is_file():
        raise CliError(f"input JSON is not a file: {path}")
    if path.suffix.lower() != ".json":
        raise CliError(f"input artifact must have .json suffix: {path}")
    return path


def _default_output_paths(repo_path: Path) -> tuple[Path, Path]:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    experiments_dir = repo_path / ".agent" / "experiments"
    stem = f"{timestamp}_{REPORT_STEM}"
    return experiments_dir / f"{stem}.json", experiments_dir / f"{stem}.md"


def _validate_output_path(
    raw_path: str | None,
    repo_path: Path,
    *,
    suffix: str,
    default_path: Path,
    input_path: Path,
) -> Path:
    path = default_path if raw_path is None else _resolve_raw_path(raw_path, repo_path)
    if path.suffix.lower() != suffix:
        raise CliError(f"output path must have {suffix} suffix: {path}")
    experiments_dir = repo_path / ".agent" / "experiments"
    if not _is_relative_to(path, experiments_dir):
        raise CliError(f"output path must resolve inside repo/.agent/experiments: {path}")
    if path == input_path:
        raise CliError(f"output path must not overwrite the input artifact: {path}")
    if path.exists():
        raise CliError(f"output path already exists and will not be overwritten: {path}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise CliError(f"input JSON root must be an object: {path}")
    return data


def _remove_partial_artifacts(paths: tuple[Path, Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_artifact_pair(
    output_json: Path,
    output_md: Path,
    report: dict[str, Any],
    markdown: str,
) -> None:
    paths = (output_json, output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    try:
        output_json.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        output_md.write_text(markdown, encoding="utf-8")
    except Exception:
        _remove_partial_artifacts(paths)
        raise


def create_report_artifacts(args: argparse.Namespace) -> dict[str, Path]:
    repo_path = Path(args.repo_path).resolve()
    input_path = _validate_input_json(args.input_json, repo_path)
    default_json, default_md = _default_output_paths(repo_path)
    output_json = _validate_output_path(
        args.output_json,
        repo_path,
        suffix=".json",
        default_path=default_json,
        input_path=input_path,
    )
    output_md = _validate_output_path(
        args.output_md,
        repo_path,
        suffix=".md",
        default_path=default_md,
        input_path=input_path,
    )

    source_record = _read_json(input_path)
    report = invariant_verification.build_invariant_verification(source_record)
    markdown = invariant_verification.format_invariant_verification_markdown(report)
    _write_artifact_pair(output_json, output_md, report, markdown)
    return {"json": output_json, "markdown": output_md}


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        out = create_report_artifacts(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"error: could not read or write invariant artifacts: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON artifact: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly CLI boundary
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    print(f"json: {out['json']}")
    print(f"markdown: {out['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
