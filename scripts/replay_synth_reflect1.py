"""Prove SYNTH.REFLECT.1 under effect denial; never execute Java or an executor."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def replay():
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        from core.runtime.synthetic.synthetic_read_only_reflection import verify
        requests, report = verify()
        if effects.denied_attempts:
            raise AssertionError("SYNTH.REFLECT.1 attempted a forbidden effect")
        assert [request.as_dict() for request in requests] == report["requests"]
        report["effect_denial"] = {"strict": True, "denied_attempts": dict(effects.denied_attempts)}
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    # Export is an additive report write after the strict, effect-free proof.
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "phase_id", "status", "scenario_id", "supported_synthetic_reflection_target_count",
        "reflection_request_valid", "reflection_execution_authority", "runtime_authority",
        "compile_count", "jvm_execution_count", "reflection_execution_count", "containers_created",
        "authorization_consumed", "effect_denial")}, indent=2, sort_keys=True))
