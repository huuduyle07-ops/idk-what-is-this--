# RUNTIME.JAVA.1D — discovery provenance stop gate

2026-10-08 KST. **RUNTIME_JAVA_1D_BLOCKED_BACKEND_BINDING**.

Fresh SANDBOX.2 passed all eleven frozen infrastructure stages and authenticated through its existing owner and public validator. Its authenticated descriptor and receipt expose neither `backend_identity` nor `backend_version`. JAVA.1D therefore stops at ordering step 2, as requested. No additive positive provider receipt can be issued under the frozen API. SANDBOX.2 was not modified.

[Blocked replay](../../../../scripts/replay_runtime_java1d.py), [pure stop-gate tests](../../../../tests/test_runtime_java1d.py), [recorded live evidence and validation](RUNTIME_JAVA_1D_LOCAL.json), and [historical byte preservation](RUNTIME_JAVA_1D_PRESERVATION.json).

The `runtime_java_1d_v1` schema identifies this separate blocked attempt. No provider descriptor or `JavaDiscoveryCompleteContinuationReceipt` exists. No compatibility relation, runtime_java_1_v1 identity claim, SYNTH.AUTH satisfaction, lease, executor adapter or real task authority is exposed. COMPAT.2 was not created, and EXECUTOR.1R was not retried.

## Measured blocker

The exact original `core/sandboxed_java_toolchain.py` verifier compares discovery backend identity **and** version with the authenticated sandbox descriptor, rejecting a mismatch as `java_runtime_boundary_incomplete:backend_binding_changed`. It separately requires `complete_inventory`, rejecting incomplete discovery as `java_artifact_discovery_incomplete`. The original discovery implementation and its success/failure tests were inspected directly before adding this stop gate.

Both frozen SANDBOX.2 dataclasses lack both backend fields. The receipt authenticates a digest of its infrastructure stage facts; those facts also contain no discovery/backend identity/version witness. Its image identity, policy hash and baseline fingerprints cannot establish the missing backend equality. A fixed local endpoint, copied report fields, Docker context name, fresh timestamps or a separate Docker version call would not bind discovery to this authenticated capability. Backend freshness across discovery and Java execution is consequently unproven too.

The replay uses the existing JAVA.1C owner's `_obtain_live_sandbox2()` helper. That helper runs the SANDBOX.2 owner live, locally reissues the same owner pair, verifies its fingerprints against that invocation, then calls the public validator and exact policy/containment checks. It does not call JAVA.1C `verify()`, accept report JSON, or read historical capability JSON. The exported result remains report-only.

| Required witness | Recorded result |
| --- | --- |
| Fresh SANDBOX.2 authentication | Passed; all eleven stages passed |
| Profile | runtime_sandbox_2_v1 |
| Policy SHA-256 | 5a36bdf1676c4b0d7b4bef489f5e90b5c8fb201b5194be48baf61f4206a81f75 |
| Descriptor fingerprint | 07b9708f67908b5c280829c7630eb4c936ac144946a59eef6633811ca8a0fa1f |
| Receipt fingerprint | b27a27db0dffd771cb086e35b0ecb6148adec33ae1cb4ef05ee0b37d441aac90 |
| SANDBOX.2 backend identity / version | Unavailable in authenticated owner records |
| Discovery backend identity / version | Unmeasured; discovery not attempted |
| Backend equality / freshness | Unproven / unproven |
| complete_inventory | Unmeasured (`null`) |
| Inventory count / deterministic digest | Unmeasured (`null` / `null`) |
| Exact pinned image inventory membership | Unmeasured |
| Fresh JAVA.1C authentication | Not attempted after earlier blocker |
| Inventory-to-JAVA.1C coherence | Unproven |
| JAVA.1D receipt fingerprint | None; no receipt issued |
| runtime_java_1_v1 identity / compatibility asserted | false / false |

## Exact original discovery domain

The original owner queries only its fixed local Docker endpoint. It enumerates `image ls --all --no-trunc --quiet`, validates immutable SHA-256 identities, and sorts/deduplicates those IDs exactly as its implementation defines. Each local image receives immutable metadata inspection. Images outside linux/amd64 or declaring volumes retain explicit ineligible inventory entries; other images receive bounded filesystem export from stopped, isolated containers. It parses executable ELF java/javac pairs and the frozen Python controller without extracting files to the host or executing Java. Tags are not required.

