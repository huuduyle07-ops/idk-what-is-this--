"""AUTO.2a — Create a Telegram Evidence Summary Contract (CLI).

Reads an AUTO.1e sandbox self-evolution evidence pack and writes a deterministic
JSON + Markdown contract describing what a chat-review summary should contain and
what a human may, and may not, do on the strength of it.

This tool is report-only. It does not contact Telegram, send messages, call
Webhooks, make any network request, call models, apply patches, run validation or
a benchmark check, write to the real repo, push, merge, open PRs, or contact a
remote git host / N8N / external automation. Chat approval is not merge authority.

Usage:
    python scripts/create_telegram_evidence_contract.py \\
        --evidence-pack .agent/self_evolution_trials/<id>/self_evolution_evidence_pack.json
    python scripts/create_telegram_evidence_contract.py \\
        --evidence-pack pack.json --output-root .agent/automation_contracts --json
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

from core.telegram_evidence_contract import (  # noqa: E402
    TELEGRAM_EVIDENCE_GUARDRAIL_NOTE,
    render_telegram_evidence_contract_markdown,
    write_telegram_evidence_contract,
)

DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "automation_contracts")

#: Source verdicts that make a contract "not sendable" and so refuse exit 0.
_REFUSED_VERDICTS = ("blocked", "incomplete_pack")


def _resolve_created_at(raw: str | float | None) -> str:
    if raw is None:
        return datetime.now(tz=timezone.utc).isoformat()
    try:
        epoch = float(raw)
    except (TypeError, ValueError):
        return str(raw)
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def _default_contract_id(created_iso: str) -> str:
    stamp = "".join(ch if ch.isalnum() else "-" for ch in created_iso).strip("-")[:24]
    return f"{stamp or 'contract'}_telegram-evidence"


def _load_evidence_pack(path: str) -> tuple[dict[str, Any] | None, str]:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read evidence pack at {path}: {exc}"
    if not isinstance(data, dict):
        return None, f"evidence pack at {path} is not a JSON object"
    return data, ""


def run_create_telegram_evidence_contract(
    *,
    evidence_pack: str,
    output_root: str = DEFAULT_OUTPUT_ROOT,
    contract_id: str | None = None,
    created_at: str | float | None = None,
    json_out: bool = False,
) -> dict[str, Any]:
    """Load the evidence pack, build the contract, and write JSON + Markdown.

    Returns ``{ok, json_path, md_path, contract, is_sendable, refused}``. A pack
    that cannot be read is recorded inside the contract (not a crash); ``refused``
    is true when the source verdict is blocked/incomplete or the pack was unreadable.
    """
    created_iso = _resolve_created_at(created_at)
    final_contract_id = contract_id or _default_contract_id(created_iso)

    pack, load_error = _load_evidence_pack(evidence_pack)

    result = write_telegram_evidence_contract(
        pack if pack is not None else {},
        output_root,
        contract_id=final_contract_id,
        created_at=created_iso,
        source_evidence_pack=str(evidence_pack),
    )
    contract = result["contract"]

    if load_error:
        # Surface the read failure inside the written artifacts, deterministically.
        contract["warnings"] = sorted(set(list(contract.get("warnings") or []) + [load_error]))
        contract["send_blockers"] = sorted(set(list(contract.get("send_blockers") or []) + [load_error]))
        Path(result["json_path"]).write_text(
            json.dumps(contract, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        Path(result["md_path"]).write_text(
            render_telegram_evidence_contract_markdown(contract), encoding="utf-8"
        )

    result["is_sendable"] = bool(contract.get("is_sendable"))
    result["refused"] = bool(load_error) or contract.get("final_verdict") in _REFUSED_VERDICTS
    return result


def _print_summary(result: dict[str, Any]) -> None:
    contract = result["contract"]
    print("AUTO.2a — Telegram Evidence Summary Contract")
    print("=" * 44)
    print(f"Contract id      : {contract.get('contract_id')}")
    print(f"Source pack      : {contract.get('source_evidence_pack')}")
    print(f"Trial id         : {contract.get('trial_id')}")
    print(f"Final verdict    : {contract.get('final_verdict')}")
    print(f"Next step        : {contract.get('recommended_next_step')}")
    print(f"Is sendable      : {contract.get('is_sendable')}")
    blockers = contract.get("send_blockers") or []
    if blockers:
        print("Send blockers    :")
        for blocker in blockers:
            print(f"  - {blocker}")
    warnings = contract.get("warnings") or []
    if warnings:
        print("Warnings         :")
        for warning in warnings:
            print(f"  - {warning}")
    print(f"JSON             : {result['json_path']}")
    print(f"Markdown         : {result['md_path']}")
    print(f"\n> {TELEGRAM_EVIDENCE_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "AUTO.2a: read an AUTO.1e evidence pack and write a chat-review summary "
            "contract. Report-only — it does not contact Telegram, send messages, call "
            "Webhooks, apply patches, run validation or a benchmark check, or call a model."
        )
    )
    parser.add_argument("--evidence-pack", required=True, help="Path to the AUTO.1e evidence pack JSON.")
    parser.add_argument("--output-root", default=DEFAULT_OUTPUT_ROOT, help="Directory to write the contract into.")
    parser.add_argument("--contract-id", default=None, help="Deterministic contract id.")
    parser.add_argument(
        "--created-at",
        default=None,
        help="Deterministic created-at (ISO-8601 string or epoch seconds).",
    )
    parser.add_argument("--json", action="store_true", help="Print the contract JSON.")
    parser.add_argument(
        "--allow-blocked-summary",
        action="store_true",
        help="Write the contract and exit 0 even when the source pack is blocked or incomplete.",
    )
    args = parser.parse_args(argv)

    result = run_create_telegram_evidence_contract(
        evidence_pack=args.evidence_pack,
        output_root=args.output_root,
        contract_id=args.contract_id,
        created_at=args.created_at,
        json_out=args.json,
    )

    if args.json:
        print(json.dumps(result["contract"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)

    if result["refused"] and not args.allow_blocked_summary:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
