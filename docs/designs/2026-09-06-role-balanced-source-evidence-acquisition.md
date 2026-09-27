# ANALYSIS.EVIDENCE.LIVE.1 — Role-Balanced Source Evidence Acquisition

**Track:** WAITER · **Prerequisite:** RETRIEVE.LIVE.4 · **Status:** complete
**Date:** 2026-09-06

---

## 1. The failure

Live T5, the recurring black-box architecture task, asks the agent to analyse
`deepseek-harness`, compare it against C.A.T.T.U.S and recommend ideas. It routes
correctly — `analysis_only` → `analysis_answer`, no CONTROL, no patch
localization — and it comes back with an accurate, shallow answer.

Measured against the real repository before this phase, by replaying the prior
selector verbatim on the canonical T5 prompt (deterministic prefix only, no
provider call):

| | |
|---|---|
| inventory (indexable) | 6,126 files |
| TypeScript available | 2,700 (`.ts` 2,438 + `.tsx` 262) |
| markdown available | 2,469 |
| **files selected** | **12 — 11 `project_document`, 1 `package_manifest`** |
| **implementation source selected** | **0** |
| characters spent | 59,674 of 60,000 |

Four of the eleven documents were Chinese translations (`.zh.md`) of documents
already selected. Not one line of the system's own code entered the evidence.

Nothing was misconfigured. `.ts` is in `SUPPORTED_EXTENSIONS`, the files were in
the inventory, and the route was right. The cause was **allocation**:

1. WAITER.LIVE.1's evidence vocabulary had no role that could hold code
   (`requested_path`, `requested_subject`, `project_document`,
   `package_manifest`, `entry_point`), so code could never be *reserved*.
2. `entry_point` matched a fixed list of **root-relative** names — `main.py`,
   `src/index.ts`, … — and a pnpm workspace keeps its entry points at
   `packages/<name>/src/index.ts`. The list matched nothing.
3. The final selection pass swept every markdown file under `docs/` into the
   remaining slots, and there were 219 of them.

So documentation reached the reader first, spent the whole character budget, and
the answer described the system from its own prose.

## 2. What this phase does not do

Not multi-root access, not repository-traversal expansion, not embeddings, not
graph ranking, not query rewriting, not a larger context window, not a new
authority. No model call was added, no network call, no traversal, no write.

In particular it does **not** raise the budget. `MAX_EVIDENCE_FILES` is still 12,
`MAX_TOTAL_CHARS` still 60,000, `MAX_CHARS_PER_FILE` still 6,000, and a test pins
all three so a later phase cannot buy the same result with a bigger budget.

## 3. The design

```
RepositoryInventory  (already built — no second walk)
    -> classify each path into ONE deterministic role     [analysis_evidence_roles]
    -> derive ONE evidence profile from the task's words  [analysis_evidence_roles]
    -> reserve a per-role minimum, INTERLEAVED            [analysis_evidence_roles]
    -> fill the remainder by role rotation                [analysis_evidence_roles]
    -> read, bounded, in that order                       [analysis_evidence]
    -> role-coverage receipt + evidence gaps              [analysis_evidence]
```

### 3.1 Roles

| role | meaning | new? |
|---|---|---|
| `requested_path` | the user typed this path | — |
| `implementation_source` | production code by the canonical extension policy | **new** |
| `project_document` | README, `docs/`, prose | — |
| `package_manifest` | `package.json`, `pyproject.toml`, … | — |
| `test_example` | tests, specs, samples, fixtures | **new** |
| `requested_subject` | matches a subject the user named, fits no role above | — |
| `entry_point` | retained so pre-phase receipts still validate; nothing classifies into it now | — |

An entry point *is* implementation source. It is now an ordering hint inside that
role, matched on the **basename** so a workspace's per-package front doors are
found — which is the specific thing the root-anchored list could not do.

### 3.2 Profiles

Derived by literal marker match over the obligations and subjects INPUT.1 already
preserved. No model, no score, no classifier. Order is fixed:
architecture → implementation → documentation → dependency → general.

| profile | reserved minimums (in fill order) |
|---|---|
| `architecture_implementation` | source 4, docs 3, manifest 1 |
| `implementation_detail` | source 5, docs 1, manifest 1 |
| `documentation_explanation` | docs 4, manifest 1, **source 0** |
| `dependency_configuration` | manifest 3, docs 1, **source 0** |
| `general_analysis` (default) | docs 3, manifest 1, **source 0** |

