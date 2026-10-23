"""Controlled pure SANDBOX.2/JAVA.1C predicate probes, never a live issuer.

Source expressions are extracted from the unchanged owners. Fixtures have no
runtime authority. Re-signing is restricted to fixtures in this process, and
no key or signature is written to the report. Run with Python -B.
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib
import inspect
import json
import os
import pickle
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_EFFECTS = {"python_domain_child": 0, "docker": 0, "java": 0,
            "caller_shell": 0, "socket": 0, "other_process": 0,
            "forbidden_attempts": 0}
_ALLOW_CHILD = False
_CHILD_COMMAND = [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                  "--domain-worker"]


def _audit(event, args):
    if event == "subprocess.Popen":
        argv = args[1]
        matches = argv == subprocess.list2cmdline(_CHILD_COMMAND) if isinstance(argv, str) else list(argv) == _CHILD_COMMAND
        if _ALLOW_CHILD and matches:
            _EFFECTS["python_domain_child"] += 1
            return
        _EFFECTS["forbidden_attempts"] += 1
        text = " ".join(map(str, argv)) if isinstance(argv, (tuple, list)) else str(argv)
        executable_name = Path(str(args[0])).name.lower()
        key = "docker" if executable_name in {"docker", "docker.exe"} else "java" if executable_name in {"java", "java.exe", "javac", "javac.exe"} else "other_process"
        _EFFECTS[key] += 1
        raise RuntimeError("pure_matrix_forbidden_process:" + key)
    if event in {"os.system", "os.posix_spawn", "os.spawn", "os.fork", "os.exec"}:
        _EFFECTS["forbidden_attempts"] += 1
        _EFFECTS["caller_shell"] += 1
        raise RuntimeError("pure_matrix_forbidden_shell_or_process")
    if event.startswith("socket."):
        _EFFECTS["forbidden_attempts"] += 1
        _EFFECTS["socket"] += 1
        raise RuntimeError("pure_matrix_forbidden_socket")
    if event == "open":
        path, mode, flags = args
        writing = (isinstance(mode, str) and any(c in mode for c in "wax+")) or (
            isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC))
        if writing and not isinstance(path, int):
            resolved = Path(path).resolve()
            if HERE != resolved and HERE not in resolved.parents:
                _EFFECTS["forbidden_attempts"] += 1
                raise RuntimeError("pure_matrix_write_outside_diagnostic")


if __name__ == "__main__":
    sys.addaudithook(_audit)

from core import sandboxed_java_positive_continuation as java1c

sandbox2 = java1c.sandbox2
baseline = java1c.baseline

_LABELS = {
    "sandbox2.validate_receipt": ("receipt_exact_type", "receipt_hmac"),
    "sandbox2.validate_descriptor": ("descriptor_exact_type", "descriptor_hmac",
        "descriptor_receipt_fingerprint", "descriptor_receipt_status",
        "descriptor_eligibility_equals_complete_status"),
    "sandbox2.validate_policy_bytes": ("baseline_policy_identity", "canonical_policy_exact_type",
        "canonical_policy_bytes", "canonical_policy_sha256"),
    "java1c.authenticate_sandbox2": ("descriptor_status_complete", "receipt_status_complete",
        "descriptor_java1_eligibility_is_true", "receipt_java1_classification",
        "receipt_cleanup_is_true", "receipt_full_ladder_passed",
        "descriptor_receipt_fingerprint_java1c", "descriptor_receipt_policy_equal",
        "receipt_policy_java1c", "canonical_policy_sha_java1c", "descriptor_image_java1c",
        "receipt_image_java1c", "all_authorities_false"),
    "java1c._obtain_live_sandbox2": ("live_descriptor_fingerprint", "live_receipt_fingerprint",
        "live_receipt_evidence_digest", "live_cleanup_is_true"),
}

_INPUTS = {
    "receipt_exact_type": ("type_identity", ["type(receipt)"], "SANDBOX.2 receipt class"),
    "receipt_hmac": ("HMAC_signature_process_local", ["receipt._signature", "_sign(receipt)"], "SANDBOX.2 issuer"),
    "descriptor_exact_type": ("type_identity", ["type(descriptor)"], "SANDBOX.2 descriptor class"),
    "descriptor_hmac": ("HMAC_signature_process_local", ["descriptor._signature", "_sign(descriptor)"], "SANDBOX.2 issuer"),
    "descriptor_receipt_fingerprint": ("receipt_fingerprint_binding", ["descriptor.verification_receipt_fingerprint", "receipt.fingerprint"], "SANDBOX.2 pair"),
    "descriptor_receipt_status": ("status_binding", ["descriptor.status", "receipt.status"], "SANDBOX.2 pair"),
    "descriptor_eligibility_equals_complete_status": ("semantic_eligibility_binding", ["descriptor.eligible_for_java1_continuation", "receipt.status", "sandbox2.COMPLETE"], "SANDBOX.2 pair"),
    "baseline_policy_identity": ("policy_SHA", ["baseline._SECCOMP", "BASELINE_POLICY_SHA256"], "SANDBOX.1 baseline and SANDBOX.2 pin"),
    "canonical_policy_exact_type": ("type_identity", ["type(raw)"], "SANDBOX.2 canonical policy bytes"),
    "canonical_policy_bytes": ("policy_bytes", ["raw", "baseline._json(expected).encode()"], "SANDBOX.2 additive policy"),
    "canonical_policy_sha256": ("policy_SHA", ["sha256(raw).hexdigest()", "POLICY_SHA256"], "SANDBOX.2 additive policy"),
    "descriptor_status_complete": ("semantic_completion", ["descriptor.status", "sandbox2.COMPLETE"], "SANDBOX.2 descriptor; JAVA.1C acceptance"),
    "receipt_status_complete": ("semantic_completion", ["receipt.status", "sandbox2.COMPLETE"], "SANDBOX.2 receipt; JAVA.1C acceptance"),
    "descriptor_java1_eligibility_is_true": ("semantic_eligibility_exact_boolean", ["descriptor.eligible_for_java1_continuation"], "SANDBOX.2 descriptor; JAVA.1C acceptance"),
    "receipt_java1_classification": ("semantic_eligibility_classification", ["receipt.compatibility_classification"], "SANDBOX.2 receipt; JAVA.1C acceptance"),
    "receipt_cleanup_is_true": ("cleanup_exact_boolean", ["receipt.cleanup_verified"], "SANDBOX.2 receipt; JAVA.1C acceptance"),
    "receipt_full_ladder_passed": ("semantic_stage_results", ["receipt.stage_results", "sandbox2.LADDER", "sandbox2.PASSED"], "SANDBOX.2 fixed verification ladder"),
    "descriptor_receipt_fingerprint_java1c": ("receipt_fingerprint_binding", ["descriptor.verification_receipt_fingerprint", "receipt.fingerprint"], "SANDBOX.2 pair; JAVA.1C acceptance"),
    "descriptor_receipt_policy_equal": ("policy_SHA_binding", ["descriptor.seccomp_policy_sha256", "receipt.seccomp_policy_sha256"], "SANDBOX.2 pair"),
    "receipt_policy_java1c": ("policy_SHA", ["receipt.seccomp_policy_sha256", "java1c.POLICY_SHA256"], "SANDBOX.2 receipt and JAVA.1C pin"),
    "canonical_policy_sha_java1c": ("policy_SHA", ["sandbox2.POLICY_SHA256", "java1c.POLICY_SHA256"], "SANDBOX.2 policy constant and JAVA.1C pin"),
    "descriptor_image_java1c": ("image_identity", ["descriptor.image_identity", "java1c.IMAGE"], "SANDBOX.2 descriptor and JAVA.1C image pin"),
    "receipt_image_java1c": ("image_identity", ["receipt.image_identity", "java1c.IMAGE"], "SANDBOX.2 receipt and JAVA.1C image pin"),
    "all_authorities_false": ("authority_exact_false", ["descriptor/receipt." + k for k in sandbox2.AUTHORITIES], "SANDBOX.2 pair; JAVA.1C acceptance"),
    "live_descriptor_fingerprint": ("descriptor_fingerprint", ["live['descriptor']['sandbox_descriptor_fingerprint']", "descriptor.fingerprint"], "SANDBOX.2 replay report and reconstructed issuer descriptor"),
    "live_receipt_fingerprint": ("receipt_fingerprint", ["live['verification_receipt']['verification_receipt_fingerprint']", "receipt.fingerprint"], "SANDBOX.2 replay report and reconstructed issuer receipt"),
    "live_receipt_evidence_digest": ("evidence_digest", ["receipt.evidence_sha256", "baseline._hash(live['stages'])"], "SANDBOX.2 measured stages and issuer receipt"),
    "live_cleanup_is_true": ("cleanup_exact_boolean", ["live['cleanup_verified']"], "SANDBOX.2 replay report"),
}


def _rejection_terms(function):
    source = inspect.getsource(function)
    tree = ast.parse(source)
    terms = []
    for node in tree.body[0].body:
        if isinstance(node, ast.If) and any(isinstance(n, ast.Raise) for n in node.body):
            error = next(n for n in node.body if isinstance(n, ast.Raise))
            reason = ast.literal_eval(error.exc.args[0])
            values = node.test.values if isinstance(node.test, ast.BoolOp) and isinstance(node.test.op, ast.Or) else [node.test]
            for value in values:
                terms.append((value, reason))
    return tree, terms


def _build_checks():
    output = []
    groups = (("sandbox2.validate_receipt", sandbox2.validate_receipt),
              ("sandbox2.validate_descriptor", sandbox2.validate_descriptor),
              ("sandbox2.validate_policy_bytes", sandbox2.validate_policy_bytes),
              ("java1c.authenticate_sandbox2", java1c.authenticate_sandbox2),
              ("java1c._obtain_live_sandbox2", java1c._obtain_live_sandbox2))
    for group, function in groups:
        tree, terms = _rejection_terms(function)
        if len(terms) != len(_LABELS[group]):
            raise AssertionError("frozen_predicate_shape_changed:" + group)
        for label, (expression, error) in zip(_LABELS[group], terms):
            category, inputs, field_owner = _INPUTS[label]
            output.append({"predicate": label, "component": group,
                "check_category": category, "fields_inputs_consumed": inputs,
                "field_owner": field_owner,
                "rejection_expression": ast.unparse(expression), "error": error,
                "source": str(Path(inspect.getsourcefile(function)).resolve()),
                "line": inspect.getsourcelines(function)[1] + expression.lineno - 1,
                "_expression": compile(ast.Expression(expression), "<frozen-" + label + ">", "eval"),
                "_globals": function.__globals__})
            if label == "all_authorities_false":
                output[-1]["ordered_authority_subpredicates"] = [
                    {"object": object_name, "field": key,
                     "rejection_expression": object_name + "." + key + " is not False",
                     "field_owner": "SANDBOX.2 " + object_name,
                     "check_category": "authority_exact_false"}
                    for object_name in ("descriptor", "receipt") for key in sandbox2.AUTHORITIES]
    return output


_CHECKS = _build_checks()


def predicate_ledger():
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in _CHECKS]


def _policy_expected():
    # Execute ONLY the actual frozen local preparation statements. This creates
    # an independent deepcopy; the baseline policy is never altered.
    tree, _ = _rejection_terms(sandbox2.validate_policy_bytes)
    statements = [node for node in tree.body[0].body if isinstance(node, (ast.Assign, ast.Expr))]
    namespace = {}
    exec(compile(ast.Module(statements, []), "<frozen-policy-locals>", "exec"),
         sandbox2.validate_policy_bytes.__globals__, namespace)
    return namespace["expected"]


def _public_call(function, *args):
    try:
        result = function(*args)
        return {"state": "PASS", "error": None,
                "original_arguments_returned": result is args[0] if len(args) == 1 else (
                    isinstance(result, tuple) and all(a is b for a, b in zip(result, args))
                    if function is java1c.authenticate_sandbox2 else result is args[0])}
    except (ValueError, TypeError, AttributeError, KeyError) as error:
        return {"state": "FAIL", "error": type(error).__name__ + ": " + str(error)}


def decompose_pair(descriptor, receipt, live=None):
    """Read original supplied objects; never reconstruct, mutate, or issue.

    The ordered ledger preserves the real short circuit order. Public calls
    are independent, read-only cross checks; they do not turn NOT_REACHED rows
    into reached rows. HMAC is observable separately only at its actual gate.
    """
    local = {"descriptor": descriptor, "receipt": receipt, "raw": sandbox2.POLICY_BYTES,
             "expected": _policy_expected(), "live": live}
    rows, failed = [], False
    for check in _CHECKS:
        row = {k: v for k, v in check.items() if not k.startswith("_")}
        if failed or (live is None and check["component"] == "java1c._obtain_live_sandbox2"):
            row["state"] = "NOT_REACHED"
        else:
            rejected = bool(eval(check["_expression"], check["_globals"], local))
            row["state"] = "FAIL" if rejected else "PASS"
            failed = rejected
        rows.append(row)
    first = next((row for row in rows if row["state"] == "FAIL"), None)
    hmac = {name: next(r["state"] for r in rows if r["predicate"] == name)
            for name in ("receipt_hmac", "descriptor_hmac")}
    public = {"sandbox_receipt": _public_call(sandbox2.validate_receipt, receipt),
              "sandbox_descriptor": _public_call(sandbox2.validate_descriptor, descriptor, receipt),
              "sandbox_policy": _public_call(sandbox2.validate_policy_bytes, sandbox2.POLICY_BYTES),
              "java1c_authenticate_sandbox2": _public_call(java1c.authenticate_sandbox2, descriptor, receipt)}
    return {"passed": first is None, "first_failing_predicate": first["predicate"] if first else None,
            "first_failure_error": first["error"] if first else None,
            "ordered_predicates": rows, "hmac_results": hmac,
            "demonstrated_HMAC_failure": any(value == "FAIL" for value in hmac.values()),
            "public_validations": public,
            "not_reached_predicates": [r["predicate"] for r in rows if r["state"] == "NOT_REACHED"]}


def fixture(tag="original"):
    stages = [{"mode": mode, "verdict": sandbox2.PASSED, "controlled_fixture": tag}
              for mode in sandbox2.LADDER]
    result = {"status": sandbox2.COMPLETE, "stages": stages, "cleanup_verified": True}
    descriptor, receipt = sandbox2._evidence_pair(result)
    result["descriptor"], result["verification_receipt"] = descriptor.as_dict(), receipt.as_dict()
    return descriptor, receipt, result


def _set(value, fields, resign):
    changed = copy.deepcopy(value)
    for key, item in fields.items():
        object.__setattr__(changed, key, item)
    if resign:
        object.__setattr__(changed, "_signature", sandbox2._sign(changed))
    return changed


def mutate_pair(descriptor, receipt, descriptor_fields=None, receipt_fields=None, resign=True,
                rebind=True):
    """Fixture-only mutation; never called with captured live owner objects."""
    if receipt_fields:
        receipt = _set(receipt, receipt_fields, resign)
        if rebind:
            descriptor_fields = {"verification_receipt_fingerprint": receipt.fingerprint,
                                 **(descriptor_fields or {})}
    if descriptor_fields:
        descriptor = _set(descriptor, descriptor_fields, resign)
    return descriptor, receipt


def _isolated_probe(name, descriptor, receipt, live, overrides=None, raw=None):
    check = next(row for row in _CHECKS if row["predicate"] == name)
    globals_copy = dict(check["_globals"])
    globals_copy.update(overrides or {})
    rejected = bool(eval(check["_expression"], globals_copy,
        {"descriptor": descriptor, "receipt": receipt, "live": live,
         "raw": sandbox2.POLICY_BYTES if raw is None else raw, "expected": _policy_expected()}))
    return {"predicate": name, "rejection_expression_true": rejected,
            "mode": "isolated_frozen_AST_expression_on_controlled_fixture",
            "owner_globals_mutated": False}


def _function_state():
    return {(module.__name__, name): id(value)
            for module in (sandbox2, java1c, baseline)
            for name, value in vars(module).items() if inspect.isfunction(value)}


def run_matrix():
    before = _function_state()
    source_hashes = {str(Path(m.__file__).resolve()): hashlib.sha256(Path(m.__file__).read_bytes()).hexdigest()
                     for m in (sandbox2, java1c)}
    cases, coverage = [], set()

    def case(name, *, df=None, rf=None, resign=True, rebind=True,
             transform=None, live_transform=None, expected=None, targets=()):
        original_d, original_r, live = fixture(name)
        d, r = mutate_pair(original_d, original_r, df, rf, resign, rebind)
        if transform:
            d, r = transform(d, r)
        if live_transform:
            live_transform(live)
        result = decompose_pair(d, r, live)
        error = result["first_failure_error"]
        if error != expected:
            raise AssertionError((name, expected, error, result["first_failing_predicate"]))
        probes = [_isolated_probe(target, d, r, live) for target in targets]
        if not all(probe["rejection_expression_true"] for probe in probes):
            raise AssertionError((name, "isolated_expression_did_not_reject", probes))
        coverage.update(targets)
        cases.append({"case": name, "expectation_passed": True,
            "expected_error": expected, "descriptor_is_fixture_original": d is original_d,
            "receipt_is_fixture_original": r is original_r,
            "fixture_resigned": resign and bool(df or rf),
            "isolated_target_probes": probes, **result})

    unauth_r = "sandbox2_receipt_unauthenticated"
    unauth_d = "sandbox2_descriptor_unauthenticated"
    semantic = "java1c_live_sandbox2_binding_rejected"
    postauth = "java1c_live_sandbox2_fingerprint_mismatch"
    case("valid_original_pair")
    case("descriptor_shallow_copy", transform=lambda d, r: (copy.copy(d), r))
    case("receipt_shallow_copy", transform=lambda d, r: (d, copy.copy(r)))
    case("same_values_nonoriginal_deepcopy", transform=lambda d, r: (copy.deepcopy(d), copy.deepcopy(r)))
    case("wrong_pairing", transform=lambda d, r: (d, fixture("different_pair")[1]), expected=unauth_d,
         targets=("descriptor_receipt_fingerprint", "descriptor_receipt_fingerprint_java1c"))
    case("wrong_exact_descriptor_type", transform=lambda d, r: (SimpleNamespace(**d.as_dict()), r),
         expected=unauth_d, targets=("descriptor_exact_type",))
    case("wrong_exact_receipt_type", transform=lambda d, r: (d, SimpleNamespace(**r.as_dict())),
         expected=unauth_r, targets=("receipt_exact_type",))
    case("unsigned_receipt", rf={"_signature": ""}, resign=False, expected=unauth_r,
         targets=("receipt_hmac",))
    case("wrong_receipt_hmac", rf={"_signature": "0" * 64}, resign=False, expected=unauth_r,
         targets=("receipt_hmac",))
    case("unsigned_descriptor", df={"_signature": ""}, resign=False, expected=unauth_d,
         targets=("descriptor_hmac",))
    case("wrong_descriptor_hmac", df={"_signature": "0" * 64}, resign=False, expected=unauth_d,
         targets=("descriptor_hmac",))
    for obj, key in (("descriptor", "phase_id"), ("descriptor", "schema_version"),
                     ("receipt", "phase_id"), ("receipt", "schema_version")):
        changes = {"df" if obj == "descriptor" else "rf": {key: "wrong_epoch"}}
        case("wrong_" + obj + "_" + key + "_unsigned", **changes, resign=False,
             expected=unauth_d if obj == "descriptor" else unauth_r)
        # A re-signed phase/schema semantic change is actually accepted. Bind
        # the exported fixture report after changing its nonchecked values.
        d, r, live = fixture("phase_schema")
        d, r = mutate_pair(d, r, **({"descriptor_fields": {key: "wrong_epoch"}}
                                  if obj == "descriptor" else {"receipt_fields": {key: "wrong_epoch"}}))
        live["descriptor"], live["verification_receipt"] = d.as_dict(), r.as_dict()
        result = decompose_pair(d, r, live)
        assert result["passed"]
        cases.append({"case": "wrong_" + obj + "_" + key + "_resigned_semantic_probe",
                      "expectation_passed": True, "expected_error": None,
                      "fixture_resigned": True, **result})
    case("descriptor_status_disagrees", df={"status": sandbox2.UNRESOLVED}, expected=unauth_d,
         targets=("descriptor_receipt_status", "descriptor_status_complete"))
    case("descriptor_eligibility_false", df={"eligible_for_java1_continuation": False}, expected=unauth_d,
         targets=("descriptor_eligibility_equals_complete_status", "descriptor_java1_eligibility_is_true"))
    case("descriptor_eligibility_integer_one", df={"eligible_for_java1_continuation": 1}, expected=semantic,
         targets=("descriptor_java1_eligibility_is_true",))
    case("owner_valid_blocked_pair", df={"status": sandbox2.UNRESOLVED,
         "eligible_for_java1_continuation": False}, rf={"status": sandbox2.UNRESOLVED}, expected=semantic,
         targets=("descriptor_status_complete", "receipt_status_complete", "descriptor_java1_eligibility_is_true"))
    case("classification_ineligible", rf={"compatibility_classification": "blocked_no_java_capability"},
         expected=semantic, targets=("receipt_java1_classification",))
    case("cleanup_false", rf={"cleanup_verified": False}, expected=semantic,
         targets=("receipt_cleanup_is_true",))
    case("stage_verdict_failed", rf={"stage_results": tuple((m, "failed") for m in sandbox2.LADDER)},
         expected=semantic, targets=("receipt_full_ladder_passed",))
    case("stage_order_wrong", rf={"stage_results": tuple((m, sandbox2.PASSED) for m in reversed(sandbox2.LADDER))},
         expected=semantic, targets=("receipt_full_ladder_passed",))
    case("receipt_fingerprint_binding_changed", df={"verification_receipt_fingerprint": "0" * 64},
         expected=unauth_d, targets=("descriptor_receipt_fingerprint", "descriptor_receipt_fingerprint_java1c"))
    case("descriptor_policy_wrong", df={"seccomp_policy_sha256": "0" * 64}, expected=semantic,
         targets=("descriptor_receipt_policy_equal",))
    case("receipt_policy_wrong", rf={"seccomp_policy_sha256": "0" * 64}, expected=semantic,
         targets=("descriptor_receipt_policy_equal", "receipt_policy_java1c"))
    case("both_policies_wrong", df={"seccomp_policy_sha256": "0" * 64},
         rf={"seccomp_policy_sha256": "0" * 64}, expected=semantic, targets=("receipt_policy_java1c",))
    case("descriptor_image_wrong", df={"image_identity": "sha256:" + "0" * 64}, expected=semantic,
         targets=("descriptor_image_java1c",))
    case("receipt_image_wrong", rf={"image_identity": "sha256:" + "0" * 64}, expected=semantic,
         targets=("receipt_image_java1c",))
    case("evidence_digest_changed_unsigned", rf={"evidence_sha256": "0" * 64}, resign=False, expected=unauth_r)
    case("evidence_digest_changed_resigned", rf={"evidence_sha256": "0" * 64}, expected=postauth,
         # Re-bind the report fingerprints to isolate the actual digest gate.
         live_transform=lambda live: None)
    # The preceding case must first encounter the report fingerprint changed
    # by re-signing. A dedicated report update below isolates its digest gate.
    d, r, live = fixture("digest_isolated")
    d, r = mutate_pair(d, r, receipt_fields={"evidence_sha256": "0" * 64})
    live["descriptor"], live["verification_receipt"] = d.as_dict(), r.as_dict()
    digest = decompose_pair(d, r, live)
    assert digest["first_failing_predicate"] == "live_receipt_evidence_digest"
    coverage.add("live_receipt_evidence_digest")
    cases.append({"case": "evidence_digest_changed_resigned_report_rebound", "expectation_passed": True,
                  "expected_error": postauth, "fixture_resigned": True,
                  "isolated_target_probes": [_isolated_probe("live_receipt_evidence_digest", d, r, live)], **digest})
    case("live_descriptor_fingerprint_changed",
         live_transform=lambda live: live["descriptor"].update(sandbox_descriptor_fingerprint="0" * 64),
         expected=postauth, targets=("live_descriptor_fingerprint",))
    case("live_receipt_fingerprint_changed",
         live_transform=lambda live: live["verification_receipt"].update(verification_receipt_fingerprint="0" * 64),
         expected=postauth, targets=("live_receipt_fingerprint",))
    case("live_stages_changed_after_pair", live_transform=lambda live: live["stages"][0].update(controlled_fixture="changed"),
         expected=postauth, targets=("live_receipt_evidence_digest",))
    case("live_cleanup_false", live_transform=lambda live: live.update(cleanup_verified=False),
         expected=postauth, targets=("live_cleanup_is_true",))
    for object_name in ("descriptor", "receipt"):
        for key in sandbox2.AUTHORITIES:
            case(object_name + "_authority_true_" + key,
                 **({"df": {key: True}} if object_name == "descriptor" else {"rf": {key: True}}),
                 expected=semantic, targets=("all_authorities_false",))

    d, r, live = fixture("isolated_policy")
    isolated = []
    baseline_proxy = SimpleNamespace(_SECCOMP={"controlled_fixture": "wrong_baseline"}, _hash=baseline._hash)
    sandbox_proxy = SimpleNamespace(POLICY_SHA256="0" * 64)
    for name, overrides, raw in (("baseline_policy_identity", {"baseline": baseline_proxy}, None),
                                  ("canonical_policy_exact_type", None, bytearray(sandbox2.POLICY_BYTES)),
                                  ("canonical_policy_bytes", None, b"{}"),
                                  ("canonical_policy_sha256", None, b"{}"),
                                  ("canonical_policy_sha_java1c", {"sandbox2": sandbox_proxy}, None)):
        probe = _isolated_probe(name, d, r, live, overrides, raw)
        assert probe["rejection_expression_true"]
        coverage.add(name)
        isolated.append(probe)
    for raw, label in ((bytearray(sandbox2.POLICY_BYTES), "wrong_policy_type"),
                       (b"{}", "wrong_policy_bytes")):
        outcome = _public_call(sandbox2.validate_policy_bytes, raw)
        assert outcome["error"] == "ValueError: exact_sandbox2_canonical_policy_required"
        cases.append({"case": label, "expectation_passed": True, "public_policy_validation": outcome})

    # Serialize originals only to a fresh Python domain for the explicit wrong
    # process test. No live objects are serialized or reconstructed here.
    global _ALLOW_CHILD
    d, r, live = fixture("wrong_process")
    _ALLOW_CHILD = True
    try:
        child = subprocess.run(_CHILD_COMMAND, input=pickle.dumps((d, r, live)),
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30,
                               shell=False, check=False)
    finally:
        _ALLOW_CHILD = False
    if child.returncode:
        raise AssertionError(("wrong_process_worker_failed", child.returncode, child.stderr.decode()))
    result = json.loads(child.stdout)
    assert result["decomposition"]["first_failing_predicate"] == "receipt_hmac"
    assert result["pid"] != os.getpid()
    cases.append({"case": "wrong_process_original_fixture_pair", "expectation_passed": True,
                  "issuing_process_pid": os.getpid(), "validation_process_pid": result["pid"],
                  "serialized_only_controlled_original_fixture": True,
                  "worker_stderr": child.stderr.decode(errors="replace"), **result["decomposition"]})
    all_predicates = {row["predicate"] for row in _CHECKS}
    assert coverage == all_predicates, ("missing_predicate_coverage", all_predicates - coverage)
    owner_unchanged = before == _function_state() and all(
        hashlib.sha256(Path(path).read_bytes()).hexdigest() == digest for path, digest in source_hashes.items())
    assert owner_unchanged
    assert _EFFECTS == {"python_domain_child": 1, "docker": 0, "java": 0,
        "caller_shell": 0, "socket": 0, "other_process": 0, "forbidden_attempts": 0}
    return {"phase_id": "RUNTIME.JAVA.1C.AUTH.DIAG.1", "passed": True,
        "case_count": len(cases), "cases": cases, "isolated_policy_probes": isolated,
        "predicate_ledger": predicate_ledger(), "all_rejection_terms_covered": True,
        "effect_counts": dict(_EFFECTS), "owner_functions_unchanged": owner_unchanged,
        "owner_sources_sha256": source_hashes, "fixture_only_signing": True,
        "secret_keys_or_signatures_exported": False, "live_owner_calls": 0,
        "not_applicable": {"object_original_identity": "No object identity gate in frozen owners; signed copies pass.",
          "live_registry_membership": "No SANDBOX.2 registry or public registry validator exists.",
          "issuing_pid_field": "No issuing PID field or explicit PID gate exists; process-local HMAC rejects the fresh child.",
          "phase_schema_semantic_gate": "No independent phase/schema gate; unsigned changes fail HMAC, controlled re-signed changes pass."},
        "generic_outer_status_mapping": {"sandbox_owner_authentication_errors": "not_authenticated",
          "java1c_semantic_binding_rejection": "not_authenticated",
          "postauth_fingerprint_digest_cleanup_rejection": "not_authenticated",
          "meaning": "Frozen verify initializes the same outer status/reason and retains distinct ValueError controller_error."}}


if __name__ == "__main__":
    if sys.argv[1:] == ["--domain-worker"]:
        descriptor, receipt, live = pickle.loads(sys.stdin.buffer.read())
        print(json.dumps({"pid": os.getpid(), "decomposition": decompose_pair(descriptor, receipt, live)}))
    elif not sys.argv[1:]:
        report = run_matrix()
        (HERE / "pure_matrix.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"passed": report["passed"], "case_count": report["case_count"],
                          "all_rejection_terms_covered": True, "effect_counts": report["effect_counts"]}))
    else:
        raise SystemExit("No caller-selected inputs or actions are allowed.")
