# CTX.SELECT.1 - Bounded Direct File Candidate Selection

Date: 2026-08-01

Status: complete contract and pure selection behavior
Recommended next phase: CTX.READ.1 - Bounded Direct File Read Runtime

## Decision

C.A.T.T.U.S can discover useful repository files without a vector database or
canonical index. CTX.SELECT.1 consumes an already-created, policy-approved
repository inventory plus caller-supplied task terms, name references, metadata,
and lexical-search results. It produces deterministic candidate, proposed-read,
and proposed-patch sets.

It does not read production file contents, execute lexical search, authorize reads or
writes, apply patches, index content, touch manifests or databases, build an
Activation Graph, or call a model/API.

The governing invariant is:

```text
relevance score
!= read authority
!= write authority
```

## Context hierarchy

The intended context order is unchanged:

1. user-provided direct context;
2. agent-selected direct file context;
3. Activation Graph;
4. canonical repository intelligence.

`not indexable` therefore does not mean `not usable as context`. A safe YAML,
TOML, Vue, shell, or other unsupported text file may be proposed as raw direct
context while making no AST, symbol, dependency, or repository-completeness
claim.

## Existing boundaries reused

`RepositoryInventory.entries` remains the sole membership input. The existing
inventory builder owns repository walking, ignore policy, deterministic order,
duplicate rejection, containment, and symlink-target validation. The selector
never calls the inventory builder or adds another scanner.

The canonical `SUPPORTED_EXTENSIONS` set was moved without changing its members
to the side-effect-free `core/source_file_policy.py`. `config.py` re-exports
that same object, so indexing behavior remains unchanged while pure selection
code avoids loading environment/application configuration.

The existing portable relative-path predicate was similarly extracted to
`core/repository_path_policy.py` and re-exported by
`core/repository_inventory.py`. Filesystem containment and runtime TOCTOU
revalidation remain outside this lexical predicate and are deferred to
CTX.READ.1.

## Independent capability axes

Every supplied inventory record is classified along independent axes:

```text
readability:
  readable_text | readable_limited | opaque_binary | unreadable | sensitive

parser_support:
  supported | partial | unsupported | not_applicable

indexability:
  canonical_indexable | direct_context_only | not_indexable

editability:
  editable | editable_with_review | read_only | generated_do_not_edit |
  sensitive_requires_approval | outside_scope | opaque | forbidden

direct-read policy:
  auto_read_allowed | explicit_human_approval_required | hard_no_auto_read

understanding confidence:
  parsed | partial | raw_text_only | unknown
```

Canonical indexability is derived from the unchanged supported-extension
policy. AST confidence is narrower: languages handled by the canonical
Tree-sitter mapping may be `parsed`; fallback-supported formats remain partial;
safe unsupported text is raw-text-only.

Contradictory metadata fails closed. A caller cannot label a `.bin` file as
readable text, weaken `.env` from approval-required to automatic, or override a
private-key, credential-store, repository-policy, outside-root, or symlink-escape
exclusion.

## Sensitive and forbidden files

The direct-context tri-state policy is:

- ordinary source and safe text: `auto_read_allowed`;
- `.env.example`, `.env.sample`, and `.env.template`: automatic placeholder
  context;
- `.env` and environment variants: explicit human approval required;
- private keys, credential/browser/session stores, canonical secret-shaped
  names, protected control files, unmanaged binary/database dumps, hard-ignore
  paths, outside-root paths, symlink escapes, and explicit repository-policy
  exclusions: hard no-auto-read.

The `.env.example` exception is deliberately local to direct-context planning;
it does not weaken the existing production index/security gate. Sensitive or
binary lexical results are discarded without retaining their supplied excerpts.

## Repository-size strategy

Thresholds are configurable at the pure helper boundary and pinned by tests:

| Tier | Safe readable count | Default disclosure |
| --- | ---: | --- |
| small | 0-30 | complete safe relative-path list plus basic capability metadata |
| medium | 31-300 | root entries, depth-limited synopsis, entrypoints, bounded matches and candidates |
| large | more than 300 | counts/synopsis plus capped exact, token, lexical, and top-ranked candidates |

Medium and large reports deliberately leave `complete_relative_paths` and the
small-only capability list empty and record truncation metadata. Large reports
also expose bounded directory/file counts and file-type counts rather than a
path dump. A safe one-file repository receives
`single_readable_file` evidence and recommends that file directly when its size
is known and within budget.

Every capped list reports `total`, `returned`, `limit`, and `truncated`. Paths
are normalized repository-relative POSIX spellings, unique, and deterministic.

## Discovery pipeline

The pure pipeline is:

```text
supplied inventory
-> filename/path evidence
-> bounded lexical-search request
-> supplied lexical-search results
-> direct-reference and test-pair evidence
-> ranked candidates
-> proposed read set
-> proposed patch candidates
```

