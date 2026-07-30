import os
import sys
from pathlib import Path
from graph.builder import build_graph_from_repo
# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from typing import Optional
from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS
from core.retriever import extract_file_text, build_code_units, get_embedding
from core.treesitter_parse import parse_code_with_treesitter
from database.code_index import (
    db_enabled as code_index_db_enabled,
    init_db,
    reconcile_code_index_scope,
    replace_code_index_for_file,
)
from core.credential_redaction import redact_credentials
from core.index_completion import (
    AUXILIARY_AUTHORITY_OUTPUT,
    EMBEDDING_STATUS_BLOCKED,
    EMBEDDING_STATUS_EMBEDDED,
    EMBEDDING_STATUS_FAILED,
    EMBEDDING_STATUS_NOT_REQUIRED,
    EMBEDDING_STATUS_PENDING,
    FILE_ACTION_FULL_REFRESH,
    FILE_PERSISTENCE_BLOCKED,
    FILE_PERSISTENCE_EMBEDDING_FAILED,
    FILE_PERSISTENCE_PARSE_FAILED,
    FILE_PERSISTENCE_PENDING,
    FILE_PERSISTENCE_PERSISTED,
    FILE_PERSISTENCE_REPLACEMENT_FAILED,
    PROCESSING_STATUS_PARSE_FAILED,
    PROCESSING_STATUS_PROCESSED,
    AuxiliaryEvidence,
    FilePersistenceEvidence,
    PersistenceEvidence,
    ProcessingEvidence,
    ReconciliationEvidence,
    classify_index_completion,
)
from core.index_delta_shadow import (
    attach_production_diagnostics,
    build_index_delta_shadow,
)
from core.dependency_target import (
    resolve_dependency_target,
)
from graph.project_map import summarize_file, build_project_map, write_project_map
from core.security import is_safe_path
from core.repo_librarian import (
    write_phantom_limb_report,
)
from core.repository_inventory import (
    RepositoryInventory,
    create_repository_inventory,
    is_canonical_index_path,
    should_skip_index_filename,
    validate_repository_inventory,
)
from core.code_dna import compute_dna, save_dna
from core.phantom_limb import scan as scan_phantom_limb
import json

