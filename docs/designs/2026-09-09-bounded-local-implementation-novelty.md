# PATCH.MINIMAL.LIVE.2 — Bounded Local Implementation Novelty

**Status:** complete · **Track:** CONTROL · **Date:** 2026-09-09
**Prerequisites:** PATCH.MINIMAL.LIVE.1, DEFECT.PROBE.LIVE.4, DEFECT.PROBE.LIVE.3,
CANDIDATE.VERIFY.LIVE.1, DEFECT.FACT.LIVE.1, OPS.PATCH.2, PATCH.BASIS.LIVE.1,
CONTROL.LOCALIZE.LIVE.2, RETRIEVE.LIVE.4

---

## 0. The measured problem

`safe_minimal`'s identifier rule was one line of lexical set arithmetic:

```python
allowed = _identifiers_in(target) | _LANGUAGE_KEYWORDS | builtins
new_idents = sorted(_identifiers_in(patched) - allowed)
if new_idents:
    reject("introduced identifiers not present in the source")
```

Round 6 authored a T6 candidate whose whole novelty was `lstrip` / `mode` /
`stripped`, and the rule rejected it with that sentence. Before changing
anything, the shipped gate was replayed against twelve representative
candidates for the live target `core/code_dna.py::_classify_indent`, recording
for every novel identifier its AST role, binding scope, load/store context,
containing function, whether it existed before, the gate's reason and its
disposition.

| candidate | novel identifiers | AST roles | pre-LIVE.2 disposition |
| --- | --- | --- | --- |
| new local assignment | `width` | Name store ×3, Name load ×2 | **rejected** |
| new loop variable | `ch`, `width` | Name store, loop target | **rejected** |
| local accumulators | `ch`, `left`, `right`, `unit`, `width`, `widths`, `append` | Name store/load + Attribute load | **rejected** |
| novel member | `append`, `lstrip`, `widths` | Attribute load | **rejected** |
| novel import | `statistics`, `mode`, … | `Import`, Attribute load | **rejected** |
| nested function | `leading`, `ch`, `width` | `FunctionDef` | **rejected** |
| novel global | `_INDENT_UNIT`, `global` | `Global` | **rejected** |
| novel parameter | `default_unit` | `arg` | **rejected** |
| attribute store | `unit` | Attribute store | **rejected** |
| Round-8 ceiling | `ch`, `indent` | Name store, loop target | **rejected** |
| exact no-op | — | — | accepted (rejected earlier by LIVE.1) |
| inverted reorder | — | — | accepted |

Every candidate carrying any novel identifier was rejected, **with the same
reason**, whether the novelty was a loop counter or a new module dependency.
That is the defect this phase repairs — in the policy, not in the target.

## 1. The distinction

> A lexical identifier being new is not evidence that the candidate expands
> program capability.

Two different things were being counted as one:

- **Local binding novelty** — a name created, used and destroyed inside the
  body of an *existing* function. It reaches nothing the function could not
  already reach.
- **External / structural reference novelty** — a new import, definition,
  parameter, global, nonlocal, attribute store, member or callable. It changes
  what the program is made of, or what it can reach.

`core/local_binding_novelty.py` reasons from syntax and lexical scope to
separate them. It never decides what is *new* — the gate's own lexical delta
stays the authority on that — it decides what a new name structurally **is**.

## 2. Eligibility is a chain, not a score

```
novel identifier
    ↓  is it a local binding of this candidate?
    ↓  contained in the ONE existing function being edited?
    ↓  within the caps?
    ↓  is there no structural / dependency / member / cross-scope novelty
       anywhere in the same candidate?
    ↓
eligible for candidate verification
```

There is no `novelty_score`, no coefficient and no confidence anywhere in the
module (§13). Admission is a boolean derived from typed findings.

## 3. What counts as a local binding (Python)

