from __future__ import annotations

import sys, json
import os

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, Exception):
        pass

import re
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from patching.patch_planner import build_patch_intent
from patching.patch_synthesizer import build_patch_candidate
# Add project root to sys.path to allow importing config.py
root_dir = str(Path(__file__).parent.parent)
if root_dir not in sys.path:
    sys.path.append(root_dir)
from reasoning.reasoning_engine import build_reasoning_context, analyze_symbol_risk
from reasoning.decision_engine import decide_patch_action
from config import LANGUAGE_MAP, SUPPORTED_EXTENSIONS, get_agent_dir
from core.project_tag import build_project_tag
from core.repo_librarian import should_include_infra_file


def _tag_for(repo_path: Optional[str], project_tag: Optional[str] = None) -> Optional[str]:
    """Resolve a project_tag, deriving from repo_path when not supplied."""
    if project_tag:
        return project_tag
    if repo_path:
        try:
            return build_project_tag(repo_path)
        except Exception:
            return None
    return None
from core.router import get_model, detect_input_mode, detect_language
from core.security import is_safe_path
from core.treesitter_parse import parse_code_with_treesitter
from graph.project_map import load_project_map
from database.memory import search_code_units, search_dependencies as search_dependencies_db
from graph.builder import build_graph_from_repo
from graph.query import explain_symbol, trace_path, impact_analysis, find_callers
from reasoning.state_reasoner import (
    build_state_trace,
    format_state_trace,
    build_symbol_state_map,
    detect_overwrite,
    detect_useless_branch,
    detect_return_conflict
)
from core.semantic_graph_pipeline import build_obsidian_semantic_context
from core.graph_walker import walk_from_nodes, get_ai_top_nodes

try:
    from pypdf import PdfReader # pyright: ignore[reportMissingImports]
except ImportError:
    PdfReader = None

try:
    from docx import Document
except ImportError:
    Document = None

def is_relevant(step, query):
    q_words = query.lower().split()
    text = (step.get("text","") + step.get("context","")).lower()

    return any(word in text for word in q_words)



def detect_state_issues(trace):
    issues = []
    issues += detect_overwrite(trace)
    issues += detect_useless_branch(trace)
    issues += detect_return_conflict(trace)
    MAX_STATES = 6

    for step in trace:
        if step["type"] == "assignment":
            states = step["states"][:MAX_STATES]
            if len(states) >= 2:
                var_maps = [tuple(sorted(s["vars"].items())) for s in states]
                if len(set(var_maps)) == 1:
                    issues.append("Assignment has no effect across branches")

    return issues

def dedupe_states(states):
    seen = set()
    result = []

    for s in states:
        key = tuple(sorted(s["vars"].items()))
        if key not in seen:
            seen.add(key)
            result.append(s)

    return result

