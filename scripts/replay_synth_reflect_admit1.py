"""Prove SYNTH.REFLECT.ADMIT.1 under strict effect denial; execute nothing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def replay():
    # Install the shared process/network/compiler/reflection/write guard before
    # importing this phase owner. Report export occurs only after proof.
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        from core.runtime.synthetic.synthetic_reflection_execution_admission import verify
        admissions, report = verify()
        if len(admissions) != 2 or effects.denied_attempts:
            raise AssertionError("SYNTH.REFLECT.ADMIT.1 attempted a forbidden effect or lost an admission")
        if any(admission.consumption_state != "issued" for admission in admissions):
            raise AssertionError("admission proof consumed a handle")
        if (report["synthetic_runtime_authorizations_consumed"] != 0
                or report["reflection_admissions_consumed"] != 0):
            raise AssertionError("admission proof consumed upstream or local authority")
        report["effect_denial"] = {
            "strict": True,
            "denied_attempts": dict(effects.denied_attempts),
            "java_compile_count": report["java_compile_count"],
            "jvm_execution_count": report["jvm_execution_count"],
            "reflection_execution_count": report["reflection_execution_count"],
            "containers_created": report["containers_created"],
            "docker_calls": report["docker_calls"],
            "network_calls": report["network_calls"],
            "shell_calls": report["shell_calls"],
            "child_processes": report["child_processes"],
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    report = replay()
    if args.output:
        args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "phase_id", "status", "supported_synthetic_reflection_admission_count",
        "scenario_id", "source_sha256", "definition_sha256", "owner", "member",
        "declared_type", "allowed_operation", "supported_roles",
        "before_admission_identity", "after_admission_identity",
        "fresh_synth_auth_1_compatibility", "fresh_synth_reflect_1_compatibility",
        "synthetic_reflection_execution_authority", "runtime_authority",
        "field_write_authority", "enumeration_authority", "private_method_authority",
        "constructor_reflection_authority", "arbitrary_class_loading_authority",
        "consumption_policy", "synthetic_runtime_authorizations_consumed",
        "reflection_admissions_consumed", "effect_denial")}, indent=2, sort_keys=True))
