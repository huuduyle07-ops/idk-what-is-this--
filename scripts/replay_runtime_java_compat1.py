"""Export the pure blocked Java contract audit; never retry EXECUTOR.1R."""
import argparse
from contextlib import ExitStack
from hashlib import sha256
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.source_layout import read_preorganization_source

FROZEN_SHA256 = {
    "core/sandboxed_java_toolchain.py": "ed96e56a875535d4cafaa107721ee6eafd5c0c1b0f8d14f59f4ad728f00288c9",
    "core/sandboxed_java_toolchain_discovery.py": "df3c047cdc64dec92827bf32cd78ba85a61837d436fe3d90c04905662019dbff",
    "core/sandboxed_java_toolchain_probe.py": "58e791ed6ac7c99a41386345ce8d392ca74cb8f574a8207fe1c85afa335ec606",
    "core/sandboxed_java_positive_continuation.py": "ec0f7a7a210fabca4d3df58323072829392bc3fcdb5b41213f5d56750af09f7f",
    "core/sandboxed_java_positive_probe.py": "d62e7ab3082f728d77bdfcfde91b5f62f11a6b8a2945b8a8c96fb5c97e3c654f",
    "core/java_single_thread_capture.py": "4ac691b2919b3e778a98c044fb166fd9804b102cdd651995eb8689839ac438fb",
    "core/candidate_runtime_sandbox.py": "ebe409e7e798ec1e8f48c4bd2c49e5cd8b282906251f7c2c38c2933d1ef51913",
    "core/candidate_runtime_sandbox_probe.py": "aa090e85f34a75c429fc98a20b562e6ebc2b7261d400b08fd7758da4994f4b6c",
    "core/thread_compatible_runtime_sandbox.py": "8eea18d16c330dc7d116065ac9d23833bb2a0af58448b02438c26526141b1d45",
    "core/thread_compatible_runtime_sandbox_probe.py": "be45d3a0106186d84a0464234f701140df6e90e99107477af358886cf5568075",
    "core/synthetic_runtime_authorization.py": "219c868080a6cca3f02dfcfbd4729f012439b8af1e8db5762c09760a41100b88",
    "core/sandboxed_java_capture_recovery.py": "4eb248c80c357966018604f208f766120a845935574aba52d9be52e55b6ae861",
    "core/sandboxed_java_single_thread_probe.py": "7bb2bceac444c80f6b2c75b335731d61b73dfff58b1b0ca72ac85f027e635716",
    "docs/roadmap/RUNTIME_JAVA_1_LOCAL.json": "bf73f4b738e3fd094b0034db2bd3cc00342f3c451a4d77760fa00947c48b7ede",
    "docs/roadmap/RUNTIME_JAVA_1C_LOCAL.json": "7deec9280b20410ea399a4c233f0ccd2fa1dd6517e402f87bfc47af7e036e822",
    "docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json": "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75",
}


def replay():
    from tests._preflight_runtime1_guard import no_runtime_effects
    with no_runtime_effects(strict=True) as effects:
        with ExitStack() as guards:
            for target in ("threading.Thread.start",
                    "core.sandboxed_java_toolchain.verify_sandboxed_java_toolchain",
                    "core.sandboxed_java_positive_continuation.verify",
                    "core.thread_compatible_runtime_sandbox.replay",
                    "core.behavioral_diagnostic_executor_lifecycle_retry.verify",
                    "core.runtime.synthetic.synthetic_runtime_authorization_lifecycle.consume_synthetic_runtime_execution_lease",
                    "core.runtime.synthetic.synthetic_reflection_execution_lifecycle.consume_synthetic_reflection_execution_lease"):
                guards.enter_context(patch(target, side_effect=effects.deny(target)))
            from core import java_runtime_compatibility as owner
            # Read-only source/evidence audit, not capability reconstruction.
            observed = {name: sha256(read_preorganization_source(name)).hexdigest()
                for name in FROZEN_SHA256}
            if observed != FROZEN_SHA256:
                raise ValueError("frozen_java_compatibility_audit_inputs_changed")
            report = owner.audit_java_runtime_compatibility().as_dict()
        if effects.denied_attempts:
            raise AssertionError("Java contract audit attempted a forbidden effect")
        report.update(frozen_input_sha256=observed, effect_denial={"strict": True,
            "denied_attempts": dict(effects.denied_attempts), "controller_thread_start_attempts": 0},
            proof_scope="guarded contract audit only; development validation is separately recorded",
            future_live_authentication_requirement="Freshly authenticate both live SANDBOX.2 and JAVA.1C through their owners before any future relation; historical JSON is never live evidence.",
            semantic_gap_policy="Stop without bridge; do not repair JAVA.1C or modify SYNTH.AUTH.1.",
            source_projection=False,
            **dict.fromkeys(("docker_calls", "containers_created", "java_executions", "javac_executions",
                "child_processes", "network_calls", "runtime_lease_consumptions", "reflection_lease_consumptions",
                "repository_runtime_writes", "apply_actions", "bank_executions", "executor1r_retries"), 0))
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = replay()
    # Development artifact export is outside the effect-free contract proof.
    if args.output:
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("phase_id", "status", "reason",
        "contract_compatible", "live_provider_authenticated", "unproven_dimensions", "effect_denial")}, indent=2))
