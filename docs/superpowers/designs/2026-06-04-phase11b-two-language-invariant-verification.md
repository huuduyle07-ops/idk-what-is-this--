# Phase 11.b Two-Language Invariant Verification Design

## Goal

Add an evidence-only report layer that records a patch invariant in two forms: a code-facing invariant and a plain-English invariant. The report checks whether already-available local evidence supports those statements.

## Scope

This phase adds `core/invariant_verification.py`, an optional local CLI, tests, and a roadmap note. It does not modify CONTROL prompts, lesson retrieval, anti-lesson behavior, benchmark scoring, patch generation, validation execution, Reverse Dream, mutation-oracle anti-lesson minting, model/API code, or web UI.

## Inputs

The builder accepts an already-loaded dictionary from a benchmark result, patch proposal artifact, apply/validation result, or replay-style summary. It reads common fields such as:

- `code_invariant`
- `plain_english_invariant`
- `invariants.code` / `invariants.plain_english`
- `changed_files`
- `patched_files`
- `touched_forbidden_files`
- `unexpected_mutations`
- `validation_command`
- `validation_ok`
- `validation_output`
- `patch_summary`
- `source_ref`

Missing optional fields degrade gracefully. Missing explicit invariant text returns `unknown` invariants and an `unknown` verdict.

## Verdict Policy

- `unsupported`: validation failed, forbidden files or unexpected mutations are present, or the invariant text obviously contradicts the evidence.
- `supported`: validation succeeded, both invariants are explicit, changed files exist, validation output exists, and there are no guardrail warnings.
- `weakly_supported`: validation succeeded and both invariants exist, but evidence is thin, such as missing validation output or missing changed-file detail.
- `unknown`: explicit invariant text is absent, validation status is absent, or local evidence is insufficient to evaluate.

Contradiction detection is intentionally narrow and deterministic: phrases such as "no behavior change" or "behavior unchanged" conflict with changed files, successful validation, or a patch summary that says a bug/fix changed behavior.

## CLI

`scripts/create_invariant_verification_report.py` reads one existing local `.json` artifact with `--input-json` and a required `--repo-path`. It writes JSON and Markdown artifacts under `.agent/experiments/<timestamp>_invariant-verification.{json,md}` unless explicit output paths are supplied. The CLI never runs validation, benchmarks, models, patching, lessons, Docker, or network calls, and it leaves the source artifact byte-identical.

## Validation

Required validation:

- `python -m compileall core scripts tests`
- `python -m pytest tests/test_invariant_verification.py -q --basetemp .fresh_tmp_phase11b_invariants`
- `python -m pytest tests -q --basetemp .fresh_tmp_phase11b_full`
- `python -m benchmarks.run_benchmarks --check`
