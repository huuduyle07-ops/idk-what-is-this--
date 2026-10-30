"""Owner-scoped concept links over immutable lecture units.

SQLite stores only user-confirmed links and edit revisions. Source containment
comes from MaterialLibrary on each read; ProgramGraph is a bounded projection,
not the source of truth or a code graph cache. Confirmation records a user's
association, not source correctness, mastery, or teaching approval.
"""
from __future__ import annotations

import hashlib
from itertools import combinations
from pathlib import Path
import sqlite3
import unicodedata

from graph.schema import ProgramGraph
from .material_library import MaterialLibrary
from .materials import MaterialsError

MAX_CONCEPTS_PER_UNIT = 12
MAX_LABEL_CHARACTERS = 80
MAX_COLLECTION_CONCEPTS = 500
MAX_COLLECTION_LINKS = 5000
MAX_RELATED = 30
MAX_EXCERPT_CHARACTERS = 300
MAX_MAP_CONCEPTS = 30
MAX_MAP_SOURCES = 10
MAX_MAP_UNIT_PREVIEWS = 5
MAX_MAP_EXCERPT_CHARACTERS = 500
MAX_MAP_SHARED_EDGES = 60
_APPLICATION_ID = 0x434B4731
_SCHEMA_VERSION = 1
_SCHEMA = (
    """CREATE TABLE concepts (
        collection_id TEXT NOT NULL, concept_id TEXT NOT NULL,
        normalized_label TEXT NOT NULL, label TEXT NOT NULL,
        PRIMARY KEY (collection_id, concept_id),
        UNIQUE (collection_id, normalized_label))""",
    """CREATE TABLE unit_state (
        collection_id TEXT NOT NULL, unit_id TEXT NOT NULL,
        revision INTEGER NOT NULL CHECK (revision >= 0),
        PRIMARY KEY (collection_id, unit_id))""",
    """CREATE TABLE unit_concepts (
        collection_id TEXT NOT NULL, unit_id TEXT NOT NULL, concept_id TEXT NOT NULL,
        PRIMARY KEY (collection_id, unit_id, concept_id),
        FOREIGN KEY (collection_id, unit_id)
            REFERENCES unit_state(collection_id, unit_id) ON DELETE CASCADE,
        FOREIGN KEY (collection_id, concept_id)
            REFERENCES concepts(collection_id, concept_id) ON DELETE CASCADE)""",
    "CREATE INDEX concept_units ON unit_concepts(collection_id, concept_id, unit_id)",
)


def _invalid_storage(error=None):
    return MaterialsError("invalid_storage", "Không đọc hoặc ghi được liên kết học tập. Hãy thử lại sau khi kiểm tra kho tài liệu.")


def _normalize_labels(labels) -> dict[str, str]:
    if not isinstance(labels, list) or len(labels) > MAX_CONCEPTS_PER_UNIT:
        raise MaterialsError("invalid_concepts", "Mỗi phần nguồn nhận tối đa 12 khái niệm.")
    normalized = {}
    for raw in labels:
        if (not isinstance(raw, str) or len(raw) > MAX_LABEL_CHARACTERS * 4
                or any(unicodedata.category(c) in {"Cc", "Cf", "Cs"} for c in raw)):
            raise MaterialsError("invalid_concepts", "Tên khái niệm có ký tự không hợp lệ.")
        label = " ".join(unicodedata.normalize("NFKC", raw).split())
        if not label or len(label) > MAX_LABEL_CHARACTERS:
            raise MaterialsError("invalid_concepts", "Tên khái niệm cần từ 1–80 ký tự.")
        key = label.casefold()
        normalized.setdefault(key, label)
    return normalized


def _concept_id(collection_id: str, normalized_label: str) -> str:
    identity = (collection_id + "\0" + normalized_label).encode("utf-8")
    return "concept-" + hashlib.sha256(identity).hexdigest()


