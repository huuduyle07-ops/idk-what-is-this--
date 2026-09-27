# OPS.PATCH.1 — Byte-Preserving Multi-File Apply & Rollback

**Date:** 2026-08-31
**Track:** OPS
**Status:** complete
**Prerequisite:** CHECK.LIVE.1
**Kind:** live production fix — not a report, plan, preview, audit or shadow experiment

First phase of the product-recovery sprint triggered by the 2026-08-30 black-box
field test. It modifies the executor that real multi-file patch runs go through.

---

## 1. The defect

Real black-box testing found that the multi-file patch path on Windows rewrote
line endings in every file it touched.

`patching/patch_plan_executor.py` read targets with `Path.read_text()` and wrote
create, replace and rollback with `Path.write_text()`:

| Site | Old call | Effect |
|---|---|---|
| original capture | `target.read_text(encoding="utf-8")` | universal newlines: `\r\n` and lone `\r` collapse to `\n` |
| `create_file` write | `target.write_text(content, encoding="utf-8")` | text mode, `newline=None` → every `\n` becomes `os.linesep` |
| `replace_snippet` write | `target.write_text(new_text, encoding="utf-8")` | same |
| rollback write | `path.write_text(original, encoding="utf-8")` | same |

The rollback baseline was itself a *string* (`RollbackEntry = tuple[Path, str | None]`),
already stripped of its real terminators by `read_text()`, so restoring it meant
decoding and re-encoding through the same translation.

```
original LF repository
    ↓
multi-file patch apply on Windows
    ↓
Python text newline translation
    ↓
entire touched file becomes CRLF
    ↓
validation fails
    ↓
rollback through the SAME faulty write
    ↓
file "restored" — with a whole-file line-ending diff
```

Observed on this host before the fix (`os.linesep == '\r\n'`):

| Case | Input bytes | Result before | Correct? |
|---|---|---|---|
| LF replace | `one\nold\nthree\n` | `one\r\nnew\r\nthree\r\n` | no |
| CRLF replace | `one\r\nold\r\nthree\r\n` | `one\r\nnew\r\nthree\r\n` | only by accident on Windows |
| create, `\n` payload | `x = 1\ny = 2\n` | `x = 1\r\ny = 2\r\n` | no |
| LF rollback | `one\nold\nthree\n` | `one\r\nold\r\nthree\r\n` | **no — sha mismatch** |
| mixed newline | `lf\ncrlf\r\nold\nend\r\n` | `lf\r\ncrlf\r\nnew\r\nend\r\n` | no — fully normalised |
| UTF-8 BOM | `<BOM>one\nold\n` | `<BOM>one\r\nnew\r\n` | BOM kept, newlines wrong |

The defect is bidirectional: on POSIX the same code turns a CRLF file into LF.

**Field-test shape.** The model produced a correct five-operation feature plan;
it applied; validation later failed for unrelated validation plumbing; rollback
ran; three files were left with line-ending-only changes; roughly 117 lines
appeared changed with zero intended semantic difference.

## 2. The invariant

`"rollback restores original content"` is insufficient. The requirement is:

```
existing file:  original bytes → replace_snippet → only the intended
                textual replacement may differ

rollback:       state after rollback == exact original bytes
created file:   state after rollback == original absence
```

Every regression test therefore compares `read_bytes()`, and rollback tests
compare SHA-256 as well. `read_text()` applies the same universal-newline
translation that hid the defect, so a text-level assertion passes against the
*broken* executor and proves nothing.

## 3. Reference implementation

`patching/patch_engine.py` — the single-file path — was already correct and was
used as the model, not rewritten:

- reads raw bytes and decodes them itself, so the text view and the byte view
  stay consistent (`code_bytes.decode("utf-8", "replace")`);
- detects the file's convention with `newline = "\r\n" if "\r\n" in text else "\n"`;
- writes through `open("w", encoding="utf-8", newline=newline)` or `write_bytes`;
- rolls back with `shutil.copy2` from a `.bak`, which is byte-exact.

## 4. What changed

### 4.1 Existing-file replace — byte-localised splice

The narrowest safe strategy (option A of the phase brief): match on the text
view, but splice the *raw* text, so bytes outside the match are never rewritten.

1. `original_bytes = target.read_bytes()`; strict `decode("utf-8")`.
   A file that is not valid UTF-8 fails **here**, before any write, exactly as
   `read_text()` used to fail it.
2. Build the universal-newline view (`_universal_newline_view`) — the identical
   text `read_text()` produced — plus the LF-view positions at which a `\r\n`
   was collapsed. One int per CRLF line, not per character.
3. `original.find(target_snippet)` — the same literal search as before.
4. Map the match span back with `_raw_offset` (`lf_index + bisect_left(collapsed, lf_index)`).
5. Render the patched snippet in the newline convention of the replaced region,
   falling back to the file's own (`_newline_for`).
6. `new_raw = raw[:start] + replacement + raw[end:]`, then `write_bytes`.

Because `raw_text` came from a *strict* decode, re-encoding the untouched
slices reproduces the original bytes exactly — that is what makes the
prefix/suffix guarantee hold, multi-byte UTF-8 included.

### 4.2 Created files — payload bytes, verbatim

`target.write_bytes(content.encode("utf-8"))`.

A new file has no existing convention to preserve, so the policy is explicit:
**the payload's own newline bytes are what lands on disk.** A model payload
containing `\n` stays `\n` on Windows; one that deliberately carries `\r\n`
keeps it. The host OS no longer converts the payload.

### 4.3 Rollback — original bytes

