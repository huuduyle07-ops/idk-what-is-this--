"""Local lecture retrieval: bounded excerpts, provenance and query isolation."""
import io
import unicodedata

from docx import Document
from PIL import Image
import pytest

from core.learning.chat_retrieval import LectureRetriever, is_followup
from core.learning.material_library import MaterialLibrary
from core.learning.materials import MaterialsError
from core.learning.knowledge_graph import LearningKnowledgeGraph

OWNER = "a" * 64
OTHER = "b" * 64


def document(*paragraphs):
    doc = Document()
    for paragraph in paragraphs:
        doc.add_paragraph(paragraph)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def picture():
    output = io.BytesIO()
    Image.new("RGB", (20, 20), (30, 70, 50)).save(output, format="PNG")
    return output.getvalue()


def imported(tmp_path, uploads, *, title="Course"):
    library = MaterialLibrary(tmp_path / "materials")
    corpus, _ = library.import_files(OWNER, "retrieval-request-0001", title, uploads)
    return library, corpus, LectureRetriever(library)


@pytest.fixture
def course(tmp_path):
    return imported(tmp_path, [
        ("java/lecture.docx", document(
            "Kế thừa giúp lớp con sử dụng hành vi từ lớp cha. Java supports inheritance.",
            "Overriding changes the implementation selected by runtime dispatch.",
            "Classification is a separate topic.",
        )),
        ("systems/lecture.docx", document(
            "Virtual memory maps virtual addresses to physical memory using page tables.",
            "Scheduling selects a process to run on the CPU.",
        )),
    ])


def test_retrieval_keeps_exact_source_offsets_and_does_not_write(course):
    library, corpus, retriever = course
    before = {path: path.read_bytes() for path in library.root.rglob("*") if path.is_file()}
    result = retriever.retrieve(OWNER, corpus["id"], "Explain inheritance.")
    assert result["status"] == "matched" and result["selection"] == "keyword"
    assert result["collection"] == {"id": corpus["id"], "title": "Course"}
    assert result["limited_context"] is True
    assert result["sources"][0]["title"] == "java/lecture.docx"
    units = {unit["unit_id"]: unit for unit in corpus["units"]}
    for index, source in enumerate(result["sources"], 1):
        unit = units[source["unit_id"]]
        assert source["citation_id"] == f"S{index}"
        assert source["collection_id"] == corpus["id"]
        assert source["source_id"] == unit["source_id"]
        assert source["locator"] == unit["locator"]
        assert source["origin"] == "extracted" and source["review_required"]
        assert source["text"] == unit["text"][source["start_char"]:source["end_char"]]
    assert before == {path: path.read_bytes() for path in library.root.rglob("*") if path.is_file()}
    assert library.get(OWNER, corpus["id"])["grounding_ready"] is False


@pytest.mark.parametrize("question", [
    "quasars", "Explain class", "Explain Java quantum chromodynamics", "please explain",
])
def test_unrelated_and_substring_queries_have_no_sources(course, question):
    _, corpus, retriever = course
    result = retriever.retrieve(OWNER, corpus["id"], question, previous_query="inheritance")
    assert result["status"] == "no_match" and result["sources"] == []


@pytest.mark.parametrize("query", ["kế thừa", "KE THUA", "KẾ THỪA"])
def test_vietnamese_accents_and_case_preserve_original_text(course, query):
    _, corpus, retriever = course
    result = retriever.retrieve(OWNER, corpus["id"], query)
    assert result["status"] == "matched"
    assert "Kế thừa" in result["sources"][0]["text"]


@pytest.mark.parametrize("query,expected", [("继承", "继承允许"), ("상속", "상속은")])
def test_cjk_and_hangul_terms_are_searchable(tmp_path, query, expected):
    _, corpus, retriever = imported(tmp_path, [("languages.docx", document(
        "继承允许子类重用父类的行为。", "상속은 자식 클래스가 부모 클래스의 기능을 사용하도록 합니다.",
    ))])
    result = retriever.retrieve(OWNER, corpus["id"], query)
    assert result["status"] == "matched" and expected in result["sources"][0]["text"]


