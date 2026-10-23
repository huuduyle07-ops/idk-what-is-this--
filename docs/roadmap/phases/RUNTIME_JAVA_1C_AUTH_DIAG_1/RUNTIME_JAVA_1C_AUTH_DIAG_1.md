# RUNTIME.JAVA.1C.AUTH.DIAG.1 — fresh SANDBOX.2 pair authentication diagnostic

2026-10-10 KST. **JAVA1C_AUTH_DIAG_COMPLETE_WITH_FINDING**. Diagnostic only; no authority issued.

The sole standalone invocation authenticated the exact original SANDBOX.2 descriptor and receipt and rejected their semantic eligibility. The first failure was `descriptor_status_complete`: `descriptor.status != sandbox2.COMPLETE` was true. The pair carried `RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED`, `eligible_for_java1_continuation=false`, `blocked_no_java_capability`, cleanup=false and an empty ladder. Both HMACs passed; **demonstrated_HMAC_failure=false**.

The SANDBOX.2 owner reported `ValueError: exact_local_java_image_required`. Its image-inspection control exited 1 before workspace creation or any verification stage. A separate read-only restricted-context check demonstrated permission denial at the local Docker pipe; a host-context check verified the exact expected Linux/amd64 image with no volumes and zero phase containers. The original control stderr was not retained, so permission denial is corroborating follow-up evidence, not a verbatim in-attempt stderr capture.

**Historical limit:** this does not establish the older nested attempt’s deeper cause. That frozen attempt’s image inspection succeeded and its SANDBOX.2 report was not retained. Its rejection was also semantic by source order, but the underlying pre-ladder failure remains unresolved. Standalone did not pass; `STANDALONE_PASS_CONTEXT_SENSITIVE` does not apply. No second issuance was performed, including outside the restricted environment.

## Result and exact original pair

| Item | Observation |
| --- | --- |
| Final diagnostic status | JAVA1C_AUTH_DIAG_COMPLETE_WITH_FINDING |
| Classification | SEMANTIC_ELIGIBILITY_FAILURE |
| Standalone JAVA.1C | RUNTIME_JAVA_1C_BLOCKED_AUTHENTICATION |
| JAVA.1C controller error | ValueError: java1c_live_sandbox2_binding_rejected |
| SANDBOX.2 status | RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED |
| First failed predicate | descriptor_status_complete |
| Public SANDBOX.2 receipt/descriptor authentication | PASS / PASS |
| Receipt HMAC / descriptor HMAC | PASS / PASS |
| demonstrated_HMAC_failure | False |
| Semantic eligibility flag | False |
| Standalone passed / nested context sensitivity | false / NOT_ESTABLISHED |
| Historical deeper cause established | False |
| Observer issuing process PID | 14420 |
| Descriptor exact type | core.thread_compatible_runtime_sandbox.ThreadCompatibleSandboxDescriptor |
| Descriptor original object identity | 0x19645956c40 |
| Receipt exact type | core.thread_compatible_runtime_sandbox.ThreadCompatibleSandboxReceipt |
| Receipt original object identity | 0x196465f1490 |
| Owner-exposed issuing PID | Absent; observer process PID is provenance, not an owner field |
| Phase / schema | RUNTIME.SANDBOX.2 / runtime_sandbox_2_v1 |
| Policy SHA | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| Image identity | sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a |
| Descriptor fingerprint | edd9ba704304d997dd2ab3db61c6761132de3a4c36e458c5d2df3dab1d949ba6 |
| Receipt fingerprint and descriptor receipt binding | 67aab975dd09eed2968975df1358c8f98188f17a2a0b8d323afc1d07b29b2d1b |
| Receipt evidence digest (hash of empty stages) | 4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945 |
| Receipt cleanup / classification | False / blocked_no_java_capability |
| Registry membership | NOT_APPLICABLE:no registry in frozen owner |
| All seven authority fields on each object | false, recorded in fresh_pair_observation.json |
| Original objects serialized/reconstructed before validation | False |
| Signature/key material exported | False |