The minimums are floors on representation, not quotas. A role with nothing
available contributes nothing and is never reported as unmet; a role listed at 0
may still fill leftover budget, which is how a repository with one README and two
source files stays sensible without any quota being met.

`general_analysis` reproduces WAITER.LIVE.1's own emphasis, so a caller that
supplies no task words sees what it saw before this phase.

### 3.3 Reservation is interleaved, and that is the point

Reserving source but reading it last would satisfy the *file* cap and starve on
the *character* cap: eight 6,000-character files exhaust 48,000 of 60,000, so
positions 11 and 12 are never opened. Reserved roles therefore take turns in the
**reading order** — source, doc, manifest, source, doc, … — so each of them
reaches the reader before the budget can run out.

This is the difference between reserving implementation source and actually
acquiring it, and it is pinned by
`test_reserved_roles_are_interleaved_so_each_survives_the_character_budget`.

### 3.4 Ordering inside a role

Every role starts from the same demotion — `0` primary, `1` test or example, `2`
generated or vendored — then applies its own notion of "strongest", then falls
back to the shallower path and finally to the canonical path.

* `project_document`: the order a human opens a repository's own documents
  (README, architecture, `docs/`), then subject overlap.
* `package_manifest`: ecosystem order, so the root `package.json` precedes a
  sample project's copy.
* `implementation_source`: program code before markup/stylesheets, then subject
  overlap, then an entry-point basename.

Overlap is a count of distinct subject tokens present in the path. It is not a
frequency, a weight or an IDF: **RETRIEVE ranking is not reopened here.** Subject
*sentences* are split into words first, because no path has ever contained
`"architecture of this deepseek-harness repository and compare it"`.

### 3.7 The question's own words

Role balance alone acquired six real source files that answered nothing:
`DeepSeekModelsEditor.tsx`, `DeepSeekOnboardingDialog.tsx`, an API gateway, a web
bootstrap. They were correctly classified, correctly reserved, correctly read —
and irrelevant.

The reason is visible in one line of the receipt. The subjects INPUT.1 preserved
for the canonical T5 request are:

```
['this repository (deepseek-harness', 'C.A.T.T.U.S', 'DeepSeek AI']
```

which tokenise to `("deepseek", "harness")` — the *name* of the thing, never what
is being asked about it. The words that say what the question is about — agent
loop, extension model — sit in the **obligations**, which were being used to pick
the profile and then discarded.

Feeding the obligations into the same bounded token overlap (subjects first, so
the narrower signal keeps the budget) moves the selection to
`packages/core/agent-loop/src/agent.ts` and its siblings. The question had
already told the system where to look.

This stays a literal token-overlap count under the same fixed cap of 12 tokens:
no frequency, no weighting, no IDF, no model. **RETRIEVE ranking is not
reopened.**

### 3.5 Reuse, not a second map

* Source detection is `core.source_file_policy.SOURCE_ROLE_BY_EXTENSION`. `.ts`
  classifies as code here for exactly the reason it does everywhere else, and
  `README.ts.md` classifies as documentation because the **real final extension**
  decides.
* Test/example location is `core.eligibility_policy.is_test_location` plus the
  two brace-language conventions it does not spell (`.test.`, `.spec.`) and the
  directories a repository keeps runnable samples in.
* Generated/vendored **segments** are derived from the module's own existing
  exclusion prefixes, so `packages/<x>/dist` and `packages/<x>/node_modules` are
  seen where a root-anchored prefix could not see them.

Tests, examples, generated output and vendored copies are **demoted, not
excluded**. A sample can be the clearest description of an API and generated code
is sometimes the only code; what the policy forbids is either of them displacing
primary implementation source while primary source exists.

### 3.6 Honesty

When a profile reserves source and none was read, the evidence gap says so and
names how many source files existed. The answer prompt gained one rule:

> Documentation describes intent; source files show implementation. If a claim
> about how something works rests only on documentation, say so in that sentence
> rather than presenting the document as proof of the code.

Presenting eleven markdown files as an account of how a system works was the
specific failure. It is now visible in the receipt and in the prompt.

## 4. Measured result

Same repository, same caps, same canonical prompt, deterministic prefix, no
provider call, no write:

