"""Small, deterministic retrieval over one learner-selected lecture collection.

This is lexical retrieval, not semantic search or source approval. Excerpts are
untrusted data with exact Unicode offsets; image descriptions remain user notes.
No model, network, embedding service or repository index is used here.
"""
from __future__ import annotations

from collections import Counter
from bisect import bisect_left, bisect_right
import math
import re
import unicodedata

from .material_library import MaterialLibrary
from .materials import MaterialsError, MAX_TOTAL_TEXT
from .knowledge_graph import LearningKnowledgeGraph

MAX_SOURCES = 5
MAX_CONTEXT_CHARACTERS = 8000
MAX_EXCERPT_CHARACTERS = 1600
MAX_QUERY_CHARACTERS = 8000
MAX_QUERY_TERMS = 64
# Include decomposed accent marks so copied Vietnamese stays one word without
# normalizing the stored text (which would change citation offsets).
_WORD = re.compile(r"(?:[^\W_]|[\u0300-\u036f])+(?:_(?:[^\W_]|[\u0300-\u036f])+)*", re.UNICODE)
_STOP = set("""a an the is are was were be been being to of in on at as and or
but with for from by this that these those it its i me my you your we our they
their what which who why how do does did can could would should will shall
please explain explanation describe tell give show about more example examples
according lecture lectures document documents material materials notes note
toi ban minh hay la va cua trong ve voi cho mot nhung cac nay do duoc thi khi
gi sao nao nhu co khong cung them giup giai thich vi du bai giang tai lieu
phan noi dung tren theo de xin lam ro hon day nay ay
""".split())
_FOLLOWUP = {
    "explain more", "explain further", "explain it", "explain that", "give an example",
    "give another example", "give more examples", "show an example", "simplify",
    "make it simpler", "explain it more simply", "continue", "go on", "why",
    "explain this more simply with a concrete example",
    "tell me more", "give me an example", "give me another example",
    "giai thich them", "giai thich ro hon", "giai thich don gian hon", "cho vi du",
    "cho them vi du", "vi du", "tiep tuc", "tai sao", "lam ro them",
    "cho toi them vi du", "cho toi them mot vi du de hieu phan vua roi",
    "giai thich phan vua roi don gian hon bang mot vi du gan gui",
    "더 설명해 주세요", "예를 들어 주세요", "继续解释", "举个例子",
}
_OVERVIEW = {
    "summarize", "summary", "overview", "summarise", "summarize this lecture",
    "summarize the lecture", "summarize the materials", "give an overview",
    "tom tat", "tom tat bai giang", "tom tat tai lieu", "tong quan",
    "noi dung chinh", "bai giang noi ve gi", "요약", "요약해 주세요", "总结", "概述",
}


def _fold(value):
    value = unicodedata.normalize("NFKD", value.casefold()).replace("đ", "d")
    return "".join(char for char in value if not unicodedata.combining(char))


def _phrase(value):
    words = " ".join(_fold(match.group()) for match in _WORD.finditer(value))
    for prefix in ("please ", "can you ", "could you ", "hay ", "ban hay ", "giup toi "):
        if words.startswith(prefix):
            words = words[len(prefix):]
    return words


def _wide(char):
    return ("\u3400" <= char <= "\u9fff" or "\u3040" <= char <= "\u30ff"
            or "\uac00" <= char <= "\ud7af")


def is_followup(query):
    """Recognize topic-free continuations; callers may skip these for an anchor."""
    return isinstance(query, str) and _phrase(_search_question(query)) in {_phrase(value) for value in _FOLLOWUP}


def _tokens(text):
    """Yield normalized terms with original offsets; Latin terms never substrings.

    CJK/Hangul runs also produce bigrams, a modest fallback for languages without
    Latin word boundaries. It does not translate queries between languages.
    """
    for match in _WORD.finditer(text):
        raw = match.group()
        start = 0
        while start < len(raw):
            wide = _wide(raw[start])
            end = start + 1
            while end < len(raw) and _wide(raw[end]) == wide:
                end += 1
            segment = raw[start:end]
            if wide:
                if len(segment) == 1:
                    yield _fold(segment), match.start() + start, match.start() + end
                else:
                    for index in range(len(segment) - 1):
                        yield _fold(segment[index:index + 2]), match.start() + start + index, match.start() + start + index + 2
            else:
                term = _fold(segment)
                if term not in _STOP and (len(term) > 1 or term.isdigit()):
                    yield term, match.start() + start, match.start() + end
            start = end