def index_repository(
    repo_path: str,
    project_tag: Optional[str] = None,
    *,
    inventory: RepositoryInventory | None = None,
    identity_state=None,
    completion_run_id: str | None = None,
    observed_state_id: str | None = None,
    include_operation_artifacts: bool = False,
):
    from core.repository_identity import build_code_index_scope
    file_summaries = []
    repo_path = os.path.abspath(repo_path)

    # A semantic label may be absent. Only index_scope controls DB authority
    # and replacement; this value is returned for display/compatibility only.

    semantic_project_tag = (
        project_tag.strip()
        if isinstance(project_tag, str) and project_tag.strip()
        else None
    )

    operation_inventory = (
        validate_repository_inventory(repo_path, inventory)
        if inventory is not None
        else create_repository_inventory(repo_path)
    )
    inventory_summary = operation_inventory.summary()
    index_scope = build_code_index_scope(repo_path)
    repo_entries = operation_inventory.canonical_index_entry_pairs

    repository_files = set(
        operation_inventory.relative_paths(None)
    )

    indexable_count = inventory_summary["indexable_count"]
    
    print(
        f"🚀 Starting Project-Wide Indexing: {repo_path} "
        f"[project_tag={semantic_project_tag or '(none)'}, "
        f"index_scope={index_scope}, "
        f"files={indexable_count}]"
    )

    # Ensure DB is initialized when persistence is enabled.
    persistence_enabled = code_index_db_enabled()
    db_available = persistence_enabled
    persistence_skip_reason = (
        None
        if db_available
        else "persistence_disabled"
    )
    persistence_attempted = False
    persistence_failure_latched = False
    persistence_failure_stage = None
    persistence_error_category = None
    persistence_error_message = None
    delta_shadow = build_index_delta_shadow(
        repo_path,
        inventory=operation_inventory,
        identity_state=identity_state,
        production_index_scope=index_scope,
        persistence_enabled=persistence_enabled,
        database_available=persistence_enabled,
        embedding_enabled=(
            os.getenv(
                "INDEX_USE_EMBEDDINGS",
                "true",
            ).strip().lower()
            not in {"false", "0", "no"}
        ),
        index_entries=repo_entries,
    )
    if not inventory_summary["ok"]:
        error = RuntimeError(
            "Indexing aborted: repo has 0 indexable files.\n"
            + json.dumps(
                inventory_summary,
                indent=2,
                ensure_ascii=False,
            )
        )
        error.delta_shadow = delta_shadow
        raise error
    if db_available:
        persistence_attempted = True
        try:
            init_db()
        except Exception as e:
            db_available = False
            persistence_failure_latched = True
            persistence_skip_reason = "db_initialization_failed"
            safe_error = redact_credentials(e)
            persistence_failure_stage = "initialization"
            persistence_error_category = "database_initialization_failed"
            persistence_error_message = safe_error
            print(
                f"⚠️ DB initialization failed: {safe_error}. "
                "Indexing will proceed, but results won't be saved."
            )

    files_indexed = 0
    units_saved = 0
    indexed_repository_files: set[str] = set()
    file_persistence_evidence: list[FilePersistenceEvidence] = []
    processing_failed_files: list[str] = []
    processing_warnings: list[str] = []
    unattempted_required_files: list[str] = []

    def record_inventory_entry_failure(
        rel_path: str,
        *,
        category: str,
        message: str,
    ) -> None:
        nonlocal persistence_failure_latched
        nonlocal persistence_failure_stage
        nonlocal persistence_skip_reason
        processing_failed_files.append(rel_path)
        persistence_failure_latched = True
        persistence_failure_stage = (
            persistence_failure_stage
            or (
                "processing"
                if persistence_enabled
                else "persistence"
            )
        )
        persistence_skip_reason = (
            persistence_skip_reason or "processing_failed"
        )
        file_persistence_evidence.append(
            FilePersistenceEvidence(
                file_path=rel_path,
                action=FILE_ACTION_FULL_REFRESH,
                processing_status=PROCESSING_STATUS_PARSE_FAILED,
                embedding_status=EMBEDDING_STATUS_NOT_REQUIRED,
                persistence_status=(
                    FILE_PERSISTENCE_PARSE_FAILED
                    if persistence_enabled
                    else FILE_PERSISTENCE_BLOCKED
                ),
                embedding_required=False,
                error_category=category,
                error_message=message,
            )
        )
        print(f"ERR: Failed to index {rel_path}: {message}")

    for file_path_obj, rel_path_obj in repo_entries:
        file_path = str(file_path_obj)
        rel_path = str(rel_path_obj).replace("\\", "/")

        if should_skip_index_file(file_path_obj.name):
            continue

        if not file_path_obj.is_file():
            safe_error = (
                "inventory entry disappeared before processing; "
                "the operation snapshot was not rescanned"
            )
            record_inventory_entry_failure(
                rel_path,
                category="inventory_entry_unavailable",
                message=safe_error,
            )
            continue

        # Rule 1: Security boundary
        if not is_canonical_index_path(
            file_path_obj,
            repo_root=repo_path,
            relative_path=rel_path_obj,
        ) or not is_safe_path(
            file_path,
            allowed_roots=[repo_path],
        ):
            record_inventory_entry_failure(
                rel_path,
                category="inventory_entry_unsafe",
                message=(
                    "inventory entry failed canonical safety "
                    "revalidation; reconciliation was suppressed"
                ),
            )
            continue

        # Rule 2: Supported extensions
        ext = rel_path_obj.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        indexed_repository_files.add(rel_path)

        try:
            text = extract_file_text(file_path, repo_path=repo_path)
            if not is_canonical_index_path(
                file_path_obj,
                repo_root=repo_path,
                relative_path=rel_path_obj,
            ) or not is_safe_path(
                file_path,
                allowed_roots=[repo_path],
            ):
                record_inventory_entry_failure(
                    rel_path,
                    category="inventory_entry_unsafe",
                    message=(
                        "inventory entry became unsafe during "
                        "processing; replacement and reconciliation "
                        "were suppressed"
                    ),
                )
                continue
            if not text:
                text = ""

            language = LANGUAGE_MAP.get(ext)
            data = {"symbols": [], "imports": [], "calls": []}

            if language:
                try:
                    raw_data = parse_code_with_treesitter(text, language)
                    if isinstance(raw_data, dict):
                        data = raw_data
                    elif isinstance(raw_data, list):
                        data["symbols"] = raw_data
                except Exception as e:
                    processing_warnings.append(
                        f"tree_sitter_fallback: {rel_path}"
                    )
                    e = redact_credentials(e)
                    print(
                        f"⚠️ Tree-sitter parse failed for {rel_path}: {e}. "
                        "Falling back to text-based code units."
                    )
                    data = {"symbols": [], "imports": [], "calls": []}
            units = []

            if not data.get("symbols"):
                units = build_code_units(file_path, text)
            else:
                for node in data["symbols"]:
                    units.append({
                        "kind": node.get("kind", "unknown"),
                        "name": node.get("name", "unknown"),
                        "content": node.get("content", ""),
                        "execution_flow": node.get("execution_flow", ""),
                    })
            # Hard fallback for Codespaces / parser mismatch:
            # If Tree-sitter and build_code_units both fail to produce units,
            # still keep a file-level unit so indexing/control can continue.
            if not units and text.strip():
                units = [{
                    "kind": "file",
                    "name": rel_path,
                    "content": text,
                    "execution_flow": "Tree-sitter unavailable; using full-file text fallback.",
                }]
            summary_symbols = data.get("symbols", [])
            if not summary_symbols and units:
                summary_symbols = [
                    {
                        "kind": u.get("kind", "unknown"),
                        "name": u.get("name", "unknown"),
                        "content": u.get("content", ""),
                        "execution_flow": u.get("execution_flow", ""),
                    }
                    for u in units
                ]

            file_summaries.append(
                summarize_file(
                    rel_path=rel_path,
                    language=language or "unknown",
                    symbols=summary_symbols,
                    imports=data.get("imports", []),
                    calls=data.get("calls", []),
                )
            )
            dependency_rows = _build_dependency_rows(
                repo_path=repo_path,
                rel_path=rel_path,
                language=language or "",
                parsed_data=data,
                repository_files=repository_files,
            )
            use_index_embeddings = os.getenv(
                "INDEX_USE_EMBEDDINGS",
                "true",
            ).strip().lower() not in {"false", "0", "no"}
            unit_rows: list[dict] = []
            embedding_status = (
                EMBEDDING_STATUS_PENDING
                if units and use_index_embeddings
                else EMBEDDING_STATUS_NOT_REQUIRED
            )
            file_persistence_status = FILE_PERSISTENCE_PENDING
            file_error_category = None
            file_error_message = None

            if db_available:
                persistence_attempted = True
                persistence_stage = "embedding"
                try:
                    for unit in units:
                        embedding_list: list[float] | None = None

                        if use_index_embeddings:
                            embedding = get_embedding(
                                unit["content"]
                            )
                            if embedding is None:
                                raise RuntimeError(
                                    "Embedding provider returned no embedding "
                                    f"for {rel_path}::{unit.get('name')}"
                                )

                            embedding_list = embedding.tolist()

                        unit_rows.append({
                            "kind": unit["kind"],
                            "name": unit["name"],
                            "content": unit["content"],
                            "embedding": embedding_list,
                        })
                    if units and use_index_embeddings:
                        embedding_status = EMBEDDING_STATUS_EMBEDDED
                    persistence_stage = "replacement"
                    inserted_count = replace_code_index_for_file(
                        file_path=rel_path,
                        index_scope=index_scope,
                        code_units=unit_rows,
                        dependencies=dependency_rows,
                    )
                    units_saved += inserted_count
                    file_persistence_status = (
                        FILE_PERSISTENCE_PERSISTED
                    )
                except Exception as e:
                    safe_error = redact_credentials(e)
                    persistence_failure_latched = True
                    persistence_failure_stage = (
                        persistence_failure_stage
                        or persistence_stage
                    )
                    file_error_message = safe_error
                    if persistence_stage == "embedding":
                        embedding_status = EMBEDDING_STATUS_FAILED
                        file_persistence_status = (
                            FILE_PERSISTENCE_EMBEDDING_FAILED
                        )
                        file_error_category = "embedding_failed"
                        persistence_skip_reason = "embedding_failed"
                    else:
                        file_persistence_status = (
                            FILE_PERSISTENCE_REPLACEMENT_FAILED
                        )
                        file_error_category = "replacement_failed"
                        persistence_skip_reason = (
                            "file_replacement_failed"
                        )
                    persistence_error_category = (
                        persistence_error_category
                        or file_error_category
                    )
                    persistence_error_message = (
                        persistence_error_message
                        or safe_error
                    )
                    print(
                        f"⚠️ Atomic DB replacement failed for "
                        f"{rel_path}: {safe_error}"
                    )
                    db_available = False
            else:
                # No DB: still index for project map / control / phantom limb,
                # but skip persistence and embeddings.
                if persistence_enabled:
                    embedding_status = EMBEDDING_STATUS_PENDING
                    file_persistence_status = FILE_PERSISTENCE_PENDING
                    unattempted_required_files.append(rel_path)
                else:
                    embedding_status = EMBEDDING_STATUS_BLOCKED
                    file_persistence_status = FILE_PERSISTENCE_BLOCKED
                    file_error_category = "persistence_disabled"
            file_persistence_evidence.append(
                FilePersistenceEvidence(
                    file_path=rel_path,
                    action=FILE_ACTION_FULL_REFRESH,
                    processing_status=PROCESSING_STATUS_PROCESSED,
                    embedding_status=embedding_status,
                    persistence_status=file_persistence_status,
                    embedding_required=bool(
                        units and use_index_embeddings
                    ),
                    error_category=file_error_category,
                    error_message=file_error_message,
                )
            )
            files_indexed += 1
            print(
                f"OK: Indexed {rel_path} "
                f"({len(units)} symbols, "
                f"{len(data.get('imports', []))} imports, "
                f"{len(data.get('calls', []))} calls)"
            )
        except Exception as e:
            inventory_entry_unavailable = isinstance(
                e,
                FileNotFoundError,
            )
            safe_error = (
                "inventory entry disappeared during processing; "
                "the operation snapshot was not rescanned"
                if inventory_entry_unavailable
                else redact_credentials(e)
            )
            processing_failed_files.append(rel_path)
            persistence_failure_latched = True
            persistence_failure_stage = (
                persistence_failure_stage
                or (
                    "processing"
                    if persistence_enabled
                    else "persistence"
                )
            )
            persistence_skip_reason = (
                persistence_skip_reason or "processing_failed"
            )
            file_persistence_evidence.append(
                FilePersistenceEvidence(
                    file_path=rel_path,
                    action=FILE_ACTION_FULL_REFRESH,
                    processing_status=PROCESSING_STATUS_PARSE_FAILED,
                    embedding_status=EMBEDDING_STATUS_NOT_REQUIRED,
                    persistence_status=(
                        FILE_PERSISTENCE_PARSE_FAILED
                        if persistence_enabled
                        else FILE_PERSISTENCE_BLOCKED
                    ),
                    embedding_required=False,
                    error_category=(
                        "inventory_entry_unavailable"
                        if inventory_entry_unavailable
                        else "processing_failed"
                    ),
                    error_message=safe_error,
                )
            )
            print(
                f"ERR: Failed to index {rel_path}: "
                f"{safe_error}"
            )

    reconciliation = {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": None,
    }
    reconciliation_attempted = False
    reconciliation_ok = False
    reconciliation_error_category = None
    reconciliation_error_message = None
    if db_available and not persistence_failure_latched:
        reconciliation_attempted = True
        try:
            cleanup = reconcile_code_index_scope(
                index_scope=index_scope,
                current_files=indexed_repository_files,
            )
            reconciliation_ok = True
            reconciliation.update({
                "performed": True,
                **cleanup,
            })
        except Exception as e:
            safe_error = redact_credentials(e)
            reconciliation_error_category = "database_error"
            reconciliation_error_message = safe_error
            reconciliation["skipped_reason"] = (
                f"reconciliation_failed: {safe_error}"
            )
            print(
                "⚠️ Code-index scope reconciliation failed: "
                f"{safe_error}"
            )
    else:
        reconciliation["skipped_reason"] = (
            persistence_skip_reason
            or "persistence_unavailable_or_failed"
        )

    auxiliary_evidence: list[AuxiliaryEvidence] = []
    dna = compute_dna(
        repo_path,
        inventory=operation_inventory,
    )
    dna_path = save_dna(repo_path, dna)
    if dna_path is None:
        auxiliary_evidence.append(
            AuxiliaryEvidence(
                component="code_dna",
                authority=AUXILIARY_AUTHORITY_OUTPUT,
                attempted=True,
                ok=False,
                error_category="code_dna_write_failed",
                error_message="Code DNA output was not written",
            )
        )
    else:
        auxiliary_evidence.append(
            AuxiliaryEvidence(
                component="code_dna",
                authority=AUXILIARY_AUTHORITY_OUTPUT,
                attempted=True,
                ok=True,
            )
        )
    print(f"🧬 Code DNA: {dna['indent']}, {dna['naming']}, line~{dna['max_line_pref']}c")
    print(f"\nSummary:")
    print(f"Files processed: {files_indexed}")
    print(f"Symbols stored: {units_saved}")
    if files_indexed == 0 and not processing_failed_files:
        raise RuntimeError(
            "Indexing aborted: repo had indexable files, "
            "but 0 files were successfully processed."
        )

    if os.getenv("BENCHMARK_SKIP_PHANTOM", "").lower() == "true":
        phantom_findings: list = []
        phantom_path = None
    else:
        phantom_findings = scan_phantom_limb(file_summaries, repo_path)
        phantom_path = write_phantom_limb_report(repo_path, phantom_findings)
        if phantom_findings:
            warn_count = sum(1 for f in phantom_findings if f.get("severity") == "warn")
            print(
                f"Phantom Limb: {len(phantom_findings)} suggestion(s) "
                f"({warn_count} warn) written to: {phantom_path}"
            )
        else:
            print(f"Phantom Limb: no structural suggestions. Report written to: {phantom_path}")
        auxiliary_evidence.append(
            AuxiliaryEvidence(
                component="phantom_limb_report",
                authority=AUXILIARY_AUTHORITY_OUTPUT,
                attempted=True,
                ok=True,
            )
        )

    # Build project map (graph is only used to render the map, so skip both together)
    if os.getenv("BENCHMARK_SKIP_PROJECT_MAP", "").lower() == "true":
        graph = None
        map_path = None
    else:
        try:
            graph = build_graph_from_repo(
                repo_path,
                inventory=operation_inventory,
            )
            auxiliary_evidence.append(
                AuxiliaryEvidence(
                    component="program_graph",
                    authority=AUXILIARY_AUTHORITY_OUTPUT,
                    attempted=True,
                    ok=True,
                )
            )
        except Exception as e:
            safe_error = redact_credentials(e)
            auxiliary_evidence.append(
                AuxiliaryEvidence(
                    component="program_graph",
                    authority=AUXILIARY_AUTHORITY_OUTPUT,
                    attempted=True,
                    ok=False,
                    error_category="graph_build_failed",
                    error_message=safe_error,
                )
            )
            print(
                "⚠️ Graph build failed: "
                f"{safe_error}. Continuing without graph."
            )
            graph = None

        try:
            content = build_project_map(
                file_summaries,
                graph=graph,
                repo_path=repo_path,
                inventory=operation_inventory,
            )
        except Exception as e:
            safe_error = redact_credentials(e)
            auxiliary_evidence.append(
                AuxiliaryEvidence(
                    component="project_map_graph_rendering",
                    authority=AUXILIARY_AUTHORITY_OUTPUT,
                    attempted=True,
                    ok=False,
                    error_category="project_map_render_failed",
                    error_message=safe_error,
                )
            )
            print(
                "⚠️ Project map graph rendering failed: "
                f"{safe_error}. Retrying without graph."
            )
            content = build_project_map(
                file_summaries,
                graph=None,
                repo_path=repo_path,
                inventory=operation_inventory,
            )

        map_path = write_project_map(repo_path, content)
        auxiliary_evidence.append(
            AuxiliaryEvidence(
                component="project_map",
                authority=AUXILIARY_AUTHORITY_OUTPUT,
                attempted=True,
                ok=True,
            )
        )
        print(f"🗺️ Project map written to: {map_path}")
    persistence_ok = (
        persistence_enabled
        and persistence_attempted
        and not persistence_failure_latched
        and not unattempted_required_files
        and all(
            item.persistence_status == FILE_PERSISTENCE_PERSISTED
            for item in file_persistence_evidence
        )
    )
    completion = classify_index_completion(
        identity_state=identity_state,
        processing=ProcessingEvidence(
            attempted=True,
            ok=not processing_failed_files,
            failed_files=tuple(processing_failed_files),
            warnings=tuple(processing_warnings),
        ),
        persistence=PersistenceEvidence(
            required=True,
            enabled=persistence_enabled,
            attempted=persistence_attempted,
            ok=persistence_ok,
            index_scope=index_scope,
            files=tuple(file_persistence_evidence),
            required_files=tuple(
                item.file_path
                for item in file_persistence_evidence
            ),
            aborted_after_failure=bool(
                persistence_failure_latched
                and unattempted_required_files
            ),
            unattempted_required_files=tuple(
                unattempted_required_files
            ),
            failure_stage=persistence_failure_stage,
            error_category=persistence_error_category,
            error_message=persistence_error_message,
        ),
        reconciliation=ReconciliationEvidence(
            required=True,
            attempted=reconciliation_attempted,
            ok=reconciliation_ok,
            index_scope=(
                index_scope if reconciliation_attempted else None
            ),
            deleted_units=reconciliation["code_units_deleted"],
            deleted_dependencies=(
                reconciliation["dependencies_deleted"]
            ),
            preserved_external_targets=0,
            skipped_reason=reconciliation["skipped_reason"],
            error_category=reconciliation_error_category,
            error_message=reconciliation_error_message,
        ),
        auxiliary=tuple(auxiliary_evidence),
        completion_run_id=completion_run_id,
        observed_state_id=observed_state_id,
    )
    try:
        delta_shadow = attach_production_diagnostics(
            delta_shadow,
            file_outcomes=file_persistence_evidence,
            reconciliation=reconciliation,
            database_available=db_available,
            persistence_failure_stage=persistence_failure_stage,
        )
    except Exception:
        # Shadow comparison is additive diagnostics only. A diagnostic
        # serialization defect must not change the established production
        # indexing result.
        delta_shadow = dict(delta_shadow)
        delta_shadow["warnings"] = sorted(
            set(delta_shadow.get("warnings", ()))
            | {"production_comparison_failed"}
        )
    traversal_diagnostics = operation_inventory.diagnostics(
        inventory_reuse={
            "code_dna": True,
            "dependency_resolver": True,
            "graph_builder": graph is not None,
            "indexer": True,
            "manifest": bool(
                delta_shadow.get("manifest", {}).get(
                    "observed_built",
                    False,
                )
            ),
            "project_map": map_path is not None,
        }
    )
    result = {
        "repo_path": repo_path,
        "project_tag": semantic_project_tag,
        "index_scope": index_scope,
        "files_processed": files_indexed,
        "symbols_stored": units_saved,
        "code_index_reconciliation": reconciliation,
        "completion": completion.to_dict(),
        "delta_shadow": delta_shadow,
        "project_map": map_path,
        "phantom_limb": {
            "report": phantom_path,
            "count": len(phantom_findings),
            "findings": phantom_findings,
        },
        "traversal_diagnostics": traversal_diagnostics,
    }
    if include_operation_artifacts:
        result["_operation_artifacts"] = {
            "inventory": operation_inventory,
            "program_graph": graph,
            "code_dna": dna,
        }
    return result

