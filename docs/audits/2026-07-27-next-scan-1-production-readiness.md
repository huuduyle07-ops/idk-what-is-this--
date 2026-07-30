# NEXT.SCAN.1 — Production Readiness & Capability Gap Audit

- **Date:** 2026-07-27
- **Scope:** read-only audit + one characterization test (`tests/test_index_production_readiness_audit.py`). No production files changed.
- **Status:** `NEXT_SCAN_1_COMPLETE_WITH_WARNINGS` (see §13 for the warnings)
- **JSON companion:** `.agent/audits/2026-07-27-next-scan-1-production-readiness.json`

---

## 1. Executive verdict

**Production indexing is not incremental at all.** The entire INDEX.1B/INDEX.1C stack — persistent manifest, delta classification, and execution planner — is fully built, fully tested (135 focused tests green), and **wired into nothing**. A repo-wide grep for `load_repository_manifest | save_repository_manifest | inspect_repository_delta | build_index_execution_plan` finds callers only in `tests/`. `core/indexer.py::index_repository` unconditionally re-reads, re-parses (twice), re-embeds, and re-replaces every file on every run — and `web/runner.py:485` triggers that on **every project-input web request**.

Worse than the missing wiring, the audit found three defects that make naive wiring dangerous:

1. **Silent partial persistence (H1).** One DB or embedding failure mid-run flips persistence off for all remaining files, skips reconciliation, and still returns a success-shaped result. If a manifest were saved after such a run, the next delta run would classify unpersisted files as `unchanged` and never index them — a permanently poisoned baseline.
2. **Unstable repository identity (H2/H8).** `build_project_tag` fingerprints the repo with an **unfiltered** `os.walk` (its `IGNORE_DIRS` set is dead code) capped at 5,000 files — on any real repo the cap is hit inside `.git/objects`, so the tag can drift between runs. Three incompatible identity schemes coexist (`project_tag`, `storage_key`, `index_scope`).
3. **Traversal explosion (H3).** One `index_repository()` call performs ~7 full repo traversals and 4 full file-content read passes; a full web request performs ~13. `config.py::get_agent_dir` re-walks the repo on each of its 22 call sites.

**Recommendation:** do *not* start Production Delta Execution Wiring directly. The evidence ranks a small, high-leverage prerequisite phase first: **INDEX.1D — Repository Identity Unification & Trusted Completion** (stable path-derived identity + honest `persistence_ok` result + credential redaction), then wire the delta path on top of it. TDD/Test Author is genuinely promising (execution substrate is strong) but has three hard prerequisites and should stay one macro-phase behind indexing.

---

## 2. Current production indexing truth

Answers to the ten mandated questions. Confidence: **high** — each is proven both statically (file:line) and dynamically (counters in `tests/test_index_production_readiness_audit.py`, all 4 tests passing).

| # | Question | Answer | Evidence |
|---|---|---|---|
| 1 | Is the persistent manifest used by production indexing? | **No.** Zero production imports of `core/index_manifest.py`. | grep (production-only) hits: definitions + `core/index_execution.py:6` only; test counter `manifest_loads == 0` |
| 2 | Is the execution planner used by production? | **No.** `build_index_execution_plan` has zero production callers. | grep; test counter `plans_built == 0` |
| 3 | Are `added`/`modified`/`deleted`/`unchanged` dispatched differently? | **No.** There is no delta concept in `index_repository`; every discovered file takes the identical full path. | `core/indexer.py:92-238` (single undifferentiated loop) |
| 4 | Does an unchanged file still get read? | **Yes — 3× per run** (indexer, code-DNA, graph builder), 4× counting phantom-limb. | `core/indexer.py:111`; `core/code_dna.py:167`; `graph/builder.py:63` |
| 5 | Does an unchanged file still get parsed? | **Yes — 2× per run** (indexer + graph builder both call `parse_code_with_treesitter`). | `core/indexer.py:120`; `graph/builder.py:64`; counters `files_parsed == graph_files_parsed == N` on run B |
| 6 | Does an unchanged file still generate embeddings? | **Yes**, when DB is available and `INDEX_USE_EMBEDDINGS` isn't false. Only a per-process in-memory text cache (`core/retriever.py:241,300`) softens this — useless across processes/runs. | `core/indexer.py:187-209`; run-B counter `embeddings_generated == N` |
| 7 | Does an unchanged file still call `replace_code_index_for_file()`? | **Yes**, every file, every run — delete+insert inside one transaction per file. | `core/indexer.py:210-215`; run-B counter `db_replacements == N` |
| 8 | Are deleted files handled directly or only by final reconciliation? | **Only by end-of-run `reconcile_code_index_scope`.** `delete_code_index_for_file` (`database/memory.py:1384`) has no production caller. | `core/indexer.py:246-255`; run-D counters `db_deletions == 0`, reconciliation receives survivor set |
| 9 | When is the new manifest written? | **Never.** `save_repository_manifest` is unreachable from production. | grep; test asserts `manifest_saves == 0` |
| 10 | Can a partial failure advance the manifest into a false completed state? | **Today: no** (no manifest is written). **Under naive future wiring: yes, catastrophically** — `index_repository` has no notion of "fully persisted"; after the first replacement failure it silently skips persistence for all remaining files yet finishes "successfully" (`core/indexer.py:217-230`). A manifest saved at that point would mark unpersisted files as indexed forever. | `core/indexer.py:217-230, 320-333` (no `persistence_ok` field) |

