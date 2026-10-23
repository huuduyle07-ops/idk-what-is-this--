# SYNTH.EXEC.PREP.CONTROLLER.IDENTITY.ENCODING.CONTRACT.1

**SYNTH_EXEC_PREP_CONTROLLER_IDENTITY_ENCODING_CONTRACT_1_COMPLETE**

Future owner/relation scalar IDs are non-secret opaque local handles for lookup, correlation and uniqueness. No scoped scalar is a bearer credential or authentication proof. This additive contract freezes future values inside the unchanged generic string schema. No owners or identity generators are implemented.

The scalar grammar is one field-family prefix plus exactly 16 lowercase ASCII hexadecimal digits, with suffix value 1..9223372036854775807. Reject zero, uppercase, wrong prefix, alternate width, escapes in the decoded scalar, normalization and coercion. Each nonnull ID is exactly 17 content bytes and 19 canonical quoted JSON bytes; it has **zero required entropy bits** and is public. The frozen ensure_ascii=true encoding adds no escaping expansion for these values.

All classes independently retain histories across an otherwise unbounded process-incarnation lifetime; no audited class has a smaller universal count bound. This phase chooses a 63-bit nonwrapping allocation capacity consistent with C:/framing/primitive_rules/positive_int; that historical rule constrains message sequences, not the existing generic ID strings, and does not mandate this choice. This is a bounded availability policy, not a cryptographic minimum. Equal widths reflect the independently shared retention/capacity obligation, not a demand that semantic classes match or a byte-fit objective. Both 32-bit and 63-bit handles can be security-correct with explicit exhaustion; a smaller bound has no independent class-specific evidence here. Full SHA256 would add authentication responsibilities these scalars do not have.

All eight semantic classes independently use this allocation primitive and the same explicit capacity policy. Their roles, authenticated domains, aliases and lifetimes differ. Existing 64-hex digest/HMAC conventions are not used to determine handle width.

Frozen source keys: C = `docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/contract.json`; S = `docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_CONTRACT_1/message_schema.json`; W = `docs/roadmap/phases/SYNTH_EXEC_PREP_WORKSPACE_CONTRACT_1/contract.json`; P = `docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1/contract.json`; B = `docs/roadmap/phases/SYNTH_EXEC_PREP_CONTROLLER_BUDGET_PROOF_1R/budget_witness.json`.

