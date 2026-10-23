# RUNTIME.JAVA.DISCOVERY.CONTRACT.1

Status: `RUNTIME_JAVA_DISCOVERY_CONTRACT_1_COMPLETE_WITH_WARNINGS`

Semantic conclusion: **`REQUIREMENT_EVOLUTION_REQUIRED`**.

This is a source-and-test contract audit, dated 2026-10-09 Asia/Seoul. It creates
no operational schema, provider, capability, lease, runtime receipt or compatibility
relation. The companion `_REPORT.json` is report-only evidence. The preservation
manifest and validation reports record checks of the existing working tree.

## Decision

An exact-provider proof cannot replace `complete_inventory=true` under the
unchanged `runtime_java_1_v1` requirement without changing its contract. The
frozen downstream requirement is generic JAVA.1 discovery and selection, with
authenticated complete-discovery witnesses. It is **not** a requirement that
only image `sha256:f6d7dc31a15bb37a618ebed6772beda3de95fdcc3394eb5a1def9b1d20673f7a`
may satisfy it. That image is the historically selected artifact and the later
continuations' explicit target; historical selection does not amend SYNTH.AUTH.1.

The audit does not establish that global inventory is intrinsically necessary
for the safety of a fixed immutable provider. No successful-provider consumer
requires that no alternative Java provider exists, or that exactly one Java
toolchain exists globally. Identity, executable pairing, controller checks,
isolation and backend comparison have their own witnesses. Nevertheless, the
old success contract explicitly includes coverage of the enumerated domain and
signed discovery/inventory evidence. Replacing those witnesses and generic
selection with a fixed target is requirement evolution, not proven equivalence.

Thus global completeness is required **by the existing contract**; an independent
global uniqueness safety invariant is not demonstrated. This distinction is why
the conclusion is `REQUIREMENT_EVOLUTION_REQUIRED`, rather than an assertion that
complete inventory is inherently necessary for every possible safe Java design.
No required property is silently discarded or declared equivalent.

Freeze both distinctions:

`global discovery completeness != exact provider authenticity`

`different mechanism != different semantic guarantee`

Different mechanisms could prove the same facts. The proposed exact-only mechanism
does not prove the old full-domain facts, and the current downstream requirement
has not adopted the narrower facts as a substitute.

## Source basis and actual selection

Primary evidence is implementation and executable pure tests, not roadmap prose.
Source references below are repository-relative and use the preserved source lines.

* `core/sandboxed_java_toolchain_discovery.py:375-452`: discovery queries the
  fixed local Docker route, measures Linux server version, obtains
  `image ls --all --no-trunc --quiet`, sorts/deduplicates immutable IDs, and
  classifies each ID. Platform-ineligible and declared-volume images are
  conclusively ineligible without an export. Eligible images need bounded
  stopped-container filesystem inspection. Inspection/export errors make the
  inventory incomplete; cleanup failure also prevents success. This is coverage
  of that measured inventory, not an atomic daemon snapshot or future inventory.
  The equivalent local `complete` variable is produced/consumed at
  `:378,401,421,437,442,447,452`; early result constructors at `:383-400` carry
  its unavailable/invalid/empty-domain cases.
* `core/sandboxed_java_toolchain.py:419-446`: JAVA.1 uses the original discovery
  owner, selects the first Linux/amd64 record with a pair and status
  `local_java_toolchain_present` **or** `local_java_controller_unavailable`,
  prefers its first valid frozen-controller pair, otherwise takes its first pair,
  and stops selection. It does not rank every provider, enforce global uniqueness,
  or fall back after failure. An earlier controllerless candidate can block a
  later usable one. Sorted image IDs and sorted resolved pair directories make
  the original mechanism deterministic; that ordering is not itself an independent
  security invariant.
* `core/sandboxed_java_toolchain.py:432-446,479-498`: cleanup, authenticated
  sandbox, discovery/backend identity AND version, complete inventory, and fixed
  controller are distinct prelaunch gates. The receipt signs the entire artifact
  inventory and `discovery_complete`, as well as the selected identity and outcome.