---

## 3. Production call-chain map

Entrypoints: `main.py:49` (`--index`), `cli/interactive.py:147`, `web/runner.py:485` (per project request). All converge on `core/indexer.py:35 index_repository(repo_path, project_tag)`.

```text
runtime caller (main.py:49 | cli/interactive.py:147 | web/runner.py:485)
→ repository identity      build_project_tag (core/project_tag.py) — UNFILTERED WALK, drift-prone
                           build_code_index_scope (core/repository_identity.py) — pure, stable
→ scan (×2)                inspect_repo_inventory + iter_repo_files (core/repo_librarian.py) — policy-pruned walks
→ manifest                 ✗ NOT WIRED (core/index_manifest.py — test-only)
→ delta                    ✗ NOT WIRED (inspect_repository_delta — test-only)
→ planner                  ✗ NOT WIRED (core/index_execution.py — test-only)
→ read/parse (ALL files)   extract_file_text + parse_code_with_treesitter (core/indexer.py:111,120)
→ embedding (ALL files)    get_embedding (core/retriever.py:296) — zeros(384) if embeddings disabled
→ DB mutation (ALL files)  replace_code_index_for_file (database/memory.py:1312) — atomic per file, scope-required
→ reconciliation           reconcile_code_index_scope (database/memory.py:1430) — end-of-run stale-row sweep
→ DNA                      compute_dna (core/code_dna.py:159) — SEPARATE rglob + re-read, own blacklist
→ phantom limb             scan_phantom_limb (in-memory summaries) + report write
→ graph/map                build_graph_from_repo (graph/builder.py:63-64) — RE-READS + RE-PARSES all files
→ manifest completion      ✗ NEVER WRITTEN
```

Per-stage detail:

| Stage | Module/function | Wired? | Pure/mutating | Unchanged files reach it? | Failure behavior | Tests | Confidence |
|---|---|---|---|---|---|---|---|
| Repo identity (tag) | `core/project_tag.py:31-68` | yes | read-only FS (full walk) | n/a | silent drift possible (cap 5000 files, dead `IGNORE_DIRS`) | none | high |
| Repo identity (scope) | `core/repository_identity.py:60` | yes | pure | n/a | raises on non-dir | indirect (`test_index_scope_wiring`) | high |
| Inventory scan | `core/repo_librarian.py:220` | yes | read-only | yes | raises RuntimeError on 0 indexable | `test_repo_ignore_policy` (partial) | high |
| File iteration | `core/repo_librarian.py:113` | yes | read-only | yes | generator; silent on missing dir | partial | high |
| Manifest load/save | `core/index_manifest.py:67,96` | **no** | read/write `.agent` (atomic tmp+`os.replace`) | n/a | returns `None` on corrupt load; atomic save | `test_index_manifest.py` (green) | high |
| Delta | `core/index_manifest.py:323` | **no** | read-only | would classify them `unchanged` | raises on wrong repo/version | `test_index_manifest.py` | high |
| Planner | `core/index_execution.py:44` | **no** | pure | plans `REUSE` for them | pure; `blocked_reason` paths | `test_index_execution_plan.py` | high |
| Read | `core/indexer.py:111` | yes | read-only | **yes** | per-file try/except → `ERR`, continue | none direct | high |
| Parse | `core/indexer.py:120` | yes | pure | **yes** | fallback chain: text units → file-level unit | wiring tests (stubbed) | high |
| Embedding | `core/indexer.py:193` / `core/retriever.py:296` | yes | pure (in-proc cache) | **yes** | raise → caught → **disables persistence for rest of run** | none | high |
| DB replace | `database/memory.py:1312` | yes | mutating, scoped, transactional | **yes** | rollback + raise → caught at `indexer.py:217` → `db_available=False` latch | `test_code_index_transactions.py` | high |
| Per-file delete | `database/memory.py:1384` | **no production caller** | mutating, scoped | n/a | rollback + raise | `test_code_index_transactions.py` | high |
| Reconciliation | `database/memory.py:1430` | yes (once, end of run) | mutating, scoped | n/a | caught, recorded in result | `test_index_scope_wiring.py` | high |
| DNA | `core/code_dna.py:129` | yes | read-only + `.agent` write | **yes (re-read)** | swallows per-file read errors | none | high |
| Graph/map | `graph/builder.py:30`, `graph/project_map.py` | yes | read-only + `.agent` write | **yes (re-read + re-parse)** | caught → degraded map silently overwrites good map | `test_dependency_wiring.py` (stubbed) | high |
| Manifest completion | — | **never** | — | — | — | new characterization test | high |