| Semantic class | Field(s) | Prefix / suffix grammar | Content / quoted bytes | Role and lifetime |
| --- | --- | --- | ---: | --- |
| WORKSPACE_OBJECT_REFERENCE | `workspace_capability_id` | `w[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Lookup exact original workspace capability object; spelling alone conveys no workspace or preparation permission. One original workspace relation through terminal evidence and permanent namespace tombstone. |
| CONTROLLER_OBJECT_REFERENCE | `controller_identity` | `c[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Lookup exact retained controller owner-object relation whose authenticated record binds source, protocol, original workspace and incarnation facts. One original controller object; never reassigned to a replacement controller. |
| EXCLUSIVE_OWNER_RELATION_REFERENCE | `exclusive_owner_relation_id`, `writer.accounted_original_relation_id` | `x[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Lookup authenticated original exclusive-owner/writer accounting relation. Writer field is an alias of an actual retained original relation, never a new ID minted for observation. One exact original exclusive relation. Minimum-path accounted controller writer uses the same exclusive_owner_relation_id. Other writer relations require their own truthful authenticated original mapping; unresolved borrower/handoff encodings are not fabricated. |
| SINGLE_OPERATION_ADMISSION_REFERENCE | `admission_relation_id` | `a[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Lookup separately authenticated owner admission bound to exact originals, purpose/tag, attempt, request, operation, generations, observation and fence; scalar is explicitly not authority. One admitted operation, permanently spent/rejected/terminal thereafter; no replay or refund. |
| PERMANENT_PREPARATION_ATTEMPT_REFERENCE | `preparation_attempt_id` | `t[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Bind the one permanent materialize -> compile attempt and its original spent facets, same workspace/controller and failure history. One attempt forever in retained namespace history; no reuse, reopen, refund or new attempt under old value. |
| SINGLE_REQUEST_CORRELATION | `request_id` | `r[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Owner-generated unique request correlation key; exact request/response equality plus owner admission/replay history rejects aliasing. One exchange; duplicates or lost replies do not authorize redispatch. A permitted cleanup re-observation requires a fresh request. |
| SINGLE_OPERATION_CORRELATION | `operation_id`, `process.admitted_operation_id`, `writer_handle.admitted_operation_id`, `active_operation_id` | `o[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Owner-generated unique admitted operation identity. Nonnull inventory/active references copy the exact bound operation_id and do not allocate new values. One original operation; no mutation retry after response loss; fresh operation cannot reuse request/admission IDs. |
| AUTHENTICATED_DEADLINE_RELATION_REFERENCE | `deadline_identity` | `d[0-7][0-9a-f]{15}`, nonzero suffix | 17 / 19 | Lookup one authenticated immutable monotonic deadline relation shared by this attempt from materialization through compile; not a timestamp, clock reading or wall-clock authenticity claim. Original attempt budget relation never reset, extended or replaced to refund time; terminal record remains tombstoned. |

All class grammars above are full-string matches with the additional shared positive-range predicate. Each inherits the generation, entropy, collision, case, secrecy, serialization, process-local namespace, owner/domain separation and terminal rules below.

`process.admitted_operation_id`, `writer_handle.admitted_operation_id` and `active_operation_id` are nullable aliases of the exact already-bound `operation_id`; a nonnull projection allocates nothing. The two successful quiescent response layouts preserve their truthful nulls. Each JSON null costs four bytes. `writer.accounted_original_relation_id` references the actual authenticated original accounting relation; in this minimum layout it is the same exclusive-owner relation, never an invented writer ID.

`authorized_borrower_relation_id` is an unestablished borrower relation and `handoff_identity` an unestablished handoff relation. Both mandatory keys are truthfully null on this minimum path. No nonnull grammar, borrower capability or handoff authenticator is invented.

**Authentication and security responsibilities.** The original custom owner-object type is checked exactly, as are built-in schema scalar types. Registry identity, issuing process, original upstream graph, independent domain/role-separated HMAC over retained canonical bytes and current eligibility remain mandatory. The frozen controller contract explicitly says scalar admission ID is not authority (C:/authority_separation/scalar_admission_id_is_authority), and its generic id primitive is a reference only (C:/framing/primitive_rules/id). W:/exact_live_object and W:/authentication supply original-object, registry, PID, HMAC, fingerprint and permanent-tombstone requirements.

JSON scalars may correlate an already authenticated retained exchange. Neither a wire ID nor JSON reconstruction creates a registry entry or original object. A controller must obtain separately authenticated admission through its future authenticated original channel; the scalar admission ID alone never suffices.

No scoped scalar crosses a boundary as a bearer capability under the frozen contracts. If an implementation accepts ID-only lookup as permission, this encoding is inapplicable: stop unresolved and require a separately reviewed capability/authentication contract before effects. Making the handle longer does not repair an ID-only authority path.

A malicious caller may know or guess all IDs and supply copied values/objects. Arbitrary execution that can mutate private registries, steal secrets or bypass validators is outside the owner abstraction; handles do not provide memory isolation.

| Threat | What encoding contributes | Mandatory protection outside the scalar |
| --- | --- | --- |
| accidental collision | Injective fixed-width positive integer representation with disjoint family prefixes; encoding alone cannot ensure allocation uniqueness. | linearizable nonwrapping reservation; collision check against reserved/live/terminal/tombstone ledger; no overwrite or reuse |
| malicious caller guessing another live ID | Predictable by design; no protection or secrecy claim. | exact original object/type; owner registry; authenticated bound admission and HMAC; current eligibility/fence |
| replay of stale ID | Never-reused spelling disambiguates history but is not freshness. | permanent spent/terminal/tombstone records; current observation sequence/challenge; generations and local fence; no mutation rerun on lost response |
| cross-process copy | Process-local namespace may repeat text; spelling is not a portable capability. | issuing PID; original process incarnation and independent owner secret; exact original process-local registry/object; no reconstruction or fork inheritance acceptance |
| cross-owner substitution | Family prefix rejects mismatched classes; same class does not identify the issuer cryptographically. | process-incarnation reservation ledger; owner/module/phase/schema/domain/role authenticated binding; exact original upstream graph and registry |
| same-process forged dataclass with copied scalar IDs | Copies validate lexically; no authority claim. | exact type; registry original is supplied object; retained canonical payload and HMAC; original upstream graph |
| PID reuse | No PID encoded; no cross-incarnation uniqueness claim. | new process-local independent secret; no old registry/object restore; original process-incarnation checks; PID equality alone insufficient |
| registry reuse after terminal state | Nonwrapping namespace must persist across registry replacement. | permanent terminal history; no re-registration/reopen; fail closed on lost namespace continuity |
| ID reuse after tombstone | Reuse is forbidden for the whole process-incarnation namespace. | burned reservation retained; tombstones never recycled; exhaustion rejects issuance |
| serialization/reconstruction | ASCII canonical text may be serialized as data only. | no restore/import API; exact original object and original registry; authenticated retained relation rather than deserialized fields |
| JSON copy | Identical bytes are valid correlation data. | no authority from JSON; authenticated retained exchange and original owner admission; exact original objects remain required |
| wrapper/subclass | No effect; scalar spelling does not certify object type. | exact type comparison rather than isinstance; registry object identity |
| immutable-binding substitution | IDs do not hash their contents. | unchanged stable fingerprint of immutable bindings; HMAC and retained canonical bytes; current mutable state authenticated separately |

**Generation and lifetime semantics.** These are declarative future obligations, tested by grammar/static/arithmetic fixtures. They are not live issuance tests or an allocator implementation.

- **namespace.** One retained allocation namespace per future issuer process incarnation, shared across every instance of the participating future owner domains; never one resetting counter per owner object.
- **reservation.** A single abstract monotonic reservation ledger assigns a fresh integer across all participating families and owners. Family prefix selects semantic domain; exact owner module/phase/schema/role and original relation are additionally authenticated. Independent owner instances may not start their own overlapping namespace.
- **thread safety.** Reservation, increment and issued/tombstoned collision check are one linearizable critical section. No assumption about the GIL. Owner registration may follow, but any reserved value stays burned on failure, exception or cancellation.
- **collision handling.** At reservation, reject any existing reserved, active, terminal or tombstoned key before claiming it. Registration may publish only that issuer's own newly created reservation, once; reject a foreign reservation or an already published/terminal/tombstoned ID. An unexpected collision or missing namespace continuity is an invariant failure: no overwrite, no retry with the same value, no alias, no dispatch; invalidate affected eligibility and retain burned values.
- **reuse forbidden.** true
- **wrap.** Never wrap, truncate, modulo, saturate or restart; reject allocation before exceeding 9223372036854775807. Exhaustion withdraws new issuance, not cleanup of retained originals.
- **fork boundary.** PID mismatch invalidates all inherited originals and allocator state before validation or issuance. A forked child may not continue an inherited namespace or lock; it needs a new empty process-incarnation namespace and independently initialized owner secrets through a future reviewed initialization path. No such path is implemented here.
- **restart boundary.** A fresh process incarnation may repeat printable strings only in a disjoint new namespace with new secrets and empty original-object registry. Old objects, JSON and HMACs cannot be imported or reattached. PID equality alone never permits continuity, including after PID reuse.
- **reload boundary.** Module reload, registry recreation, allocator replacement or secret rotation cannot reset counters while any namespace originals/tombstones can be recognized. Retain namespace continuity or fail closed for new issuance and old eligibility. No rehydration from serialized IDs.
- **lifetime.** Reservation histories and permanent terminal tombstones last to process-incarnation termination, independently of whether the original operational object remains live. Strong originals/graph remain as required by their owning contracts.
- **terminal.** Terminal records may authenticate historical evidence but cannot restore readiness. Never remove a tombstone to free a scalar; no namespace recycling after registry cleanup.
- **domain separation.** Prefix validation rejects class substitution before lookup. A prefix is not an HMAC domain: independent existing owner secret/domain/role separation and exact original graph comparisons remain mandatory for cross-owner substitution within the same class.
- **allocation is not coordination.** The abstract reservation ledger concerns name uniqueness only. It does not hold existing private owner locks, bridge owner stores, authenticate an admission, spend a facet or establish a cross-owner effect transaction. Concrete synchronization remains a future implementation obligation.
- **caller control.** Only the authenticated issuing owner reserves a new value; callers may echo an already bound value but cannot select, register, overwrite or alias it. Parse/equality checks use exact strings without coercion.
- **random alternatives.** No scoped scalar requires unpredictability. Random or cryptographic random allocation is not the accepted primitive for these future fields; the frozen historical random conventions remain untouched. Observation challenges and independent HMAC secrets retain their stronger existing requirements.

No accidental-collision probability is needed for a correctly reserved nonwrapping sequence. These non-secret handles remain unsuitable for ID-only authorization; the frozen architecture requires the original-object/authenticated-owner conjunction. An unexpected duplicate is an invariant failure and must fail closed rather than overwrite a live or historical relation. Repeating textual strings in a new disjoint process incarnation is not namespace reuse or permission to restore old objects.

`request_id` and `operation_id` require owner reservation, freshness, unique retained history, exact request/response equality and duplicate rejection, not cryptographic randomness. Caller-selected aliases are forbidden. The owning admission authenticates exact request/operation bindings. Lost mutation replies never authorize retry. The permanent attempt binds materialize through compile with no reopen, refund or attempt reuse. `deadline_identity` references the same authenticated immutable monotonic 5000ms attempt deadline from the frozen controller bounds; it never encodes a raw clock value or permits reset.

**Controller and digest separation.** `controller_identity` references only the exact retained controller owner object. Its authenticated record still binds all C:/identity/must_bind facts. Stable implementation identity remains separate exact source bytes/hash/size, executable, interpreter, image, protocol and bootstrap/environment/policy. Incarnation remains separately bound by controller_generation and original process/channel facts; their encoders are untouched. Source hash, protocol ID, module name and PID cannot stand in for the owner-object handle.

ID != stable_fingerprint != HMAC != capability. The separate stable fingerprint stays an unchanged 64-lowercase-hex SHA256 digest of authenticated immutable identity; mutable current state/freshness needs its own authentication. A digest alone never restores original-object authority.

**Existing owner comparison.** [Source audit](existing_owner_audit.md) and existing_owner_audit.json record exact generator, authentication, registry/tombstone anchors and source hashes. AST/source tests check these without importing the owners.

| Existing family / variant | ID(s) | Existing generator / width | Why not mandatory for future handles |
| --- | --- | --- | --- |
| authorization_ids / legacy | issuance_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| authorization_ids / pinned | authorization_id, proof_context_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| runtime_lease_ids / legacy | lease_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| runtime_lease_ids / pinned | lease_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| provider_ids / pinned_exact_provider_and_runtime_attachment | proof_context_identity, RuntimeProviderAttachment.receipt_id, PinnedJavaExactProviderReceipt.receipt_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| reflection_admission_ids / legacy | admission_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| reflection_admission_ids / pinned | admission_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| reflection_lease_ids / legacy | lease_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |
| reflection_lease_ids / pinned | lease_id | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |

Historical authorization/provider insertions do not all explicitly retry collisions, and weak registries alone do not retain permanent nonreuse. Those omissions are not adopted: future handles require atomic collision checks and permanent burned/tombstoned history. Existing owners remain byte-identical.

**Owner-width-only budget substitution: CONDITIONAL.** Only frozen budget_witness.json data is read. BUDGET.PROOF.1R is not executed. The reference profile is candidate_A_writer_lower_widths_class_5_digits. Kernel identities and modes retain their previous unresolved lower-width placeholders. The reference writer topology and Candidate-A-only fixed container/generation/framing assumptions remain unchanged. All required nullable keys remain.

| Family | Content bytes if nonnull | Materialize occurrences | Compile occurrences | Delta from one-byte relaxation |
| --- | ---: | ---: | ---: | ---: |
| workspace_capability_id | 17 | 2 | 2 | 64 |
| controller_identity | 17 | 1 | 1 | 32 |
| exclusive_owner_relation_id | 17 | 1 | 1 | 32 |
| writer.accounted_original_relation_id | 17 | 1 | 1 | 32 |
| admission_relation_id | 17 | 0 | 0 | 0 |
| preparation_attempt_id | 17 | 1 | 1 | 32 |
| request_id | 17 | 1 | 1 | 32 |
| operation_id | 17 | 1 | 1 | 32 |
| deadline_identity | 17 | 0 | 1 | 16 |
| process.admitted_operation_id | 17 | 0 nonnull, 1 null | 0 nonnull, 1 null | 0 |
| writer_handle.admitted_operation_id | 17 | 0 nonnull, 2 null | 0 nonnull, 2 null | 0 |
| active_operation_id | 17 | 0 nonnull, 1 null | 0 nonnull, 1 null | 0 |
| authorized_borrower_relation_id | nonnull deferred | 1 null | 1 null | 0 |
| handoff_identity | nonnull deferred | 1 null | 1 null | 0 |

Admission IDs occur only in requests and contribute no response bytes. Request inputs remain in their own direction and add zero stdout bytes. The exclusive relation occurs four times including writer aliases. The 17 nonnull occurrences split 8 materialize / 9 compile; each grows by 16 bytes.

| Conditional response accounting | Previous bytes | Owner delta | Projected bytes |
| --- | ---: | ---: | ---: |
| Materialize response | 3251 | 128 | 3379 |
| Compile response | 4809 | 144 | 4953 |
| Response payload sum | 8060 | 272 | 8332 |
| Candidate-A-only response framing | 8 | 0 | 8 |
| Candidate-A-only framed sum | 8068 | 272 | 8340 |

**OWNER_ENCODING_ALONE_EXCEEDS_8192_FOR_CANDIDATE_A**, conditionally: remaining margin -148 bytes, excess 148 bytes. The unchanged formula is 8068 + 17*(17-1) = 8340. Uniform 32/64-byte sensitivity substitutions independently recover historical 8595/9139. Full field paths and exact substitution evidence are in budget_projection.json and budget_ledger_audit.json.

This settles the scoped owner-encoding question only. It neither establishes an attainable successful execution witness nor proves universal budget feasibility/impossibility. Historical BUDGET_WITNESS_UNRESOLVED and its historical identity subresult are preserved as recorded. Kernel projection, complete inventory, physical mapping/framing and independent backend-generation cleanup remain separate blockers. Candidate A remains UNSELECTED. The 8192 cap and one-attempt scope are unchanged.

**Validation.** Focused tests: 154/154; benchmark --check: 54 cases, zero errors. Registry/picker baseline and after are identical: 299 collected, 292 passed, same 7 pre-existing failures and normalized diagnostic signatures. In-memory compilation, JSON, authored whitespace and configured git diff --check pass. A supplementary check with autocrlf disabled records existing CRLF lines as whitespace diagnostics; it did not change configuration or files. Preservation hashes cover 26991 existing non-cache files with no changes, deletions or outside-phase additions. No stash/reset/clean, repin, schema edit or historical rewrite occurred.

Validation host Python/Git invocations perform only the requested static checks; guarded validation starts no child process and imports no capability owners. All process/network/owner import/issuance/transition/execution/outside-phase-write audit counters are zero. All authority flags are false; all operational effect counts are zero. No Docker, live kernel inspection, target process, source materialization, javac/java, capability issuance or identity generation occurred. STOP.
