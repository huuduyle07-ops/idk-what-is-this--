# ANALYSIS.MULTIROOT.LIVE.1 — Explicit Read-Only Multi-Repository Evidence Contract

**Track:** WAITER · **Prerequisite:** INPUT.PRESERVE.LIVE.1 · **Status:** complete
**Date:** 2026-09-06

---

## 1. The failure

Live T5 asks one question the analysis route could not answer:

> Compare this repository (deepseek-harness, the DeepSeek AI agent harness)
> against C.A.T.T.U.S, the Python agent harness located at `../C.A.T.T.U.S`.

Every phase before this one honoured that request faithfully and then stopped at
acquisition. INPUT.1 extracted the comparison. INPUT.PRESERVE.LIVE.1 carried all
six dimensions through without truncating them. WAITER.LIVE.1 routed it to
`analysis_only`. ANALYSIS.EVIDENCE.LIVE.1 acquired role-balanced documentation
*and* implementation source. All of it from one repository, because evidence
acquisition is scoped to one project root.

The answer therefore opened by declaring the second repository inaccessible, and
the disclaimer was accurate: nothing in the system could read it. The remaining
capability gap was not routing, not preservation and not ranking. It was **read
scope**.

| Before | |
|---|---|
| roots readable per analysis request | 1 |
| `../C.A.T.T.U.S` | structurally unreachable |
| T5 comparison | one-sided by construction |

---

## 2. What this phase does not do

It adds read scope for **explicitly requested** repository roots and nothing
wider. It is not multi-repository patching, not multi-repository execution, not
Commander, not workspace-wide search, not unrestricted `../` traversal, not
index federation, not graph merging and not cross-repository symbol resolution.

No write authority. No patch authority. No execution authority. No model call.
No embedding. No network access. No change to RETRIEVE.LIVE.4. No increase to
the analysis context budget because there happen to be two roots.

---

## 3. The design

### 3.1 Provenance: the user, and only the user

A repository outside the active project root may enter analysis evidence only
when the user named it as a subject of the task. The chain is:

```
explicit user request
    → preserved Task Contract / obligations       (INPUT.1, INPUT.PRESERVE.LIVE.1)
    → requested analysis root literal             (extract_requested_root_literals)
    → validated, canonicalized project root       (resolve_analysis_subjects)
    → AnalysisReadScope: read yes, write no       (acquire_subject_membership)
```

`extract_requested_root_literals` accepts only already-frozen explicit-input
structures — the preserved obligations, `ExplicitEvidence.file_paths`, the task
subjects. A model draft, a retrieved document, a README link and a source import
are not inputs to it, so none of them can widen scope. The Semantic Waiter
cannot grant a root the user never named.

On the exact T5 text, `ExplicitEvidence.file_paths` is empty — INPUT.1's path
regex requires a file extension and `../C.A.T.T.U.S` has none — so the literal
is recovered from the **preserved obligations**, which is the reason
INPUT.PRESERVE.LIVE.1 is this phase's prerequisite. Before that phase the first
clause was cut at 240 characters and `../C.A.T.T.U.S` survived only by luck of
position; after it, the whole clause is authoritative.

### 3.2 Candidacy is not acceptance

A *candidate* is a path-shaped literal that names somewhere outside the current
root: a `..` escape, a POSIX absolute path, a Windows drive path or a `~` path.

`..` is the trigger for candidacy, never the denial criterion — T5 legitimately
writes `../C.A.T.T.U.S`, so "the string contains `..`" cannot be the rule. What
follows candidacy is a resolution pipeline with a closed status vocabulary:

| order | check | status on failure |
|---|---|---|
| 1 | operating-system location (literal, drive-stripped) | `not_project_root` |
| 2 | resolves to a filesystem/drive root | `not_project_root` |
| 3 | does not exist | `not_found` |
| 4 | exists but is not a directory | `not_directory` |
| 5 | declares no repository marker (one shallow listing) | `not_project_root` |
| 6 | no repository identity derivable | `repository_identity_invalid` |
| 7 | resolves to a repository already accepted | `duplicate_of_accepted_root` |
| 8 | more than `MAX_ANALYSIS_ROOTS` | `root_count_exceeded` |
| 9 | no containment boundary bindable | `containment_invalid` |
| — | otherwise | `accepted` |

Step 1 tests the **literal** the user typed rather than the canonical path, and
strips any drive letter first. That is what makes `/etc/passwd` refuse
identically on every platform: on Linux it exists and is a file, on Windows it
would canonicalize to `C:/etc/passwd` and merely not exist, and neither
accident should be what the safety property rests on.

