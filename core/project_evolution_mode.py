"""Immutable metadata for the broad Project Evolution Mode workflow.

Safe to import anywhere: this module is metadata only. It has no runtime
pipeline imports, no model/API hooks, no patch/validation execution, and no
side effects.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class ProjectEvolutionStage:
    name: str
    description: str
    responsibilities: Tuple[str, ...]
    artifacts: Tuple[str, ...]
    approval: Tuple[str, ...]
    guardrails: Tuple[str, ...]


PROJECT_EVOLUTION_STAGES: tuple[ProjectEvolutionStage, ...] = (
    ProjectEvolutionStage(
        name="Intake",
        description=(
            "Capture the evolution request, target repo, goal, constraints, "
            "and risk tolerance before broad analysis starts."
        ),
        responsibilities=(
            "Capture the requested migration, architecture change, provider swap, or multi-file feature goal in the operator's own words.",
            "Capture repo path, current branch/state assumptions, and the intended project boundary.",
            "Capture constraints such as deadlines, compatibility promises, rollback expectations, and dependency-install limits.",
            "Capture explicit risk tolerance so later plan choices can stay conservative or aggressive on purpose.",
        ),
        artifacts=(
            "evolution request summary",
            "repo_path and project boundary notes",
            "constraints and risk-tolerance notes",
            "initial success criteria",
        ),
        approval=(
            "Human supplies the repo path, goal, and constraints.",
            "Supplying an evolution request does not approve patch generation or dependency changes.",
        ),
        guardrails=(
            "Do not read the whole repo blindly at intake.",
            "Do not generate patches, run validation, or change runtime behavior from this metadata helper.",
            "Do not treat broad intent as approval to write.",
        ),
    ),
    ProjectEvolutionStage(
        name="Existing Map Inventory",
        description=(
            "Inventory the existing project-map, repo-librarian, indexer, "
            "graph, and search layers before proposing any new map behavior."
        ),
        responsibilities=(
            "Identify the current repo inventory and file-manifest layer already provided by core.repo_librarian.",
            "Identify the current indexing and Tree-sitter summary layer already provided by core.indexer.",
            "Identify the current project map and hotspot summarization layer already provided by graph.project_map.",
            "Identify the current graph builder, graph weights, semantic graph, and deep-understanding helpers already present in graph.builder, graph.weights, core.semantic_graph_pipeline, and reasoning.deep_project_understand.",
            "Decide which layers are reused as-is, which are upgraded for richer metadata, and which remain unchanged so Evolution Mode does not create a duplicated project-map system.",
        ),
        artifacts=(
            "component inventory",
            "reuse/extend/unchanged decision notes",
            "current map/search layer list",
        ),
        approval=(
            "Human can review the inventory before richer mapping is requested.",
            "Inventory findings are evidence, not approval to add a second map stack.",
        ),
        guardrails=(
            "Reuse or upgrade the existing project-map/search components instead of building a competing second system.",
            "Do not import runtime mapping code into this helper.",
            "Do not add Semble or any other new dependency in this contract slice.",
        ),
    ),
    ProjectEvolutionStage(
        name="Project Map",
        description=(
            "Build or refresh a richer project map focused on structure, "
            "entrypoints, boundaries, and files relevant to the requested evolution."
        ),
        responsibilities=(
            "Identify languages, package/dependency files, config files, entrypoints, test roots, documentation files, and generated/build folders to ignore.",
            "Record likely architecture layers, integration boundaries, external services, and environment-variable touch points.",
            "Preserve lightweight mapping for Debug Mode while allowing Evolution Mode to request richer project metadata when justified.",
            "Prefer structural summaries first so later full-file reads are intentional instead of default.",
        ),
        artifacts=(
            "project map snapshot",
            "repo structure summary",
            "ignore-list notes",
            "architecture-layer sketch",
        ),
        approval=(
            "Human may review the richer map before broad patch planning starts.",
            "A project map is navigation evidence, not approval to patch.",
        ),
        guardrails=(
            "Do not replace the existing debug-oriented project map for normal repair runs.",
            "Do not force full-repo file reads when structural metadata is enough.",
            "Do not treat generated/build output as source-of-truth architecture.",
        ),
    ),
    ProjectEvolutionStage(
        name="Architecture Read",
        description=(
            "Select and read the most relevant full files needed to understand "
            "architecture and migration touch points."
        ),
        responsibilities=(
            "Choose selected full files only when structure, ownership, or integration boundaries cannot be understood from snippets or summaries.",
            "Read entrypoints, dependency/provider abstractions, config loaders, test harnesses, and integration seams most likely to move in the requested change.",
            "Record why each file was read so the plan can justify its context window.",
        ),
        artifacts=(
            "selected full-file list",
            "file-read rationale",
            "architecture notes",
        ),
        approval=(
            "Human can inspect which full files were selected for broad understanding.",
            "Selected reads still do not approve patch generation.",
        ),
        guardrails=(
            "Read selected full files, not every file in the repository.",
            "Do not blindly read the full repo.",
            "Do not let Evolution Mode change Debug Mode's minimal-read default.",
        ),
    ),
    ProjectEvolutionStage(
        name="Impact Analysis",
        description=(
            "Trace the modules, dependencies, compatibility risks, and test "
            "surface that the requested evolution is likely to affect."
        ),
        responsibilities=(
            "Identify affected modules, dependency edges, and integration boundaries.",
            "Identify compatibility risks such as API shape drift, embedding-dimension drift, config/env changes, rollout sequencing, and rollback triggers.",
            "Identify tests, docs, config, and migration checks that will need updates if patching proceeds.",
        ),
        artifacts=(
            "impact matrix",
            "dependency-edge notes",
            "compatibility and rollout risks",
            "test/doc/config impact list",
        ),
        approval=(
            "Human reviews the blast radius before patching is proposed.",
            "Impact analysis is advisory until a plan is approved.",
        ),
        guardrails=(
            "Do not skip impact analysis for multi-file work.",
            "Do not collapse risks into a one-line summary when rollback and compatibility details matter.",
            "Do not run migrations or installs from the metadata helper.",
        ),
    ),
    ProjectEvolutionStage(
        name="Migration Plan",
        description=(
            "Turn the impact analysis into a human-readable, file-aware plan "
            "before any patch generation happens."
        ),
        responsibilities=(
            "List likely changed files and the reason each file would change.",
            "List risk notes, tests to run, config/docs updates, and rollback considerations.",
            "Describe phased sequencing when a safer migration path exists than one broad patch.",
        ),
        artifacts=(
            "human-readable migration plan",
            "likely changed file list",
            "test plan",
            "rollback notes",
        ),
        approval=(
            "Human reviews the migration plan before patch generation.",
            "Plan approval is the explicit gate between analysis and any future multi-file patch work.",
        ),
        guardrails=(
            "Produce a migration plan before patching.",
            "Do not generate patches from impact notes alone.",
            "Do not auto-upgrade dependencies or providers from this contract slice.",
        ),
    ),
    ProjectEvolutionStage(
        name="Approval Gate",
        description=(
            "Require an explicit human decision before any future patch "
            "generation for broad changes can begin."
        ),
        responsibilities=(
            "Record whether the operator approved, rejected, or requested revision of the migration plan.",
            "Keep patch generation blocked until approval is explicit.",
            "Preserve a reviewable record of the decision and any scope limits attached to it.",
        ),
        artifacts=(
            "approval decision",
            "approval scope notes",
            "revision requests when present",
        ),
        approval=(
            "Human approval is required before patch generation.",
            "Silence, context gathering, or prior debug approval do not count as evolution approval.",
        ),
        guardrails=(
            "Require human approval before patch generation.",
            "Do not infer approval from a broad request.",
            "Do not bypass operator review for multi-file evolution work.",
        ),
    ),
    ProjectEvolutionStage(
        name="Patch Execution",
        description=(
            "Describe the future execution phase for controlled, minimal, "
            "validated multi-file patches without wiring it in yet."
        ),
        responsibilities=(
            "Reserve a future phase for controlled multi-file patch generation after approval.",
            "Keep future patches minimal, explicit, and validated against the approved plan.",
            "Keep docs, config, tests, and code changes aligned with the approved migration scope.",
        ),
        artifacts=(
            "future patch set",
            "changed-file bundle",
            "validation results",
        ),
        approval=(
            "Execution belongs to a later phase only after the approval gate is satisfied.",
            "This contract slice does not itself authorize or implement execution.",
        ),
        guardrails=(
            "Do not wire Project Evolution Mode into runtime patch generation in B.1.",
            "Do not add automatic dependency upgrades, GitHub writes, or remote worker execution here.",
            "Do not change existing patch generation behavior for Debug Mode.",
        ),
    ),
    ProjectEvolutionStage(
        name="Evidence",
        description=(
            "Preserve the map, plan, approvals, selected files, and validation "
            "artifacts so evolution work can be reviewed or replayed safely."
        ),
        responsibilities=(
            "Store the project map, inventory, selected full files, impact analysis, migration plan, approvals, and validation evidence.",
            "Preserve replay/debug artifacts so broad changes remain inspectable instead of opaque.",
            "Keep evidence reviewable without forcing future automation hooks on today’s workflow.",
        ),
        artifacts=(
            "project map and inventory artifacts",
            "selected-file record",
            "plan and approval record",
            "validation and replay/debug artifacts",
        ),
        approval=(
            "Evidence supports review, rollback, and handoff; it is not an execution shortcut.",
            "Future automation can consume evidence only after explicit later design work.",
        ),
        guardrails=(
            "Do not mutate benchmark scoring, lessons, or runtime behavior while recording evidence.",
            "Do not make future automation hooks active in B.1.",
            "Do not hide the approval trail for broad project changes.",
        ),
    ),
)


def get_project_evolution_stages() -> tuple[ProjectEvolutionStage, ...]:
    return PROJECT_EVOLUTION_STAGES


def canonical_evolution_stage_names() -> tuple[str, ...]:
    return tuple(stage.name for stage in PROJECT_EVOLUTION_STAGES)
