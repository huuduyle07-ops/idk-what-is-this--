# ACQUIRE.3 — Bounded Content Acquisition & Source Receipt

Date: 2026-08-24
Status: complete
Prerequisite: ACQUIRE.2 (closed / frozen)
Next: EVIDENCE.1 — verify acquired content and expected evidence roles

## Decision

ACQUIRE.3 answers one mechanical question:

> What exact source bytes or already-available context references were obtained,
> from a caller-supplied ACQUIRE.2 subset, under which explicit bounded human
> authorization?

It does not decide which candidates are interesting and it does not decide what
the acquired material proves.

```text
ACQUIRE.2 eligible candidate envelope
    + explicit canonically ordered selection
    + explicit human-approved fingerprint-bound authorization
    ↓
ACQUIRE.3 bounded repository bytes / direct-context references
    + tamper-bound unverified source receipts
    ↓
STOP
```

Future EVIDENCE.1 owns the transition from acquired source to verified evidence.

## Public contracts

`AcquisitionSelection` is an immutable caller proposal. It contains a canonical,
duplicate-free tuple of candidate identifiers and binds it to the ACQUIRE.1
request, ACQUIRE.2 receipt, inventory and repository identity. Its source may say
human, validated CTX.SELECT output, or another authorized selector; that is
provenance only. ACQUIRE.3 validates every source identically and never executes
a selector.

`AcquisitionAuthorization` defaults to no authority. A usable grant records:

- `acquisition_allowed=true` and `human_approved=true`;
- the ACQUIRE.1, ACQUIRE.2, inventory and repository fingerprints;
- an exact allowed-candidate envelope and allowed domains;
- an explicit absolute repository root for repository reads;
- source-count, total-byte and per-source-byte caps; and
- structured approval/read-mode reasons, without credentials.

The authorization is supplied by the caller. ACQUIRE.3 never mints one.

Authorization can only narrow. It cannot add a candidate or domain, promote a
tier, remove an exclusion, change workflow/repository identity, or exceed any
ACQUIRE.1/2 ceiling. The allowlist is an envelope; the explicit selection is the
closed set that spends source and byte budgets. A grant may therefore allow ten
candidates while authorizing a two-source selection, but it may not read a third.

## Pure gates before filesystem access

No repository root or candidate path is touched until all of these pass:

1. authorization exists, allows acquisition, and records human approval;
2. INPUT, INPUT.3, WAITER.1, WAITER.2, ACQUIRE.1 and ACQUIRE.2 fingerprints and
   schemas form one monotonic chain;
3. the selection is an active primary/secondary subset of ACQUIRE.2;
4. claimed CTX.SELECT output satisfies ACQUIRE.2's selector envelope;
5. the supplied inventory fingerprint and repository identity match; ACQUIRE.2's
   metadata-only eligibility outcome is re-derived for repository, direct-context
   and external-only receipts to keep every envelope closed;
6. authorization identifiers, domains and limits only narrow upstream; and
7. the whole proposed selection fits its global and per-request source/byte
   budgets.

Failure of any pure gate produces a bounded blocked/authorization/budget result
with zero candidate-path reads.

## Candidate-addressed repository reads

A repository read requires an explicit absolute root whose lexical and resolved
identities agree. ACQUIRE.3 does not search parents for a root.

For each selected identifier, in canonical selection order, it:

- requires the exact inventory spelling and a portable safe relative path;
- rejects absolute, drive-relative, rooted and `..` paths structurally;
- `lstat`s only the named path components, never enumerating a directory;
- rejects symlinks and Windows reparse points in the root, parents or leaf;
- requires the resolved target to remain inside the authorized root;
- requires a regular file whose live size equals both inventory and candidate;
- preflights the complete selection before opening any candidate;
- opens read-only with `O_NOFOLLOW` where the platform supplies it;
- adds `O_NONBLOCK` where available so a raced FIFO cannot hang before `fstat`;
- reads at most the exact preflight size in fixed-size chunks;
- compares full mode, device/inode, size, modification time, stable platform
  change/creation time, root identity and path metadata before/after the read; and