[Full JSON report](RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json), [original pair observation](fresh_pair_observation.json), [unchanged JAVA.1C owner report](JAVA1C_standalone_report.json), [retained SANDBOX.2 owner report](SANDBOX2_observed_report.json).

## Static audit and actual ordered predicate decomposition

Rejection expressions below are extracted from the frozen source. PASS means the expression was false and the gate continued. FAIL means it was true and short circuited. Later terms are NOT_REACHED even where independent read-only inspection exposes their field values. The 14 authority subpredicates run descriptor first, then receipt, in SANDBOX.2.AUTHORITIES order.

| Order | Owner | Source | Exact pre-pair condition / operation |
| --- | --- | --- | --- |
| 1 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:328 | validate_policy_bytes(POLICY_PATH.read_bytes()) |
| 2 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:331 | image.status == 'sandbox_completed' and image.exit_code == 0 |
| 3 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:332 | not prefix |
| 4 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:332 | metadata.get('Id') != IMAGE |
| 5 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:332 | metadata.get('Os') != 'linux' |
| 6 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:333 | metadata.get('Architecture') != 'amd64' |
| 7 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:333 | metadata.get('Config', {}).get('Volumes') |
| 8 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:361 | if verdict != PASSED: result['status'] = verdict; break |
| 9 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:375 | count == 0 and result.get('temporary_workspace_removed') is True and all(s['cleanup_verified'] for s in result['stages']) |
| 10 | SANDBOX.2 | core/thread_compatible_runtime_sandbox.py:156 | status == COMPLETE and (not result['cleanup_verified'] or tuple((s['mode'] for s in result['stages'])) != LADDER or any((s['verdict'] != PASSED for s in result['stages']))) |
| 11 | JAVA.1C | core/sandboxed_java_positive_continuation.py:76 | sandbox2.validate_policy_bytes(sandbox2.POLICY_PATH.read_bytes()) |
| 12 | SANDBOX.2 called by JAVA.1C | core/sandboxed_java_positive_continuation.py:77 | sandbox2._evidence_pair(live) |

