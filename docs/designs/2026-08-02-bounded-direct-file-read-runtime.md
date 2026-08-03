# CTX.READ.1 — Bounded Direct File Read Runtime

## Outcome

CTX.READ.1 creates ephemeral, task-local raw-text context from files already
selected by CTX.SELECT.1, with optional line evidence supplied by CTX.SEARCH.1.
It works without canonical identity confirmation, a canonical manifest,
indexing, vectors, embeddings, a database, parser support, an Activation Graph,
or model/API calls.

The authorized pipeline is:

```text
RepositoryInventory
→ CTX.SELECT candidate and proposed-read evidence
→ CTX.SEARCH lexical evidence
→ validated proposed read set
→ CTX.READ descriptor-bound reads
→ ephemeral Direct File Context
```

No output from this phase is write or patch authority. A later CTX.PATCH.1
gate must recheck receipt freshness before using any direct-read evidence.

## Contracts

`core/direct_context_runtime.py` validates schema version 1, the repository
root, a deterministic identity of the supplied immutable inventory, the
separate proposed-read set, unique selected paths, trusted lexical match
locations, and request budgets. Arbitrary strings are never sufficient to
authorize a read: a path must match both an immutable inventory entry and a
CTX.SELECT proposed-read record.

`compute_repository_inventory_identity()` hashes only already-supplied
inventory metadata. It does not read file contents or traverse membership.
Root or inventory-identity mismatch blocks the whole operation. Individual
sensitive, binary, missing, changed, or unreadable entries do not prevent an
independent safe entry from being read.

Each successful result and receipt states:

```text
read_authority_granted = true
write_authority = false
patch_authority = false
```

The authority is task-scoped, operation-scoped, non-persistent,
repository-contained, revocable by policy, and invalid after an identity
change. Failed outcomes return no content and grant no read authority.

## Read modes

`choose_direct_read_mode()` is a pure deterministic helper:

| Evidence | Decision |
|---|---|
| Safe file, including a single unsupported-text file, fits complete-read budgets | `full_file` |
| Medium/large file with trusted lexical matches | `match_windows` |
| Large unmatched file | bounded `explicit_ranges` header |
| Unknown size or non-readable capability | reject |

The stable modes are `full_file`, `match_windows`, `explicit_ranges`, and
`header_and_matches`. Match windows default to 40 lines before and 80 lines
after each match. Ranges are sorted and merged deterministically; adjacent or
overlapping ranges become one interval. No regex, AST parsing, tailing,
repository-wide reading, dependency expansion, or new search occurs.

## Descriptor safety

The reader reuses the CTX.SEARCH.1 descriptor boundary:

```text
validate immutable inventory entry
→ validate repository-relative path and policy
→ lstat and reject symlinks/special files
→ open read-only with O_NOFOLLOW where available
→ compare opened descriptor to inventory identity
→ read incrementally within the remaining byte budget
→ compare descriptor and current path identity after reading
```

Device, inode, regular-file mode, size, modification time, and platform-stable
creation/change-time evidence bind the operation to the inventory snapshot.
Content is discarded when identity changes during the read. No automatic
rescan occurs.

Stable file outcomes are `read_complete`,
`read_complete_with_truncation`, `file_changed_or_replaced`,
`path_not_in_inventory`, `path_outside_repository`, `symlink_rejected`,
`sensitive_file_blocked`, `binary_or_opaque`, `encoding_unsupported`,
`budget_exhausted`, and `read_failed`.

## Budgets and encoding

Hard defaults are eight files, 1 MiB total returned content, 256 KiB scanned
and returned per file, 4,000 returned lines per file, eight match windows,
eight merged ranges, and bounded excerpt lines. Runtime requests may reduce
but cannot increase those ceilings. Separate scanned/returned byte and line
counters are emitted. Higher-priority proposed files are completed first;
lower-priority omissions are explicit.

The initial decoding contract is strict UTF-8, UTF-8 with BOM, and ASCII as a
UTF-8 subset. Invalid UTF-8 returns `encoding_unsupported`; NUL/control-heavy
or known opaque content returns `binary_or_opaque`. No implicit replacement
decoding is enabled. Unsupported extensions with valid UTF-8 are returned as
`raw_text_only`, and even parser-supported files make no AST or semantic claim.

`.env.example` remains auto-readable under budget. `.env` returns an explicit
human-approval-required blocked result with no content. Private keys,
credential stores, forbidden paths, opaque binaries, and adapter-required
documents return no content; relevance cannot override these gates.

## Receipts and context artifact

`core/direct_read_receipt.py` records task and operation identifiers, inventory
identity, exact path and mode, final descriptor identity, a full-file digest
when the bounded read reaches EOF (otherwise an explicitly scoped prefix
digest), actual returned ranges, scanned/returned counters, decoding,
truncation, parser capability metadata, and raw-text understanding confidence.

`verify_direct_read_receipt()` is pure and returns `fresh`, `changed`,
`deleted`, `replaced`, or `unverifiable`. It performs no filesystem I/O and
never grants patch authority.

The `DirectFileContext` is explicitly ephemeral and always declares
`repository_completeness_claimed=false`. It reports zero indexing, manifest,
vector, embedding, graph, parser, database, model/API, search-expansion,
repository-traversal, write, and patch operations. Contents are not persisted
to canonical repository intelligence or a vector database.

## Next phase

Recommended next phase: `CTX.PATCH.1 — Direct Context Patch Candidate Gate`.
CTX.READ.1 neither starts that phase nor authorizes or applies a patch.