---

## 4. Four-run behavior table

Method: `tests/test_index_production_readiness_audit.py` — temp repo (3 small `.py` files), counting fakes for parse/embedding/DB/reconciliation/scan/manifest/planner, real `extract_file_text`, real `iter_repo_files`, real `build_graph_from_repo` body, embeddings enabled via fake provider, phantom-limb skipped via its production env flag. **All 4 tests pass** (0.77s). N = files present at run time; each file yields 1 unit in the fixture.

| Measure | Run A: cold (N=3) | Run B: no change (N=3) | Run C: 1 modified (N=3) | Run D: 1 deleted (N=2) | Ideal incremental target |
|---|---|---|---|---|---|
| Files discovered | 3 | 3 | 3 | 2 | same |
| Files read (indexer) | **3** | **3** | **3** | **2** | A: 3 · B: 0 · C: 1 · D: 0 |
| Files parsed (indexer) | **3** | **3** | **3** | **2** | B: 0 · C: 1 · D: 0 |
| Files parsed again (graph) | **3** | **3** | **3** | **2** | 0 (reuse indexer parse) |
| Hashes computed / reused | 0 / 0 — no fingerprinting exists in production | 0 / 0 | 0 / 0 | 0 / 0 | A: N/0 · B: 0/N · C: 1/N-1 |
| Embeddings generated | **3** | **3** | **3** | **2** | B: 0 · C: 1 · D: 0 |
| DB replacements | **3** | **3** | **3** | **2** | B: 0 · C: 1 · D: 0 |
| DB per-file deletions | 0 | 0 | 0 | **0** (cleanup only via reconciliation) | D: 1 |
| Reconciliation calls | 1 | 1 | 1 | 1 (receives `{alpha.py, beta.py}`) | 0 unless scope reset |
| Repository scans (inventory+iter) | 2 | 2 | 2 | 2 | 1 total (delta scan doubles as the scan) |
| DNA scans (each = full rglob + re-read) | 1 | 1 | 1 | 1 | 0 on unchanged |
| Graph builds (each = full re-read + re-parse) | 1 | 1 | 1 | 1 | incremental |
| Manifest loads / saves / delta / plans | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 0 / 0 / 0 / 0 | 1 / 1 / 1 / 1 per run |

Evidence classes:
- **Observed production behavior** (mocked I/O boundaries, real control flow): every count above.
- **Mocked characterization:** embedding vectors, DB calls, tree-sitter parses were counting fakes — counts are exact, costs are not measured (timing was out of bounds per mission).
- **Inferred:** the static traversal table in §6/H3 (7 traversals incl. `get_agent_dir` walks) — the test stubs `compute_dna` and skips phantom, so the test proves ≥4 of the 7; the other 3 are proven statically at `core/project_tag.py:45`, `config.py:182`, `graph/project_map.py:398`. Confidence high.
- **Ideal target:** last column, from `core/index_execution.py` plan semantics (`REUSE`, `to_parse = added+modified`, `to_delete = deleted`).

Run B verdict against the mission's critical target (`files parsed = 0, embeddings = 0, DB replacements = 0, DB deletions = 0`): **currently 100% miss** — production repeats all work (3/3/3, deletions 0 only because none ever happen per-file).

---

## 5. Correctness / recovery risk table

