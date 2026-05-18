from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Optional, Iterable, List, Tuple

from database.memory import get_memory_by_category, save_memory_note, get_pool
from agents.gemini_client import run_gemini_request

try:
    from config import AGENT_DIR
except Exception:
    AGENT_DIR = Path(".agent")


# ---------------------------------------------------------------------------
# Legacy whole-category consolidator. Kept for backward compatibility.
# New code should prefer consolidate_clusters (cluster-scoped, LLM-cheap)
# or consolidate_all(mode="deep") (the orchestrated pipeline).
# ---------------------------------------------------------------------------
CONSOLIDATE_PROMPT = """Below are engineering memories from the same project.
Merge duplicates. Generalize specifics where 2+ notes share a pattern.
Drop contradictions (keep the newer one).
Return JSON: [{"category": "...", "note": "...", "importance": 1-5}]
Aim to compress N notes into max N/2.

Notes:
{notes}
"""


def _backup_dir(project_tag: Optional[str]) -> Path:
    """Resolve the .agent backup folder for a project tag, creating it lazily."""
    base = AGENT_DIR / project_tag if project_tag else AGENT_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def _parse_llm_json(response: str):
    """Strip markdown fences / ``json`` prefixes, then json.loads. Returns None on failure."""
    try:
        cleaned = response.strip().strip("`").lstrip("json").strip()
        return json.loads(cleaned)
    except Exception:
        return None


def consolidate(project_tag: str, category: str = "bug_pattern"):
    """LLM-driven merge for one (project_tag, category) pair.

    Legacy API. Sends every note in the category to the LLM in one shot, then
    replaces them with whatever the LLM returned. Prefer consolidate_clusters
    for new code — it sends only small near-duplicate clusters and deletes by
    ID, so a sparse merge doesn't lose notes the LLM chose to drop silently.
    """
    # Read IDs at the same time as content so DELETE is scoped to the rows we
    # actually examined — protects against a concurrent save_memory_note racing
    # against the LLM call.
    sql = """
    SELECT id, note, importance
    FROM memory_notes
    WHERE project_tag = %s AND category = %s
    ORDER BY importance DESC, id DESC
    LIMIT 50;
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (project_tag, category))
        rows = cur.fetchall()

    if len(rows) < 8:
        return  # not enough to consolidate

    text = "\n".join(f"- [{imp}] {note}" for _, note, imp in rows)
    response = run_gemini_request(CONSOLIDATE_PROMPT.format(notes=text))
    merged = _parse_llm_json(response)
    if not isinstance(merged, list):
        return

    backup_path = _backup_dir(project_tag) / f"memory_backup_{project_tag}_{category}.json"
    backup_path.write_text(
        json.dumps(
            [{"id": rid, "note": n, "importance": imp} for rid, n, imp in rows],
            indent=2, ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    ids = [rid for rid, _, _ in rows]
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM memory_notes WHERE id = ANY(%s);", (ids,))
        conn.commit()
    for m in merged:
        save_memory_note(
            session_id=None,
            category=m.get("category", category),
            note=m["note"],
            importance=m.get("importance", 3),
            project_tag=project_tag,
        )


def dedupe_memory_notes(project_tag: Optional[str] = None) -> int:
    """Remove exact-duplicate rows from memory_notes.

    Two rows are duplicates iff they share (project_tag, category, note).
    Keeps the row with the highest importance, with newest id as a tiebreak.
    Scoped by project_tag when given, so other projects are untouched.
    Returns the number of rows deleted.
    """
    if project_tag is not None:
        sql = """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_tag, category, note
                       ORDER BY importance DESC, id DESC
                   ) AS rn
            FROM memory_notes
            WHERE project_tag = %s
        )
        DELETE FROM memory_notes
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
        params: tuple = (project_tag,)
    else:
        sql = """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY project_tag, category, note
                       ORDER BY importance DESC, id DESC
                   ) AS rn
            FROM memory_notes
        )
        DELETE FROM memory_notes
        WHERE id IN (SELECT id FROM ranked WHERE rn > 1);
        """
        params = ()

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, params)
        deleted = cur.rowcount or 0
        conn.commit()
    return int(deleted)