`Name` in `Store` context reached through an assignment, augmented or annotated
assignment, `for`/`async for` target, walrus, `with ... as`, `except ... as`, or
a comprehension target. Loads are admitted only by **resolution**: a novel load
must resolve through the lexical scope chain to a binding this candidate made
inside the same existing function (§5). No spelling is ever whitelisted.

Deliberately *not* local bindings:

| construct | classified as |
| --- | --- |
| `import x` / `from m import x` | `novel_import` |
| `def` / nested `def` / `class` / `lambda` | `novel_definition` |
| a new parameter, default, annotation, decorator, async-ness | `signature_change` |
| `global x` / `nonlocal x` | `novel_scope_declaration` |
| `self.mode = …`, `obj.state = …` | `novel_attribute_store` |
| `line.lstrip(...)`, `client.request(...)` | `novel_external_reference` |
| a novel keyword-argument name | `novel_external_reference` |
| `mapping[key] = value`, `append(...)` | binds nothing; left to the semantic verifiers (§17) |
| a novel module-level `Name` store | `novel_definition` |
| a name the candidate never binds | `unresolved_novel_identifier` |

## 4. Language coverage

**Python only.** Lexical scope is a language-specific fact, and applying
Python's rules to every grammar for symmetry is exactly what §4 forbids.
`javascript`, `typescript`, `go`, `rust` and an unset language all report
`language_supported=false` and keep the previous conservative rule byte for
byte. Aliases `py` / `python` / `python3` reach the classifier.

## 5. Candidate shapes

| shape | when | why it is safe |
| --- | --- | --- |
| `definition` | both snippets parse as-is and both carry a top-level `def`/`class` | definition sets, public shapes and per-function bodies are directly comparable |
| `function_body_fragment` | both snippets parse only after dedent, `target_node_kind == "function"`, neither side contains a `def`/`class`/`lambda`, and every non-blank line of both is indented | a contiguous, definition-free, wholly-indented region cannot contain module-level code and cannot span two functions, so no signature can change and the scope is one function's suite |
| `unsupported` | anything else, including unparsable input | falls back to the previous rule; fail closed |

## 6. Caps — measured, not chosen

| cap | value | derivation |
| --- | --- | --- |
| novel local bindings | **3** | the measured local-only family binds 1, 2, 2, 3, 5; 3 is the smallest cap admitting a correct fix |
| touched functions | **1** | §25's own bound |
| changed lines | **24** | the largest measured local-only diff; the correct candidate measures 18 |

The caps can only ever narrow the widening. Classification runs *only* when the
lexical delta is non-empty and its only possible effect is to skip a rejection,
so the gate rejects a strict subset of what it rejected before. A test pins
that directly.

## 7. The correct local-only candidate (test-only)

```python
counts = Counter()
unit = 0
for line in text.splitlines():
    if not line or line[0] not in " \t":
        continue
    if line.startswith("\t"):
        counts["tab"] += 1
        continue
    counts["space"] += 1
    width = 0
    for ch in line:
        if ch != " ":
            break
        width += 1
    while width:
        unit, width = width, unit % width
if unit and counts["space"] >= counts["tab"]:
    return "2space" if unit <= 2 else "4space"
return "tab" if counts["tab"] else None
```

Three novel locals — `unit`, `width`, `ch`. No import, no definition, no
signature change, no novel member and no novel callable: the leading-space
width is counted with a loop rather than `lstrip`, and the greatest common
divisor is accumulated in place rather than in a list, which is why `append` is
not needed either. It infers the base indentation **unit**, which is what the
subject invariant actually says, and answers all four DEFECT.PROBE.LIVE.4 cases.

It is never applied to production `_classify_indent` and never offered to a
model.

## 8. Results

