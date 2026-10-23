"""Pure JSON/raw-byte/AST closure checks; never import a capability owner.

The existing Java byte literal is inspected in memory only. These checks do
not materialize source, execute a compiler/JVM, or issue/spend capabilities.
"""
import ast
from hashlib import sha256
import json
from pathlib import Path
import unittest


PHASE = Path(__file__).resolve().parent
ROOT = PHASE.parents[3]
PREP = "docs/roadmap/phases/SYNTH_EXEC_PREP_PINNED_CONTRACT_1/contract.json"
REQ = "docs/roadmap/phases/SYNTH_EXEC_ACTIVATION_BOUNDARY_REQ_1/requirement.json"
REFLECT = "docs/roadmap/phases/SYNTH_REFLECT_PINNED_CONTRACT_1/contract.json"
SOURCE = "core/synthetic_runtime_authorization.py"
RUNTIME = "core/synthetic_runtime_authorization_pinned_lifecycle.py"
REFLECTION = "core/synthetic_reflection_execution_lifecycle_pinned.py"
ADMISSION = "core/synthetic_reflection_execution_admission_pinned.py"
SOURCE_HASH = "813a17fd33e9c3d5a9bdc5bb6f8158e97ad7b021c3a0d2915ef68e45b0f09302"
DEFINITION_HASH = "e9466adfd5ab3e881b96deab9ac5bdac6907da17a9014f457bb20d7fdc2a941d"


