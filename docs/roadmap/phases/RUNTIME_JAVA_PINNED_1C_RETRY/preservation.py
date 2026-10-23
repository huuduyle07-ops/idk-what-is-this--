"""Additive, byte-exact retry preservation; no runtime owner is imported."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
BASELINE = PHASE / "preservation_baseline.json"
SNAPSHOT = PHASE / "reviewed_source_runtime_java_pinned_provider.py"
PROVIDER = "core/runtime_java_pinned_provider.py"
CORRECTED_SHA256 = "bca4a46363a27e23fba60cbc556eb30e3f2b6e03f4ed6e95c81ac7231756ddaa"
ATTEMPT1_SHA256 = "e1edf506c522515199a98a0ff90e1985dbfce0235854ac9978b549c5938b8bee"
ATTEMPT1_PHASE = "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C/"
RETRY_PHASE = "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1C_RETRY/"
PRIOR_BASELINES = (
    "docs/roadmap/phases/RUNTIME_JAVA_REQUIREMENT_PINNED_1/preservation_baseline.json",
    "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1A/preservation_baseline.json",
    "docs/roadmap/phases/RUNTIME_JAVA_PINNED_1B/preservation_baseline.json",
    ATTEMPT1_PHASE + "preservation_baseline.json",
)
FROZEN_ATTEMPT1 = {
    "RUNTIME_JAVA_PINNED_1C_REPORT.json": "9562bc27c7b9997695340628899330352284ed427f5ecd85140a77b5bf873ebe",
    "RUNTIME_JAVA_PINNED_1C_LOCAL.json": "726c138e666e61f4112db32014c5502cf16c9c98d8269045183144387e3738a8",
    "attempt_source_runtime_java_pinned_provider.py": ATTEMPT1_SHA256,
    "live_attempt_gates.json": "0b7c096b6fd2bf4fc169c1b961ba5b08fa83104fbf498446ca17b00925a24751",
    "preservation_baseline.json": "93686ceb9ed76f5214b2747b1fb4a36bcae41c5dc0f19f3092caa11b5d40cb8c",
}
EXCLUDED_COMPONENTS = {
    ".git", ".agent", ".agents", ".codex", ".aws", "__pycache__",
    ".pytest_cache", "node_modules", ".venv", "venv", ".mypy_cache",
    ".codex_cache", "pytest_cache", "pytest", ".pytest_tmp", "target",
    "build", "dist", ".tmp", "tmp",
}
EXCLUDED_PREFIXES = ("tmp_tests", "validation_temp_", "validation-temp-")


def _read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_new(path: Path, value):
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _excluded(relative: str) -> bool:
    path = Path(relative)
    return (relative.replace("\\", "/").startswith(RETRY_PHASE)
            or any(part in EXCLUDED_COMPONENTS or part.startswith(EXCLUDED_PREFIXES)
                   for part in path.parts)
            or path.name == ".env" or path.suffix in {".log", ".pyc", ".pyo"})


def _rows(baseline):
    files = baseline["files"]
    rows = ({"path": path, **row} for path, row in files.items()) if isinstance(files, dict) else files
    for row in rows:
        yield {"path": row["path"].replace("\\", "/"), "sha256": row["sha256"],
               "size_bytes": row.get("size_bytes", row.get("size"))}


def _verify(rows):
    changed, missing = [], []
    count = 0
    for row in rows:
        count += 1
        path = ROOT / row["path"]
        if not path.is_file():
            missing.append(row["path"])
            continue
        content = path.read_bytes()
        actual = sha256(content).hexdigest()
        if actual != row["sha256"] or (row.get("size_bytes") is not None
                                        and len(content) != row["size_bytes"]):
            changed.append({"path": row["path"], "expected_sha256": row["sha256"],
                            "actual_sha256": actual, "expected_size_bytes": row.get("size_bytes"),
                            "actual_size_bytes": len(content)})
    return {"files_checked": count, "changed": changed, "missing": missing,
            "all_bytes_preserved": not changed and not missing, "historical_repins": False}


def original_baseline_checks():
    checks = []
    originals = {}
    conflicts = []
    for relative in PRIOR_BASELINES:
        path = ROOT / relative
        rows = list(_rows(_read(path)))
        # The 1C baseline's entire frozen set is authoritative. Earlier expansive
        # snapshots also contain generated caches/temp trees outside phase scope.
        historical = rows if relative == PRIOR_BASELINES[-1] else [
            row for row in rows if not _excluded(row["path"])]
        checks.append({"baseline": relative, "baseline_sha256": sha256(path.read_bytes()).hexdigest(),
                       "recorded_files": len(rows), "generated_rows_excluded": len(rows) - len(historical),
                       **_verify(historical)})
        for row in historical:
            existing = originals.get(row["path"])
            if existing is not None and existing["sha256"] != row["sha256"]:
                conflicts.append({"path": row["path"], "first_original_sha256": existing["sha256"],
                                  "later_baseline": relative, "later_sha256": row["sha256"]})
            else:
                originals.setdefault(row["path"], {**row, "origin": relative})
    return checks, originals, conflicts


def _inventory():
    args = ["rg", "--files", "--hidden", "--no-ignore"]
    for part in sorted(EXCLUDED_COMPONENTS):
        args.extend(["-g", "!**/" + part + "/**"])
    for prefix in EXCLUDED_PREFIXES:
        args.extend(["-g", "!**/" + prefix + "*/**"])
    args.extend(["-g", "!" + RETRY_PHASE + "**"])
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, check=True)
    return sorted({path.replace("\\", "/") for path in result.stdout.splitlines()
                   if not _excluded(path)})


def capture():
    if BASELINE.exists():
        raise ValueError("retry_preservation_baseline_already_exists_no_repin")
    prior_checks, originals, conflicts = original_baseline_checks()
    pinned = [{"path": ATTEMPT1_PHASE + name, "sha256": digest}
              for name, digest in FROZEN_ATTEMPT1.items()]
    attempt1_check = _verify(pinned)
    if conflicts or not all(row["all_bytes_preserved"] for row in prior_checks) or not attempt1_check["all_bytes_preserved"]:
        return {"captured": False, "original_baseline_checks": prior_checks,
                "original_baseline_conflicts": conflicts, "attempt1_check": attempt1_check}
    current_source = (ROOT / PROVIDER).read_bytes()
    current_sha = sha256(current_source).hexdigest()
    if current_sha != CORRECTED_SHA256 or current_sha == ATTEMPT1_SHA256:
        raise ValueError("retry_corrected_source_not_reviewed_expected_hash:" + current_sha)
    if SNAPSHOT.exists():
        if SNAPSHOT.read_bytes() != current_source:
            raise ValueError("retry_reviewed_source_snapshot_already_exists_with_different_bytes")
    else:
        with SNAPSHOT.open("xb") as handle:
            handle.write(current_source)
    for relative in _inventory():
        if relative not in originals:
            content = (ROOT / relative).read_bytes()
            originals[relative] = {"path": relative, "size_bytes": len(content),
                                   "sha256": sha256(content).hexdigest(),
                                   "origin": "retry_supplement_only"}
    result = {"schema_version": "runtime_java_pinned_1c_retry_preservation_baseline_v1",
              "phase_id": "RUNTIME.JAVA.PINNED.1C", "attempt": 2,
              "created_utc": datetime.now(timezone.utc).isoformat(),
              "scope": "Original historical hashes retained unchanged; additive retry supplement authenticates existing non-temp repository files and every frozen Attempt 1 artifact. Retry folder excluded from historical set.",
              "historical_repins": False, "original_baseline_checks": prior_checks,
              "original_baseline_conflicts": conflicts, "attempt1_check": attempt1_check,
              "excluded_components": sorted(EXCLUDED_COMPONENTS),
              "excluded_prefixes": list(EXCLUDED_PREFIXES), "excluded_phase": RETRY_PHASE,
              "reviewed_provider_source": {"path": PROVIDER, "sha256": current_sha,
                                          "size_bytes": len(current_source),
                                          "snapshot": SNAPSHOT.name,
                                          "attempt1_source_sha256": ATTEMPT1_SHA256,
                                          "different_from_attempt1": True},
              "file_count": len(originals), "files": [originals[path] for path in sorted(originals)]}
    _write_new(BASELINE, result)
    return {"captured": True, "baseline": str(BASELINE.relative_to(ROOT)).replace("\\", "/"),
            "baseline_sha256": sha256(BASELINE.read_bytes()).hexdigest(),
            "files_checked": len(originals), "original_baseline_checks": prior_checks,
            "reviewed_provider_source": result["reviewed_provider_source"], **check()}


def check():
    baseline = _read(BASELINE)
    result = _verify(baseline["files"])
    source = baseline["reviewed_provider_source"]
    snapshot = PHASE / source["snapshot"]
    snapshot_sha = sha256(snapshot.read_bytes()).hexdigest() if snapshot.is_file() else None
    result["reviewed_source_snapshot_sha256"] = snapshot_sha
    result["reviewed_source_snapshot_preserved"] = snapshot_sha == source["sha256"]
    result["all_bytes_preserved"] = result["all_bytes_preserved"] and result["reviewed_source_snapshot_preserved"]
    return result


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in {"capture", "check"}:
        raise ValueError("retry_preservation_requires_capture_or_check")
    result = capture() if sys.argv[1] == "capture" else check()
    print(json.dumps(result, indent=2, allow_nan=False))
    return int(not result.get("all_bytes_preserved", result.get("captured", False)))


if __name__ == "__main__":
    sys.exit(main())