| # | Case | Current behavior | Classification | Confidence |
|---|---|---|---|---|
| 1 | Failure during file N — read/parse | Per-file `except` prints `ERR`, continues; file stays in reconciliation's `current_files` (added at `indexer.py:108` *before* the try), so its old DB rows survive | **safe with warning** (old rows intentionally retained; file missing from that run's map summaries) | high |
| 2 | Failure during file N — DB replacement | `db_available=False` latch (`indexer.py:222`) → all remaining files silently unpersisted, reconciliation skipped, run returns success-shaped dict; callers never check `reconciliation.skipped_reason` | **stale-data risk (severe)** — H1 | high |
| 3 | DB initialization failure | Warning printed, indexing continues without persistence; reason recorded in result; also `database/memory.py:46` embeds `DATABASE_URL` (credentials) in the printed error | **safe with warning** + **secret-leak defect** (H16) | high |
| 4 | Embedding provider failure (model load/encode raises) | Raises inside the per-file DB try → same latch as case 2, but mislabeled `persistence_skip_reason="file_replacement_failed"` | **stale-data risk + misdiagnosis** | high |
| 5 | Embeddings disabled at retriever layer (`RETRIEVER_USE_EMBEDDINGS=false`) while indexer embeddings on | `get_embedding` returns `np.zeros(384)` (`core/retriever.py:297-299`) — zero vectors persisted as real embeddings, silently poisoning similarity ranking | **stale-data / data-quality risk** | high (static); behavior with live pgvector untested |
| 6 | Parse failure | Fallback chain: text-based units → whole-file unit (`indexer.py:143-152`) | **safe** | high |
| 7 | Graph / project-map failure | Caught; degraded (edge-free) map **overwrites** the previous good `PROJECT_MAP.md`; no degradation flag in result (H5) | **stale-data risk (artifact quality)** | high |
| 8 | Reconciliation failure | Caught, recorded in result; stale rows persist until next fully-successful run | **safe with warning / bounded stale-data** | high |
| 9 | Policy fingerprint change | Production: moot (full rescan every run applies policy live). Library: `inspect_repository_delta` computes `policy_changed` (`index_manifest.py:357`) but `build_index_execution_plan` **never consumes it** — the caller must translate it into `force_full_reindex`, and nothing enforces that | **latent unnecessary-work / stale-data gap for the wiring phase** | high |
| 10 | Embedding provider or dimension change | **No detection exists anywhere.** `EmbeddingCompatibility` is consumed by the planner but nothing computes it from DB state (no production import outside `core/index_execution.py`). Dimension mismatch on insert → case 2 cascade; same-dimension provider swap → silently mixed embedding spaces until the next full run completes cleanly | **state-corruption risk / needs test** | high that detection is absent; pgvector failure mode inferred |
| 11 | File rename | Full reindex: new path inserted, old path swept by reconciliation. Under future delta: added + deleted — planner handles | **safe** | high |
| 12 | File becomes ignored | Excluded from scan → reconciliation deletes its rows. Manifest library also reports it as `deleted` (`test_delta_reports_newly_ignored_file_as_deleted` green) | **safe** | high |
| 13 | File becomes unsupported | Stays in `repository_files` (dependency resolution set) but not indexed → reconciliation removes rows (proven by `test_indexer_reconciliation_receives_supported_current_files`) | **safe** | high |
| 14 | Interrupted manifest write | Library uses tmp + `os.replace` (atomic), cleans tmp on failure (`index_manifest.py:124-138`); corrupt manifest loads as `None` → full-reindex fallback | **safe** (unwired) | high |
| 15 | Stale rows under legacy project tags | `reconcile_code_index_scope` deletes only `WHERE project_tag = index_scope`; rows written under pre-scope display tags are never cleaned. Retrieval is scope-guarded (`search_safe_code_units` overrides arbitrary tags; unscoped search rejected — `test_index_scope_wiring.py:35-82`), so this is bloat, not result corruption. **Also live:** public `clear_code_units_for_file` / `clear_dependencies_for_file` default `project_tag=None` → **unscoped cross-project DELETE** branches (`database/memory.py:971,1091,1279-1284`) guarded today only by a source-string test | **unnecessary-work risk** (bloat) + **state-corruption risk** (unscoped API, one call away) | high |
| 16 | Manifest false completion (forward-looking) | See §2 Q10 — naive wiring after case 2 permanently poisons the delta baseline | **state-corruption risk — must be solved before wiring** | high |

---

## 6. Architecture hotspots

Static scan (delegated sweep + direct verification). 16 hotspots; full detail in the JSON companion. TODO/FIXME markers: 17 grep hits, **0 real debt markers** (all domain strings) — this codebase's debt is structural and unmarked.

