from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any, Optional
from graph.compressor import compress_to_modules
from graph.weights import rank_nodes_by_weight
from config import get_agent_dir, BASE_DIR
import re

CRITICAL_SYMBOL_TYPES = {
    "function",
    "class",
    "struct",
    "interface",
    "type",
    "enum",
    "trait",
    "union",
    "object",
    "record",
}

def summarize_file(rel_path: str, language: str, symbols: list, imports: list, calls: list) -> dict:
    names = [s.get("name", "unknown") for s in symbols[:12]]
    kinds = list(dict.fromkeys(s.get("kind", "unknown") for s in symbols))

    return {
        "file": rel_path,
        "language": language,
        "main_symbols": names,
        "symbol_kinds": kinds,
        "imports": imports[:12],
        "calls": calls[:20],
        "purpose_guess": guess_purpose(rel_path, names, imports, calls),
    }


def guess_purpose(rel_path: str, names: list, imports: list, calls: list) -> str:
    p = rel_path.lower()
    text = " ".join(names + imports + calls).lower()

    if any(k in p for k in ["router", "controller", "api", "route"]):
        return "Handles request routing and traffic management."
    if any(k in p for k in ["retriever", "search", "rag", "fetcher"]):
        return "Retrieves data or documents from external sources or indices."
    if any(k in p for k in ["indexer", "loader", "parser", "scanner"]):
        return "Parses and indexes repository content for search and analysis."
    if any(k in p for k in ["executor", "runner", "apply", "worker"]):
        return "Executes tasks, processes commands, or applies changes."
    if any(k in p for k in ["patch", "diff", "merge", "conflict"]):
        return "Manages code changes, patches, and versioning logic."
    if any(k in p for k in ["memory", "database", "store", "cache", "sql"]):
        return "Handles data persistence, storage, and retrieval logic."
    if any(k in p for k in ["prompter", "prompt", "template", "llm"]):
        return "Builds and manages prompts for AI model interactions."
    if any(k in p for k in ["validator", "check", "test", "lint", "guard"]):
        return "Validates code, runs tests, and ensures quality standards."
    if any(k in p for k in ["security", "auth", "encrypt", "perm"]):
        return "Manages access control, security policies, and authentication."
    if any(k in p for k in ["tree", "ast", "parse", "grammar"]):
        return "Parses and analyzes code structure using AST or grammars."
    if any(k in p for k in ["util", "helper", "common", "shared", "base"]):
        return "Provides utility functions and shared logic across the project."
    if "retriever" in text:
        return "Retrieves multi-level context (macro → meso → micro) for code reasoning."
    if "main" in text:
        return "Main entry point for the application."

    return "General project component; purpose inferred from symbols and imports."

def clean_name(x: str) -> str | None:
    x = (x or "").strip()

    if not x:
        return None
    if len(x) < 3:
        return None
    if len(x) > 80:
        return None
    if any(ch in x for ch in ["\n", "`", "(", ")", "{", "}", "[", "]"]):
        return None
    if not any(c.isalpha() for c in x):
        return None
    if re.search(r"\s{2,}", x):
        return None
    if x in {"str", "int", "list", "dict", "set", "len", "any", "print"}:
        return None

    return x

def clean_names(items, limit=8):
    result = []
    seen = set()

    for item in items:
        name = item.get("name") if isinstance(item, dict) else str(item)
        name = clean_name(name)

        if not name or name in seen:
            continue

        seen.add(name)
        result.append(name)

    return result[:limit]

def compute_hotspots(graph):
    scores = {}

    for edge in graph.edges:
        if edge.type == "resolved_call":
            scores[edge.target] = scores.get(edge.target, 0) + 1

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [node for node, _ in ranked[:10]]

def compute_symbol_hotspots(graph):
    ranked = rank_nodes_by_weight(
        graph,
        limit=10,
        node_types=CRITICAL_SYMBOL_TYPES,
    )
    return [(metric.node_id, metric.weight) for metric in ranked]

def _is_self_analysis(repo_path: Optional[str]) -> bool:
    if not repo_path:
        return False
    try:
        return Path(repo_path).resolve() == BASE_DIR.resolve()
    except Exception:
        return False


def _detect_languages(file_summaries: List[dict]) -> List[str]:
    counts: Dict[str, int] = defaultdict(int)
    for item in file_summaries:
        lang = item.get("language") or "unknown"
        if lang not in {"unknown", "text", "json", "document"}:
            counts[lang] += 1
    return [lang for lang, _ in sorted(counts.items(), key=lambda x: -x[1])]


def _infer_repo_purpose(repo_name: str, file_summaries: List[dict]) -> str:
    langs = _detect_languages(file_summaries)
    n_files = len(file_summaries)

    lang_part = ", ".join(langs[:3]) if langs else "mixed"
    return (
        f"Auto-generated map for `{repo_name}` ({n_files} files, languages: {lang_part}). "
        "Purpose inferred from folder/file structure below."
    )