Step 5 reuses `MANIFEST_NAMES` and `PROJECT_DOCUMENT_NAMES` from
`core.analysis_evidence_roles` plus the version-control markers, read with one
non-recursive `os.scandir`. A directory listing is not a repository traversal;
it is counted and reported separately as `validation_listings`.

### 3.3 Two roots, one budget

`MAX_ANALYSIS_ROOTS = 2` — the current root plus at most one explicitly
requested additional root. That is exactly T5. A third requested root produces
`root_count_exceeded` with a reason; it is never silently dropped and never
silently taken.

The global analysis budget does not move: **12 files, 60,000 characters, 6,000
characters per file**, shared. Multi-root must allocate, not multiply.

`allocate_root_balanced_selections` is two rules in order:

1. **Exactly requested files first**, in every root that has them. Generic
   balancing never evicts a path the user named.
2. **Rotation.** One file at a time, taking turns between roots, over each
   root's own role-balanced reading order — of which only a *prefix* is ever
   taken, so ANALYSIS.EVIDENCE.LIVE.1's within-root reservation survives being
   given six slots instead of twelve.

Rotation is what makes the root floor availability-aware without any quota: a
root with nothing left simply stops being offered a turn, and its unused slots
go to the root that can fill them. It also keeps the *character* budget
symmetric, because the reading order is the allocation order — if 60,000
characters run out, they run out on both sides at once rather than on whichever
root happened to be listed first.

### 3.4 Containment is per root

Each accepted root gets its own `AnalysisReadScope`, bound to its own canonical
root. A relative path belonging to root A never resolves through root B, and
there is no shared "largest common parent" boundary. Containment is checked on
the canonical target — `resolve()` then `relative_to()` — so a symlink inside an
approved repository that points outside it is refused. Approving a repository
never approved what its links reach. The secondary root's membership walk is
`core.repo_librarian._walk_policy_files`, which already runs `followlinks=False`
and drops symlinks resolving outside the root; this phase reuses that rather
than writing weaker rules for secondary roots.

### 3.5 Read scope is a type, not a flag

```python
class AnalysisReadScope:
    evidence_read_allowed          -> True      # property
    write_authority                -> False     # property
    patch_application_authority    -> False     # property
    execution_authority            -> False     # property
    human_review_eligible          -> False     # property
    approval_ready                 -> False     # property
```

All six are read-only properties on a frozen dataclass. A caller cannot
construct a read scope that writes, patches or executes, and
`AnalysisRepositorySubject.__post_init__` refuses to attach a scope to a root
whose status is not `accepted`. Reusing a write-authority flag to mean "read
allowed" is the mistake this shape makes unrepresentable.

### 3.6 Membership: reuse one, walk one

| root | source of membership | traversals added |
|---|---|---|
| primary, inventory supplied | the request-scoped `RepositoryInventory` | **0** |
| primary, no inventory | WAITER.LIVE.1's pre-existing bounded listing | **0** (unchanged) |
| additional, accepted | `create_repository_inventory` | **1** |
| additional, refused | none | **0** |

This phase cannot honestly claim traversal delta zero: a previously
inaccessible repository has to obtain membership somehow. What it does claim,
and measures, is *at most one canonical membership traversal per newly accepted
root, per analysis request* — through the same walker, the same
`RepoIgnorePolicy`, the same hard excludes and the same `.gitignore` /
`.cattusignore` behaviour as any other repository. No graph is built for it, no
index is written, no embedding is generated and no command is run inside it.

An inventory that declares a *different* canonical root than the subject
resolved to is never merged; the affected root fails conservatively with
`repository_identity_invalid`. An inventory that declares no canonical root at
all cannot be checked and is accepted as before, which keeps existing callers
and test doubles working unchanged.

### 3.7 Provenance survives into the answer

Every evidence item carries `repository_id` and `repository_display`, and
citations are rendered as `repository::path` — not a syntax invented here, but
the repository-qualified reference grammar ANSWER.GROUND.LIVE.1 already parses.
Each excerpt block carries a `cite=` line spelling the exact string, and the
`[FILES READ]` section is grouped by repository first and role second.

`_state_repository_evidence` now emits **one `RepositoryEntityEvidence` per
accepted root**, each grounded strictly by what was acquired from it. The
primary root's fold skips items belonging to another repository. This is what
keeps ANSWER.GROUND.LIVE.2's separated symbol universes true when there is
finally more than one of them: if `Foo.run` exists only in root A, the claim
"C.A.T.T.U.S uses Foo.run" cannot be grounded from root A.

