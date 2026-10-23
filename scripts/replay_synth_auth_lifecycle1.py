"""Record one ISSUED lifecycle proof under strict denial; never run an executor."""
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
            from core.runtime.synthetic import synthetic_runtime_authorization_lifecycle as owner
            handles, report = owner.verify()
            authorization, lease = handles
            assert owner.validate_synthetic_runtime_execution_lease(lease, authorization) is lease
            assert owner.synthetic_runtime_execution_lease_satisfies_executor(lease, authorization)
            assert owner.lease_is_issued(lease, authorization)
            assert lease.as_dict() == report["execution_lease"]
        if effects.denied_attempts:
            raise AssertionError("lifecycle proof attempted a forbidden effect")
        report["effect_denial"] = {"strict": True,
            "denied_attempts": dict(effects.denied_attempts), "thread_start_attempts": 0}
    # Export is deliberately outside the proof's no-write boundary. The live
    # pair was never consumed; this dictionary is historical evidence only.
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf8")
    print(json.dumps({key: report[key] for key in (
        "phase_id", "status", "supported_lifecycle_scope_count", "executor_compatibility",
        "final_strict_proof_lease_state", "synthetic_runtime_authorizations_consumed",
        "java_compile_count", "jvm_execution_count", "effect_denial")}, indent=2, sort_keys=True))
