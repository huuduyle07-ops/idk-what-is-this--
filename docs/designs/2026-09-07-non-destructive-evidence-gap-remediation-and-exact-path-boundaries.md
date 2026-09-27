# ANSWER.GROUND.LIVE.3 — Non-Destructive Evidence-Gap Remediation & Exact Path Boundaries

**Track:** CHECK · **Prerequisite:** ANALYSIS.MULTIROOT.LIVE.1 · **Status:** complete
**Date:** 2026-09-07

---

## 1. The failure

Round-6 black-box evidence established two concrete answer-grounding defects in
the live T5 answer. Both are remediation defects. Neither is a classification
defect: every status ANSWER.GROUND.LIVE.1/.2 assigned in Round-6 was defensible.

### Defect A — destructive remediation

The T5 answer contained true, correctly cited prose:

> deepseek-harness uses `Cordis`, where the `AgentLoop` plugin registers
> execution modes (parallel vs. exclusive), and state transitions are recorded
> per step.

`Cordis` and `AgentLoop` are not established inside the bounded evidence symbol
universe this run acquired, so ANSWER.GROUND marked them
`unverified_model_assertion`. That classification is conservative but valid.

The remediation then deleted the **entire containing sentence** — and because
`_sentence_bounds` split on `[!?.]\s+`, the abbreviation `vs.` was read as a
sentence boundary, so the deletion started mid-clause:

```
IN : ... the `AgentLoop` plugin registers execution modes
     (parallel vs. exclusive), and state transitions ...
OUT: exclusive), and state transitions ...
```

Measured on the reconstructed Round-6 T5 answer: **419 characters deleted**, one
of two bullets destroyed, section 3 emptied entirely, and the `e.g.` clause cut
to a fragment. True, user-visible, correctly cited content was destroyed in
order to retract two entities.

### Defect B — path grammar was not extension-boundary safe

`_ENTITY_RE` built its extension alternation as `"|".join(...)` over the
declaration order of `COMMON_REPOSITORY_EXTENSIONS`, with no boundary assertion
after the extension. A supported extension could therefore match as a *prefix*
inside a longer dotted token:

| answer text | Round-6 finding |
|---|---|
| `args.cmd` | fabricated file claim `args.c` |
| `t.json` | truncated to `t.js` |
| `_pytest.capture.CaptureFixture` | fabricated file claim `_pytest.capture.C` |
| `Cordis.plugin` | fabricated file claim `Cordis.pl` |

Reproduction also found three cases the bug report did not list: `config.json`
→ `config.js`, `module.cpp` → `module.c` and `src/app.tsx` → `src/app.ts`. The
gate was reporting fabrication findings for file claims nobody made, and was
silently mis-citing real files whose extension happened to have a shorter
supported prefix.

---

## 2. The primary epistemic distinction

`unverified_model_assertion` means **not established by the current bounded
evidence**. It does not mean **proven nonexistent**.

ANSWER.GROUND never walks the repository, never queries an index and never
builds a graph. It reads what the run already acquired. That is enough to
report *"I cannot support this from what I have"* and structurally insufficient
to report *"the repository does not contain this."*

This matters most in exactly the Round-6 case. `Cordis` and `AgentLoop` really
do exist in deepseek-harness; the run simply never acquired the files that
declare them. The correct product behaviour is an evidence gap, not a denial —
and this phase does **not** rescue them with a repository-wide scan, because
that would trade a wording defect for a traversal the boundary forbids.

---

## 3. What this phase does not do

Not whole-repository symbol indexing. Not broader answer fact checking. Not
semantic model verification. Not a sentence parser. Not retrieval, CONTROL,
analysis-evidence ranking, answer generation or authority work.

No change to retrieval. No change to analysis evidence selection. No enlargement
of the symbol universe. No model call. No network call. No repository traversal.
No change to patch/write/execution authority. `_classify_indent` untouched.

---

## 4. The design

### 4.1 The remediation unit is the entity span

The hard invariant:

```
unsupported entity span  !=  containing sentence
```

`_annotate_unsupported_spans` replaces the delete-the-sentence pass. It
**inserts and never deletes**, so text before the entity, text after it,
punctuation, citations, bullets and clause structure survive byte for byte:

```
`Cordis` → `Cordis` (not established in the current evidence)
```

Remediation no longer consults sentence bounds at all. `_sentence_bounds`
remains for the two unrelated purposes it already served — hypothetical-cue
context in `_is_hypothetical_context`, and sentence-local path context for
ambiguity resolution in `_sentence_local_paths` — and controls nothing about
what survives. `vs.`, `e.g.` and `i.e.` therefore cannot influence remediation,
because remediation never asks where the sentence ends.

**Position stability.** Insertions are applied right to left over the accepted
points, so every remaining offset stays valid regardless of how many entities
a paragraph carries.

**Overlap ownership.** Spans are taken in reading order, longest first; a span
overlapping an already-accepted one is skipped for annotation. One span is
annotated exactly once even where the path and symbol grammars could both claim
it. Both findings are still reported — only the text edit is deduplicated.

**Markdown safety.** `_annotation_point` places the marker after a closing
delimiter when the span sits *directly* inside one of `` ` ` ``, `( )`, `[ ]`,
`" "`. Without it, `[the loop](docs/loop.md)` would become
`[the loop](docs/loop.md (…))` — markdown damage rather than a downgrade.

