# Project Map Upgrade Plan

This document explains how Project Evolution Mode should reuse and upgrade the
existing mapping and search stack instead of building a duplicated second
project-map system.

## Existing Components To Inventory

Inventory these existing components first:

- `core.repo_librarian` for repo inventory, file manifests, language counts, and skip rules
- `core.indexer` for Tree-sitter-backed file summaries, import/call extraction, and project-map generation entrypoints
- `graph.project_map` for the existing project map, hotspot summaries, and folder responsibility output
- `graph.builder` for graph builder relationships
- `graph.weights` for graph weights and ranked hotspots
- `core.semantic_graph_pipeline` for semantic graph caching and Obsidian export support
- `reasoning.deep_project_understand` for graph-backed impact and path tracing helpers
- ripgrep/grep fallback for exact text search when structure or embeddings are insufficient
- MiniLM or other embedding providers for semantic retrieval

## Retrieval/Search Layers

Project Evolution Mode should document these layers clearly and keep them in
their current roles:

- Tree-sitter: structural reader for symbols, imports, classes, and functions
- existing project map / repo librarian / indexer: repo layout, ownership, and broad file summaries
- graph builder / graph weights: relationship and evidence graph
- grep/ripgrep fallback: exact text search
- MiniLM / embeddings: semantic similarity
- Semble: optional future fast local code-search backend candidate
- LLM: summarizer/planner only after selected files or snippets are chosen

Semble is a candidate retrieval/search backend, not the summarizer. It is not
required for B.1 and should not be introduced as a dependency here.

## Reuse Versus Upgrade

Reuse as-is:

- repo-librarian manifest and skip logic
- existing project map writing path
- graph builder and graph weights
- current ripgrep exact-match fallback behavior

Upgrade for Evolution Mode only:

- richer project map fields for architecture planning
- richer inventory output that records entrypoints, integration boundaries, and external services/env vars
- explicit full-file-read candidates with rationale
- migration risk notes attached to the map output

Leave unchanged:

- Debug Mode's lightweight mapping behavior
- existing runtime patch generation paths
- existing benchmark scoring and lesson behavior

Project Evolution Mode should reuse the existing project map rather than
duplicate it. If a richer map is needed, upgrade the current map/inventory
contracts so both workflows still share one family of mapping components.

## Project Map V2 Contents

Project Map v2 for Evolution Mode should contain:

- languages
- package/dependency files
- config files
- entrypoints
- test roots
- documentation files
- generated/build folders to ignore
- likely architecture layers
- integration boundaries
- external services/env vars
- full-file-read candidates
- migration risk notes

## Why Debug Mode Stays Lightweight

Debug Mode keeps using lightweight mapping because repair tasks need fast,
evidence-first narrowing instead of broad architectural reading. For a small
bug, broad project-map expansion and selected full-file reading would often add
noise, cost, and delay.

## Why Evolution Mode Can Ask For Richer Mapping

Evolution Mode can request richer mapping because migrations and architecture
changes need repo-wide ownership, dependency boundaries, config surfaces, and
rollback planning before patching. That broader map should still be selective:
it enables selected full-file reading, not blind full-repo reading.

## Full-File Read Policy

Selected full-file reading is allowed when the richer map shows a real need,
for example:

- entrypoints that stitch layers together
- provider abstractions and dependency wiring
- config/env loaders
- integration tests and migration-sensitive test helpers
- docs that define operator-visible behavior or rollout steps

The workflow should not blindly read every file. The project map chooses
full-file-read candidates first, then the planner decides which of those files
actually justify a full read.

## Future Provider Evaluation Notes

Future provider evaluation can compare Gemini, model2vec, and Semble-backed
search ideas, but B.1 stops at documentation and metadata. Semble remains a
candidate backend only; it is not the summarizer, not required, and not added
as a dependency in this slice.