| candidate | pre-LIVE.2 | post-LIVE.2 `safe_minimal` | DEFECT.PROBE.LIVE.4 | CANDIDATE.VERIFY |
| --- | --- | --- | --- | --- |
| exact no-op | accepted here, rejected by LIVE.1 | unchanged — no delta to classify | never entered | never entered |
| inverted reorder | accepted | accepted (no delta) | `fixed_but_regressive` | `rejected` |
| Round-8 ceiling (local-only form) | **rejected** | **admitted** | `fixed_but_regressive` | `rejected` |
| correct local-only | **rejected** | **admitted** | `fixed_and_preserved` | `verified` |
| new import / new function / novel member / global / nonlocal / attribute store / signature change / mixed | rejected | rejected, each with its own reason | — | — |

The Round-8 ceiling row is the one that matters most: admission is eligibility
for verification, never a verdict. `execution_authorized=false` and
`final_repository_changed=false` on every row, and the real repository file is
byte-compared before and after every T6 test.

## 9. Authority

Admission writes no `human_review_eligible`, no `candidate_review_ready`, no
`approval_ready`, no `execution_authorized` and no `write_authority`. There is
no path from local novelty to a behavioral verdict: the matrix and the
verification reducer are unchanged and unbypassable, and `AUTO_PATCH_ENABLED=false`
still means no mutation.

## 10. Freshness

The receipt is bound to the existing candidate fingerprint primitive
(`candidate_fingerprint_from_payload`) — no new fingerprint algorithm.
`core/pipeline.py` drops the whole `_CANDIDATE_NOVELTY_KEYS` group when the
candidate changes after classification, with the same exemption
PATCH.MINIMAL.LIVE.1 has for a recorded rejection: that receipt is the record of
why the payload carries no candidate at all.

## 11. The re-pin, made a proof

DEFECT.PROBE.LIVE.4 and CANDIDATE.VERIFY.LIVE.1 both froze
`patching/patch_gates.py` at
`816101991102f593cd037ec2009ddbfb3936b6ceb004dd839a1584e01434425e`. This phase
is the one authorised to move `safe_minimal`, so both pins move to
`cec73583c9d416e3b4f883090b02f2b48e0b012c44d2962f5e40819a5c070cf7` — and
`tests/fixtures/patch_minimal_live2_safe_minimal_reversal.json` stores the four
hunks that reverse the change, so the test reconstructs the pre-LIVE.2 file from
the shipped one and asserts the old digest. Of the file's 35 top-level
definitions, exactly one — `_enforce_safe_minimal` — has a different AST. Every
other file in both fixtures is still byte-identical.

## 12. Known limitations

- **f-strings cannot be admitted.** The gate's lexical scanner strips quoted
  text and leaves the `f` prefix behind as an identifier that no AST node
  carries, so it falls through to `unresolved_novel_identifier`. Pre-existing
  behaviour, unchanged, fail-closed.
- **`.append()` and friends stay blocked.** Python's builtin allowlist contains
  functions and types, not methods, so a novel method name on any receiver is
  external reference novelty. Widening that is a different question about the
  builtin allowlist, not about local scope.
- **Pure gcd over-generalises on real source files.** The positive control
  answers all four bounded matrix cases, but a real file with alignment-style
  continuation indents drives the gcd to 1. It is a test-only candidate for a
  bounded oracle, not a proposed production fix.
- **One function, definition or fragment.** Multi-function and multi-file
  candidates keep the previous conservative treatment.

## 13. Boundaries

Unchanged: RETRIEVE.LIVE.4, CONTROL.LOCALIZE.LIVE.2, DEFECT.FACT.LIVE.1,
DEFECT.PROBE execution and LIVE.4 matrix semantics, PATCH.MINIMAL.LIVE.1's
no-op gate, targeted validation (selectors, 3-file cap, 8-node cap, commands,
budgets), the candidate verification reducer, EXEC.AUTH / EXEC.POLICY /
EXEC.APPROVAL, the authoring prompt, and `_classify_indent` itself.

Zero model calls, zero network calls, zero subprocesses, zero repository
traversal. The classifier imports only `ast`, `difflib`, `hashlib`, `json`,
`textwrap`, `time`, `dataclasses` and `typing`, and parses only the two bounded
snippets the gate already holds.
