# DATA.UNDO.1 — Repository-Scoped Backup Identity & Exact Undo Binding

DATA-01 is closed for the audited automated web Undo path. A production-format
artifact from repository A is rejected by HTTP Undo in repository B, with the
entire test filesystem unchanged. The original 2026-09-11 audit remains intact.
This is one Track-B remediation phase in the existing HARDEN registry track.

1. **Exact files changed.** Eight existing files were edited and seven files
   added. Existing: `web/routes/patch_routes.py`, `web/app.py`,
   `web/templates/index.html`, `core/phase_registry.py`,
   `docs/roadmap/phase_registry.json`, `tests/test_phase_registry.py`,
   `tests/test_phase_picker.py`, `tests/test_sec_ui1.py`. Added:
   `core/undo_backup.py`, `tests/test_data_undo1.py`,
   `tests/_data_undo1_maintenance.py`,
   `tests/fixtures/data_undo1_frozen_boundaries.json`,
   `tests/fixtures/data_undo1_reversal.json`,
   `tests/fixtures/data_undo1_completion.json`, and this document.
2. **Old identity.** `/apply_patch` wrote UTF-8 text backups beneath a shared
   `web/backups` directory, named from the relative path with separators replaced
   by underscores plus a timestamp. No repository, transaction or version binding
   existed; text reads also normalized original newlines.
3. **Old lookup.** `/undo_patch` built that same prefix from the requested file,
   sorted all matching `.bak` files, restored the first one and immediately
   deleted it. The recorded entry route reproduces A-to-B restoration and
   deletion in the red test, without a provider or Apply invocation.
4. **New owner and bounded audit.** `core.undo_backup.UndoBackupStore` owns the
   durable artifact contract. The sole producer of this shared web format is
   `web.routes.patch_routes.apply_patch`; its sole restore consumer is
   `web.app.undo_patch`. The browser `undoPatch()` is the direct caller.
   `web.patch_helpers.backup_key_for_path` remains a legacy compatibility helper
   with no production backup producer/consumer references. Executor-local
   `patching.patch_engine.backup_file/restore_backup/cleanup_backup` uses the
   different adjacent `file.ext.bak` rollback format and remains untouched.
   Patch-plan rollback uses its existing in-memory byte snapshots; Dream Apply
   and plan Apply never produced this durable web format and were not migrated.
5. **Durable typed schema.** Frozen `BackupArtifact` contains `backup_id`,
   `schema_version=1`, `canonical_repository_identity`,
   `repository_relative_path`, `transaction_id`, `before_exists`,
   `before_sha256`, `backup_bytes_sha256`, `expected_post_exists`, and
   `expected_post_sha256`. Types, schema, digest syntax and relationships are
   validated. No model claims, UI state or candidate-confidence fields occur.
6. **Repository identity source.** Existing
   `core.repository_identity.build_repository_identity` supplies the canonical
   root and authoritative `repository_id`. No new repository hash or identity
   scheme was added. Its content-independent, zero-walk contract is preserved.
7. **Target identity.** Existing `evaluate_patch_safety`, physical `Path.resolve`
   containment, `relative_to` and the existing Windows `normcase` policy bind
   the physical repository-relative target. Stored paths use POSIX separators;
   Windows case and separator aliases compare consistently. Request paths are
   cross-checks, never artifact selectors. Drive-qualified inputs are rejected,
   including Windows forms when checked on another platform.
8. **Transaction identity.** This direct Executor boundary has no authoritative
   per-mutation run receipt ID to reuse. Each before snapshot therefore receives
   one server-generated UUID4 transaction, distinct even for identical bytes and
   target names. Client transaction values are optional cross-checks only.
9. **Opaque backup ID.** SHA-256 of the canonical immutable metadata, excluding
   `backup_id` itself and including the random transaction, yields a 64-character
   opaque ID. This also commits the issued ID to every metadata field: changing
   any field under that ID fails validation. It is not a filesystem path or a
   separate repository identity. Possession alone never bypasses server checks.
10. **Before state.** Exact `read_bytes()` data is durably saved before Executor
    runs, with its byte hash. Incomplete or failed Apply snapshots stay as
    `pending-<transaction>.bak` for manual recovery, never as Undo authority.
11. **Expected post state.** Only a successful completed existing-file mutation
    publishes metadata, using the resulting target's exact byte hash. Publication
    failure reports `backup_error` and no backup ID while preserving the
    executor's actual success/rollback result. Failure to save the before bytes
    refuses Apply before mutation. Created-file Undo was unsupported and remains
    unsupported; no authority is published for a previously absent target.