`RollbackEntry` is now `tuple[Path, bytes | None]` and rollback calls
`path.write_bytes(original)`. Bytes rather than text because a text baseline
must be decoded and re-encoded to be written back, and that round trip
re-applies the translation. Restoring captured bytes preserves terminators,
encoding and BOM without reinterpreting any of them.

Created files are still deleted (`unlink`), restoring absence rather than an
empty stub.

### 4.4 Failure safety

Rollback entries are now registered **before** their write, not after. A write
that fails part way through is therefore still reversed, instead of leaving a
truncated file with no rollback record. Combined with capturing the original
bytes before mutation, the executor never writes first and discovers afterward
that exact restoration is impossible.

## 5. What deliberately did not change

**Matching.** Snippet matching still runs against the universal-newline view,
so which snippets ground is bit-for-bit the decision it was before — including
the long-standing behaviour that a `\n` snippet matches a CRLF file. No
whitespace-normalised, newline-fuzzy or AST fallback matching was added. Had
matching moved to raw bytes, patches that used to apply to CRLF checkouts would
have started failing; had it been loosened, literal grounding would have weakened.
It did neither.

**Ordering and transactions.** Operation order and LIFO rollback are untouched.
LIFO with a per-op baseline is already what collapses several operations on one
file back to the state before the *first* of them; no transaction redesign was
needed, only correct baselines.

**Authority and policy.** Patch safety, target eligibility, `AUTO_PATCH_ENABLED`,
write authorization, CTX.PATCH / CTX.APPLY, human approval, CONTROL confidence
and localization ranking are all unchanged. So is every validation policy — the
pytest command, zero-test handling, output classification and TypeScript
detection. A forced validation failure appears only as a *test fixture* for
exercising rollback.

**CHECK.1 / CHECK.LIVE.1.** Not modified, and not special-cased. A rolled-back
run now simply presents a final observed state equal to the original one; if
shadow reconciliation reads that differently than before, it is because the
fact improved.

## 6. Deltas

| Dimension | Delta |
|---|---|
| repository traversal | **zero** — only paths the plan itself names are opened, each read once |
| model calls | **zero** |
| network calls | **zero** |
| new authority | **zero** |
| benchmark cases altered | **zero** |
| single-file path (`patch_engine`) | **unchanged** |

Reading each target's bytes once is the whole cost. No whole-repo snapshot,
hashing, indexing or graph build was introduced.

## 7. Results

All measured on Windows (`os.linesep == '\r\n'`) with explicit LF/CRLF byte
fixtures, so the invariant is equally testable on POSIX CI.

| Case | After |
|---|---|
| LF replace | `one\nnew\nthree\n` — zero CRLF |
| CRLF replace | `one\r\nnew\r\nthree\r\n` — CRLF kept |
| create, `\n` payload | `x = 1\ny = 2\n` — verbatim |
| LF rollback | byte-equal **and** sha-equal |
| CRLF rollback | byte-equal |
| mixed newline | `lf\ncrlf\r\nnew\nend\r\n` — only `old`→`new` |
| UTF-8 BOM | preserved on both apply and rollback |
| multi-file success (3 files) | only intended lines changed, no CRLF, no line-count drift |
| multi-file failed validation | all three files byte-identical to originals |
| create then replace, rolled back | file absent |
| replace twice, rolled back | exact original bytes |
| partial apply failure | every earlier file byte-exact |

## 8. Known limitations

- **File metadata is out of scope.** The invariant is file *content bytes* and
  *existence*. Timestamps, ACLs, extended attributes and inode identity are not
  preserved and were never promised by this executor.
- **Directories created for a `create_file` op are not removed on rollback.**
  Pre-existing behaviour, unchanged here.
- **Non-UTF-8 targets are rejected**, as before. This phase deliberately did not
  expand into a general encoding project; UTF-8 remains the executor's
  assumption. Rollback preferring original bytes means BOM presence and exact
  terminators survive without needing to reinterpret them.
- **Mixed-newline files.** Untouched regions keep their exact bytes. The
  *inserted* snippet is rendered in the replaced region's convention, falling
  back to the file's dominant one — the file is never wholesale normalised.
- **Registry schema.** `automation_level` has no value meaning "human-authored
  production bug fix"; its five values describe how much power an *automation*
  is granted. `LOCAL_1_PREPARE` is recorded as the closest honest value, with
  `writes_real_repo: true` carrying the fact that matters. This is documented
  rather than papered over by labelling a live fix observation-only.

## 9. Benchmark blind spot

The existing 54 benchmark cases did not catch this, and were **not altered by
this phase**. They compare semantic outcomes, and universal-newline reads hide a
line-ending-only diff entirely — byte-level newline fidelity was never an
asserted dimension. A future product black-box suite should assert bytes.

## 10. Files changed

| File | Change |
|---|---|
| `patching/patch_plan_executor.py` | byte-oriented create / replace / rollback |
| `tests/test_patch_write_byte_fidelity.py` | new — 35 byte-level regressions |
| `tests/test_phase_registry.py` | OPS.PATCH.1 registration tests; `writes_real_repo` conservatism rule |
| `tests/test_phase_picker.py` | phase-count assertions |
| `docs/roadmap/phase_registry.json` | OPS.PATCH.1 entry (additive splice) |
| `docs/designs/2026-08-31-…-apply-and-rollback.md` | this document |

## 11. Readiness for VALIDATE.LIVE.1

Not started here, deliberately. What OPS.PATCH.1 hands it: a rollback that
restores exact original bytes, so a validation failure no longer leaves residue
that would confuse the next phase's signal. The field test's validation-plumbing
failure — the reason rollback ran at all — is still unfixed and is
VALIDATE.LIVE.1's subject.
