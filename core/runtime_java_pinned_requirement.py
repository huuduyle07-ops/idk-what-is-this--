"""RUNTIME.JAVA.REQUIREMENT.PINNED.1: immutable requirement metadata only.

This owner imports no runtime owner, performs no I/O and authenticates nothing.
Its schema identifies a new requirement, never a provider receipt or authority.
All evidence below is an obligation for a future additive provider proof owner.
"""
from dataclasses import asdict, dataclass, field

PHASE_ID = "RUNTIME.JAVA.REQUIREMENT.PINNED.1"
PROFILE_ID = "RUNTIME.JAVA.PINNED.1"
SCHEMA_VERSION = "runtime_java_pinned_1_v1"
COMPLETE = "RUNTIME_JAVA_REQUIREMENT_PINNED_1_COMPLETE"
IMAGE = "sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a"
POLICY_SHA256 = "5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75"


@dataclass(frozen=True, slots=True)
class ExecutableIdentity:
    path: str
    sha256: str


@dataclass(frozen=True, slots=True)
class ControllerRequirement:
    path: str = "/usr/local/bin/python"
    identity_kind: str = "exact_path_and_owner_authenticated_runtime_measurement"
    pinned_sha256: None = None
    proof_obligations: tuple[str, ...] = (
        "Resolve the exact path; measure bounded Linux amd64 ELF64 little-endian executable bytes and SHA-256.",
        "Authenticate normalized path, resolved path, executable hash and image identity with the target inspection owner.",
        "Authenticate that the runtime controller is that same measured executable in that same immutable image.",
        "Bind controller source identity and frozen JAVA.1C invocation to the runtime evidence digest.",
        "JAVA.1C currently lacks a controller binary identity field; an additive authenticated measurement attachment is required.",
        "No stable fixed controller digest is established for requirement pinning; historical report hashes cannot supply it.",
    )


@dataclass(frozen=True, slots=True)
class InspectionBounds:
    export_timeout_ms: int = 30_000
    max_archive_bytes: int = 2 * 1024 * 1024 * 1024
    max_archive_entries: int = 250_000
    max_executable_bytes: int = 128 * 1024 * 1024
    max_link_hops: int = 40


@dataclass(frozen=True, slots=True)
class EvidenceEdge:
    source: str
    target: str
    equalities: tuple[tuple[str, str], ...]
    obligation: str


@dataclass(frozen=True, slots=True)
class NegativeOutcome:
    code: str
    condition: str
    meaning: str
    blocks_provider_proof: bool = field(default=True, init=False)
    fallback_allowed: bool = field(default=False, init=False)
    global_absence_claimed: bool = field(default=False, init=False)


TARGET_LOCAL_SAFETY = (
    ("immutable_image", "Exact required sha256 image ID, independently inspected metadata identity; tags are never identity."),
    ("platform", "Image OS linux, architecture amd64; Linux amd64 ELF64 little-endian ET_EXEC/ET_DYN executables, machine 62."),
    ("java_identity", "Exact normalized java path and SHA-256 of all measured executable bytes; remeasure at runtime."),
    ("javac_identity", "Exact normalized javac path and SHA-256 of all measured executable bytes; remeasure at runtime."),
    ("toolchain_pair", "Both exact binaries resolve to one valid same-directory toolchain pair; ambiguous target records/pairs block."),
    ("controller_identity", "Exact /usr/local/bin/python plus owner-authenticated measured executable/runtime identity; presence is insufficient."),
    ("path_normalization", "Frozen POSIX normalization; reject NUL, backslash, invalid paths and parent traversal."),
    ("root_escape_prevention", "Resolve absolute/relative symlinks and root-relative hardlinks within the image root."),
    ("link_bounds", "Reject symlink/hardlink cycles and resolution beyond the frozen 40-hop bound."),
    ("nonroot_access", "Executable and known ancestor traversal checks for uid/gid 65534; unlisted ancestors require runtime confirmation."),
    ("no_extraction", "Stream archive members in memory; never extract filesystem entries onto the host."),
    ("no_inspection_execution", "Inspect a stopped phase-owned container; no container start, java, javac or controller execution during inspection."),
    ("bounded_archive", "30-second per-target export, 2 GiB archive, 250000 entries; overflow/truncation/error blocks."),
    ("bounded_executable", "20..134217728 executable bytes; bounded reads, full byte digest and ELF validation; truncation blocks."),
    ("safe_inspection_container", "Independently inspect exact image, nonroot, network none, read-only root, no privilege/caps/mounts and frozen resource configuration."),
    ("no_declared_volumes", "Reject image-declared volumes and all host Binds/Mounts; retain original inspection-container safety checks."),
    ("cleanup", "Reap export/control processes, close pipes, remove phase containers and temporary state, independently verify absence."),
    ("no_pull", "Required target must already be local; pull never."),
    ("no_build", "No builds or provisioning."),
    ("no_tag_substitution", "No mutable tag resolution, tag selection or automatic substitution."),
    ("no_fallback", "No alternate provider, candidate ranking, first match, retry with another provider or generic discovery."),
)

