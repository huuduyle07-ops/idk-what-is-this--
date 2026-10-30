"""Lecture selection, retrieval and citation snapshots through the real HTTP gate."""
import copy
import uuid

import pytest

from tests.integration.test_learning_chat_web import chat, send, API
from tests.integration.test_learning_materials_web import BASE, page, upload, assert_error
from tests.learning.test_document_extractors import word, pdf, presentation


@pytest.fixture
def grounded(chat, tmp_path, monkeypatch):
    monkeypatch.setitem(chat.app.config, "TARGETED_SUBJECT_ROOT", tmp_path / "materials")
    chat.groundings = []
    chat.reply = "Inheritance gives subclasses behavior from a parent. [S1]"

    def respond(messages, *, grounding=None):
        chat.responder.calls.append(copy.deepcopy(messages))
        chat.groundings.append(copy.deepcopy(grounding))
        if chat.responder.error:
            raise chat.responder.error
        return chat.reply

    chat.responder.respond = respond
    return chat


def choose(client, csrf, collection_id=None, request_id=None):
    return client.post(API, base_url=BASE,
                       json={"request_id": request_id or uuid.uuid4().hex, "collection_id": collection_id},
                       headers={"Origin": BASE, "X-CSRF-Token": csrf})


def setup(state):
    client = state.app.test_client()
    csrf = page(client, "/learn/chat")
    collection = upload(client, csrf).get_json()["collection"]
    created = choose(client, csrf, collection["id"])
    assert created.status_code == 201, created.get_data(as_text=True)
    return client, csrf, collection, created.get_json()["conversation"]


def test_selected_lecture_retrieves_exact_excerpt_and_persists_citation_snapshot(grounded):
    client, csrf, collection, conversation = setup(grounded)
    assert conversation["collection"] == {"id": collection["id"], "title": collection["title"]}
    assert conversation["grounding"] == "materials" and not grounded.responder.calls
    rid = uuid.uuid4().hex
    response = send(client, csrf, conversation["id"], "Explain inheritance", request_id=rid)
    assert response.status_code == 200, response.get_data(as_text=True)
    view = response.get_json()["conversation"]
    evidence = view["messages"][-1]["evidence"]
    assert evidence["status"] == "matched" and evidence["cited_ids"] == ["S1"]
    assert evidence["invalid_citation_ids"] == []
    source = evidence["sources"][0]
    unit = collection["units"][0]
    assert source["unit_id"] == unit["unit_id"] and source["source_id"] == unit["source_id"]
    assert source["locator"] == unit["locator"]
    assert source["text"] == unit["text"][source["start_char"]:source["end_char"]]
    assert source["origin"] == "extracted" and source["review_required"] is True
    assert send(client, csrf, conversation["id"], "Explain inheritance", request_id=rid).get_json() == response.get_json()
    assert len(grounded.responder.calls) == 1
    assert client.get(f"{API}/{conversation['id']}", base_url=BASE).get_json() == response.get_json()
    assert client.get("/learn/api/materials/" + collection["id"], base_url=BASE).get_json()["collection"]["grounding_ready"] is False


def test_owner_cannot_select_foreign_collection_or_inject_excerpts(grounded):
    client, csrf, collection, conversation = setup(grounded)
    other = grounded.app.test_client()
    other_csrf = page(other, "/learn/chat")
    assert_error(choose(other, other_csrf, collection["id"]), 404)
    assert other.get(API, base_url=BASE).get_json()["conversations"] == []
    for body in (
        {"request_id": uuid.uuid4().hex, "collection_id": "../../private"},
        {"request_id": uuid.uuid4().hex, "sources": [{"text": "injected"}]},
    ):
        assert client.post(API, base_url=BASE, json=body,
                           headers={"Origin": BASE, "X-CSRF-Token": csrf}).status_code in {400, 404}
    assert_error(client.post(f"{API}/{conversation['id']}/messages", base_url=BASE,
                            json={"request_id": uuid.uuid4().hex, "text": "Inheritance", "expected_revision": 0,
                                  "collection_id": collection["id"]},
                            headers={"Origin": BASE, "X-CSRF-Token": csrf}), 400)
    assert not grounded.responder.calls


