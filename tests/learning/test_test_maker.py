"""Independent arithmetic, bounded input parsing and authored test contracts."""
from copy import deepcopy
from fractions import Fraction
import json

import pytest

from core.learning.store import LearningError
from core.learning.test_maker import (
    build_test, catalog, grade_question, public_question, validate_answer, validate_test,
)

NUMERIC = ["ml_mse", "ml_gini", "ml_tpr", "os_paging", "la_matrix_product"]


def question(topic, seed=17):
    return build_test([topic], seed)["questions"][0]


def test_catalog_has_all_eleven_topics_and_finite_point_budget():
    rows = catalog()
    assert len(rows) == len({row["id"] for row in rows}) == 11
    assert {row["kind"] for row in rows} == {"numeric", "matrix", "diagram", "essay"}
    assert sum(row["points"] for row in rows) == 36
    assert all(row["title"] and row["description"] and row["subject"] for row in rows)


def test_seed_reproduction_is_independent_of_selection_order_and_copies():
    first = build_test(NUMERIC, 17)
    assert first == build_test(list(reversed(NUMERIC)), 17)
    assert first != build_test(NUMERIC, 18)
    copied = validate_test(first)
    copied["questions"][0]["answer_key"]["value"] = "wrong"
    assert validate_test(first) == first


@pytest.mark.parametrize("topics,seed", [([], 1), (["unknown"], 1), (["ml_mse", "ml_mse"], 1),
                                       ("ml_mse", 1), (["ml_mse"], True), (["ml_mse"], -1),
                                       (["ml_mse"], 2**31), (["ml_mse"], 1.0), ([["ml_mse"]], 1)])
def test_invalid_test_selection_is_rejected(topics, seed):
    with pytest.raises(LearningError) as caught:
        build_test(topics, seed)
    assert caught.value.code == "test_maker_invalid"


def test_fixed_seed_math_matches_independently_worked_results():
    questions = build_test(NUMERIC, 17)["questions"]
    mse, gini, tpr, paging, matrix = questions
    # Errors: -1,2,0,-2,-2 => 13/5. Class counts 5,8,8 => 1-153/441.
    assert mse["data"]["tables"][0]["rows"] == [[1, 9, 8], [2, 7, 9], [3, 5, 5], [4, 6, 4], [5, 5, 3]]
    assert grade_question(mse, "2.6")["earned"] == 2
    assert grade_question(mse, "13/5")["correct"] is True
    assert grade_question(gini, "32/49")["correct"] is True
    # Actual positives are TP26+FN21, not TP26+FP11.
    assert grade_question(tpr, "26/47")["correct"] is True
    assert grade_question(tpr, "55.3191%")["correct"] is True
    assert grade_question(tpr, "26/37")["correct"] is False
    assert grade_question(tpr, "55.3191")["correct"] is False
    # Virtual286 is page0/offset286; frame25 *1024 +286 =25886=0x651E.
    assert grade_question(paging, "25886")["correct"] is True
    assert grade_question(paging, "0x651E")["correct"] is True
    assert grade_question(paging, "25886.5")["correct"] is False
    # [[0,-1,5],[5,0,2]] @ [[5,-2],[-2,1],[3,-2]].
    assert matrix["answer_key"]["cells"] == [["17", "-11"], ["31", "-14"]]
    assert grade_question(matrix, [["17", "-11"], ["31", "-14"]])["earned"] == 4
    assert grade_question(matrix, [["17", "-11"], ["wrong", ""]])["earned"] == 2


@pytest.mark.parametrize("seed", [0, 1, 19, 2147483647])
def test_generated_numeric_data_and_matrix_products_match_independent_calculations(seed):
    items = build_test(NUMERIC, seed)["questions"]
    rows = items[0]["data"]["tables"][0]["rows"]
    mse = sum(Fraction((predicted - actual) ** 2) for _, actual, predicted in rows) / len(rows)
    assert grade_question(items[0], str(mse))["correct"] is True
    counts = [row[1] for row in items[1]["data"]["tables"][0]["rows"]]
    total = sum(counts)
    gini = Fraction(total * total - sum(count * count for count in counts), total * total)
    assert grade_question(items[1], str(gini))["correct"] is True
    confusion = items[2]["data"]["tables"][0]["rows"]
    recall = Fraction(confusion[0][1], confusion[0][1] + confusion[0][2])
    assert grade_question(items[2], str(recall))["correct"] is True
    a, b = [table["rows"] for table in items[4]["data"]["tables"]]
    product = [[str(sum(a[i][k + 1] * b[k][j + 1] for k in range(3))) for j in range(2)] for i in range(2)]
    assert grade_question(items[4], product)["correct"] is True


@pytest.mark.parametrize("answer", ["nan", "NaN", "Infinity", "-inf", "1/0", "1e9999999999999", "1e99", "1e-99",
                                   "9" * 100, "2**1000000000", "1+1", "__import__('os').getcwd()", "1/2/3", "0x10", "10%"])
def test_malformed_or_unbounded_numeric_strings_are_saved_but_never_evaluated(answer):
    q = question("ml_mse")
    assert validate_answer(q, answer) == answer
    grade = grade_question(q, answer)
    assert grade["status"] == "graded" and grade["correct"] is False and grade["earned"] == 0


def test_numeric_rounding_tolerance_is_explicit_and_percent_is_topic_specific():
    q = question("ml_gini")
    value = Fraction(q["answer_key"]["value"])
    assert grade_question(q, f"{float(value):.4f}")["correct"] is True
    assert grade_question(q, str(value + Fraction(1, 1000)))["correct"] is False
    assert grade_question(q, str(float(value) * 100) + "%")["correct"] is False


