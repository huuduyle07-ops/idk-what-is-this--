# RETRIEVE.LIVE.1 — Candidate Population Hygiene & Symbol Eligibility

**Track:** INDEX (ID namespace `RETRIEVE.*`) · **Status:** complete · **Date:** 2026-09-01
**Prerequisite:** OPS.VALIDATE.2

This is a live production retrieval-quality fix. It changes code real runs go
through. It is not an audit, a plan, a preview, a shadow experiment or a
report-only layer.

---

## 1. The question this phase answers

Before asking

> which candidate should rank highest?

establish

> which objects are legitimate localization candidates at all?

A program graph does two jobs that are not the same job. **Graph
representation** wants call nodes, expression nodes and file nodes; dependency
and structure are built out of them. **Localization** wants the much smaller
set of objects a person could open and edit as the likely source of a task.
Conflating the two is what let a misaligned parser fragment sit in the same
competition as an implementation symbol.

The boundary drawn here is *eligibility*, never deletion:

```
a node may exist in the graph
    and still carry  candidate_eligible = False
```

Nothing is removed. No edge is dropped. Connectivity is untouched.

---

## 2. The reported symptom, and what it actually was

Reported on the C.A.T.T.U.S self-repository (≈1,252 indexed files, ≈55,228
graph nodes, ≈26 min wall time): CONTROL localized a defect in
`core/code_dna.py::_classify_indent` to `tests/test_index_completion.py::
write_text` instead, and the graph visibly contained garbage symbols such as
`call::e(\n`, `call::n⚠️ O` and `agents/deepseek_client.py::cont`.

The measurement came first, before any production change:

| parser-level, whole repository | before |
| --- | --- |
| files parsed | 1,272 |
| files containing non-ASCII | 523 |
| files producing at least one malformed name | 413 |
| symbols extracted | 19,837 |
| **malformed symbol names** | **8,367 (42%)** |
| call names extracted | 197,682 |
| **malformed call names** | **59,957 (30%)** |

Malformed name classes: control characters (4,380 symbols / 18,094 calls),
syntax delimiters (3,285 / 32,792), embedded whitespace (702 / 9,071).

Then the decisive fact. `core/code_dna.py` produced **12 corrupt symbol names
and zero correct ones**:

```
['() -> set[str]:\n', 'e: str) -> str', 'ext: str) -> Opt', 'xt: str) -> Opt',
 'style(text: str) -> Opt', 'epo_path: s', 'ct:\n    re', 'str, dna',
 ' -> Opti', 'repo_path: str,\n  ', 'ict, mode: str = "m', '<top-level>']
```

`_classify_indent` **was not in the graph at all.** The retrieval failure was
never a ranking failure. It was an absence. CONTROL localized to
`tests/test_index_completion.py::write_text` because that file is ASCII-clean
and its symbols survived.

---

## 3. Root cause — one mechanism, not several

`core/treesitter_parse.py`:

```python
tree = parser.parse(bytes(code, "utf8"))   # byte offsets
...
return code[func_node.start_byte:func_node.end_byte]   # sliced on the str
```

Tree-sitter reports **byte** offsets into the buffer it was given. Every
extraction sliced the Python **string** with them. Byte offsets index
characters only while a file is pure ASCII. From the first non-ASCII character
onward, every symbol, call and import name is a shifted fragment of the source.

Traced on the reported file, `agents/deepseek_client.py`:

- three `⚠️` sequences, each two characters and six bytes → offsets run 4, then
  8, then 12 bytes ahead of characters;
- the real symbol `main` begins at byte 2300; character 2300 lands twelve bytes
  later, inside `content_to_review`, yielding **`cont`**;
- the identifier spans inside the emoji-bearing region decode as **`e(\n  `**
  and **`n⚠️ O`**.

All three reported examples, and all 68,324 malformed names, are this single
line. The evidence that no second mechanism was hiding behind it: slicing bytes
takes both counts to **exactly zero**.

`core/code_dna.py`'s first non-ASCII character is an em dash at byte 31 — in
the module docstring — which is why the entire file was lost.

---

## 4. Fix the producer, not the symptom

The brief asks for producer fixes over denylists, and the defect shape forces
it independently:

- `cont` is a perfectly valid identifier. **No grammar filter could ever have
  rejected it.**
- More importantly, no filter could have *recovered* `main`, `_classify_indent`
  or the other 8,367 lost symbols. Filtering addresses noise; this was loss.

`parse_code_with_treesitter` now encodes once and slices that buffer:

```python
source = bytes(code, "utf8")
tree = parser.parse(source)
...
def _decode_span(source, start, end) -> str: ...
```