* `core/sandboxed_java_toolchain.py:217-248`: descriptor verification and the
  public executor predicate consume authenticated COMPLETE status indirectly.
  They do not independently recount providers or read a global uniqueness fact.
* `core/synthetic_runtime_authorization.py:27-30,103-146,168-174,264-269` and
  `tests/test_synthetic_runtime_authorization.py:69-123`: SYNTH requests exactly
  `RUNTIME.JAVA.1` / `runtime_java_1_v1`, sandbox profile and policy. The spec
  contains no image or Java/Javac/controller pin. Every spec field remains exact.
* `core/behavioral_diagnostic_executor_lifecycle_retry.py:70-105,195-202` and
  `tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py:96-127`:
  the downstream inspection preserves the exact SYNTH Java schema/policy
  requirement and blocks on `java_profile_contract_mismatch`; JAVA.1C's own
  predicate does not assert that requirement. This is a separate frozen stop.
* `core/java_runtime_compatibility.py:114-128,188-207` and
  `tests/test_runtime_java_compat1.py:36-56,126-161,174-188`: completeness and
  signed receipt witnesses are independently frozen comparison dimensions.
  The exact image comparison is traced to the historical selected-artifact report.
* `core/sandboxed_java_discovery_continuation.py:56-89,122-157,263-275,349-367`:
  JAVA.1D retry retains complete inventory first, then selects exactly one target
  record and exact pair. It does not require all other providers to be absent.
  It signs a canonical inventory retaining every record and distinction, plus
  exact provider and backend coherence. It asserts no JAVA.1 identity or SYNTH
  satisfaction even on its fabricated positive test path.

## Completeness consumers and classifications

The report JSON contains the exhaustive named-occurrence index (file, line, token,
one primary classification, consumer), plus this equivalent-field dependency graph.
The search covers production and tests under `core`, `scripts`, `tests`; unrelated
evidence-quality inventories, file-capability inventories and checkpoint test names
are explicitly excluded from the Java dependency graph. Historical JSON/Markdown
are evidence/report sinks, never live authority. New audit files are excluded from
the historical occurrence index.