| Order | Predicate | Inputs | Field owner / category | Rejection expression | Result |
| --- | --- | --- | --- | --- | --- |
| 1 | receipt_exact_type | ["type(receipt)"] | SANDBOX.2 receipt class / type_identity | type(receipt) is not ThreadCompatibleSandboxReceipt | PASS |
| 2 | receipt_hmac | ["receipt._signature", "_sign(receipt)"] | SANDBOX.2 issuer / HMAC_signature_process_local | not hmac.compare_digest(receipt._signature, _sign(receipt)) | PASS |
| 3 | descriptor_exact_type | ["type(descriptor)"] | SANDBOX.2 descriptor class / type_identity | type(descriptor) is not ThreadCompatibleSandboxDescriptor | PASS |
| 4 | descriptor_hmac | ["descriptor._signature", "_sign(descriptor)"] | SANDBOX.2 issuer / HMAC_signature_process_local | not hmac.compare_digest(descriptor._signature, _sign(descriptor)) | PASS |
| 5 | descriptor_receipt_fingerprint | ["descriptor.verification_receipt_fingerprint", "receipt.fingerprint"] | SANDBOX.2 pair / receipt_fingerprint_binding | descriptor.verification_receipt_fingerprint != receipt.fingerprint | PASS |
| 6 | descriptor_receipt_status | ["descriptor.status", "receipt.status"] | SANDBOX.2 pair / status_binding | descriptor.status != receipt.status | PASS |
| 7 | descriptor_eligibility_equals_complete_status | ["descriptor.eligible_for_java1_continuation", "receipt.status", "sandbox2.COMPLETE"] | SANDBOX.2 pair / semantic_eligibility_binding | descriptor.eligible_for_java1_continuation != (receipt.status == COMPLETE) | PASS |
| 8 | baseline_policy_identity | ["baseline._SECCOMP", "BASELINE_POLICY_SHA256"] | SANDBOX.1 baseline and SANDBOX.2 pin / policy_SHA | baseline._hash(baseline._SECCOMP) != BASELINE_POLICY_SHA256 | PASS |
| 9 | canonical_policy_exact_type | ["type(raw)"] | SANDBOX.2 canonical policy bytes / type_identity | type(raw) is not bytes | PASS |
| 10 | canonical_policy_bytes | ["raw", "baseline._json(expected).encode()"] | SANDBOX.2 additive policy / policy_bytes | raw != baseline._json(expected).encode() | PASS |
| 11 | canonical_policy_sha256 | ["sha256(raw).hexdigest()", "POLICY_SHA256"] | SANDBOX.2 additive policy / policy_SHA | sha256(raw).hexdigest() != POLICY_SHA256 | PASS |
| 12 | descriptor_status_complete | ["descriptor.status", "sandbox2.COMPLETE"] | SANDBOX.2 descriptor; JAVA.1C acceptance / semantic_completion | descriptor.status != sandbox2.COMPLETE | FAIL |
| 13 | receipt_status_complete | ["receipt.status", "sandbox2.COMPLETE"] | SANDBOX.2 receipt; JAVA.1C acceptance / semantic_completion | receipt.status != sandbox2.COMPLETE | NOT_REACHED |
| 14 | descriptor_java1_eligibility_is_true | ["descriptor.eligible_for_java1_continuation"] | SANDBOX.2 descriptor; JAVA.1C acceptance / semantic_eligibility_exact_boolean | descriptor.eligible_for_java1_continuation is not True | NOT_REACHED |
| 15 | receipt_java1_classification | ["receipt.compatibility_classification"] | SANDBOX.2 receipt; JAVA.1C acceptance / semantic_eligibility_classification | receipt.compatibility_classification != 'eligible_for_JAVA_1_continuation_only' | NOT_REACHED |
| 16 | receipt_cleanup_is_true | ["receipt.cleanup_verified"] | SANDBOX.2 receipt; JAVA.1C acceptance / cleanup_exact_boolean | receipt.cleanup_verified is not True | NOT_REACHED |
| 17 | receipt_full_ladder_passed | ["receipt.stage_results", "sandbox2.LADDER", "sandbox2.PASSED"] | SANDBOX.2 fixed verification ladder / semantic_stage_results | receipt.stage_results != tuple(((m, sandbox2.PASSED) for m in sandbox2.LADDER)) | NOT_REACHED |
| 18 | descriptor_receipt_fingerprint_java1c | ["descriptor.verification_receipt_fingerprint", "receipt.fingerprint"] | SANDBOX.2 pair; JAVA.1C acceptance / receipt_fingerprint_binding | descriptor.verification_receipt_fingerprint != receipt.fingerprint | NOT_REACHED |
| 19 | descriptor_receipt_policy_equal | ["descriptor.seccomp_policy_sha256", "receipt.seccomp_policy_sha256"] | SANDBOX.2 pair / policy_SHA_binding | descriptor.seccomp_policy_sha256 != receipt.seccomp_policy_sha256 | NOT_REACHED |
| 20 | receipt_policy_java1c | ["receipt.seccomp_policy_sha256", "java1c.POLICY_SHA256"] | SANDBOX.2 receipt and JAVA.1C pin / policy_SHA | receipt.seccomp_policy_sha256 != POLICY_SHA256 | NOT_REACHED |
| 21 | canonical_policy_sha_java1c | ["sandbox2.POLICY_SHA256", "java1c.POLICY_SHA256"] | SANDBOX.2 policy constant and JAVA.1C pin / policy_SHA | sandbox2.POLICY_SHA256 != POLICY_SHA256 | NOT_REACHED |
| 22 | descriptor_image_java1c | ["descriptor.image_identity", "java1c.IMAGE"] | SANDBOX.2 descriptor and JAVA.1C image pin / image_identity | descriptor.image_identity != IMAGE | NOT_REACHED |
| 23 | receipt_image_java1c | ["receipt.image_identity", "java1c.IMAGE"] | SANDBOX.2 receipt and JAVA.1C image pin / image_identity | receipt.image_identity != IMAGE | NOT_REACHED |
| 24 | all_authorities_false | ["descriptor/receipt.runtime_authority", "descriptor/receipt.repository_write_authority", "descriptor/receipt.apply_authority", "descriptor/receipt.shell_available", "descriptor/receipt.arbitrary_command_authority", "descriptor/receipt.host_mount_authority", "descriptor/receipt.network_authority"] | SANDBOX.2 pair; JAVA.1C acceptance / authority_exact_false | any((getattr(value, key) is not False for value in (descriptor, receipt) for key in sandbox2.AUTHORITIES)) | NOT_REACHED |
| 25 | live_descriptor_fingerprint | ["live['descriptor']['sandbox_descriptor_fingerprint']", "descriptor.fingerprint"] | SANDBOX.2 replay report and reconstructed issuer descriptor / descriptor_fingerprint | live['descriptor']['sandbox_descriptor_fingerprint'] != descriptor.fingerprint | NOT_REACHED |
| 26 | live_receipt_fingerprint | ["live['verification_receipt']['verification_receipt_fingerprint']", "receipt.fingerprint"] | SANDBOX.2 replay report and reconstructed issuer receipt / receipt_fingerprint | live['verification_receipt']['verification_receipt_fingerprint'] != receipt.fingerprint | NOT_REACHED |
| 27 | live_receipt_evidence_digest | ["receipt.evidence_sha256", "baseline._hash(live['stages'])"] | SANDBOX.2 measured stages and issuer receipt / evidence_digest | receipt.evidence_sha256 != baseline._hash(live['stages']) | NOT_REACHED |
| 28 | live_cleanup_is_true | ["live['cleanup_verified']"] | SANDBOX.2 replay report / cleanup_exact_boolean | live['cleanup_verified'] is not True | NOT_REACHED |

