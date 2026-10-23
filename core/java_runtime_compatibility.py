"""RUNTIME.JAVA.COMPAT.1 frozen contract audit; no execution or authority.

The original Java success contract includes complete local discovery and an
explicit discovery/backend binding. JAVA.1C proves neither claim. V1 therefore
exposes a typed blocked audit, never a compatibility relation or live provider.
This module deliberately imports no runtime owner and performs no I/O.
"""
from dataclasses import asdict, dataclass, field, fields, is_dataclass

PHASE_ID = "RUNTIME.JAVA.COMPAT.1"
SCHEMA_VERSION = "runtime_java_compat_1_v1"
SEMANTIC_GAP = "RUNTIME_JAVA_COMPAT_1_BLOCKED_SEMANTIC_GAP"
PROVIDER_AMBIGUITY = "RUNTIME_JAVA_COMPAT_1_BLOCKED_PROVIDER_AMBIGUITY"
SANDBOX_BINDING = "RUNTIME_JAVA_COMPAT_1_BLOCKED_SANDBOX_BINDING"
UNPROVEN_REQUIREMENT = "RUNTIME_JAVA_COMPAT_1_BLOCKED_UNPROVEN_REQUIREMENT"
POLICY_SHA256 = "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"
IMAGE = "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"


@dataclass(frozen=True, slots=True)
class JavaRuntimeRequirement:
    java_profile_id: str
    java_schema_version: str
    sandbox_profile_id: str
    sandbox_policy_sha256: str


@dataclass(frozen=True, slots=True)
class SemanticComparison:
    dimension: str
    required: str
    provider: str
    comparison: str
    evidence: tuple[str, ...]


def _row(name, required, provider, comparison, *evidence):
    return SemanticComparison(name, required, provider, comparison, evidence)