RUNTIME_SAFETY = (
    ("sandbox", "Exact runtime_sandbox_2_v1 and required policy; authenticate owner descriptor/receipt and every frozen SANDBOX.2 ladder gate."),
    ("invocation", "Fresh RUNTIME.JAVA.1C/runtime_java_1c_v1 fixed source, javac/JVM argv, main/classpath and controller source; no caller command/flags/source."),
    ("versions", "Successful nonempty exact java/javac version evidence from the authenticated SANDBOX.2 ladder; no generic version range."),
    ("isolation", "Network none and frozen syscall denials; no shell, host mounts, image volumes or arbitrary commands; read-only root."),
    ("identity", "PID 1, uid/gid 65534:65534, all capabilities dropped/zero, no-new-privileges, exact frozen eight-variable environment."),
    ("containment", "Private PID/cgroup; IPC none; all seven measured namespaces; identical child/controller namespace and cgroup boundaries before/after."),
    ("resources", "128 PIDs, 134217728 bytes memory, 1000000000 NanoCpus; /work 32 MiB rw,nosuid,nodev,1777; /tmp 16 MiB rw,nosuid,nodev,noexec,1777."),
    ("controller_threads", "One Python and OS controller thread before/after; zero Thread.start attempts; frozen selector capture."),
    ("capture", "10000 ms outer timeout, 5000 ms abort/shared controller deadline; independent bounded pipes/EOF; outer stdout/stderr 8192 each, version/runtime 1024 each, compiler 2048 each."),
    ("source_class_output", "Exact 129-byte frozen source/hash/readback, initially empty workdir, sole valid class 1..32768 bytes, exact manifest and JAVA_SANDBOX_OK stdout/empty stderr; runtime leaves workspace unchanged."),
    ("cleanup", "Kill/reap process groups/children, close pipes and selector, both EOFs, only PID 1 remains before container removal; authenticated removal/absence and ephemeral outputs."),
    ("authority", "Provider evidence is infrastructure evidence only; no execution, SYNTH, reflection, lease, BANK, EXECUTOR or Apply authority."),
)

# Conceptual field roles, not a new receipt implementation or class layout.
EVIDENCE_FIELDS = (
    "proof_owner_identity", "proof_context_identity", "requirement_profile", "requirement_schema",
    "target_inspection_owner_identity", "target_image_identity", "backend_route_identity",
    "backend_server_version", "target_inspection_evidence_fingerprint",
    "backend_binding_evidence_fingerprint", "backend_binding_sandbox_descriptor_fingerprint",
    "backend_binding_sandbox_receipt_fingerprint", "backend_binding_sandbox_receipt_evidence_digest",
    "sandbox_pair_bridge_evidence_fingerprint",
    "sandbox_descriptor_fingerprint", "sandbox_receipt_fingerprint", "sandbox_receipt_evidence_digest",
    "java1c_descriptor_fingerprint", "java1c_receipt_fingerprint", "java1c_receipt_evidence_digest",
    "java1c_image_identity", "java_path", "java_sha256", "javac_path", "javac_sha256",
    "controller_path", "controller_resolved_path", "controller_measured_sha256",
    "controller_runtime_identity_evidence_fingerprint", "controller_source_identity",
    "cleanup_result", "cleanup_evidence_fingerprint",
)