| Consumer / preserved source | Primary classification | Actual dependent decision |
|---|---|---|
| Discovery record `:59-71`, local `complete` producer `:378-452` | DISCOVERY_MECHANISM | Coverage flag is false on unavailable/invalid inventory, metadata/export/inspection failure; true on complete classification, including an empty inventory. |
| Archive/export bounds `:24-27,162-289` | RESOURCE_BOUND_REQUIREMENT | Size, entries, executable size and deadline stop inspection; a failed eligible-image export prevents complete classification. |
| Discovery cleanup `:421-438` | SECURITY_REQUIREMENT | Unverified removal fails completion/success; completeness alone never substitutes for cleanup. |
| JAVA.1 absent-artifact branch `:434-437` | DISCOVERY_MECHANISM | Complete absence becomes `no_suitable_local_java_artifact`; partial knowledge retains an incomplete/error reason. |
| JAVA.1 prelaunch completeness gate `:445` | TOOLCHAIN_SELECTION_REQUIREMENT | An otherwise selected candidate cannot launch when any eligible classification is unresolved. |
| JAVA.1 receipt fields/signing `:109-111,160-165,479-498` | RECEIPT_COMPLETENESS_REQUIREMENT | Inventory and completeness enter authenticated payload, fingerprint and exported report. |
| JAVA.1 descriptor/public predicate `:217-248` | SECURITY_REQUIREMENT | Authenticated COMPLETE is the indirect success dependency; no independent global cardinality test. |
| JAVA.1 discovery backend equality `:442-444` | BACKEND_BINDING_REQUIREMENT | Both route identity and server version must match authenticated sandbox; independent of completeness. |
| Original replay stop `scripts/replay_runtime_java1.py:35` | RESOURCE_BOUND_REQUIREMENT | Stops further attempts on incompatible or incomplete receipt; does not retry incomplete discovery to claim success. |
| Original replay inventory reporting `:44-48,68` | HISTORICAL_IMPLEMENTATION_DETAIL | Reports domain and measured inventory size; no new acceptance rule. |
| COMPAT receipt dimension `:114-116` | RECEIPT_COMPLETENESS_REQUIREMENT | JAVA.1C lacks original signed inventory/discovery witnesses. |
| COMPAT discovery dimension and final block `:123-125,207` | TOOLCHAIN_SELECTION_REQUIREMENT | Full discovery remains independently required under the old requirement; caller metadata cannot fill it. |
| COMPAT backend dimension `:126-128` | BACKEND_BINDING_REQUIREMENT | Separate missing discovery/backend provenance witness. |
| First JAVA.1D replay `scripts/replay_runtime_java1d.py:68-89` | HISTORICAL_IMPLEMENTATION_DETAIL | Null completeness/count/hash/inventory and declared original domain; pre-discovery block supplies no measurements. |
| JAVA.1D retry `_discovery_gates` `:62-89` | TOOLCHAIN_SELECTION_REQUIREMENT | Rejects incomplete owner record before backend comparison, membership or JAVA.1C. |
| JAVA.1D exact record/pair counts `:73-88` | AMBIGUITY_REQUIREMENT | Exactly one matching target record/pair; does not count all providers. |
| JAVA.1D canonical full inventory and receipt `:56-60,122-126,143,349-367` | RECEIPT_COMPLETENESS_REQUIREMENT | Retains/hashes all records, sources, count and completeness; does not collapse to target-only data. |
| JAVA.1D report projection `:211,269-270`; retry CLI `scripts/replay_runtime_java1d_retry.py:22-23` | HISTORICAL_IMPLEMENTATION_DETAIL | Report/printing only, no authority from JSON. |
| JAVA.1D owner identity/backend coherence `:64-72,91-108,178-191` | PROVENANCE_REQUIREMENT | Exact owner records and authenticated runtime evidence remain separate; copies/reports cannot substitute. |
| JAVA.1 tests `tests/test_runtime_java1.py:93-108,185-202` | RECEIPT_COMPLETENESS_REQUIREMENT | Complete empty inventory yields an authenticated unavailable result, not runtime success; payload tampering fails authentication. |
| Discovery tests `tests/test_runtime_java1_discovery.py:163-226` | DISCOVERY_MECHANISM | No backend is incomplete; fully classified wrong platform, declared volumes, empty domain are complete and do not launch Java. |
| COMPAT tests `tests/test_runtime_java_compat1.py:36-43,110-118,126-161` | TOOLCHAIN_SELECTION_REQUIREMENT | Missing completeness independently blocks; edited metadata and JAVA.1C's missing fields cannot bridge it. |
| First JAVA.1D tests `tests/test_runtime_java1d.py:56-83` | HISTORICAL_IMPLEMENTATION_DETAIL | Completeness remains unmeasured at the earlier binding stop. |
| JAVA.1D retry tests `tests/test_runtime_java1d_retry.py:62-88,93-113,156-176` | RECEIPT_COMPLETENESS_REQUIREMENT | Positive fabricated fixture retains full inventory; incomplete fixture stops; count remains measured; inventory-hash tampering is rejected; canonical evidence retains unrelated and duplicate distinctions. |
| DIAG classifier/tests `scripts/measure_runtime_java_discovery_diag1.py:36-51,378-385`; `tests/test_runtime_java_discovery_diag1.py:12-25,126-168` | RESOURCE_BOUND_REQUIREMENT | Raw transport failure stops before semantic parsing, full discovery, JAVA.1C or retry. No completeness is asserted. |
| SYNTH projection and executor consumers cited above | TOOLCHAIN_SELECTION_REQUIREMENT | Exact Java profile/schema remain the generic old requirement; no pin-only replacement exists. |

