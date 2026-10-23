"""Record two ISSUED reflection leases in one ISSUED activation; execute nothing."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def replay():
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        with patch("threading.Thread.start", side_effect=effects.deny("threading.Thread.start")):
            from core.runtime.synthetic import synthetic_reflection_execution_lifecycle as owner
            handles, report = owner.verify()
            assert handles["runtime"].lifecycle_state == owner.ISSUED
            for label, role in (("before", owner.BEFORE_ROLE), ("after", owner.AFTER_ROLE)):
                lease = handles[label + "_lease"]
                assert owner.validate_synthetic_reflection_execution_lease(lease) is lease
                assert owner.synthetic_reflection_execution_lease_satisfies_executor(lease,
                    handles[label + "_admission"], handles[label + "_request"],
                    handles["runtime"], handles["authorization"], observation_role=role)
                assert lease.lifecycle_state == owner.ISSUED
                assert lease.as_dict() == report[label + "_reflection_lease"]
        if effects.denied_attempts:
            raise AssertionError("reflection lifecycle proof attempted a forbidden effect")
        report["effect_denial"] = {"strict": True, "denied_attempts": dict(effects.denied_attempts),
            "thread_start_attempts": 0}
    # Export occurs outside the no-write proof. JSON is historical evidence;
    # process-local identities and HMAC domains cannot be restored from it.
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({key: report[key] for key in ("phase_id", "status", "supported_lifecycle_scope_count",
        "preexecution_executor_compatibility", "final_strict_runtime_lease_state",
        "final_strict_before_lease_state", "final_strict_after_lease_state",
        "strict_runtime_lease_consumptions", "strict_reflection_lease_consumptions", "effect_denial")}, indent=2))