def trace_execution_flow(query: str, repo_path: str = None, top_k: int = 3) -> str:
    hits = search_safe_code_units(query, repo_path=repo_path, limit=top_k, project_tag=_tag_for(repo_path))
    
    if not hits:
        if detect_input_mode(query) == "code":
            lang = detect_language(query)
            # Find a matching extension for the detected language
            ext = ".py"
            for e, l in LANGUAGE_MAP.items():
                if l == lang:
                    ext = e
                    break
            hits = [{
                "content": query,
                "file_path": f"query_snippet{ext}",
                "name": "<query_context>",
                "similarity": 1.0
            }]
        else:
            return ""
    lines = ["=== EXECUTION FLOW TRACE ==="]
    for h in hits:
        content = h.get("content", "")
        file_path = h.get("file_path")
        name = h.get("name")

        ext = Path(file_path).suffix.lower()
        language = LANGUAGE_MAP.get(ext, "unknown")

        parsed = parse_code_with_treesitter(content, language)
        symbols = parsed.get("symbols", []) if isinstance(parsed, dict) else []
        symbol_map = build_symbol_state_map(symbols)

        state_blocks = []
        for s in symbols[:2]:
            if s.get("name") in symbol_map:
                state_blocks.append(symbol_map[s["name"]])

        lines.append(f"\nSeed: {file_path}::{name} (execution focus)")
        lines.append(f"\nFunction: {name}")
        
        for st in state_blocks:
            formatted_trace = format_state_trace(st)
            lines.append(f"\nSymbol: {st['symbol']}")
            lines.append(formatted_trace)

            trace = st["state_trace"]
            issues = detect_state_issues(trace)

            if issues:
                graph = _get_cached_repo_graph(repo_path) if repo_path else None
                symbol_name = st["symbol"]
                if graph:
                    callers = find_callers(graph, symbol_name)
                    impact = impact_analysis(graph, symbol_name)
                    
                    lines.append(f"Impact: {impact}")
                    lines.append(f"Impacted callers: {callers}")

                    risk = analyze_symbol_risk(graph, symbol_name)
                    decision = decide_patch_action(risk, issues)

                    lines.append("=== DECISION ===")
                    lines.append(json.dumps(decision, indent=2))
                else:
                    callers =[]

                lines.append("=== STATE ANALYSIS ===")
                symbol_obj = next(
                    (x for x in symbols if x.get("name") == symbol_name),
                    None
                )

                for issue in issues:
                    if isinstance(issue, dict):
                        lines.append(f"- {issue.get('reason', issue)}")
                        for p in issue.get("paths", []):
                            lines.append(f"  path: {p}")
                    else:
                        lines.append(f"- {issue}")

                    if not symbol_obj:
                        continue

                    patch_intent = build_patch_intent(issue, symbol_obj, file_path)
                    if patch_intent:
                        lines.append("=== PATCH INTENT ===")
                        lines.append(json.dumps(
                             patch_intent,
                             indent=2,
                             ensure_ascii=False
                         ))

                        patch_candidate = build_patch_candidate(patch_intent)

                        lines.append("=== PATCH CANDIDATE (PRE) ===")
                        lines.append(json.dumps(
                            patch_candidate,
                            indent=2,
                            ensure_ascii=False
                        ))
        relevant_symbols = [
            s for s in symbols
            if any(word in (s.get("name","").lower() + s.get("content","").lower())
            for word in query.lower().split())
        ]

        for s in (relevant_symbols or symbols)[:2]:
            flow = s.get("execution_flow", [])
            filtered = [s for s in flow if is_relevant(s, query)]
            for step in (filtered or flow)[:6]:
                lines.append(f"- {step['type']}: {step['text']}")
                if step.get("context"):
                    lines.append(f"    ↳ {step['context'][:120]}")

    return "\n".join(lines)

# --- Constants & State ---

_cache: dict[str, Any] = {}
_graph_cache: dict[str, Any] = {}

# Constants moved to config.py
TEXT_EXTENSIONS = SUPPORTED_EXTENSIONS
CODE_EXTENSIONS = {ext for ext, lang in LANGUAGE_MAP.items() if lang not in {"document", "text", "json"}}


def get_cached_graph(repo_path):
    if repo_path not in _graph_cache:
        print("🔧 Building graph once...")
        _graph_cache[repo_path] = build_graph_from_repo(repo_path)
    return _graph_cache[repo_path]

# --- Embeddings ---

def get_embedding(text: str):
    if text in _cache:
        return _cache[text]
    model = get_model()
    emb = model.encode([text])[0]
    _cache[text] = emb
    return emb


# --- File Readers ---

def read_pdf(file_path: str) -> str:
    if PdfReader is None:
        return "AGENT_ERROR: pypdf is not installed."
    reader = PdfReader(file_path)
    all_text: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            all_text.append(text)
    return "\n\n".join(all_text)


