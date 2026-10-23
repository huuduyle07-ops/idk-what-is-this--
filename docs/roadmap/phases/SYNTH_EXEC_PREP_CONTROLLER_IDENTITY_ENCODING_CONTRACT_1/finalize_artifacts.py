"""Assemble reviewable contract evidence; never implement or issue identities."""
from hashlib import sha256
import json
from pathlib import Path
import runpy

HERE = Path(__file__).resolve().parent
REPORT = "SYNTH_EXEC_PREP_CONTROLLER_IDENTITY_ENCODING_CONTRACT_1_REPORT.json"


def read(name):
    return json.loads((HERE / name).read_text(encoding="utf-8"))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True, ensure_ascii=True) + "\n", encoding="utf-8")


def assemble(counters, blocked):
    contract, projection, owners = (read(name) for name in
        ("contract.json", "budget_projection.json", "existing_owner_audit.json"))
    evidence = {name: read(name + ".json") for name in ("focused", "benchmark", "registry_baseline",
        "registry_after", "registry_comparison", "preservation_comparison", "static_validation", "git_validation")}
    assert evidence["focused"]["exit_code"] == 0
    assert evidence["focused"]["collected"] == evidence["focused"]["passed_count"]
    assert evidence["benchmark"]["exit_code"] == evidence["benchmark"]["benchmark_errors"] == 0
    assert evidence["registry_comparison"]["unchanged"]
    assert evidence["preservation_comparison"]["historical_preservation_passed"]
    assert evidence["static_validation"]["passed"]
    assert evidence["git_validation"]["baseline_vs_after_identical"]
    assert evidence["git_validation"]["git_diff_check_exit_code"] == 0
    assert evidence["git_validation"]["git_cached_diff_check_exit_code"] == 0
    review = read("contract_review.json")
    assert review["reviewed_snapshot_sha256"] == sha256((HERE / "contract.json").read_bytes()).hexdigest()
    assert not review["blocking_findings"]
    validator_hash = sha256((HERE / "validate_pure.py").read_bytes()).hexdigest()
    for name in ("focused", "benchmark", "registry_baseline", "registry_after"):
        value = evidence[name]
        assert value["all_operational_effects_zero"] and not value["blocked_actions"]
        assert not value["imported_capability_owners"] and not any(value["audit_guard"].values())
        assert value["validator_sha256"] == validator_hash
    assert not any(contract["authority_flags"].values()) and not any(contract["operational_effects"].values())
    summary = dict(typed_result=contract["typed_result"], created_at=contract["created_at"],
        all_required_checks_passed=True,
        focused_collected=evidence["focused"]["collected"], focused_passed=evidence["focused"]["passed_count"],
        benchmark_checked=evidence["benchmark"]["benchmark_cases_checked"], benchmark_errors=0,
        registry_collected=evidence["registry_after"]["collected"], registry_passed=evidence["registry_after"]["passed_count"],
        registry_existing_failures=len(evidence["registry_after"]["failed"]), registry_baseline_vs_after_identical=True,
        historical_files_preserved=evidence["preservation_comparison"]["baseline_file_count"],
        historical_preservation_passed=True, git_diff_check_passed=True,
        compiled_in_memory=evidence["static_validation"]["compiled_count"],
        all_operational_effects_zero=True, all_authority_flags_false=True,
        validator_sha256=validator_hash, finalizer_guard=counters, finalizer_blocked_actions=blocked,
        no_owner_or_identity_generator_implemented=True, historical_budget_proof_rerun=False)
    report = dict(contract, validation=summary, budget_width_substitution=projection,
        existing_owner_comparison=owners, independent_contract_review=review,
        independent_budget_report_review=read("report_review.json"))
    write("validation_summary.json", summary)
    write(REPORT, report)
    lines = ["# SYNTH.EXEC.PREP.CONTROLLER.IDENTITY.ENCODING.CONTRACT.1", "",
        "**" + contract["typed_result"] + "**", "",
        "Future owner/relation scalar IDs are non-secret opaque local handles for lookup, correlation and uniqueness. "
        "No scoped scalar is a bearer credential or authentication proof. This additive contract freezes future "
        "values inside the unchanged generic string schema. No owners or identity generators are implemented.", "",
        "The scalar grammar is one field-family prefix plus exactly 16 lowercase ASCII hexadecimal digits, "
        "with suffix value 1..9223372036854775807. Reject zero, uppercase, wrong prefix, alternate width, "
        "escapes in the decoded scalar, normalization and coercion. Each nonnull ID is exactly 17 content bytes "
        "and 19 canonical quoted JSON bytes; it has **zero required entropy bits** and is public. The frozen "
        "ensure_ascii=true encoding adds no escaping expansion for these values.", "",
        contract["encoding"]["capacity_rationale"], "",
        "All eight semantic classes independently use this allocation primitive and the same explicit capacity "
        "policy. Their roles, authenticated domains, aliases and lifetimes differ. Existing 64-hex digest/HMAC "
        "conventions are not used to determine handle width.", "",
        "Frozen source keys: " + "; ".join(key + " = `" + value + "`" for key, value in contract["sources"].items()) + ".", "",
        "| Semantic class | Field(s) | Prefix / suffix grammar | Content / quoted bytes | Role and lifetime |",
        "| --- | --- | --- | ---: | --- |"]
    for row in contract["identity_classes"]:
        lines.append("| " + row["class"] + " | " + ", ".join("`" + field + "`" for field in row["fields"]) +
            " | `" + row["regex"] + "`, nonzero suffix | 17 / 19 | " + row["role"] + " " + row["lifetime"] + " |")
    lines += ["", "All class grammars above are full-string matches with the additional shared positive-range predicate. "
        "Each inherits the generation, entropy, collision, case, secrecy, serialization, process-local namespace, "
        "owner/domain separation and terminal rules below.", "",
        "`process.admitted_operation_id`, `writer_handle.admitted_operation_id` and `active_operation_id` "
        "are nullable aliases of the exact already-bound `operation_id`; a nonnull projection allocates nothing. "
        "The two successful quiescent response layouts preserve their truthful nulls. Each JSON null costs four "
        "bytes. `writer.accounted_original_relation_id` references the actual authenticated original accounting "
        "relation; in this minimum layout it is the same exclusive-owner relation, never an invented writer ID.", "",
        "`authorized_borrower_relation_id` is an unestablished borrower relation and `handoff_identity` an "
        "unestablished handoff relation. Both mandatory keys are truthfully null on this minimum path. "
        "No nonnull grammar, borrower capability or handoff authenticator is invented.", "",
        "**Authentication and security responsibilities.** The original custom owner-object type is checked "
        "exactly, as are built-in schema scalar types. Registry identity, issuing process, original upstream graph, "
        "independent domain/role-separated HMAC over retained canonical bytes and current eligibility remain "
        "mandatory. The frozen controller contract explicitly says scalar admission ID is not authority "
        "(C:/authority_separation/scalar_admission_id_is_authority), and its generic id primitive is a reference "
        "only (C:/framing/primitive_rules/id). W:/exact_live_object and W:/authentication supply original-object, "
        "registry, PID, HMAC, fingerprint and permanent-tombstone requirements.", "",
        contract["authority_basis"]["wire_rule"], "", contract["authority_basis"]["trust_boundary_rule"], "",
        contract["authority_basis"]["threat_model_limit"], "",
        "| Threat | What encoding contributes | Mandatory protection outside the scalar |",
        "| --- | --- | --- |"]
    for row in contract["security_property_matrix"]:
        lines.append("| " + row["threat"] + " | " + row["encoding"] + " | " + "; ".join(row["enforcement"]) + " |")
    lines += ["", "**Generation and lifetime semantics.** These are declarative future obligations, tested by "
        "grammar/static/arithmetic fixtures. They are not live issuance tests or an allocator implementation.", ""]
    for key, value in contract["generation_semantics"].items():
        rendered = value if type(value) is str else json.dumps(value)
        lines.append("- **" + key.replace("_", " ") + ".** " + rendered)
    lines += ["", "No accidental-collision probability is needed for a correctly reserved nonwrapping sequence. "
        "These non-secret handles remain unsuitable for ID-only authorization; the frozen architecture requires "
        "the original-object/authenticated-owner conjunction. An unexpected duplicate is an invariant "
        "failure and must fail closed rather than overwrite a live or historical relation. Repeating textual "
        "strings in a new disjoint process incarnation is not namespace reuse or permission to restore old objects.", "",
        "`request_id` and `operation_id` require owner reservation, freshness, unique retained history, exact "
        "request/response equality and duplicate rejection, not cryptographic randomness. Caller-selected aliases "
        "are forbidden. The owning admission authenticates exact request/operation bindings. Lost mutation replies "
        "never authorize retry. The permanent attempt binds materialize through compile with no reopen, refund "
        "or attempt reuse. `deadline_identity` references the same authenticated immutable monotonic 5000ms "
        "attempt deadline from the frozen controller bounds; it never encodes a raw clock value or permits reset.", "",
        "**Controller and digest separation.** `controller_identity` references only the exact retained controller "
        "owner object. Its authenticated record still binds all C:/identity/must_bind facts. Stable implementation "
        "identity remains separate exact source bytes/hash/size, executable, interpreter, image, protocol and "
        "bootstrap/environment/policy. Incarnation remains separately bound by controller_generation and original "
        "process/channel facts; their encoders are untouched. Source hash, protocol ID, module name and PID "
        "cannot stand in for the owner-object handle.", "",
        "ID != stable_fingerprint != HMAC != capability. The separate stable fingerprint stays an unchanged "
        "64-lowercase-hex SHA256 digest of authenticated immutable identity; mutable current state/freshness "
        "needs its own authentication. A digest alone never restores original-object authority.", "",
        "**Existing owner comparison.** [Source audit](existing_owner_audit.md) and existing_owner_audit.json "
        "record exact generator, authentication, registry/tombstone anchors and source hashes. AST/source tests "
        "check these without importing the owners.", "",
        "| Existing family / variant | ID(s) | Existing generator / width | Why not mandatory for future handles |",
        "| --- | --- | --- | --- |"]
    for row in owners["owners"]:
        lines.append("| " + row["family"] + " / " + row["variant"] + " | " + ", ".join(row["ids"]) +
            " | token_hex(32), 64 ASCII bytes, 256 random bits | Separate original-object/registry/PID/graph/HMAC authentication remains required; historical random handle convention does not determine future scalar entropy. |")
    lines += ["", "Historical authorization/provider insertions do not all explicitly retry collisions, and weak "
        "registries alone do not retain permanent nonreuse. Those omissions are not adopted: future handles require "
        "atomic collision checks and permanent burned/tombstoned history. Existing owners remain byte-identical.", "",
        "**Owner-width-only budget substitution: CONDITIONAL.** Only frozen budget_witness.json data is read. "
        "BUDGET.PROOF.1R is not executed. The reference profile is candidate_A_writer_lower_widths_class_5_digits. "
        "Kernel identities and modes retain their previous unresolved lower-width placeholders. The reference "
        "writer topology and Candidate-A-only fixed container/generation/framing assumptions remain unchanged. "
        "All required nullable keys remain.", "",
        "| Family | Content bytes if nonnull | Materialize occurrences | Compile occurrences | Delta from one-byte relaxation |",
        "| --- | ---: | ---: | ---: | ---: |"]
    for row in read("budget_ledger_audit.json")["response_identity_ledger"]:
        lines.append(f'| {row["identity_family"]} | 17 | {row["materialize_occurrences"]} | {row["compile_occurrences"]} | {row["delta_from_one_byte_relaxation_bytes"]} |')
    lines += ["| process.admitted_operation_id | 17 | 0 nonnull, 1 null | 0 nonnull, 1 null | 0 |",
        "| writer_handle.admitted_operation_id | 17 | 0 nonnull, 2 null | 0 nonnull, 2 null | 0 |",
        "| active_operation_id | 17 | 0 nonnull, 1 null | 0 nonnull, 1 null | 0 |",
        "| authorized_borrower_relation_id | nonnull deferred | 1 null | 1 null | 0 |",
        "| handoff_identity | nonnull deferred | 1 null | 1 null | 0 |", "",
        "Admission IDs occur only in requests and contribute no response bytes. Request inputs remain in their "
        "own direction and add zero stdout bytes. The exclusive relation occurs four times including writer "
        "aliases. The 17 nonnull occurrences split 8 materialize / 9 compile; each grows by 16 bytes.", "",
        "| Conditional response accounting | Previous bytes | Owner delta | Projected bytes |",
        "| --- | ---: | ---: | ---: |",
        "| Materialize response | 3251 | 128 | 3379 |",
        "| Compile response | 4809 | 144 | 4953 |",
        "| Response payload sum | 8060 | 272 | 8332 |",
        "| Candidate-A-only response framing | 8 | 0 | 8 |",
        "| Candidate-A-only framed sum | 8068 | 272 | 8340 |", "",
        "**OWNER_ENCODING_ALONE_EXCEEDS_8192_FOR_CANDIDATE_A**, conditionally: remaining margin -148 bytes, "
        "excess 148 bytes. The unchanged formula is 8068 + 17*(17-1) = 8340. Uniform 32/64-byte "
        "sensitivity substitutions independently recover historical 8595/9139. Full field paths and exact "
        "substitution evidence are in budget_projection.json and budget_ledger_audit.json.", "",
        "This settles the scoped owner-encoding question only. It neither establishes an attainable successful "
        "execution witness nor proves universal budget feasibility/impossibility. Historical BUDGET_WITNESS_UNRESOLVED "
        "and its historical identity subresult are preserved as recorded. Kernel projection, complete inventory, "
        "physical mapping/framing and independent backend-generation cleanup remain separate blockers. "
        "Candidate A remains UNSELECTED. The 8192 cap and one-attempt scope are unchanged.", "",
        "**Validation.** Focused tests: " + str(summary["focused_passed"]) + "/" + str(summary["focused_collected"]) +
        "; benchmark --check: " + str(summary["benchmark_checked"]) + " cases, zero errors. Registry/picker "
        "baseline and after are identical: " + str(summary["registry_collected"]) + " collected, " +
        str(summary["registry_passed"]) + " passed, same " + str(summary["registry_existing_failures"]) +
        " pre-existing failures and normalized diagnostic signatures. In-memory compilation, JSON, authored "
        "whitespace and configured git diff --check pass. A supplementary check with autocrlf disabled records "
        "existing CRLF lines as whitespace diagnostics; it did not change configuration or files. Preservation "
        "hashes cover " + str(summary["historical_files_preserved"]) + " existing non-cache files with no changes, "
        "deletions or outside-phase additions. No stash/reset/clean, repin, schema edit or historical rewrite occurred.", "",
        "Validation host Python/Git invocations perform only the requested static checks; guarded validation starts "
        "no child process and imports no capability owners. All process/network/owner import/issuance/transition/"
        "execution/outside-phase-write audit counters are zero. All authority flags are false; all operational "
        "effect counts are zero. No Docker, live kernel inspection, target process, source materialization, "
        "javac/java, capability issuance or identity generation occurred. STOP.", ""]
    (HERE / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    (HERE / "README.md").write_text("# Future process-local identity encoding contract\n\n" + contract["typed_result"] +
        ". Read [REPORT.md](REPORT.md) for the classification/security matrices, grammar, generation semantics "
        "and conditional 8340-byte Candidate-A width projection. Normative data: contract.json. "
        "No owner/generator implementation or transport selection. All authority false; operational effects zero.\n", encoding="utf-8")
    checks = dict(python_compiled=[], json_validated=[], whitespace_errors=[])
    for path in HERE.rglob("*"):
        if not path.is_file() or "validation_tmp" in path.parts or path.suffix not in {".py", ".json", ".md"}:
            continue
        content = path.read_text(encoding="utf-8")
        if path.suffix == ".py":
            compile(content, str(path), "exec")
            checks["python_compiled"].append(path.relative_to(HERE).as_posix())
        elif path.suffix == ".json":
            json.loads(content)
            checks["json_validated"].append(path.relative_to(HERE).as_posix())
        checks["whitespace_errors"].extend(dict(file=path.relative_to(HERE).as_posix(), line=index)
            for index, line in enumerate(content.splitlines(), 1) if line.rstrip() != line)
    assert not checks["whitespace_errors"] and not any(counters.values()) and not blocked
    checks.update(passed=True, finalizer_guard=counters, finalizer_blocked_actions=blocked,
        report_sha256=sha256((HERE / "REPORT.md").read_bytes()).hexdigest())
    write("final_artifact_checks.json", checks)
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    validator = runpy.run_path(str(HERE / "validate_pure.py"))
    with validator["operational_guard"]() as (counters, blocked):
        assemble(counters, blocked)