EVIDENCE_GRAPH = (
    EvidenceEdge("backend_binding", "target_inspection", (
        ("canonical_backend_identity", "backend_route_identity"),
        ("canonical_backend_version", "backend_server_version"),
        ("target_image_identity", "target_image_identity"),
        ("target_inspection_evidence_fingerprint", "evidence_fingerprint"),
        ("target_inspection_owner_identity", "owner_identity"),
    ), "Future additive target-binding owner authenticates inspection provenance and the original route/Server.Version bracket; string equality alone is insufficient."),
    EvidenceEdge("target_inspection", "provider_identity", (
        ("evidence_fingerprint", "target_inspection_evidence_fingerprint"),
        ("target_image_identity", "provider_image_identity"),
        ("java_path", "java_path"), ("java_sha256", "java_sha256"),
        ("javac_path", "javac_path"), ("javac_sha256", "javac_sha256"),
        ("controller_path", "controller_path"),
        ("controller_resolved_path", "controller_resolved_path"),
        ("controller_measured_sha256", "controller_measured_sha256"),
    ), "Provider owner authenticates the exact inspection object and checks all required pins/local checks/bounds; metadata or fabricated hashes do not prove bytes."),
    EvidenceEdge("backend_binding", "backend_binding_sandbox", (
        ("sandbox_descriptor_fingerprint", "descriptor_fingerprint"),
        ("sandbox_receipt_fingerprint", "receipt_fingerprint"),
        ("sandbox_receipt_evidence_digest", "receipt_evidence_digest"),
        ("target_image_identity", "image_identity"),
        ("canonical_backend_identity", "backend_route_identity"),
        ("canonical_backend_version", "backend_server_version"),
    ), "Authenticate BIND's exact own sandbox pair, projecting its fingerprints/digest as backend_binding_sandbox evidence roles; these are not the actual JAVA.1C pair's fingerprints/digest."),
    EvidenceEdge("backend_binding_sandbox", "java1c_sandbox", (
        ("image_identity", "image_identity"),
        ("backend_route_identity", "backend_route_identity"),
        ("backend_server_version", "backend_server_version"),
    ), "An additive owner-authenticated route/version bridge must bind both exact sandbox pairs and target inspection fingerprint/owner. Preserve distinct fingerprints/digests if separately issued; never equate pair fingerprints. Route/version are future authenticated attachment measurements, not fields claimed to exist in frozen SANDBOX.2 receipts. Never assume pairs are identical."),
    EvidenceEdge("java1c_sandbox", "runtime", (
        ("descriptor_fingerprint", "sandbox_descriptor_fingerprint"),
        ("receipt_fingerprint", "sandbox_receipt_fingerprint"),
        ("receipt_evidence_digest", "sandbox_receipt_evidence_digest"),
        ("image_identity", "java1c_image_identity"),
        ("backend_route_identity", "backend_route_identity"),
        ("backend_server_version", "backend_server_version"),
    ), "Authenticate fresh JAVA.1C descriptor/receipt with its own sandbox pair, exact policy and sandbox receipt evidence digest; its descriptor must reference that exact JAVA.1C receipt fingerprint. Future attachments must authenticate actual runtime route/version measurements too; frozen JAVA.1C exposes no such receipt fields."),
    EvidenceEdge("provider_identity", "runtime", (
        ("provider_image_identity", "java1c_image_identity"),
        ("java_path", "java_path"), ("java_sha256", "java_sha256"),
        ("javac_path", "javac_path"), ("javac_sha256", "javac_sha256"),
        ("controller_path", "controller_path"),
        ("controller_resolved_path", "controller_resolved_path"),
        ("controller_measured_sha256", "controller_measured_sha256"),
    ), "Future provider attachment authenticates inspection fingerprint, backend binding, runtime descriptor/receipt/digest and controller runtime measurement together. Frozen JAVA.1C lacks these cross-owner/controller fields; no implicit link is allowed."),
    EvidenceEdge("target_inspection", "cleanup", (
        ("evidence_fingerprint", "target_inspection_evidence_fingerprint"),
        ("cleanup_result", "target_inspection_cleanup_result"),
    ), "Authenticate successful inspection/export/control cleanup and zero remaining phase containers; incomplete cleanup blocks proof."),
    EvidenceEdge("runtime", "cleanup", (
        ("java1c_receipt_fingerprint", "java1c_receipt_fingerprint"),
        ("cleanup_result", "runtime_cleanup_result"),
    ), "Authenticate successful sandbox/runtime/child/capture/container cleanup. Final proof binds the cleanup evidence fingerprint; any cleanup failure blocks."),
    EvidenceEdge("backend_binding", "cleanup", (
        ("evidence_fingerprint", "backend_binding_evidence_fingerprint"),
        ("cleanup_result", "backend_binding_cleanup_result"),
    ), "Authenticate BIND pre/post control reaping, pipe closure, sandbox cleanup, workspace removal and zero remaining phase containers."),
    EvidenceEdge("backend_binding_sandbox", "cleanup", (
        ("receipt_fingerprint", "backend_binding_sandbox_receipt_fingerprint"),
        ("cleanup_result", "backend_binding_sandbox_cleanup_result"),
    ), "Authenticate cleanup of BIND's exact own sandbox pair; no cleanup result is inferred from a different pair."),
    EvidenceEdge("java1c_sandbox", "cleanup", (
        ("receipt_fingerprint", "sandbox_receipt_fingerprint"),
        ("cleanup_result", "sandbox_cleanup_result"),
    ), "Authenticate cleanup of the actual JAVA.1C sandbox pair; no cleanup result is inferred from BIND's pair or another node."),
)