`_decode_span` snaps off UTF-8 continuation bytes before decoding. Tree-sitter
node boundaries always fall on character boundaries, so the snapping matters
only for the deliberately approximate `±60` byte context windows in
`extract_execution_flow` — which can no longer emit a replacement character
into evidence text.

**Byte offsets were already the contract everywhere else.**
`patching/patch_engine.py` slices `code_bytes[node["start"]:node["end"]]` with
the same numbers. The fix aligned extraction with what the rest of production
already assumed rather than inventing a convention.

One further producer correctness fix: `graph/builder.py::resolve_call_edges`
used `edge.target.replace("call::", "")`, which mangles a name containing the
marker anywhere. It now uses `removeprefix`.

---

## 5. Defence in depth: `core/localization_candidate.py`

Deterministic, stdlib-only. Reads no file, calls no model, opens no socket,
walks no directory. Every verdict is a function of metadata indexing already
produced.

Check order is fixed, so one node always yields exactly one reason:

```
kind → source binding → source role → symbol grammar → span consistency
```

### Bounded rejection vocabulary

| reason | meaning |
| --- | --- |
| `eligible` | may enter localization competition |
| `structural_only` | real and useful to the graph, but structure or bookkeeping |
| `invalid_source_binding` | no repo-relative file, unrecognised extension, or a span that contradicts itself |
| `malformed_symbol` | cannot have come from an identifier in any language parsed here |
| `unsupported_candidate_kind` | a kind this boundary does not admit |
| `source_role_mismatch` | an implementation symbol claimed from a document, or prose claimed from source |

No prose reasons. No score, no weight, no confidence.

### Node kinds inventoried (this repository, post-fix)

| kind | count | standing |
| --- | ---: | --- |
| function | 18,949 | primary |
| call | 6,622 | structural only |
| file | 1,274 | structural only |
| class | 457 | primary |
| expression | 299 | structural only |
| type / struct | 10 | primary |
| enum / trait | 2 | primary |

**Primary localization kinds:** function, method, constructor, property, class,
struct, union, enum, trait, interface, object, record, type, and the generic
`symbol` default. **Structural-only kinds:** file, directory, module, package,
call, expression, statement, external, dependency, root.

### Call nodes

Structural only — and the reason is a missing source binding, not the `call::`
prefix. A call node carries no file, no span and no language; it is a name plus
edges. It cannot satisfy the source-binding requirement, so it never competes
with an implementation symbol as a primary defect target.

The dependency relation is untouched: `caller → call → resolved_call → callee`
all survive. Resolved-call connectivity in fact **improved**, from 406,718 to
577,996 total edges, because correct call names now resolve to real symbols.

### Symbol grammar is language-aware

