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
from database.memory import save_code_unit, clear_code_units_for_file, init_db, clear_dependencies_for_file, save_dependency
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
    file_summaries = []
    repo_path = os.path.abspath(repo_path)

    # Auto-derive a stable tag if the caller didn't supply one. Same repo →
    # same tag, so re-indexing replaces only this project's rows.
    if not project_tag:
        project_tag = build_project_tag(repo_path)
    
    inventory = inspect_repo_inventory(repo_path)
    if not inventory["ok"]:
        raise RuntimeError(
            "Indexing aborted: repo has 0 indexable files.\n"
            + json.dumps(inventory, indent=2, ensure_ascii=False)
        )

    indexable_count = inventory["indexable_count"]
    
    print(f"🚀 Starting Project-Wide Indexing: {repo_path}  [tag={project_tag}, files={indexable_count}]")

    # Ensure DB is initialized
    db_available = True
    try:
        init_db()
    except Exception as e:
        db_available = False
        print(f"⚠️ DB initialization failed: {e}. Indexing will proceed, but results won't be saved.")

    files_indexed = 0
    units_saved = 0

    for file_path_obj, rel_path_obj in iter_repo_files(repo_path):
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

            if not units and not data.get("imports") and not data.get("calls"):
                continue
            if db_available:
                try:
                    clear_code_units_for_file(rel_path, project_tag=project_tag)
                    clear_dependencies_for_file(rel_path, project_tag=project_tag)
                except Exception as e:
                    print(f"⚠️ DB cleanup failed for {rel_path}: {e}")
                    db_available = False

            for imp in data.get("imports", []):
                if db_available:
                    try:
                        save_dependency(
                            source_file=rel_path,
                            target_file=imp,
                            dependency_type="import",
                            project_tag=project_tag,
                        )
                    except Exception as e:
                        print(f"⚠️ DB save failed for import in {rel_path}: {e}")
                        db_available = False
                

            all_symbol_calls = set()
            for symbol in data.get("symbols", []):
                current_func = symbol.get("name")

                for call in symbol.get("calls", []):
                    all_symbol_calls.add(call)
                    if db_available:
                        try:
                            save_dependency(
                                source_file=rel_path,
                                source_symbol=current_func,
                                target_symbol=call,
                                dependency_type="call",
                                project_tag=project_tag,
                            )
                        except Exception as e:
                            print(f"⚠️ DB save failed for call in {rel_path}: {e}")
                            db_available = False

            file_level_calls = [
                c for c in data.get("calls", [])
                if c not in all_symbol_calls
            ]

            for call in file_level_calls:
                if db_available:
                    try:
                        save_dependency(
                            source_file=rel_path,
                            target_symbol=call,
                            dependency_type="call",
                            project_tag=project_tag,
                        )
                    except Exception as e:
                        print(f"⚠️ DB save failed for file-level call in {rel_path}: {e}")
                        db_available = False

            use_index_embeddings = os.getenv(
                "INDEX_USE_EMBEDDINGS",
                "true",
            ).lower() not in {"0", "false", "no"}

            if db_available:
                for unit in units:
                    if use_index_embeddings:
                        embedding = get_embedding(unit["content"])
                        embedding_list = embedding.tolist()
                    else:
                        embedding_list = []

                    try:
                        save_code_unit(
                            file_path=rel_path,
                            kind=unit["kind"],
                            name=unit["name"],
                            content=unit["content"],
                            embedding=embedding_list,
                            project_tag=project_tag,
                        )
                        units_saved += 1
                    except Exception as e:
                        print(f"⚠️ DB save skipped for {rel_path}::{unit.get('name')}: {e}")
                        db_available = False
                        break
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

    # Build project map
    graph = build_graph_from_repo(repo_path)
    content = build_project_map(file_summaries, graph=graph, repo_path=repo_path)
    map_path = write_project_map(repo_path, content)
    print(f"🗺️ Project map written to: {map_path}")
    return {
        "repo_path": repo_path,
        "project_tag": project_tag,
        "files_processed": files_indexed,
        "symbols_stored": units_saved,
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

if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "."
    index_repository(path)
