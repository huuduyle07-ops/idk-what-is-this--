"""INDEX.1D.1 - write the deterministic Dual Graph Lifecycle Contract.

This artifact builder serializes the pure contract to JSON and Markdown. It does
not scan or index a repository, create either graph, access a database or
manifest, call a model or API, run embeddings, or delete graph artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from core.dual_graph_lifecycle import (  # noqa: E402
    CONTRACT_JSON_NAME,
    CONTRACT_MD_NAME,
    DUAL_GRAPH_GUARDRAIL_NOTE,
    build_dual_graph_lifecycle_contract,
    render_dual_graph_lifecycle_json,
    render_dual_graph_lifecycle_markdown,
)


DEFAULT_OUTPUT_ROOT = str(Path(".agent") / "index" / "dual_graph_lifecycle")


def run_create_dual_graph_lifecycle_contract(
    *,
    output_root: str = DEFAULT_OUTPUT_ROOT,
) -> dict[str, Any]:
    """Write fixed-name deterministic contract artifacts."""
    contract = build_dual_graph_lifecycle_contract()
    output = Path(output_root)
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / CONTRACT_JSON_NAME
    md_path = output / CONTRACT_MD_NAME
    json_path.write_text(render_dual_graph_lifecycle_json(contract), encoding="utf-8")
    md_path.write_text(
        render_dual_graph_lifecycle_markdown(contract),
        encoding="utf-8",
    )
    return {
        "ok": True,
        "json_path": str(json_path),
        "md_path": str(md_path),
        "contract": contract,
    }


def _print_summary(result: dict[str, Any]) -> None:
    print("INDEX.1D.1 - Dual Graph Lifecycle Contract")
    print("=" * 45)
    print(f"JSON     : {result['json_path']}")
    print(f"Markdown : {result['md_path']}")
    print(f"\n> {DUAL_GRAPH_GUARDRAIL_NOTE}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Write the contract-only INDEX.1D.1 JSON and Markdown artifacts. "
            "No graph runtime behavior is created or invoked."
        )
    )
    parser.add_argument(
        "--output-root",
        default=DEFAULT_OUTPUT_ROOT,
        help="Directory for the fixed-name contract artifacts.",
    )
    parser.add_argument("--json", action="store_true", help="Print contract JSON.")
    args = parser.parse_args(argv)
    result = run_create_dual_graph_lifecycle_contract(output_root=args.output_root)
    if args.json:
        print(json.dumps(result["contract"], indent=2, ensure_ascii=False, sort_keys=True))
    else:
        _print_summary(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