| ID | Hotspot (file:line) | Why it matters / evidence | Impact | Treatment | Blocks delta wiring? |
|---|---|---|---|---|---|
| H1 | Silent persistence death — `core/indexer.py:217-230,320-333` | First DB/embedding failure latches `db_available=False`; `files_indexed` keeps counting; result has no `persistence_ok`; all 3 callers ignore `reconciliation.skipped_reason` | A run persisting 3/900 files is indistinguishable from clean | Add `persistence_ok`/`files_persisted` to result; never save a future manifest unless fully persisted | **YES** |
| H2 | Drift-prone project tag — `core/project_tag.py:29-55` | `IGNORE_DIRS` defined and never used; unfiltered `os.walk` capped at 5,000 files hits `.git/objects` first; walk order not guaranteed → tag drift | `.agent/<tag>/` and memory/session bucket drift; dominant traversal cost | Path-derived tag (delegate to `build_repository_storage_key`) or policy-filtered + memoized walk | **YES** |
| H3 | `get_agent_dir` walks repo per call — `config.py:165-186` | Full walk + `mkdir` side effect; 22 call sites, no cache; 3 of the 7 index-run traversals | Highest fan-in perf hazard | Cache per resolved path; split pure resolve from mkdir | no (worsens after wiring) |
| H4 | Manifest+planner fully built, unwired — `core/index_manifest.py`, `core/index_execution.py` | ~640 tested lines, zero production callers | Every run re-embeds everything | This *is* the wiring phase; sequence after H1/H2/H8 | is the wiring |
| H5 | Degraded map overwrites good map — `core/indexer.py:302-318` | Graph failure → edge-free map silently replaces previous good `PROJECT_MAP.md`; consumed by `control_engine.py:66` | Persistent reasoning-quality regression after one transient error | `project_map_degraded` flag; don't overwrite good with degraded | no |
| H6 | Unscoped DELETE branches live — `database/memory.py:971,1091,1267-1284` | Public wrappers default `project_tag=None` → cross-project deletion is the *default*; guarded only by a source-string test on the caller | Cross-project index destruction one call away | Require scope; delete `else` branches | **partially** (new delete path must use `delete_code_index_for_file`) |
| H7 | Four ignore policies, three dead/divergent — `repo_ignore.py` (live), `code_dna.py:46` (divergent), `project_tag.py:29` (dead), `graph/builder.py:13-28 SKIP_DIRS` (dead), `core/repo_inventory.py` (dead module) | `compute_dna` sees a different file set than the index; manifest `policy_fingerprint` won't invalidate DNA | File-set divergence across artifacts | Route DNA through `iter_repo_files`; delete dead code | **YES** (for DNA consistency) |
| H8 | Three repo-identity schemes — `repository_identity.py:48,60` vs `project_tag.py:68` | DB keyed by `index_scope`, manifests by `storage_key`, `.agent`/memory by content-dependent `project_tag` | Manifest/DB/artifact desync when tag drifts | Unify on path-derived identity | **YES** |
| H9 | Graph re-reads + re-parses everything — `graph/builder.py:52-64` | Indexer's parse results discarded; `repo_entries` plumbing removed duplicate traversal but not duplicate parse | ~2× tree-sitter CPU; post-wiring the graph would diverge from delta-parsed set | Pass parsed-data map into graph build | **YES** (same change as wiring) |
| H10 | Phantom-limb rule errors become findings — `core/phantom_limb.py:344-353` | Exception text written into findings; `severity=="error"` invisible in summary; leaks into LLM prompt via `web/runner.py:497` | Stack traces in model context | Separate `errors` from `findings` | no |
| H11 | Source-string tests — `test_dependency_wiring.py:558-570`, `test_repo_ignore_policy.py:207-219`, ~28 files with `read_text` substring asserts, 3 `inspect.getsource` | Guard callers not APIs; break on safe refactors, pass on unsafe ones | H6 API itself untested; wiring rewrite breaks them cosmetically | Replace with behavioral asserts | **partially** |
| H12 | "One scan" test counts one helper — `test_dependency_wiring.py:614-693` | Asserts `iter_repo_files` called once while 6 other traversals run stubbed | False deduplication confidence | Count at `os.walk` boundary | **YES** (as regression gate) |
| H13 | Zero direct tests on wired path — `indexer.py` (427 LOC), `retriever.py` (1022), `code_dna.py`, `phantom_limb.py`, `project_tag.py`, `repository_identity.py`, `repo_librarian.py` | Unwired modules are well-tested; wired ones aren't — coverage tracks authorship recency, not runtime authority | No safety net under the rewrite target | Behavioral tests first (this audit's characterization test is a start) | **YES** |
| H14 | One try wraps index+preflight+control+memory+scout — `web/runner.py:485-540` | All failure modes collapse to one opaque message | Undiagnosable primary path | Per-stage try + `failure_stage` field | no |
| H15 | Fan-in giants — `web/app.py` (4080 LOC, 4 unparameterized `build_graph_from_repo` calls → 4 extra full scans), `database/memory.py` (neutral returns mask "no DB" vs "empty") | Request path multiplies index-time waste | Pass `repo_entries`; distinguish disabled from empty | no |
| H16 | **Credential leak** — `database/memory.py:46` embeds `DATABASE_URL` in error string; printed at `indexer.py:84`; can reach web response via `runner.py:537`; atexit pool close swallows all (`memory.py:57-61`) | Secrets in stdout/logs/answer field | Redact URL now (independent one-line fix) | no (fix immediately regardless) |

---

## 7. TDD / Test Author capability readiness matrix

Delegated deep audit, directly verified at the decision-critical points. Full per-capability citations in the JSON companion.