def test_general_chat_does_not_retrieve_and_scope_is_fixed_on_create_retry(grounded):
    client, csrf, collection, _ = setup(grounded)
    rid = uuid.uuid4().hex
    general = choose(client, csrf, request_id=rid).get_json()["conversation"]
    assert_error(choose(client, csrf, collection["id"], request_id=rid), 409)
    assert send(client, csrf, general["id"], "Explain inheritance").status_code == 200
    assert grounded.groundings == [None]


def test_unrelated_query_abstains_without_model_or_general_fallback(grounded):
    client, csrf, _, conversation = setup(grounded)
    result = send(client, csrf, conversation["id"], "Photosynthesis chlorophyll sunlight")
    assert result.status_code == 200
    answer = result.get_json()["conversation"]["messages"][-1]
    assert answer["evidence"]["status"] == "no_match" and answer["evidence"]["sources"] == []
    assert "couldn't find a relevant passage" in answer["content"] and answer["provider"] == "retrieval"
    assert not grounded.responder.calls


def test_citation_membership_does_not_fabricate_source_or_claim_verification(grounded):
    client, csrf, _, conversation = setup(grounded)
    grounded.reply = "Claim [S1]. Another claim [S999]. <script>alert(1)</script>"
    result = send(client, csrf, conversation["id"], "Explain inheritance").get_json()["conversation"]
    answer = result["messages"][-1]
    assert "[S999]" not in answer["content"]
    assert answer["evidence"]["cited_ids"] == ["S1"]
    assert answer["evidence"]["invalid_citation_ids"] == ["S999"]
    assert len(answer["evidence"]["sources"]) == 1
    assert "verified" not in answer["evidence"]


def test_old_sources_not_reused_as_current_citations_and_failure_is_not_retried(grounded):
    client, csrf, _, conversation = setup(grounded)
    cid = conversation["id"]
    assert send(client, csrf, cid, "Explain inheritance").status_code == 200
    assert send(client, csrf, cid, "Give an example", revision=2).status_code == 200
    assert "[S1]" not in grounded.responder.calls[-1][1]["content"]
    assert grounded.groundings[-1]["sources"]
    grounded.responder.error = RuntimeError("private lecture path /secret")
    rid = uuid.uuid4().hex
    failure = send(client, csrf, cid, "Inheritance", revision=4, request_id=rid)
    assert_error(failure, 502, "chat_provider_error")
    assert "/secret" not in failure.get_data(as_text=True)
    count = len(grounded.responder.calls)
    assert send(client, csrf, cid, "Inheritance", revision=4, request_id=rid).status_code == 200
    assert len(grounded.responder.calls) == count


def test_followup_anchor_survives_history_trimming_and_failed_questions(grounded):
    client, csrf, _, conversation = setup(grounded)
    cid = conversation["id"]
    grounded.reply = "a" * 23980 + " [S1]"
    assert send(client, csrf, cid, "Explain inheritance").status_code == 200
    assert send(client, csrf, cid, "Give an example", revision=2).status_code == 200
    assert send(client, csrf, cid, "Give another example", revision=4).status_code == 200
    assert grounded.groundings[-1]["status"] == "matched"
    assert grounded.groundings[-1]["sources"][0]["text"] == "Inheritance lesson"


@pytest.mark.parametrize("filename,content,query,locator", [
    ("reading.pdf", pdf(), "Last page", {"kind": "page", "index": 3}),
    ("slides.pptx", presentation(), "Second file", {"kind": "slide", "index": 1}),
    ("lecture.docx", word("<w:p><w:r><w:t>Dynamic dispatch chooses the override.</w:t></w:r></w:p>"),
     "Dynamic dispatch", {"kind": "paragraph", "index": 1}),
])
def test_real_document_formats_reach_chat_with_original_locator(grounded, filename, content, query, locator):
    client = grounded.app.test_client()
    csrf = page(client, "/learn/chat")
    collection = upload(client, csrf, paths=[filename], contents=[content]).get_json()["collection"]
    cid = choose(client, csrf, collection["id"]).get_json()["conversation"]["id"]
    result = send(client, csrf, cid, query)
    assert result.status_code == 200, result.get_data(as_text=True)
    source = result.get_json()["conversation"]["messages"][-1]["evidence"]["sources"][0]
    assert source["locator"] == locator and source["title"] == filename
