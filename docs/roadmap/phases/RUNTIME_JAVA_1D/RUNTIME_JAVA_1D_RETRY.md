# RUNTIME.JAVA.1D — additive operational retry

2026-10-08 KST. **RUNTIME_JAVA_1D_BLOCKED_DISCOVERY_INCOMPLETE**.

Exactly one fresh public BIND.1 attachment authenticated and the exact frozen original discovery owner ran once. It returned `complete_inventory=false`: image `sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089` hit the unchanged 30,000 ms export limit. The five owner artifact records include the exact pinned Java image and toolchain, but cannot establish complete discovery. The retry stops before public backend comparison, JAVA.1C verification and positive JAVA.1D receipt issuance.

[Additive owner](../../../../core/sandboxed_java_discovery_continuation.py), [retry replay](../../../../scripts/replay_runtime_java1d_retry.py), [pure tests](../../../../tests/test_runtime_java1d_retry.py), [full retry evidence](RUNTIME_JAVA_1D_RETRY_LOCAL.json), and [preservation manifest](RUNTIME_JAVA_1D_RETRY_PRESERVATION.json). The first JAVA.1D blocked attempt and all historical owners/reports remain unchanged. This is RUNTIME.JAVA.1D / runtime_java_1d_v1, with separate retry evidence; no JAVA.1E was introduced.

## Provenance and stopping point

| Requested witness | Result |
| --- | --- |
| Final typed status | RUNTIME_JAVA_1D_BLOCKED_DISCOVERY_INCOMPLETE |
| Fresh BIND.1 authentication | Passed through public issuer and validator; exactly one issuance |
| Attachment ID | 5e8502e09b6445948f9231a8733b216031d33c074743e56664cc16f093428eee |
| Attachment fingerprint | f86ad86126ec8990275e046d131fbe307d71db32d1b34d364ccdf0e892659964 |
| Bound SANDBOX.2 descriptor fingerprint | f4e2a82183c97f897bcf90c8476bf3e0f182ddbf8f04767530374c4d0fc9b231 |
| Bound SANDBOX.2 receipt fingerprint | e8632738e3473b113d98e4014a40dc5dcda6e3e73c597b66d05605c34f288e97 |
| Bound receipt evidence digest | 0eff0308df016ceb62e1474befba4f7ed7d45ed438263dc69a8fb614e1026544 |
| Profile / policy | runtime_sandbox_2_v1 / 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| Binding semantics | original_java1_route_and_server_version_v1 |
| Route/version bracket equal | true |
| Canonical backend identity | local-docker:npipe:////./pipe/dockerDesktopLinuxEngine |
| Canonical backend version | 29.6.1 |
| Original discovery backend identity | local-docker:npipe:////./pipe/dockerDesktopLinuxEngine |
| Original discovery backend version | 29.6.1 |
| Public discovery/backend comparison | Not reached after completeness failure; result null. No manual string equality is substituted. |
| Daemon continuity / ABA resistance claimed | false / false; neither demanded |
| complete_inventory | false |
| Recorded artifact count | 5; one filesystem inspection incomplete |
| Deterministic recorded inventory digest | 4d3b8f6f1adc3311071f188cd5909971d6c64597dcdecbca7b580325d591b92e |
| Exact pinned image observed | true in the incomplete inventory; no complete-membership claim |
| Selected image | Not selected after earlier gate failure |
| Fresh JAVA.1C authentication / descriptor / receipt | Not attempted / none / none |
| Inventory/provider image and toolchain coherence | Not established with fresh JAVA.1C |
| Positive JAVA.1D receipt fingerprint | None; no positive receipt issued |
| JAVA.1 identity equality / compatibility asserted | false / false |
| Compatibility relation / SYNTH satisfaction / runtime authority | none / false / false |

The canonical representation sorts full original artifact records by immutable image identity and full record encoding. It retains duplicates and every inner metadata/toolchain distinction. The digest above authenticates no completeness claim: it describes the recorded incomplete representation only. The original owner still defines its own sorted unique image-ID domain, classifications and available-toolchain candidates; no approximate discovery implementation or tag selection exists here.

| Original immutable artifact identity | Original classification | Cleanup |
| --- | --- | --- |
| sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089 | image_export_timeout | True |
| sha256:1d533553fefe4f12e5d80c7b80622ba0c382abb5758856f52983d8789179f0fb | local_image_mounts_ineligible | True |
| sha256:4fbb8e6a8395de5a7550b33509421a2bafbc0aab6c06ba2cef9ebffbc7092d90 | local_java_toolchain_absent | True |
| sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de | local_java_toolchain_absent | True |
| sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a | local_java_toolchain_present | True |

