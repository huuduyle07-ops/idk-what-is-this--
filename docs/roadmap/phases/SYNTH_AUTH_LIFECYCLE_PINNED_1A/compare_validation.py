"""Compare phase registry/picker validation with its immutable baseline."""
from __future__ import annotations
import json
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent


def main():
    before = json.loads((OUTPUT / "registry_baseline.json").read_text(encoding="utf-8"))
    after = json.loads((OUTPUT / "registry_after.json").read_text(encoding="utf-8"))
    keys = ("registry_summary", "picker", "collected", "passed_count", "failed", "skipped", "selected_nodes", "passed_nodes", "exit_code")
    comparison = {key: before[key] == after[key] for key in keys}
    result = {"comparison": comparison, "baseline_failed": before["failed"],
        "after_failed": after["failed"], "baseline_passed_count": before["passed_count"],
        "after_passed_count": after["passed_count"],
        "unchanged_pre_existing_failures": before["failed"] == after["failed"],
        "all_compared_fields_unchanged": all(comparison.values()),
        "guard_baseline_zero": before["all_operational_effects_zero"],
        "guard_after_zero": after["all_operational_effects_zero"],
        "phase_registration_performed": False}
    (OUTPUT / "registry_comparison.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if all(comparison.values()) and result["guard_baseline_zero"] and result["guard_after_zero"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