| Capability | Verdict | Key evidence |
|---|---|---|
| Test framework detection | **ready w/ guardrails** (Py/Go/Rust); **prerequisite missing** (TypeScript & C have *no* matching branch; two detectors already drifted) | `core/validation_command.py:48-112` vs `core/preflight.py:22-95`; `config.py:94-95` |
| Validation command discovery | **ready now** — operator override → DB tooling profile → language default, persisted back per repo | `core/pipeline.py:820-871`; `database/memory.py:882,947` |
| Safe validation execution | **ready now** — argv-only allowlist, mandatory ≤600s timeout, secret-env scrubbing, metachar rejection | `core/validation_execution.py:12-310` |
| Temp-clone / sandbox | **ready now** — temp-clone + hardened Docker backends; sha256 pre/post tree diff = `changed_files` | `core/sandbox_runner.py:296-340,498,917` |
| — caveat | `core/project_evolution_sandbox_validation.py` never actually applies/validates (all paths `not_run`) — **unsuitable for v1** despite the name | `:397-400,464-478` |
| Patch safety for test files | **PREREQUISITE MISSING (hard blocker)** — test paths hard-blocked, no override; rationale for a future exception already written in the code | `core/patch_safety.py:69-75,187-194,220`; enforced `core/executor.py:181-203`, `core/self_correct_loop.py:117-124` |
| Generated-artifact ledger | **ready w/ guardrails** — closed artifact allowlist needs new TDD artifact names | `benchmarks/artifact_ledger.py:57-93`; `core/run_artifacts.py:13-23,91-93` |
| Mutation oracle | **ready w/ guardrails** as GREEN-patch strength probe; **unsuitable** as test-quality oracle (no per-test kill attribution; wired only to legacy shell path, off by default) | `core/mutation_oracle.py`; wiring `core/executor.py:325`; `config.py:361` |
| Patch minimality | **ready w/ guardrails** — real math lives only in the benchmark harness; live path uses risk scoring | `benchmarks/run_benchmarks.py:418-482`; `core/executor.py:629-684` |
| Changed-file visibility | **ready now** — 4 independent mechanisms (rollback ledger, sandbox sha256 diff, side-effect diff, benchmark diff) | `patching/patch_plan_executor.py:135-142`; `core/validation_side_effects.py:110-158` |
| Test-only vs source patch handling | **prerequisite missing** — classifier mature, policy branch absent; the worker `allowed_files` override is the precedent to follow | `core/patch_safety.py:220`; `core/worker_assignment.py:567-574` |
| RED-before-GREEN verification | **PREREQUISITE MISSING** — nothing runs tests pre-patch and compares; preflight is the only pre-state signal (boolean+category, never re-diffed) | `core/executor.py:282-313`; `core/pipeline.py:678-689` |
| Deleted/weakened-test detection | **PREREQUISITE MISSING** — no test-count/skip/xfail delta anywhere; the blanket test-path block is the *only* current defense and is exactly what TDD must relax | `core/invariant_verification.py:1-6`; `core/validator.py:856` |
| Python/pytest | **ready now** | matrix in JSON |
| JavaScript/TS | JS ready w/ guardrails (blind `npm test`); **TS prerequisite missing** | `core/preflight.py:9-19,52-60` |
| Go / Rust | ready now / ready w/ guardrails | `core/validation_command.py:96-110` |
| C/C++ | C prerequisite missing; C++ unsuitable for v1 (single-`main.cpp` g++ only) | `core/validation_command.py:84-87` |

**Design evaluation:**

- **Design A (top-level TDD mode): poor for v1.** `core/mode_router.py` is suggestion-only and never dispatches (`:1-6`, confirmation hardcoded `:203`); the workflow "modes" are frozen documentation contracts. A real mode means touching patch policy, pipeline, and both contracts — high blast radius, low reuse.
- **Design B (test strategy inside existing modes): best fit for v1.** Runtime behavior is already driven by per-run fields (`patch_style` at `core/agent_state.py:44`, `harness_mode` at `:52`) threading through `policy/decision_helper.py:38-109` → `patching/patch_gates.py:1386-1424` → executor. A `test_strategy` field (`existing_tests | characterize_first | generate_regression_first | implementation_then_tests | no_generated_tests`) lands in the same seams and gives `evaluate_patch_safety` a natural place to receive a scoped test-path allowance.
- **Design C (separate Test Author worker): good fit for v2, not v1.** The worker pipeline (assignment → import → sandbox-validate → trust-review) exists and its `allowed_files` already overrides the test-path forbid (`core/worker_assignment.py:567-574`) — but it is human-copy/paste by construction (`worker_launch_allowed: False` at `:365`).

**Recommendation: staged B → C.** V1 = Design B with an explicit permission model: (a) test-path patch allowance is granted only by the `test_strategy` value, scoped to declared test paths, human-approved per run (mirroring the worker `allowed_files` precedent); (b) the same change-set MUST ship the test-weakening detector (test-count/skip delta across the run pair), because relaxing `patch_safety` removes the system's only anti-test-gaming defense; (c) RED→GREEN = two recorded runs through the existing safe-validation sandbox with a comparator asserting the new test fails pre-patch and passes post-patch, with implementation-diff and test-diff kept as separate patch phases so the Test Author's writes can be mechanically confined to test paths even inside Design B. V2 promotes the Test Author to a separate worker (Design C) reusing the same permission contract.