Some rows summarize several decisions; each named occurrence has exactly one
primary category in the JSON. Distinct backend, ambiguity and cleanup dependencies
are listed even where no completeness token appears. No occurrence is classified
solely from its variable name. `UNKNOWN` is not used to invent an invariant.

## Original threats and the hypothetical exact proof

The exact-only hypothetical is assessed as the user's fourteen-step specification,
not as a new implementation or an already authenticated result. No report value
is promoted to live evidence.

| Property / threat | Historical protection and need for global coverage | Exact-only proof comparison |
|---|---|---|
| Multiple Java images | Accepted; first-match mechanism, no global uniqueness rule | Alternatives need not be inspected under a **new explicitly pinned requirement**; cannot establish old selector's result. |
| Ambiguous toolchains | Original first pair/preferred controller; 1D uniquely matches target pair | Exact paths/hashes plus target-pair checks preserve target authenticity; no global uniqueness claim. |
| Unexpected local selection / hidden alternate provider | Complete classification documents original candidate domain and selection inputs | No selection/fallback preserves explicit new target selection, but changes generic old selection and loses coverage of alternatives. |
| Tag spoofing / mutable references | Immutable image ID validation and exact metadata identity `discovery:354-372`; no tags for execution | Preserved by exact immutable image equality and no tag-based identity; global inventory is not needed for this local check. |
| Wrong OS/architecture | Image metadata plus Linux/amd64 executable ELF checks `discovery:125-161,355-372,411-413` | Preserved if original metadata/ELF checks remain. |
| Wrong java/javac pair | Resolved same-directory pair, exact executable hashes, in-sandbox rehash and fixed argv | Preserved for exact pair with original link/path/traversal checks and fresh JAVA.1C. |
| Wrong executable hashes | Hash actual bounded executable bytes; compare runtime evidence | Preserved for target; exact claimed hash strings alone are insufficient. |
| Wrong controller | Fixed path, resolved ELF/hash, nonroot execution/traversal; runtime controller proof | Preserved if actual target controller identity is checked and coherently bound. Original 1D validates hash shape rather than an exact controller digest pin. |
| Unknown eligible-image classification | Any failed eligible-image inspection leaves full inventory incomplete, even if target is known | **Lost outside target.** Exact inspection cannot say every listed eligible image has been classified. |
| Backend mismatch | Original route AND server-version equality, separately authenticated sandbox | **Conditional.** Actual targeted inspection measurements must be bound to fresh BIND and runtime evidence; chronology alone is insufficient. |
| Fallback to unintended image | JAVA.1 does not retry another candidate after selected-candidate failure; immutable launches, pull never | Preserved by explicit target equality, no fallback, no provisioning and fail-closed mismatch. |
| Global absence of any eligible provider | Complete empty/classified inventory can justify unavailable result | **Lost.** Target absence cannot establish global absence. This is a negative-result capability, not a successful-provider uniqueness requirement. |
| Exactly one provider / no other eligible provider | **Not required or proven** by successful JAVA.1 or SYNTH | No such equivalence claim is needed or permitted. |
| Complete signed inventory / discovery provenance | Explicit original receipt fields and COMPAT dimensions | **Lost as old witness.** Exact-provider evidence must use a different truthful proof type under a new boundary. |
| Sandbox boundary, no network/mounts/shell, exact source/class/argv, bounded capture/deadline, cleanup | Separately authenticated original sandbox/image probes and Java predicates | Preservable with retained checks and fresh JAVA.1C; global enumeration is not their enforcement mechanism. |

The machine report has individual property rows and evidence references, including
every COMPAT.1 dimension. “Preserved” describes the hypothetical contract, not a
measurement or a compatibility relation issued by this phase.

## Negative evidence and semantic limits

Full discovery can establish that the measured enumeration is empty or contains no
eligible toolchain, subject to its exact platform/controller classification. An
exact-target inspection cannot establish those global negative facts. Neither
JAVA.1's positive predicate nor SYNTH consumes “no other eligible provider exists”
or “there is exactly one global Java toolchain.” JAVA.1D's `len(matches)==1` and
`len(pairs)==1` are target-scoped ambiguity checks, not global uniqueness.

