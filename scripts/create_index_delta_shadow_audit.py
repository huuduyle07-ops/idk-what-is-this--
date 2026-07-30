"""Create deterministic INDEX.1E.1 shadow-dispatch audit artifacts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOC_PATH = (
    Path("docs")
    / "audits"
    / "2026-07-29-index-1e-1-shadow-delta-dispatch.md"
)
AGENT_JSON_PATH = (
    Path(".agent")
    / "audits"
    / "index-1e-1-shadow-delta-dispatch.json"
)
AGENT_MD_PATH = (
    Path(".agent")
    / "audits"
    / "index-1e-1-shadow-delta-dispatch.md"
)


def build_report(
    *,
    validation: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    validation_block: dict[str, Any] = {
        "focused_tests": "360 passed, 4 skipped",
        "compatibility_tests": "159 passed",
        "compileall": "passed",
        "phase_registry": (
            "valid; 113 phases; 110 complete; 3 proposed; 7 INDEX"
        ),
        "phase_picker": (
            "valid; 110 history; 0 deferred; DOGFOOD.1B remains top"
        ),
        "benchmark_check": "54 passed, 0 errors",
        "git_diff_check": (
            "passed; informational existing LF-to-CRLF warnings only"
        ),
        "repository_wide_observed": {
            "passed": 6366,
            "skipped": 6,
            "failed": 48,
        },
        "repository_passed_delta": 57,
        "baseline_failure_node_ids_reproduced": 48,
        "new_failures": 0,
        "authoritative_index_failures": 0,
        "unclassified_failures": 0,
    }
    validation_block.update(dict(validation or {}))
    return {
        "schema_version": 1,
        "report_kind": "index_1e_1_shadow_delta_dispatch",
        "phase_id": "INDEX.1E.1",
        "status": "INDEX_1E_1_COMPLETE_WITH_WARNINGS",
        "generated_for_date": "2026-07-29",
        "integration_seam": {
            "entrypoint": "core.indexer.index_repository",
            "position": (
                "after shared RepositoryInventory, canonical scope, "
                "persistence observation, and identity observation; before "
                "the unchanged full-processing file loop"
            ),
            "web_entrypoint": "web.runner.run_agent_web",
            "web_uses_same_seam": True,
            "second_dispatcher_created": False,
        },
        "manifest_load_outcomes": [
            "loaded",
            "missing",
            "invalid",
            "root_mismatch",
            "repository_mismatch",
            "epoch_mismatch",
            "scope_mismatch",
            "unsupported_schema",
        ],
        "manifest_safety": {
            "bounded_read_bytes": 4 * 1024 * 1024,
            "descriptor_bound_hashing": True,
            "duplicate_json_keys_rejected": True,
            "duplicate_canonical_paths_rejected": True,
            "unsafe_paths_rejected": True,
            "policy_fingerprint_validated": True,
            "invalid_manifest_used_for_deletions": False,
            "invalid_manifest_rewritten": False,
        },
        "observed_applied_boundary": {
            "previous_applied_role": (
                "historical canonical state committed before this operation"
            ),
            "current_observed_role": (
                "request-scoped filesystem observation with no persistence "
                "or completion authority"
            ),
            "observed_saved_as_applied": False,
            "applied_manifest_advance": False,
            "trusted_current_receipt_created": False,
        },
        "membership": {
            "source": "shared RepositoryInventory",
            "translation": (
                "RepositoryInventory.canonical_index_entries"
            ),
            "repository_members_distinguished": True,
            "indexable_members_distinguished": True,
            "manifest_control_files_distinguished": True,
            "non_indexable_metadata_distinguished": True,
            "additional_repository_membership_walks": 0,
        },
        "runs": {
            "A_cold": {
                "manifest_load_status": "missing",
                "delta": {
                    "added": 3,
                    "modified": 0,
                    "deleted": 0,
                    "unchanged": 0,
                },
                "planned": {
                    "parse": 3,
                    "embed": 3,
                    "replace": 3,
                    "delete": 0,
                },
                "actual_production": {
                    "parsed": 3,
                    "embedded": 3,
                    "replaced": 3,
                    "direct_file_deletions": 0,
                    "reconciliations": 1,
                },
            },
            "B_unchanged": {
                "manifest_load_status": "loaded",
                "delta": {
                    "added": 0,
                    "modified": 0,
                    "deleted": 0,
                    "unchanged": 3,
                },
                "planned": {
                    "parse": 0,
                    "embed": 0,
                    "replace": 0,
                    "delete": 0,
                },
                "actual_production": {
                    "parsed": 3,
                    "embedded": 3,
                    "replaced": 3,
                    "direct_file_deletions": 0,
                    "reconciliations": 1,
                },
                "expected_shadow_only_mismatch": True,
                "shadow_plan_remains_valid": True,
            },
            "C_one_modified": {
                "manifest_load_status": "loaded",
                "delta": {
                    "added": 0,
                    "modified": 1,
                    "deleted": 0,
                    "unchanged": 2,
                },
                "planned": {
                    "parse": 1,
                    "embed": 1,
                    "replace": 1,
                    "delete": 0,
                },
                "actual_production": {
                    "parsed": 3,
                    "embedded": 3,
                    "replaced": 3,
                    "direct_file_deletions": 0,
                    "reconciliations": 1,
                },
                "expected_shadow_only_mismatch": True,
            },
            "D_one_deleted": {
                "manifest_load_status": "loaded",
                "delta": {
                    "added": 0,
                    "modified": 0,
                    "deleted": 1,
                    "unchanged": 2,
                },
                "planned": {
                    "parse": 0,
                    "embed": 0,
                    "replace": 0,
                    "delete": 1,
                },
                "actual_production": {
                    "parsed": 2,
                    "embedded": 2,
                    "replaced": 2,
                    "direct_file_deletions": 0,
                    "reconciliations": 1,
                },
                "expected_shadow_only_mismatch": True,
                "deletion_path_parity_available": False,
            },
            "invalid_manifest": {
                "manifest_load_status": "invalid",
                "observed_manifest_built": True,
                "delta_available": False,
                "planner_status": "planner_unavailable",
                "production_compatibility_continues": True,
                "artifact_rewritten": False,
            },
        },
        "shadow_authority": {
            "authoritative": False,
            "plan_controls_execution": False,
            "still_full_processing": True,
            "file_skip_dispatch_added": False,
            "database_mutation_dispatch_added": False,
            "deletion_dispatch_added": False,
            "shadow_plan_changes_reconciliation_dispatch": False,
            "unsafe_entry_guard_suppresses_reconciliation": True,
            "manifest_write_added": False,
        },
        "embedding_compatibility": {
            "source": (
                "applied-manifest signature compared with the current "
                "configured signature"
            ),
            "exact_signature_match_supported": True,
            "same_dimension_drift_supported": True,
            "dimension_mismatch_supported": True,
            "cold_build_supported": True,
            "legacy_missing_signature_fails_closed": True,
            "environment_override_grants_authority": False,
        },
        "identity": {
            "confirmed_is_future_candidate_only": True,
            "initial_confirmation_blocks_future_execution": True,
            "major_change_blocks_future_deletion": True,
            "archived_or_blocked_fails_closed": True,
            "project_tag_grants_authority": False,
            "production_scope_mismatch_fails_closed": True,
        },
        "persistence_disabled": {
            "observed_manifest_may_build": True,
            "delta_may_classify": True,
            "plan_may_be_described": True,
            "trusted_persistent_completion": False,
            "manifest_advance_allowed": False,
        },
        "traversal": {
            "canonical_operation_membership_walks": 1,
            "web_operation_membership_walks": 1,
            "manifest_additional_walks": 0,
            "graph_additional_walks": 0,
            "hidden_os_walk": False,
            "hidden_rglob": False,
        },
        "manifest_immutability": {
            "cold_created_authoritative_manifest": False,
            "unchanged_byte_equal": True,
            "modified_byte_equal": True,
            "deleted_byte_equal": True,
            "persistence_failure_byte_equal": True,
            "reconciliation_failure_byte_equal": True,
            "persistence_disabled_byte_equal": True,
            "identity_blocked_byte_equal": True,
        },
        "compatibility": {
            "existing_top_level_fields_preserved": True,
            "delta_shadow_additive": True,
            "web_runner_uses_canonical_entrypoint": True,
            "cli_callers_may_ignore_new_block": True,
            "retriever_setup": {
                "audited": True,
                "finding": "unchanged",
                "detail": (
                    "retriever setup continues to use canonical repository "
                    "scope and ignores the additive delta_shadow block"
                ),
            },
            "code_dna": {
                "audited": True,
                "finding": "unchanged",
                "detail": (
                    "Code DNA continues to consume the shared inventory and "
                    "receives no shadow execution authority"
                ),
            },
            "graph_builders": {
                "audited": True,
                "finding": "unchanged",
                "detail": (
                    "graph builders continue to consume the shared inventory "
                    "and add zero repository-membership walks"
                ),
            },
            "health_status_surfaces": {
                "audited": True,
                "finding": "unchanged_or_additive",
                "detail": (
                    "health and status surfaces preserve existing fields and "
                    "make no new trusted-current or mutation-authority claim"
                ),
            },
            "activation_graph_runtime_added": False,
            "legacy_namespace_migration_added": False,
            "network_or_model_call_added": False,
            "background_worker_added": False,
            "benchmark_behavior_changed": False,
        },
        "baseline_comparison": {
            "prior": {
                "passed": 6309,
                "skipped": 5,
                "known_unrelated_failures": 48,
                "authoritative_index_failures": 0,
                "unclassified_failures": 0,
            },
            "observed": validation_block.get(
                "repository_wide_observed"
            ),
            "new_failures": validation_block.get("new_failures"),
        },
        "validation": {
            key: validation_block[key]
            for key in sorted(validation_block)
            if key != "repository_wide_observed"
            and key != "new_failures"
        },
        "warnings": [
            (
                "Legacy applied manifests without a persisted embedding "
                "signature fail closed with planner_unavailable when "
                "embeddings are enabled; cold builds and signature-bound "
                "manifests remain deterministic."
            ),
            (
                "The repository-wide suite retains 48 classified unrelated "
                "baseline failures and must not be described as fully green."
            ),
            (
                "Production extract_file_text still has a pre-existing "
                "check-then-open race; descriptor-bound reads are future "
                "security hardening outside this shadow-dispatch phase."
            ),
            (
                "Production reconciliation exposes aggregate deletion "
                "counters rather than per-file deletion paths, so Run D "
                "cannot claim deletion path parity."
            ),
        ],
        "readiness": {
            "decision": "ready_for_index_1e_2_design",
            "recommended_next_phase": (
                "INDEX.1E.2 - Unchanged File Fast Path"
            ),
            "next_phase_started": False,
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    runs = report["runs"]
    baseline = report["baseline_comparison"]
    observed = baseline.get("observed")
    observed_text = (
        "not run"
        if observed is None
        else (
            f"{observed['passed']} passed, {observed['skipped']} skipped, "
            f"{observed['failed']} failed"
        )
    )
    lines = [
        "# INDEX.1E.1 - Manifest Load and Shadow Delta Plan Dispatch",
        "",
        f"**Status:** `{report['status']}`",
        "",
        "## Integration seam",
        "",
        (
            "`core.indexer.index_repository` prepares the diagnostic after "
            "the one shared inventory and identity/scope observation, then "
            "continues its existing full-processing loop. The web runner "
            "uses that same entrypoint."
        ),
        "",
        "## Applied/observed boundary",
        "",
        (
            "The previous applied manifest remains historical authority. "
            "The current observed manifest is request-scoped evidence only; "
            "it is never saved, advanced, or converted into a trusted-current "
            "receipt in this phase."
        ),
        "",
        "## Manifest loading",
        "",
        (
            "Explicit outcomes: "
            + ", ".join(
                f"`{value}`"
                for value in report["manifest_load_outcomes"]
            )
            + ". Reads are bounded to 4 MiB; duplicate keys, unsafe paths, "
            "invalid policy fingerprints, and identity/epoch/scope mismatch "
            "fail closed. File hashes are descriptor-bound and verify stable "
            "file identity."
        ),
        "",
        "## Run characterization",
        "",
        "| Run | Delta A/M/D/U | Planned P/E/R/D | Actual P/E/R | Result |",
        "|---|---:|---:|---:|---|",
    ]
    labels = (
        ("A_cold", "A cold"),
        ("B_unchanged", "B unchanged"),
        ("C_one_modified", "C modified"),
        ("D_one_deleted", "D deleted"),
    )
    for key, label in labels:
        item = runs[key]
        delta = item["delta"]
        planned = item["planned"]
        actual = item["actual_production"]
        result = (
            "expected shadow/full mismatch"
            if item.get("expected_shadow_only_mismatch")
            else "cold parity"
        )
        lines.append(
            f"| {label} | "
            f"{delta['added']}/{delta['modified']}/"
            f"{delta['deleted']}/{delta['unchanged']} | "
            f"{planned['parse']}/{planned['embed']}/"
            f"{planned['replace']}/{planned['delete']} | "
            f"{actual['parsed']}/{actual['embedded']}/"
            f"{actual['replaced']} | {result} |"
        )
    lines.extend(
        [
            "",
            (
                "Run B is the decisive shadow-only proof: the plan recommends "
                "zero changed-file work while production still parses, embeds, "
                "and replaces all three files."
            ),
            "",
            "## Traversal and immutability",
            "",
            (
                "Canonical and web operations each perform exactly one "
                "repository-membership walk. Manifest and graph consumers add "
                "zero. Applied manifests remain byte-for-byte unchanged for "
                "unchanged, modified, deleted, persistence-failure, "
                "reconciliation-failure, persistence-disabled, and "
                "identity-blocked runs; a cold run creates none."
            ),
            "",
            "## Compatibility",
            "",
            (
                "`delta_shadow` is additive. For stable valid entries, "
                "production parsing, embedding, replacement, "
                "deletion-by-reconciliation, completion, and manifest "
                "behavior remain authoritative full-processing behavior. "
                "A post-inventory entry that becomes unsafe now fails closed "
                "before replacement and suppresses reconciliation; this "
                "guardrail is independent of the shadow plan. No Activation "
                "Graph runtime, migration, model/network call, or worker was "
                "added."
            ),
            "",
            (
                "Compatibility review explicitly audited retriever setup as "
                "unchanged, Code DNA as unchanged, graph builders as unchanged "
                "with zero added membership walks, and health/status surfaces "
                "as unchanged or additive with no new trusted-current or "
                "mutation-authority claim."
            ),
            "",
            "## Validation",
            "",
            (
                f"Prior baseline: {baseline['prior']['passed']} passed, "
                f"{baseline['prior']['skipped']} skipped, "
                f"{baseline['prior']['known_unrelated_failures']} known "
                "unrelated failures. Observed repository-wide result: "
                f"{observed_text}."
            ),
            "",
            "## Warnings",
            "",
        ]
    )
    lines.extend(
        f"- {warning}" for warning in report["warnings"]
    )
    lines.extend(
        [
            "",
            "## Readiness",
            "",
            (
                "Ready to design `INDEX.1E.2 - Unchanged File Fast Path`. "
                "INDEX.1E.2 was not started or authorized here."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def _contained_path(root: Path, relative: Path) -> Path:
    resolved_root = root.resolve()
    candidate = (resolved_root / relative).resolve()
    candidate.relative_to(resolved_root)
    return candidate


def write_report(
    report: Mapping[str, Any],
    *,
    repo_root: str | Path = PROJECT_ROOT,
) -> dict[str, str]:
    root = Path(repo_root)
    json_path = _contained_path(root, AGENT_JSON_PATH)
    agent_md_path = _contained_path(root, AGENT_MD_PATH)
    doc_path = _contained_path(root, DOC_PATH)
    for path in (json_path, agent_md_path, doc_path):
        path.parent.mkdir(parents=True, exist_ok=True)

    serialized = json.dumps(
        dict(report),
        indent=2,
        ensure_ascii=False,
        sort_keys=True,
    ) + "\n"
    markdown = render_markdown(report)
    json_path.write_text(
        serialized,
        encoding="utf-8",
        newline="\n",
    )
    agent_md_path.write_text(
        markdown,
        encoding="utf-8",
        newline="\n",
    )
    doc_path.write_text(
        markdown,
        encoding="utf-8",
        newline="\n",
    )
    return {
        "agent_json": str(json_path),
        "agent_markdown": str(agent_md_path),
        "docs_markdown": str(doc_path),
    }


def _main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=PROJECT_ROOT,
    )
    args = parser.parse_args()
    paths = write_report(
        build_report(),
        repo_root=args.repo_root,
    )
    print(json.dumps(paths, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