---

## 8. Candidate phase ranking

Scores 1–5. `risk`: 5 = high risk. `scope`: 5 = large. Weighted score = 0.20·pain + 0.20·correctness + 0.15·perf + 0.20·leverage + 0.10·(6−risk) + 0.05·testability + 0.05·(6−scope) + 0.05·prereq.

| Rank | Candidate | pain | correct | perf | leverage | risk | testable | scope | prereq | **Score** |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | **(new) Repository Identity Unification & Trusted Completion** (H2+H8+H1+H16, incl. `get_agent_dir` caching from H3) | 4 | 4 | 5 | 5 | 2 | 5 | 2 | 5 | **4.45** |
| 2 | Production Delta Execution Wiring (H4, +H7/H9 file-set unification) | 5 | 3 | 5 | 5 | 3 | 4 | 4 | 3 | **4.10** |
| 3 | Trusted Manifest Completion & Recovery (as a standalone phase) | 2 | 5 | 1 | 5 | 2 | 5 | 2 | 5 | **3.65** |
| 4 | TDD Test Strategy Contract (Design B + patch-safety exception + weakening detector) | 3 | 4 | 1 | 4 | 3 | 4 | 3 | 3 | **3.15** |
| 5 | Python/Pytest Test Author Sandbox MVP | 3 | 3 | 1 | 3 | 4 | 3 | 4 | 2 | **2.50** |
| 6= | Incremental Graph/Activation Work | 2 | 2 | 3 | 2 | 3 | 3 | 4 | 2 | **2.30** |
| 6= | Two-run Indexing Performance Dogfood | 1 | 1 | 2 | 2 | 1 | 4 | 1 | 5 | **2.30** |
| 8 | Cross-language Generated-Test Adapters | 2 | 2 | 1 | 2 | 4 | 2 | 5 | 1 | **1.75** |

