"""AUTO.1e — Create a Sandbox Self-Evolution Evidence Pack (CLI).

Bundles the AUTO.1a/1b/1c/1d sandbox self-evolution artifacts into one
human-readable evidence pack. Accepts explicit artifact paths or a ``--trial-dir``
shortcut that discovers the known artifact filenames in a trial directory.

This tool is report-only. It reads the artifacts and packages them; it does not
execute, approve, apply a patch, run validation or a benchmark check, call a
model, write to the real repo, push, merge, open a PR, or contact a remote git
host / chat service / external automation. Human approval is required before any
real repo change.

Usage:
    python scripts/create_self_evolution_evidence_pack.py \\
        --trial-dir .agent/self_evolution_trials/<id>
    python scripts/create_self_evolution_evidence_pack.py \\
        --trial-contract a.json --patch-evaluation c.json --graduation-review d.json --json
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

from core.self_evolution_evidence_pack import (  # noqa: E402
    ARTIFACT_FILENAMES,
    ARTIFACT_KINDS,
    EVIDENCE_PACK_GUARDRAIL_NOTE,
    build_evidence_pack,
    render_evidence_pack_markdown,
)

DEFAULT_OUTPUT_SUBPATH = Path(".agent") / "self_evolution_trials"
JSON_NAME = "self_evolution_evidence_pack.json"
MD_NAME = "self_evolution_evidence_pack.md"


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_pack_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'pack'}_evidence-pack"


def discover_artifacts_in_trial_dir(trial_dir: str | Path) -> dict[str, str]:
    """Return ``{kind: path}`` for known artifact filenames present in a dir."""
    base = Path(trial_dir)
    found: dict[str, str] = {}
    for kind in ARTIFACT_KINDS:
        candidate = base / ARTIFACT_FILENAMES[kind]
        if candidate.is_file():
            found[kind] = str(candidate)
    return found


def _load_artifact(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _resolve_paths(
    trial_dir: str | None,
    explicit: dict[str, str | None],
) -> dict[str, str]:
    resolved: dict[str, str] = {}
    if trial_dir:
        resolved.update(discover_artifacts_in_trial_dir(trial_dir))
    for kind, path in explicit.items():
        if path:
            resolved[kind] = str(path)
    return resolved


def _resolve_output_dir(
    *, output_root: str | None, trial_dir: str | None, resolved_paths: dict[str, str], out_id: str
) -> Path:
    if output_root:
        return Path(output_root) / out_id
    if trial_dir:
        return Path(trial_dir)
    for kind in ARTIFACT_KINDS:
        if kind in resolved_paths:
            return Path(resolved_paths[kind]).parent
    return DEFAULT_OUTPUT_SUBPATH / out_id


def run_create_self_evolution_evidence_pack(
    *,
    trial_dir: str | None = None,
    trial_contract: str | None = None,
    dry_run: str | None = None,
    patch_evaluation: str | None = None,
    graduation_review: str | None = None,
    pack_id: str | None = None,
    created_at: str | float | None = None,
    output_root: str | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load the artifacts, build the evidence pack, and write JSON + Markdown."""
    created_iso = _resolve_created_at(created_at)
    final_pack_id = pack_id or _default_pack_id(created_iso)

    explicit = {
        "contract": trial_contract,
        "dry_run": dry_run,
        "patch_evaluation": patch_evaluation,
        "graduation_review": graduation_review,
    }
    resolved_paths = _resolve_paths(trial_dir, explicit)

    artifacts = {kind: _load_artifact(resolved_paths.get(kind)) for kind in ARTIFACT_KINDS}
    artifact_paths = {kind: resolved_paths.get(kind, "") for kind in ARTIFACT_KINDS}

    record = build_evidence_pack(
        artifacts=artifacts,
        pack_id=final_pack_id,
        created_at=created_iso,
        artifact_paths=artifact_paths,
    )

    out_id = str(record.get("trial_id") or final_pack_id)
    out_dir = _resolve_output_dir(
        output_root=output_root, trial_dir=trial_dir, resolved_paths=resolved_paths, out_id=out_id
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / JSON_NAME
    md_path = out_dir / MD_NAME
    json_path.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")
    md_path.write_text(render_evidence_pack_markdown(record), encoding="utf-8")

    return {"ok": True, "json_path": str(json_path), "md_path": str(md_path), "record": record}


def _print_summary(result: dict[str, Any]) -> None:
    record = result["record"]
    print("AUTO.1e — Sandbox Self-Evolution Evidence Pack")
    print("=" * 46)
    print(f"Pack id          : {record.get('pack_id')}")
    print(f"Trial id         : {record.get('trial_id')}")
    print(f"Final verdict    : {record.get('final_verdict')}")
    print(f"Next step        : {record.get('recommended_next_step')}")
    included = [a.get("label") for a in record.get("source_artifacts") or []]
    print(f"Artifacts        : {', '.join(included) if included else 'none'}")
    missing = record.get("missing_artifacts") or []
    if missing:
        print(f"Missing          : {', '.join(missing)}")
    blockers = record.get("blockers") or []
    if blockers:
        print("Blockers         :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = record.get("warnings") or []
    if warnings:
        print("Warnings         :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {EVIDENCE_PACK_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.1e: bundle the AUTO.1a/1b/1c/1d sandbox self-evolution artifacts into "
            "one human-readable evidence pack. Report-only — it does not execute, apply "
            "a patch, run validation or a benchmark check, or call a model."
        )
    )
    parser.add_argument("--trial-contract", default=None, help="Path to the AUTO.1a trial contract JSON.")
    parser.add_argument("--dry-run", default=None, help="Path to the AUTO.1b dry-run JSON.")
    parser.add_argument("--patch-evaluation", default=None, help="Path to the AUTO.1c patch evaluation JSON.")
    parser.add_argument("--graduation-review", default=None, help="Path to the AUTO.1d graduation review JSON.")
    parser.add_argument(
        "--trial-dir",
        default=None,
        help="Trial directory to discover known AUTO.1 artifacts in (a shortcut).",
    )
    parser.add_argument("--pack-id", default=None, help="Deterministic pack id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--output-root", default=None, help="Override the artifact root.")
    parser.add_argument("--json", action="store_true", help="Print the record JSON.")
    args = parser.parse_args(argv)

    result = run_create_self_evolution_evidence_pack(
        trial_dir=args.trial_dir,
        trial_contract=args.trial_contract,
        dry_run=args.dry_run,
        patch_evaluation=args.patch_evaluation,
        graduation_review=args.graduation_review,
        pack_id=args.pack_id,
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
