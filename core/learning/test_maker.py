"""Seeded authored tests with bounded arithmetic and explicit essay review.

No model, eval, execution tool or network is used. Version 1 content is frozen:
persisted tests are revalidated against the same seed and topic selection.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal, InvalidOperation
from fractions import Fraction
import json
import random
import re
import unicodedata

from .store import LearningError

VERSION = "test-maker-v1"
_DECIMAL = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]{1,2})?\Z")
_HEX = re.compile(r"[+]?0[xX][0-9a-fA-F]{1,12}\Z")
_TOPICS = (
    ("ml_mse", "Mean squared error", "Machine Learning", "numeric", "Calculate MSE from targets and predictions.", 2),
    ("ml_gini", "Gini impurity", "Machine Learning", "numeric", "Calculate impurity from class counts.", 2),
    ("ml_tpr", "True positive rate", "Machine Learning", "numeric", "Read a confusion matrix and calculate recall.", 2),
    ("os_paging", "Paging address translation", "Operating Systems", "numeric", "Translate a virtual byte address using a page table.", 2),
    ("la_matrix_product", "Matrix multiplication", "Linear Algebra", "matrix", "Multiply a 2 by 3 matrix by a 3 by 2 matrix.", 4),
    ("ml_training_diagram", "Training loop diagram", "Machine Learning", "diagram", "Complete a supervised gradient-descent training loop.", 4),
    ("os_producer_consumer_diagram", "Producer-consumer diagram", "Operating Systems", "diagram", "Complete a bounded-buffer semaphore protocol.", 4),
    ("os_deadlock", "Deadlock conditions", "Operating Systems", "essay", "Explain the Coffman conditions and one prevention approach.", 4),
    ("os_isr_semaphore", "ISR and semaphore", "Operating Systems", "essay", "Distinguish an ISR from a synchronization primitive.", 4),
    ("la_r3", "R3 and a subspace", "Linear Algebra", "essay", "Describe the ambient space, a subspace and their dimensions.", 4),
    ("ml_tree_criteria", "Decision-tree split criteria", "Machine Learning", "essay", "Distinguish entropy, information gain and Gini impurity.", 4),
)
_BY_TOPIC = {item[0]: item for item in _TOPICS}
_REFS = {
    "metrics": [{"title": "scikit-learn: model evaluation", "url": "https://scikit-learn.org/stable/modules/model_evaluation.html"}],
    "trees": [{"title": "scikit-learn: decision trees", "url": "https://scikit-learn.org/stable/modules/tree.html"}],
    "matrix": [{"title": "NumPy: matrix product", "url": "https://numpy.org/doc/stable/reference/generated/numpy.matmul.html"}],
    "paging": [{"title": "OSTEP: paging", "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/vm-paging.pdf"}],
    "semaphores": [{"title": "OSTEP: semaphores", "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-sema.pdf"}],
    "deadlock": [{"title": "OSTEP: concurrency bugs", "url": "https://pages.cs.wisc.edu/~remzi/OSTEP/threads-bugs.pdf"}],
    "isr": [{"title": "FreeRTOS: binary semaphores", "url": "https://github.freertos.org/Documentation/02-Kernel/02-Kernel-features/02-Queues-mutexes-and-semaphores/02-Binary-semaphores"}],
    "training": [{"title": "Google ML Crash Course: gradient descent", "url": "https://developers.google.com/machine-learning/crash-course/linear-regression/gradient-descent"}],
    "r3": [{"title": "MIT OpenCourseWare: subspaces", "url": "https://ocw.mit.edu/courses/18-06sc-linear-algebra-fall-2011/ca8b2f24428c3ab6c74757ae5ff5056b_MIT18_06SCF11_Ses1.13sum.pdf"}],
}


def _invalid():
    return LearningError("test_maker_invalid", "Test topics, seed or answer fields are invalid.", 400)


def catalog():
    return [dict(zip(("id", "title", "subject", "kind", "description", "points"), item)) for item in _TOPICS]


def _text(value, maximum):
    if (not isinstance(value, str) or len(value) > maximum
            or any(unicodedata.category(c) == "Cs" or (ord(c) < 32 and c not in "\n\r\t") for c in value)):
        raise _invalid()
    return value


def _ratio(value):
    return str(value.numerator) if value.denominator == 1 else f"{value.numerator}/{value.denominator}"


def _table(title, headers, rows):
    return {"title": title, "headers": headers, "rows": rows}


def _criterion(identifier, description, points=1):
    return {"id": identifier, "description": description, "points": points}


def _base(topic, index, prompt, data, input_, answer, explanation, rubric, reference):
    item = _BY_TOPIC[topic]
    return {"id": f"q{index + 1}", "topic_id": topic, "kind": item[3], "subject": item[2], "title": item[1],
            "prompt": prompt, "data": data, "input": input_, "points": item[5], "answer_key": answer,
            "explanation": explanation, "rubric": rubric, "references": deepcopy(_REFS[reference])}


def _numeric(topic, index, rng):
    input_ = {"format": "number", "allow_percent": topic == "ml_tpr", "placeholder": "Fraction or decimal, e.g. 1/4 or 0.2500"}
    if topic == "ml_mse":
        actual = [rng.randint(1, 9) for _ in range(5)]
        errors = [rng.choice([-2, -1, 0, 1, 2]) for _ in actual]
        if not any(errors):
            errors[0] = 1
        predicted = [value + error for value, error in zip(actual, errors)]
        squared = [error * error for error in errors]
        result = Fraction(sum(squared), len(actual))
        data = {"tables": [_table("Targets and predictions", ["Sample", "Actual y", "Prediction"],
                                  [[i + 1, a, p] for i, (a, p) in enumerate(zip(actual, predicted))])], "lines": []}
        prompt = "Compute mean squared error: MSE = (1/n) sum (prediction - actual)^2. Give a fraction or a decimal accurate to 4 decimal places."
        explanation = f"The squared errors are {squared}. Their sum is {sum(squared)}; divide by n={len(actual)} to obtain MSE={_ratio(result)}."
        reference = "metrics"
    elif topic == "ml_gini":
        counts = [rng.randint(2, 9) for _ in range(3)]
        total = sum(counts)
        result = 1 - sum((Fraction(count, total) ** 2 for count in counts), Fraction(0))
        data = {"tables": [_table("Class counts in one node", ["Class", "Count"], [[label, count] for label, count in zip("ABC", counts)])], "lines": []}
        prompt = "Compute this node's Gini impurity, G = 1 - sum p_k^2, using all three classes. Give a fraction or a decimal accurate to 4 decimal places."
        explanation = f"There are {total} samples. Use class probabilities {counts[0]}/{total}, {counts[1]}/{total}, {counts[2]}/{total}; Gini impurity is {_ratio(result)}."
        reference = "trees"
    elif topic == "ml_tpr":
        tp, fn, fp, tn = rng.randint(10, 60), rng.randint(5, 25), rng.randint(1, 20), rng.randint(20, 80)
        result = Fraction(tp, tp + fn)
        data = {"tables": [_table("Binary confusion matrix", ["Actual / Predicted", "Positive", "Negative"],
                                  [["Positive", tp, fn], ["Negative", fp, tn]])], "lines": ["Rows are actual classes. Columns are predicted classes."]}
        prompt = "Calculate true positive rate (recall for the positive class): TP/(TP+FN). A fraction, a decimal accurate to 4 places, or an explicit percentage with % is accepted."
        explanation = f"TP={tp} and FN={fn}; the denominator is actual positives, not predicted positives. TPR={tp}/({tp}+{fn})={_ratio(result)}."
        reference = "metrics"
    else:
        size = rng.choice([256, 512, 1024])
        frames = rng.sample(range(2, 31), 4)
        page, offset = rng.randrange(4), rng.randrange(size)
        virtual = page * size + offset
        result = Fraction(frames[page] * size + offset)
        data = {"tables": [_table("All listed page entries are valid", ["Virtual page", "Physical frame"], [[i, frame] for i, frame in enumerate(frames)])],
                "lines": [f"Page/frame size: {size} bytes.", f"Virtual byte address: {virtual} (0x{virtual:X})."]}
        input_ = {"format": "address", "allow_percent": False, "placeholder": "Physical byte address, decimal or 0x hexadecimal"}
        prompt = "Translate the given virtual byte address to a physical byte address using the page table. Pages and frames are numbered from zero. Return a decimal integer or a hexadecimal integer prefixed by 0x."
        explanation = f"Virtual page={virtual}//{size}={page}; offset={virtual}%{size}={offset}. Frame {frames[page]} gives physical address {frames[page]}*{size}+{offset}={result.numerator} (0x{result.numerator:X})."
        reference = "paging"
    return _base(topic, index, prompt, data, input_, {"value": _ratio(result), "tolerance": "0" if topic == "os_paging" else "1/10000"},
                 explanation, [_criterion("result", "Correct numeric result using the stated convention.", 2)], reference)


def _matrix(index, rng):
    a = [[rng.randint(-3, 5) for _ in range(3)] for _ in range(2)]
    b = [[rng.randint(-3, 5) for _ in range(2)] for _ in range(3)]
    result = [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(2)] for i in range(2)]
    data = {"tables": [_table("A (2 by 3)", ["", "c1", "c2", "c3"], [[f"r{i+1}", *row] for i, row in enumerate(a)]),
                        _table("B (3 by 2)", ["", "c1", "c2"], [[f"r{i+1}", *row] for i, row in enumerate(b)])], "lines": []}
    return _base("la_matrix_product", index, "Compute C = A B. Enter every entry of the resulting 2 by 2 matrix. Each entry earns one point.",
                 data, {"rows": 2, "cols": 2}, {"cells": [[str(value) for value in row] for row in result]},
                 "Each C[i,j] is the dot product of row i of A and column j of B, summing three products. Matrix multiplication is not elementwise multiplication.",
                 [_criterion(f"cell_{i+1}_{j+1}", f"Correct entry in row {i+1}, column {j+1}.") for i in range(2) for j in range(2)], "matrix")


def _diagram(topic, index):
    if topic == "ml_training_diagram":
        nodes = [{"id": "batch", "x": 20, "y": 35, "width": 150, "height": 75, "text": "Training batch (x, y)"}]
        positions = [(220, 35), (420, 35), (620, 35), (420, 245)]
        for i, (x, y) in enumerate(positions):
            nodes.append({"id": f"n{i+1}", "x": x, "y": y, "width": 150, "height": 75, "slot_id": f"slot{i+1}"})
        edges = [{"from": "batch", "to": "n1"}, {"from": "n1", "to": "n2", "label": "compare with y"},
                 {"from": "n2", "to": "n3"}, {"from": "n3", "to": "n4"}, {"from": "n4", "to": "n1", "label": "updated parameters"}]
        keys = {"slot1": ["Forward pass", "forward propagation", "predict", "prediction", "compute predictions"],
                "slot2": ["Compute loss", "loss", "loss calculation", "calculate loss", "loss function"],
                "slot3": ["Compute gradients", "gradients", "gradient calculation", "backpropagation", "back propagation"],
                "slot4": ["Update parameters", "parameter update", "update weights", "optimizer step", "gradient descent update"]}
        prompt = "Fill the four missing stages of this supervised gradient-descent training loop. The feedback arrow carries updated parameters into the next iteration. Use English labels."
        explanation = "Predictions come from a forward pass. Compare them with targets to compute loss, calculate parameter gradients, and use them to update parameters. Repeat with the updated parameters."
        reference = "training"
    else:
        nodes, edges, keys = [], [], {}
        for lane, y in enumerate((70, 250)):
            title = "Producer" if lane == 0 else "Consumer"
            nodes.append({"id": f"heading{lane}", "x": 20, "y": y - 45, "width": 140, "height": 30, "text": title})
            sequence = []
            for step, x in enumerate((20, 190, 360, 530, 700)):
                identifier = f"lane{lane}_n{step}"
                node = {"id": identifier, "x": x, "y": y, "width": 150, "height": 75}
                if step == 2:
                    node["text"] = "Insert item into buffer" if lane == 0 else "Remove item from buffer"
                else:
                    offset = step if step < 2 else step - 1
                    sid = f"slot{lane * 4 + offset + 1}"
                    node["slot_id"] = sid
                    operation, semaphore = (("wait", "empty"), ("wait", "mutex"), ("signal", "mutex"), ("signal", "full"))[offset] if lane == 0 else (("wait", "full"), ("wait", "mutex"), ("signal", "mutex"), ("signal", "empty"))[offset]
                    aliases = [f"wait({semaphore})", f"P({semaphore})", f"sem_wait({semaphore})", f"acquire({semaphore})"] if operation == "wait" else [f"signal({semaphore})", f"V({semaphore})", f"sem_post({semaphore})", f"release({semaphore})"]
                    keys[sid] = aliases
                nodes.append(node); sequence.append(identifier)
            edges.extend({"from": sequence[i], "to": sequence[i+1]} for i in range(4))
        prompt = "Complete both bounded-buffer semaphore protocols. Initially empty=N, full=0, mutex=1. Use wait(name) and signal(name), or equivalent P/V notation. The capacity wait must happen before acquiring mutex."
        explanation = "Producer: wait(empty), wait(mutex), insert, signal(mutex), signal(full). Consumer: wait(full), wait(mutex), remove, signal(mutex), signal(empty). Waiting for capacity/data while holding mutex can prevent the other side from making progress."
        reference = "semaphores"
    slots = [{"id": sid, "label": f"Step {i+1}"} for i, sid in enumerate(keys)]
    return _base(topic, index, prompt, {"width": 900, "height": 400, "nodes": nodes, "edges": edges}, {"slots": slots},
                 {"slots": keys}, explanation, [_criterion(sid, f"Correct label for {slots[i]['label']}.", 4 / len(keys)) for i, sid in enumerate(keys)], reference)


_ESSAYS = {
    "os_deadlock": (
        "Explain deadlock and the four Coffman necessary conditions. Explain why one condition alone does not establish deadlock, and give one way to prevent deadlock by breaking a condition.",
        "Deadlock is a set of participants waiting indefinitely for resources held by one another. In the classic reusable-resource model its four necessary conditions are mutual exclusion, hold and wait, no preemption, and circular wait. These are jointly necessary conditions, not four independent causes: one condition alone does not prove deadlock. A fixed global resource-acquisition order prevents circular wait; other prevention approaches deliberately break another condition.",
        [("definition_exclusion", "Accurate deadlock definition and mutual exclusion."), ("hold_wait", "Explains holding resources while waiting for more."),
         ("no_preemption", "Explains why resources cannot simply be taken away in the stated model."), ("cycle_prevention", "Explains circular wait and one prevention strategy that breaks a condition.")], "deadlock"),
    "os_isr_semaphore": (
        "Contrast an interrupt service routine (ISR) with a semaphore. In a FreeRTOS-like system, describe a safe ISR-to-task notification design and the constraints on calling kernel APIs in interrupt context.",
        "An ISR is code invoked to handle an interrupt; a semaphore is a synchronization primitive whose state coordinates activity between execution contexts. They play different roles and can be used together. In FreeRTOS an ISR can give a suitable semaphore using the documented FromISR API, such as xSemaphoreGiveFromISR, to unblock a task that performs deferred work. The ISR must not block waiting for a semaphore. Only APIs permitted for ISR context and the port's interrupt-priority rules are valid; ordinary task-context blocking calls are not interchangeable with FromISR calls. Keep interrupt handling short and perform longer work in the task.",
        [("isr", "Defines ISR as interrupt-handling code."), ("semaphore", "Defines semaphore and distinguishes synchronization from interrupt handling."),
         ("handoff", "Describes an ISR notifying a task through an appropriate FromISR API."), ("constraints", "States no blocking in ISR and platform/API/priority constraints.")], "isr"),
    "la_r3": (
        "Describe R^3 as a vector space over R and state its dimension. For W={(x,y,z) in R^3 : x+y+z=0}, decide whether W is a subspace, justify your answer, and give a basis and its dimension.",
        "R^3 is the vector space of ordered triples of real numbers, with componentwise addition and real scalar multiplication; its standard basis has three vectors, so its dimension is 3. W is a subspace because it is the kernel of the linear map (x,y,z) -> x+y+z: it contains zero and is closed under addition and scalar multiplication. One basis is {(1,-1,0),(1,0,-1)}. These vectors are independent and span W, so dim(W)=2; W is not all of R^3.",
        [("ambient", "Identifies real triples, the scalar field R and ambient dimension 3."), ("subspace", "Justifies zero/closure or the kernel argument."),
         ("basis", "Provides a valid independent spanning pair for W."), ("dimension", "Distinguishes dim(W)=2 from dim(R^3)=3.")], "r3"),
    "ml_tree_criteria": (
        "Distinguish entropy, information gain and Gini impurity for classification trees. Describe how child-node weights enter a split score. Must the entropy-based and Gini-based criteria rank every candidate split identically? Explain.",
        "Entropy H=-sum p_k log2(p_k), with 0 log 0 defined as 0, and Gini impurity G=1-sum p_k^2 both describe a node's class mixture. Information gain is a reduction: parent entropy minus the sample-count-weighted entropy of the children. For a fixed parent, choose the split with greatest gain, equivalently smallest weighted child entropy. A Gini-based split uses the corresponding weighted reduction in Gini impurity. Raw entropy is not itself information gain. Entropy and Gini use different functions, so they need not rank every candidate split identically.",
        [("entropy", "Gives an accurate entropy definition, including the zero-probability convention."), ("gini", "Gives the Gini impurity definition."),
         ("gain", "Defines information gain as parent minus weighted child entropy and explains selection."), ("comparison", "Distinguishes criteria and rejects a universal identical-ranking claim.")], "trees"),
}


def _essay(topic, index):
    prompt, answer, criteria, reference = _ESSAYS[topic]
    return _base(topic, index, prompt, {"tables": [], "lines": []}, {"max_length": 4000}, {"model_answer": answer},
                 "This answer needs human review against the criteria below. It is not automatically scored by matching keywords.",
                 [_criterion(identifier, description) for identifier, description in criteria], reference)


def build_test(topic_ids, seed):
    if (not isinstance(topic_ids, list) or not 1 <= len(topic_ids) <= len(_TOPICS)
            or any(not isinstance(topic, str) or topic not in _BY_TOPIC for topic in topic_ids)
            or len(set(topic_ids)) != len(topic_ids) or type(seed) is not int or not 0 <= seed <= 2**31 - 1):
        raise _invalid()
    selected = set(topic_ids)
    topic_ids = [item[0] for item in _TOPICS if item[0] in selected]
    rng = random.Random(seed)
    questions = []
    for index, topic in enumerate(topic_ids):
        kind = _BY_TOPIC[topic][3]
        if kind == "numeric": question = _numeric(topic, index, rng)
        elif kind == "matrix": question = _matrix(index, rng)
        elif kind == "diagram": question = _diagram(topic, index)
        else: question = _essay(topic, index)
        questions.append(question)
    return {"version": VERSION, "title": "Test Maker · ML, Operating Systems and Linear Algebra", "seed": seed,
            "topics": list(topic_ids), "questions": questions}


def validate_test(bundle):
    try:
        if not isinstance(bundle, dict) or set(bundle) != {"version", "title", "seed", "topics", "questions"} or bundle["version"] != VERSION:
            raise _invalid()
        expected = build_test(bundle["topics"], bundle["seed"])
        # Serialized comparison preserves numeric type distinctions such as
        # integer coordinates versus floats and true versus 1.
        supplied = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        if len(supplied.encode("utf-8")) > 128 * 1024 or supplied != json.dumps(expected, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False):
            raise _invalid()
        return deepcopy(expected)
    except (TypeError, ValueError, KeyError, UnicodeError, RecursionError):
        raise _invalid() from None


def public_question(question, include_solution=False):
    return deepcopy({key: value for key, value in question.items() if include_solution or key not in {"answer_key", "explanation", "rubric"}})


def validate_answer(question, answer, allow_empty=True):
    if answer is None:
        if allow_empty: return None
        raise _invalid()
    kind, input_ = question["kind"], question["input"]
    if kind in {"numeric", "essay"}:
        answer = _text(answer, 100 if kind == "numeric" else input_["max_length"])
        if not allow_empty and not answer.strip(): raise _invalid()
        return answer
    if kind == "matrix":
        if not isinstance(answer, list) or len(answer) != input_["rows"]:
            raise _invalid()
        if any(not isinstance(row, list) or len(row) != input_["cols"] for row in answer):
            raise _invalid()
        result = [[_text(cell, 100) for cell in row] for row in answer]
        if not allow_empty and not any(cell.strip() for row in result for cell in row): raise _invalid()
        return result
    if kind == "diagram":
        ids = [slot["id"] for slot in input_["slots"]]
        if not isinstance(answer, dict) or set(answer) - set(ids): raise _invalid()
        result = {sid: _text(answer.get(sid, ""), 120) for sid in ids}
        if not allow_empty and not any(text.strip() for text in result.values()): raise _invalid()
        return result
    raise _invalid()


def _number(value, *, allow_percent=False, allow_hex=False):
    """Parse only bounded numbers/fractions; never evaluate an expression."""
    if not isinstance(value, str) or not value.strip() or len(value) > 100:
        return None
    value = unicodedata.normalize("NFKC", value).strip()
    percent = value.endswith("%")
    if percent:
        if not allow_percent: return None
        value = value[:-1].strip()
    if allow_hex and _HEX.fullmatch(value):
        result = Fraction(int(value, 16))
    else:
        parts = value.split("/")
        if len(parts) > 2: return None
        numbers = []
        for part in parts:
            part = part.strip()
            if len(part) > 45 or not _DECIMAL.fullmatch(part): return None
            try:
                decimal = Decimal(part)
                if not decimal.is_finite() or abs(decimal) > 10**12 or decimal.as_tuple().exponent < -40 or decimal.as_tuple().exponent > 12:
                    return None
                numbers.append(Fraction(decimal))
            except (InvalidOperation, ValueError, OverflowError):
                return None
        if len(numbers) == 2 and numbers[1] == 0: return None
        result = numbers[0] if len(numbers) == 1 else numbers[0] / numbers[1]
    if percent: result /= 100
    return result if abs(result) <= 10**12 else None


def _label(value):
    return "".join(unicodedata.normalize("NFKC", value).split()).casefold()


def grade_question(question, answer):
    answer = validate_answer(question, answer)
    kind, key, points = question["kind"], question["answer_key"], question["points"]
    expected = key["value"] if kind == "numeric" else key["cells"] if kind == "matrix" else {sid: labels[0] for sid, labels in key["slots"].items()} if kind == "diagram" else key["model_answer"]
    result = {"question_id": question["id"], "status": "graded", "correct": False, "earned": 0, "possible": points,
              "feedback": "", "expected": deepcopy(expected), "explanation": question["explanation"], "rubric": deepcopy(question["rubric"])}
    empty = answer is None or (isinstance(answer, str) and not answer.strip()) or (isinstance(answer, list) and not any(cell.strip() for row in answer for cell in row)) or (isinstance(answer, dict) and not any(value.strip() for value in answer.values()))
    if empty:
        result.update(status="unanswered", correct=None, feedback="No answer submitted.")
        return result
    if kind == "essay":
        result.update(status="pending_review", correct=None, earned=None, feedback="Awaiting human review. Compare the response with the model answer and rubric; no automatic essay score was assigned.")
        return result
    if kind == "numeric":
        parsed = _number(answer, allow_percent=question["input"]["allow_percent"], allow_hex=question["input"]["format"] == "address")
        target, tolerance = Fraction(key["value"]), Fraction(key["tolerance"])
        correct = parsed is not None and abs(parsed - target) <= tolerance
        if question["input"]["format"] == "address": correct = correct and parsed.denominator == 1
        result.update(correct=correct, earned=points if correct else 0,
                      feedback="Correct numeric result." if correct else "The number does not match the expected result. Use a finite decimal/fraction, or the stated address/percentage format.")
    elif kind == "matrix":
        matched = sum(_number(answer[i][j]) == Fraction(key["cells"][i][j]) for i in range(question["input"]["rows"]) for j in range(question["input"]["cols"]))
        count = question["input"]["rows"] * question["input"]["cols"]
        result.update(correct=matched == count, earned=points * matched / count, feedback=f"{matched}/{count} matrix entries are correct.")
    else:
        matched = sum(_label(answer[sid]) in {_label(label) for label in labels} for sid, labels in key["slots"].items())
        count = len(key["slots"])
        result.update(correct=matched == count, earned=points * matched / count, feedback=f"{matched}/{count} diagram labels are correct.")
    return result