Explicitly **not** `symbol_name.isascii()` and **not** `[A-Za-z0-9_]+`. The rule
is UAX-31 identifier validity per qualified segment — Python's
`str.isidentifier` — after normalising the extra characters a language allows
(`$` in JS/TS/Java/Kotlin, `~` in C/C++, `@` in C#, `'` in Rust). Qualified
names split on `::`, `.` and `#`.

So `élévation`, `面積` and `поиск` pass; `e(\n  `, `pt =` and `say("hi")` do not.
Length is never evidence: `cont` passes the grammar, which is precisely why the
producer had to be fixed.

### Source-backed candidates

A candidate must resolve to a canonical repo-relative path with a recognised
extension. Where the parser recorded a span, `0 ≤ start ≤ end` must hold, and
`end` must fit the file when the size is known. Sizes are harvested from the
graph's own file nodes, recorded while the builder already had the file open —
**no repository re-read and no second traversal.**

---

## 6. What was deliberately *not* excluded

**Tests.** `tests/test_index_completion.py::write_text` — the symbol CONTROL
used to pick — remains an eligible primary candidate. T3 and many legitimate
tasks need test-file changes, and CONTROL.SAFETY.LIVE.1, not this filter,
decides authority.

**Benchmarks, vendor, generated code.** Not excluded by this boundary. The
existing editability and generated-source policy remains authoritative. Any
vendor/generated population optimisation needs its own evidence and its own
phase.

**Documents.** In production a `.md` file produces no code symbols at all —
markdown has no entry in `TREESITTER_LANG_MAP` — so there was no role leak to
fix and none was invented. Document-kind nodes (`section`, `heading`,
`document`, `prose`) stay eligible navigation candidates and are never primary
defect targets. `source_role_mismatch` is reserved for the actual leak shape:
an implementation symbol claimed from a document, or a prose object claimed
from source. The identity-profile fallback still returns
`README.md::project_overview`, unchanged.

---

## 7. Where the boundary is wired

`core/control_engine.py`, replacing the ad-hoc `call::` / `::expr::` / "must
contain `::`" string sniffing that used to guard these paths:

1. `resolve_symbol_to_graph_nodes` — symbol → node resolution
2. `fallback_entry_nodes_from_graph` — the fallback enumerator
3. `select_entry_nodes` — the project-map direct-hit shortcut
4. `control_dfs_v2` — neighbour expansion

(4) matters: `app.py::<top-level>` is a legitimate `resolved_call` source, so
DFS reaches it from a real symbol. It is still **traversed** — the relation is
real, and its callees are still reached — but it never becomes an evidence row
of its own. A node must not become a candidate by being adjacent to one.

Classification is memoised per graph, so one CONTROL operation classifies once.

---

## 8. Index freshness

The `ProgramGraph` CONTROL localizes on is rebuilt in-process from source, so
the parser fix takes effect there immediately. The persisted code-unit index is
**incremental**, and would otherwise leave unchanged files serving symbols built
by the broken parser indefinitely — the fix would be real and invisible.

`SYMBOL_EXTRACTION_VERSION` now enters `compute_policy_fingerprint`, which the
existing delta path already turns into `force_full_reindex` **exactly once**.
No new migration system. No manual index deletion asked of users. No run forced
to rebuild — the fingerprint is stable between runs.

Old graph artifacts remain readable, and their malformed nodes are exposed as
`candidate_eligible=false` rather than pretended out of history.

---

## 9. Measured effect

| | before | after |
| --- | ---: | ---: |
| graph nodes | 56,522 | 27,613 |
| graph edges | 406,718 | 577,996 |
| call nodes | 35,528 | 6,622 |
| function nodes | 18,951 | 18,949 |
| raw selectable (old ad-hoc filter) | 19,421 | 19,418 |
| **eligible localization candidates** | **10,016** | **18,645** |
| rejected: `malformed_symbol` | 8,632 | **0** |
| rejected: `structural_only` | 37,874 | 8,968 |
| `core/code_dna.py::_classify_indent` | **absent** | **eligible, primary** |

Performance: graph build 50.59 s → 51.26 s (within noise, despite many more
resolved-call edges). Parse-only time 18.9 s → 13.3 s, because 13,610 fewer
bogus call names are produced. The eligibility filter costs 0.22 s over 27,613
nodes.

No claim is made about T6's ~26-minute wall time. Indexing and retrieval have
other known costs this phase did not address.

---

## 10. Frozen in this phase

Ranking coefficients are unchanged and pinned by test: `score_control_node`'s
weights, `compute_node_weights`' `alpha`/`beta`/`gamma` defaults, and the
identity profile's path multipliers are all asserted literally, so the
population effect stays measurable separately from any future ranking effect.

Also unchanged: CONTROL.SAFETY authority semantics, WAITER routing, patch basis,
validation, execution authorization, `core/code_dna.py`.

Deltas: **zero** model calls, network calls, embedding or vector-retrieval
calls, added repository traversals, ranking-coefficient changes, authority
changes.

---

## 11. `_classify_indent` remains broken, on purpose

Two tests pin it: a realistic nested two-space fixture still classifies as
`4space`, and the function's source is asserted unchanged.

The defect: realistically nested two-space code spends most of its indented
lines at depth two or deeper; those lines start with four spaces and outvote the
depth-one lines, so `counts.most_common(1)` reports `4space`.

It stays available as the live retrieval target for RETRIEVE.LIVE.2.

---

## 12. Known limitations

- **C++ operator overloads** (`operator()`, `operator[]`) are dropped by
  `extract_name` before they reach the graph. The grammar's rejection of
  delimiters therefore costs nothing today, but would need a kind-aware
  exception if that extractor is ever fixed.
- **`<top-level>`** is classified `structural_only` rather than removed. It
  remains a real graph node with real edges.
- **Vendor/generated population optimisation** was deliberately not attempted.
- The C# regex fallback (`fallback_csharp_symbols`) is unchanged; it produces
  well-formed but semantically noisy names when tree-sitter is unavailable.
- One existing test changed:
  `test_control_dfs_visits_high_penalty_file_neighbor_first` used bare **file**
  nodes as `resolved_call` targets, a shape production never produces (those
  edges are built from the symbol table). It now uses symbol nodes and is
  renamed; what it pins — penalty-driven neighbour ordering, and the penalty
  reaching the evidence row — is unchanged.

---

## 13. Readiness for RETRIEVE.LIVE.2

RETRIEVE.LIVE.2 (Entry Candidate Quality / Ranking) inherits a candidate
population in which every member is a source-backed symbol, and weights that
have not moved. Whether `_classify_indent` now ranks first is a ranking
question, and answering it was explicitly not this phase's job — but it is now
a question that can be asked, because the target is finally in the population.