def _ai_project_specific_sections() -> List[str]:
    """Sections that only make sense when analyzing AI_project itself."""
    out: List[str] = []
    out.append("## Purpose")
    out.append(
        "AI coding agent system for tutoring, reviewing, planning, retrieving code context, "
        "applying patches, validating changes, and learning from memory."
    )
    out.append("")
    out.append("## Key Hotspots")
    out.append("- main.py: central orchestration")
    out.append("- core/retriever.py: context retrieval bottleneck")
    out.append("- core/patch_engine.py: patch application logic")
    out.append("- core/executor.py: runtime execution + validation")
    out.append("")
    out.append("## Architecture Overview")
    out.append("- `main.py`: orchestrates interface, task routing, prompting, model calls, planner loop, patch loop, and session lifecycle.")
    out.append("- `agents/`: model clients for Gemini drafting/refinement and DeepSeek/Ollama reviewing.")
    out.append("- `core/`: reasoning, retrieval, parsing, patching, validation, security, and prompt construction.")
    out.append("- `database/`: persistent memory, sessions, code units, dependencies, patch attempts, and tooling profiles.")
    out.append("- `.agent/`: generated agent metadata such as this project map.")
    out.append("")
    out.append("## Main Runtime Flow")
    out.append("```text")
    out.append("User input")
    out.append("→ CONTROL ENGINE")
    out.append("→ Graph layer (ProgramGraph, resolved_call)")
    out.append("→ Reasoning layer (state + risk + symbol analysis)")
    out.append("→ Patch planning (intent → candidate → scoring)")
    out.append("→ Patch execution (AST / fuzzy / literal)")
    out.append("→ Validation")
    out.append("→ memory.py stores results")
    out.append("```")
    out.append("")
    out.append("## Error Localization Guide")
    out.append("- Bad mode/task classification → `core/router.py`")
    out.append("- Missing or weak context → `core/retriever.py`, `core/indexer.py`, `database/memory.py`")
    out.append("- Wrong project overview → `graph/project_map.py`")
    out.append("- Bad prompt behavior → `core/prompter.py`")
    out.append("- Patch fails to apply → `core/patch_engine.py`, `core/executor.py`")
    out.append("- Validation failure → `core/validator.py`")
    out.append("- Unsafe file access → `core/security.py`")
    out.append("- Memory not reused → `database/memory.py`, `main.py`")
    out.append("")
    return out


def build_project_map(
    file_summaries: List[dict],
    graph=None,
    repo_path: Optional[str] = None,
    inventory: Optional[dict] = None,
) -> str:
    if not file_summaries:
        repo_name = Path(repo_path).resolve().name if repo_path else "project"
        error_messages = []
        if inventory:
            if inventory.get("ok") is False:
                error_messages.append("- Indexing failed: " + (inventory.get("error") or "unknown error"))
            if inventory.get("indexable_count") == 0:
                error_messages.append("- repo has 0 indexable files (check extensions, folder_blacklist)")
        error_section = "\n".join(error_messages) if error_messages else ""

        return "\n".join([
            f"# Project Map: {repo_name}",
            "",
            error_section,
            "## WARNING",
            "No files were indexed for this repository.",
            "This project map is incomplete.",
            "",
            "Possible causes:",
            "- upload_folder created an empty temp repo",
            "- files have unsupported extensions",
            "- security filter blocked all files",
            "- wrong repo_path was passed",
            "",
        ])
    is_self = _is_self_analysis(repo_path)
    repo_name = Path(repo_path).resolve().name if repo_path else "project"

    by_folder = defaultdict(list)
    for item in file_summaries:
        file = item.get("file", "")
        if should_skip_project_map_file(file):
            continue
        folder = str(Path(file).parent)
        by_folder[folder].append(item)

    lines: List[str] = []
    title = "AI Coding Mentor — Project Map" if is_self else f"Project Map: {repo_name}"
    lines.append(f"# {title}")
    lines.append("")

    if is_self:
        lines.extend(_ai_project_specific_sections())
    else:
        lines.append("## Purpose")
        lines.append(_infer_repo_purpose(repo_name, file_summaries))
        lines.append("")

    # ----- Module Responsibilities (always auto-generated) -----
    lines.append("## Module Responsibilities")
    for folder, items in sorted(by_folder.items()):
        folder_title = "root" if folder == "." else folder.replace("\\", "/")
        lines.append(f"### {folder_title}")
        lines.append(folder_responsibility(folder_title, is_self=is_self))

        for item in sorted(items, key=lambda x: x["file"]):
            symbols = ", ".join(clean_names(item.get("main_symbols", []), limit=8)) or "none"
            calls = ", ".join(clean_names(item.get("calls", []), limit=6)) or "none"
            lines.append(f"- `{item['file']}`")
            lines.append(f"  - Purpose: {item['purpose_guess']}")
            lines.append(f"  - Key symbols: {symbols}")
            lines.append(f"  - Key calls: {calls}")
        lines.append("")

    # ----- Graph-derived sections (always auto-generated) -----
    if graph:
        compressed = compress_to_modules(graph)

        lines.append("## Module Graph (Compressed)")
        for name, data in compressed["modules"].items():
            lines.append(f"- {name} ({data['node_count']} nodes)")
        lines.append("")

        lines.append("## Module Connections")
        for e in compressed["edges"][:20]:
            lines.append(f"- {e['source']} → {e['target']} ({e['type']}, w={e['weight']})")
        lines.append("")

        lines.append("## Dynamic Hotspots (Graph-based)")
        for node in compute_hotspots(graph):
            lines.append(f"- {node}")
        lines.append("")

        lines.append("## Critical Symbols (High Impact)")
        for node, score in compute_symbol_hotspots(graph):
            lines.append(f"- {node} (score={score})")
        lines.append("")

    # ----- Generic LLM guidance (universal) -----
    lines.append("## Retrieval Strategy")
    lines.append("- Macro questions should start from this PROJECT_MAP.")
    lines.append("- Meso questions should use symbols and dependencies.")
    lines.append("- Micro bug questions should inspect exact code snippets.")
    lines.append("- Hybrid debugging should combine PROJECT_MAP → symbols → dependency/call-chain → code.")
    lines.append("")

    lines.append("## Grounding Rules for LLM")
    lines.append("- Treat this map as navigation, not truth.")
    lines.append("- Verify exact code through symbol retrieval before patching.")
    lines.append("- Do not patch based only on PROJECT_MAP.")
    lines.append("- If project map conflicts with graph/retriever/code, trust code and graph first.")
    lines.append("")

    lines.append("## Map Confidence")
    lines.append("- Symbol extraction: partial (tree-sitter dependent)")
    lines.append("- Call graph: best-effort (name-based resolution)")
    lines.append("- May contain outdated assumptions")
    lines.append("")

    lines.append("- Memory is a hint, not a source of truth")
    lines.append("- Always verify memory using graph or state reasoning")
    lines.append("")

    return "\n".join(lines)

