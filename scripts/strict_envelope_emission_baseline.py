"""WORKER.DECL.2A.1 §21 — offline baseline of what providers already emit.

Before turning the emission experiment on, we need the number it is being
compared against: of the worker responses this repository has *already
recorded*, how many are pure JSON, how many are fenced, how many are prose with
an object buried in them, and how many carry no object at all.

§21 is explicit that the baseline must not cost a live model call per run, so
this reads recorded artifacts and nothing else:

    replay bundles      model_raw_response.txt
    proposal queue      raw_model_response.txt
    dream consultant    raw_model_attempt*.txt

It performs no model call, opens no socket and starts no subprocess — the
boundary suite asserts each absence by name.

On the two classifiers
----------------------

Every response is read by WORKER.DECL.2A's **frozen** strict parser, unchanged
and unweakened, and that status is what the adoption number is made of.

The shape label beside it (``fenced_json`` / ``prose_wrapped_json``) exists only
to say *why* a rejection happened, and it is computed here, in an offline
operator tool, by asking the **legacy** extractor what it would have found.  It
never runs inside a live run, never feeds the strict parser, and cannot change a
strict status: `classify_recorded_response` calls the strict parser first and
copies its verdict out verbatim.

This script is not part of any run.  It reads a directory an operator names, and
writes counts.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

from core.json_utils import extract_json_block  # noqa: E402
from core.strict_envelope_emission import (  # noqa: E402
    EMISSION_OBSERVATION_SCHEMA_VERSION,
    PHASE_ID,
)
from core.worker_patch_envelope import (  # noqa: E402
    MAX_ENVELOPE_RESPONSE_CHARS,
    parse_strict_worker_patch_envelope,
)


#: Recorded worker-response artifacts, by the name each producer writes.
RECORDED_RESPONSE_GLOBS: tuple[str, ...] = (
    "**/model_raw_response.txt",
    "**/raw_model_response.txt",
    "**/raw_model_attempt*.txt",
)

#: Bounded shape vocabulary.  Descriptive only: none of these is a verdict, and
#: none of them can turn a strict rejection into an acceptance.
SHAPE_PURE_JSON_OBJECT = "pure_json_object"
SHAPE_FENCED_JSON = "fenced_json"
SHAPE_PROSE_WRAPPED_JSON = "prose_wrapped_json"
SHAPE_NO_JSON_FOUND = "no_json_found"

RESPONSE_SHAPES: tuple[str, ...] = (
    SHAPE_PURE_JSON_OBJECT,
    SHAPE_FENCED_JSON,
    SHAPE_PROSE_WRAPPED_JSON,
    SHAPE_NO_JSON_FOUND,
)

#: A scan is bounded, and what it drops is reported rather than silently cut.
DEFAULT_MAX_RESPONSES = 5000


def classify_response_shape(text: str) -> str:
    """Why the strict parser said what it said — never whether it should have.

    The legacy extractor is asked what *it* would have recovered, exactly as the
    authoritative path does.  Nothing here is handed to the strict parser.
    """
    stripped = (text or "").strip()
    if not stripped:
        return SHAPE_NO_JSON_FOUND
    if stripped.startswith("{"):
        try:
            if isinstance(json.loads(stripped), dict):
                return SHAPE_PURE_JSON_OBJECT
        except ValueError:
            pass
    recovered = extract_json_block(text)
    if not isinstance(recovered, dict):
        return SHAPE_NO_JSON_FOUND
    if "```" in text:
        return SHAPE_FENCED_JSON
    return SHAPE_PROSE_WRAPPED_JSON


def classify_recorded_response(text: str) -> dict[str, Any]:
    """One recorded response, read by the frozen parser and shape-labelled."""
    parse = parse_strict_worker_patch_envelope(text)
    recovered = extract_json_block(text)
    plan = recovered.get("patch_plan") if isinstance(recovered, dict) else None
    return {
        "strict_status": parse.status,
        "strict_valid": parse.is_valid,
        "response_shape": classify_response_shape(text),
        "legacy_plan_available": isinstance(plan, list) and bool(plan),
    }


def iter_recorded_responses(
    root: Path,
    *,
    limit: int = DEFAULT_MAX_RESPONSES,
) -> Iterable[tuple[Path, str]]:
    """Yield recorded response artifacts under ``root``, bounded and in order."""
    seen: set[Path] = set()
    paths: list[Path] = []
    for pattern in RECORDED_RESPONSE_GLOBS:
        for path in sorted(root.glob(pattern)):
            resolved = path.resolve()
            if resolved in seen or not path.is_file():
                continue
            seen.add(resolved)
            paths.append(path)

    for path in paths[:limit]:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        yield path, text[:MAX_ENVELOPE_RESPONSE_CHARS]


def summarize_recorded_baseline(
    root: Path,
    *,
    limit: int = DEFAULT_MAX_RESPONSES,
) -> dict[str, Any]:
    """Count the current, un-experimented emission behaviour on disk.

    Counts only.  §20 forbids a pass threshold and this reports no rate, no
    score and no verdict: a human reads the distribution.
    """
    by_status: dict[str, int] = {}
    by_shape: dict[str, int] = {}
    strict_valid = 0
    legacy_only = 0
    invalid_both = 0
    scanned = 0

    for _path, text in iter_recorded_responses(root, limit=limit):
        scanned += 1
        record = classify_recorded_response(text)
        status = record["strict_status"]
        shape = record["response_shape"]
        by_status[status] = by_status.get(status, 0) + 1
        by_shape[shape] = by_shape.get(shape, 0) + 1
        if record["strict_valid"]:
            strict_valid += 1
        elif record["legacy_plan_available"]:
            legacy_only += 1
        else:
            invalid_both += 1

    total_available = sum(
        1 for _ in iter_recorded_responses(root, limit=limit + 1)
    )
    return {
        "schema_version": EMISSION_OBSERVATION_SCHEMA_VERSION,
        "phase_id": PHASE_ID,
        "baseline_kind": "recorded_response_shapes",
        "transport_strategy": "legacy_prompt",
        "responses_scanned": scanned,
        "responses_dropped_by_limit": max(0, total_available - scanned),
        "strict_valid": strict_valid,
        "legacy_only": legacy_only,
        "invalid_both": invalid_both,
        "strict_status_counts": dict(sorted(by_status.items())),
        "response_shape_counts": dict(sorted(by_shape.items())),
        "model_calls_performed": 0,
        "network_calls_performed": 0,
        "authoritative_effect": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Classify already-recorded worker responses with WORKER.DECL.2A's "
            "frozen strict parser. Performs no model call and no network call."
        )
    )
    parser.add_argument(
        "--root",
        required=True,
        help="Directory holding recorded run artifacts to scan.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_MAX_RESPONSES,
        help=f"Maximum responses to read (default {DEFAULT_MAX_RESPONSES}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional path to write the JSON report to.",
    )
    args = parser.parse_args(argv)

    root = Path(args.root)
    if not root.is_dir():
        sys.stderr.write(f"not a directory: {root}\n")
        return 2

    report = summarize_recorded_baseline(root, limit=max(0, args.limit))
    rendered = json.dumps(report, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    if report["responses_dropped_by_limit"]:
        sys.stderr.write(
            f"note: {report['responses_dropped_by_limit']} recorded responses "
            f"were not read because --limit was {args.limit}\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
