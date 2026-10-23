"""Finalize diagnostic artifacts from retained evidence; no runtime calls."""
import ast
from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


def write(name, value):
    (HERE / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n',
                            encoding='utf-8', newline='\n')


def source_function(path, name):
    tree = ast.parse((ROOT / path).read_text(encoding='utf-8'))
    return next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)


def preservation():
    baseline = read('preservation_baseline.json')['files']
    changed = [name for name, digest in baseline.items() if not (ROOT / name).is_file()
               or hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest]
    return {'files_checked': len(baseline), 'changed_or_missing': changed, 'passed': not changed}


def cell(value):
    if isinstance(value, (dict, list)):
        value = json.dumps(value, sort_keys=True)
    return str(value).replace('|', '\\|').replace('\n', ' ')


def table(headers, rows):
    return '\n'.join(['| ' + ' | '.join(headers) + ' |',
                     '| ' + ' | '.join('---' for _ in headers) + ' |'] +
                    ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows])


result = read('RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json')
pure = read('pure_matrix.json')
observer = read('observer_checks.json')
restricted = read('post_observation_restricted.json')
host = read('post_observation_host.json')
image = read('post_exact_image_observation.json')
java = read('JAVA1C_standalone_report.json')
sandbox = read('SANDBOX2_observed_report.json')
controls = read('observed_controls.json')
context = read('context_comparison.json')
ledger = read('predicate_ledger.json')

# The original owner reports and original observation are retained unchanged.
result['original_owner_cleanup_proof_unavailable'] = not result['cleanup']['owner_cleanup_verified']
result['cleanup']['in_attempt_remaining_phase_containers'] = java['phase_container_count_after_teardown']
result['cleanup']['independent_post_attempt_phase_container_observation'] = host['phase_containers']
result['cleanup']['remaining_phase_containers'] = host['phase_containers']['count']
result['cleanup']['owner_cleanup_proof_status'] = 'UNAVAILABLE_DOCKER_PIPE_PERMISSION_DENIED'
result['cleanup']['post_observation_private_config_paths_absent'] = all(
    row['config_absent_before'] and row['config_absent_after'] for row in (restricted, host, image))
result['cleanup']['post_observation_controls_reaped_and_pipes_closed'] = (
    restricted['processes_reaped_and_pipes_closed'] and host['processes_reaped_and_pipes_closed']
    and image['process_reaped_and_pipes_closed'])
result['cleanup']['independent_final_cleanup_verified'] = (
    host['phase_containers']['count'] == 0
    and all(result['cleanup'][k] is True for k in ('all_host_controls_reaped',
        'all_host_control_pipes_closed', 'all_private_config_paths_absent', 'observer_restored',
        'temporary_workspace_removed', 'post_observation_private_config_paths_absent',
        'post_observation_controls_reaped_and_pipes_closed'))
    and result['cleanup']['surviving_host_readers'] == 0)
result['cleanup']['passed'] = result['cleanup']['independent_final_cleanup_verified']
result['cleanup_failure_separate_from_diagnosis'] = not result['cleanup']['passed']
result['diagnostic_execution_context_limit'] = {
    'standalone_context': 'Restricted tool process, with no preexisting profiler/tracer/monitoring.',
    'observed_in_attempt_exact_image_inspect_exit_code': controls[0]['exit_code'],
    'original_control_stderr_retained': False,
    'restricted_post_observation_error': restricted['exact_image']['stderr'],
    'post_host_exact_image_metadata': image['metadata'],
    'attribution': 'The permitted standalone attempt was obstructed before SANDBOX.2 ladder creation. '
        'A separate read-only observation demonstrated Docker pipe permission denial in the restricted '
        'execution context; the host observation reached the exact expected image. The original control '
        'stderr was not retained, so the permission-denial attribution is corroborating follow-up evidence, '
        'not a verbatim in-attempt stderr measurement.',
    'second_standalone_owner_invocation': False,
    'historical_nested_deeper_cause_established': False,
    'historical_limit': 'The frozen nested attempt recorded successful exact-image inspection, unlike this '
        'restricted standalone attempt. Its SANDBOX.2 pre-ladder metadata/workspace/socket failure remains '
        'unresolved because its live report and pair were not retained. Do not attribute it to this new '
        'permission denial.'}