def should_skip_project_map_file(file_path: str) -> bool:
    p = file_path.replace("\\", "/").lower()
    name = Path(p).name

    blocked_names = {
        ".env",
        "session_log.txt",
        "memory_file_for_agent.txt",
        "postgres_auth.txt",
    }

    blocked_dirs = {
        ".git",
        "__pycache__",
        "node_modules",
        "venv",
        ".venv",
        ".vscode",
        ".idea",
        ".agent",
        ".agents",
    }

    if name in blocked_names or name.startswith(".env"):
        return True

    parts = set(Path(p).parts)
    if any(d in parts for d in blocked_dirs):
        return True

    return False


def folder_responsibility(folder: str, is_self: bool = False) -> str:
    f = folder.lower()

    # Generic mappings that apply to most projects
    if f == "root":
        return "Top-level orchestration, configuration, and application entrypoints."
    if any(k in f for k in ("test", "tests", "spec", "specs", "__tests__")):
        return "Test/sample code used to validate behavior."
    if any(k in f for k in ("doc", "docs", "documentation")):
        return "Project documentation and reference material."
    if any(k in f for k in ("example", "examples", "sample", "samples", "demo")):
        return "Example/demo code showing usage patterns."
    if any(k in f for k in ("script", "scripts", "tools", "tooling")):
        return "Build, deploy, and developer tooling scripts."
    if any(k in f for k in ("util", "utils", "helper", "helpers", "common", "shared", "lib")):
        return "Utility/helper modules used across the project."
    if any(k in f for k in ("config", "settings", "conf")):
        return "Configuration files and environment setup."
    if any(k in f for k in ("api", "routes", "controller", "controllers", "handler", "handlers")):
        return "API routing and request handling."
    if any(k in f for k in ("model", "models", "schema", "schemas", "entity", "entities")):
        return "Data models and schema definitions."
    if any(k in f for k in ("service", "services")):
        return "Business logic / service layer."
    if any(k in f for k in ("ui", "view", "views", "component", "components", "page", "pages")):
        return "User interface / presentation layer."
    if "src" == f or f.endswith("/src") or f.startswith("src/"):
        return "Primary source code."

    # AI_project-specific mappings — only used when self-analyzing
    if is_self:
        if "agents" in f:
            return "Model client layer: sends prompts to external/local LLMs and returns raw model outputs."
        if "core" in f:
            return "Core reasoning layer: routing, retrieval, parsing, prompting, patching, validation, and security."
        if "database" in f:
            return "Persistence layer: sessions, memory notes, code units, dependencies, tooling profiles, and patch history."

    return "Project submodule."


def write_project_map(repo_path: str, content: str) -> str:
    out_dir = get_agent_dir(repo_path)
    out_path = out_dir / "PROJECT_MAP.md"
    out_path.write_text(content, encoding="utf-8")
    return str(out_path)


def load_project_map(repo_path: str) -> str:
    path = get_agent_dir(repo_path) / "PROJECT_MAP.md"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")