The discovery domain remains all IDs from the frozen local Docker endpoint's `image ls --all --no-trunc --quiet`, immutable image metadata and bounded stopped-container exports for eligible linux/amd64 images without declared volumes. Original archive, executable, path/link and controller rules remain unchanged: 2 GiB archive, 250,000 entries, 128 MiB executable, 65,536-byte control stdout and 30-second export bound. The image declaring volumes is an explicit original ineligible classification, not the cause of incompleteness. No timeout increase, artifact filtering, image mutation, provisioning or repeat discovery followed the block.

Required JAVA.1C identity remains RUNTIME.JAVA.1C / runtime_java_1c_v1, image `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`, java `/opt/temurin-26.0.2.1/bin/java` / `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2`, javac `/opt/temurin-26.0.2.1/bin/javac` / `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023`. The original discovery record observes that exact image/toolchain. These required identities and discovery observations are not fresh JAVA.1C positive evidence.

The additive owner has a gated positive continuation receipt with a separate process-local HMAC domain and live object provenance. Pure tests cover that path with fabricated fixtures. This operational retry issued no such receipt. Reports cannot reconstruct a capability; no compatibility relation or synthetic requirement satisfaction is exposed. Historical SANDBOX.2P remains RUNTIME_SANDBOX_2P_BLOCKED_FRESHNESS, historical JAVA.1D remains RUNTIME_JAVA_1D_BLOCKED_BACKEND_BINDING, and COMPAT.1 remains RUNTIME_JAVA_COMPAT_1_BLOCKED_SEMANTIC_GAP.

## Effects and cleanup

| Operational effect | Count |
| --- | --- |
| BIND.1 PRE / POST version calls | 1 / 1 |
| BIND.1 SANDBOX.2 Docker calls / creates / starts | 74 / 11 / 11 |
| Original discovery Docker calls / inventory / image inspections | 27 / 1 / 5 |
| Discovery stopped containers / exports / starts | 4 / 4 / 0 |
| Fresh JAVA.1C Docker calls / containers | 0 / 0 |
| Final phase-container inspection | 1 |
| Total Docker calls / created containers / host children | 104 / 15 / 104 |
| javac / Java executions | 1 / 1; BIND.1 SANDBOX.2 version commands only |
| Java compilations / Java fixture executions / Java source projections | 0 / 0 / 0 |
| Pulls / builds / other exports | 0 / 0 / 0; all four exports belong to exact original discovery |
| Outbound network / shell / host mounts | 0 / 0 / 0 |
| SYNTH runtime / reflection lease consumptions | 0 / 0 |
| BANK / EXECUTOR.1R retries / Apply / repository runtime writes | 0 / 0 / 0 / 0 |
| Remaining phase containers | 0 |

BIND.1 fresh sandbox cleanup, PRE/POST reaping, all discovery controls, export controls, temporary workspace removal and final container absence passed. The new observer verified all 104 host Docker children were reaped and stdin/stdout/stderr pipes closed. The unchanged SANDBOX.2 ladder checks contained descendants and selector cleanup and uses two host loopback isolation listeners; it performs no outbound traffic. No JAVA.1C resources were created.

## Validation and preservation

| Selection | Baseline | After |
| --- | --- | --- |
| SYNTH / reflection / lifecycles / historical executor | 801 passed, 0 failed | 801 passed, 0 failed |
| Frozen Java / sandbox / original discovery pure selection | 498 passed, 1 failed, 5 deselected | 498 passed, 1 failed, 5 deselected |
| Registry / picker / historical reversals | 292 passed, 12 failed | 292 passed, 12 failed |
| Authority / Apply / patch / path safety | 241 passed, 1 failed | 241 passed, 1 failed |
| Current EXECUTOR.1R blocked-result unit regression | 46 passed, 0 failed | 46 passed, 0 failed |
| BIND.1 / SANDBOX.2P / COMPAT.1 / historical JAVA.1D / retry | 260 passed, 0 failed | 287 passed, 0 failed |

All 27 new retry tests pass; the combined focused selection has 287 passes. Five historical fake-process reader tests also pass separately. The same twelve distinct pre-existing failure identities remain, with no new regression failure. The initial Windows platform-probe guard diagnostic is retained and explained in the JSON; the corrected guard still denies the probe before launch and lets Python's standard platform fallback run. No registry projection or fixture repinning was used.

`benchmarks --check`: 54 checked, zero errors, zero workload/agent calls. In-memory Python compilation: 1236 files, zero failures and no bytecode emission. `git diff --check`, additive whitespace checks and historical byte checks pass. Full repository suite not run.

All 1,841 pre-existing files are byte-identical, and eight already-missing paths remain missing. All seven prior preservation manifests match, including BIND.1, SANDBOX.2P and the first JAVA.1D attempt. All original Java/sandbox/synthetic owners, executor attempts, registry history, reversal receipts and unrelated edits are preserved. No stash/reset/clean was used.

Work stops at incomplete original discovery. No COMPAT.2, JAVA.1C operational proof, synthetic/BANK execution or EXECUTOR.1R retry follows.
