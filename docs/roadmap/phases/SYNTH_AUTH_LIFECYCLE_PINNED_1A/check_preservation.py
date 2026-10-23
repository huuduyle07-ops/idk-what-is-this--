"""Capture/check existing historical bytes without changing historical files."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUTPUT = Path(__file__).resolve().parent
FROZEN_TESTS = (
    "test_synthetic_runtime_authorization.py",
    "test_synthetic_runtime_authorization_lifecycle.py",
    "test_synthetic_runtime_authorization_pinned.py",
    "test_synthetic_runtime_authorization_lifecycle_pinned_compat.py",
    "test_synthetic_runtime_authorization_lifecycle_pinned_contract.py",
    "test_patch_candidate_behavior_executor1r.py",
    "test_patch_candidate_behavior_executor1r_lifecycle_retry.py",
    "test_synthetic_read_only_reflection.py",
    "test_synthetic_reflection_execution_admission.py",
    "test_synthetic_reflection_execution_lifecycle.py",
    "test_phase_registry.py",
    "test_phase_picker.py",
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def historical_paths():
    paths = set((ROOT / "core").rglob("*"))
    paths.update((ROOT / "scripts").glob("replay*"))
    paths.update((ROOT / "tests" / "fixtures").rglob("*"))
    paths.update(path for path in (ROOT / "docs/roadmap/phases").rglob("*")
        if not path.is_relative_to(OUTPUT))
    paths.update((ROOT / "tests" / name) for name in FROZEN_TESTS)
    paths.update(ROOT / name for name in (
        "docs/roadmap/phase_registry.json", "benchmarks/run_benchmarks.py"))
    return sorted(path for path in paths if path.is_file())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "check"), required=True)
    args = parser.parse_args()
    baseline_path = OUTPUT / "preservation_baseline.json"
    if args.mode == "baseline":
        if baseline_path.exists():
            raise AssertionError("Preservation baseline is immutable")
        result = {"mode": "baseline", "sha256": {
            path.relative_to(ROOT).as_posix(): digest(path) for path in historical_paths()}}
        result["file_count"] = len(result["sha256"])
        baseline_path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps({"file_count": result["file_count"], "baseline_captured": True}))
        return 0
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))["sha256"]
    missing = [name for name in baseline if not (ROOT / name).is_file()]
    changed = [name for name, sha in baseline.items()
        if (ROOT / name).is_file() and digest(ROOT / name) != sha]
    current = {path.relative_to(ROOT).as_posix() for path in historical_paths()}
    added = sorted(current.difference(baseline))
    allowed_additions = ["core/synthetic_runtime_authorization_pinned_lifecycle.py"]
    unexpected = [name for name in added if name not in allowed_additions]
    result = {"mode": "check", "baseline_file_count": len(baseline),
        "missing": missing, "changed": changed, "added": added,
        "allowed_additions": allowed_additions, "unexpected_additions": unexpected,
        "historical_bytes_preserved": not missing and not changed and not unexpected}
    (OUTPUT / "preservation_check.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["historical_bytes_preserved"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