Bounds remain those of the original owner: Docker control stdout 65,536 bytes, archive 2 GiB, 250,000 archive entries, executable 128 MiB, export timeout 30,000 ms. Its existing path/link, executable permission, platform and toolchain-pair semantics remain authoritative. No host-global scanner, new approximate discovery algorithm, inventory normalization, or inventory digest was implemented after the binding stop gate.

Required JAVA.1C identity remains `RUNTIME.JAVA.1C` / `runtime_java_1c_v1`, with image `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`. Required binaries are `/opt/temurin-26.0.2.1/bin/java`, SHA-256 `a719fab9108ba87eba82655ba904edbee0a91ff13365579519f44f99100382b2`, and `/opt/temurin-26.0.2.1/bin/javac`, SHA-256 `e21c219e342544cbf107d25e86ed1d809eac6cc57bce8f68750a42783f13e023`. These are required identities, not fresh JAVA.1C proof or complete inventory membership claims.

## Effects and cleanup

One fresh SANDBOX.2 live ladder ran. Its unchanged fixed probes retain the exact policy, no network, no host mounts, nonroot user, read-only root, closed environment and bounded selector capture for its toolchain stages.

| Operational effect | Count |
| --- | --- |
| Docker calls / discovery calls / inspect calls | 74 / 0 / 26 |
| Containers created / sandbox controller starts | 11 / 11 |
| javac executions / Java executions | 1 / 1; version commands only |
| Compile executions / Java fixture executions | 0 / 0 |
| Child processes | 90: 74 host Docker CLI + 11 sandbox controllers + 5 contained descendants |
| Java source projections | 0 |
| Non-Java data fixture projections | 2; existing boundary/controller probes, tmpfs only |
| Outbound network / shell / host mount calls | 0 / 0 / 0 |
| Host loopback listener sockets | 2; existing sandbox isolation observers, endpoints stayed quiet |
| SYNTH runtime / reflection lease consumptions | 0 / 0 |
| BANK executions / EXECUTOR.1R operational retries | 0 / 0 |
| Repository runtime writes / Apply actions | 0 / 0 |
| Artifact pulls / builds | 0 / 0 |

All stage cleanup checks passed, the temporary host workspace was removed, and zero phase containers remained. The controller stages verified descendant reaping, selector/pipe closure and empty work directories. No compilation ran and no Java class/source artifacts were created. Development pytest, fixture Git/Python commands and report exports are recorded separately from operational effects.

## Validation and preservation

| Selection | Baseline | After |
| --- | --- | --- |
| JAVA.1 / 1A / 1B / 1C and SANDBOX.1 / 2 pure subset | 498 passed, 1 failed, 5 deselected | 498 passed, 1 failed, 5 deselected |
| SYNTH.AUTH / reflection / lifecycles / historical EXECUTOR.1R | 801 passed | 801 passed |
| Current EXECUTOR.1R blocked retry unit regression | 46 passed | 46 passed |
| Authority / Apply / patch / path safety | 241 passed, 1 failed | 241 passed, 1 failed |
| Registry / picker / historical reversals | 292 passed, 12 failed | 292 passed, 12 failed |
| COMPAT.1 and original discovery success-gate controls | 67 passed | 67 passed, plus 10 JAVA.1D tests passed |
| Five historical fake-process reader tests | Existing pure subset excludes these | 5 passed separately with benign host Python threads |

The same twelve distinct pre-existing failures remain, with no new failure identities. No registry projection or reversal repinning was used. The safety guard rejected the same intentionally failing fixture command before a process could start in both baseline and after runs; this is development validation, with details preserved in JSON. The Python google.genai deprecation warning remains.

`benchmarks --check`: 54 checked, zero errors, no workload/agent execution. In-memory compilation, `git diff --check`, and additive-file whitespace checks pass. Exact command selections, failures and compilation counts are recorded in the JSON. The full repository suite was not run.

All 1,824 pre-existing tracked/nonignored files retain their exact bytes; eight already-missing paths remain missing. Historical Java/sandbox/synthetic owners, reports, compatibility audit, executor attempts, registry snapshots and reversal receipts are preserved. All four prior lifecycle/compatibility preservation manifests still match. No stash/reset/clean was used. Only this phase's replay, tests and three report artifacts were added.

Work stops at the measured backend-binding blocker. The frozen SANDBOX.2 API cannot support the requested discovery provenance without a separately authorized owner/API continuation.
