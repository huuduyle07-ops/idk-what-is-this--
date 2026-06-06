# Project Evolution Mode

Project Evolution Mode is the broad-change workflow for migrations,
architecture changes, dependency or provider swaps, and multi-file feature
evolution.

It is a planning and evidence contract first. In B.1 it does not wire into
runtime patch generation, runtime routes, model/API calls, validation behavior,
benchmark scoring, lesson behavior, Docker/subprocess behavior, or UI changes.

## When To Use It

Use Project Evolution Mode when the operator is asking for a change that is too
wide for small debug-style patching, such as:

- migrating embeddings from MiniLM to Gemini, model2vec, or a future Semble-aided search stack
- replacing a storage backend
- changing architecture boundaries across multiple modules
- adding a feature that touches code, tests, config, and docs together
- planning a staged migration with rollout and rollback notes

## When Not To Use It

Do not use Project Evolution Mode for normal bug repair, narrow explanation,
single-file cleanup, or evidence-first debugging where the root cause can be
found from focused snippets and lightweight mapping.

Project Evolution Mode must not replace Debug Mode.

## How It Differs From Debug Mode

Project Evolution Mode differs from Debug Mode in scope and reading strategy.

Debug Mode stays:

- small
- evidence-first
- bug and patch oriented
- minimal-context by default
- minimal-file-read by default

Project Evolution Mode can:

- build a broader project map
- ask for architecture understanding before patching
- read selected full files when justified
- run impact analysis before patching
- require a migration plan before patching
- require human approval before patch generation

Important boundary:
Project Evolution Mode must not change the default Debug Mode behavior. Normal
debug runs should not start reading broad/full-project files by default.

## Canonical Stages

## Intake

Capture the evolution request, repo path, goal, constraints, and risk
tolerance. This is where the operator says what broad change is wanted and what
must stay safe.

## Existing Map Inventory

Inventory the current project-map, repo-librarian, indexer, graph, and search
capabilities already present in C.A.T.T.U.S. Evolution Mode should reuse or
upgrade those existing components instead of creating a duplicated second
project-map system.

## Project Map

Build or refresh a richer project map that identifies structure, languages,
dependency files, config files, entrypoints, test roots, docs, and
generated/build folders to ignore. This remains navigation, not truth.

## Architecture Read

Read selected full files when summaries and snippets are not enough to
understand integration boundaries. Selected full files are justified and named;
the workflow should not blindly read every file or blindly read the full repo.

## Impact Analysis

Identify affected modules, dependency edges, compatibility risks, tests needed,
rollout points, and rollback points before any patching is considered.

## Migration Plan

Produce a human-readable migration plan before patching. The plan should list
likely changed files, reasons, risks, tests, and rollback notes.

## Approval Gate

Require human approval before patch generation. Broad understanding, impact
analysis, or prior debug approval do not count as permission to start a
multi-file patch.

## Patch Execution

Patch Execution is a later phase only. Multi-file patches must be controlled,
minimal, and validated against the approved plan. B.1 does not wire this stage
into runtime patch generation yet.

## Evidence

Store the plan, project map, selected files, approvals, validation, and
replay/debug artifacts so broad changes can be reviewed safely.

## Retrieval And Search Architecture Notes

Project Evolution Mode should describe and reuse these layers clearly:

- Tree-sitter for structural reading of symbols, imports, classes, and functions
- existing project map / repo librarian / indexer for repo layout and ownership
- graph builder / graph weights for relationship and evidence context
- grep or ripgrep fallback for exact text search
- MiniLM or other embedding providers for semantic similarity
- Semble as an optional future fast local code-search backend candidate
- LLMs only after selected files or snippets are chosen, acting as summarizer or planner rather than first-pass search

Important Semble rule:
Semble is a candidate retrieval/search backend, not the summarizer. It is
future-only in this slice, not a required dependency, and not added in B.1.

## Example Use Case

Example: migrating embeddings from MiniLM to Gemini/model2vec/Semble.

The workflow would:

1. capture the migration goal and compatibility constraints
2. inventory the current embedding, index, retrieval, and graph-related
   components already in the repo
3. build a richer project map that highlights provider modules, env vars, test
   roots, and retrieval boundaries
4. read selected full files such as the embedding-provider abstraction,
   retriever/indexer touch points, health checks, and tests
5. run impact analysis on dimensions, provider IDs, env vars, docs, and
   fallback behavior
6. produce a migration plan before patching
7. stop for human approval before patch generation

Semble stays documented as a future search candidate only. It is not the
summarizer and not required for the first migration plan.

## Expected Artifacts

- evolution request summary
- existing map inventory
- richer project map
- selected full-file list with rationale
- impact analysis
- migration plan
- approval record
- validation and replay/debug evidence once later execution exists

## Human Approval Points

- approving the repo path and constraints is not approval to patch
- approving the richer map is optional review, not execution approval
- approving the migration plan is the required gate before patch generation

## Safety Boundaries

- Project Evolution Mode must not replace Debug Mode
- Debug Mode must stay lightweight by default
- no automatic multi-file patching in B.1
- no automatic dependency upgrades
- no automatic GitHub writes
- no n8n or remote worker integration yet
- no Dream or research auto-ingestion yet
- no CONTROL prompt changes
- no benchmark scoring changes
- no lesson or anti-lesson behavior changes
- no model/API/subprocess/Docker behavior changes

## Future-Only Connection Points

These are future-only and not implemented by B.1:

- n8n for orchestrated approval or follow-up flows
- GitHub for PR/draft workflows after human approval
- Scholar for research-backed migration notes
- Dream for sandboxed evolution experiments and review packs
