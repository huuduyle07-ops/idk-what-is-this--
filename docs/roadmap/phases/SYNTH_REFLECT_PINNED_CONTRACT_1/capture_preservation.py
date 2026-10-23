"""Read-only preservation capture; all evidence writes stay in this phase."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
EXCLUDED_NAMES = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
}


def snapshot() -> dict:
    hashes = {}
    excluded = []
    for current, dirs, files in os.walk(ROOT):
        base = Path(current)
        retained = []
        for name in sorted(dirs):
            target = base / name
            if target == PHASE or name in EXCLUDED_NAMES:
                excluded.append(target.relative_to(ROOT).as_posix() + "/")
            else:
                retained.append(name)
        dirs[:] = retained
        for name in sorted(files):
            path = base / name
            data = path.read_bytes()
            hashes[path.relative_to(ROOT).as_posix()] = {
                "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)
            }
    return {
        "method": "SHA-256 of raw bytes; no imports of repository capability owners",
        "root": str(ROOT), "excluded": sorted(excluded),
        "files": hashes, "file_count": len(hashes),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=("baseline", "after"))
    args = parser.parse_args()
    if args.mode == "baseline" and (PHASE / "preservation_baseline.json").exists():
        raise AssertionError("The frozen original preservation baseline must not be overwritten")
    current = snapshot()
    (PHASE / f"preservation_{args.mode}.json").write_text(
        json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"], cwd=ROOT,
        capture_output=True, text=True, check=False,
    )
    (PHASE / f"git_status_{args.mode}.txt").write_text(status.stdout, encoding="utf-8")
    if args.mode == "baseline":
        print(json.dumps({"baseline_file_count": current["file_count"], "status_exit_code": status.returncode}))
        return 0
    baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
    before, after = baseline["files"], current["files"]
    changed = sorted(k for k in before.keys() & after.keys() if before[k] != after[k])
    deleted = sorted(before.keys() - after.keys())
    added = sorted(after.keys() - before.keys())
    result = {
        "baseline_file_count": len(before), "after_file_count": len(after),
        "changed": changed, "deleted": deleted, "added_outside_new_phase": added,
        "allowed_additions": ["tests/test_synthetic_reflection_pinned_contract.py"],
        "historical_preservation_passed": not (changed or deleted or
            set(added) - {"tests/test_synthetic_reflection_pinned_contract.py"}),
        "initial_dirty_workspace_preserved": not (changed or deleted),
    }
    (PHASE / "preservation_comparison.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
    return 0 if result["historical_preservation_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
