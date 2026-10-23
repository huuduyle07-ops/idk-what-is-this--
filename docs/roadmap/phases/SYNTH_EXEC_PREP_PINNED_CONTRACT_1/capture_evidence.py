"""Capture raw source hashes and exact anchors without importing any owner."""
from hashlib import sha256
import json
from pathlib import Path

PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
ANCHORS = {
    "core/synthetic_runtime_authorization.py": ["_SOURCE =", "private int value = 10;", "def _validate_source", "def get_executor1r_decrement_3_source"],
    "core/synthetic_runtime_authorization_pinned.py": ["def _authenticate_provider", "def validate_pinned_synthetic_runtime_authorization"],
    "core/synthetic_runtime_authorization_lifecycle.py": ["CONSUMPTION_POLICY =", "COMPILATION_POLICY ="],
    "core/synthetic_runtime_authorization_pinned_lifecycle.py": ["_LOCK = Lock()", "def _consumer_readiness", "def _transition", "_STORE = updated  # The only terminal"],
    "core/synthetic_read_only_reflection.py": ["_BEFORE_HELPER =", "_AFTER_HELPER =", "def render_synthetic_read_only_reflection"],
    "core/synthetic_reflection_execution_admission_pinned.py": ["def issue_pinned_synthetic_reflection_execution_admission"],
    "core/synthetic_reflection_execution_lifecycle_pinned.py": ["EXECUTOR_SEQUENCE =", "BEFORE_HELPER_SHA256 =", "AFTER_HELPER_SHA256 =", "def _authenticate_graph", "def issue_pinned_synthetic_reflection_execution_lease", "def _transition"],
    "core/runtime_java_pinned_requirement.py": ["IMAGE =", "POLICY_SHA256 =", "e21c219e", "class PinnedJavaRequirement", "source_class_output"],
    "core/runtime_java_pinned_provider.py": ["def validate_pinned_java_exact_provider"],
    "core/sandboxed_java_toolchain_probe.py": ["COMPILE_ARGUMENTS ="],
    "core/sandboxed_java_positive_probe.py": ["followlinks=False", "32768", "def "],
    "core/sandboxed_java_positive_continuation.py": ["def safe_configuration", "def evaluate", "32768", "def verify"],
    "core/thread_compatible_runtime_sandbox.py": ["def safe_configuration", "size=32m", "size=16m"],
    "core/candidate_runtime_sandbox.py": ["_WORKLOAD_ENVIRONMENT =", "ephemeral_tmpfs_exact_inputs_only"],
    "core/structural_compile_validation.py": ["diagnostic authority only"],
    "core/behavioral_diagnostic_executor_refresh.py": ["existing_synthetic_issuer_cannot_reconstruct_independent_scenario", "harness_sha256"],
    "core/behavioral_diagnostic_executor_retry.py": ["frozen_synth_auth_1_has_no_public_consumption_contract", "harness_sha256"],
    "core/behavioral_diagnostic_executor_lifecycle_retry.py": ["java_profile_contract_mismatch", "No effectful runner", "harness_sha256"],
    "docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json": [],
    "docs/roadmap/phases/RUNTIME_JAVA_1C/RUNTIME_JAVA_1C.md": ["Exact compile argv", "JAVA_SANDBOX_OK"],
    "docs/roadmap/phases/SYNTH_AUTH_LIFECYCLE_PINNED_CONTRACT_1/contract.json": ["source_harness_readiness_before_consumption", "immediately before the first behavioral runtime effect"],
    "docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json": ["first_behavior_boundary", '"first_behavioral_effect": "BEFORE exact read"'],
    "docs/roadmap/phases/SYNTH_REFLECT_LIFECYCLE_PINNED_1A/SYNTH_REFLECT_LIFECYCLE_PINNED_1A_REPORT.md": ["SYNTH_REFLECT_LIFECYCLE_PINNED_1A_COMPLETE", "Normative ordering remains"],
}


def main():
    files = {}
    for relative, needles in ANCHORS.items():
        data = (ROOT / relative).read_bytes()
        lines = data.decode("utf-8").splitlines()
        anchors = []
        for needle in needles:
            matches = [(i, line) for i, line in enumerate(lines, 1) if needle in line]
            if not matches:
                raise AssertionError("Missing source evidence: " + relative + ":" + needle)
            anchors.append({"line": matches[0][0], "text": needle})
        files[relative] = {"sha256": sha256(data).hexdigest(), "bytes": len(data), "anchors": anchors}
    result = {"phase_id": "SYNTH.EXEC.PREP.PINNED.CONTRACT.1", "owner_modules_imported": False,
        "source_materialized": False, "method": "raw byte SHA256 and source-text anchors only", "files": files}
    (PHASE / "evidence_index.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"files": len(files), "owner_modules_imported": False, "source_materialized": False}))


if __name__ == "__main__":
    main()
