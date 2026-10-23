# RUNTIME.SANDBOX.2.NESTED.CONTEXT.DIAG.1

**UNRESOLVED**. Historical nested root cause unresolved.

The static and pure audit found surviving process context differences, but no exact active denial mechanism that explains the historical post-image, pre-create failure. The lost SANDBOX.2 report and first failing statement prevent causal attribution. This phase stops here.

The exact runner is `scripts/replay_synth_auth_pinned1.py`, SHA256 `73ac65320825f3f32726526bcb5f2aa492887ef496b06d086932903b47cfc440`, matching its retained preoperational source binding. The original Codex launch record directly invoked `python -B scripts/replay_synth_auth_pinned1.py` with host access. Session and turn context record this repository as cwd; no workdir override, environment assignment, or validation wrapper appears in the launch. Selected original records and their line hashes are retained in [launch provenance](historical_launch_provenance.json).

`tempfile.tempdir` and consequently `tempfile.gettempdir()` were the absolute SYNTH phase directory for the entire authorization/provider call. Runner line 61 sets the override; line 102 restores it after issuance returns. Historical TMP, TEMP, TMPDIR and the previous cached tempdir were not retained. The explicit global override bypasses their selection. No pytest basetemp context was active in the directly launched live runner.

Both the absent Docker config path (`candidate_runtime_sandbox.py:371`) and `TemporaryDirectory(prefix='runtime-sandbox2-')` (`thread_compatible_runtime_sandbox.py:335`) use that same root. The successful standalone diagnostic used normal Windows Temp. The config path itself is not a demonstrated cause: image inspection succeeded, and the earlier BIND SANDBOX.2 replay in the same historical issuance completed all 11 stages, removed its workspace, and verified cleanup while the phase-local override remained active. This excludes an unconditional root-wide write denial or socket prohibition throughout the attempt.

The historical root was present and allowed earlier workspace writes. Its exact later ACL, symlink, write-denial policy and cleanup state were not recorded. Current read-only metadata shows an ordinary directory with Modify ACL entries; current metadata cannot establish historical permissions. The exact live source contains no early cleanup of the phase root. [Current path and tempfile observations](historical_path_current_observation.json) preserve this distinction.

| Context / owner | Active at JAVA.1C SANDBOX.2 boundary | Lifetime / affected step | Classification |
| --- | --- | --- | --- |
| phase_local_temp_root | Yes | Whole authorization/provider call; restored only in outer finally after JAVA1C returns; private_config_path_derivation, TemporaryDirectory, policy_and_sentinel_writes | OBSERVED_NONCAUSAL_DIFFERENCE |
| provider_return_frame_profiler | Yes | sys.setprofile(observer) around runtime.verify(), including JAVA1C and SANDBOX2; Python_return_events, bounded_process_return_accounting | OBSERVED_NONCAUSAL_DIFFERENCE |
| PINNED1B_transport_and_replay_observers | No | patch.object only around upstream backend binding; exits before target inspection and provider JAVA1C call; earlier_upstream_bounded_process_and_SANDBOX2_only | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| BIND_transport_observer | No | Scoped transport patch during upstream BIND replay; earlier_upstream_transport_only | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| successful_retry_private_config_tracer | No | Different successful retry runner only; not entered by blocked SYNTH runner; No direct pre-ladder dependency | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| validation_only_audit_guards | No | Separate pure validation worker processes; direct live launch starts a fresh Python interpreter; No direct pre-ladder dependency | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| runner_import_path_and_bytecode_flag | Yes | Entire fresh process; module_resolution, implicit_bytecode_output | OBSERVED_NONCAUSAL_DIFFERENCE |
| negative_authentication_controls | No | After successful authorization only; branch skipped in blocked attempt; No direct pre-ladder dependency | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| JAVA1B_recovered_controller_binding | No | Scoped JAVA1B replay context replaces JAVA_PROBE_SOURCE/_invoke_java and restores in finally; No direct pre-ladder dependency | NOT_ACTIVE_AT_FAILURE_BOUNDARY |
| provider_registry_globals | Yes | Process-local attempts/origins and authenticated upstream registries persist; No direct pre-ladder dependency | OBSERVED_NONCAUSAL_DIFFERENCE |
| unretained_parent_or_late_host_state | Unknown | Unknown; metadata_parse, workspace_creation_and_writes, TCP_UDP_socket_setup | INSUFFICIENT_EVIDENCE |

The provider's `sys.setprofile` return-frame observer remains installed across `runtime.verify()` and SANDBOX.2. Its callback reads selected return values, arguments and locals for accounting; it does not install an audit hook, deny sockets or writes, or replace owner values. It is shared with the successful PINNED.1C retry. Direct denial by this callback is excluded; historical timing or allocation effects are unmeasured. Pure controls execute the exact helper with inert stand-ins and verify observation plus restoration on success and exception.

