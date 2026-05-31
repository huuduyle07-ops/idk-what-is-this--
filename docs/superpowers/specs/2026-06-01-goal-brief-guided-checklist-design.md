# Goal Brief Guided Checklist Design

## Purpose

Make Goal Brief easier to use by turning missing schema fields into a task-shaped checklist. The user should always know the next useful thing to provide without reading raw JSON field names.

## Scope

This change improves the existing Goal Brief web panel. It keeps the current storage schema, routes, chat transcript, parser, and raw details section. It does not add command execution, automatic patching, or a Dream handoff.

## Recommended Approach

Use a guided checklist in the right panel while keeping chat and paste-based replies on the left. The checklist becomes the primary navigation aid; chat remains useful for messy terminal output and the interviewer transcript.

Rows are grouped as:

- Task: task type.
- Evidence: command or manual check, expected result, observed result.
- Scope: allowed files.
- Validation: validation command and success criteria.

Each row shows:

- A plain-English label.
- A short state: complete or missing.
- The captured value when present.
- A small action that inserts a labeled template into the reply box.

Examples:

- Task type inserts `problem_type: bug_fix`.
- Expected result inserts `expected_result: all tests pass`.
- Allowed files inserts `allowed_files: path/to/file.py, tests/test_file.py`.
- Validation command inserts `validation_command: python -m pytest tests -q`.

## UI Behavior

The summary panel shows progress such as `2 of 7 complete`, then checklist groups. Missing rows are visually distinct but not alarming. Completed rows show their value with wrapping so long commands and file paths do not overlap.

Quick reply chips remain near the reply box, but they should be more practical:

- Bug fix.
- Feature.
- Expected pass.
- Actual failure.
- Allowed files.
- Validation command.
- No files forbidden.

The raw evidence, missing field list, suggested commands, and final prompt stay inside `Raw details`.

## Data Flow

The backend continues returning `brief`, `summary`, `assistant_message`, and paths. The frontend derives checklist rows from `brief` and existing missing data. Clicking a checklist row only inserts text into the reply textarea; submitting still uses `/goal-brief/update`.

No schema changes are required. The saved `goal_brief.json` must remain compatible with `GOAL_BRIEF_SCHEMA`.

## Error Handling

If no brief exists, the checklist shows a quiet empty state asking for a goal. If the backend request fails, the existing status line displays the error and the current checklist remains untouched. If a field is absent or malformed, the row is treated as missing.

## Testing

Add focused tests that verify:

- The web panel includes the guided checklist container and the new quick replies.
- Existing route behavior still creates and updates drafts.
- Existing schema invariants remain unchanged.

Manual verification should load the Goal Brief tab, start a brief, click checklist actions, send a reply, and confirm completed rows update without exposing raw schema details as the primary experience.