@pytest.mark.parametrize("followup", [
    "Please explain more.", "Give me another example.", "Cho tôi thêm ví dụ.",
    "Giải thích phần vừa rồi đơn giản hơn, bằng một ví dụ gần gũi.",
    "Cho tôi thêm một ví dụ để hiểu phần vừa rồi.",
    "Explain this more simply, with a concrete example.",
    "Explain more in English.",
])
def test_topic_free_followups_reuse_only_explicit_anchor(course, followup):
    _, corpus, retriever = course
    assert is_followup(followup)
    result = retriever.retrieve(OWNER, corpus["id"], followup, previous_query="Explain inheritance")
    assert result["selection"] == "followup" and result["status"] == "matched"
    assert "inheritance" in result["sources"][0]["text"]
    unrelated = retriever.retrieve(OWNER, corpus["id"], "Explain quasars", previous_query="inheritance")
    assert unrelated["status"] == "no_match"


def test_new_topic_does_not_mix_previous_question(course):
    _, corpus, retriever = course
    result = retriever.retrieve(OWNER, corpus["id"], "virtual memory", previous_query="inheritance")
    assert result["status"] == "matched" and result["selection"] == "keyword"
    assert all(source["title"] == "systems/lecture.docx" for source in result["sources"])
    assert not is_followup("Give another example about quasars")


@pytest.mark.parametrize("query", ["Explain inheritance in English", "Explain inheritance. Answer in Chinese."])
def test_output_language_is_not_a_search_term(course, query):
    _, corpus, retriever = course
    result = retriever.retrieve(OWNER, corpus["id"], query)
    assert result["status"] == "matched"
    assert "inheritance" in result["sources"][0]["text"]


def test_exact_user_concept_alias_reuses_its_source_not_unrelated_units(tmp_path):
    library, corpus, retriever = imported(tmp_path, [("os.docx", document(
        "An interrupt service routine handles an interrupt.",
        "A semaphore coordinates access to shared resources.",
    ))])
    unit = corpus["units"][0]
    LearningKnowledgeGraph(library).set_concepts(OWNER, corpus["id"], unit["unit_id"], ["ISR"], 0)
    result = retriever.retrieve(OWNER, corpus["id"], "Explain ISR.")
    assert result["status"] == "matched" and result["selection"] == "concept_link"
    assert result["concept_link_origin"] == "user"
    assert [source["unit_id"] for source in result["sources"]] == [unit["unit_id"]]
    assert result["sources"][0]["text"] == unit["text"]
    assert retriever.retrieve(OWNER, corpus["id"], "ISR photosynthesis quantum")["status"] == "no_match"


def test_user_concept_alias_does_not_cross_collection(course):
    library, corpus, retriever = course
    unit = corpus["units"][0]
    LearningKnowledgeGraph(library).set_concepts(OWNER, corpus["id"], unit["unit_id"], ["Alias"], 0)
    other, _ = library.import_files(OWNER, "second-collection-0001", "Other", [("other.docx", document("Completely different content."))])
    assert retriever.retrieve(OWNER, other["id"], "Explain Alias.")["status"] == "no_match"


def test_concept_labels_preserve_distinct_punctuation(tmp_path):
    library, corpus, retriever = imported(tmp_path, [("languages.docx", document("First language.", "Second language."))])
    graph = LearningKnowledgeGraph(library)
    for unit, label in zip(corpus["units"], ("C++", "C#")):
        graph.set_concepts(OWNER, corpus["id"], unit["unit_id"], [label], 0)
        result = retriever.retrieve(OWNER, corpus["id"], "Explain " + label + ".")
        assert result["selection"] == "concept_link"
        assert [source["unit_id"] for source in result["sources"]] == [unit["unit_id"]]


def test_linked_long_unit_still_centers_excerpt_on_literal_match(tmp_path):
    text = "Unrelated filler. " * 700 + "Semaphore coordinates concurrent access."
    library, corpus, retriever = imported(tmp_path, [("os.docx", document(text))])
    unit = corpus["units"][0]
    LearningKnowledgeGraph(library).set_concepts(OWNER, corpus["id"], unit["unit_id"], ["Semaphore"], 0)
    result = retriever.retrieve(OWNER, corpus["id"], "Explain Semaphore.")
    assert result["selection"] == "concept_link"
    source = result["sources"][0]
    assert source["start_char"] > 10000 and "Semaphore" in source["text"]
    assert source["text"] == text[source["start_char"]:source["end_char"]]


def test_summary_is_explicitly_limited_and_samples_multiple_sources(course):
    _, corpus, retriever = course
    first = retriever.retrieve(OWNER, corpus["id"], "Tóm tắt bài giảng")
    assert first == retriever.retrieve(OWNER, corpus["id"], "Tóm tắt bài giảng")
    assert first["selection"] == "overview" and first["limited_context"]
    assert {source["title"] for source in first["sources"]} == {"java/lecture.docx", "systems/lecture.docx"}
    assert len(first["sources"]) <= 5


