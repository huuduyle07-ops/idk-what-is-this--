# Phase 11.c Honeypot Benchmark Cases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add four benchmark-only honeypot cases that test whether agents avoid tempting wrong fixes before Phase 11 anti-lesson execution work.

**Architecture:** The slice adds static benchmark fixtures under `benchmarks/cases`, registers them in existing suite manifests, and pins the intended metadata with a focused pytest file. No runtime production modules are modified.

**Tech Stack:** Python benchmark runner, JSON case manifests, local Python/TypeScript/Go validation commands, pytest.

---

### Task 1: Focused Honeypot Metadata Tests

**Files:**
- Create: `tests/test_honeypot_benchmark_cases.py`

- [ ] **Step 1: Write the failing test file**

Add tests that define the four Phase 11.c case IDs, assert they are discovered, assert `full_v1` contains all four, assert `dev_v1` contains the first three, assert each case has expected/forbidden files, assert validation commands avoid network/install markers, and assert guarded production modules are unchanged by this slice.

- [ ] **Step 2: Run the focused tests and verify RED**

Run: `python -m pytest tests/test_honeypot_benchmark_cases.py -q --basetemp .fresh_tmp_phase11c_honeypots`

Expected: fail because the new case folders and suite entries do not exist yet.

### Task 2: Add Honeypot Fixtures

**Files:**
- Create: `benchmarks/cases/python/python_wrong_abstraction_honeypot/case.json`
- Create: `benchmarks/cases/python/python_wrong_abstraction_honeypot/buggy_repo/main.py`
- Create: `benchmarks/cases/python/python_wrong_abstraction_honeypot/buggy_repo/windowing.py`
- Create: `benchmarks/cases/typescript/ts_wrong_file_honeypot/case.json`
- Create: `benchmarks/cases/typescript/ts_wrong_file_honeypot/buggy_repo/main.ts`
- Create: `benchmarks/cases/typescript/ts_wrong_file_honeypot/buggy_repo/display.ts`
- Create: `benchmarks/cases/typescript/ts_wrong_file_honeypot/buggy_repo/normalizer.ts`
- Create: `benchmarks/cases/go/go_validation_gap_honeypot/case.json`
- Create: `benchmarks/cases/go/go_validation_gap_honeypot/buggy_repo/go.mod`
- Create: `benchmarks/cases/go/go_validation_gap_honeypot/buggy_repo/main.go`
- Create: `benchmarks/cases/go/go_validation_gap_honeypot/buggy_repo/invite.go`
- Create: `benchmarks/cases/python/python_test_deletion_honeypot/case.json`
- Create: `benchmarks/cases/python/python_test_deletion_honeypot/buggy_repo/main.py`
- Create: `benchmarks/cases/python/python_test_deletion_honeypot/buggy_repo/discounts.py`
- Create: `benchmarks/cases/python/python_test_deletion_honeypot/buggy_repo/tests/test_discounts.py`

- [ ] **Step 1: Add minimal buggy repos and manifests**

Each `case.json` must include `name`, `language`, `category`, `difficulty`, `agent_mode`, `patch_style`, `validation_command`, `expected_changed_files`, `forbidden_changed_files`, and a strict prompt naming the tempting wrong fix and the evidence-backed file restriction.

- [ ] **Step 2: Keep each correct fix small**

The intended correct fixes are source-only: a boundary comparison in `windowing.py`, field normalization in `normalizer.ts`, email trimming in `invite.go`, and a loyalty threshold branch in `discounts.py`.

### Task 3: Register Suites

**Files:**
- Modify: `benchmarks/suites/dev_v1.json`
- Modify: `benchmarks/suites/full_v1.json`
- Modify: `tests/test_benchmark_suites.py`

- [ ] **Step 1: Register cases**

Add all four honeypots to `full_v1`; add `python_wrong_abstraction_honeypot`, `ts_wrong_file_honeypot`, and `go_validation_gap_honeypot` to `dev_v1`.

- [ ] **Step 2: Update pinned suite tests**

Update the full discovery count and relevant new-case lists so the existing suite tests describe the 54-case full suite and Phase 11.c registrations.

### Task 4: Roadmap and Validation

**Files:**
- Modify: `docs/AI_Coding_Mentor_Roadmap_Refresh_2026-05-16.md`

- [ ] **Step 1: Add a compact roadmap note**

Record that Phase 11.c shipped benchmark-only honeypot cases, with no CONTROL, lesson, anti-lesson, Reverse Dream, mutation-oracle, model/API, web UI, or scoring behavior change.

- [ ] **Step 2: Run validation**

Run:

```powershell
python -m compileall benchmarks tests
python -m pytest tests/test_honeypot_benchmark_cases.py -q --basetemp .fresh_tmp_phase11c_honeypots
python -m pytest tests -q --basetemp .fresh_tmp_phase11c_full
python -m benchmarks.run_benchmarks --check
```

Optional smoke:

```powershell
python -m benchmarks.run_benchmarks --case python_wrong_abstraction_honeypot --fast --summary --skip-toolchain-failures
```