- accepts bytes only when the complete file remained stable.

Missing, stale, non-regular, unsafe or changed-during-read candidates receive a
per-source failure. No replacement is searched for and no unselected path is
touched. A partial result can contain successful A/C receipts and a failed B
receipt, but never a substituted D.

The conservative symlink policy is refusal. No repository traversal, recursive
glob, manifest refresh, indexing, graph/database lookup or fallback discovery is
present.

UNC/network-share roots are refused before filesystem access so an authorization
cannot introduce hidden SMB I/O while the result says `network_called=false`.

## Budgets and ordering

The selection contract must already be canonically ordered by
`(identifier.casefold(), identifier)`. ACQUIRE.3 preserves that order; there is
no relevance ranking.

The whole selection is refused before root access if it exceeds source count,
total bytes, a per-source limit, or one request's reserved budget. Exact
boundaries are accepted. Successful and failed reads report:

- source limit, acquired and remaining;
- total-byte limit, acquired and remaining;
- selected source count and reserved bytes; and
- actual physical bytes read.

The invariants make spending monotonic and prevent accepted bytes from exceeding
physical reads, selected reservations or either authorization/upstream ceiling.
Unknown-size members remain outside ACQUIRE.2's active pool.

## Payload and receipts

`AcquiredSourcePayload` holds exact `bytes` in memory, its SHA-256 and byte count.
It has no ordinary serializer and suppresses bytes from `repr`.

`SourceAcquisitionReceipt` records the identifier, domain, tier, expected roles,
eligible source classes, explicit-target fact, exact byte count, SHA-256 and a
`SourceBinding`. It always says:

```text
acquisition_status = acquired
verification_status = unverified
authority_status = not_verified
```

`SourceBinding` binds a repository receipt to the downstream INPUT/WAITER chain,
WAITER.2 evidence requirements, ACQUIRE.1 request, ACQUIRE.2 candidate receipt,
selection, authorization, inventory and repository identity. The result checks
every nested binding against its top-level provenance.

Normal result/receipt JSON contains no payload bytes. The payload is not written
or persisted. Same bytes produce the same SHA-256; a one-byte change produces a
different source identity. Bytes remain authoritative for acquisition identity;
ACQUIRE.3 does no decoding, parsing, AST work, summarization or semantic analysis.

`expected_roles` records why ACQUIRE.2 admitted a source. It is never a verified
role. A source may be acquired but still be irrelevant, contradictory, stale in
meaning, or non-authoritative; only EVIDENCE.1 may decide.

## Tiers and domains

- Active primary and active secondary candidates are readable only when selected
  and authorized.
- Deferred/historical candidates are structurally rejected. Remaining budget
  never promotes them.
- Excluded candidates are absent from ACQUIRE.2 and inventory re-derivation
  prevents a forged receipt from readmitting them.
- An explicitly targeted inventory member such as `README.md` may be read even
  with empty expected roles/classes. Its target fact grants no implementation,
  architecture, configuration, verification or write authority.
- Direct context becomes an `existing_context` / `already_available_reference`
  receipt bound to upstream identity. No root, inventory read or raw prompt copy
  is required.
- An abstract external envelope becomes
  `external_discovery_required`. ACQUIRE.3 creates no query, URL or concrete
  candidate and performs no network operation.

## Status semantics

- `acquired`: one or more successful repository/direct receipts, nothing
  unresolved;
- `partial`: at least one success plus bounded failures and/or unresolved
  external discovery;
- `authorization_required`: grant absent/disabled/not human-approved, zero reads;
- `budget_blocked`: a pre-read selection/grant ceiling violation;
- `stale_candidates`: no success and only stale/missing failures;
- `external_discovery_required`: no concrete source and external work unresolved;
- `blocked`: another structural or per-source failure, including mixed unresolved
  failure kinds.