result['first_failing_predicate'] = result['predicate_decomposition']['first_failing_predicate']
result['not_reached_predicates'] = result['predicate_decomposition']['not_reached_predicates']
result['demonstrated_HMAC_failure'] = result['fresh_SANDBOX2_pair']['demonstrated_HMAC_failure']
result['nested_context_sensitivity_status'] = 'NOT_ESTABLISHED; standalone was environment limited'
result['underlying_standalone_failure'] = {
    'owner': 'core.thread_compatible_runtime_sandbox.replay',
    'error': sandbox['controller_error'], 'exact_image_control_exit_code': controls[0]['exit_code'],
    'verification_ladder_started': False, 'stages': [],
    'failure_before_SANDBOX2_pair_issuance': False,
    'explanation': 'SANDBOX.2 still issued signed blocked infrastructure evidence after its image gate '
        'failed. JAVA.1C authenticated that evidence, then rejected its blocked status at its first '
        'semantic predicate.'}
result['operational_effects'].update(
    post_attempt_read_only_Docker_controls=5, total_Docker_controls=8,
    pure_fixture_Python_domain_children=pure['effect_counts']['python_domain_child'])
result['post_observation_errors'] = {
    'restricted': restricted['exact_image']['stderr'],
    'host_initial_format': host['exact_image']['stderr'],
    'host_format_corrected': image['stderr'],
    'explanation': 'The initial read-only host image output filter used a missing optional Volumes key. '
        'The corrected read-only filter used index and passed; both artifacts are retained.'}
result['historical_preservation'] = preservation()
result['validation_summary'] = {'pure_fixture_matrix_passed': pure['passed'],
    'pure_fixture_cases': pure['case_count'], 'all_frozen_rejection_terms_covered': pure['all_rejection_terms_covered'],
    'exact_rejection_terms': len(ledger), 'authority_subpredicates': 14,
    'pure_Docker_effects': pure['effect_counts']['docker'], 'pure_Java_effects': pure['effect_counts']['java'],
    'observer_self_checks_passed': observer['passed'],
    'live_observer_restored': result['cleanup']['observer_restored'],
    'owner_functions_and_code_identities_unchanged': not result['owner_mutation_occurred'],
    'historical_bytes_preserved': result['historical_preservation']['passed'],
    'single_live_attempt_only': result['standalone_invocations'] == 1,
    'remaining_containers_independently_verified_zero': host['phase_containers']['count'] == 0}
if (HERE / 'validation_summary.json').is_file():
    result['validation_summary']['final_artifact_checks'] = {
        'passed': read('validation_summary.json')['passed'], 'artifact': 'validation_summary.json'}

pre = []
def pre_row(order, owner, source, line, expression, meaning):
    pre.append({'order': order, 'owner': owner, 'source': source, 'line': line,
                'expression': expression, 'meaning': meaning,
                'fields_inputs_consumed': expression, 'field_owner': owner,
                'check_category': 'policy_identity' if 'policy' in expression.lower() else
                    'image_identity_or_eligibility' if 'metadata' in expression or 'image.' in expression else
                    'cleanup_and_completion' if 'cleanup' in expression or 'verdict' in expression else
                    'owner_operation_or_transport'})

s2path = 'core/thread_compatible_runtime_sandbox.py'
jpath = 'core/sandboxed_java_positive_continuation.py'
replay = source_function(s2path, 'replay')
policy_call = next(n for n in ast.walk(replay) if isinstance(n, ast.Expr)
                  and ast.unparse(n).startswith('validate_policy_bytes('))
metadata_assign = next(n for n in ast.walk(replay) if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == 'metadata' for t in n.targets))
image_gate = next(n for n in ast.walk(replay) if isinstance(n, ast.If)
    and any(isinstance(c, ast.Raise) and 'exact_local_java_image_required' in ast.unparse(c) for c in n.body))
pre_row(1, 'SANDBOX.2', s2path, policy_call.lineno, ast.unparse(policy_call),
        'Disk policy validator uses the same four policy rejection terms as the canonical bytes check in the pair ledger.')
