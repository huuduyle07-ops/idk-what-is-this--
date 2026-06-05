#!/usr/bin/env python
"""Create a read-only anti-lesson CONTROL dogfood evaluation report.

Consumes already-written JSON benchmark/experiment reports and writes JSON plus
Markdown artifacts under ``.agent/experiments/``. This CLI does not run
benchmarks, call models, spawn subprocesses, mutate lessons, patch files, or
change CONTROL prompts.
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

from core import anti_lesson_dogfood as dogfood


REPORT_STEM = "anti-lesson-control-dogfood"


class CliError(ValueError):
    """Validation error for user-supplied CLI paths."""


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Create a read-only anti-lesson CONTROL dogfood evaluation report.",
    )
    parser.add_argument("--baseline-report", required=True, help="Baseline JSON report path.")
    parser.add_argument("--experiment-report", required=True, help="Experiment JSON report path.")
    parser.add_argument(
        "--repo-path",
        required=True,
        help="Repository root that owns .agent/benchmarks and .agent/experiments.",
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


def _validate_source_report(raw_path: str, repo_path: Path) -> Path:
    path = _resolve_raw_path(raw_path, repo_path)
    if not path.exists():
        raise CliError(f"source report does not exist: {path}")
    if not path.is_file():
        raise CliError(f"source report is not a file: {path}")
    if path.suffix.lower() != ".json":
        raise CliError(f"source report must have .json suffix: {path}")

    allowed_roots = (
        repo_path / ".agent" / "benchmarks",
        repo_path / ".agent" / "experiments",
    )
    if not any(_is_relative_to(path, root) for root in allowed_roots):
        raise CliError(
            "source report must resolve inside repo/.agent/benchmarks or "
            f"repo/.agent/experiments: {path}"
        )
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
    input_paths: set[Path],
) -> Path:
    path = default_path if raw_path is None else _resolve_raw_path(raw_path, repo_path)
    if path.suffix.lower() != suffix:
        raise CliError(f"output path must have {suffix} suffix: {path}")

    experiments_dir = repo_path / ".agent" / "experiments"
    if not _is_relative_to(path, experiments_dir):
        raise CliError(f"output path must resolve inside repo/.agent/experiments: {path}")
    if path in input_paths:
        raise CliError(f"output path must not overwrite an input report: {path}")
    if path.exists():
        raise CliError(f"output path already exists and will not be overwritten: {path}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise CliError(f"source report JSON root must be an object: {path}")
    return data


def _write_text_artifact(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _remove_partial_artifacts(paths: tuple[Path, Path]) -> None:
    for path in paths:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _write_artifact_pair(output_json: Path, output_md: Path, report: dict[str, Any], markdown: str) -> None:
    paths = (output_json, output_md)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    try:
        _write_text_artifact(output_json, json.dumps(report, indent=2, sort_keys=True) + "\n")
        _write_text_artifact(output_md, markdown)
    except Exception:
        _remove_partial_artifacts(paths)
        raise


def create_report_artifacts(args: argparse.Namespace) -> dict[str, Path]:
    repo_path = Path(args.repo_path).resolve()
    baseline_path = _validate_source_report(args.baseline_report, repo_path)
    experiment_path = _validate_source_report(args.experiment_report, repo_path)
    default_json, default_md = _default_output_paths(repo_path)
    input_paths = {baseline_path, experiment_path}
    output_json = _validate_output_path(
        args.output_json,
        repo_path,
        suffix=".json",
        default_path=default_json,
        input_paths=input_paths,
    )
    output_md = _validate_output_path(
        args.output_md,
        repo_path,
        suffix=".md",
        default_path=default_md,
        input_paths=input_paths,
    )

    baseline_report = _read_json(baseline_path)
    experiment_report = _read_json(experiment_path)
    report = dogfood.build_anti_lesson_dogfood_report(baseline_report, experiment_report)
    markdown = dogfood.format_anti_lesson_dogfood_markdown(report)

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
        print(f"error: could not read or write report artifacts: {exc}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON report: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 - friendly CLI boundary
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    print(f"json: {out['json']}")
    print(f"markdown: {out['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