def test_diagram_geometry_is_bounded_and_contains_no_semantic_answer_slot_ids():
    for topic in ["ml_training_diagram", "os_producer_consumer_diagram"]:
        q = question(topic)
        nodes, edges = q["data"]["nodes"], q["data"]["edges"]
        ids = {node["id"] for node in nodes}
        assert all(0 <= node["x"] < node["x"] + node["width"] <= q["data"]["width"] for node in nodes)
        assert all(0 <= node["y"] < node["y"] + node["height"] <= q["data"]["height"] for node in nodes)
        assert all(edge["from"] in ids and edge["to"] in ids for edge in edges)
        assert {node["slot_id"] for node in nodes if "slot_id" in node} == set(q["answer_key"]["slots"])
        assert all(slot["id"].startswith("slot") for slot in q["input"]["slots"])
        assert len(q["input"]["slots"]) <= 8


def test_training_diagram_label_aliases_and_partial_credit():
    q = question("ml_training_diagram")
    result = grade_question(q, {"slot1": " FORWARD propagation ", "slot2": "loss", "slot3": "unrelated"})
    assert result["earned"] == 2 and result["correct"] is False
    full = {sid: labels[0] for sid, labels in q["answer_key"]["slots"].items()}
    assert grade_question(q, full)["earned"] == 4


def test_producer_consumer_capacity_waits_precede_mutex_and_release_signals_follow():
    q = question("os_producer_consumer_diagram")
    expected = ["wait(empty)", "wait(mutex)", "signal(mutex)", "signal(full)",
                "wait(full)", "wait(mutex)", "signal(mutex)", "signal(empty)"]
    assert list(grade_question(q, {})["expected"].values()) == expected
    aliases = {f"slot{i+1}": value for i, value in enumerate(["P ( empty )", "p(mutex)", "V(mutex)", "v(full)",
                                                              "P(full)", "P(mutex)", "V(mutex)", "V(empty)"])}
    assert grade_question(q, aliases)["earned"] == 4
    aliases["slot1"], aliases["slot2"] = aliases["slot2"], aliases["slot1"]
    assert grade_question(q, aliases)["earned"] == 3


@pytest.mark.parametrize("topic", ["os_deadlock", "os_isr_semaphore", "la_r3", "ml_tree_criteria"])
def test_essays_are_not_automatically_keyword_scored(topic):
    q = question(topic)
    result = grade_question(q, "deadlock entropy R3 semaphore -- these keywords are not a reasoned answer")
    assert result["status"] == "pending_review" and result["earned"] is None and result["correct"] is None
    assert result["expected"] == q["answer_key"]["model_answer"]
    assert sum(c["points"] for c in result["rubric"]) == 4
    assert grade_question(q, " \n")["status"] == "unanswered"


def test_authored_essay_content_covers_critical_distinctions():
    assert "one condition alone does not prove" in question("os_deadlock")["answer_key"]["model_answer"]
    isr = question("os_isr_semaphore")["answer_key"]["model_answer"]
    assert "xSemaphoreGiveFromISR" in isr and "must not block" in isr and "priority" in isr
    r3 = question("la_r3")["answer_key"]["model_answer"]
    assert "dimension is 3" in r3 and "dim(W)=2" in r3
    tree = question("ml_tree_criteria")["answer_key"]["model_answer"]
    assert "sample-count-weighted" in tree and "need not rank" in tree


@pytest.mark.parametrize("topic,answer", [("ml_mse", 1), ("ml_mse", "x" * 101), ("ml_mse", "\ud800"),
                                         ("la_matrix_product", [["1"]]), ("la_matrix_product", [[1, ""], ["", ""]]),
                                         ("ml_training_diagram", {"unexpected": "label"}), ("os_deadlock", "x" * 4001)])
def test_invalid_answer_shapes_or_sizes_are_rejected(topic, answer):
    with pytest.raises(LearningError):
        validate_answer(question(topic), answer)


def test_no_answer_key_or_hidden_rubric_is_in_public_questions():
    bundle = build_test([row["id"] for row in catalog()], 7)
    for q in bundle["questions"]:
        view = public_question(q)
        assert not {"answer_key", "explanation", "rubric"} & view.keys()
        assert "answer_key" in public_question(q, include_solution=True)
        assert q["references"] and all(reference["url"].startswith("https://") for reference in q["references"])
    assert "answer_key" not in json.dumps([public_question(q) for q in bundle["questions"]])


@pytest.mark.parametrize("mutation", ["key", "coordinate", "float", "extra", "reference", "seed_bool"])
def test_persisted_test_tampering_is_rejected(mutation):
    bundle = build_test(["ml_mse", "ml_training_diagram"], 5)
    damaged = deepcopy(bundle)
    if mutation == "key": damaged["questions"][0]["answer_key"]["value"] = "999"
    elif mutation == "coordinate": damaged["questions"][1]["data"]["nodes"][0]["x"] = -1
    elif mutation == "float": damaged["questions"][0]["points"] = 2.0
    elif mutation == "extra": damaged["questions"][0]["script"] = "alert(1)"
    elif mutation == "reference": damaged["questions"][0]["references"][0]["url"] = "javascript:alert(1)"
    else: damaged["seed"] = True
    with pytest.raises(LearningError):
        validate_test(damaged)
    assert validate_test(bundle) == bundle