pre_row(2, 'SANDBOX.2', s2path, metadata_assign.lineno, ast.unparse(metadata_assign.value.test),
        'Capture status and exit code select parsed metadata or empty dict. In this attempt status was sandbox_completed and exit code was 1, so metadata was empty.')
for term in image_gate.test.values:
    pre_row(len(pre) + 1, 'SANDBOX.2', s2path, term.lineno, ast.unparse(term),
        'Exact local image eligibility gate before any ladder container; rejection raises exact_local_java_image_required.')
stage_gate = next(n for n in ast.walk(replay) if isinstance(n, ast.If) and ast.unparse(n.test) == 'verdict != PASSED')
pre_row(len(pre) + 1, 'SANDBOX.2', s2path, stage_gate.lineno, "if verdict != PASSED: result['status'] = verdict; break",
        'Fixed eleven-stage ladder stops at first nonpassed verdict; all stages must pass for COMPLETE.')
cleanup_assign = next(n for n in ast.walk(replay) if isinstance(n, ast.Assign)
                     and any(ast.unparse(t) == "result['cleanup_verified']" for t in n.targets))
pre_row(len(pre) + 1, 'SANDBOX.2', s2path, cleanup_assign.lineno,
        "count == 0 and result.get('temporary_workspace_removed') is True and all(s['cleanup_verified'] for s in result['stages'])",
        'Final cleanup produces the boolean bound into the receipt; stage evidence can never bless unverified cleanup.')
evidence = source_function(s2path, '_evidence_pair')
guard = next(n for n in evidence.body if isinstance(n, ast.If))
pre_row(len(pre) + 1, 'SANDBOX.2', s2path, guard.lineno, ast.unparse(guard.test),
        'COMPLETE-only evidence guard. Blocked outcomes are signed too and derive eligible=False/classification blocked_no_java_capability.')
pre_row(len(pre) + 1, 'JAVA.1C', jpath, 76, 'sandbox2.validate_policy_bytes(sandbox2.POLICY_PATH.read_bytes())',
        'The frozen owner checks disk bytes again after replay and before constructing its consumed pair.')
pre_row(len(pre) + 1, 'SANDBOX.2 called by JAVA.1C', jpath, 77, 'sandbox2._evidence_pair(live)',
        'Constructs the second signed pair in the same process; the observer captures this exact pair at authenticate call entry.')
static = {'pre_pair_flow': pre, 'pair_acceptance_predicates': ledger,
    'ordering': 'JAVA.1C _obtain_live_sandbox2: replay, disk-policy validation, issuer evidence-pair guard, '
        'authenticate_sandbox2 ordered ledger, then postauth fingerprint/digest/cleanup ledger. verify repeats '
        'authenticate_sandbox2 only after _obtain returns. It was NOT_REACHED in this live attempt.',
    'public_authentication_and_semantics_distinct': True,
    'absent_predicates': pure['not_applicable'],
    'issuer_guard_terms': [{'expression': ast.unparse(n), 'source': s2path, 'line': n.lineno}
        for n in ast.walk(guard.test) if isinstance(n, (ast.Compare, ast.UnaryOp))],
    'source_hashes': pure['owner_sources_sha256']}
write('static_predicate_audit.json', static)
write('RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json', result)