Evidence includes user-named files and symbols, exact and token filename/path
matches, likely entrypoints, configuration files, test pairs, direct import or
symbol references, lexical matches, recent-change hints, a safe single-file
signal, and unsupported-but-readable text.

Name reports precede lexical search. User-named safe files have the strongest
ordering priority, exact name matches precede token-only matches, and all
remaining ties resolve by deterministic score/path order. Test pairing is
directory-local when duplicate source basenames make a global stem match
ambiguous; an unresolvable pair contributes no validation evidence.

## Bounded lexical-search contract

CTX.SELECT.1 describes a request and consumes supplied results; it does not run
grep, ripgrep, a subprocess, or any search API.

Hard maximums are:

```text
matches:            200
distinct files:      40
excerpt characters: 240
expansion rounds:      2
terms:                32
include paths:         40
exclude paths:         64
```

Terms and include/exclude prefixes are normalized, duplicate-free, sorted, and
bounded with truncation metadata. Repository hard exclusions, sensitive path
prefixes, and default `.git/`, `.agent/`, virtualenv, cache, dependency, and
temporary paths cannot enter the search scope. Composed plans expand requested
directory prefixes to exact auto-readable inventory files. Every request states
that a future executor must reapply the safe-inventory filter and that this
phase grants no production-search authority. Results are validated against
supplied inventory capabilities, sorted before both caps, deduplicated by
path/location/term/source, and clipped deterministically.

Requests select literal case-sensitive or case-insensitive matching and carry
a whole-token preference as metadata. They do not request regex, symbol, or AST
matching.

## File Actionability Score

Actionability is an explainable integer from 0 through 100:

```text
bounded positive evidence
- bounded risk adjustments
= actionability score
```

Configured evidence weights cannot be increased by caller input. Repeated
evidence is identity-deduplicated and each evidence kind has a bounded aggregate
cap; defensive intake caps prevent unbounded evidence or risk records. Risk
adjustments are deduplicated by risk kind and include high dependency centrality, blast radius, file
class, parser confidence, generated/vendor status, and validation gaps.

History always uses the stable stage order:

```text
inventory -> filename_match -> lexical_search
```

Score bands are:

- 80-100: `primary_patch_candidate`;
- 60-79: `inspect_before_patch`;
- 35-59: `supporting_context`;
- 1-34: `low_priority_context`;
- 0: `forbidden_or_no_evidence`.

Generated files may retain a high relevance score while their action redirects
to an authoritative schema/generator input. A forbidden/outside-scope state
forces the actionable score to zero. Neither result grants permission.

## Proposed read-set planner

The planner accepts ranked immutable candidate records and proposes at most
eight files totaling at most 1 MiB (1,048,576 bytes). Unknown sizes fail closed with a future
bounded-range recommendation. A file exactly at the remaining byte boundary is
allowed.

When diversity is enabled, the planner tries, in order:

1. primary likely target;
2. dependency or caller;
3. validation/test;
4. task-relevant configuration;
5. one contrasting candidate when ambiguity remains;
6. highest remaining bounded evidence.

Security and readability gates run before budgeting. The output records every
selection/exclusion reason, byte totals, truncation, and false read/write
authority. Inputs are never mutated.

## Proposed patch boundary

A file may be a proposed patch candidate only if it:

- already belongs to the proposed read set;
- is repository-contained and safe readable text;
- has `editable` or `editable_with_review` state;
- reaches the score threshold (60 by default);
- has grounding beyond filename similarity;
- is not generated, vendor, sensitive, opaque, read-only, outside-scope, or
  forbidden;
- has an inventory-known, policy-safe validation candidate or carries an
  explicit validation-gap warning.

Every result contains `write_authority: false`. `approved_writable_files` is not
produced in this phase. Existing patch safety and human approval remain the only
later authorization boundaries.

## Independence and escalation

The selector imports no vector, embedding, manifest, identity-state, database,
graph, patch, model, API, or network runtime. It works with supplied inventory
under `uninitialized`, `initial_confirmation_required`,
`major_change_confirmation_required`, and `blocked` canonical identity states.

It may recommend one advisory outcome without dispatching it:

- `direct_context_sufficient`;
- `activation_graph_recommended`;
- `canonical_intelligence_recommended`;
- `human_file_selection_required`.

## Deferred work

CTX.READ.1 may add bounded runtime file reads only after fresh containment,
symlink, sensitivity, and byte-range checks. Direct-read scoring updates,
reference expansion, validation mapping from inspected content, patch authority,
Activation Graph execution, and canonical intelligence escalation remain
deferred.

CTX.READ.1 is recommended only. It is not started or authorized by CTX.SELECT.1.