# These are reviewed public contract representations, not runtime descriptors.
# Source hashes and executable assertions are recorded by the guarded replay.
COMPARISON = (
    _row("toolchain_image_identity", IMAGE, IMAGE, "equal",
        "JAVA.1 frozen explicit_artifact_selection.image_identity", "JAVA.1C JavaContinuationReceipt.image_identity"),
    _row("platform", "linux/amd64", "linux/amd64", "equal",
        "JAVA.1 verify_sandboxed_java_toolchain", "JAVA.1C verify exact image inspection"),
    _row("java_executable_path", "/opt/temurin-26.0.2.1/bin/java", "/opt/temurin-26.0.2.1/bin/java", "equal",
        "JAVA.1 frozen java_executable_identity", "JAVA.1C JavaContinuationReceipt.java_path"),
    _row("java_executable_digest", "a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2",
        "a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2", "equal",
        "JAVA.1 frozen java_executable_identity", "JAVA.1C JavaContinuationReceipt.java_sha256"),
    _row("javac_executable_path", "/opt/temurin-26.0.2.1/bin/javac", "/opt/temurin-26.0.2.1/bin/javac", "equal",
        "JAVA.1 frozen javac_executable_identity", "JAVA.1C JavaContinuationReceipt.javac_path"),
    _row("javac_executable_digest", "e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023",
        "e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023", "equal",
        "JAVA.1 frozen javac_executable_identity", "JAVA.1C JavaContinuationReceipt.javac_sha256"),
    _row("java_version_expectations", "Nonempty successful exact binary -version; no generic version range",
        "Same binaries; versions bound through freshly authenticated SANDBOX.2 ladder", "intentionally_different",
        "JAVA.1 _java_failure identity stages and version()", "JAVA.1C verify toolchain_versions"),
    _row("compiler_invocation_restrictions", "Frozen javac argv; phase source only; no caller flags",
        "Imports identical COMPILE_ARGUMENTS; no caller inputs", "equal",
        "sandboxed_java_toolchain_probe.COMPILE_ARGUMENTS", "sandboxed_java_positive_probe.COMPILE_ARGV"),
    _row("runtime_invocation_restrictions", "Frozen JVM argv; /work/classes; JavaSandboxProbe only",
        "Imports identical RUNTIME_ARGUMENTS; no caller inputs", "equal",
        "sandboxed_java_toolchain_probe.RUNTIME_ARGUMENTS", "sandboxed_java_positive_probe.RUNTIME_ARGV"),
    _row("bounded_capture", "Independent bounded pipes with two reader threads",
        "Independent bounded nonblocking pipes with one selector thread, EOF and cleanup checks", "stronger_provider",
        "JAVA.1 JAVA_PROBE_SOURCE.run", "java_single_thread_capture.capture_process", "JAVA.1C evaluate"),
    _row("timeout", "10000 ms outer bound; 5000 ms abort cutoff",
        "Same outer bounds plus shared 5000 ms controller deadline", "stronger_provider",
        "JAVA.1 _invoke_java", "JAVA.1C _invoke", "sandboxed_java_positive_probe.BODY"),
    _row("stdout_cap", "8192 outer; 2048 compiler; 1024 runtime/version",
        "8192 outer; 2048 compiler; 1024 runtime/version", "equal", "JAVA.1 _java_failure", "JAVA.1C INVOCATIONS; SANDBOX.2 version gates"),
    _row("stderr_cap", "8192 outer; 2048 compiler; 1024 runtime/version",
        "8192 outer; 2048 compiler; 1024 runtime/version; bounded separate progress", "equal", "JAVA.1 _java_failure", "JAVA.1C evaluate and _progress"),
    _row("cleanup", "Child wait, pipe close and verified container removal; ephemeral outputs",
        "Also process-group kill/reap, selector cleanup, both EOFs, only PID 1 remains", "stronger_provider",
        "JAVA.1 _invoke_java and JAVA_PROBE_SOURCE.run", "JAVA.1C evaluate and verify"),
    _row("network_prohibition", "network none; socket/connect syscall denials", "Identical restriction and original hostile probes", "equal",
        "SANDBOX.1 _safe_configuration_facts and _facts_passed", "SANDBOX.2 safe_configuration and classify"),
    _row("host_mount_prohibition", "No Binds, Mounts or image volumes", "Same independently inspected prohibition", "equal",
        "SANDBOX.1 _safe_configuration_facts", "JAVA.1C safe_configuration and verify"),
    _row("root_filesystem", "Read-only root", "Same; also measured before/after", "stronger_provider",
        "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("uid_gid", "65534:65534", "65534:65534", "equal", "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("capability_drop", "ALL; no CapAdd; effective capabilities zero", "Same", "equal", "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("no_new_privileges", "true", "true", "equal", "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("pid_namespace_budget", "Private PID namespace/cgroup; 128 PIDs; descendants contained",
        "Same; observes all seven namespaces and child cgroups", "stronger_provider", "JAVA.1 JAVA_PROBE_SOURCE.boundary", "JAVA.1C _state_safe and evaluate"),
    _row("memory_limit", "134217728 bytes", "134217728 bytes", "equal", "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("cpu_limit", "1000000000 NanoCpus (one CPU)", "Same; measured quota equals period", "stronger_provider",
        "SANDBOX.1 _safe_configuration_facts", "JAVA.1C _state_safe"),
    _row("environment_closure", "Exact frozen eight-variable environment", "Exact same environment", "equal",
        "SANDBOX.1 _WORKLOAD_ENVIRONMENT", "JAVA.1C _state_safe and safe_configuration"),
    _row("temporary_filesystems", "/work rw,nosuid,nodev,32m,1777; /tmp rw,nosuid,nodev,noexec,16m,1777",
        "Same; removal of container destroys both", "equal", "SANDBOX.1 _safe_configuration_facts", "JAVA.1C safe_configuration and verify"),
    _row("seccomp_policy", "SYNTH.AUTH.1 explicitly requires exact SANDBOX.2 hash " + POLICY_SHA256,
        "Exact required hash; clone3 errno EPERM -> ENOSYS; execution remains denied", "intentionally_different",
        "SYNTH.AUTH.1 SANDBOX_POLICY_SHA256", "SANDBOX.2 policy_diff/validate_policy_bytes", "JAVA.1C authenticate_sandbox2"),
    _row("controller_threads", "Historical controller attempts reader threads; no single-thread guarantee",
        "Python/OS thread count one before/after; Thread.start forbidden", "stronger_provider",
        "JAVA.1 JAVA_PROBE_SOURCE.run", "JAVA.1C _state_safe; positive_probe.BODY"),
    _row("source_projection", "Only fixed 129 bytes, SHA256 3975c5e03edb79439d6146b7714a6d3c31af86ce42f05624cdf6c28f69b4e224",
        "Imports exact source; also checks full byte readback and empty initial workdir", "stronger_provider",
        "JAVA.1 ExactJavaSandboxInput", "JAVA.1C evaluate; positive_probe.execute"),
    _row("class_projection", "One JavaSandboxProbe.class, valid digest, 1..32768 bytes; tmpfs only",
        "Same; exact entire work manifest; runtime cannot change workspace", "stronger_provider",
        "JAVA.1 _java_failure", "JAVA.1C evaluate"),
    _row("arbitrary_command_prohibition", "No caller command/source/main/classpath", "Same; no-argument verifier", "equal",
        "JAVA.1 JavaToolchainExecutionSpec", "JAVA.1C verify; positive_probe.source"),
    _row("shell_prohibition", "shell=False", "shell=False; shell_available=False", "equal",
        "JAVA.1 JAVA_PROBE_SOURCE.run", "java_single_thread_capture.capture_process; JAVA.1C receipt"),
    _row("runtime_receipt_semantics", "Signed original receipt includes discovery_complete and inventory, results and boundary outcomes",
        "Separate signed receipt binds exact image/source/argv/class/output and evidence digest; lacks discovery witnesses", "unproven",
        "JAVA.1 SandboxedJavaToolchainVerificationReceipt", "JAVA.1C JavaContinuationReceipt"),
    _row("descriptor_authentication", "Original process-local HMAC; authentic receipt and exact descriptor payload",
        "Separate process-local HMAC; authentic descriptor/receipt binding; JSON rejected", "equal",
        "JAVA.1 validate_java_descriptor", "JAVA.1C validate_descriptor; java_toolchain_satisfies_executor_runtime"),
    _row("sandbox_owner_relationship", "Original JAVA.1 public predicate only accepts original SANDBOX.1",
        "JAVA.1C explicitly authenticates fresh SANDBOX.2 pair and exact required policy", "intentionally_different",
        "JAVA.1 java_toolchain_satisfies_executor_runtime", "JAVA.1C authenticate_sandbox2"),
    _row("complete_local_artifact_discovery", "Complete inventory required before Java success; authenticated discovery_complete field",
        "Only exact pinned image inspect and executable hashes; no complete inventory claim", "unproven",
        "JAVA.1 verify_sandboxed_java_toolchain: java_artifact_discovery_incomplete", "JAVA.1C verify; JavaContinuationReceipt"),
    _row("discovery_backend_binding", "Inventory backend identity AND version must equal authenticated sandbox backend",
        "SANDBOX.2 descriptor/receipt and JAVA.1C receipt expose no corresponding discovery/backend identity/version witness", "unproven",
        "JAVA.1 verify_sandboxed_java_toolchain: backend_binding_changed", "SANDBOX.2 ThreadCompatibleSandboxReceipt; JAVA.1C JavaContinuationReceipt"),
)


@dataclass(frozen=True, slots=True)
class FrozenProviderContract:
    """Public audit metadata only, never an authenticated provider handle."""
    phase_id: str
    schema_version: str
    sandbox_phase_id: str
    sandbox_schema_version: str
    sandbox_policy_sha256: str
    semantic_dimensions: tuple[tuple[str, str], ...]


REQUIREMENT = JavaRuntimeRequirement("RUNTIME.JAVA.1", "runtime_java_1_v1",
    "runtime_sandbox_2_v1", POLICY_SHA256)
PROVIDER = FrozenProviderContract("RUNTIME.JAVA.1C", "runtime_java_1c_v1",
    "RUNTIME.SANDBOX.2", "runtime_sandbox_2_v1", POLICY_SHA256,
    tuple((row.dimension, row.provider) for row in COMPARISON))


@dataclass(frozen=True, slots=True)
class JavaRuntimeCompatibilityAudit:
    status: str
    reason: str
    requirement: JavaRuntimeRequirement = REQUIREMENT
    provider: FrozenProviderContract = PROVIDER
    comparison: tuple[SemanticComparison, ...] = COMPARISON
    phase_id: str = PHASE_ID
    schema_version: str = SCHEMA_VERSION
    contract_compatible: bool = field(default=False, init=False)
    live_provider_authenticated: bool = field(default=False, init=False)
    compatibility_authority: bool = field(default=False, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    compatibility_relation: None = field(default=None, init=False)
    relation_count: int = field(default=0, init=False)
    identity_equality_asserted: bool = field(default=False, init=False)
    profile_schema_relabeling: bool = field(default=False, init=False)
    historical_receipts_rewritten: bool = field(default=False, init=False)

    def as_dict(self):
        return {**asdict(self), "report_only": True,
            "unproven_dimensions": [row.dimension for row in self.comparison
                if row.comparison == "unproven"]}


def _exact(value, template):
    if type(value) is not type(template):
        return False
    if is_dataclass(template):
        return all(_exact(getattr(value, f.name), getattr(template, f.name))
            for f in fields(template))
    if type(template) is tuple:
        return len(value) == len(template) and all(_exact(v, t) for v, t in zip(value, template))
    return value == template


def audit_java_runtime_compatibility(requirement=REQUIREMENT, provider=PROVIDER):
    """Assess only the fixed frozen metadata; no bridge exists in this V1.

    Caller edits cannot fill gaps in an owner's frozen contract. Even exact
    metadata is report-only and says nothing about a future live provider.
    """
    if not _exact(requirement, REQUIREMENT):
        return JavaRuntimeCompatibilityAudit(UNPROVEN_REQUIREMENT, "exact_frozen_requirement_required")
    if type(provider) is not FrozenProviderContract:
        return JavaRuntimeCompatibilityAudit(PROVIDER_AMBIGUITY, "frozen_contract_metadata_required_not_live_or_report_json")
    if not all(_exact(getattr(provider, key), getattr(PROVIDER, key))
            for key in ("phase_id", "schema_version")):
        return JavaRuntimeCompatibilityAudit(PROVIDER_AMBIGUITY, "exact_java_provider_identity_required")
    if not all(_exact(getattr(provider, key), getattr(PROVIDER, key))
            for key in ("sandbox_phase_id", "sandbox_schema_version", "sandbox_policy_sha256")):
        return JavaRuntimeCompatibilityAudit(SANDBOX_BINDING, "exact_sandbox2_binding_required")
    if not _exact(provider.semantic_dimensions, PROVIDER.semantic_dimensions):
        return JavaRuntimeCompatibilityAudit(SEMANTIC_GAP, "caller_metadata_cannot_change_frozen_semantics")
    return JavaRuntimeCompatibilityAudit(SEMANTIC_GAP,
        "unproven_complete_local_artifact_discovery_and_discovery_backend_binding")