EVIDENCE_AUTHENTICATION = (
    "One future provider owner must authenticate every node and edge, and bind all required identifiers/fingerprints/digests into one final proof root with the new requirement profile/schema.",
    "Each node must identify its issuer/owner and a fresh owner-established proof context; explicit authenticated attachments must relate independently issued contexts.",
    "Owner authenticators must validate original typed evidence and exact payload/fingerprint links; report JSON, copied objects and caller-supplied strings cannot replace owner provenance.",
    "Fingerprints/digests must use their frozen owners' canonical full-payload SHA-256 semantics; additive attachments must define canonical domain-separated payloads covering all bindings and cleanup. Hash equality without owner authentication is insufficient.",
    "Freshness requires newly authenticated owner evidence for this proof attempt; historical LOCAL reports/receipts cannot be replayed. Common process, endpoint or time order supplies no binding.",
    "Original BIND.1 means fixed local-docker route plus exact Linux Server.Version before/after equality only; daemon instance identity, continuity and ABA resistance are not established or claimed.",
    "A fresh BIND alone is insufficient. sandbox_backend_binding_satisfies_java1_discovery requires original discovery-owner evidence and must not be repurposed for target inspection.",
    "Fresh JAVA.1C is one runtime component, not this requirement or an exact-provider proof; its actual newly issued SANDBOX.2 pair must be authenticated and bridged to the target binding.",
    "All required equalities and authenticators must pass. Missing, conflicting, stale, fabricated, incomplete or unauthenticated evidence blocks; no best-effort acceptance.",
)

NEGATIVE_OUTCOMES = (
    NegativeOutcome("PINNED_PROVIDER_ABSENT", "Exact target conclusively unavailable locally", "Only required exact provider unavailable; never NO_SUITABLE_LOCAL_JAVA_ARTIFACT or global_java_provider_absent."),
    NegativeOutcome("PINNED_PROVIDER_METADATA_MISMATCH", "Image ID/platform/volume/container metadata mismatch", "Required target failed exact metadata checks."),
    NegativeOutcome("PINNED_PROVIDER_INSPECTION_INCOMPLETE", "Unavailable/failed/truncated/over-budget inspection or ambiguous target evidence", "Target authenticity unproven; transport/inspection failure cannot imply target absence."),
    NegativeOutcome("PINNED_TOOLCHAIN_MISMATCH", "Exact java/javac path/hash/ELF/access/pair mismatch", "Required target toolchain unproven."),
    NegativeOutcome("PINNED_CONTROLLER_MISMATCH", "Controller path/bytes/authenticity/runtime linkage missing or mismatched", "Required controller identity unproven, including unresolved provider-proof obligations."),
    NegativeOutcome("PINNED_BACKEND_BINDING_MISMATCH", "Route/version/sandbox-pair/owner/target binding missing, stale or mismatched", "Required coherent target/backend/sandbox binding unproven."),
    NegativeOutcome("PINNED_RUNTIME_EVIDENCE_MISMATCH", "Fresh JAVA.1C authenticity/identity/digest/constraints/linkage missing or mismatched", "Required runtime component unproven."),
    NegativeOutcome("PINNED_CLEANUP_FAILURE", "Any inspection/backend/sandbox/runtime cleanup incomplete or failed", "Provider proof blocked regardless of other positive evidence."),
    NegativeOutcome("PINNED_PROOF_UNRESOLVED", "Other unknown or unclassified proof condition", "Fail closed; no provider proof or absence inference."),
)

SEMANTIC_DIFFERENCES = (
    ("generic_ordered_provider_selection", "Replaced intentionally by an explicit immutable provider pin; no selection step."),
    ("complete_domain_classification", "Not required and not claimed; unrelated local images need no inspection/classification."),
    ("full_authenticated_inventory_witness", "Not required and not claimed; new exact_provider_proven proof with explicit authenticated evidence graph is required instead."),
    ("global_absence_reporting", "Not available; target_provider_absent != global_java_provider_absent."),
)


