# Phase 11.b Two-Language Invariant Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an evidence-only invariant verification report that records code-facing and plain-English invariant statements for already-existing patch artifacts.

**Architecture:** A pure core module normalizes local artifact dictionaries into a stable report and Markdown rendering. A thin CLI reads one existing JSON artifact and writes JSON/Markdown under `.agent/experiments`; it does not run validation, benchmarks, patching, models, lessons, or CONTROL behavior.

**Tech Stack:** Python dataclasses/dicts, argparse/json/pathlib CLI, pytest, AST guardrail tests.

---

### Task 1: Focused Tests

**Files:**
- Create: `tests/test_invariant_verification.py`

- [ ] **Step 1: Write failing core tests**

Cover supported verdicts, validation failure, missing invariants, missing validation output, forbidden/unexpected mutations, contradiction detection, input immutability, and Markdown output.

- [ ] **Step 2: Write failing CLI tests**

Cover strict local JSON input, JSON/Markdown output under `.agent/experiments`, byte-identical source artifacts, and no partial output left after failures.

- [ ] **Step 3: Write AST guardrail tests**

Assert the new core/CLI modules do not import or call subprocess, Docker, network, model/API, benchmark execution, patch execution, lesson mutation, mutation-oracle, CONTROL, prompter, or lesson-retrieval sinks.

### Task 2: Core Module

**Files:**
- Create: `core/invariant_verification.py`

- [ ] **Step 1: Add constants and helpers**

Define `REPORT_TITLE`, `GUARDRAIL_NOTE`, verdict constants, timestamp helper, string/list normalizers, evidence extractors, and narrow contradiction detection.

- [ ] **Step 2: Implement `infer_basic_invariants`**

Read explicit invariant fields from root-level or nested `invariants`; return conservative `unknown` placeholders when absent.

- [ ] **Step 3: Implement `build_invariant_verification`**

Return a dict with title, generated_at, source_ref, invariant strings, evidence block, verdict, reasons, and guardrail without mutating the input.

- [ ] **Step 4: Implement Markdown formatter**

Render both invariant forms, verdict, reasons, evidence, and guardrail as text-only Markdown.

### Task 3: CLI

**Files:**
- Create: `scripts/create_invariant_verification_report.py`

- [ ] **Step 1: Add strict path handling**

Require `--repo-path`; resolve `--input-json` inside the repo, require `.json`, reject traversal, require file existence, reject output paths outside `.agent/experiments`, reject existing output files, and reject output equal to input.

- [ ] **Step 2: Read/build/write artifacts**

Read the source JSON object, build the report, render Markdown, and write paired JSON/Markdown outputs. On write failure, remove partial outputs.

### Task 4: Docs, Roadmap, Validation

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

- [ ] **Step 1: Add compact roadmap note**

Record that Phase 11.b shipped evidence-only invariant verification with no benchmark scoring, CONTROL/retrieval, Reverse Dream, mutation-oracle anti-lesson minting, model/API, patch, validation, lesson, or web behavior change.

- [ ] **Step 2: Run validation**

Run:

```powershell
python -m compileall core scripts tests
python -m pytest tests/test_invariant_verification.py -q --basetemp .fresh_tmp_phase11b_invariants
python -m pytest tests -q --basetemp .fresh_tmp_phase11b_full
python -m benchmarks.run_benchmarks --check
```