All authority subpredicates were NOT_REACHED in the live invocation: `descriptor.runtime_authority`, `descriptor.repository_write_authority`, `descriptor.apply_authority`, `descriptor.shell_available`, `descriptor.arbitrary_command_authority`, `descriptor.host_mount_authority`, `descriptor.network_authority`, followed by the same seven receipt fields. The exact subpredicate metadata is retained in the JSON ledger.

The initial public receipt/descriptor validator contains semantic consistency checks as well as type/HMAC authentication: matching receipt fingerprint, status and eligibility relation. Its `*_unauthenticated` error therefore also must not be interpreted as a cryptographic diagnosis without decomposition. The later JAVA.1C branch raises `java1c_live_sandbox2_binding_rejected`; the still later report-binding branch raises `java1c_live_sandbox2_fingerprint_mismatch`. Frozen `verify` maps all of those pre-controller exceptions to its initialized `not_authenticated` reason.

There is no original-object identity, issuing-PID or registry predicate. Phase/schema are included in the signed payload but have no independent equality predicate. Signed same-value copies pass. Unsigned phase/schema changes fail HMAC; controlled re-signed fixture changes pass. A fresh interpreter has a new module-local HMAC domain; PID itself is not checked, and a fork-inherited key would be a different scenario from the tested fresh interpreter.

[Exact static flow and predicate metadata](static_predicate_audit.json), [pair ledger](predicate_ledger.json).

## Pure fixture matrix and validation

All **57 fixture expectations passed**, covering all 28 rejection expressions and all 14 authority fields. Independent AST probes cover dominated/repeated expressions and constant policy comparisons without replacing owner functions or constants. Controlled fixture signing never supplied live authority.

The matrix covers valid originals; descriptor/receipt copies; wrong pairs and exact types; wrong process; phase/schema; policy and image; receipt/report fingerprints; evidence digest; cleanup; eligibility/status/classification/stage order; signatures; authorities; and explicit nonapplicability of registry/object/PID predicates. One exact Python-only child tested the fresh-process HMAC domain. Pure Docker, Java, shell and socket effects were zero.

Observer self-tests retained the exact fixture objects, rejected existing system profiling and tracing, restored instrumentation and preserved owner functions. Runtime entry rejects system/thread profiling, tracing and occupied monitoring slots. The live observer reads only fixed code-object argument/return frames; it does not assign frame locals, owner functions, receipts or returns. Owner object identities, function code identities and public policy hashes stayed unchanged. Original live objects were used for public validators and direct HMAC checks before report serialization.

[Full fixture evidence](pure_matrix.json), [observer checks](observer_checks.json), [final artifact consistency, compilation, JSON and link checks](validation_summary.json).