### 3.8 Partial comparisons are stated, not hidden

If a requested root cannot be resolved or read, the available root is still
analysed. The refused subject appears in `[REPOSITORIES]` with its status and
reason, appears again as an evidence gap, and the prompt is told to report the
comparison as partial on that dimension rather than constructing the missing
half from the half it has.

The symmetric rule matters as much: where a repository *was* read, the prompt
says so explicitly and instructs the answer not to open by claiming it could not
access it. An answer that hedges about evidence it actually holds is as wrong as
one that invents evidence it does not.

---

## 4. Measured result

Exact live T5, deterministic prefix only, no provider call, real repositories,
primary inventory supplied as production supplies it:

| | before | after |
|---|---|---|
| roots requested | 2 | 2 |
| roots accepted | 1 | **2** |
| `deepseek-harness` files / chars | 12 / 59,674 | 6 / 20,802 |
| `C.A.T.T.U.S` files / chars | **0 / 0** | **6 / 17,604** |
| global files | 12 | **12** |
| global chars | 59,674 | **38,406** |
| implementation source, root A | 6 | 3 |
| implementation source, root B | **0** | **3** |
| project documents, root A | — | 2 |
| project documents, root B | **0** | **2** |
| unmet role requirements | — | none, either root |
| membership traversals added | 0 | **1** |
| model calls | 1 draft / 0 review | **1 draft / 0 review** |

Root balance status `every_accepted_root_represented`; budget not exhausted; no
evidence gaps recorded.

Performance, same run:

| stage | seconds |
|---|---|
| root resolution | 0.003 |
| primary membership (reused) | 0.012 |
| **secondary membership (the one added cost)** | **2.19** |
| selection | 0.076 |
| acquisition (12 bounded reads) | 0.004 |
| **analysis prefix total** | **2.28** |

For scale: the primary root's own inventory, which production already builds,
takes 16.0 s for 6,126 indexable files. The added secondary walk is 1,315 files.

---

## 5. Compatibility

* **Single-root analysis is byte-identical.** Same selections, same gaps, same
  profile, same selection reason, same unmet requirements, with and without the
  `analysis_only` gate. Pinned by test.
* **Documentation-only analysis** stays documentation-centric; a sibling
  repository that merely exists on disk changes nothing.
* **T1–T4 unchanged.** Multi-root activates only on `analysis_only`, so defect
  repair, explicit change and clarification never reach it.
* **Historical artifacts** load unchanged. A run with no multi-root receipt
  reports `single_root_legacy`, which is what it is — not a failed multi-root
  acquisition. Single-root evidence items carry no `repository_id` key at all.
* **Frozen boundaries untouched:** CONTROL, PATCH, VALIDATE, EXEC,
  RETRIEVE.LIVE.1–4, INPUT.1/.2/.3, WAITER.LIVE.1, ANSWER.GROUND.LIVE.1/.2.
  `MAX_SUBJECT_TOKENS` is not raised.

---

## 6. Known limitations

1. **The second root grounds only what was read.** No inventory is carried
   across for additional roots, so a path that exists in root B but was not
   acquired stays unverified rather than confirmed. This is the conservative
   direction for a grounding gate, and it is an asymmetry with the primary root,
   whose full inventory is available.
2. **A file path inside another root is not a root literal.** `../repo-b/src/x.ts`
   is classified as a requested *file*, so it does not by itself open `repo-b`.
   The user must name the repository. Requested filenames still take priority
   inside whichever accepted root contains them.
3. **Root validation is conservative about system locations.** A genuine project
   living under `/usr/local/src` would be refused. The denylist is small and
   static by design; widening it is a separate decision.
4. **Within-root selection quality is unchanged and still imperfect.** On the
   real T5 run, C.A.T.T.U.S's sixth slot went to a benchmark fixture
   (`benchmarks/cases/.../buggy_repo/main.py`) rather than production code. That
   is ANALYSIS.EVIDENCE.LIVE.1's ranking, deliberately not touched here.
5. **The symlink-escape test skips where the OS denies symlink creation**
   (Windows without the privilege). The containment predicate it exercises is
   pinned separately by resolve-then-contain tests on the real reader.
6. **Two roots is the cap.** A three-way comparison returns explicit overflow
   evidence, not an answer.
