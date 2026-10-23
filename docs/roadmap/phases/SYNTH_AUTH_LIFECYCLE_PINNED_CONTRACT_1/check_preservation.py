"""Read-only workspace and original-pin checks; output only new phase evidence.

Use python -B. Baseline records current bytes without replacing any historical
pin. Historical verification imports the unchanged compatibility checker as
definitions only, then compares its original stored manifests in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
PHASE = "SYNTH.AUTH.LIFECYCLE.PINNED.CONTRACT.1"
NEW_PREFIX = OUTPUT.relative_to(ROOT).as_posix() + "/"
NEW_TEST = "tests/test_synthetic_runtime_authorization_lifecycle_pinned_contract.py"
CACHE_PARTS = {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache", ".git", "node_modules", "validation_tmp"}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def candidate_paths():
    result = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT, check=True, stdout=subprocess.PIPE)
    paths = sorted(set(value.decode("utf-8") for value in result.stdout.split(b"\0") if value))
    return [path for path in paths if path != NEW_TEST and not path.startswith(NEW_PREFIX)
        and not (set(Path(path).parts) & CACHE_PARTS)]


def observation(relative):
    path = (ROOT / relative).resolve()
    if not path.is_relative_to(ROOT):
        raise ValueError("Preservation path escapes repository: " + relative)
    if not path.is_file():
        return None
    content = path.read_bytes()
    return {"sha256": digest(content), "size_bytes": len(content)}


def historical():
    source = ROOT / "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/check_historical_preservation.py"
    spec = importlib.util.spec_from_file_location("_frozen_compat_preservation_definitions", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    audit = module.HistoricalAudit()
    error = None
    try:
        audit.run()
    except (OSError, ValueError, KeyError, TypeError) as exception:
        error = type(exception).__name__ + ": " + str(exception)
    report = audit.report(error)
    report.update(phase_id=PHASE, audit_artifact_output=NEW_PREFIX + "historical_preservation.json",
        reused_frozen_checker=source.relative_to(ROOT).as_posix(),
        reused_frozen_checker_sha256=digest(source.read_bytes()),
        reproduce="python -B " + NEW_PREFIX + "check_preservation.py --mode after")
    return report


def write(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("baseline", "after"), required=True)
    args = parser.parse_args()
    baseline_path = OUTPUT / "preservation_baseline.json"
    if args.mode == "baseline":
        if baseline_path.exists():
            raise AssertionError("Original workspace baseline must never be overwritten")
        files = {path: observation(path) for path in candidate_paths()}
        baseline = {"phase_id": PHASE, "schema_version": "additive_workspace_preservation_v1",
            "file_count": len(files), "files": files, "historical_drift_repinned": False,
            "initial_missing_paths": [path for path, value in files.items() if value is None],
            "scope": "All tracked/nonignored workspace files; new phase/test and temporary/cache directories excluded",
            "excluded_path_parts": sorted(CACHE_PARTS)}
        write("preservation_baseline.json", baseline)
        original = historical()
        write("historical_preservation_baseline.json", original)
        print(json.dumps({"workspace_baseline_count": len(files), "historical_result": original["result"],
            "historical_drift_count": original["drift_count"]}, sort_keys=True))
        return 0 if original["historical_preservation_verified"] else 1
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    changed = []
    for path, expected in baseline["files"].items():
        actual = observation(path)
        if actual != expected:
            changed.append({"path": path, "expected": expected, "actual": actual})
    added = sorted(set(candidate_paths()) - set(baseline["files"]))
    report = {"phase_id": PHASE, "baseline_sha256": digest(baseline_path.read_bytes()),
        "files_checked": len(baseline["files"]), "changed": changed, "unexpected_added": added,
        "historical_drift_repinned": False, "passed": not changed and not added}
    write("preservation_after.json", report)
    original = historical()
    write("historical_preservation.json", original)
    print(json.dumps({"files_checked": report["files_checked"], "changed": changed,
        "unexpected_added": added, "historical_result": original["result"],
        "historical_drift_count": original["drift_count"]}, sort_keys=True))
    return 0 if report["passed"] and original["historical_preservation_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
