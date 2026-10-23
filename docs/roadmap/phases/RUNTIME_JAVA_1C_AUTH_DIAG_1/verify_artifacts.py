"""Read-only consistency checks of the retained diagnostic, no owner imports."""
import ast
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def read(name):
    return json.loads((HERE / name).read_text(encoding='utf-8'))


r = read('RUNTIME_JAVA_1C_AUTH_DIAG_1_REPORT.json')
j = read('JAVA1C_standalone_report.json')
s = read('SANDBOX2_observed_report.json')
p = read('pure_matrix.json')
pair = read('fresh_pair_observation.json')
marker = read('LIVE_ATTEMPT_STARTED.json')
ledger = read('predicate_ledger.json')
assert r['status'] == 'JAVA1C_AUTH_DIAG_COMPLETE_WITH_FINDING'
assert r['classification'] == 'SEMANTIC_ELIGIBILITY_FAILURE'
assert r['first_failing_predicate'] == 'descriptor_status_complete'
assert r['standalone_invocations'] == 1 and marker['maximum_standalone_invocations'] == 1
assert marker['pid'] == pair['observed_pid'] == r['process_state_before']['current_pid']
assert r['process_state_before']['current_pid'] == r['process_state_after']['current_pid']
assert all(value is False for value in r['process_state_before']['instrumentation'].values())
assert all(value is False for value in r['process_state_after']['instrumentation'].values())
assert r['process_state_before']['owner_entry_points'] == r['process_state_after']['owner_entry_points']
assert not r['owner_mutation_occurred'] and not r['JAVA1C_source_changed'] and not r['SANDBOX2_source_changed']
assert not r['SYNTH_authorization_retried'] and not r['provider_root_issued']
assert not r['forbidden_owner_calls_observed'] and not r['observer_callback_errors'] and not r['diagnostic_errors']
assert pair['HMAC_results'] == {'descriptor': True, 'receipt': True}
assert r['demonstrated_HMAC_failure'] is pair['demonstrated_HMAC_failure'] is False
assert pair['public_validators']['descriptor_and_pair']['result'] == 'PASS'
assert pair['public_validators']['JAVA1C_semantic_gate']['error'] == 'java1c_live_sandbox2_binding_rejected'
assert not pair['semantic_eligibility']
d, receipt = pair['descriptor']['signed_public_fields'], pair['receipt']['signed_public_fields']
assert d['status'] == receipt['status'] == s['status'] == 'RUNTIME_SANDBOX_2_BLOCKED_UNRESOLVED'
assert d['verification_receipt_fingerprint'] == receipt['verification_receipt_fingerprint']
assert receipt['stage_results'] == s['stages'] == []
assert receipt['evidence_sha256'] == hashlib.sha256(b'[]').hexdigest()
assert receipt['cleanup_verified'] is False
assert j['cleanup_verified'] is s['cleanup_verified'] is False
assert j['phase_container_count_after_teardown'] is s['phase_container_count_after_teardown'] is None
assert r['cleanup']['in_attempt_remaining_phase_containers'] is None
assert r['cleanup']['remaining_phase_containers'] == 0
assert r['cleanup']['independent_final_cleanup_verified'] is True
assert not r['diagnostic_execution_context_limit']['historical_nested_deeper_cause_established']
assert r['nested_context_sensitivity_status'].startswith('NOT_ESTABLISHED')
rows = r['predicate_decomposition']['ordered_predicates']
first_index = next(i for i, row in enumerate(rows) if row['state'] == 'FAIL')
assert rows[first_index]['predicate'] == 'descriptor_status_complete'
assert all(row['state'] == 'PASS' for row in rows[:first_index])
assert all(row['state'] == 'NOT_REACHED' for row in rows[first_index + 1:])
assert len(r['not_reached_predicates']) == 16
assert len(ledger) == 28 and all(row['field_owner'] and row['fields_inputs_consumed'] and row['check_category'] for row in ledger)
authorities = next(row for row in ledger if row['predicate'] == 'all_authorities_false')['ordered_authority_subpredicates']
assert len(authorities) == 14
for row in authorities:
    assert (d if row['object'] == 'descriptor' else receipt)[row['field']] is False
assert p['passed'] and p['case_count'] == 57 and all(case['expectation_passed'] for case in p['cases'])
assert p['all_rejection_terms_covered'] and p['owner_functions_unchanged']
assert p['effect_counts'] == {'python_domain_child': 1, 'docker': 0, 'java': 0,
    'caller_shell': 0, 'socket': 0, 'other_process': 0, 'forbidden_attempts': 0}
assert r['operational_effects']['Docker_controls'] == 3
assert r['operational_effects']['post_attempt_read_only_Docker_controls'] == 5
assert r['operational_effects']['total_Docker_controls'] == 8
baseline = read('preservation_baseline.json')['files']
assert all((ROOT / name).is_file() and hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
           for name, digest in baseline.items())
files = list(HERE.iterdir())
python_files, json_files, markdown_links = 0, 0, 0
for path in files:
    if not path.is_file():
        continue
    text = path.read_text(encoding='utf-8')
    if path.suffix in ('.py', '.md', '.json'):
        assert not any(line != line.rstrip() for line in text.splitlines()), 'authored trailing whitespace: ' + path.name
    if path.suffix == '.py':
        compile(text, str(path), 'exec')
        python_files += 1
    if path.suffix == '.json':
        json.loads(text)
        json_files += 1
    if path.suffix == '.md':
        for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)', text):
            if target.startswith(('https:', 'http:')):
                continue
            target = re.sub(r':\d+$', '', target.split('#')[0])
            assert (HERE / target).exists(), 'broken link: ' + target
            markdown_links += 1
diagnostic = ast.parse((HERE / 'diagnostic.py').read_text(encoding='utf-8'))
verify_calls = [node for node in ast.walk(diagnostic) if isinstance(node, ast.Call)
    and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name)
    and node.func.value.id == 'java' and node.func.attr == 'verify']
assert len(verify_calls) == 1
result = {'passed': True, 'historical_files_preserved': len(baseline),
    'diagnostic_python_sources_compiled_in_memory': python_files, 'JSON_artifacts_parsed': json_files,
    'markdown_links_checked': markdown_links, 'authored_whitespace_passed': True,
    'live_owner_invocations': 0, 'Docker_controls': 0, 'Java_effects': 0,
    'evidence_consistency_passed': True, 'single_effectful_call_site_and_exclusive_marker': True}
(HERE / 'validation_summary.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n',
    encoding='utf-8', newline='\n')
print(json.dumps(result))