## Process state and historical context

No preexisting system/thread profiler, tracer or monitoring tool was present. Only this diagnostic’s profile observer was installed during the sole call; all instrumentation was restored afterward. Before/after module identities, entry-function/code identities, current PID, tempfile global and authentication-domain identity class are in the full report. No SANDBOX.2 registry exists, so registry sizes/identities are not applicable. No HMAC keys or signatures were dumped.

The successful historical retry and blocked nested SYNTH path share five frozen owner source hashes. Both used the provider’s return-frame profiler; the successful retry additionally used a private-config tracer and a different phase-local temporary root. The upstream transport wrappers are lexically scoped and end before JAVA.1C; static evidence does not establish residue. Profiler presence alone is not a demonstrated cause. The older nested control record has successful exact-image inspection and zero SANDBOX.2 creates. Those facts bound its missing failure to pre-ladder work but cannot select metadata, temporary workspace or socket setup as the exact cause.

[Pure/static context comparison](context_comparison.md), [source-hash comparison evidence](context_comparison.json).

## Operational effects, cleanup and preservation

| Effect | Count |
| --- | --- |
| Apply | 0 |
| BANK | 0 |
| BIND1 | 0 |
| Docker_controls | 3 |
| EXECUTOR.1R | 0 |
| JAVA1C_JVM_probe_count | 0 |
| JAVA1C_compile_count | 0 |
| JAVA1C_fixed_controller_containers | 0 |
| PINNED1A_export | 0 |
| SANDBOX2_fixed_probe_containers | 0 |
| SANDBOX2_java_version_probes | 0 |
| SANDBOX2_javac_version_probes | 0 |
| SyntheticStateBox | 0 |
| alternative_provider_inspection | 0 |
| arbitrary_Java | 0 |
| caller_shell | 0 |
| generic_image_inventory | 0 |
| host_mounts | 0 |
| outbound_workload_network | 0 |
| post_attempt_read_only_Docker_controls | 5 |
| pure_fixture_Python_domain_children | 1 |
| reflection | 0 |
| reflection_lease_consumption | 0 |
| repository_runtime_writes | 0 |
| runtime_lease_consumption | 0 |
| total_Docker_controls | 8 |

The Docker controls comprise three controls in the original owner invocation and five separate post-attempt read-only exact-image/phase-container observations. None created containers. Zeroes are supported by frozen source hashes, observed original argv/scope, `shell=False`, absence of create/start commands and zero observed forbidden owner calls; they are not an OS-wide event-tracing claim. All runtime authority fields remain false.

The original owner cleanup proof was unavailable because both in-attempt container listings exited 1; their remaining counts are null and their original cleanup flags remain false in the raw reports. A separate host read-only phase-filtered listing verified **zero remaining containers**. All original controls were reaped, all pipes closed, zero host readers survived, all generated private Docker config paths remained absent, no temporary workspace was created, and the observer was restored. The post-observation controls were also reaped and their private config paths remained absent. Independent final cleanup passed; no residual cleanup failure was measured.

The first host image-output filter failed on a missing optional Volumes key. Its artifact was retained; a corrected read-only filter passed. This was a reporting correction, not another owner invocation.

All **1828 frozen existing files** retain their baseline bytes. JAVA.1C and SANDBOX.2 sources, PINNED phases/retry artifacts, SYNTH blocked attempt/source/contracts, lifecycle/reflection/EXECUTOR owners and history, registry and reversal artifacts were preserved. Existing worktree changes were neither repinned nor reverted. No stash/reset/clean was used. Only this new diagnostic folder was authored.

[Control observations](observed_controls.json), [restricted read-only follow-up](post_observation_restricted.json), [host zero-container observation](post_observation_host.json), [corrected exact-image observation](post_exact_image_observation.json), [preservation baseline](preservation_baseline.json).

**STOP boundary:** no owner remediation, synthetic authorization retry, execution lease, reflection, SyntheticStateBox, BANK, EXECUTOR.1R, runtime grant or provider-root issuance. Exactly one standalone JAVA.1C diagnostic call was made.
