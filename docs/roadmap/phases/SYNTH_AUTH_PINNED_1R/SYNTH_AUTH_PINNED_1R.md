SYNTH.AUTH.PINNED.1R — authorization evidence

Final status: **SYNTH_AUTH_PINNED_1R_COMPLETE**. Reserved at 2026-10-11T02:48:18.046722+09:00 (Asia/Seoul).

Exactly one unchanged authorization-owner call and one public provider-owner call occurred. The original live authorization passed its public validator. This phase stopped at authorization; no execution lease was issued.

The exact scenario is synthetic.EXECUTOR.1R.decrement_3: boolean SyntheticStateBox.decrement(int), argument 3, field SyntheticStateBox.value:int. Expectations remain 10 / true / 7. They were not executed.

| Provider stage | Original status | Live authenticated objects |
|---|---|---|
| PINNED.1A | RUNTIME_JAVA_PINNED_1A_COMPLETE | True |
| PINNED.1B | RUNTIME_JAVA_PINNED_1B_COMPLETE | True |
| fresh_JAVA.1C | RUNTIME_JAVA_1_COMPLETE_WITH_WARNINGS | True |
| PINNED.1C_provider_root | RUNTIME_JAVA_PINNED_1C_COMPLETE | True |

The JAVA1C SANDBOX2 completed all 11 frozen stages. Its original report, descriptor and receipt were retained in process. Descriptor HMAC, receipt HMAC, public authentication, semantic eligibility, fingerprint/evidence consistency and cleanup all passed.

| Pre-ladder step | Outcome |
|---|---|
| report_initialization | COMPLETED |
| Docker_prefix_resolution | COMPLETED |
| private_config_path_construction | COMPLETED |
| policy_read_validation | COMPLETED |
| exact_image_inspect | COMPLETED |
| parsed_metadata | COMPLETED |
| metadata_validation | COMPLETED |
| temporary_workspace_creation | COMPLETED |
| seccomp_policy_write | COMPLETED |
| sentinel_write | COMPLETED |
| TCP_socket_construction | COMPLETED |
| UDP_socket_construction | COMPLETED |
| TCP_bind | COMPLETED |
| TCP_listen | COMPLETED |
| selected_port_retrieval | COMPLETED |
| UDP_bind | COMPLETED |
| first_ladder_mode_selection | COMPLETED |
| first_container_name_construction | COMPLETED |
| first_Docker_create_attempt | COMPLETED |

First failing step: none. All six frozen local socket operations succeeded. Image inspect returned linux/amd64, exact Id sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a, Config.Volumes=null.

The JAVA1C SANDBOX2 workspace was C:\Users\Admin\AppData\Local\Temp\runtime-sandbox2-x7x0vvm1; it was removed. Its policy and sentinel existed after their writes. Private Docker configuration paths were absent and were not symlinks.

167 original Docker control summaries retain argv, scope, capture status, exit code, bounded byte counts/hashes and process/pipe observations. Every observed provider child was reaped, every pipe closed and every reader stopped. The PINNED1A streamed stdout hash covers the bounded bytes consumed by its unchanged archive inspector.

Owner cleanup=true with zero remaining containers. The separate final read-only observation also found zero SANDBOX2, JAVA1C and PINNED1A containers. BIND uses the SANDBOX2 container prefix. Observer hooks and frozen owner namespaces were restored.

Only synthetic_scenario_authorized=true. Every runtime, lease, reflection, repository-write, Apply, network, host-mount, shell, arbitrary-command, executor and BANK authority remains false. All forbidden behavioral effect counts remain zero. JSON exports are reports and cannot restore live authority.

335 focused tests passed: 318 existing tests plus 17 observer tests. Benchmark --check passed 54 cases with zero errors. Registry/picker remained identical: 292 passing tests and the same seven preexisting failures. No full-suite pass is claimed. Post-live artifact checks passed without any provider issuance.

All 359 frozen source bindings, 2,246 preserved files, the original blocked attempt and all prior diagnostic/history pins remained unchanged. No repository source was written. The new runner remains outside the repository.

Runner SHA256: 7dea3b744a62531d90da5f471a12a48b32932a3c926ab2d88196ea1bc2e2a20c
Original frozen runner SHA256: 73ac65320825f3f32726526bcb5f2aa492887ef496b06d086932903b47cfc440
Scenario source SHA256: 813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302
Authorization ID: aebe68932b8a50000f65bf6587aceb4c62a2a71f5d0f0110df3de6244f1e3669
Authorization fingerprint: 8bdd69b2fe63ba4d8291a47d223d6472fb2295d228fc8df36b04db0d97241228

A preparatory launch stopped before reservation/provider effects when final pure-test results changed a validation checksum. The completed results were bound again before the sole live attempt. No failed provider attempt was retried.

Complete retained observations are in SYNTH_AUTH_PINNED_1R_REPORT.json. SYNTH_AUTH_PINNED_1R_SUMMARY.json includes exact hashes, scenario/provider binding, scope, PINNED1A nested cleanup and validation results.
