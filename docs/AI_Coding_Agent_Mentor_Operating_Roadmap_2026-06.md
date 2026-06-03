# AI Coding Agent/Mentor — Operating Roadmap 2026-06

## Purpose

This roadmap is the post-stabilization operating roadmap for C.A.T.T.U.S / AI Coding Mentor.

The old roadmap remains the historical build log:

- AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md

This roadmap focuses on what to improve next after the Phase 13 stabilization and UI presentation freeze.

---

## Current Position

C.A.T.T.U.S is currently strongest at:

- debugging
- repair
- explanation
- validation
- evidence-grounded patching
- benchmark-based safety checks

It is weaker at:

- project creation
- broad migrations
- architecture evolution
- multi-file feature development

Reason:

The current system is optimized for small, evidence-first repair tasks. Creation and migration tasks require broader project understanding and full-file planning.

---

## Track A — Stabilized Debug Agent

Keep improving the existing debug/repair workflow.

Goals:

- keep patches small
- preserve evidence grounding
- improve speed/cost
- reduce UI complexity
- expand benchmark coverage

---

## Track B — Project Evolution Mode

New idea, not part of the frozen historical roadmap.

Purpose:

Support creation/migration tasks such as:

- migrating MiniLM embeddings to Semble/model2vec
- replacing storage backends
- changing project architecture
- adding multi-file features
- updating config/docs/tests together

Workflow:

1. Build project map
2. Read relevant full files
3. Produce architecture migration plan
4. Identify affected modules
5. Identify risks
6. Ask for approval
7. Generate controlled multi-file patch
8. Update tests/docs/config
9. Run validation
10. Produce rollback notes

Important rule:

Project Evolution Mode should be separate from Debug Mode.

Debug Mode should stay small, fast, and evidence-first.
Evolution Mode can read more files, but only when explicitly selected.

---

## Track C — External Benchmark Sandbox

- C.1 Public benchmark survey
- C.2 Manual import of 3–5 small real-world cases
- C.3 Dependency sandbox design
- C.4 Explicit package-install approval gate
- C.5 Real-world benchmark trial report

---

## Track E — Dream Evolution Sandbox

### Goal:
Let Dream propose architecture improvements in isolated branches/temp clones,
evaluate them with tests/benchmarks/replay evidence,
then ask the human before any merge/apply.

### E.1 Branch Sandbox Proposal Writer
- create feature branch or temp clone
- write proposal only
- no merge
- no auto PR

### E.2 Dream Evolution Scorecard
- tests passed
- benchmark delta
- files touched
- risk score
- replay artifacts
- rollback notes

### E.3 Human Review Pack
- summary
- changed files
- why this exists
- evidence
- risks
- rollback command

### E.4 Optional PR Draft
- create PR draft only after explicit user click
- never auto-merge

### E.5 Artifact Janitor / Branch Janitor
- dry-run first
- delete only failed sandbox branches or old temp artifacts
- never delete active lessons or pinned replays

---

## Track F — Operator Assistant / Prompt Courier

### Purpose:
Reduce manual friction in Goal Brief and Mayor Mode by converting messy user intent into structured, reviewable task briefs and handoff notes.

### F.1 Goal Brief Autocomplete
- user writes messy request
- assistant proposes structured Goal Brief fields
- user edits/approves
- no patch/model execution from this step

### F.2 Handoff Composer
- convert Goal Brief into Mayor handoff note
- fill title, allowed files, validation command, risk notes
- keep "human_approved_for_proposal=false"

### F.3 Mode Router
- suggest Debug Mode vs Project Evolution Mode vs Dream Trial
- explanation only
- user must confirm

### F.4 Review Pack Generator
- generate a final prompt for Claude/Codex/Gemini worker
- include constraints, allowed files, validation, stop conditions

---

## Track G — Remote Operator Mode

### G.1 Local daemon
- C.A.T.T.U.S runs on stayed-on computer
- localhost/local LAN first
- no public internet exposure yet

### G.2 Secure remote web access
- login token
- one-user mode
- HTTPS/tunnel only
- read-only dashboard first

### G.3 Remote approval actions
- approve proposal
- start benchmark
- view replay
- create goal brief
- create handoff note

### G.4 Dangerous actions require second confirmation
- apply patch
- run validation
- create branch
- install packages
- delete artifacts

### G.5 Mobile-friendly UI
- simplified dashboard
- approve/reject buttons
- replay summary
- benchmark status

### Reference Study: Scrapling + Arkon

#### Goal:
Evaluate whether Scrapling/WebBridge and Arkon can help C.A.T.T.U.S collect public documentation and build a dynamic AI-readable graph.

#### Rules:
- no anti-bot evasion goal
- no scraping behind login
- no CAPTCHA solving
- no automatic browsing
- no automatic patching
- output only local research notes

---

## Deferred Ideas

- Migration Planner
- Full-file project understanding mode
- Architecture change proposal generator
- Multi-file patch planner
- Rollback report generator
- Compatibility report generator
- Chat app intergration (like OpenClaw/n8n)