### 4.2 Structured fields stay field-local

A typed symbol field is one claim whose span is the whole value, so the same
span-local rule yields an explicit unverified value:

```json
"symbol": "IndentationNormalizer (not established in the current evidence)\n\nRepository evidence gap: …"
```

The bounded gap statement is retained (it is what LIVE.2 already put there), and
structured-field remediation is still never converted into prose rewriting.

### 4.3 The evidence-gap wording

The closing clause is the epistemic boundary, not politeness:

> Repository evidence gap: the model named "X", but the reference is not
> established in the current evidence for LABEL, so I am not treating it as a
> real source location. This check reads only the evidence this run acquired,
> so that is an evidence limit and not a finding about whether LABEL contains
> it.

No categorical "does not exist in the repository" is reachable from this gate.

### 4.4 The path grammar

Two changes, both pinned by test.

**Longest extension first**, constructed rather than inherited:

```python
_COMMON_REPOSITORY_EXTENSIONS = "|".join(
    sorted(COMMON_REPOSITORY_EXTENSIONS, key=lambda item: (-len(item), item))
)
```

**A post-extension boundary** inside the path group:

```python
_EXTENSION_BOUNDARY = r"(?![A-Za-z0-9_])"
```

The class is ASCII on purpose. It is the exact complement of the ASCII
lookbehind already guarding the left edge and of `_PATH_PART` itself, and a
Unicode `\w` would additionally *stop finding* `main.py` inside non-Latin prose
— a false negative, which is the wrong direction for a truthfulness gate and a
localization behaviour change T6 forbids.

Before:

```python
rf"(?P<path>(?:{_PATH_PART}[\\/])*{_PATH_PART}\.(?:{_COMMON_REPOSITORY_EXTENSIONS}))"
rf"(?:::(?P<symbol>…))?(?::(?P<line>[1-9][0-9]*))?"
```

After:

```python
rf"(?P<path>(?:{_PATH_PART}[\\/])*{_PATH_PART}\.(?:{_COMMON_REPOSITORY_EXTENSIONS}))"
rf"{_EXTENSION_BOUNDARY}"
rf"(?:::(?P<symbol>…))?(?::(?P<line>[1-9][0-9]*))?"
```

`::symbol` and `:line` are unaffected — neither `:` nor `/` is a word character
— so `file.py::Class.method` and `main.py:12` stay single coherent entities.

---

## 5. Measured on the reconstructed Round-6 T5 answer

Two-root bounded evidence, no provider call, insert-only remediation.

| | before | after |
|---|---|---|
| characters deleted from the answer | 419 | **0** |
| bullets surviving (source 2) | 1 | **2** |
| headings surviving (source 3) | 3 | 3 |
| repository-qualified citations (source 7) | 7 | 7 |
| mid-clause cut at `vs.` | yes | **no** |
| fabricated extension-prefix path findings | `args.c`, `t.js`, `Cordis.pl`, `_pytest.capture.C` | **none** |
| findings | 15 | 13 |
| median grounding time | 0.001010 s | 0.000949 s |

**Insert-only proof.** Removing every inserted marker from the grounded body
reproduces the source answer exactly (modulo the single trailing newline the
gap-statement seam consumes): character delta 252 = 6 markers × 42 characters.
The same operation on the Round-6 body does not recover the source, because 419
characters no longer exist.

---

## 6. Boundaries

| dimension | delta |
|---|---|
| model calls | 0 |
| network calls | 0 |
| filesystem traversal | 0 |
| graph / index / embedding | 0 |
| retrieval | unchanged |
| analysis evidence selection | unchanged |
| write / patch / execution authority | unchanged |

Statically pinned: no `os.walk`, `rglob`, `glob(`, provider import, network
import, `core.retriever`, `core.indexer` or authority setter may appear in
`core/answer_entity_grounding.py`, and no T5-specific symbol allowlist may be
smuggled in as a fix.

---

## 7. Known limitations

- **The annotation is verbose.** Every occurrence of an unsupported entity is
  marked, so an answer that names one entity ten times carries ten markers.
  Annotating only the first occurrence would read better and was rejected:
  a later unmarked occurrence still reads as established fact, which weakens
  LIVE.2. Truthfulness wins over terseness.
- **`Cordis` and `AgentLoop` remain unverified.** They exist in the real
  deepseek-harness; this run never acquired the files declaring them. Rescuing
  them needs acquisition, not grounding, and is deliberately not done here.
- **Multi-root gap labels degrade to "the relevant repository"** when an
  unsupported entity binds to no repository. That is pre-existing LIVE.1/.2
  behaviour in the two-root case, and it is honest — the gate genuinely cannot
  say which universe the claim was aimed at.
- **A pre-existing LIVE.2 grammar quirk was found and not fixed:**
  `parse_symbol_text` rejects `Cc.dd` because `cc` is a supported extension, so
  a qualified symbol whose owner is spelled like an extension is never extracted
  as a claim. That lives in `core/repository_symbol_membership.py`, which is out
  of this phase's scope.
- **`t.json` is still classified as a path claim.** That is correct — it is a
  file spelling — and it is downgraded when absent from evidence. Only the
  truncation to `t.js` was a defect.
- Not report-only: this is the live display/persistence grounding path.