def _query(value):
    if (not isinstance(value, str) or len(value) > MAX_QUERY_CHARACTERS
            or any(unicodedata.category(char) == "Cs" for char in value)):
        raise MaterialsError("invalid_query", "Câu hỏi truy xuất không hợp lệ hoặc quá dài.")
    return value


def _search_question(value):
    # Explicit output-language requests are not lecture search terms. Keep the
    # topic and original source text; this does not translate either one.
    languages = r"(?:English|Vietnamese|Chinese|Mandarin|Korean)"
    value = re.sub(r"\b(?:answer|respond|reply|write)(?:\s+(?:to me|this|it))?\s+in\s+" + languages + r"\b", " ", value, flags=re.I)
    return re.sub(r"\bin\s+" + languages + r"\b", " ", value, flags=re.I)


class LectureRetriever:
    def __init__(self, library: MaterialLibrary):
        self.library = library

    @staticmethod
    def _entries(corpus):
        source_map = {source["source_id"]: source for source in corpus["sources"]}
        total = 0
        for unit in corpus["units"]:
            source = source_map[unit["source_id"]]
            text = unit["text"]
            if not isinstance(text, str):
                raise ValueError("invalid unit text")
            origin = "extracted"
            revision = None
            if source["format"] in {"png", "jpeg"}:
                note = source.get("description", {})
                text = note.get("text", "")
                origin = "user_note"
                revision = note.get("revision", 0)
            total += len(text)
            if total > MAX_TOTAL_TEXT + 40000:
                raise ValueError("oversized corpus")
            if not text.strip():
                continue
            entry = {"collection_id": corpus["id"], "source_id": unit["source_id"],
                     "unit_id": unit["unit_id"], "title": source["original_names"][0],
                     "locator": dict(unit["locator"]), "text": text, "origin": origin,
                     "warnings": list(dict.fromkeys([*source.get("warnings", []), *unit.get("warnings", [])])),
                     "review_required": True}
            if revision is not None:
                entry["annotation_revision"] = revision
            yield entry

    @staticmethod
    def _excerpt(entry, start, end):
        return {**entry, "text": entry["text"][start:end], "start_char": start, "end_char": end}

    def retrieve(self, owner, collection_id, query, *, previous_query=""):
        # Always validate ownership, even when the query has no useful keywords.
        corpus = self.library.get(owner, collection_id)
        query, previous_query = _query(query), _query(previous_query)
        query, previous_query = _search_question(query), _search_question(previous_query)
        result = {"status": "no_match", "sources": [], "collection": {"id": corpus["id"], "title": corpus["title"]},
                  "selection": "keyword", "limited_context": True}
        phrase = _phrase(query)
        overview = phrase in {_phrase(value) for value in _OVERVIEW}
        if is_followup(query) and previous_query.strip():
            query = previous_query
            result["selection"] = "followup"
            overview = _phrase(query) in {_phrase(value) for value in _OVERVIEW}
        terms = set(list(dict.fromkeys(term for term, _, _ in _tokens(query)))[:MAX_QUERY_TERMS])
        try:
            entries = list(self._entries(corpus))
        except (KeyError, TypeError, ValueError) as error:
            raise MaterialsError("invalid_collection", "Không đọc được nội dung bài giảng để truy xuất.") from error
        if overview:
            # Round-robin source files before revisiting one, so an overview is
            # not silently just the first file. This remains a bounded sample.
            groups = {}
            for entry in entries:
                groups.setdefault(entry["source_id"], []).append(entry)
            ordered = []
            for index in range(MAX_SOURCES):
                for group in groups.values():
                    if index < len(group):
                        ordered.append(group[index])
            result["selection"] = "overview"
            selected = [self._excerpt(entry, 0, min(len(entry["text"]), MAX_EXCERPT_CHARACTERS))
                        for entry in ordered[:MAX_SOURCES]]
        else:
            selected = self._concept_excerpts(owner, collection_id, query, entries)
            if selected:
                result["selection"] = "concept_link"
                result["concept_link_origin"] = "user"
            else:
                selected = self._rank(entries, terms) if terms else []
        remaining = MAX_CONTEXT_CHARACTERS
        for excerpt in selected[:MAX_SOURCES]:
            excerpt["text"] = excerpt["text"][:remaining]
            excerpt["end_char"] = excerpt["start_char"] + len(excerpt["text"])
            if not excerpt["text"].strip():
                continue
            excerpt["citation_id"] = "S" + str(len(result["sources"]) + 1)
            result["sources"].append(excerpt)
            remaining -= len(excerpt["text"])
            if remaining <= 0:
                break
        if result["sources"]:
            result["status"] = "matched"
        return result

    def _concept_excerpts(self, owner, collection_id, query, entries):
        """Follow a learner's exact label; associations are not verified facts."""
        def key(value):
            return " ".join(unicodedata.normalize("NFKC", value).casefold().split())

        label = key(query)
        if label.startswith("please "):
            label = label[7:]
        for prefix in ("explain ", "what is ", "what are ", "giải thích "):
            if label.startswith(prefix):
                label = label[len(prefix):]
                break
        candidates = {label}
        if label.endswith((".", "?")):
            candidates.add(label[:-1])
        if not label or len(label) > 81:
            return []
        # Preserve punctuation: C++ and C# must remain distinct concepts.
        links = LearningKnowledgeGraph(self.library).concept_links(owner, collection_id)
        matches = [row for row in links if key(row["label"]) in candidates]
        unit_ids = {uid for row in matches for uid in row["unit_ids"]}
        linked = [entry for entry in entries if entry["unit_id"] in unit_ids]
        terms = {term for term, _, _ in _tokens(query)}
        ranked = self._rank(linked, terms) if terms and linked else []
        if ranked:
            return ranked
        return [self._excerpt(entry, 0, min(len(entry["text"]), MAX_EXCERPT_CHARACTERS))
                for entry in linked][:MAX_SOURCES]

    def _rank(self, entries, terms):
        matches = []
        frequency = Counter()
        for entry in entries:
            hits = [(term, start, end) for term, start, end in _tokens(entry["text"]) if term in terms]
            matches.append(hits)
            frequency.update({term for term, _, _ in hits})
        weights = {term: 1 + math.log((len(entries) + 1) / (frequency[term] + 1)) for term in terms}
        query_weight = sum(weights.values())
        candidates = []
        for order, (entry, hits) in enumerate(zip(entries, matches)):
            last_end = -1
            positions = [hit[1] for hit in hits]
            for _, position, _ in hits:
                if position < last_end - 300:
                    continue
                start = max(0, position - 400)
                end = min(len(entry["text"]), start + MAX_EXCERPT_CHARACTERS)
                start = max(0, end - MAX_EXCERPT_CHARACTERS)
                if end == last_end:
                    continue
                last_end = end
                left_index, right_index = bisect_left(positions, start), bisect_right(positions, end)
                present = {term for term, _, right in hits[left_index:right_index] if right <= end}
                score = sum(weights[term] for term in present)
                # A broad shared word (e.g. Java) must not ground a question
                # whose more specific terms are absent from every excerpt.
                if score and score >= query_weight * 0.5:
                    candidates.append((score, order, start, end))
        candidates.sort(key=lambda value: (-value[0], value[1], value[2]))
        chosen = []
        threshold = candidates[0][0] * 0.5 if candidates else 0
        for score, order, start, end in candidates:
            if score < threshold:
                break
            if any(other_order == order and min(end, other_end) - max(start, other_start) > min(end - start, other_end - other_start) // 2
                   for _, other_order, other_start, other_end in chosen):
                continue
            chosen.append((score, order, start, end))
            if len(chosen) == MAX_SOURCES:
                break
        return [self._excerpt(entries[order], start, end) for _, order, start, end in chosen]