class LearningKnowledgeGraph:
    def __init__(self, library: MaterialLibrary):
        self.library = library

    def _corpus(self, owner, collection_id, unit_id):
        corpus = self.library.get(owner, collection_id)
        units = {unit["unit_id"]: unit for unit in corpus["units"]}
        if not isinstance(unit_id, str) or unit_id not in units:
            raise MaterialsError("not_found", "Không tìm thấy phần nguồn trong bộ tài liệu này.")
        return corpus, units

    def _database_path(self, owner: str) -> Path:
        # MaterialLibrary owns validation of the browser's opaque owner and root.
        directory = self.library._owner_dir(owner)
        path = directory / "knowledge.sqlite3"
        try:
            for candidate in (path, *(Path(str(path) + suffix) for suffix in ("-journal", "-wal", "-shm"))):
                if (candidate.is_symlink() or candidate.resolve().parent != directory.resolve()
                        or (candidate.exists() and not candidate.is_file())):
                    raise _invalid_storage()
        except OSError as error:
            raise _invalid_storage() from error
        return path

    @staticmethod
    def _connect(path: Path, *, write: bool):
        connection = sqlite3.connect(path.as_uri() + ("?mode=rwc" if write else "?mode=ro"),
                                     uri=True, timeout=5, isolation_level=None)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _schema(connection, *, initialize=False):
        version = connection.execute("PRAGMA user_version").fetchone()[0]
        application = connection.execute("PRAGMA application_id").fetchone()[0]
        if version == 0 and application == 0 and initialize:
            if connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchone():
                raise _invalid_storage()
            for statement in _SCHEMA:
                connection.execute(statement)
            connection.execute(f"PRAGMA application_id = {_APPLICATION_ID}")
            connection.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")
        elif version != _SCHEMA_VERSION or application != _APPLICATION_ID:
            raise _invalid_storage()

    @staticmethod
    def _state(connection, collection_id):
        concepts = {row["concept_id"]: dict(row) for row in connection.execute(
            "SELECT concept_id, normalized_label, label FROM concepts WHERE collection_id = ?",
            (collection_id,))}
        links = {}
        for row in connection.execute("SELECT unit_id, concept_id FROM unit_concepts WHERE collection_id = ?", (collection_id,)):
            links.setdefault(row["unit_id"], set()).add(row["concept_id"])
        revisions = {row["unit_id"]: row["revision"] for row in connection.execute(
            "SELECT unit_id, revision FROM unit_state WHERE collection_id = ?", (collection_id,))}
        if len(concepts) > MAX_COLLECTION_CONCEPTS or sum(map(len, links.values())) > MAX_COLLECTION_LINKS:
            raise _invalid_storage()
        return concepts, links, revisions

    def get(self, owner: str, collection_id: str, unit_id: str) -> dict:
        corpus, units = self._corpus(owner, collection_id, unit_id)
        path = self._database_path(owner)
        if not path.exists():
            return self._view(corpus, units, unit_id, {}, {}, {})
        connection = None
        try:
            connection = self._connect(path, write=False)
            connection.execute("BEGIN")
            self._schema(connection)
            state = self._state(connection, collection_id)
            return self._view(corpus, units, unit_id, *state)
        except (sqlite3.Error, OSError, KeyError, ValueError, TypeError) as error:
            raise _invalid_storage() from error
        finally:
            if connection is not None:
                connection.close()

    def _collection_state(self, owner, collection_id):
        corpus = self.library.get(owner, collection_id)
        path = self._database_path(owner)
        connection = None
        try:
            concepts, links = {}, {}
            if path.exists():
                connection = self._connect(path, write=False)
                connection.execute("BEGIN")
                self._schema(connection)
                concepts, links, _ = self._state(connection, collection_id)
            return corpus, concepts, links
        except (sqlite3.Error, OSError, KeyError, ValueError, TypeError, IndexError) as error:
            raise _invalid_storage() from error
        finally:
            if connection is not None:
                connection.close()

    def collection_map(self, owner: str, collection_id: str) -> dict:
        """Project explicit associations and source structure without inferring facts."""
        corpus, concepts, links = self._collection_state(owner, collection_id)
        try:
            return self._map_view(corpus, concepts, links)
        except (KeyError, ValueError, TypeError, IndexError) as error:
            raise _invalid_storage() from error

    def concept_links(self, owner: str, collection_id: str) -> list[dict]:
        """Return all explicit labels and valid unit IDs, within storage quotas.

        Unlike the visual map, this view does not trim the alphabetic tail. It
        lets a selected alias (e.g. ISR) resolve the units the learner linked.
        """
        corpus, concepts, links = self._collection_state(owner, collection_id)
        try:
            _, _, memberships = self._concept_memberships(corpus, concepts, links)
            ordered = sorted(memberships, key=lambda cid: (concepts[cid]["normalized_label"], cid))
            return [{"label": concepts[cid]["label"], "unit_ids": memberships[cid]} for cid in ordered]
        except (KeyError, ValueError, TypeError, IndexError) as error:
            raise _invalid_storage() from error

    @staticmethod
    def _concept_memberships(corpus, concepts, links):
        units = {unit["unit_id"]: unit for unit in corpus["units"]}
        # A stale link cannot revive a removed unit or a deleted concept. Only
        # associations whose endpoints are in this collection are projected.
        linked = {uid: tags & concepts.keys() for uid, tags in links.items() if uid in units}
        concept_units = {}
        for uid in units:
            for cid in linked.get(uid, ()):
                concept_units.setdefault(cid, []).append(uid)
        for cid in concept_units:
            concept = concepts[cid]
            normalized = _normalize_labels([concept["label"]])
            if (list(normalized) != [concept["normalized_label"]]
                    or cid != _concept_id(corpus["id"], concept["normalized_label"])):
                raise _invalid_storage()
        return units, linked, concept_units

    @staticmethod
    def _map_view(corpus, concepts, links):
        sources = {source["source_id"]: source for source in corpus["sources"]}
        units, linked, concept_units = LearningKnowledgeGraph._concept_memberships(corpus, concepts, links)
        source_units = {sid: [] for sid in sources}
        for uid, unit in units.items():
            source_units[unit["source_id"]].append(uid)
        ordered_concepts = sorted(concept_units, key=lambda cid: (concepts[cid]["normalized_label"], cid))
        selected_concepts = ordered_concepts[:MAX_MAP_CONCEPTS]
        selected_sources = list(sources)[:MAX_MAP_SOURCES]
        truncated = len(ordered_concepts) > MAX_MAP_CONCEPTS or len(sources) > MAX_MAP_SOURCES

        def preview(uid):
            unit = units[uid]
            source = sources[unit["source_id"]]
            note = source.get("description", {}) if source["format"] in {"png", "jpeg"} else None
            content = note.get("text", "") if note is not None else unit["text"]
            item = {"unit_id": uid, "source_id": unit["source_id"],
                    "source_name": source["original_names"][0], "locator": dict(unit["locator"]),
                    "excerpt": content[:MAX_MAP_EXCERPT_CHARACTERS],
                    "origin": "user_note" if note is not None else "extracted"}
            if note is not None:
                item["annotation_revision"] = note.get("revision", 0)
            return item

        def metadata(unit_ids, origin):
            nonlocal truncated
            limited = len(unit_ids) > MAX_MAP_UNIT_PREVIEWS
            truncated = truncated or limited
            return {"origin": origin, "units": [preview(uid) for uid in unit_ids[:MAX_MAP_UNIT_PREVIEWS]],
                    "unit_count": len(unit_ids), "units_truncated": limited}

        graph = ProgramGraph()
        root = "collection:" + corpus["id"]
        graph.add_node(root, "collection", corpus["title"], origin="source_structure")
        for sid in selected_sources:
            graph.add_node(sid, "source", sources[sid]["original_names"][0],
                           **metadata(source_units[sid], "source_structure"))
            graph.add_edge(root, sid, "contains_source", origin="source_structure", status="deterministic")
        for cid in selected_concepts:
            graph.add_node(cid, "concept", concepts[cid]["label"], **metadata(concept_units[cid], "user"))
            graph.add_edge(root, cid, "has_concept", origin="user", status="user_confirmed")

        shared = {}
        chosen = set(selected_concepts)
        for uid in units:
            for pair in combinations(sorted(linked.get(uid, set()) & chosen), 2):
                shared.setdefault(pair, []).append(uid)
        # Deterministic order makes truncation and refresh behavior predictable.
        pairs = sorted(shared, key=lambda pair: (-len(shared[pair]), pair))
        truncated = truncated or len(pairs) > MAX_MAP_SHARED_EDGES
        for left, right in pairs[:MAX_MAP_SHARED_EDGES]:
            refs = shared[(left, right)]
            truncated = truncated or len(refs) > MAX_MAP_UNIT_PREVIEWS
            graph.add_edge(left, right, "shared_source", origin="user", status="derived_from_user_links",
                           unit_count=len(refs), unit_ids=refs[:MAX_MAP_UNIT_PREVIEWS],
                           units_truncated=len(refs) > MAX_MAP_UNIT_PREVIEWS)
        return {"collection": {"id": corpus["id"], "title": corpus["title"]},
                "graph": graph.to_dict(), "concept_count": len(ordered_concepts),
                "source_count": len(sources), "truncated": truncated, "grounding_ready": False}

    def set_concepts(self, owner: str, collection_id: str, unit_id: str,
                     labels: list[str], expected_revision: int) -> dict:
        normalized = _normalize_labels(labels)
        if type(expected_revision) is not int or expected_revision < 0:
            raise MaterialsError("invalid_concepts", "Phiên bản liên kết không hợp lệ.")
        corpus, units = self._corpus(owner, collection_id, unit_id)
        path = self._database_path(owner)
        wanted = {_concept_id(collection_id, key): (key, label) for key, label in normalized.items()}
        connection = None
        try:
            connection = self._connect(path, write=True)
            connection.execute("BEGIN IMMEDIATE")
            self._schema(connection, initialize=True)
            concepts, links, revisions = self._state(connection, collection_id)
            revision = revisions.get(unit_id, 0)
            current = links.get(unit_id, set())
            if set(wanted) == current and expected_revision in {revision, revision - 1}:
                view = self._view(corpus, units, unit_id, concepts, links, revisions)
                connection.commit()
                return view
            if expected_revision != revision:
                raise MaterialsError("knowledge_conflict", "Khái niệm đã được sửa ở lượt khác. Xem bản đã lưu trước khi sửa tiếp.")

            other_links = {key: value for key, value in links.items() if key != unit_id}
            retained_ids = set().union(*other_links.values()) if other_links else set()
            if (len(retained_ids | set(wanted)) > MAX_COLLECTION_CONCEPTS
                    or sum(map(len, other_links.values())) + len(wanted) > MAX_COLLECTION_LINKS):
                raise MaterialsError("knowledge_limit", "Bộ tài liệu đã đạt giới hạn liên kết khái niệm. Hãy bỏ liên kết không cần dùng.")

            connection.execute("INSERT INTO unit_state(collection_id, unit_id, revision) VALUES (?, ?, ?) "
                               "ON CONFLICT(collection_id, unit_id) DO UPDATE SET revision=excluded.revision",
                               (collection_id, unit_id, revision + 1))
            connection.execute("DELETE FROM unit_concepts WHERE collection_id=? AND unit_id=?", (collection_id, unit_id))
            for concept_id, (key, label) in wanted.items():
                connection.execute("INSERT OR IGNORE INTO concepts(collection_id, concept_id, normalized_label, label) VALUES (?, ?, ?, ?)",
                                   (collection_id, concept_id, key, label))
                connection.execute("INSERT INTO unit_concepts(collection_id, unit_id, concept_id) VALUES (?, ?, ?)",
                                   (collection_id, unit_id, concept_id))
            connection.execute("DELETE FROM concepts WHERE collection_id=? AND NOT EXISTS "
                               "(SELECT 1 FROM unit_concepts l WHERE l.collection_id=concepts.collection_id AND l.concept_id=concepts.concept_id)",
                               (collection_id,))
            view = self._view(corpus, units, unit_id, *self._state(connection, collection_id))
            connection.commit()
            return view
        except (sqlite3.Error, OSError, KeyError, ValueError, TypeError) as error:
            # MaterialsError inherits ValueError: retain its explicit conflicts,
            # validation and quota codes while the transaction rolls back.
            if isinstance(error, MaterialsError):
                raise
            raise _invalid_storage() from error
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _view(corpus, units, selected_id, concepts, links, revisions):
        selected = units[selected_id]
        selected_concepts = links.get(selected_id, set())
        sources = {source["source_id"]: source for source in corpus["sources"]}
        order = {unit_id: index for index, unit_id in enumerate(units)}

        def public_concepts(ids):
            return [{"id": cid, "label": concepts[cid]["label"]} for cid in sorted(ids, key=lambda cid: (concepts[cid]["normalized_label"], cid))]

        matches = [(unit_id, tags & selected_concepts) for unit_id, tags in links.items()
                   if unit_id != selected_id and unit_id in units and tags & selected_concepts]
        matches.sort(key=lambda item: (-len(item[1]), order[item[0]]))
        related = []
        for unit_id, shared in matches[:MAX_RELATED]:
            unit = units[unit_id]
            source = sources[unit["source_id"]]
            related.append({"unit_id": unit_id, "source_id": unit["source_id"],
                            "source_name": source["original_names"][0], "locator": unit["locator"],
                            "concepts": public_concepts(shared), "excerpt": unit["text"][:MAX_EXCERPT_CHARACTERS]})

        graph = ProgramGraph()
        projected = [(selected_id, selected_concepts), *((row["unit_id"], {c["id"] for c in row["concepts"]}) for row in related)]
        for unit_id, tags in projected:
            unit = units[unit_id]
            source_id = unit["source_id"]
            source = sources[source_id]
            graph.add_node(source_id, "source", source["original_names"][0], collection_id=corpus["id"], source_id=source_id)
            graph.add_node(unit_id, "source_unit", unit["locator"]["kind"] + " " + str(unit["locator"]["index"]),
                           collection_id=corpus["id"], source_id=source_id, locator=unit["locator"])
            graph.add_edge(source_id, unit_id, "contains", origin="source_structure", status="deterministic", source_unit_id=unit_id)
            for concept in public_concepts(tags):
                graph.add_node(concept["id"], "concept", concept["label"], collection_id=corpus["id"])
                graph.add_edge(unit_id, concept["id"], "related_to_concept", origin="user", status="user_confirmed", source_unit_id=unit_id)
        return {"unit_id": selected_id, "source_id": selected["source_id"], "locator": selected["locator"],
                "revision": revisions.get(selected_id, 0), "concepts": public_concepts(selected_concepts),
                "related": related, "related_total": len(matches), "related_truncated": len(matches) > MAX_RELATED,
                "graph": graph.to_dict(), "grounding_ready": False}