12. **Backup-byte integrity.** Publication rehashes stored before bytes; Undo
    rehashes them again against `backup_bytes_sha256`, which must also equal
    `before_sha256`. Corrupt or missing bytes fail closed.
13. **Storage namespace.** `web/backups/v1/<backup_id>.json` and
    `<backup_id>.bak` identify one artifact. The random transaction and metadata
    commitment isolate repositories, target directories and repeated mutations.
    Copying this directory elsewhere cannot change the metadata repository.
    The unsafe shared seven-backup prefix cleanup was removed. No replacement
    retention rule or background janitor was introduced.
14. **Producer receipt.** Apply returns `backup_id` and
    `undo_backup={backup_id, transaction_id}`; the latter also enters the existing
    serialized `patch` payload and existing session persistence. Incoming
    `undo_backup` is discarded before producing an Apply response. No executor
    receipt, candidate fingerprint or execution-authority decision was changed.
15. **Request contract.** POST `/undo_patch` carries existing `repo_path` plus
    exact `backup_id`, and optionally `file` and `transaction_id` cross-checks.
    The browser carries both cross-checks. Client repository IDs and hashes are
    not accepted as authoritative metadata.
16. **Exact lookup.** A strict ID format permits only exact file opens. Metadata
    must reproduce the requested ID before its bindings are used. No directory
    listing, repository inventory, filename prefix selection or latest fallback
    occurs. Tests prohibit `glob`, `rglob` and `os.walk` in production and Undo.
17. **Repository mismatch.** `backup_repo_mismatch`, `success:false`; neither
    target nor artifact changes. This applies even after copying the artifact
    store into a directory named for the other repository.
18. **Target mismatch.** `backup_target_mismatch`, `success:false`; same basename
    in another directory grants no authority. Retargeted physical paths are also
    rejected. Transaction cross-check mismatch uses
    `backup_transaction_mismatch`.
19. **Stale target.** Missing/non-file targets or a different current byte hash
    return `stale_target`. The expected post-version must match before restore.
20. **User edit.** A later manual edit is preserved along with the backup. No
    best-effort overwrite is attempted. The guarantee covers edits visible at
    the version check; the concurrency boundary is described below.
21. **Tampered backup.** `backup_integrity_failed`; target bytes and the corrupt
    artifact are retained, with structured JSON.
22. **Tampered metadata.** Changing repository, relative path, transaction,
    before/post hash, existence flags, schema or document shape under an issued
    ID returns `backup_metadata_invalid`. Metadata validation and path checks
    are both enforced; even an internally consistent newly seeded record with
    a traversal path cannot escape the repository.
23. **Traversal.** Relative traversal using either separator, absolute POSIX
    paths, Windows drive paths/drive-relative paths and UNC paths are rejected.
    Both request and metadata paths are tested; backup IDs cannot carry paths.
24. **Symlinks/reparse points.** The existing patch gate follows links that
    resolve inside the canonical repository and rejects escape. Undo reuses
    that policy. Windows junction tests prove internal aliases work, external
    aliases fail, and redirecting the recorded physical target outside fails.
    File-symlink creation needs a privilege unavailable on this host; the focused
    proof uses real directory junctions without skips.
25. **Two repositories.** Production artifacts for `A/app.py` and `B/app.py` have
    distinct IDs and repository metadata. Each rejects the other's artifact;
    each legitimate Undo restores only its own before bytes. The primary
    rejected cross-repository request preserves every file under the fixture.
26. **Two transactions.** B1 describes v0→v1, B2 describes v1→v2. B1 rejects v2
    without consuming anything. B2 restores v1; then the still-valid B1 restores
    v0. Transactions and IDs remain distinct.
27. **Successful Undo.** The result includes `success:true`, `backup_id`,
    `transaction_id` and independently verified `restored_sha256`. The real
    Apply/session/HTTP Undo integration restores the exact original bytes.
28. **Byte fidelity.** Empty files, CRLF, LF, terminal-newline absence, Korean and
    accented UTF-8, and raw non-UTF-8/NUL bytes all restore exactly. Restore does
    not decode or re-encode the backup.
29. **Post-restore verification.** A new read/hash of the final target must equal
    `before_sha256`. Injected incorrect final bytes produce
    `backup_restore_verification_failed` and retain the artifact. Existing
    atomic helpers are specialized text/JSON writers; this owner adds one
    bounded binary helper using same-directory temp/write/fsync/`os.replace`,
    preserving the target mode. An injected replacement failure leaves the old
    complete target, preserves the backup and cleans the temporary file.