def should_skip_index_file(file_name: str) -> bool:
    """Compatibility wrapper around canonical inventory translation policy."""
    return should_skip_index_filename(file_name)

def _build_dependency_rows(
    *,
    repo_path: str,
    rel_path: str,
    language: str,
    parsed_data: dict,
    repository_files: set[str],
) -> list[dict]:
    dependencies: list[dict] = []
    seen: set[tuple] = set()

    def add_dependency(
        *,
        dependency_type: str,
        source_symbol: str | None = None,
        target_file: str | None = None,
        target_symbol: str | None = None,
    ) -> None:
        if not target_file and not target_symbol:
            return

        key = (
            dependency_type,
            source_symbol,
            target_file,
            target_symbol,
        )
        if key in seen:
            return

        seen.add(key)
        dependencies.append({
            "dependency_type": dependency_type,
            "source_symbol": source_symbol,
            "target_file": target_file,
            "target_symbol": target_symbol,
        })

    for raw_import in parsed_data.get("imports", []):
        target = resolve_dependency_target(
            repo_root=repo_path,
            source_file=rel_path,
            language=language,
            raw_target=raw_import,
            repository_files=repository_files,
        )

        add_dependency(
            dependency_type="import",
            target_file=target.target_file,
            target_symbol=target.target_symbol,
        )

    symbol_calls: set[str] = set()

    for symbol in parsed_data.get("symbols", []):
        source_symbol = symbol.get("name")

        for call in symbol.get("calls", []):
            symbol_calls.add(call)
            add_dependency(
                dependency_type="call",
                source_symbol=source_symbol,
                target_symbol=call,
            )

    for call in parsed_data.get("calls", []):
        if call in symbol_calls:
            continue

        add_dependency(
            dependency_type="call",
            target_symbol=call,
        )

    return dependencies

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    index_repository(path)