def dedupe_sessions_json(path: Path) -> int:
    """Remove duplicate sessions from a sessions log file in place.

    Two sessions are duplicates iff they share
    (query, repo_path, mode, project_tag). Keeps the first occurrence —
    sessions are stored newest-first by web/app.py's save_session, so the
    most recent run survives.

    Returns the number of entries removed. Returns 0 (no file rewrite) when
    the file is missing or unreadable.
    """
    p = Path(path)
    if not p.exists():
        return 0

    try:
        sessions = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return 0

    if not isinstance(sessions, list):
        return 0

    seen: set[tuple] = set()
    deduped: list[dict] = []
    for s in sessions:
        if not isinstance(s, dict):
            deduped.append(s)
            continue
        key = (
            (s.get("query") or "").strip(),
            (s.get("repo_path") or "").strip(),
            (s.get("mode") or "").strip(),
            (s.get("project_tag") or "").strip(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(s)

    removed = len(sessions) - len(deduped)
    if removed > 0:
        p.write_text(
            json.dumps(deduped, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    return removed


# ---------------------------------------------------------------------------
# Test-log dedupe — collapse `.agent/<lang>test-<hash>` directories that map
# to the same project. The dedupe key hashes ALL three artifact files
# (PROJECT_MAP.md, code_dna.json, PHANTOM_LIMB.json) together — PROJECT_MAP
# alone misses divergence in code_dna (e.g. C++ run vs Rust run that share
# a project map skeleton). Keeps the newest run by mtime.
# ---------------------------------------------------------------------------
_TEST_LOG_FILES = ("PROJECT_MAP.md", "code_dna.json", "PHANTOM_LIMB.json")


def _is_test_log_dir(p: Path) -> bool:
    """A test-log directory has 'test' in its name and contains PROJECT_MAP.md."""
    return p.is_dir() and "test" in p.name.lower() and (p / "PROJECT_MAP.md").exists()


def _test_log_fingerprint(d: Path) -> Optional[str]:
    """Hash of all three artifact files concatenated. Missing files contribute
    a null marker, so two dirs with the same missing file still match each
    other but not a dir where the file is present.
    """
    h = hashlib.sha1()
    for fname in _TEST_LOG_FILES:
        h.update(fname.encode("utf-8"))
        h.update(b"\0")
        p = d / fname
        try:
            h.update(p.read_bytes() if p.exists() else b"\0__missing__")
        except OSError:
            return None
        h.update(b"\0")
    return h.hexdigest()


def dedupe_test_logs(
    agent_dir: Optional[Path] = None,
    dry_run: bool = False,
) -> dict:
    """Remove duplicate test-log directories from .agent/.

    Two dirs are duplicates iff they share the same fingerprint over
    PROJECT_MAP.md + code_dna.json + PHANTOM_LIMB.json. The newest dir by
    PROJECT_MAP.md mtime survives in each group.

    Before deletion, a manifest containing the FULL contents of every removed
    dir's three artifact files is appended to
    .agent/test_log_dedupe_manifest.json — this is the recovery path if a
    deletion turns out to be wrong.

    Args:
        agent_dir: scan root, defaults to AGENT_DIR.
        dry_run: when True, returns the plan without deleting.

    Returns dict with: groups_found, dirs_removed, kept, removed (list of names).
    """
    root = Path(agent_dir) if agent_dir is not None else AGENT_DIR
    if not root.exists():
        return {"groups_found": 0, "dirs_removed": 0, "kept": [], "removed": []}

    by_hash: dict[str, list[Path]] = {}
    for child in root.iterdir():
        if not _is_test_log_dir(child):
            continue
        digest = _test_log_fingerprint(child)
        if digest is None:
            continue
        by_hash.setdefault(digest, []).append(child)

    kept: list[str] = []
    removed_dirs: list[Path] = []
    groups_found = 0
    for digest, dirs in by_hash.items():
        if len(dirs) < 2:
            continue
        groups_found += 1
        # Newest mtime on PROJECT_MAP.md wins — that's the most recent scan.
        dirs.sort(key=lambda p: (p / "PROJECT_MAP.md").stat().st_mtime, reverse=True)
        kept.append(dirs[0].name)
        removed_dirs.extend(dirs[1:])

    removed = [d.name for d in removed_dirs]

    if removed and not dry_run:
        backup_entries: list[dict] = []
        for d in removed_dirs:
            entry: dict = {"name": d.name, "files": {}}
            for fname in _TEST_LOG_FILES:
                p = d / fname
                if p.exists():
                    try:
                        entry["files"][fname] = p.read_text(encoding="utf-8")
                    except (OSError, UnicodeDecodeError):
                        entry["files"][fname] = None
            backup_entries.append(entry)

        manifest_path = root / "test_log_dedupe_manifest.json"
        existing: list[dict] = []
        if manifest_path.exists():
            try:
                loaded = json.loads(manifest_path.read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    existing = loaded
            except Exception:
                existing = []
        existing.append({
            "kept": kept,
            "removed": removed,
            "backup": backup_entries,
        })
        manifest_path.write_text(
            json.dumps(existing, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        for d in removed_dirs:
            shutil.rmtree(d, ignore_errors=True)

    return {
        "groups_found": groups_found,
        "dirs_removed": len(removed),
        "kept": kept,
        "removed": removed,
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Cluster-scoped LLM merge — the core compression engine.
# Pulls near-duplicates via pgvector cosine, groups them, sends ONE cluster
# at a time to the LLM. Avoids the "send 50 notes, hope for the best" pattern.
# ---------------------------------------------------------------------------
_CLUSTER_PROMPT = """You are merging duplicate engineering memory notes from one project.

Below are {n} notes that are near-duplicates of each other. Produce ONE
replacement note that:
- captures the shared insight in 1-2 sentences
- generalizes specifics so it covers all inputs
- inherits the highest importance (1-5) seen in the inputs

Return ONLY JSON: {{"note": "...", "importance": <1-5>}}

Notes:
{notes}
"""


def _find_similar_pairs(
    project_tag: str,
    category: str,
    threshold: float,
) -> List[Tuple[int, str, int, int, str, int, float]]:
    """Self-join on memory_notes — return pairs above the cosine threshold.

    Each row: (id_a, note_a, imp_a, id_b, note_b, imp_b, similarity).
    """
    sql = """
    WITH base AS (
        SELECT id, note, importance, embedding
        FROM memory_notes
        WHERE project_tag = %s AND category = %s AND embedding IS NOT NULL
    )
    SELECT a.id, a.note, a.importance,
           b.id, b.note, b.importance,
           1 - (a.embedding <=> b.embedding) AS sim
    FROM base a
    JOIN base b ON a.id < b.id
    WHERE 1 - (a.embedding <=> b.embedding) >= %s
    ORDER BY sim DESC;
    """
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql, (project_tag, category, threshold))
        return [
            (ia, na, int(ima), ib, nb, int(imb), float(sim))
            for ia, na, ima, ib, nb, imb, sim in cur.fetchall()
        ]


def _cluster_pairs(
    pairs: List[Tuple[int, str, int, int, str, int, float]],
) -> List[List[Tuple[int, str, int]]]:
    """Union-find on similar pairs → list of clusters. Each cluster is
    [(id, note, importance), ...]. Singletons are dropped."""
    parent: dict[int, int] = {}
    notes_by_id: dict[int, Tuple[str, int]] = {}

    def find(x: int) -> int:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for ia, na, ima, ib, nb, imb, _ in pairs:
        notes_by_id[ia] = (na, ima)
        notes_by_id[ib] = (nb, imb)
        parent.setdefault(ia, ia)
        parent.setdefault(ib, ib)
        union(ia, ib)

    groups: dict[int, List[int]] = {}
    for nid in notes_by_id:
        groups.setdefault(find(nid), []).append(nid)

    return [
        [(nid, *notes_by_id[nid]) for nid in ids]
        for ids in groups.values()
        if len(ids) >= 2
    ]


def consolidate_clusters(
    project_tag: str,
    category: str = "bug_pattern",
    similarity_threshold: float = 0.85,
    max_clusters: int = 10,
) -> dict:
    """LLM-merge near-duplicate clusters within (project_tag, category).

    Improvements over `consolidate()`:
      - Sends ONE small cluster to the LLM at a time, not all 50 notes.
      - Deletes only the IDs that were merged, never the whole category.
      - Skips clusters whose LLM response failed to parse (no data loss).

    Args:
        project_tag: scope to one project; required.
        category: which category to compress (default: bug_pattern).
        similarity_threshold: cosine similarity above which two notes are
            considered duplicates. 0.85 is conservative; 0.75 is aggressive.
        max_clusters: cap LLM calls per run to keep cost bounded.
    """
    pairs = _find_similar_pairs(project_tag, category, similarity_threshold)
    if not pairs:
        return {"category": category, "clusters_merged": 0, "notes_removed": 0}

    clusters = _cluster_pairs(pairs)
    if not clusters:
        return {"category": category, "clusters_merged": 0, "notes_removed": 0}

    # Process biggest clusters first — they yield the most compression per call.
    clusters.sort(key=len, reverse=True)
    clusters = clusters[:max_clusters]

    notes_removed = 0
    backup: list[dict] = []

    for cluster in clusters:
        text = "\n".join(f"- [{imp}] {note}" for _, note, imp in cluster)
        prompt = _CLUSTER_PROMPT.format(n=len(cluster), notes=text)
        response = run_gemini_request(prompt)
        merged = _parse_llm_json(response)
        if not isinstance(merged, dict) or "note" not in merged:
            continue  # parse failed — leave this cluster intact

        backup.extend(
            {"id": nid, "note": note, "importance": imp}
            for nid, note, imp in cluster
        )

        ids = [nid for nid, _, _ in cluster]
        with get_pool().connection() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM memory_notes WHERE id = ANY(%s);", (ids,))
            conn.commit()
        notes_removed += len(ids)

        fallback_imp = max(imp for _, _, imp in cluster)
        save_memory_note(
            session_id=None,
            category=category,
            note=str(merged["note"]).strip(),
            importance=int(merged.get("importance", fallback_imp)),
            project_tag=project_tag,
        )

    if backup:
        backup_path = _backup_dir(project_tag) / f"cluster_backup_{category}.json"
        backup_path.write_text(
            json.dumps(backup, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    return {
        "category": category,
        "clusters_merged": len(clusters),
        "notes_removed": notes_removed,
    }


# ---------------------------------------------------------------------------
# Forgetfulness — archive low-importance, old notes out of the hot table.
# Backed up to .agent/<tag>/ before deletion so nothing is truly lost.
# ---------------------------------------------------------------------------
def archive_stale_notes(
    project_tag: Optional[str] = None,
    max_age_days: int = 60,
    max_importance: int = 2,
) -> int:
    """Archive low-importance notes older than `max_age_days`.

    "Archive" = serialize to .agent/<tag>/archive_stale.json (append) and
    delete from the hot table. High-importance notes are never archived,
    so durable rules survive.

    Returns the number of rows removed.
    """
    if project_tag is not None:
        sql_select = """
        SELECT id, category, note, importance, created_at
        FROM memory_notes
        WHERE project_tag = %s
          AND importance <= %s
          AND created_at < NOW() - (%s || ' days')::interval
        ORDER BY id;
        """
        params: tuple = (project_tag, max_importance, str(max_age_days))
    else:
        sql_select = """
        SELECT id, category, note, importance, created_at
        FROM memory_notes
        WHERE importance <= %s
          AND created_at < NOW() - (%s || ' days')::interval
        ORDER BY id;
        """
        params = (max_importance, str(max_age_days))

    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute(sql_select, params)
        rows = cur.fetchall()

    if not rows:
        return 0

    archive = [
        {
            "id": rid,
            "category": cat,
            "note": note,
            "importance": int(imp),
            "created_at": ts.isoformat() if ts else None,
        }
        for rid, cat, note, imp, ts in rows
    ]

    archive_path = _backup_dir(project_tag) / "archive_stale.json"
    existing: list[dict] = []
    if archive_path.exists():
        try:
            loaded = json.loads(archive_path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                existing = loaded
        except Exception:
            existing = []
    archive_path.write_text(
        json.dumps(existing + archive, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    ids = [r["id"] for r in archive]
    with get_pool().connection() as conn, conn.cursor() as cur:
        cur.execute("DELETE FROM memory_notes WHERE id = ANY(%s);", (ids,))
        conn.commit()

    return len(ids)


# ---------------------------------------------------------------------------
# Project rules extraction — distill semantic memory into a small JSON
# sitting next to code_dna.json. Lets the prompter read precompressed rules
# instead of re-deriving them from raw notes every request.
# ---------------------------------------------------------------------------
_RULES_PROMPT = """You are distilling project rules from engineering memory notes.

Output up to 8 rules. Each rule must be:
- one short sentence (under 20 words)
- specific to this project (cite tooling, conventions, or constraints)
- actionable for an AI coding assistant

Drop weak/duplicate notes. Each rule belongs to one of:
  conventions | tooling | bug_patterns | project_context

Return ONLY JSON:
{{
  "rules": [
    {{"category": "conventions", "rule": "..."}}
  ]
}}

Notes:
{notes}
"""


def extract_project_rules(project_tag: str, per_category_limit: int = 25) -> Optional[Path]:
    """Distill semantic memory notes into .agent/<tag>/project_rules.json.

    Pulls from rule-like categories (project_context, repo_convention,
    tooling_command, learning_style, bug_pattern) and asks the LLM to compress
    them into a short rule set the prompter can read directly. Returns the
    output path, or None when there's not enough material or the LLM fails.
    """
    rule_categories = [
        "project_context",
        "repo_convention",
        "tooling_command",
        "learning_style",
        "bug_pattern",
    ]
    notes: list[dict] = []
    for cat in rule_categories:
        notes.extend(
            get_memory_by_category(cat, limit=per_category_limit, project_tag=project_tag)
        )

    if len(notes) < 3:
        return None

    text = "\n".join(
        f"- [{n['category']}] (imp={n.get('importance', '?')}) {n['note']}"
        for n in notes
    )
    response = run_gemini_request(_RULES_PROMPT.format(notes=text))
    parsed = _parse_llm_json(response)
    if not isinstance(parsed, dict) or "rules" not in parsed:
        return None

    out_path = _backup_dir(project_tag) / "project_rules.json"
    out_path.write_text(json.dumps(parsed, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


# ---------------------------------------------------------------------------
# Orchestration. "fast" preserves the existing UI behavior (strict dedupe,
# no LLM cost). "deep" layers cluster-merge, archive, and rules extraction
# on top — opt-in so the manual button stays cheap.
# ---------------------------------------------------------------------------
def consolidate_all(
    project_tag: Optional[str] = None,
    sessions_paths: Optional[Iterable[Path]] = None,
    mode: str = "fast",
    cluster_categories: Optional[Iterable[str]] = None,
    archive_max_age_days: int = 60,
    archive_max_importance: int = 2,
) -> dict:
    """Run dedupe passes and (optionally) deep consolidation. Returns stats.

    Modes:
      "fast" — strict dedupe across memory_notes + sessions logs. No LLM
               calls. This is what the web UI button calls today.
      "deep" — fast pass, plus per-category cluster-merge, age-based archive,
               and project_rules.json extraction. Requires `project_tag`.

    Args:
        project_tag: scope dedupe / cluster / archive to a project.
        sessions_paths: iterable of session-log JSON files to dedupe in place.
        mode: "fast" (default) or "deep".
        cluster_categories: which categories to cluster-merge in deep mode.
            Defaults to ["bug_pattern", "successful_fix"] — the high-volume
            episodic categories that benefit most from compression.
        archive_max_age_days: notes older than this become archive candidates.
        archive_max_importance: notes with importance ≤ this are archive candidates.
    """
    notes_removed = dedupe_memory_notes(project_tag=project_tag)
    test_logs_stats = dedupe_test_logs()

    sessions_stats: list[dict] = []
    for path in (sessions_paths or []):
        p = Path(path)
        removed = dedupe_sessions_json(p)
        sessions_stats.append({
            "path": str(p),
            "existed": p.exists(),
            "removed": removed,
        })

    deep: Optional[dict] = None
    if mode == "deep":
        if not project_tag:
            deep = {"skipped": "deep mode requires a project_tag"}
        else:
            cats = list(cluster_categories) if cluster_categories else [
                "bug_pattern", "successful_fix",
            ]
            cluster_stats = [
                consolidate_clusters(project_tag=project_tag, category=cat)
                for cat in cats
            ]
            archived = archive_stale_notes(
                project_tag=project_tag,
                max_age_days=archive_max_age_days,
                max_importance=archive_max_importance,
            )
            rules_path = extract_project_rules(project_tag)
            deep = {
                "clusters": cluster_stats,
                "archived": archived,
                "rules_path": str(rules_path) if rules_path else None,
            }

    return {
        "memory_notes_removed": notes_removed,
        "project_tag": project_tag,
        "sessions": sessions_stats,
        "test_logs": test_logs_stats,
        "mode": mode,
        "deep": deep,
    }