pair = result['fresh_SANDBOX2_pair']
d = pair['descriptor']['signed_public_fields']
r = pair['receipt']['signed_public_fields']
parts = ['# RUNTIME.JAVA.1C.AUTH.DIAG.1 — fresh SANDBOX.2 pair authentication diagnostic',
    '', '2026-10-10 KST. **JAVA1C_AUTH_DIAG_COMPLETE_WITH_FINDING**. Diagnostic only; no authority issued.', '',
    'The sole standalone invocation authenticated the exact original SANDBOX.2 descriptor and receipt '
    'and rejected their semantic eligibility. The first failure was `descriptor_status_complete`: '
    '`descriptor.status != sandbox2.COMPLETE` was true. The pair carried '
    '`RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED`, `eligible_for_java1_continuation=false`, '
    '`blocked_no_java_capability`, cleanup=false and an empty ladder. Both HMACs passed; '
    '**demonstrated_HMAC_failure=false**.', '',
    'The SANDBOX.2 owner reported `ValueError: exact_local_java_image_required`. Its image-inspection '
    'control exited 1 before workspace creation or any verification stage. A separate read-only '
    'restricted-context check demonstrated permission denial at the local Docker pipe; a host-context '
    'check verified the exact expected Linux/amd64 image with no volumes and zero phase containers. '
    'The original control stderr was not retained, so permission denial is corroborating follow-up '
    'evidence, not a verbatim in-attempt stderr capture.', '',
    '**Historical limit:** this does not establish the older nested attempt’s deeper cause. That frozen '
    'attempt’s image inspection succeeded and its SANDBOX.2 report was not retained. Its rejection was '
    'also semantic by source order, but the underlying pre-ladder failure remains unresolved. '
    'Standalone did not pass; `STANDALONE_PASS_CONTEXT_SENSITIVE` does not apply. No second issuance '
    'was performed, including outside the restricted environment.', '',
    '## Result and exact original pair', '',
    table(['Item', 'Observation'], [
        ['Final diagnostic status', result['status']], ['Classification', result['classification']],
        ['Standalone JAVA.1C', result['standalone_JAVA1C_status']],
        ['JAVA.1C controller error', java['controller_error']], ['SANDBOX.2 status', sandbox['status']],
        ['First failed predicate', result['first_failing_predicate']],
        ['Public SANDBOX.2 receipt/descriptor authentication', 'PASS / PASS'],
        ['Receipt HMAC / descriptor HMAC', 'PASS / PASS'], ['demonstrated_HMAC_failure', False],
        ['Semantic eligibility flag', pair['semantic_eligibility']],
        ['Standalone passed / nested context sensitivity', 'false / NOT_ESTABLISHED'],
        ['Historical deeper cause established', False], ['Observer issuing process PID', pair['observed_pid']],
        ['Descriptor exact type', pair['descriptor']['exact_type']],
        ['Descriptor original object identity', pair['descriptor']['object_id_hex']],
        ['Receipt exact type', pair['receipt']['exact_type']],
        ['Receipt original object identity', pair['receipt']['object_id_hex']],
        ['Owner-exposed issuing PID', 'Absent; observer process PID is provenance, not an owner field'],
        ['Phase / schema', d['phase_id'] + ' / ' + d['schema_version']],
        ['Policy SHA', d['seccomp_policy_sha256']], ['Image identity', d['image_identity']],
        ['Descriptor fingerprint', d['sandbox_descriptor_fingerprint']],
        ['Receipt fingerprint and descriptor receipt binding', r['verification_receipt_fingerprint']],
        ['Receipt evidence digest (hash of empty stages)', r['evidence_sha256']],
        ['Receipt cleanup / classification', str(r['cleanup_verified']) + ' / ' + r['compatibility_classification']],
        ['Registry membership', pair['registry_membership']],
        ['All seven authority fields on each object', 'false, recorded in fresh_pair_observation.json'],
        ['Original objects serialized/reconstructed before validation', False],
        ['Signature/key material exported', False],
    ]), '',
    '[Full JSON report](RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json), '
    '[original pair observation](fresh_pair_observation.json), '
    '[unchanged JAVA.1C owner report](JAVA1C_standalone_report.json), '
    '[retained SANDBOX.2 owner report](SANDBOX2_observed_report.json).', '',
    '## Static audit and actual ordered predicate decomposition', '',
    'Rejection expressions below are extracted from the frozen source. PASS means the expression '
    'was false and the gate continued. FAIL means it was true and short circuited. Later terms are '
    'NOT_REACHED even where independent read-only inspection exposes their field values. The '
    '14 authority subpredicates run descriptor first, then receipt, in SANDBOX.2.AUTHORITIES order.', '',
    table(['Order', 'Owner', 'Source', 'Exact pre-pair condition / operation'],
        [[row['order'], row['owner'], row['source'] + ':' + str(row['line']), row['expression']] for row in pre]), '',
    table(['Order', 'Predicate', 'Inputs', 'Field owner / category', 'Rejection expression', 'Result'],
        [[i + 1, row['predicate'], row.get('fields_inputs_consumed', ''),
          str(row.get('field_owner', row['component'])) + ' / ' + str(row.get('check_category', '')),
          row['rejection_expression'], row['state']]
         for i, row in enumerate(result['predicate_decomposition']['ordered_predicates'])]), '',
    'All authority subpredicates were NOT_REACHED in the live invocation: '
    '`descriptor.runtime_authority`, `descriptor.repository_write_authority`, `descriptor.apply_authority`, '
    '`descriptor.shell_available`, `descriptor.arbitrary_command_authority`, `descriptor.host_mount_authority`, '
    '`descriptor.network_authority`, followed by the same seven receipt fields. The exact subpredicate '
    'metadata is retained in the JSON ledger.', '',
    'The initial public receipt/descriptor validator contains semantic consistency checks as well as '
    'type/HMAC authentication: matching receipt fingerprint, status and eligibility relation. Its '
    '`*_unauthenticated` error therefore also must not be interpreted as a cryptographic diagnosis '
    'without decomposition. The later JAVA.1C branch raises '
    '`java1c_live_sandbox2_binding_rejected`; the still later report-binding branch raises '
    '`java1c_live_sandbox2_fingerprint_mismatch`. Frozen `verify` maps all of those pre-controller '
    'exceptions to its initialized `not_authenticated` reason.', '',
    'There is no original-object identity, issuing-PID or registry predicate. Phase/schema are '
    'included in the signed payload but have no independent equality predicate. Signed same-value '
    'copies pass. Unsigned phase/schema changes fail HMAC; controlled re-signed fixture changes '
    'pass. A fresh interpreter has a new module-local HMAC domain; PID itself is not checked, '
    'and a fork-inherited key would be a different scenario from the tested fresh interpreter.', '',
    '[Exact static flow and predicate metadata](static_predicate_audit.json), '
    '[pair ledger](predicate_ledger.json).', '',
    '## Pure fixture matrix and validation', '',
    f'All **{pure["case_count"]} fixture expectations passed**, covering all {len(ledger)} rejection '
    'expressions and all 14 authority fields. Independent AST probes cover dominated/repeated '
    'expressions and constant policy comparisons without replacing owner functions or constants. '
    'Controlled fixture signing never supplied live authority.', '',
    'The matrix covers valid originals; descriptor/receipt copies; wrong pairs and exact types; '
    'wrong process; phase/schema; policy and image; receipt/report fingerprints; evidence digest; '
    'cleanup; eligibility/status/classification/stage order; signatures; authorities; and explicit '
    'nonapplicability of registry/object/PID predicates. One exact Python-only child tested the '
    'fresh-process HMAC domain. Pure Docker, Java, shell and socket effects were zero.', '',
    'Observer self-tests retained the exact fixture objects, rejected existing system profiling '
    'and tracing, restored instrumentation and preserved owner functions. Runtime entry rejects '
    'system/thread profiling, tracing and occupied monitoring slots. The live observer reads only '
    'fixed code-object argument/return frames; it does not assign frame locals, owner functions, '
    'receipts or returns. Owner object identities, function code identities and public policy '
    'hashes stayed unchanged. Original live objects were used for public validators and direct '
    'HMAC checks before report serialization.', '',
    '[Full fixture evidence](pure_matrix.json), [observer checks](observer_checks.json), '
    '[final artifact consistency, compilation, JSON and link checks](validation_summary.json).', '',
    '## Process state and historical context', '',
    'No preexisting system/thread profiler, tracer or monitoring tool was present. Only this '
    'diagnostic’s profile observer was installed during the sole call; all instrumentation was '
    'restored afterward. Before/after module identities, entry-function/code identities, current '
    'PID, tempfile global and authentication-domain identity class are in the full report. No '
    'SANDBOX.2 registry exists, so registry sizes/identities are not applicable. No HMAC keys or '
    'signatures were dumped.', '',
    'The successful historical retry and blocked nested SYNTH path share five frozen owner source '
    'hashes. Both used the provider’s return-frame profiler; the successful retry additionally '
    'used a private-config tracer and a different phase-local temporary root. The upstream '
    'transport wrappers are lexically scoped and end before JAVA.1C; static evidence does not '
    'establish residue. Profiler presence alone is not a demonstrated cause. The older nested '
    'control record has successful exact-image inspection and zero SANDBOX.2 creates. Those '
    'facts bound its missing failure to pre-ladder work but cannot select metadata, temporary '
    'workspace or socket setup as the exact cause.', '',
    '[Pure/static context comparison](context_comparison.md), '
    '[source-hash comparison evidence](context_comparison.json).', '',
    '## Operational effects, cleanup and preservation', '',
    table(['Effect', 'Count'], [[k, v] for k, v in result['operational_effects'].items()]), '',
    'The Docker controls comprise three controls in the original owner invocation and five '
    'separate post-attempt read-only exact-image/phase-container observations. None created '
    'containers. Zeroes are supported by frozen source hashes, observed original argv/scope, '
    '`shell=False`, absence of create/start commands and zero observed forbidden owner calls; '
    'they are not an OS-wide event-tracing claim. All runtime authority fields remain false.', '',
    'The original owner cleanup proof was unavailable because both in-attempt container listings '
    'exited 1; their remaining counts are null and their original cleanup flags remain false in '
    'the raw reports. A separate host read-only phase-filtered listing verified **zero remaining '
    'containers**. All original controls were reaped, all pipes closed, zero host readers '
    'survived, all generated private Docker config paths remained absent, no temporary workspace '
    'was created, and the observer was restored. The post-observation controls were also reaped '
    'and their private config paths remained absent. Independent final cleanup passed; no '
    'residual cleanup failure was measured.', '',
    'The first host image-output filter failed on a missing optional Volumes key. Its artifact '
    'was retained; a corrected read-only filter passed. This was a reporting correction, not '
    'another owner invocation.', '',
    f'All **{result["historical_preservation"]["files_checked"]} frozen existing files** retain their '
    'baseline bytes. JAVA.1C and SANDBOX.2 sources, PINNED phases/retry artifacts, SYNTH blocked '
    'attempt/source/contracts, lifecycle/reflection/EXECUTOR owners and history, registry and '
    'reversal artifacts were preserved. Existing worktree changes were neither repinned nor '
    'reverted. No stash/reset/clean was used. Only this new diagnostic folder was authored.', '',
    '[Control observations](observed_controls.json), '
    '[restricted read-only follow-up](post_observation_restricted.json), '
    '[host zero-container observation](post_observation_host.json), '
    '[corrected exact-image observation](post_exact_image_observation.json), '
    '[preservation baseline](preservation_baseline.json).', '',
    '**STOP boundary:** no owner remediation, synthetic authorization retry, execution lease, '
    'reflection, SyntheticStateBox, BANK, EXECUTOR.1R, runtime grant or provider-root issuance. '
    'Exactly one standalone JAVA.1C diagnostic call was made.']
(HERE / 'RUNTIME_JAVA_1C_AUTH_DIAG_1.md').write_text('\n'.join(parts) + '\n', encoding='utf-8', newline='\n')
(HERE / 'README.md').write_text(
    '# RUNTIME.JAVA.1C.AUTH.DIAG.1\n\n'
    '[Diagnostic report](RUNTIME_JAVA_1C_AUTH_DIAG_1.md) · '
    '[Full measured JSON](RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json)\n\n'
    'One standalone attempt; original SANDBOX.2 HMACs pass, first semantic status predicate fails. '
    'Restricted Docker transport obstructed the attempt; historical nested deeper cause remains unresolved. '
    'No remediation or authority issuance.\n', encoding='utf-8', newline='\n')
print(json.dumps({'status': result['status'], 'first_failing_predicate': result['first_failing_predicate'],
                  'demonstrated_HMAC_failure': result['demonstrated_HMAC_failure'],
                  'remaining_containers': result['cleanup']['remaining_phase_containers'],
                  'historical_preservation': result['historical_preservation'],
                  'historical_nested_deeper_cause_established': False}))