30. **Consumption timing.** Only after final verification is the immutable JSON
    atomically renamed to `<backup_id>.consumed.json`, then backup bytes are
    deleted. A byte-cleanup failure cannot reactivate consumed authority. All
    failures before verified restore retain the backup. If recording consumption
    fails, the API reports failure and retains the bytes; it does not claim the
    already-performed restore was rolled back.
31. **Double Undo.** The durable consumption marker yields deterministic
    `backup_already_consumed` without mutation, including two overlapping local
    requests and reuse after reload. One-shot behavior is explicit.
32. **Legacy backups.** Old unbound `.bak` files remain untouched for manual
    recovery. Missing/pathlike IDs return `backup_id_required`; a syntactically
    valid unknown ID returns `backup_not_found`. Messages explicitly state that
    legacy backups are not trusted. No location-based migration is attempted.
33. **Structured errors.** Identity/version/integrity errors return JSON with
    `success:false`, `code`, and `message`. Filesystem errors use
    `backup_io_failed`. Invalid JSON/types and missing request fields fail
    closed instead of reaching an HTML 500 response.
34. **Frontend delta.** Six changed/added transport lines in `undoPatch()` read
    `parsed.undo_backup` and pass its two IDs through `URLSearchParams`. Existing
    Apply handling already updates the serialized patch state; existing session
    persistence already saves it. The actual handler sends the persisted receipt
    identically after two browser loads.
35. **UX-03 delta.** Zero. The existing handler still sets `last_action:"undone"`
    after `success:false`; a browser test explicitly preserves this deferred
    behavior. No UI redesign or state-management rewrite was included.
36. **EXEC-01 delta.** Zero. Patch-plan prevalidation, partial-write behavior and
    executor transaction execution remain unchanged.
37. **AUTH-01 delta.** Zero. Dream review/apply selection, candidate identity and
    authorization semantics remain unchanged. Backup publication failure does
    not rewrite execution success to imply a rollback.
38. **DATA-02 delta.** Zero. Generic executor rollback restore-failure truthfulness
    and validation-side-effect semantics remain untouched.
39. **SEC.UI.1 delta.** Zero rendering semantics. DOMPurify assets/policy,
    `safe_content.js`, Evidence and Critique handlers are unchanged. Two
    historical boundary tests now reverse DATA.UNDO.1's exact maintenance hunks
    in memory before checking their original immutable fixtures. All 30 security
    tests pass, including browser integration.
40. **Track-A delta.** Zero semantics. PATCH.AUTHOR, PATCH.MINIMAL, INDENT.*, probes,
    candidate verification, answer coherence, targeted validation and execution
    authority are preserved. Production executor and patching files retain their
    entry SHA-256. No T6 Round 11 was started.
41. **Persistence/reload.** A fresh Python process loads and consumes an artifact
    created by another process. Actual Apply persists the exact receipt into the
    existing session; a later HTTP request uses that disk-loaded receipt. Browser
    reload transport is checked independently. No process-local map is the only
    authority.
42. **Traversal delta.** Zero new repository walks or broad backup searches. The
    backup flow touches the canonical root and exact named target/artifact paths.
    Existing validation command selection is unchanged and outside the measured
    metadata overhead.
43. **Model/network delta.** Zero live provider calls and zero external network
    added or required. Regression tests use temporary repositories, direct
    fixtures and existing controlled provider adapters. Browser transport requests
    are intercepted locally; SEC.UI.1's existing local test controls remain.
44. **Performance.** Seven measured samples after two warmups on Windows, using
    16 KiB and 256 KiB files, are recorded below. Full Undo medians were 3.4934 ms
    and 3.9595 ms. These are local warm measurements, not worst-case guarantees.
45. **Focused tests.** 50 passed, zero failures/errors/skips, 12.18 seconds.
    Historical red reproduction, current green HTTP regression, full identity,
    freshness, integrity, path, byte, failure, lock, persistence, transport and
    maintenance checks are included.
46. **Adjacent/broad tests.** 653 passed, two existing platform skips, 53.15 seconds
    across 24 modules. Coverage includes patch/plan routes, HTTP workflows,
    mutation auth/surface, human Apply, path safety, byte fidelity, atomicity,
    web UI/history compatibility, canonical identity and registry/picker tests.
    The skips are POSIX case policy on Windows and unavailable symlink-creation
    privilege in the existing identity suite. SEC.UI.1 separately: 30 passed,
    zero skips, 68.85 seconds. Total: 733 passed, two skips. The complete repository
    test suite was not run; no such claim is made. Existing Google SDK deprecation
    warning only.
