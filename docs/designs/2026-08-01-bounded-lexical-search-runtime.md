# CTX.SEARCH.1 — Bounded Lexical Search Runtime

Status: complete  
Phase: `CTX.SEARCH.1`  
Recommended next phase: `CTX.READ.1 — Bounded Direct File Read Runtime`

## Decision

CTX.SEARCH.1 is a repository-contained, standard-library lexical-search
runtime for the bounded requests produced by CTX.SELECT.1. It discovers
candidate evidence when vectors, embeddings, canonical manifests, canonical
identity confirmation, and canonical indexing are absent or unavailable.

The runtime grants only:

```text
candidate evidence
```

Every match and enclosing result states:

```json
{
  "execution_authority": "candidate_discovery_only",
  "read_authority": false,
  "write_authority": false
}
```

Search evidence does not authorize a later direct read or patch. CTX.READ.1 and
the human-controlled patch boundary remain separate.

## Pipeline and inventory reuse

```text
CTX.SELECT lexical request
→ validate root, request, and supplied RepositoryInventory
→ filter only supplied entries through existing path/file policy
→ open one candidate descriptor
→ compare descriptor identity with inventory-time identity
→ scan bounded UTF-8 chunks for literal terms
→ emit capped raw-text matches
→ sanitize through CTX.SELECT result consumption
```

The runtime never calls the canonical repository walker, reloads ignore policy,
or creates a replacement inventory. Iterating the already-validated
`RepositoryInventory.entries` adds zero repository-membership traversals.

`RepositoryEntry.file_identity` captures device, inode, regular-file mode,
size, modification time, and diagnostic change time when the immutable
inventory is created. Existing `(absolute_path, relative_path)` compatibility
is unchanged.

## File safety and descriptor-bound reads

Before opening, each supplied relative path must retain its safe portable shape
and resolve within the inventory root to the inventory target. The runtime then
opens that relative path read-only and compares `fstat` identity with the
inventory snapshot. It repeats both descriptor and current-path comparisons
after scanning. Symlinked search candidates are conservatively rejected, so a
missing identity, replacement, in-place content change, symlink escape, or
non-regular descriptor yields closed evidence with no excerpt.

Path-only policy runs before content access:

- `.env` requires human approval and is not searched automatically;
- private keys, credential/session stores, and security-blacklisted names are
  excluded without being opened;
- generated files require `allow_generated=True`, which permits search-only
  evidence and still grants no read or write authority;
- vendor files and hard-excluded temporary paths remain excluded;
- known opaque binary and adapter-required document types are excluded;
- an unknown extension is provisionally inspected using bounded bytes, so a
  one-file readable project remains searchable;
- NUL bytes, invalid UTF-8, or a bounded binary-control heuristic discard every
  tentative match from that file and return no excerpt.

Unknown and unsupported text never receives parser, symbol, or AST claims. Its
contract is `parser_support=unsupported` and
`file_understanding=raw_text_only`.

## Matching and ordering

Version 1 supports literal terms only. Matching can be case-sensitive or
case-insensitive. `whole_token`, boundary completeness, and the request's
whole-token preference are metadata; they do not misrepresent a substring as a
symbol match.

Identical `(path, line, offset, term)` matches are deduplicated. Returned
matches use this deterministic order:

1. request term priority;
2. include/candidate path priority;
3. repository-relative path;
4. one-based line number;
5. zero-based match offset.

The CTX.SELECT projection retains line, location, term, excerpt, literal match
kind, raw-text understanding, and candidate-only authority. Its existing
sanitizer may apply its own deterministic scoring-oriented ordering afterward.

## Bounds and truncation

The CTX.SELECT limits remain hard maxima:

| Limit | Maximum |
|---|---:|
| Terms | 32 |
| Include paths | 40 |
| Exclude paths | 64 |
| Total matches | 200 |
| Matched files | 40 |
| Excerpt characters | 240 |
| Expansion rounds | 2 |

Additional runtime caps are:

| Limit | Default | Hard maximum |
|---|---:|---:|
| Bytes scanned per file | 1,048,576 | 8,388,608 |
| Total bytes scanned | 8,388,608 | 67,108,864 |
| Matches per file | 20 | 20 |
| Single retained line chunk | 16,384 | 65,536 |
| Inventory members considered | 1,000 | 4,096 |
| Returned file outcomes | 200 | 200 |

Reads use explicit chunks no larger than the configured retained-line cap.
Only a term-length overlap is retained across chunks, so an arbitrarily long
line is never accumulated. Reaching a cap adds a stable truncation reason;
diagnostics distinguish upstream request truncation, per-file match and byte
limits, global matches, matched files, total bytes, considered files, and
returned file outcomes.

## Stable outcomes

The runtime exposes these stable statuses:

```text
search_complete
search_complete_with_truncation
no_matches
invalid_request
inventory_mismatch
file_changed_or_replaced
sensitive_file_excluded
binary_file_excluded
budget_exhausted
search_failed
```

One file failure is recorded independently and does not discard safe evidence
from other inventory members. Unknown conditions fail closed.

## Independence and non-authority

The implementation imports no vector, embedding, canonical-index, model/API,
database, subprocess, shell-search, graph, or patch subsystem. It performs no
database operation, canonical indexing, repository write, patch operation, or
model/API call. Neither the input request nor the immutable inventory is
mutated.

CTX.READ.1 is the next phase. It is not implemented or authorized here.