Notes on the scoring:
- Candidate 1 was **discovered by the audit** (mission slot #8). It absorbs the standalone "Trusted Manifest Completion" (rank 3) — H1's `persistence_ok` is one of its deliverables — which is why rank 3 need not run separately.
- Delta Wiring scores higher on raw pain/perf but its prerequisite readiness is 3: wiring before H1/H2/H8 risks poisoned manifests and desynchronized identities (§5 cases 2, 16; §6). Evidence, not indexing-bias, puts it second-in-time.
- Two-run Dogfood is largely superseded: the characterization test added by this audit already pins the two-run behavior deterministically; wall-clock dogfooding becomes an acceptance criterion of the wiring phase instead of a phase.
- TDD candidates stay behind indexing because three hard prerequisites (patch-safety exception, RED/GREEN comparator, weakening detector) must land as one coupled unit, and the indexing path currently burns weak machines on every single web request — the pain asymmetry is decisive.

---

## 9. Recommended next phase

**INDEX.1D — Repository Identity Unification & Trusted Completion** (immediate next).

Contents (smallest defensible set):
1. Make auto-derived repository identity path-derived and stable: `build_project_tag(repo_path, None)` delegates to `build_repository_storage_key` (explicit user tags preserved verbatim); delete the dead `IGNORE_DIRS`/fingerprint walk or keep it only behind an explicit opt-in.
2. Cache `get_agent_dir` per resolved path; split pure resolution from `mkdir`.
3. Add honest completion truth to `index_repository`'s return: `persistence_ok: bool`, `files_persisted: int`, `persistence_skip_reason`, `first_persistence_error`, distinguishing embedding failure from replacement failure; stop latching `db_available` silently.
4. Redact `DATABASE_URL` from connection error strings (H16).
5. Behavioral tests for `project_tag` stability across `.git` mutation, `get_agent_dir` single-walk, and the `persistence_ok` contract.

**Backup phase:** Production Delta Execution Wiring (run it immediately after INDEX.1D; if INDEX.1D is judged too small for a full phase, fold it into the wiring phase as its first two commits — but do not start the wiring loop itself before items 1 and 3 exist).

**Deferred:** Incremental Graph/Activation; Cross-language Test Adapters; Test Author Sandbox MVP; Two-run Dogfood (absorbed into wiring acceptance); TDD Test Strategy Contract (next macro-phase after wiring, as Design B with the coupled §12 detector).

**Confidence:** high on the ranking's top-3 ordering (grounded in reproducible tests + file:line evidence); medium on TDD-vs-indexing relative placement (depends on operator priorities not visible in the repo).

**Evidence that would change the recommendation:**
- Proof that `build_project_tag` drift does not occur in practice (e.g., a stability test across `.git` churn passing on real repos) would demote INDEX.1D item 1 and could make Delta Wiring immediate.
- A measured two-run wall-clock profile showing embedding time dominated by something *other* than per-file rework (e.g., model load) would lower the perf payoff of wiring and raise TDD's relative rank.
- An operator decision that generated-test capability is the product priority would justify starting the TDD Test Strategy Contract in parallel, since its blockers are disjoint from the indexing blockers.

---

## 10. Exact acceptance criteria for INDEX.1D

1. `build_project_tag(same_repo_path, None)` returns an identical tag before and after: (a) a commit is added to `.git`; (b) `node_modules`/`.venv` contents change; (c) two consecutive calls in different process runs. Proven by new behavioral tests.
2. For an auto-derived tag, `build_project_tag(p, None)`, `build_repository_storage_key(p)`, and `build_code_index_scope(p)` are all pure functions of the normalized path (one shared digest), and a test asserts their mutual consistency.
3. `get_agent_dir` performs zero repository traversals on a second call for the same path within a process (counter test at the `os.walk` boundary, not at a named-helper boundary — per H12).
4. `index_repository` result contains `persistence_ok`, `files_persisted`, and a non-misleading `persistence_skip_reason` that distinguishes `embedding_failed` from `db_replacement_failed` from `db_initialization_failed` from `persistence_disabled`; a run with a mid-loop replacement failure returns `persistence_ok=False` while still completing map/DNA work. Proven by extending the characterization test.
5. Reconciliation is skipped iff `persistence_ok` is false or DB is unavailable, and the result says which.
6. No error/log path emits `DATABASE_URL`; a test asserts the redaction.
7. Explicit user-supplied tags behave exactly as before (regression tests over `build_project_tag(p, "user-tag")`).
8. Focused suite + `tests/test_index_production_readiness_audit.py` green; `python -m compileall core graph database tests` clean; no changes to `.env`, Docker, schema, benchmarks, prompts, lessons, roadmap registry.
9. Explicit non-goals recorded in the phase doc: no manifest wiring, no planner wiring, no per-file delete dispatch (all reserved for the Delta Wiring phase).

---

## 11. Deferred work

- Delta Wiring itself (next after INDEX.1D), including: single-traversal design (delta scan doubles as *the* repo scan), routing `plan.to_parse`/`to_delete` into the loop and `delete_code_index_for_file`, `plan.reset_index_scope` → reconciliation, manifest save **only** on `persistence_ok`, planner consumption of `policy_changed`, and an `EmbeddingCompatibility` detector (currently nothing computes it — §5 case 10).
- H7/H9: unify DNA/graph file sets and reuse indexer parses (same change window as wiring).
- H5 (degraded-map overwrite), H6 (unscoped DELETE API hardening), H10 (phantom errors), H11/H12 (test modernization), H14/H15 (web runner/app granularity), legacy-tag row cleanup (one-time scoped sweep).
- TDD track: patch-safety scoped exception + weakening detector + RED/GREEN run-pair comparator (one coupled unit), then Design B `test_strategy`, then Design C worker promotion; TS/C detection gaps; `dotnet` missing from `sandbox_runner` allowlist.

## 12. Commands run and results

```text
python -m pytest tests/test_index_production_readiness_audit.py -q
→ 4 passed in 0.77s

python -m pytest tests/test_index_manifest.py tests/test_index_execution_plan.py \
  tests/test_dependency_target.py tests/test_code_index_transactions.py \
  tests/test_dependency_wiring.py tests/test_index_scope_wiring.py \
  tests/test_project_index_scope.py -q
→ 135 passed, 6 warnings (pathspec GitWildMatchPattern deprecation) in 1.21s

python -m compileall core graph database tests -q
→ exit 0

git diff --check
→ exit 0 (clean)
```

Not run (out of bounds per mission): full test suite, model-backed benchmarks, real-embedding indexing, live-database runs. No network calls, no packages installed, no production files modified, no persistent production DB data written.

## 13. Limitations and unknowns

Warnings behind the `_WITH_WARNINGS` status:
1. **Four-run counts are exact under mocks, not costs.** DB, embeddings, and tree-sitter were counting fakes; wall-clock and live-pgvector behavior (notably dimension-mismatch errors, §5 case 10) remain characterized-but-unmeasured. This was a mission constraint, not an omission.
2. **Three of the seven per-run traversals are proven statically only** (`build_project_tag`, `get_agent_dir` via `save_dna`/report writers) — the characterization test stubs DNA and skips phantom-limb, so it dynamically pins 4 of 7.
3. **A security defect was found during a readiness audit** (H16, credentials in error output) and is unfixed by design of this phase — it should not wait for INDEX.1D review if a hotfix window exists earlier.
4. Legacy-tag row volume in the live database is unknown (no live DB access during the audit) — bloat magnitude unquantified.
5. The delegated hotspot and TDD sweeps were verified at decision-critical points but not every cited line was independently re-read; citations carry the sub-audit's confidence (high) rather than direct verification everywhere.

## Final status

```text
NEXT_SCAN_1_COMPLETE_WITH_WARNINGS
```