47. **Governance/build.** Exactly one new phase, DATA.UNDO.1, in HARDEN. Registry:
    182 phases, 178 complete/history, 11 HARDEN; picker remains DOGFOOD.1B.
    Registry/picker CLIs, compileall, all 54 `benchmarks --check` fixtures and
    `git diff --check` passed. Git emitted existing line-ending normalization
    notices, not diff errors.
48. **Frozen/concurrent-work attribution.** 1,432 entry files were hashed before
    edits. Exactly eight entry files changed; their recorded, unique hunks reverse
    to the entry SHA-256 in memory. Other entry files, original audit artifacts
    and prior historical fixtures remain byte-identical. Seven new deliverables
    belong to this phase. No historical production bytes were restored to meet
    a pin; no stash/reset/clean was used. Sub-agents were not used.
49. **Remaining Track-B findings.** EXEC-01, AUTH-01, DATA-02, SEC-02, UX-01 through
    UX-06 remain open and were not begun. SEC-01 remains closed by SEC.UI.1.
    Created-file Undo and backup retention are unchanged in supported scope or
    deferred as described above, not new remediation phases.
50. **DATA-01 closure.** Yes, for the measured exact automated Undo boundary:
    canonical repository, physical relative target, distinct transaction,
    immutable metadata, stored-byte integrity and expected current version are
    verified before atomic byte restore; final bytes are verified before
    consumption. The original cross-repository overwrite/deletion is rejected.

The local serialization boundary is deliberately small. No suitable existing
web file-mutation lock was present, so one `RLock` covers the durable web Apply
snapshot/mutation/publication and the entire Undo validation/restore/verification/
consumption operation. It serializes those operations within one server process.
External editors, independent server processes and the frozen other mutation
paths do not acquire it; this phase does not promise an OS-wide compare-and-swap
against such concurrent writers. Normal later edits present at verification are
rejected. A crash between restore and consumption can leave a retained artifact
whose expected post-state no longer matches; no successful response is fabricated.

| Operation, median milliseconds | 16 KiB | 256 KiB |
| --- | ---: | ---: |
| Durable before snapshot, including hash | 2.2025 | 2.6250 |
| Backup byte SHA-256 alone | 0.0099 | 0.1330 |
| Metadata creation/publication, including post read/hash | 3.4079 | 2.7737 |
| Exact metadata lookup and validation | 0.2377 | 0.2318 |
| Current target read/hash | 0.0826 | 0.2420 |
| Atomic byte replacement plus final read/hash | 1.8217 | 1.3848 |
| Full production Undo, including checks and consumption | 3.4934 | 3.9595 |

Columns overlap by design and should not be summed. Full Undo executes the
production owner. Byte hashing is measured separately from file I/O, and atomic
replacement includes flushing the temporary file. Raw timings and exact test
case results are retained in `tests/fixtures/data_undo1_completion.json`.

| Explicit question | Answer |
| --- | --- |
| Can A's backup restore into canonical repository B? | No; repository mismatch rejects before mutation or consumption. |
| Can identical relative paths collide across repositories? | No; repository metadata and unique opaque artifact IDs isolate them. |
| Can two mutations accidentally share backup authority? | No; each has a distinct random transaction committed into its ID. |
| Can Undo overwrite a file changed after its mutation? | A changed current hash is rejected; external concurrent-writer limits are stated above. |
| Can a tampered backup be restored? | No; byte integrity and metadata commitment are checked. |
| Is the backup deleted when Undo fails? | No; failures before verified success retain the backup. |
| Does successful Undo verify final bytes/hash? | Yes, with an independent final read/hash. |
| Are legacy unbound backups automatically trusted? | No; automated restore is refused and files retained. |
| Does Undo still select latest by filename/path? | No; only exact issued artifact lookup. |
| Were EXEC-01 semantics changed? | No. |
| Were Dream Apply semantics changed? | No. |
| Was generic rollback truthfulness changed? | No. |
| Was SEC.UI.1 changed? | No rendering/policy change; only test maintenance for later hunks. |
| Was Track A changed? | No semantic changes. |
| Were live provider calls added? | No. |

Reproduction uses the existing local test dependencies with database and embedding
providers disabled and `WEB_AUTH_TOKEN` empty. Run `python -m pytest
tests/test_data_undo1.py -q`; adjacent module names and original test results are
in the completion fixture. No package installation or external service is needed
on this configured host. Source hashes, rather than the already-dirty Git base,
define phase attribution.