The source does not explain an independent safety need to inspect an unrelated
candidate that sorts after an already usable candidate. It nonetheless explicitly
requires full classification before success and signs that evidence. This audit
does not relabel that obligation as optional. Conversely, it does not invent a
global-exclusivity threat to rationalize the historical implementation.

Whether the original selector would select the pinned provider in a future live
domain is unproven from exact-only evidence. Historical selected values cannot
prove current selection or freshness. The audit can decide the contract boundary
without claiming that full enumeration is a universal safety necessity.

## COMPAT.1 and evidence binding

COMPAT.1 marks `complete_local_artifact_discovery` independently unproven and also
marks `runtime_receipt_semantics` and `discovery_backend_binding` unproven. It
does not describe completeness solely as a proxy for executable authenticity.
Its missing-witness regression proves prelaunch failure with a known candidate.
That block remains correct under its frozen requirement. COMPAT.1 is not changed
or retroactively made compatible.

BIND.1 authenticates an exact live SANDBOX.2 pair and route/server-version
measurements (`core/sandbox_backend_binding.py:121-135,179-206`). Its comparison
helper expressly does not authenticate caller-supplied discovery strings. It
retains neither daemon-instance continuity nor ABA resistance. JAVA.1C obtains
another fresh SANDBOX.2 pair internally and authenticates its own exact pair
(`core/sandboxed_java_positive_continuation.py:51-84,294-302,369-394`).

Therefore “fresh BIND, then fresh JAVA.1C” alone does not establish evidence
linkage. Any future targeted contract must define how actual targeted inspection
measurements are authenticated against BIND's route/version and how the exact
runtime pair, image, toolchain and cleanup evidence are coherently bound. The
frozen BIND comparator's original-discovery-owner expectation must not be silently
repurposed. The hypothetical's sequence does not explicitly provide all that
linkage; this audit marks it conditional/unproven and fails closed on equivalence.
No daemon continuity or ABA property is claimed by either approach.

## Resource result stays separate

Historical DIAG.1 remains `RUNTIME_JAVA_DISCOVERY_DIAG_1_COMPLETE_WITH_WARNINGS`,
classification `EXPORT_TRANSPORT_EXCEEDS_BOUND`. Its measured target was
`sha256:09361da47d33ad0d44f89947d5e99003e94594e885328cdb5cd7b1c515a1a089`.
One raw-drain export received 384,237,059 bytes and did not complete within the
unchanged 30,000 ms budget. No semantic archive parsing occurred; the parser
trial was correctly skipped. The measured timeout does not require the parser.

This does not isolate daemon production from transport/host capture, prove that
host capture dominates, show the artifact can never finish in 30 seconds, prove
zero parser cost, or predict a later cold/warm run. Budget execution feasibility
and semantic necessity are separate questions. The resource result supplies no
premise for deleting completeness. No timeout or discovery domain was changed.

## Recommended next boundary; stop

Keep historical JAVA.1D and both blocked attempts blocked. Do not create COMPAT.2,
retry EXECUTOR.1R, or implement DISCOVERY.PINNED.1 in this phase.

If targeted architecture is desired, review an **additive requirement epoch**
whose explicit accepted provider is the immutable image and exact Java/Javac and
controller evidence. It should expose a truthful different proof kind such as
`exact_provider_proven`, never assert `complete_inventory=true`, prohibit
alternative selection/fallback/tags/provisioning, retain the local safety checks,
and explicitly define backend/runtime evidence binding. Such a field is only a
proposed boundary here, not an operational schema.

A subsequent SYNTH authorization epoch/projection must explicitly adopt that
requirement if needed, and a later compatibility/migration audit must understand
the different requirement. Old JAVA.1, COMPAT.1, SYNTH, lifecycle/reflection and
executor owners, registry history and reversal receipts remain unchanged. No
profile/schema alias, frozen-owner rewrite, timeout increase or retroactive pass.

## Effect accounting and preservation