PINNED.1B and BIND transport/replay patches finish before JAVA.1C. Their lexical lifetime makes them NOT_ACTIVE_AT_FAILURE_BOUNDARY. The successful retry's private-config tracer is absent from the blocked runner. Negative authentication mutations run only after successful issuance and were skipped. Provider registries survive but SANDBOX.2 pre-ladder setup does not read them. Runner import-path insertion and bytecode suppression survive and expose no post-image denial mechanism.

No Python audit registration, socket constructor/bind/listen patch, Popen/run patch or shutil.which patch was found on the exact retained live path. Guards in separate validation processes are not inherited into the fresh live Python interpreter. No system/thread trace, thread profile or monitoring mutation was found there; inherited startup and native policy were not recorded. The separate strict-resolution sandbox probe does not establish a denial in the host-capable historical launch.

The retained JAVA.1C-period Docker controls are successful image inspection followed by two successful cleanup listings; creates and starts are zero at the failed boundary. A global subprocess prohibition contradicts this evidence. There is no further subprocess between image inspection and SANDBOX.2 workspace/socket setup. Parsed metadata eligibility, workspace creation, file writes, TCP/UDP construction, TCP bind/listen and UDP bind remain possible failure steps, with no retained first-failure evidence. No socket rejection rule is proven active there. JAVA.1C's generic not_authenticated label does not demonstrate HMAC failure.

Pure temp controls use the exact historical override statement and exact frozen pre-socket workspace subtree, rebound only to a new phase-owned scratch root. They confirm shared config/workspace root selection, successful policy/sentinel writes and cleanup, without Docker or socket operations. This proves the semantic connection, not the historical root cause.

| Validation | Result |
| --- | --- |
| context-audit | 11 passed; PASS |
| pytest | 230 passed; PASS |
| auth-matrix | 57 passed; PASS |
| auth-artifacts | PASS |
| context-contracts | 59 passed; PASS |
| historical-blocked | PASS |
| benchmark | PASS |
| Registry/picker tests | Identical baseline and after: 292 passed, 7 existing failures |
| Registry/picker reports | Identical deterministic baseline and after |
| In-memory compilation, JSON, whitespace, git diff --check | PASS |
| Historical byte preservation | 2185 files unchanged; prior frozen pins also match |

Completed guarded validation workers report zero forbidden process, socket and historical-write attempts. Frozen pure contracts use controlled fixtures; no live provider graph or operational owner was issued. One exact isolated Python authentication-domain control child is retained separately from operational effects. All 21 inventoried frozen project sources also compile in memory without import, execution or bytecode output.

SANDBOX.2 source changed: **false**. JAVA.1C source changed: **false**. SYNTH retried: **false**. Remediation implemented: **false**. Existing registry, reversal artifacts, blocked attempt, diagnostics, lifecycle/reflection owners and EXECUTOR history are byte preserved. Output is confined to this new phase; no stash, reset, clean or historical repinning occurred.

The initial broad fixture-contract attempt reached its 300-second limit before a final worker summary. It is retained as a partial attempt, with no full-suite pass claimed. The completed contract result above covers the selected context helpers and pure authorization/replay checks; exact test selections are in validation_summary.json. The timed-out process was killed and reaped. Its audit guard prevented operational effects, but a final attempted-effect counter snapshot was unavailable. [broad_contract_timeout.json](broad_contract_timeout.json)

| Operational effect | Count |
| --- | --- |
| Apply | 0 |
| BANK | 0 |
| Docker | 0 |
| EXECUTOR.1R | 0 |
| JAVA1C | 0 |
| PINNED1A_export | 0 |
| PINNED1B | 0 |
| PINNED1C | 0 |
| SANDBOX2_issuance | 0 |
| SYNTH_retry | 0 |
| SyntheticStateBox | 0 |
| execution_leases | 0 |
| provider_root | 0 |
| reflection | 0 |

Recommended next slice: one separately authorized instrumented fresh SYNTH.AUTH.PINNED.1 authorization retry. Retain the full fresh SANDBOX.2 report, original pair observations/authentication in the issuing process, parsed metadata, private-config absence, ordered pre-ladder entries/completions/first exception, workspace and socket outcomes, exact process-context ledger and owner cleanup. Exported reports remain report-only. Bind exact source hashes, use narrow observation without owner replacement, restore instrumentation and preserve failure evidence without exposing secrets or persisting capabilities. Stop at the authorization boundary. No retry is run in this phase.

[Full typed report](RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1_REPORT.json) · [Source inventory](source_context_inventory.json) · [Validation](validation_summary.json) · [Preservation baseline](preservation_baseline.json)

Reproduce pure checks only: `python -B docs/roadmap/phases/RUNTIME_SANDBOX_2_NESTED_CONTEXT_DIAG_1/validation.py validate`. Never run historical live or validation scripts directly; historical validation scripts write their own evidence. Regenerate this joined report with this phase's `finalize_report.py`, then run `validation.py source-checks` and `validation.py preservation`.
