# Phase B.12 — External Queue Import Contract Design

## Purpose

Add a safe internal contract for importing external research/wishlist items from systems like Discord, n8n, Zalo, or webhook workflows. The imported item becomes a review-only artifact under `.agent/external_queue/`. It cannot trigger Dream, apply patches, or modify the repository.

## Scope

Three new files only:

- `core/external_queue_import.py` — normalizer, risk classifier, artifact writer
- `scripts/import_external_queue_item.py` — CLI
- `tests/test_external_queue_import.py` — contract tests

No live API connections, no model calls, no patch apply, no web UI changes.

## Architecture

**Data flow:**

1. Caller provides fields (via CLI flags or `--input-json`).
2. Normalizer coerces `source` and `kind` to known safe values.
3. Secret scanner redacts obvious secrets and appends risk reasons.
4. Result is truncated to 4 096 chars; metadata is depth- and size-bounded.
5. Risk classifier assigns `low` / `medium` / `high` using text analysis only.
6. Record is built with hardcoded gates.
7. Artifacts are written under `.agent/external_queue/{queue_id}/`.
8. Output dir is verified to be contained inside `.agent/external_queue/`.

## Schema

**Inputs:**

| Field | Type | Required | Notes |
|---|---|---|---|
| `source` | string | yes | Normalized to known value or `manual` |
| `kind` | string | yes | Normalized to known value or `research_wishlist` |
| `query` | string | yes | Reject if empty |
| `result` | string | no | Truncated to 4 096 chars |
| `source_url` | string | no | |
| `submitted_by` | string | no | |
| `received_at` | string | no | ISO timestamp |
| `metadata` | object | no | Depth ≤ 4, size ≤ 32 KB |

**Known sources:** `discord`, `n8n`, `zalo`, `webhook`, `manual`

**Known kinds:** `research_wishlist`, `bug_seed`, `project_evolution_seed`, `lesson_candidate_seed`

**Hardcoded output gates:**

```json
{
  "auto_dream_allowed": false,
  "human_review_required": true,
  "import_status": "pending_review"
}
```

These are never settable from caller input.

## Secret Handling

Scan `query` and `result` for token-like patterns before writing:

- `sk-<16+ chars>` — OpenAI-style key
- `ghp_<36+ chars>` — GitHub PAT
- `AKIA<16 chars>` — AWS access key
- `Bearer <token>`
- `password=<value>`, `secret=<value>`, `token=<value>`, `api_key=<value>` (case-insensitive)

For each match:

1. Append `"possible secret detected: {label}"` to `risk_reasons`.
2. Replace the secret value with `[REDACTED_SECRET]` in both `query` and `result` before writing to disk.

No raw secret is preserved in the JSON or Markdown artifact.

## Risk Classification

Text analysis only (no model call). Applied to the combined lowercased `query + result` (after redaction).

**High risk — any of:**
- Possible secret detected.
- Any of: `apply patch`, `auto patch`, `push to`, `commit to`, `modify repo`, `mutate repo`, `server mutation`, `production deploy`, `force push`.
- Any standalone high-risk word: `credential`, `credentials`, `deploy`, `password`.
- `project_evolution_seed` kind AND any of: `apply`, `patch`, `push`, `commit`, `deploy`, `mutate`, `modify` in text.

**Medium risk — any of (if not high):**
- `project_evolution_seed` kind (planning-only, no apply keywords).
- Keywords: `architecture`, `broad migration`, `refactor everything`, `migrate from`, `migrate to`, `big refactor`.
- No `result` provided.
- Query longer than 300 chars with no concrete file reference (e.g., no `.py`, `.ts`, `/`).

**Low risk:**
- None of the above. Narrow research item, `result` present, no mutation keywords.

**Default:** `medium` when uncertain.

## Output Artifact

Output path: `.agent/external_queue/{queue_id}/`

`queue_id` = `{timestamp}_{slug}` where slug is derived from `source + query[:20]`, slugified (alphanumeric + hyphens only).

Files:
- `external_queue_item.json`
- `external_queue_item.md`

**Output record fields:**

`queue_id`, `generated_at`, `mode`, `source`, `kind`, `query`, `result`, `source_url`, `submitted_by`, `received_at`, `auto_dream_allowed`, `human_review_required`, `import_status`, `risk_level`, `risk_reasons`, `allowed_next_steps`, `forbidden_next_steps`, `reviewer_checklist`, `metadata`

**Allowed next steps (fixed list):**

`review_manually`, `convert_to_dream_candidate`, `convert_to_project_evolution_candidate`, `convert_to_goal_brief_seed`, `reject`

**Forbidden next steps (fixed list):**

`auto_dream`, `auto_patch`, `apply_patch`, `modify_real_repo`, `promote_lesson_without_review`, `run_subagent_without_approval`

## Path Containment

The output directory is always verified to be inside `<repo>/.agent/external_queue/`. The `queue_id` slug sanitizer strips `..`, `/`, `\`, and any non-alphanumeric-or-hyphen characters, so the path cannot escape.

## Markdown Report

10 sections:

```
# External Queue Item
## Status
## Source
## Query
## Result Summary
## Risk
## Allowed Next Steps
## Forbidden Next Steps
## Reviewer Checklist
## Guardrails
```

Guardrails section must state verbatim:
- This item is review-only.
- It cannot trigger Dream automatically.
- It cannot apply patches.
- It cannot modify the real repository.
- Human review is required before conversion into any stronger mode.

## CLI

```bash
# Via flags
python scripts/import_external_queue_item.py \
  --repo-path . \
  --source discord \
  --kind research_wishlist \
  --query "Research embedding providers" \
  --result "Gemini embeddings look viable"

# Via input JSON
python scripts/import_external_queue_item.py \
  --repo-path . \
  --input-json path/to/item.json
```

`--input-json` reads any readable JSON file. If the file does not exist or is not valid JSON, exit code 1 with a clear error on stderr.

Prints: `json_path`, `md_path`, `queue_id`, `risk_level`, `import_status`, `auto_dream_allowed`, `human_review_required`.

## Tests (~20 cases)

All in temporary directories. No real repo source files touched. Covers:

- Minimal manual import
- Discord research wishlist import
- JSON + Markdown output
- Gate defaults (auto_dream_allowed, human_review_required, import_status)
- Empty query rejection
- Unknown source normalization
- Unknown kind normalization
- Auto-patch request → high risk
- Broad migration → medium/high risk
- Secret redaction + flag in risk_reasons
- Input JSON error handling
- Result truncation
- Allowed next steps list
- Forbidden next steps list
- No forbidden imports/calls (AST check)
- Output artifact containment
- Markdown guardrail text
- CLI writes artifacts