| | before | after |
|---|---|---|
| files selected | 12 | 12 |
| `implementation_source` | **0** | **6** |
| `project_document` | 11 | 4 |
| `package_manifest` | 1 | 2 |
| TypeScript characters acquired | **0** | **20,241** |
| total characters | 59,674 / 60,000 | 39,158 / 60,000 |
| groundable TypeScript symbols | 0 | 47 |

Selected after: `packages/core/agent-loop/src/{index,agent,invariant,constants}.ts`,
`packages/core/agent-default-model/src/{index,invariant}.ts`, `README.md`,
`CONTRIBUTING.md`, `docs/architecture.md`, one postmortem, and the two owning
package manifests.

Documentation stayed represented. Source stopped being absent — and, after §3.7,
stopped being irrelevant.

Selection cost in isolation, over a synthetic 4,002-path inventory (20-call
mean): 46.9 ms per call. The whole real-repository prefix — selecting from 4,000
paths and reading 12 files — takes 114 ms, against a 16–26 second inventory walk
this phase does not touch. No overall T5 latency improvement is claimed.

The profile depends on the task, not the repository: the same 40-document /
30-source fixture selects **0** source files under `documentation_explanation`
and **≥ 4** under `architecture_implementation`.

### 4.1 Model smoke

Three runs against the real repository, `AUTO_PATCH_ENABLED=false`,
`deepseek-harness` verified 0 dirty before and after each:

| run | source citations | doc citations |
|---|---|---|
| role balance only | **0** of 6 acquired files | 6 across 2 files |
| + prompt role grouping | **0** of 6 acquired files | 8 across 2 files |
| + obligation tokens | **9** across 5 of 6 files | 6 across 2 files |

The first two runs are the important negative result: the model was right not to
cite that source, because it did not answer the question. Acquiring source and
acquiring *the right* source are different problems, and only the third run
solved the second one. In it the answer grounded a recommendation in
`packages/core/agent-loop/src/invariant.ts` rather than in prose, and
ANSWER.GROUND refused the names it reached for beyond the evidence in every run.

## 5. Compatibility

* **T1–T4 unchanged.** Only the analysis route's evidence acquisition moved;
  `defect_repair`, `explicit_change` and `needs_clarification` acquisition is
  untouched.
* **ANSWER.GROUND.LIVE.1/.2** already extracts declared symbols from analysis
  excerpts, so acquired TypeScript symbols ground without a ProgramGraph. Pinned
  by `test_acquired_typescript_symbols_can_ground_an_answer`.
* **RETRIEVE.LIVE.1–.4, WAITER.LIVE.1, CONTROL.SAFETY, PATCH.BASIS, OPS.PATCH,
  OPS.VALIDATE, EXEC.\*, DEFECT.PROBE, VALIDATE.ORACLE** untouched.
* **Historical artifacts** remain readable: `entry_point` stays in the frozen
  role vocabulary and old receipts still validate. New receipts carry the extra
  role-coverage fields.

## 6. Known limitations

1. **Multi-root remains unavailable.** The T5 request names `../C.A.T.T.U.S`.
   The `deepseek-harness` side is now deeper; the C.A.T.T.U.S side is still out
   of scope and the answer must keep saying so. Cross-root read authority needs
   its own contract.
2. **Localized duplicates.** `docs/architecture.zh.md` still takes the fourth
   documentation slot beside `docs/architecture.md`. Translation-aware
   deduplication would be a separate, deliberate change to document ordering.
3. **`MAX_INVENTORY_SCAN` still caps the candidate pool at 4,000 paths.** On
   `deepseek-harness` that window holds 1,360 of the 2,700 TypeScript files —
   ample for a 12-file budget, but half the workspace is not considered. Raising
   it is a bounds change this phase deliberately did not make.
4. **INPUT.1 truncates a long obligation at ~250 characters.** On the canonical
   T5 request that cuts the sentence at "…how each handle", so `tool`, `plugin`,
   `lifecycle`, `context` and `retrieval` never reach token extraction.
   Dimension 1 of the question (agent loop) became source-backed; dimensions 2
   and 3 stayed documentation-backed for exactly this reason. Widening that
   bound belongs to INPUT.1, not here.
5. **Localized duplicates.** A `.zh.md` translation can still take a
   documentation slot on prompts where it ties on overlap. Translation-aware
   deduplication would be a separate, deliberate change to document ordering.
