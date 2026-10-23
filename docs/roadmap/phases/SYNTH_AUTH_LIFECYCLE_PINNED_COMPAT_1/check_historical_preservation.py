"""Pure stored-pin checks; writes only this phase's historical_preservation.json.

Run from the repository: python -B docs/roadmap/phases/
SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/check_historical_preservation.py

This script reads bytes and JSON with standard-library modules only. It never
imports owners, executes tests, issues capabilities, or derives replacement pins.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


PHASE_ID = "SYNTH.AUTH.LIFECYCLE.PINNED.COMPAT.1"
AUDIT_DIRECTORY = Path(__file__).resolve().parent
REPOSITORY_ROOT = AUDIT_DIRECTORY.parents[3]
OUTPUT_PATH = AUDIT_DIRECTORY / "historical_preservation.json"
PINNED_1 = "docs/roadmap/phases/SYNTH_AUTH_PINNED_1/"
PINNED_1R = "docs/roadmap/phases/SYNTH_AUTH_PINNED_1R/"


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash_string(value) -> bool:
    return (type(value) is str and len(value) == 64
        and all(character in "0123456789abcdef" for character in value))


def _bindings(files, *, prefix=""):
    """Normalize frozen arrays, structured maps, and path-to-hash maps."""
    if type(files) is list:
        records = files
    elif type(files) is dict:
        records = []
        for path, value in files.items():
            if type(value) is str:
                records.append({"path": path, "sha256": value})
            elif type(value) is dict:
                records.append({**value, "path": path})
            else:
                raise ValueError("Unsupported frozen manifest entry: " + path)
    else:
        raise ValueError("Unsupported frozen manifest shape")
    result = []
    seen = set()
    for record in records:
        if type(record) is not dict or type(record.get("path")) is not str:
            raise ValueError("Frozen binding requires a path")
        path = prefix + record["path"]
        if path in seen or not _hash_string(record.get("sha256")):
            raise ValueError("Duplicate path or invalid original hash: " + path)
        seen.add(path)
        size = record.get("size_bytes", record.get("size"))
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError("Invalid frozen size: " + path)
        result.append({"path": path, "sha256": record["sha256"], "size_bytes": size})
    return result


class HistoricalAudit:
    def __init__(self):
        self.current = {}
        self.checks = []

    def _path(self, relative):
        if type(relative) is not str or Path(relative).is_absolute():
            raise ValueError("Expected repository-relative historical path")
        candidate = (REPOSITORY_ROOT / relative).resolve()
        if not candidate.is_relative_to(REPOSITORY_ROOT):
            raise ValueError("Historical path escapes repository: " + relative)
        return candidate

    def _record_bytes(self, relative, content):
        observation = {"sha256": _sha256(content), "size_bytes": len(content)}
        previous = self.current.get(relative)
        if previous is not None and previous != observation:
            raise ValueError("Historical file changed during audit: " + relative)
        self.current[relative] = observation
        return observation

    def observation(self, relative):
        if relative in self.current:
            return self.current[relative]
        path = self._path(relative)
        if not path.is_file():
            return None
        return self._record_bytes(relative, path.read_bytes())

    def read_json(self, relative):
        content = self._path(relative).read_bytes()
        self._record_bytes(relative, content)
        return json.loads(content.decode("utf-8-sig"))

    def check_bindings(self, label, records, *, expected_count=None):
        drift = []
        for record in records:
            actual = self.observation(record["path"])
            expected_size = record.get("size_bytes")
            if actual is None:
                drift.append({"path": record["path"], "reason": "missing",
                    "expected_sha256": record["sha256"]})
            elif (actual["sha256"] != record["sha256"]
                    or (expected_size is not None and actual["size_bytes"] != expected_size)):
                drift.append({"path": record["path"], "reason": "hash_or_size_mismatch",
                    "expected_sha256": record["sha256"], "actual_sha256": actual["sha256"],
                    "expected_size_bytes": expected_size, "actual_size_bytes": actual["size_bytes"]})
        count_matches = expected_count is None or len(records) == expected_count
        self.checks.append({"label": label, "bindings_checked": len(records),
            "expected_binding_count": expected_count, "binding_count_matches": count_matches,
            "unchanged_count": len(records) - len(drift), "drift": drift,
            "passed": not drift and count_matches})

    def check_manifest(self, path, *, expected_count=None):
        manifest = self.read_json(path)
        records = _bindings(manifest["files"])
        declared_count = manifest.get("file_count", expected_count)
        if expected_count is not None and declared_count != expected_count:
            raise ValueError("Frozen manifest count conflicts with recorded history: " + path)
        self.check_bindings(path, records, expected_count=declared_count)
        return manifest

    def check_file_hash(self, label, path, expected):
        if not _hash_string(expected):
            raise ValueError("Original stored hash required: " + path)
        self.check_bindings(label, [{"path": path, "sha256": expected}], expected_count=1)

    def run(self):
        pinned1r_baseline = self.check_manifest(PINNED_1R + "preservation_baseline.json",
            expected_count=2246)
        self.check_manifest(PINNED_1 + "preservation_baseline.json", expected_count=355)
        self.check_manifest(PINNED_1 + "historical_preservation_baseline.json", expected_count=355)

        identity_path = PINNED_1R + "source_identity.json"
        self.check_file_hash("PINNED.1R original source identity checksum", identity_path,
            pinned1r_baseline["source_identity_sha256"])
        identity = self.read_json(identity_path)
        frozen = identity["frozen_identity_checks"]
        for prior in frozen["prior_historical_baseline_integrity"]:
            self.check_file_hash("Original prior baseline checksum: " + prior["baseline_path"],
                prior["baseline_path"], prior["baseline_sha256"])
            self.check_manifest(prior["baseline_path"], expected_count=prior["bindings_checked"])

        source_records = [{"path": record["path"], "sha256": record["expected_sha256"]}
            for record in frozen["source_bindings"]]
        self.check_bindings("PINNED.1R original expected source pins", _bindings(source_records),
            expected_count=359)
        live_sources = [record for record in frozen["source_bindings"] if record["live_graph_source"]]
        self.check_bindings("PINNED.1R frozen live graph source subset", _bindings([
            {"path": record["path"], "sha256": record["expected_sha256"]}
            for record in live_sources]), expected_count=frozen["live_graph_source_count"])

        gate_path = identity["frozen_gate_path"]
        self.check_file_hash("PINNED.1 original frozen gate checksum", gate_path,
            identity["frozen_gate_sha256"])
        gate = self.read_json(gate_path)
        self.check_bindings("PINNED.1 original gate source pins", _bindings(gate["source_bindings"]),
            expected_count=359)

        supplemental = self.read_json(PINNED_1 + "supplemental_historical_pins.json")
        self.check_file_hash("Supplemental original gate checksum", supplemental["source"],
            supplemental["source_sha256"])
        prior_gate = self.read_json(supplemental["source"])
        added_paths = set(supplemental["added_paths"])
        supplemental_records = [record for record in prior_gate["source_bindings"]
            if record["path"] in added_paths]
        if len(added_paths) != 13 or set(record["path"] for record in supplemental_records) != added_paths:
            raise ValueError("Supplemental original source pin selection changed")
        self.check_bindings("Supplemental original gate source pins", _bindings(supplemental_records),
            expected_count=13)
        provenance = supplemental["additional_preservation_binding"]
        for source in (provenance["source"], provenance["original_pin_source"]):
            manifest = self.read_json(source)
            records = [record for record in _bindings(manifest["files"])
                if record["path"] == provenance["path"]]
            self.check_bindings("Additional provenance original pin: " + source, records,
                expected_count=1)

        artifact = self.read_json(PINNED_1R + "artifact_manifest.json")
        self.check_bindings("PINNED.1R original artifact manifest", _bindings(artifact["files"],
            prefix=PINNED_1R), expected_count=10)
        runner = identity["historical_original_runner"]
        self.check_file_hash("Historical original replay runner checksum", runner["path"], runner["sha256"])
        blocked = identity["original_blocked_attempt"]
        if blocked["sha256"] != pinned1r_baseline["original_blocked_attempt_sha256"]:
            raise ValueError("Historical blocked-attempt checksum sources disagree")
        self.check_file_hash("Historical original blocked authorization report checksum", blocked["path"],
            blocked["sha256"])

    def report(self, error=None):
        passed = error is None and all(check["passed"] for check in self.checks)
        return {"phase_id": PHASE_ID, "schema_version": "historical_preservation_audit_v1",
            "result": "HISTORICAL_PRESERVATION_VERIFIED" if passed else "HISTORICAL_PRESERVATION_FAILED",
            "historical_preservation_verified": passed, "historical_drift_repinned": False,
            "expected_hash_origin": "Unchanged stored historical manifests and source-identity records only",
            "check_count": len(self.checks), "checks": self.checks,
            "unique_current_files_hashed": len(self.current),
            "drift_count": sum(len(check["drift"]) for check in self.checks),
            "binding_count_failures": sum(not check["binding_count_matches"] for check in self.checks),
            "error": error, "operational_effect_counts": {
                "owner_imports": 0, "tests_run": 0, "provider_issuance": 0,
                "authorization_issuance": 0, "execution_lease_issuance": 0,
                "execution_lease_consumption": 0, "Docker": 0, "JAVA1C": 0,
                "SANDBOX2_issuance": 0, "PINNED1A_export": 0, "SyntheticStateBox": 0,
                "reflection": 0, "BANK": 0, "EXECUTOR_1R": 0, "Apply": 0,
                "repository_runtime_writes": 0},
            "audit_artifact_output": "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/historical_preservation.json",
            "reproduce": "python -B docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_COMPAT_1/check_historical_preservation.py",
            "scope_limit": "Historical stored-pin integrity only; the phase's separate 2263-file baseline is checked independently."}


def main():
    audit = HistoricalAudit()
    error = None
    try:
        audit.run()
    except (OSError, ValueError, KeyError, TypeError) as exception:
        error = type(exception).__name__ + ": " + str(exception)
    report = audit.report(error)
    OUTPUT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("result", "check_count", "unique_current_files_hashed",
        "drift_count", "binding_count_failures", "error")}, sort_keys=True))
    return 0 if report["historical_preservation_verified"] else 1


if __name__ == "__main__":
    sys.exit(main())