def test_excerpt_finds_late_hit_and_keeps_bounded_character_offsets(tmp_path):
    text = "Unrelated filler. " * 900 + "OVERRIDING determines the called method. " + "Trailing filler. " * 100
    _, corpus, retriever = imported(tmp_path, [("long.docx", document(text))])
    result = retriever.retrieve(OWNER, corpus["id"], "overriding")
    source = result["sources"][0]
    assert "OVERRIDING" in source["text"] and source["start_char"] > 10000
    assert len(source["text"]) <= 1600
    assert source["text"] == text[source["start_char"]:source["end_char"]]


def test_context_and_source_count_are_bounded_for_many_hits(tmp_path):
    _, corpus, retriever = imported(tmp_path, [("long.docx", document(*[
        "Inheritance " + (f"explanation{index} " * 200) for index in range(20)
    ]))])
    result = retriever.retrieve(OWNER, corpus["id"], "inheritance")
    assert len(result["sources"]) == 5
    assert sum(len(source["text"]) for source in result["sources"]) <= 8000
    assert all(len(source["text"]) <= 1600 for source in result["sources"])


def test_owner_and_collection_isolation_even_for_identical_source_bytes(course):
    library, corpus, retriever = course
    with pytest.raises(MaterialsError) as missing:
        retriever.retrieve(OTHER, corpus["id"], "inheritance")
    assert missing.value.code == "not_found"
    another, _ = library.import_files(OWNER, "retrieval-request-0002", "Other", [
        ("another.docx", document("Astronomy explains stars.")),
    ])
    assert retriever.retrieve(OWNER, another["id"], "inheritance")["status"] == "no_match"
    with pytest.raises(MaterialsError):
        retriever.retrieve("../escape", corpus["id"], "")


def test_image_notes_have_separate_origin_revision_and_exact_note_offsets(tmp_path):
    library, corpus, retriever = imported(tmp_path, [("diagram.png", picture())])
    assert retriever.retrieve(OWNER, corpus["id"], "inheritance")["status"] == "no_match"
    source_id = corpus["sources"][0]["source_id"]
    note = "Inheritance diagram: Cat extends Animal; arrows point to the parent."
    library.describe_image(OWNER, corpus["id"], source_id[7:], note, 0)
    result = retriever.retrieve(OWNER, corpus["id"], "inheritance")
    source = result["sources"][0]
    assert source["origin"] == "user_note" and source["annotation_revision"] == 1
    assert source["unit_id"] == corpus["units"][0]["unit_id"]
    assert source["locator"] == {"kind": "image", "index": 1}
    assert source["text"] == note[source["start_char"]:source["end_char"]]
    assert source["warnings"] and source["review_required"]
    updated = "Composition diagram: Car owns Engine."
    library.describe_image(OWNER, corpus["id"], source_id[7:], updated, 1)
    assert retriever.retrieve(OWNER, corpus["id"], "inheritance")["status"] == "no_match"
    changed = retriever.retrieve(OWNER, corpus["id"], "composition")["sources"][0]
    assert changed["annotation_revision"] == 2 and changed["text"] == updated
    assert source["text"] == note  # Previous evidence remains an independent snapshot.


def test_empty_documents_do_not_invent_summary_evidence(tmp_path):
    _, corpus, retriever = imported(tmp_path, [("empty.docx", document(""))])
    for query in ("summarize", "inheritance", ""):
        result = retriever.retrieve(OWNER, corpus["id"], query)
        assert result["status"] == "no_match" and not result["sources"]


@pytest.mark.parametrize("query", [None, 1, "a" * 8001, "bad\ud800text"])
def test_invalid_query_is_rejected_after_owner_check(course, query):
    _, corpus, retriever = course
    with pytest.raises(MaterialsError) as invalid:
        retriever.retrieve(OWNER, corpus["id"], query)
    assert invalid.value.code == "invalid_query"


def test_decomposed_unicode_in_query_matches_composed_source(course):
    _, corpus, retriever = course
    result = retriever.retrieve(OWNER, corpus["id"], unicodedata.normalize("NFD", "kế thừa"))
    assert result["status"] == "matched"


def test_decomposed_source_keeps_original_offsets(tmp_path):
    text = unicodedata.normalize("NFD", "Kế thừa giúp tái sử dụng hành vi.")
    _, corpus, retriever = imported(tmp_path, [("accents.docx", document(text))])
    source = retriever.retrieve(OWNER, corpus["id"], "kế thừa")["sources"][0]
    assert source["text"] == text[source["start_char"]:source["end_char"]]