def load(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def tree(relative):
    return ast.parse((ROOT / relative).read_text(encoding="utf-8"))


def literal(module, name):
    values = [node.value for node in module.body if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
    if len(values) != 1:
        raise AssertionError("Exactly one frozen literal required: " + name)
    return ast.literal_eval(values[0])


def function(module, name):
    matches = [node for node in module.body if isinstance(node, ast.FunctionDef) and node.name == name]
    if len(matches) != 1:
        raise AssertionError("Exactly one owner function required: " + name)
    return matches[0]


def condition(node, expression):
    expected = ast.dump(ast.parse(expression, mode="eval").body)
    matches = [item for item in ast.walk(node) if isinstance(item, ast.If)
        and ast.dump(item.test) == expected]
    if len(matches) != 1:
        raise AssertionError("Exactly one required guard: " + expression)
    return matches[0]


def call(node, name):
    matches = [item for item in ast.walk(node) if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Name) and item.func.id == name]
    if len(matches) != 1:
        raise AssertionError("Exactly one required call: " + name)
    return matches[0]


class PreparationClosureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads((PHASE / "contract.json").read_text(encoding="utf-8"))
        cls.previous = load(PREP)
        cls.requirement = load(REQ)

    def test_all_six_review_decisions_close_only_preparation_semantics(self):
        contract = self.contract
        self.assertEqual(contract["completion_marker"], "SYNTH_EXEC_PREP_PINNED_CONTRACT_CLOSE_1_COMPLETE")
        self.assertEqual(contract["phase_id"], "SYNTH.EXEC.PREP.PINNED.CONTRACT.CLOSE.1")
        self.assertIs(contract["decision_frozen"], True)
        self.assertIs(contract["preparation_contract_complete"], True)
        expected = [
            (1, "in_memory_source_projection", "PURE_DERIVATION", "ACCEPTED_UNCHANGED"),
            (2, "sandbox_materialization", "PREPARATION_EFFECT", "ACCEPTED_UNCHANGED"),
            (3, "javac_compilation", "PREPARATION_EFFECT", "ACCEPTED_WITH_ADDITIVE_CLARIFICATION"),
            (4, "JVM_startup", "BEHAVIORAL_ACTIVATION_EFFECT", "ACCEPTED_WITH_ADDITIVE_CLARIFICATION"),
            (5, "target_loading_initialization_construction", "AFTER_ACTIVATION_BOUNDARY", "ACCEPTED_UNCHANGED"),
            (6, "no_preparation_after_runtime_consumption", "ORDERING_INVARIANT", "ACCEPTED_UNCHANGED"),
        ]
        self.assertEqual([(row["item"], row["proposal"], row["classification"], row["decision"])
            for row in contract["proposal_review"]], expected)
        self.assertTrue(all(row["rationale"] for row in contract["proposal_review"]))
        scope = contract["closure_scope"]
        self.assertEqual(scope["previous_proposal"], PREP)
        self.assertEqual(scope["revised_requirement"], REQ)
        self.assertEqual(scope["previous_outcome"], self.previous["completion_marker"])
        self.assertEqual(scope["previous_outcome"], "PREPARATION_REQUIRES_REQUIREMENT_EVOLUTION")
        self.assertIs(scope["preparation_semantics_now_frozen"], True)
        for flag in ("frozen_semantics_are_operational_authority", "historical_artifacts_rewritten",
                     "additional_historical_claims_superseded", "consumer_owner_or_runtime_integration_frozen"):
            self.assertIs(scope[flag], False, flag)

    def test_frozen_materialization_compiler_sandbox_output_cleanup_unchanged(self):
        for section in ("scenario", "effect_classification", "materialization", "compiler", "sandbox",
                        "compile_output", "cleanup"):
            with self.subTest(section=section):
                self.assertEqual(self.contract[section], self.previous[section])

    def test_existing_source_literal_exact_bytes_identity_and_definition(self):
        module = tree(SOURCE)
        data, scenario = literal(module, "_SOURCE"), self.contract["scenario"]
        self.assertIs(type(data), bytes)
        self.assertEqual(len(data), literal(module, "SOURCE_SIZE_BYTES"))
        self.assertEqual(len(data), scenario["source_size_bytes"])
        self.assertEqual(len(data), 239)
        self.assertEqual(sha256(data).hexdigest(), SOURCE_HASH)
        self.assertEqual(literal(module, "SOURCE_SHA256"), SOURCE_HASH)
        self.assertEqual(scenario["source_sha256"], SOURCE_HASH)
        self.assertEqual(scenario["definition_sha256"], DEFINITION_HASH)
        self.assertEqual(literal(module, "_DEFINITION_SHA256"), DEFINITION_HASH)
        self.assertEqual(scenario["scenario_id"], literal(module, "SCENARIO_ID"))
        self.assertEqual(scenario["scenario_id"], self.requirement["scope"]["scenario_id"])
        invocation = call(function(module, "_fixed_spec"), "SyntheticInvocationContract")
        self.assertEqual([ast.literal_eval(arg) for arg in invocation.args],
            ["SyntheticStateBox", "decrement", (3,), ("int",), "boolean"])
        metadata = call(function(module, "_fixed_spec"), "SyntheticRequestedFieldMetadata")
        self.assertEqual([ast.literal_eval(arg) for arg in metadata.args[:3]],
            ["SyntheticStateBox", "value", "int"])
        self.assertEqual([arg.id for arg in metadata.args[3:]], ["_DEFINITION_SHA256", "SOURCE_SHA256"])
        for key in ("source_regeneration_allowed", "source_rewriting_allowed", "alternative_implementation_allowed",
                    "expected_values_are_observed_evidence"):
            self.assertIs(scenario[key], False, key)

    def test_source_evidence_is_closed_and_construction_precedes_observation(self):
        data = literal(tree(SOURCE), "_SOURCE")
        self.assertTrue(data.startswith(b"final class SyntheticStateBox {\n"))
        self.assertEqual(data.count(b"class "), 1)
        self.assertEqual(data.count(b"private int value = 10;"), 1)
        self.assertIn(b"public boolean decrement(int amount)", data)
        self.assertIn(b"value -= amount;", data)
        for forbidden in (b"import ", b"@", b"static", b"SyntheticStateBox("):
            self.assertNotIn(forbidden, data)
        boundary = self.contract["first_behavioral_effect"]
        self.assertEqual(boundary["first_known_source_level_mutable_state_effect"],
            "ordinary construction initializing value = 10")
        self.assertIsNone(boundary["first_exact_executable_harness_instruction"])
        self.assertIs(boundary["source_evidence_contradicts_compilation_classification"], False)
        self.assertIn("STOP", boundary["contradiction_policy"])
        self.assertIn("do not compile or run", boundary["contradiction_policy"])
        self.assertIn("UNRESOLVED", boundary["contradiction_policy"])

    def test_materialization_retains_exact_budget_exclusivity_and_no_host_export(self):
        materialization = self.contract["materialization"]
        self.assertEqual(materialization["destination"], "/work/SyntheticStateBox.java")
        self.assertEqual(materialization["directories_created"], ["/work/classes"])
        self.assertEqual(materialization["maximum_materialized_source_files"], 1)
        self.assertEqual(materialization["maximum_materialized_source_bytes"], 239)
        self.assertEqual(materialization["maximum_preparation_regular_files"], 2)
        self.assertEqual(materialization["allowed_preparation_regular_files"],
            ["/work/SyntheticStateBox.java", "/work/classes/SyntheticStateBox.class"])
        for key in ("harness_files_included", "repository_source_write_authority", "persistent_artifacts_allowed",
                    "export_source_or_class_to_host_allowed"):
            self.assertIs(materialization[key], False, key)
        for fragment in ("exclusive", "Never overwrite", "byte-identical"):
            self.assertIn(fragment, materialization["overwrite_policy"])
        for fragment in ("unexpected/subordinate mount", "symlinks", "hardlink", "special files", "no-follow"):
            self.assertIn(fragment, materialization["symlink_policy"])
        for fragment in ("NUL", "traversal", "No caller path"):
            self.assertIn(fragment, materialization["path_policy"])

    def test_compiler_exact_argv_and_pins_are_recovered_from_unchanged_ast(self):
        compiler = self.contract["compiler"]
        historical = [compiler["path"], *literal(tree("core/sandboxed_java_toolchain_probe.py"), "COMPILE_ARGUMENTS")]
        self.assertEqual(compiler["historical_JAVA_1C_argv"], historical)
        self.assertEqual(compiler["exact_scenario_argv"], historical[:-1] + ["/work/SyntheticStateBox.java"])
        self.assertEqual(historical[-1], "/work/JavaSandboxProbe.java")
        self.assertNotIn("-proc:none", compiler["exact_scenario_argv"])
        self.assertEqual(compiler["cwd"], "/work")
        self.assertIs(compiler["shell"], False)
        requirement = tree("core/runtime_java_pinned_requirement.py")
        self.assertEqual(compiler["image"], literal(requirement, "IMAGE"))
        self.assertEqual(compiler["sandbox_policy_sha256"], literal(requirement, "POLICY_SHA256"))
        cls = next(node for node in requirement.body if isinstance(node, ast.ClassDef)
            and node.name == "PinnedJavaRequirement")
        javac = next(node.value for node in cls.body if isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name) and node.target.id == "javac")
        self.assertIsInstance(javac, ast.Call)
        self.assertEqual([ast.literal_eval(arg) for arg in javac.args], [compiler["path"], compiler["sha256"]])
        policy = (ROOT / "docs/roadmap/RUNTIME_SANDBOX_2_SECCOMP.json").read_bytes()
        self.assertEqual(sha256(policy).hexdigest(), compiler["sandbox_policy_sha256"])

    def test_compiler_has_closed_inputs_and_exact_noninjectable_environment(self):
        compiler, sandbox = self.contract["compiler"], self.contract["sandbox"]
        for key in ("caller_flags_allowed", "argument_files_allowed", "arbitrary_classpath_allowed", "maven_allowed",
                    "gradle_allowed", "dependency_download_allowed", "network_allowed", "processor_plugin_inputs_allowed"):
            self.assertIs(compiler[key], False, key)
        environment = literal(tree("core/candidate_runtime_sandbox.py"), "_WORKLOAD_ENVIRONMENT")
        self.assertEqual(sandbox["environment"], environment)
        self.assertEqual(len(environment), 8)
        for variable in ("CLASSPATH", "JDK_JAVAC_OPTIONS", "JAVA_TOOL_OPTIONS", "_JAVA_OPTIONS"):
            self.assertNotIn(variable, environment)
            self.assertIn(variable, compiler["input_closure"])
        for fragment in ("no class/JAR/processor/service/config inputs", "no source imports/annotations",
                         "Do not invent -proc:none or other flags"):
            self.assertIn(fragment, compiler["input_closure"])
        rationale = self.contract["proposal_review"][2]["rationale"]
        self.assertIn("Compiler JVM infrastructure startup is distinct", rationale)
        self.assertIn("processor/plugin/dependency", rationale)

    def test_exact_sandbox_bounds_and_inert_output_never_predict_behavior(self):
        sandbox, output, compiler = self.contract["sandbox"], self.contract["compile_output"], self.contract["compiler"]
        self.assertEqual(sandbox["tmpfs"], {"/work": "rw,nosuid,nodev,size=32m,mode=1777",
            "/tmp": "rw,nosuid,nodev,noexec,size=16m,mode=1777"})
        self.assertEqual(sandbox["network"], "none")
        self.assertIs(sandbox["rootfs_readonly"], True)
        self.assertEqual(sandbox["host_mounts"], [])
        self.assertIs(sandbox["image_declared_volumes_allowed"], False)
        self.assertIs(sandbox["provider_proof_workspace_reusable"], False)
        self.assertEqual(sandbox["uid_gid"], "65534:65534")
        self.assertEqual((sandbox["pids_max"], sandbox["memory_bytes"], sandbox["nano_cpus"]),
            (128, 134217728, 1000000000))
        self.assertEqual((compiler["compiler_stdout_max_bytes"], compiler["compiler_stderr_max_bytes"]), (2048, 2048))
        self.assertEqual((compiler["outer_stdout_max_bytes"], compiler["outer_stderr_max_bytes"]), (8192, 8192))
        self.assertEqual((compiler["outer_timeout_ms"], compiler["shared_controller_deadline_ms"]), (10000, 5000))
        self.assertEqual(output["expected_relative_class_set"], ["SyntheticStateBox.class"])
        self.assertEqual(output["expected_path"], "/work/classes/SyntheticStateBox.class")
        self.assertEqual((output["maximum_class_files"], output["minimum_class_bytes"], output["maximum_class_bytes"]), (1, 1, 32768))
        self.assertIsNone(output["predicted_class_sha256"])
        self.assertIn("never load", output["manifest"])
        self.assertIn("inert data", output["manifest"])
        self.assertIn("same source bytes before/after", output["manifest"])
        self.assertIn("COMPILE_OUTPUT_MISMATCH", output["unexpected_file_behavior"])
        self.assertIs(output["exit_zero_proves_source_identity"], False)
        self.assertIs(output["compile_success_proves_behavior_success"], False)
        self.assertTrue(any("empty stdout/stderr" in item for item in output["success_requirements"]))

    def test_future_preparation_facets_are_noninterchangeable_one_shot_and_bound(self):
        authority = self.contract["preparation_authority"]
        self.assertEqual(authority["future_owner"], "core.synthetic_execution_preparation_pinned")
        self.assertEqual(authority["facets"],
            ["exact_sandbox_materialization_authority", "exact_scenario_compilation_authority"])
        self.assertIs(authority["one_authority_two_noninterchangeable_facets"], True)
        self.assertEqual(authority["semantics"], self.previous["authority_separation"])
        facet = authority["each_facet"]
        self.assertIs(type(facet["max_attempts"]), int)
        self.assertEqual(facet["max_attempts"], 1)
        self.assertEqual(facet["reservation"], "immediately before its exact effect")
        self.assertIs(facet["failure_spends_attempt"], True)
        self.assertIs(facet["refund_allowed"], False)
        self.assertIs(facet["reissue_allowed"], False)
        self.assertEqual(facet["runtime_state_required"], "ISSUED")
        self.assertEqual(facet["exact_original_bindings"],
            ["pinned authorization", "runtime lease", "workspace/container generation", "controller", "provider graph"])
        self.assertIs(authority["compilation_requires_verified_materialization"], True)
        for key in ("materialization_facet_can_compile", "compilation_facet_can_materialize",
                    "generic_file_or_command_API_allowed", "sandbox_or_provider_issuance_granted",
                    "future_implementation_or_lock_integration_preapproved", "phase_issues_authority"):
            self.assertIs(authority[key], False, key)

    def test_preparation_receipt_proves_only_preparation_and_cleanup_remains_pending(self):
        receipt = self.contract["preparation_receipt"]
        self.assertEqual(receipt["kind"], "authenticated_evidence_not_capability")
        self.assertEqual(receipt["may_prove_only"], ["exact source authentication", "materialization and full readback",
            "compiler identity", "exact argv/cwd/environment", "compile result",
            "bounded output manifest with actual class hash", "live workspace generation", "cleanup pending"])
        for key in ("runtime_permission", "execution_permission", "caller_boolean_accepted",
                    "context_bindings_are_additional_readiness_claims", "may_claim_full_harness_readiness",
                    "may_claim_consumer_readiness", "may_claim_behavior_success", "alone_unlocks_runtime_consumption"):
            self.assertIs(receipt[key], False, key)
        for key, value in self.previous["preparation_receipt"].items():
            self.assertEqual(receipt[key], value, key)
        self.assertEqual(receipt["cleanup_state_at_success"], "LIVE_EPHEMERAL_ARTIFACTS_CLEANUP_PENDING")
        self.assertIs(receipt["cleanup_success_claimed_at_preparation_success"], False)
        cleanup = self.contract["cleanup"]
        self.assertIs(cleanup["preparation_success_implies_cleanup_success"], False)
        self.assertIn("consumer completion", cleanup["after_preparation_success"])
        self.assertIn("independently verify absence", cleanup["after_behavior_or_abandonment"])
        self.assertIn("No source, class, harness", cleanup["persistent_artifacts"])

    def test_authentication_does_not_freeze_a_consumer_domain_or_treat_digest_as_authority(self):
        authentication = self.contract["preparation_evidence_authentication"]
        self.assertEqual(authentication, {key: value for key, value in self.previous["evidence_authentication"].items()
            if key != "consumer_domain"})
        self.assertNotIn("consumer_domain", authentication)
        self.assertIs(authentication["digest_is_authentication"], False)
        self.assertIs(authentication["JSON_exports_report_only"], True)
        for key in ("source_identity_not_equal_to_obtained_bytes", "obtained_bytes_not_equal_to_materialization",
                    "materialization_not_equal_to_compilation", "compilation_not_equal_to_runtime_behavior"):
            self.assertIs(authentication[key], True, key)

    def test_harness_fields_remain_null_and_helpers_cannot_supply_missing_proof(self):
        boundary = self.contract["harness_boundary"]
        self.assertEqual(boundary["decision"], "UNRESOLVED")
        self.assertEqual(boundary["full_harness"], self.requirement["full_harness"])
        expected = {"source_bytes", "source_sha256", "source_size_bytes", "main_class", "scenario_JVM_argv",
            "loader_controller_implementation", "staged_BEFORE_AFTER_protocol_implementation"}
        harness = boundary["full_harness"]
        self.assertEqual(set(harness["unresolved_fields"]), expected)
        for field in expected:
            self.assertIsNone(harness[field], field)
        for field in ("full_executable_harness_frozen", "reflection_helpers_establish_full_harness",
                      "earlier_exact_instruction_invented"):
            self.assertIs(harness[field], False, field)
        self.assertEqual(boundary["invented_harness_fields"], [])
        self.assertIs(boundary["helpers_establish_full_harness"], False)
        self.assertIs(boundary["preparation_closure_requires_harness_completion"], False)
        history = boundary["historical_renderer_identity"]
        self.assertEqual(history, self.previous["harness_identity"])
        for role in ("before", "after"):
            helper = literal(tree("core/synthetic_read_only_reflection.py"), "_" + role.upper() + "_HELPER")
            digest = sha256(helper.encode("utf-8")).hexdigest()
            self.assertEqual(history[role + "_helper_sha256"], digest)
            self.assertEqual(literal(tree(REFLECTION), role.upper() + "_HELPER_SHA256"), digest)
            self.assertNotIn("main(", helper)

    def test_consumer_review_freezes_only_dependency_shape_not_owner_schema_or_api(self):
        consumer = self.contract["consumer_readiness"]
        self.assertEqual(consumer["review_scope"], "DEPENDENCY_SHAPE_ONLY")
        self.assertEqual(consumer["dependency_decision"], "ACCEPTED_WITH_ADDITIVE_CLARIFICATION")
        self.assertEqual(consumer["final_owner_decision"], "UNRESOLVED")
        self.assertIs(consumer["preparation_receipt_may_be_one_future_input"], True)
        self.assertIs(consumer["separate_full_harness_and_consumer_review_required"], True)
        for key in ("preparation_receipt_alone_unlocks_runtime_consumption", "final_owner_frozen", "final_schema_frozen",
                    "final_public_API_frozen", "runtime_lock_integration_frozen", "implemented"):
            self.assertIs(consumer[key], False, key)
        self.assertEqual(consumer["runtime_consumption"], "PROOF_UNRESOLVED")
        for unreviewed in ("proposed_owner", "proposed_type", "proposed_schema", "minimum_signed_bindings",
                           "runtime_integration", "race_policy", "consumer_domain"):
            self.assertNotIn(unreviewed, consumer)

    def test_activation_boundary_matches_completed_requirement_without_global_jvm_claim(self):
        self.assertEqual(self.contract["activation_boundary"], self.requirement["activation_boundary"])
        boundary = self.contract["first_behavioral_effect"]
        self.assertEqual(boundary["operation"], "dispatch exact scenario-executing JVM")
        self.assertEqual(boundary["classification"], "BEHAVIORAL_ACTIVATION_EFFECT")
        self.assertIs(boundary["requirement_evolution_required"], False)
        self.assertEqual(boundary["resolved_by"], "SYNTH.EXEC.ACTIVATION.BOUNDARY.REQ.1")
        self.assertIn("no universal classification", self.contract["proposal_review"][3]["rationale"])
        self.assertIs(self.contract["activation_boundary"]["launch_authorized_by_this_requirement"], False)

    def test_sequence_prepares_both_roles_issued_and_preserves_requirement_order(self):
        order = self.contract["ordering"]
        self.assertEqual(order["preparation_runtime_state"], "ISSUED")
        self.assertEqual(order["both_reflection_admissions_and_leases_prepared_with_runtime"], "ISSUED")
        self.assertIs(order["preparation_requires_runtime_CONSUMED"], False)
        self.assertIs(order["preparation_after_runtime_consumption_allowed"], False)
        self.assertIs(order["cleanup_is_preparation"], False)
        ids = [step["id"] for step in order["sequence"]]
        self.assertEqual(len(ids), len(set(ids)))
        normative = [step["id"] for step in self.requirement["normative_ordering"]
            if step["id"] != "preparation_complete"]
        self.assertEqual([item for item in ids if item in normative], normative)
        preparation = ["prepare_reflection", "source_authentication", "source_projection", "materialization",
            "compilation", "preparation_evidence", "future_full_readiness", "handoff"]
        self.assertEqual([item for item in ids if item in preparation], preparation)
        self.assertTrue(all(ids.index(item) < ids.index("runtime_consume") for item in preparation))
        self.assertEqual(ids[ids.index("runtime_consume"):ids.index("scenario_dispatch") + 1],
            ["runtime_consume", "before_permission_consume", "scenario_dispatch"])
        prepare = next(step["operation"] for step in order["sequence"] if step["id"] == "prepare_reflection")
        self.assertIn("BEFORE and AFTER", prepare)
        self.assertIn("runtime ISSUED", prepare)
        self.assertEqual(order["between_runtime_consumption_and_dispatch"],
            self.requirement["activation_boundary"]["between_runtime_consumption_and_dispatch"])
        for key in ("launch_before_runtime_and_BEFORE_commits_allowed", "refund_after_runtime_consumption_allowed",
                    "future_order_is_current_execution_permission"):
            self.assertIs(order[key], False, key)
        self.assertIn("no refund, reopening, reissue or retry", order["launch_failure_or_postcommit_check_failure"])

    def test_runtime_readiness_is_unconditional_denial_before_terminal_publication(self):
        module = tree(RUNTIME)
        readiness = function(module, "_consumer_readiness")
        body = [node for node in readiness.body if not (isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str))]
        self.assertEqual(len(body), 1)
        self.assertIsInstance(body[0], ast.Expr)
        denial = body[0].value
        self.assertIsInstance(denial, ast.Call)
        self.assertEqual(ast.unparse(denial.func), "_fail")
        self.assertEqual(ast.literal_eval(denial.args[0]), "PROOF_UNRESOLVED")
        self.assertEqual(readiness.args.args, [])
        fail = function(module, "_fail")
        self.assertTrue(any(isinstance(item, ast.Raise) for item in fail.body))
        transition = function(module, "_transition")
        gate = condition(transition, "target == CONSUMED")
        self.assertEqual(len(gate.body), 1)
        self.assertEqual(ast.unparse(gate.body[0]), "_consumer_readiness()")
        publication = [item for item in ast.walk(transition) if isinstance(item, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "_STORE" for target in item.targets)]
        self.assertEqual(len(publication), 1)
        self.assertLess(gate.lineno, publication[0].lineno)
        self.assertEqual(ast.unparse(call(function(module,
            "consume_pinned_synthetic_runtime_execution_lease"), "_transition")),
            "_transition(lease, authorization, CONSUMED)")

    def test_reflection_issuance_requires_issued_and_consumption_requires_consumed_runtime(self):
        module = tree(REFLECTION)
        issue = function(module, "issue_pinned_synthetic_reflection_execution_lease")
        graph = call(issue, "_authenticate_graph")
        self.assertEqual({keyword.arg: ast.literal_eval(keyword.value) for keyword in graph.keywords},
            {"require_issued": True})
        guard = condition(issue, "_runtime_state(runtime, authorization) != ISSUED")
        self.assertEqual(ast.literal_eval(call(guard, "_fail").args[0]), "PINNED_RUNTIME_STATE_MISMATCH")
        transition = function(module, "_transition")
        guard = condition(transition, "target == CONSUMED and runtime_state != CONSUMED")
        self.assertEqual(ast.literal_eval(call(guard, "_fail").args[0]), "PINNED_RUNTIME_STATE_MISMATCH")
        sequence = literal(module, "EXECUTOR_SEQUENCE")
        self.assertEqual(sequence[2:4], ("consume pinned runtime lease", "consume BEFORE reflection lease"))
        for owner in (tree(RUNTIME), module):
            for name in ("ISSUED", "CONSUMED", "INVALIDATED"):
                # This owner's tuple assignment is intentionally inspected as AST.
                assignment = next(node for node in owner.body if isinstance(node, ast.Assign)
                    and any(isinstance(target, ast.Tuple) and any(isinstance(elt, ast.Name) and elt.id == name
                        for elt in target.elts) for target in node.targets))
                self.assertEqual(ast.literal_eval(assignment.value), ("ISSUED", "CONSUMED", "INVALIDATED"))
            condition(function(owner, "_transition"), "record.lifecycle_state != ISSUED")
            condition(function(owner, "_transition"), "type(target) is not str or target not in (CONSUMED, INVALIDATED)")

    def test_every_current_authority_is_false_and_effect_is_integer_zero(self):
        contract = self.contract
        for key in ("implementation_authorized", "owners_implemented", "capabilities_issued", "behavioral_activation_ready",
                    "runtime_consumption_ready", "harness_contract_complete",
                    "preparation_contract_complete_implies_harness_contract_complete"):
            self.assertIs(contract[key], False, key)
        self.assertEqual(contract["reason"], "PROOF_UNRESOLVED")
        self.assertIs(contract["stop_after_contract_closure"], True)
        self.assertTrue(contract["authority_flags"])
        for key, value in contract["authority_flags"].items():
            self.assertIs(value, False, key)
        self.assertTrue(set(self.previous["authority_flags"]) <= set(contract["authority_flags"]))
        self.assertEqual(set(contract["operational_effects"]), set(self.previous["operational_effects"]))
        for key, value in contract["operational_effects"].items():
            self.assertIs(type(value), int, key)
            self.assertEqual(value, 0, key)
        completion = contract["completion_rule"]
        self.assertEqual(completion["success"], contract["completion_marker"])
        self.assertIs(completion["source_contradiction_stops_closure"], True)
        self.assertIs(completion["validation_and_preservation_required"], True)
        self.assertIs(completion["stop_after_closure"], True)
        self.assertIsNone(completion["next_action_authorized"])
        self.assertFalse((ROOT / "core/synthetic_execution_preparation_pinned.py").exists())
        self.assertFalse((ROOT / "core/synthetic_execution_consumer_pinned.py").exists())

    def test_historical_supersession_is_preserved_and_not_extended(self):
        history = load(REFLECT)
        self.assertEqual(history["first_behavior_boundary"]["first_behavioral_effect"], "BEFORE exact read")
        supersessions = self.requirement["supersessions"]
        self.assertEqual(len(supersessions), 1)
        self.assertEqual(supersessions[0]["superseded_historical_artifact_path"], REFLECT)
        self.assertEqual(supersessions[0]["exact_superseded_key"], "first_behavior_boundary.first_behavioral_effect")
        preservation = self.contract["historical_preservation"]
        self.assertEqual(preservation, self.requirement["historical_preservation"])
        self.assertIs(preservation["historical_bytes_preserved"], True)
        for key in ("old_JSON_rewritten", "history_repinned", "retroactive_mutation", "old_requirement_globally_invalidated"):
            self.assertIs(preservation[key], False, key)

    def test_source_evidence_index_and_preservation_baseline_match_raw_history(self):
        index = json.loads((PHASE / "evidence_index.json").read_text(encoding="utf-8"))
        self.assertIs(index["owner_modules_imported"], False)
        self.assertIs(index["source_materialized"], False)
        required = {SOURCE, RUNTIME, ADMISSION, REFLECTION, PREP, REQ, REFLECT}
        self.assertTrue(required <= set(index["files"]))
        for relative, record in index["files"].items():
            with self.subTest(evidence=relative):
                data = (ROOT / relative).read_bytes()
                self.assertEqual(len(data), record["bytes"])
                self.assertEqual(sha256(data).hexdigest(), record["sha256"])
                lines = data.decode("utf-8").splitlines()
                for anchor in record["anchors"]:
                    self.assertIn(anchor["text"], lines[anchor["line"] - 1])
        baseline = json.loads((PHASE / "preservation_baseline.json").read_text(encoding="utf-8"))
        self.assertIs(baseline["links_followed"], False)
        self.assertEqual(baseline["file_count"], len(baseline["files"]))
        self.assertEqual(baseline["new_phase_excluded"].rstrip("/"), PHASE.relative_to(ROOT).as_posix())
        self.assertTrue(required <= set(baseline["files"]))
        for relative, before in baseline["files"].items():
            if not relative.startswith(("core/", "docs/", "scripts/")):
                continue
            with self.subTest(preserved=relative):
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
