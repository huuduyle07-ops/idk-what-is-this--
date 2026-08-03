"""Write the deterministic CTX.SELECT.1 JSON and Markdown contract artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.context_selection import (  # noqa: E402
    CONTRACT_JSON_NAME,
    CONTRACT_MARKDOWN_NAME,
    build_candidate_selection_contract,
    render_candidate_selection_contract_json,
    render_candidate_selection_contract_markdown,
)


DEFAULT_OUTPUT_ROOT = Path(".agent") / "context_selection"


def run_create_context_selection_contract(
    *,
    output_root: str | Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    contract = build_candidate_selection_contract()
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    json_path = root / CONTRACT_JSON_NAME
    markdown_path = root / CONTRACT_MARKDOWN_NAME
    json_path.write_text(
        render_candidate_selection_contract_json(contract),
        encoding="utf-8",
        newline="\n",
    )
    markdown_path.write_text(
        render_candidate_selection_contract_markdown(contract),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "ok": True,
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "contract": contract,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Create the pure CTX.SELECT.1 candidate-selection contract"
    )
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--json", action="store_true", dest="json_output")
    args = parser.parse_args(argv)
    result = run_create_context_selection_contract(output_root=args.output_root)
    if args.json_output:
        print(
            json.dumps(
                {
                    "ok": result["ok"],
                    "phase_id": result["contract"]["phase_id"],
                    "contract_status": result["contract"]["contract_status"],
                    "json_path": result["json_path"],
                    "markdown_path": result["markdown_path"],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"JSON: {result['json_path']}")
        print(f"Markdown: {result['markdown_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
