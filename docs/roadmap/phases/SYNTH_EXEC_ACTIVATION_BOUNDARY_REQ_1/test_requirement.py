"""Pure file/JSON/AST checks: never import or execute a capability owner.

The frozen Java source is inspected as its existing Python AST byte literal.
Nothing writes that source, loads a class, or issues/spends any capability.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
import unittest


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
REFLECT = "docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json"
PREP = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/contract.json"
SOURCE = "core/synthetic_runtime_authorization.py"
RUNTIME = "core/synthetic_runtime_authorization_pinned_lifecycle.py"
ADMISSION = "core/synthetic_reflection_execution_admission_pinned.py"
REFLECTION = "core/synthetic_reflection_execution_lifecycle_pinned.py"
REQUIREMENT_ID = "SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1"
SCENARIO_ID = "synthetic.EXECUTOR.1R.decrement_3"
SOURCE_SHA256 = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
STATES = ("ISSUED", "CONSUMED", "INVALIDATED")
COMPONENTS = {
    "PinnedSyntheticRuntimeExecutionLease_state_machine",
    "PinnedSyntheticReflectionExecutionAdmission",
    "PinnedSyntheticReflectionExecutionLease_state_machine",
    "one_shot_semantics", "terminal_tombstones", "public_validators",
    "HMAC_domains", "authority_matrices", "activation_policy_identity_or_digest",
}
ORDER = [
    "capability_gates", "preparation_complete", "runtime_consume",
    "before_permission_consume", "scenario_dispatch", "target_activation",
    "ordinary_construction", "before_read", "decrement",
    "after_permission_consume", "after_read", "cleanup",
]
FROZEN_STEP_IDS = {
    "authenticate all capability gates": "capability_gates",
    "all capability/authentication gates": "capability_gates",
    "source/harness ready": "preparation_complete",
    "consume pinned runtime lease": "runtime_consume",
    "consume BEFORE reflection lease": "before_permission_consume",
    "perform BEFORE read": "before_read",
    "perform BEFORE exact reflection read": "before_read",
    "invoke public decrement(3)": "decrement",
    "invoke exact public decrement(3)": "decrement",
    "consume AFTER reflection lease": "after_permission_consume",
    "perform AFTER read": "after_read",
    "perform AFTER exact reflection read": "after_read",
}
EFFECTS = {
    "scenario_JVM_dispatch": "BEHAVIORAL_ACTIVATION_EFFECT",
    "target_class_loading_linking_under_scenario_consumer": "BEHAVIORAL_ACTIVATION_EFFECT",
    "target_class_initialization": "BEHAVIORAL_ACTIVATION_EFFECT",
    "ordinary_SyntheticStateBox_construction": "BEHAVIORAL_EFFECT",
    "BEFORE_exact_reflection_read": "BEHAVIORAL_EFFECT",
}
ZERO_EFFECTS = {
    "Docker", "SANDBOX2", "JAVA1C", "provider_issuance", "auth_issuance",
    "runtime_lease_issuance", "runtime_lease_consumption",
    "reflection_admission_issuance", "reflection_lease_issuance",
    "reflection_lease_consumption", "preparation_authority_issuance",
    "capability_invalidation", "source_materialization", "filesystem_runtime_write",
    "javac", "java", "class_loading", "reflection", "SyntheticStateBox",
    "BANK", "EXECUTOR_1R", "Apply",
}
AUTHORITIES = {
    "source_identity_authority_issued_by_this_phase", "preparation_authority",
    "sandbox_materialization_authority", "exact_sandbox_materialization_authority",
    "scenario_compilation_authority", "exact_scenario_compilation_authority",
    "compilation_authority", "runtime_activation_authority", "runtime_authority",
    "real_task_runtime_authority", "reflection_execution_authority",
    "executor_authority", "repository_write_authority", "repository_source_write_authority",
    "repository_java_authority", "apply_authority", "network_authority",
    "shell_authority", "arbitrary_command_authority", "host_mount_authority",
    "arbitrary_java_authority", "arbitrary_source_authority", "arbitrary_class_authority",
    "arbitrary_class_loading_authority", "arbitrary_method_authority",
    "constructor_reflection_authority", "generic_reflection_authority",
    "arbitrary_reflection_authority", "field_write_authority",
    "private_method_authority", "enumeration_authority", "BANK_authority",
}


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def load_json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)


def tree(path):
    return ast.parse((ROOT / path).read_bytes(), filename=path)


def literal(module, name):
    for node in module.body:
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == name:
                return ast.literal_eval(node.value)
            if isinstance(target, ast.Tuple):
                names = [item.id for item in target.elts if isinstance(item, ast.Name)]
                if len(names) == len(target.elts) and name in names:
                    return ast.literal_eval(node.value)[names.index(name)]
    raise AssertionError("Missing literal assignment: " + name)


def function(module, name):
    return next(node for node in module.body
                if isinstance(node, ast.FunctionDef) and node.name == name)


def contains_condition(node, expression):
    expected = ast.dump(ast.parse(expression, mode="eval").body)
    return any(isinstance(item, ast.If) and ast.dump(item.test) == expected
               for item in ast.walk(node))


def class_fields(module, name):
    cls = next(node for node in module.body
               if isinstance(node, ast.ClassDef) and node.name == name)
    return {node.target.id: node.value for node in cls.body
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}


def default_false(node):
    return isinstance(node, ast.Call) and any(
        keyword.arg == "default" and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False for keyword in node.keywords)


class ActivationBoundaryRequirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.req = load_json(PHASE / "requirement.json")
        cls.reflect = load_json(ROOT / REFLECT)
        cls.prep = load_json(ROOT / PREP)
        cls.review = load_json(PHASE / "compatibility_review.json")

    def test_exact_historical_assertion_and_one_scoped_supersession(self):
        req = self.req
        self.assertEqual(req["requirement_id"], REQUIREMENT_ID)
        self.assertEqual(req["artifact_kind"], "additive_semantic_requirement_only")
        self.assertIs(req["decision_frozen"], True)
        self.assertEqual(self.reflect["first_behavior_boundary"]["first_behavioral_effect"], "BEFORE exact read")
        self.assertEqual(req["scope"]["scenario_id"], SCENARIO_ID)
        self.assertIs(req["scope"]["other_scenarios_affected"], False)
        self.assertEqual(len(req["supersessions"]), 1)
        supersession = req["supersessions"][0]
        self.assertEqual(supersession["new_requirement_id"], REQUIREMENT_ID)
        self.assertEqual(supersession["superseded_historical_artifact_path"], REFLECT)
        self.assertEqual(supersession["exact_superseded_key"], "first_behavior_boundary.first_behavioral_effect")
        self.assertEqual(supersession["exact_superseded_value"], "BEFORE exact read")
        self.assertEqual(supersession["scope"], "pinned synthetic." + "EXECUTOR.1R.decrement_3 execution epoch only")
        self.assertIs(supersession["historical_bytes_preserved"], True)
        self.assertIs(supersession["retroactive_mutation"], False)
        self.assertIs(supersession["all_other_historical_claims_superseded"], False)
        self.assertIn("private int value = 10;", supersession["reason"])
        self.assertIn("dispatch of the exact scenario-executing JVM", supersession["effective_downstream_interpretation"])

    def test_exact_source_ast_literal_and_mutable_state_counterexample(self):
        module = tree(SOURCE)
        source = literal(module, "_SOURCE")
        self.assertIs(type(source), bytes)
        self.assertEqual(len(source), 239)
        self.assertEqual(sha256(source).hexdigest(), SOURCE_SHA256)
        self.assertEqual(literal(module, "SOURCE_SHA256"), SOURCE_SHA256)
        self.assertEqual(literal(module, "SOURCE_SIZE_BYTES"), 239)
        self.assertEqual(self.req["scope"]["source_sha256"], SOURCE_SHA256)
        self.assertEqual(self.req["scope"]["source_size_bytes"], 239)
        self.assertTrue(source.startswith(b"final class SyntheticStateBox {\n"))
        self.assertEqual(source.count(b"    private int value = 10;\n"), 1)
        self.assertNotIn(b"static", source)
        self.assertNotIn(b"SyntheticStateBox(", source)
        self.assertIn(b"        value -= amount;\n", source)
        evidence = self.req["semantic_evidence"]
        self.assertEqual(evidence["historical_assertion"], "first_behavioral_effect = BEFORE exact read")
        self.assertEqual(evidence["exact_counterexample"], "private int value = 10;")
        self.assertEqual(evidence["first_known_source_level_mutable_state_effect"], "ordinary construction initializing value = 10")
        self.assertIs(evidence["necessarily_first_executable_harness_effect"], False)
        self.assertIsNone(evidence["earlier_exact_harness_instruction"])
        self.assertIs(evidence["earlier_harness_instruction_may_be_invented"], False)

    def test_ordering_preserves_both_frozen_sequences_and_no_refund(self):
        ids = [step["id"] for step in self.req["normative_ordering"]]
        self.assertEqual(ids, ORDER)
        for sequence in (self.reflect["ordering"], literal(tree(REFLECTION), "EXECUTOR_SEQUENCE")):
            projected = [FROZEN_STEP_IDS[step] for step in sequence]
            self.assertEqual(projected, [item for item in ids if item in projected])
        boundary = self.req["activation_boundary"]
        self.assertEqual(boundary["operation"], "dispatch exact scenario-executing JVM")
        self.assertEqual(boundary["classification"], "BEHAVIORAL_ACTIVATION_EFFECT")
        self.assertEqual(boundary["required_before_dispatch"], [
            "all capability/authentication gates", "all preparation evidence",
            "full harness readiness", "consumer readiness",
            "runtime lease ISSUED -> CONSUMED", "BEFORE reflection lease ISSUED -> CONSUMED",
        ])
        self.assertIs(boundary["preparation_after_runtime_consumption_allowed"], False)
        self.assertIs(boundary["target_loading_linking_initialization_or_construction_before_dispatch_allowed"], False)
        self.assertTrue(boundary["between_runtime_consumption_and_dispatch"].startswith("Only mandatory authenticated permission checks/commits"))
        self.assertEqual(boundary["launch_failure_after_runtime_consumption"], "no refund")
        self.assertIn("no launch, refund, reopening or retry", boundary["failed_check_after_runtime_consumption"])
        self.assertIs(self.reflect["first_behavior_boundary"]["failure_after_commit_refunds"], False)
        self.assertTrue(self.req["preserved_invariants"])
        self.assertTrue(all(value is True for value in self.req["preserved_invariants"].values()))

    def test_five_scoped_effect_classifications_do_not_generalize_jvm_behavior(self):
        self.assertEqual(self.req["effect_terminology"], EFFECTS)
        self.assertIs(self.req["semantic_evidence"]["all_JVM_launches_are_behavioral"], False)
        self.assertIs(self.req["activation_boundary"]["exact_first_harness_instruction_claimed"], False)
        self.assertIn("compiler JVMs", self.req["activation_boundary"]["generic_JVM_startup_classification"])
        self.assertIn("independently proved inert infrastructure JVMs", self.req["activation_boundary"]["generic_JVM_startup_classification"])
        self.assertIn("Loading/linking is distinct from initialization", self.req["effect_terminology_scope"])
        self.assertIn("not a universal claim", self.req["effect_terminology_scope"])

    def test_full_harness_remains_unresolved_and_readiness_false(self):
        expected = {
            "source_bytes", "source_sha256", "source_size_bytes", "main_class",
            "scenario_JVM_argv", "loader_controller_implementation",
            "staged_BEFORE_AFTER_protocol_implementation",
        }
        harness = self.req["full_harness"]
        self.assertEqual(set(harness["unresolved_fields"]), expected)
        for key in expected:
            self.assertIsNone(harness[key], key)
        for key in ("full_executable_harness_frozen", "reflection_helpers_establish_full_harness", "earlier_exact_instruction_invented"):
            self.assertIs(harness[key], False)
        self.assertIs(self.req["behavioral_activation_ready"], False)
        self.assertEqual(self.req["reason"], "PROOF_UNRESOLVED")
        self.assertIs(self.req["activation_boundary"]["launch_authorized_by_this_requirement"], False)
        self.assertIs(self.reflect["readiness"]["behavioral_activation_ready"], False)
        self.assertEqual(self.reflect["readiness"]["reason"], "PROOF_UNRESOLVED")

    def test_prep_proposals_require_separate_closure_and_grant_no_authority(self):
        relationship = self.req["preparation_relationship"]
        self.assertEqual(self.prep["completion_marker"], "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION")
        self.assertEqual(relationship["historical_outcome"], self.prep["completion_marker"])
        self.assertIs(self.prep["proposed_downstream_rules_are_operational_authority"], False)
        self.assertEqual(relationship["proposed_classifications"], {
            "in_memory_exact_source_projection": self.prep["effect_classification"]["in_memory_source_projection"]["class"],
            "sandbox_exact_source_materialization": self.prep["effect_classification"]["sandbox_materialization"]["class"],
            "exact_bounded_javac_scenario_compilation": self.prep["effect_classification"]["javac_compilation"]["class"],
        })
        self.assertEqual(set(relationship["proposed_classifications"].values()), {"PURE_DERIVATION", "PREPARATION_EFFECT"})
        self.assertEqual(relationship["proposal_status"], "non-operational proposals until preparation contract closure")
        self.assertIs(relationship["closure_review_required"], True)
        for key in ("automatically_become_operational_requirements", "preparation_authority_granted_by_this_evolution", "preparation_implementation_allowed_from_this_phase", "proposed_owner_receipt_and_consumer_designs_adopted"):
            self.assertIs(relationship[key], False, key)
        self.assertIn("materialization, compile and readiness rules", relationship["next_review"])
        self.assertIn("before any preparation implementation", relationship["next_review"])

    def test_new_phase_all_authorities_false_and_effects_exact_integer_zero(self):
        self.assertEqual(set(self.req["authority_flags"]), AUTHORITIES)
        for key, value in self.req["authority_flags"].items():
            self.assertIs(value, False, key)
        self.assertEqual(set(self.req["operational_effects"]), ZERO_EFFECTS)
        for key, value in self.req["operational_effects"].items():
            self.assertIs(type(value), int, key)
            self.assertEqual(value, 0, key)
        for key in ("implementation_authorized", "preparation_owner_implemented", "preparation_receipt_implemented", "consumer_owner_implemented", "runtime_integration_implemented", "harness_implemented", "executor_implemented", "source_materialized"):
            self.assertIs(self.req[key], False, key)
        completion = self.req["completion_rule"]
        self.assertEqual(completion["success"], "SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1_COMPLETE")
        self.assertEqual(completion["unresolved"], "REQUIREMENT_EVOLUTION_UNRESOLVED")
        self.assertIs(completion["fail_closed"], True)
        self.assertIs(completion["stop_after_requirement_evolution"], True)

    def test_static_compatibility_review_hashes_anchors_and_no_required_change(self):
        compat = self.req["compatibility_review"]
        self.assertEqual(compat["change_kind"], "semantic requirement placement only")
        self.assertEqual(set(compat["requires_change"]), COMPONENTS)
        self.assertTrue(all(value is False for value in compat["requires_change"].values()))
        self.assertEqual(set(self.review["components"]), COMPONENTS)
        self.assertEqual(set(self.review["reviewed_sources"]), {SOURCE, RUNTIME, ADMISSION, REFLECTION, REFLECT, PREP})
        self.assertEqual(self.review["requirement_id"], REQUIREMENT_ID)
        self.assertIs(self.review["static_source_contract_review_only"], True)
        self.assertIs(self.review["requires_owner_or_api_changes"], False)
        self.assertIs(self.review["operational_authority_granted"], False)
        for path, pin in self.review["reviewed_sources"].items():
            data = (ROOT / path).read_bytes()
            self.assertEqual(len(data), pin["size_bytes"], path)
            self.assertEqual(sha256(data).hexdigest(), pin["sha256"], path)
        for component in self.review["components"].values():
            self.assertIs(component["requires_change"], False)
            self.assertTrue(component["rationale"])
            self.assertTrue(component["evidence"])
            for anchor in component["evidence"]:
                lines = (ROOT / anchor["path"]).read_text(encoding="utf-8").splitlines()
                self.assertEqual("\n".join(lines[anchor["start_line"] - 1:anchor["end_line"]]), anchor["text"])
        for key in ("new_state_or_transition", "runtime_policy_digest_recomputed_or_repinned", "public_validator_call_contracts_rewritten", "historical_sequence_constants_rewritten", "future_implementation_compatibility_preapproved"):
            self.assertIs(compat[key], False)

    def test_static_terminal_state_machine_one_shot_and_admission_compatibility(self):
        runtime, reflection, admission = tree(RUNTIME), tree(REFLECTION), tree(ADMISSION)
        for module in (runtime, reflection):
            self.assertEqual(tuple(literal(module, state) for state in STATES), STATES)
            transition = function(module, "_transition")
            self.assertTrue(contains_condition(transition, "type(target) is not str or target not in (CONSUMED, INVALIDATED)"))
            self.assertTrue(contains_condition(transition, "record.lifecycle_state != ISSUED"))
            self.assertIn("_sign(record.projection_json, target)", ast.unparse(transition))
        self.assertTrue(contains_condition(function(runtime, "issue_pinned_synthetic_runtime_execution_lease"), "key in _STORE.authorization_leases"))
        self.assertTrue(contains_condition(function(admission, "issue_pinned_synthetic_reflection_execution_admission"), "key in _STORE.admission_slots"))
        self.assertTrue(contains_condition(function(reflection, "issue_pinned_synthetic_reflection_execution_lease"), "key in _STORE.admission_leases"))
        self.assertTrue(contains_condition(function(reflection, "_transition"), "target == CONSUMED and runtime_state != CONSUMED"))
        self.assertIs(self.reflect["admission_identity"]["admission_has_no_consumption_state_machine"], True)
        self.assertEqual(self.reflect["state_machine"]["states"], list(STATES))
        self.assertEqual(self.reflect["state_machine"]["transitions"], [["ISSUED", "CONSUMED"], ["ISSUED", "INVALIDATED"]])
        for key in ("refund_allowed", "reissue_allowed", "collection_reopens_issuance"):
            self.assertIs(self.reflect["state_machine"][key], False)
            self.assertIs(self.reflect["admission_one_shot"][key], False)
        self.assertIs(self.reflect["state_machine"]["permanent_admission_and_lease_tombstones"], True)
        self.assertIs(self.reflect["admission_one_shot"]["permanent_tombstones"], True)

    def test_static_fail_closed_policy_and_readiness_compatibility(self):
        module = tree(RUNTIME)
        policy_return = next(node for node in function(module, "_activation_policy").body if isinstance(node, ast.Return))
        self.assertIsInstance(policy_return.value, ast.Dict)
        policy = {}
        for key, value in zip(policy_return.value.keys, policy_return.value.values):
            if isinstance(value, ast.Name):
                self.assertEqual(value.id, "ACTIVATION_POLICY_ID")
                value = literal(module, value.id)
            else:
                value = ast.literal_eval(value)
            policy[ast.literal_eval(key)] = value
        self.assertEqual(literal(module, "ACTIVATION_POLICY_ID"), "SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-decrement-3-activation:v1")
        self.assertIs(policy["behavioral_readiness_established_by_this_phase"], False)
        self.assertIs(policy["lease_local_ready_implies_behavioral_ready"], False)
        self.assertEqual(policy["unresolved_dependency_error"], "PROOF_UNRESOLVED")
        readiness = function(module, "check_pinned_synthetic_runtime_execution_lease_preconditions")
        result = next(node.value for node in ast.walk(readiness) if isinstance(node, ast.Return))
        self.assertIsInstance(result, ast.Call)
        self.assertIs(result.args[1].value, False)
        unresolved = function(module, "_consumer_readiness")
        self.assertIn('_fail(\'PROOF_UNRESOLVED\'', ast.unparse(unresolved))
        self.assertIn("_consumer_readiness()", ast.unparse(function(module, "_transition")))
        for path, cls in ((RUNTIME, "PinnedSyntheticRuntimeExecutionLease"), (ADMISSION, "PinnedSyntheticReflectionExecutionAdmission"), (REFLECTION, "PinnedSyntheticReflectionExecutionLease")):
            owner_tree = tree(path)
            fields = class_fields(owner_tree, cls)
            for flag in literal(owner_tree, "_FALSE_AUTHORITY"):
                self.assertIn(flag, fields)
                self.assertTrue(default_false(fields[flag]), path + ":" + flag)
        report = class_fields(tree(REFLECTION), "PinnedSyntheticReflectionExecutionLeaseReadiness")
        self.assertTrue(default_false(report["behavioral_activation_ready"]))
        self.assertIs(self.reflect["authority"]["exact_role_read_only_permission"], True)
        self.assertIs(self.reflect["authority"]["admission_can_prepare_lease_only"], True)
        self.assertIs(self.reflect["authority"]["consumption_widens_scope"], False)

    def test_static_hmac_domains_framing_and_public_validators_unchanged(self):
        domains = {
            RUNTIME: b"CATTUS:SYNTH.AUTH.LIFECYCLE.PINNED.1:exact-execution-lease:v1",
            ADMISSION: b"CATTUS:SYNTH.REFLECT.ADMIT.PINNED.1:exact-reflection-admission:v1",
            REFLECTION: b"CATTUS:SYNTH.REFLECT.LIFECYCLE.PINNED.1:exact-reflection-lease:v1",
        }
        validators = {
            RUNTIME: ("validate_pinned_synthetic_runtime_execution_lease", ["lease", "authorization"]),
            ADMISSION: ("validate_pinned_synthetic_reflection_execution_admission", ["admission", "authorization", "runtime", "request", "role"]),
            REFLECTION: ("validate_pinned_synthetic_reflection_execution_lease", ["lease", "admission", "authorization", "runtime", "request", "role"]),
        }
        for path, domain in domains.items():
            owner = tree(path)
            self.assertEqual(literal(owner, "_DOMAIN"), domain)
            self.assertIn("b'\\x00'", ast.unparse(function(owner, "_framed")))
            signed = ast.unparse(function(owner, "_sign"))
            self.assertIn("hmac.new", signed)
            self.assertIn("record-hmac", signed)
            self.assertIn("'sha256'", signed)
            validator, arguments = validators[path]
            self.assertEqual([item.arg for item in function(owner, validator).args.args], arguments)
            self.assertIn("_authenticated_record_locked", ast.unparse(function(owner, validator)))
        for path in (ADMISSION, REFLECTION):
            graph = ast.unparse(function(tree(path), "_authenticate_graph"))
            for name in ("validate_synthetic_reflection_request", "validate_pinned_synthetic_runtime_authorization", "validate_pinned_synthetic_runtime_execution_lease"):
                self.assertIn(name, graph)
            public = ast.unparse(function(tree(path), "_public_validate"))
            self.assertIn("is not value", public)

    def test_historical_owners_contracts_and_phase_baseline_bytes_and_links(self):
        baseline_path = PHASE / "preservation_baseline.json"
        self.assertTrue(baseline_path.is_file(), "Capture immutable historical baseline before validation")
        baseline = load_json(baseline_path)
        self.assertIs(baseline["links_followed"], False)
        self.assertEqual(baseline["file_count"], len(baseline["files"]))
        self.assertEqual(baseline["new_phase_excluded"].rstrip("/"), PHASE.relative_to(ROOT).as_posix())
        self.assertTrue({SOURCE, RUNTIME, ADMISSION, REFLECTION, REFLECT, PREP}.issubset(baseline["files"]))
        for relative, before in baseline["files"].items():
            # The final validator checks all baseline entries, including archives.
            # Focused checks cover all owners/contracts and frozen phase history.
            if not relative.startswith(("core/", "docs/", "scripts/")):
                continue
            with self.subTest(path=relative):
                path = ROOT / relative
                self.assertTrue(path.is_relative_to(ROOT))
                if before["kind"] == "link":
                    self.assertTrue(path.is_symlink() or getattr(path, "is_junction", lambda: False)())
                    self.assertEqual(str(path.readlink()), before["target"])
                else:
                    self.assertEqual(before["kind"], "file")
                    self.assertFalse(path.is_symlink())
                    data = path.read_bytes()
                    self.assertEqual(len(data), before["bytes"])
                    self.assertEqual(sha256(data).hexdigest(), before["sha256"])
        preservation = self.req["historical_preservation"]
        self.assertIs(preservation["historical_bytes_preserved"], True)
        for key in ("old_JSON_rewritten", "history_repinned", "retroactive_mutation", "old_requirement_globally_invalidated"):
            self.assertIs(preservation[key], False)


if __name__ == "__main__":
    unittest.main(verbosity=2)
