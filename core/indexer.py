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
from database.memory import (
    db_enabled as code_index_db_enabled,
    init_db,
    reconcile_code_index_scope,
    replace_code_index_for_file,
)
from core.dependency_target import (
    resolve_dependency_target,
)
from graph.project_map import summarize_file, build_project_map, write_project_map
from core.security import is_safe_path
from core.project_tag import build_project_tag
from core.repo_librarian import (
    inspect_repo_inventory,
    iter_repo_files,
    write_phantom_limb_report,
)
from core.code_dna import compute_dna, save_dna
from core.phantom_limb import scan as scan_phantom_limb
import json

def index_repository(repo_path: str, project_tag: Optional[str] = None):
    from core.repository_identity import build_code_index_scope
    file_summaries = []
    repo_path = os.path.abspath(repo_path)

    # Auto-derive a stable tag if the caller didn't supply one. Same repo →
    # same tag, so re-indexing replaces only this project's rows.

    display_project_tag = (
        project_tag or build_project_tag(repo_path)
    )

    inventory = inspect_repo_inventory(repo_path)
    if not inventory["ok"]:
        raise RuntimeError(
            "Indexing aborted: repo has 0 indexable files.\n"
            + json.dumps(inventory, indent=2, ensure_ascii=False)
        )
    index_scope = build_code_index_scope(repo_path)
    repo_entries = list(iter_repo_files(repo_path))

    repository_files = {
        rel_path.as_posix()
        for _file_path, rel_path in repo_entries
    }

    indexable_count = inventory["indexable_count"]
    
    print(
        f"🚀 Starting Project-Wide Indexing: {repo_path} "
        f"[tag={display_project_tag}, "
        f"index_scope={index_scope}, "
        f"files={indexable_count}]"
    )

    # Ensure DB is initialized when persistence is enabled.
    db_available = code_index_db_enabled()
    persistence_skip_reason = (
        None
        if db_available
        else "persistence_disabled"
    )
    if db_available:
        try:
            init_db()
        except Exception as e:
            db_available = False
            persistence_skip_reason = "db_initialization_failed"
            print(
                f"⚠️ DB initialization failed: {e}. "
                "Indexing will proceed, but results won't be saved."
            )

    files_indexed = 0
    units_saved = 0
    indexed_repository_files: set[str] = set()

    for file_path_obj, rel_path_obj in repo_entries:
        file_path = str(file_path_obj)
        rel_path = str(rel_path_obj).replace("\\", "/")

        if should_skip_index_file(file_path_obj.name):
            continue

        # Rule 1: Security boundary
        if not is_safe_path(file_path, allowed_roots=[repo_path]):
            continue

        # Rule 2: Supported extensions
        ext = file_path_obj.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            continue

        indexed_repository_files.add(rel_path)

        try:
            text = extract_file_text(file_path, repo_path=repo_path)
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

            if db_available:
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
                    inserted_count = replace_code_index_for_file(
                        file_path=rel_path,
                        index_scope=index_scope,
                        code_units=unit_rows,
                        dependencies=dependency_rows,
                    )
                    units_saved += inserted_count
                except Exception as e:
                    print(
                        f"⚠️ Atomic DB replacement failed for "
                        f"{rel_path}: {e}"
                    )
                    db_available = False
                    persistence_skip_reason = (
                        "file_replacement_failed"
                    )
            else:
                # No DB: still index for project map / control / phantom limb,
                # but skip persistence and embeddings.
                pass
            files_indexed += 1
            print(
                f"OK: Indexed {rel_path} "
                f"({len(units)} symbols, "
                f"{len(data.get('imports', []))} imports, "
                f"{len(data.get('calls', []))} calls)"
            )
        except Exception as e:
            print(f"ERR: Failed to index {rel_path}: {e}")

    reconciliation = {
        "performed": False,
        "dependencies_deleted": 0,
        "code_units_deleted": 0,
        "skipped_reason": None,
    }
    if db_available:
        try:
            cleanup = reconcile_code_index_scope(
                index_scope=index_scope,
                current_files=indexed_repository_files,
            )
            reconciliation.update({
                "performed": True,
                **cleanup,
            })
        except Exception as e:
            reconciliation["skipped_reason"] = (
                f"reconciliation_failed: {e}"
            )
            print(
                "⚠️ Code-index scope reconciliation failed: "
                f"{e}"
            )
    else:
        reconciliation["skipped_reason"] = (
            persistence_skip_reason
            or "persistence_unavailable_or_failed"
        )

    dna = compute_dna(repo_path)
    save_dna(repo_path, dna)
    print(f"🧬 Code DNA: {dna['indent']}, {dna['naming']}, line~{dna['max_line_pref']}c")
    print(f"\nSummary:")
    print(f"Files processed: {files_indexed}")
    print(f"Symbols stored: {units_saved}")
    if files_indexed == 0:
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

    # Build project map (graph is only used to render the map, so skip both together)
    if os.getenv("BENCHMARK_SKIP_PROJECT_MAP", "").lower() == "true":
        graph = None
        map_path = None
    else:
        try:
            graph = build_graph_from_repo(
                repo_path,
                repo_entries=repo_entries,
                repository_files=repository_files,
            )
        except Exception as e:
            print(f"⚠️ Graph build failed: {e}. Continuing without graph.")
            graph = None

        try:
            content = build_project_map(file_summaries, graph=graph, repo_path=repo_path)
        except Exception as e:
            print(f"⚠️ Project map graph rendering failed: {e}. Retrying without graph.")
            content = build_project_map(file_summaries, graph=None, repo_path=repo_path)

        map_path = write_project_map(repo_path, content)
        print(f"🗺️ Project map written to: {map_path}")
    return {
        "repo_path": repo_path,
        "project_tag": display_project_tag,
        "index_scope": index_scope,
        "files_processed": files_indexed,
        "symbols_stored": units_saved,
        "code_index_reconciliation": reconciliation,
        "project_map": map_path,
        "phantom_limb": {
            "report": phantom_path,
            "count": len(phantom_findings),
            "findings": phantom_findings,
        },
    }

def should_skip_index_file(file_name: str) -> bool:
    name = file_name.lower()
    return (
        name == ".env"
        or name.startswith(".env")
        or name in {
            "session_log.txt",
            "memory_file_for_agent.txt",
            "postgres_auth.txt",
        }
    )

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