def read_docx(file_path: str) -> str:
    if Document is None:
        return ""
    doc = Document(file_path)
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def read_text_file(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def extract_file_text(file_path: str, repo_path: str = None, query: str | None = None) -> str:
    # Resolve a stable relative path for the infra-file gate before we
    # absolutize, so basename matching ("Dockerfile") and folder matching
    # (".devcontainer/") both work regardless of how the caller passed the path.
    if repo_path and os.path.isabs(file_path):
        try:
            rel_for_gate = os.path.relpath(file_path, repo_path)
        except ValueError:
            rel_for_gate = os.path.basename(file_path)
    else:
        rel_for_gate = file_path

    if not should_include_infra_file(query, rel_for_gate):
        return ""

    if repo_path and not os.path.isabs(file_path):
        file_path = os.path.join(repo_path, file_path)

    file_path = os.path.abspath(file_path)
    allowed_roots = [repo_path] if repo_path else None
    if not is_safe_path(file_path, allowed_roots=allowed_roots):
        return ""

    ext = Path(file_path).suffix.lower()

    if ext == ".pdf":
        return read_pdf(file_path)
    if ext == ".docx":
        return read_docx(file_path)
    if ext in TEXT_EXTENSIONS:
        return read_text_file(file_path)

    return ""

def format_dependency_graph(results, query):
    lines = ["=== DEPENDENCY GRAPH ==="]

    # simple ranking
    ranked = sorted(
        results,
        key=lambda r: (
            (r.get("target_symbol") or "").lower().count(query.lower()),
            (r.get("target_file") or "").lower().count(query.lower()),
        ),
        reverse=True
    )

    for r in ranked:
        src = r["source_file"]
        tgt = r.get("target_file") or r.get("target_symbol")
        
        # Security check
        if not is_safe_path(src) or (r.get("target_file") and not is_safe_path(r["target_file"])):
            continue
            
        lines.append(f"{src} → {tgt}")
        if len(lines) > 6: # limit to 5 results + header
            break

    return "\n".join(lines)

# --- Chunking & Parsing ---

def split_text(text: str, chunk_size: int = 220) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [
        " ".join(words[i:i + chunk_size])
        for i in range(0, len(words), chunk_size)
    ]


def build_code_units(file_path: str, text: str) -> list[dict]:
    ext = Path(file_path).suffix.lower()
    language = LANGUAGE_MAP.get(ext)

    if not language:
        return []

    try:
        data = parse_code_with_treesitter(text, language)
        # Handle both old list format (for safety) and new dict format
        if isinstance(data, list):
            nodes = data
        else:
            nodes = data.get("symbols", [])
    except Exception:
        return []

    units: list[dict] = []

    for node in nodes:
        content = str(node.get("content", "") or "").strip()
        if not content:
            continue

        units.append({
            "kind": node.get("kind", "unknown"),
            "name": node.get("name", "unknown"),
            "content": content,
            "label": f"{node.get('kind', 'unit')}:{node.get('name', 'unknown')}",
        })

    return units
def extract_relevant_project_sections(query, project_map):
    lines = project_map.split("\n")
    lines = [l for l in lines if l.strip()]
    if not lines:
        return ""

    model = get_model()
    line_embeddings = model.encode(lines)
    query_embedding = model.encode([query])[0]
    
    norms = np.linalg.norm(line_embeddings, axis=1) * np.linalg.norm(query_embedding)
    scores = np.dot(line_embeddings, query_embedding) / np.where(norms == 0, 1e-9, norms)

    top_indices = np.argsort(scores)[-20:][::-1]

    return "\n".join(lines[i] for i in top_indices)

# --- Semantic Search ---

def semantic_rank(query: str, units: list[dict], top_k: int = 3) -> list[dict]:
    if not units:
        return []

    model = get_model()

    texts = [
        f"{u['label']}\n{u['content']}"
        for u in units
    ]

    unit_embeddings = model.encode(texts)
    query_embedding = model.encode([query])[0]
    
    scores = np.dot(unit_embeddings, query_embedding) / (
        np.linalg.norm(unit_embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    top_indices = np.argsort(scores)[-top_k:][::-1]

    ranked: list[dict] = []
    for idx in top_indices:
        unit = dict(units[int(idx)])
        unit["score"] = float(scores[int(idx)])
        ranked.append(unit)

    return ranked


def get_relevant_code_units(query: str, file_path: str, text: str, top_k: int = 3) -> list[str]:
    units = build_code_units(file_path, text)
    if not units:
        return []

    ranked = semantic_rank(query, units, top_k=top_k)
    output: list[str] = []

    for item in ranked:
        header = f"[{item['kind']}:{item['name']}]"
        output.append(f"{header}\n{item['content']}")

    return output


def get_relevant_text_chunks(query: str, document: str, top_k: int = 3) -> list[str]:
    chunks = split_text(document)
    if not chunks:
        return []

    model = get_model()
    chunk_embeddings = model.encode(chunks)
    query_embedding = model.encode([query])[0]

    scores = np.dot(chunk_embeddings, query_embedding) / (
        np.linalg.norm(chunk_embeddings, axis=1) * np.linalg.norm(query_embedding)
    )

    top_indices = np.argsort(scores)[-top_k:][::-1]
    return [chunks[int(i)] for i in top_indices]


def search_safe_code_units(
    query: str,
    repo_path: str = None,
    limit: int = 5,
    project_tag: Optional[str] = None,
) -> List[Dict]:
    """Wraps search_code_units with safety filtering AND project_tag scoping."""
    tag = _tag_for(repo_path, project_tag)
    hits = search_code_units(query, limit=limit * 3, project_tag=tag)  # Over-fetch for filtering
    safe = []
    allowed_roots = [repo_path] if repo_path else None
    for h in hits:
        p = h["file_path"]
        if repo_path and not os.path.isabs(p):
            p = os.path.join(repo_path, p)
        if is_safe_path(p, allowed_roots=allowed_roots):
            safe.append(h)
    return safe[:limit]


def search_global_symbols(
    query: str,
    repo_path: str = None,
    top_k: int = 5,
    project_tag: Optional[str] = None,
) -> str:
    results = search_safe_code_units(query, repo_path=repo_path, limit=top_k, project_tag=project_tag)
    if not results:
        return ""

    output = ["Project-Wide Symbol Matches:"]
    for res in results:
        header = f"[{res['kind']}:{res['name']}] in {res['file_path']} (sim={res['similarity']:.2f})"
        output.append(f"{header}\n{res['content']}")

    return "\n\n".join(output)


def search_dependencies(
    query: str,
    top_k: int = 5,
    repo_path: Optional[str] = None,
    project_tag: Optional[str] = None,
) -> str:
    tag = _tag_for(repo_path, project_tag)
    results = search_dependencies_db(query, limit=top_k, project_tag=tag)
    if not results:
        return ""
    return format_dependency_graph(results, query)

def _extract_symbol_candidates(query: str) -> list[str]:
    candidates = re.findall(r"\b[A-Za-z_][A-Za-z0-9_]*\b", query)
    stop_words = {
        "the", "a", "an", "and", "or", "to", "from", "in", "on", "for", "with",
        "is", "are", "was", "were", "why", "how", "what", "where", "when",
        "this", "that", "it", "of",
    }

    result = []
    seen = set()
    for candidate in candidates:
        c = candidate.strip()
        c_lower = c.lower()
        if len(c) < 2 or c_lower in stop_words:
            continue
        if c_lower in seen:
            continue
        seen.add(c_lower)
        result.append(c)
    return result[:8]

def _get_cached_repo_graph(repo_path: str):
    repo_abs = os.path.abspath(repo_path)
    if repo_abs in _graph_cache:
        return _graph_cache[repo_abs]

    graph = build_graph_from_repo(repo_abs)
    _graph_cache[repo_abs] = graph
    return graph

def expand_candidates(words):
    expanded = set(words)
    for w in words:
        expanded.add(w.capitalize())
        expanded.add(w.lower())
    return list(expanded)

def retrieve_file_context(query: str, file_path: str, repo_path: str = None) -> str:
    text = extract_file_text(file_path, repo_path=repo_path, query=query)
    if not text:
        return ""

    extra = []

    if repo_path and os.path.isdir(repo_path):
        try:
            graph = _get_cached_repo_graph(repo_path) if repo_path else None
            extra.append("=== PROGRAM GRAPH CONTEXT ===")
            extra.append(f"Graph nodes: {len(graph.nodes)}")
            extra.append(f"Graph edges: {len(graph.edges)}")

            
            candidates = _extract_symbol_candidates(query)
            candidates = expand_candidates(candidates)

            if "move" in query.lower():
                candidates.append("Move")

            # reasoning engine (chỉ gọi 1 lần)
            reasoning_context = build_reasoning_context(graph, candidates)
            if reasoning_context.strip() != "=== REASONING ENGINE CONTEXT ===":
                extra.append(reasoning_context)

            # sau đó loop từng candidate
            for word in candidates:
                info = explain_symbol(graph, word)
                impact = impact_analysis(graph, word)

                if impact:
                    extra.append(f"- impact: {impact}")
                if info["called_by"] or info["calls"]:
                    extra.append(f"Symbol: {word}")
                    extra.append(f"- called_by: {info['called_by']}")
                    extra.append(f"- calls: {info['calls']}")
        except Exception:
            # Keep retrieval output clean when graph enrichment fails.
            pass
    code_units = get_relevant_code_units(query, file_path, text, top_k=3)
    if code_units:
        return "\n\n".join(extra + code_units)
    
    chunks = get_relevant_text_chunks(query, text, top_k=3)
    
    return "\n\n...\n\n".join(extra + chunks)

def pick_seed_symbols(query, repo_path: str = None):
    hits = search_safe_code_units(query, repo_path=repo_path, limit=10)

    keywords = query.lower().split()

    ranked = sorted(
        hits,
        key=lambda x: sum(k in x["name"].lower() for k in keywords),
        reverse=True
    )

    return ranked[:3]

def trace_call_chain(query: str, repo_path: str = None, max_depth: int = 3, fanout: int = 3) -> str:
    tag = _tag_for(repo_path)
    seeds = pick_seed_symbols(query, repo_path=repo_path)
    if not seeds:
        return ""

    lines = ["=== CALL CHAIN TRACE ==="]

    visited = set()

    def walk(symbol_name: str, depth: int):
        if depth > max_depth or symbol_name in visited:
            return
        visited.add(symbol_name)

        deps = search_dependencies_db(symbol_name, limit=fanout, project_tag=tag)
        for dep in deps:
            if dep.get("dependency_type") != "call":
                continue

            src = dep.get("source_symbol") or dep.get("source_file")
            tgt = dep.get("target_symbol") or dep.get("target_file")
            if not tgt:
                continue

            code_hits = search_safe_code_units(tgt, repo_path=repo_path, limit=1, project_tag=tag)

            snippet = code_hits[0]["content"][:200] if code_hits else ""

            lines.append("  " * depth + f"{src} → {tgt}")
            if snippet:
                lines.append("  " * (depth+1) + f"> {snippet}")

            walk(tgt, depth + 1)

    for seed in seeds:
        name = seed.get("name")
        file_path = seed.get("file_path")
        if not name:
            continue
        lines.append(f"Seed: {file_path}::{name}")
        walk(name, 1)

    return "\n".join(lines)

# --- RAG Flow ---

def classify_retrieval_level(query: str) -> dict:
    text = query.lower()
    macro_signals = [
        "project này làm gì",
        "project này làm về cái gì",
        "what is this project",
        "what does this project do",
        "architecture",
        "kiến trúc",
        "overview",
        "tổng quan",
        "module nào",
        "which module",
        "which file",
        "file nào",
        "where is",
        "ở đâu xử lý",
        "flow",
        "pipeline",
        "system",
        "codebase",
    ]

    micro_signals = [
        "bug",
        "fix",
        "traceback",
        "syntaxerror",
        "typeerror",
        "nameerror",
        "==",
        "!=",
        ">=",
        "<=",
        "null",
        "none",
        "line",
        "this code",
        "đoạn code",
        "hàm này",
        "function này",
    ]

    meso_signals = [
        "function",
        "class",
        "symbol",
        "import",
        "call",
        "dependency",
        "hàm",
        "biến",
        "class",
        "module",
    ]

    macro_score = sum(1 for s in macro_signals if s in text)
    meso_score = sum(1 for s in meso_signals if s in text)
    micro_score = sum(1 for s in micro_signals if s in text)

    # Logic bug kiểu ==/!= thường cần hybrid:
    # cần map để khoanh vùng, symbol để định vị, RAG để soi dòng thật.
    if macro_score > 0 and micro_score > 0:
        level = "hybrid"
    elif macro_score >= 2:
        level = "macro"
    elif micro_score >= 1:
        level = "micro"
    elif meso_score >= 1:
        level = "meso"
    elif macro_score == 1:
        level = "macro"
    else:
        level = "micro"

    confidence = max(macro_score, meso_score, micro_score) / max(
        1, macro_score + meso_score + micro_score
    )

    return {
        "level": level,
        "confidence": round(confidence, 2),
        "scores": {
            "macro": macro_score,
            "meso": meso_score,
            "micro": micro_score,
        },
    }


def get_project_map_context(repo_path: str, max_chars: int = 6000) -> str:
    content = load_project_map(repo_path)
    if not content:
        return ""
    return content[:max_chars]


def retrieve_context(
    query: str,
    file_path: str | None = None,
    repo_path: str = ".",
    project_tag: Optional[str] = None,
) -> str:
    route = classify_retrieval_level(query)
    level = route["level"]
    tag = _tag_for(repo_path, project_tag)

    blocks = []
    blocks.append(f"Retrieval Level: {level} | confidence={route['confidence']} | scores={route['scores']}")
    blocks.insert(0, f"""
You are analyzing a codebase using multi-level context:

1. PROJECT MAP = high-level architecture
2. SYMBOLS = likely relevant functions/classes
3. CODE = exact implementation

Use them in this order:
- first narrow down module using PROJECT MAP
- then locate functions using SYMBOLS
- finally inspect CODE for exact bug
""")
    blocks.insert(1, f"""
Query Analysis:
- Likely intent: {level}
- Strategy:
  - macro → identify module
  - meso → locate symbols
  - micro → inspect code
""")
    blocks.append("""
Dependency Interpretation:
- Follow arrows as execution or data flow
- Bugs may originate downstream
- Trace chain before inspecting code
""")
    # === GRAPH REASONING ===
    if repo_path and os.path.isdir(repo_path):
        try:
            graph = get_cached_graph(repo_path)

            blocks.append("=== PROGRAM GRAPH ===")
            blocks.append(f"Nodes: {len(graph.nodes)}, Edges: {len(graph.edges)}")

            repo_abs = Path(repo_path).resolve()
            vault_path = str(get_agent_dir(str(repo_abs)) / "Obsidian Graph" / "latest")

            semantic_graph_context = build_obsidian_semantic_context(
                repo_path=str(repo_abs),
                vault_path=vault_path,
            )

            if semantic_graph_context:
                blocks.insert(2, semantic_graph_context)
            AI_TOP_NODES = get_ai_top_nodes(str(repo_abs), vault_path)
            paths = walk_from_nodes(graph, AI_TOP_NODES)

            blocks.append("=== GRAPH TRACE FROM AI_TOP_NODES ===")
            for p in paths[:5]:
                blocks.append(" → ".join(p))

            for word in query.split():
                info = explain_symbol(graph, word)
                if info["called_by"] or info["calls"]:
                    blocks.append(f"\nSymbol: {word}")
                    blocks.append(f"- called_by: {info['called_by']}")
                    blocks.append(f"- calls: {info['calls']}")

                    impact = impact_analysis(graph, word)
                    if impact:
                        blocks.append(f"- impact: {impact}")

        except Exception as e:
            blocks.append(f"GRAPH ERROR: {e}")
    execution_trace = trace_execution_flow(query, repo_path=repo_path, top_k=3)
    if execution_trace:
        blocks.append(execution_trace)

    if level in {"macro", "hybrid"}:
        project_map = get_project_map_context(repo_path)
        if project_map:
            blocks.append("=== PROJECT MAP / MACRO CONTEXT ===")
            filtered_map = extract_relevant_project_sections(query, project_map)
            blocks.append(filtered_map)


    if level in {"meso", "hybrid"}:
        symbol_hits = search_safe_code_units(query, repo_path=repo_path, limit=8, project_tag=tag)
        dependency_hits = search_dependencies_db(query, limit=5, project_tag=tag)
        if dependency_hits:
            blocks.append(format_dependency_graph(dependency_hits, query))
        # new: trace call chain
        call_trace = trace_call_chain(query, repo_path=repo_path, max_depth=3, fanout=3)
        if call_trace:
            blocks.append("=== CALL CHAIN TRACE ===")
            blocks.append(call_trace)
        if symbol_hits:
            blocks.append("=== SYMBOL / MESO CONTEXT ===")
            for hit in symbol_hits:
                blocks.append(
                    f"- {hit['file_path']}::{hit['kind']} {hit['name']} "
                    f"(sim={hit['similarity']:.3f})"
                )

    if level in {"micro", "hybrid"}:
        if file_path:
            # dùng flow RAG hiện tại của bạn
            micro_context = retrieve_file_context(query, file_path, repo_path=repo_path)
            blocks.append("=== MICRO RAG CONTEXT ===")
            blocks.append(micro_context)
        else:
            # nếu không có file cụ thể, dùng code_units toàn repo
            safe_hits = search_safe_code_units(query, repo_path=repo_path, limit=5, project_tag=tag)
            
            if safe_hits:
                blocks.append("=== MICRO CODE HITS ===")
                for h in safe_hits:
                    blocks.append(f"\n--- {h['file_path']}::{h['name']} ---")
                    blocks.append(h["content"][:2500])
                    
    return "\n\n".join(blocks)


# --- CLI ---

def main():
    prompt = sys.argv[1] if len(sys.argv) > 1 else "No prompt provided"
    file_path = sys.argv[2] if len(sys.argv) > 2 else None

    if file_path and not is_safe_path(file_path):
        print(f"Error: Unsafe file path '{file_path}'")
        return

    try:
        # Note: top_k parameter is not available in retrieve_context
        context = retrieve_context(prompt, file_path)
        print(context)
    except Exception as e:
        print(f"Retriever Error: {e}")


if __name__ == "__main__":
    main()