@dataclass(frozen=True, slots=True)
class PinnedJavaRequirement:
    phase_id: str = PHASE_ID
    java_profile_id: str = PROFILE_ID
    java_schema_version: str = SCHEMA_VERSION
    image_identity: str = IMAGE
    java: ExecutableIdentity = ExecutableIdentity(
        "/opt/temurin-26.0.2.1/bin/java", "a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2")
    javac: ExecutableIdentity = ExecutableIdentity(
        "/opt/temurin-26.0.2.1/bin/javac", "e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023")
    controller: ControllerRequirement = ControllerRequirement()
    sandbox_profile_id: str = "runtime_sandbox_2_v1"
    sandbox_policy_sha256: str = POLICY_SHA256
    inspection_bounds: InspectionBounds = InspectionBounds()
    target_local_safety: tuple[tuple[str, str], ...] = TARGET_LOCAL_SAFETY
    runtime_safety: tuple[tuple[str, str], ...] = RUNTIME_SAFETY
    proof_kind: str = "exact_provider_proven"
    provider_selection: str = "exact_required_immutable_provider_only_no_selection_step"
    mismatch_action: str = "BLOCK"
    evidence_fields: tuple[str, ...] = EVIDENCE_FIELDS
    evidence_graph: tuple[EvidenceEdge, ...] = EVIDENCE_GRAPH
    evidence_authentication: tuple[str, ...] = EVIDENCE_AUTHENTICATION
    negative_outcomes: tuple[NegativeOutcome, ...] = NEGATIVE_OUTCOMES
    old_new_semantic_differences: tuple[tuple[str, str], ...] = SEMANTIC_DIFFERENCES
    future_authorization_epoch: str = "SYNTH.AUTH.PINNED.1 (proposed identity; additive authorization epoch required before SYNTH use)"
    lifecycle_boundary: str = "Later explicit lifecycle compatibility review required; SYNTH.AUTH.LIFECYCLE.1 acceptance and existing handles cannot be assumed or migrated."
    required_future_receipt_statement: str = (
        "The explicitly required immutable provider was inspected, authenticated, coherently bound to the required backend and runtime evidence, and verified under the required sandbox/runtime constraints."
    )
    future_receipt_fields: tuple[str, ...] = (
        "exact_provider_proven=true", "provider_image_identity", "provider_java_identity",
        "provider_javac_identity", "provider_controller_identity", "target_inspection_evidence",
        "backend_binding_evidence", "sandbox_evidence", "runtime_evidence", "cleanup_evidence",
    )
    forbidden_equivalences: tuple[str, ...] = (
        "exact_provider_proven != complete_inventory",
        "exact_provider_proven != complete_local_artifact_discovery",
        "target_provider_absent != global_java_provider_absent",
        "event A happened before event B != A and B are authenticated as one provider proof",
        "provider evidence != requirement identity",
    )
    proposed_future_chain: tuple[str, ...] = (
        PHASE_ID, "target-specific provider proof implementation", "provider proof validation",
        "new SYNTH authorization epoch", "lifecycle compatibility review", "operational EXECUTOR retry",
    )
    old_requirement_preserved: bool = field(default=True, init=False)
    global_inventory_required: bool = field(default=False, init=False)
    global_inventory_claimed: bool = field(default=False, init=False)
    global_provider_absence_claimed: bool = field(default=False, init=False)
    global_provider_uniqueness_required: bool = field(default=False, init=False)
    global_provider_uniqueness_claimed: bool = field(default=False, init=False)
    inventory_boolean_adapter_allowed: bool = field(default=False, init=False)
    fallback_allowed: bool = field(default=False, init=False)
    tag_selection_allowed: bool = field(default=False, init=False)
    provisioning_allowed: bool = field(default=False, init=False)
    chronology_accepted_as_provenance: bool = field(default=False, init=False)
    old_java1_compatibility_asserted: bool = field(default=False, init=False)
    schema_alias: None = field(default=None, init=False)
    profile_alias: None = field(default=None, init=False)
    synth_auth1_modified: bool = field(default=False, init=False)
    future_synth_authorization_epoch_required: bool = field(default=True, init=False)
    runtime_authority: bool = field(default=False, init=False)
    repository_write_authority: bool = field(default=False, init=False)
    apply_authority: bool = field(default=False, init=False)
    provider_proof_issued: bool = field(default=False, init=False)
    report_only: bool = field(default=True, init=False)
    requirement_only: bool = field(default=True, init=False)

    def as_dict(self):
        """Requirement projection only; no input here can authenticate evidence."""
        return asdict(self)


REQUIREMENT = PinnedJavaRequirement()