There is no successful status when nothing was acquired.

## Authority and performed-state separation

Only a validated, human-approved repository grant for the exact selection can
make `candidate_content_read_authority` and `repository_read_authority` true.
Blocked pre-grant results serialize them false. Performed flags independently
state whether bytes were actually read.

All broader authorities remain false: traversal, external search/fetch,
CTX.SELECT execution, indexing, graph/database access, validation/command
execution, worker launch, repository write/patch, planning/routing, model/provider
selection, project evolution, evidence verification and claim promotion.

Successful repository acquisition truthfully records candidate/repository reads.
Every other guardrail remains false, including traversal, inventory rebuild,
manifest refresh, network, test execution, model calls, verification, promotion
and writes.

## Bounded regressions

All dynamic reads target tiny pytest-created repositories. The suite covers the
authorization gate, fingerprint tamper, exact bytes/hash, arbitrary/outside paths,
case aliases, missing/stale/non-regular sources, root and symlink refusal, source
and byte ceilings, canonical selection, primary/secondary/deferred/excluded
tiers, explicit target acquisition, direct context, external no-network behavior,
partial acquisition, payload secrecy, anti-epistemic language, and detectable
TOCTOU replacement.

The anti-6087 regression supplies 6,200 inventory members and two explicit
selected candidates. Only those two candidate paths receive metadata/content
access; source/byte ceilings hold; no unselected, deferred or excluded member is
touched and no fallback occurs.

Static tests allow only candidate-addressed `lstat`/`fstat`, read-only descriptor
open and bounded `os.read`. They reject traversal/enumeration, filesystem
mutation, subprocess, network/browser, model/provider, database/index/graph,
selector and dynamic-import machinery. A repository-wide source scan proves no
live production module imports or calls ACQUIRE.3.

## Registry limitation

The ROAD.1 phase-registry schema has a single `reads_repository` safety bit. It
cannot distinguish “conditionally supports candidate-addressed reads” from
“performed a read by default.” ACQUIRE.3 therefore retains the registry's
conservative safety value and documents the richer truth in its note: direct
invocation supports read-only source access only after a supplied selection and
valid human-approved fingerprint-bound grant; absent/invalid authority means zero
reads, and registry/picker operations execute nothing.

## Not wired

No live path calls ACQUIRE.3. Instant Run, Commander, Project Evolution,
Workbench, Mixed Mode, web runners, CTX.SELECT runtime and planners are untouched.
Importing the phase is inert; only an explicit direct call with all contracts can
reach its bounded read primitive.

## Known limitations

- ACQUIRE.2 is frozen and its inventory carries a logical repository identity,
  not a physical root. The external human authorization is therefore the trust
  statement binding an absolute local root to that identity. ACQUIRE.3 fingerprints
  that statement and holds the root's live metadata stable, but cannot prove the
  human supplied the intended same-shaped checkout. EVIDENCE.1 must not treat path
  identity alone as semantic authority.
- Mounted or mapped remote filesystems cannot be identified portably. Explicit
  UNC roots are rejected; a mapped drive supplied as a local root remains part of
  the authorization trust boundary.
- No portable pathname API eliminates an adversarial replace-and-restore race on
  every supported Windows/POSIX filesystem. ACQUIRE.3 rechecks immediately before
  open, validates the descriptor before reading, limits the read, and rechecks the
  root/path afterward. Persistent and ordinary replacements fail; a hostile
  concurrent actor able to reproduce every checked identity field remains a
  residual best-effort TOCTOU limitation, consistent with this phase's deliberately
  non-locking scope.

## Next boundary: EVIDENCE.1

EVIDENCE.1 should accept the in-memory payload plus its matching source receipt,
recheck the binding/hash, inspect content under its own authority, evaluate the
expected role, and record support, contradiction or insufficiency. It must make
the promotion from acquired source to verified evidence explicit. It should not
silently broaden acquisition, search for replacements, or inherit write/patch
authority.
