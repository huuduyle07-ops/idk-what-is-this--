"""Record SYNTH.AUTH.1 contract issuance without executing Java or reflection."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def replay():
    # Install process/network/provider/compiler/reflection/write denials before
    # importing the new owner. Report export occurs after the pure proof ends.
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        from core.runtime.synthetic.synthetic_runtime_authorization import verify
        authorization, report = verify()
        if effects.denied_attempts:
            raise AssertionError("SYNTH.AUTH.1 attempted a forbidden effect")
        report["effect_denial"] = {"strict": True, "denied_attempts": dict(effects.denied_attempts)}
        # Keep the authenticated handle alive until the proof's export is made.
        assert authorization.as_dict() == report["synthetic_authorization"]
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"phase_id": report["phase_id"], "status": report["status"],
        "scenario_id": report["spec"]["scenario_id"],
        "authenticated_in_issuing_process": report["authenticated_in_issuing_process"],
        "synthetic_authorizations_issued": report["synthetic_authorizations_issued"],
        "jvm_execution_count": report["jvm_execution_count"],
        "reflection_execution_count": report["reflection_execution_count"],
        "real_runtime_authority_available": report["real_runtime_authority_available"]},
        indent=2, sort_keys=True))