Operational Docker calls, containers, exports, Java, javac, compile, network,
shell, host mounts, source projection, runtime lease consumption, reflection
lease consumption, BANK, EXECUTOR.1R and Apply are **all zero**. The pure
regressions use fabricated fixtures and process/network denial; fixture calls
and historical counters are not operational activity. Existing pure tests may
construct their own development-only authenticated fixtures; this phase defines
and issues no new capability or runtime receipt.

Host repository reads, Python/pytest validation and report writes are maintenance
actions, not runtime shell/compile effects. “Shell=0” denotes operational/runtime
shell execution; it does not pretend this audit used no host command interpreter.
In-memory Python compilation checks syntax without executing compiled code and
is distinct from the zero Java compilation count.

Before additions, 1,852 existing Git-visible files were hashed, including unrelated
modified and untracked files; eight tracked fixture paths were already missing.
The preservation report compares the same paths byte-for-byte and their missing
state, covering all named historical owners/artifacts and registry/reversal files.
No stash/reset/clean, repinning or changes to existing files are permitted here.

## Validation

Validation results and exact baseline/after failure identities are recorded in
the companion `_VALIDATION.json` and `_PRESERVATION.json`.

The final guarded pure selection passed **555/555**, including all ten new audit
controls. No real process/network effect was attempted. The selection comprised:

| Pure suite | Passed |
|---|---:|
| New contract audit | 10 |
| JAVA.1 | 91 |
| JAVA.1 discovery | 24 |
| JAVA.1 governance | 7 |
| JAVA.COMPAT.1 | 67 |
| JAVA.1D first attempt | 10 |
| JAVA.1D retry | 27 |
| DISCOVERY.DIAG.1 | 15 |
| BIND.1 | 129 |
| SYNTH.AUTH.1, including exact requirement projection | 117 |
| EXECUTOR.1R blocked result | 12 |
| EXECUTOR.1R lifecycle retry blocked contract result | 46 |

The initial run had 552 passes and three discovery failures caused by
`local_java_artifact_detection_failed:PermissionError` when the frozen tests used
the default host temp directory. All three passed with the temp directory inside
the workspace. The full selection then passed using that same setting. No frozen
test, source, expected value or hash was edited. Raw initial/final logs remain
separate. One dependency deprecation warning remains.

The direct current-tree registry/picker result was **292 passed, 7 failed** both
before and after. The exact failure identities are unchanged:

* `tests/test_phase_registry.py::test_seed_registry_has_expected_phases`
* `tests/test_phase_registry.py::test_live_strict_envelope_dogfood_is_the_first_phase_to_declare_a_model_call`
* `tests/test_phase_registry.py::test_seed_registry_is_conservative`
* `tests/test_phase_registry.py::test_seed_registry_summary_counts`
* `tests/test_phase_picker.py::test_seed_registry_produces_expected_buckets`
* `tests/test_phase_picker.py::test_behavioral_runtime_executor_is_blocked_and_never_recommended_without_isolation`
* `tests/test_phase_picker.py::test_verified_runtime_sandbox_is_history_and_executor_stays_blocked`

No registry projection plugin was used to conceal those current-tree baseline
failures. No historical pin was changed. Benchmark structure validation checked
**54 cases, zero errors**, under real process/network denial. In-memory Python
compilation passed for **26 audited/new source files**, without executing the
compiled code. `git diff --check` passed; authored Markdown/JSON/test whitespace
checks passed, and all JSON reports parsed. Raw pytest diagnostic logs retain
their original output formatting.

Final preservation: **1,852/1,852 existing Git-visible files unchanged**, all eight
already-missing paths still missing, and only additive audit/test/report artifacts
added. This includes the protected runtime, SYNTH, reflection/lifecycle, executor,
registry and reversal history, as well as unrelated working-tree edits.

Old contract rewritten: **false**. COMPAT.1 retroactively changed: **false**.
Provider-specific proof equivalent under unchanged requirement: **false**.
Stop after this contract decision; no remediation implemented.
