from __future__ import annotations
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path
import re
import sys
OUTPUT = Path(__file__).resolve().parent
ROOT = OUTPUT.parents[3]
NEW_TEST = ROOT / 'tests/test_synthetic_reflection_pinned_contract.py'

def write_json(name, value):
    (OUTPUT / name).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n', encoding='utf-8')

def read(name):
    return json.loads((OUTPUT / name).read_text(encoding='utf-8'))

def tree(name):
    return ast.parse((ROOT / 'core' / (name + '.py')).read_text(encoding='utf-8'))

def function(module, name):
    return next((node for node in tree(module).body if isinstance(node, ast.FunctionDef) and node.name == name))

def calls(node):
    return {ast.unparse(item.func) for item in ast.walk(node) if isinstance(item, ast.Call)}

def source_checks():
    passed, failed = ([], [])

    def check(name, condition):
        (passed if condition else failed).append(name)
    primitive = 'synthetic_read_only_reflection'
    admission = 'synthetic_reflection_execution_admission'
    lifecycle = 'synthetic_reflection_execution_lifecycle'
    pinned = 'synthetic_runtime_authorization_pinned_lifecycle'
    request = next((node for node in tree(primitive).body if isinstance(node, ast.ClassDef) and node.name == 'SyntheticReflectionRequest'))
    fields = {node.target.id for node in request.body if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)}
    identity_fields = {name for name in fields if name not in {'runtime_authority', 'real_task_runtime_authority'}}
    check('old_request_payload_has_no_upstream_authorization_or_runtime_identity', fields and (not any(('authorization' in name or 'runtime' in name or 'provider' in name for name in identity_fields))))
    check('old_renderer_authenticates_only_independent_original_request', calls(function(primitive, 'render_synthetic_read_only_reflection')) == {'validate_synthetic_reflection_request'})
    check('old_auth_compatibility_keeps_unchanged_public_old_auth_validator', 'authorization_owner.validate_synthetic_runtime_authorization' in calls(function(primitive, 'synthetic_reflection_satisfies_authorization')))
    check('old_admission_authenticates_old_auth_and_original_request_publicly', {'authorization_owner.validate_synthetic_runtime_authorization', 'reflection_owner.validate_synthetic_reflection_request'} <= calls(function(admission, '_validate_upstream_pair')))
    admission_source = (ROOT / 'core' / (admission + '.py')).read_text(encoding='utf-8')
    check('old_admission_has_no_pinned_or_runtime_or_provider_bridge', not any((value in admission_source for value in ('synthetic_runtime_authorization_pinned', 'synthetic_runtime_authorization_lifecycle', 'runtime_java'))))
    pair = ast.unparse(function(admission, '_validate_upstream_pair'))
    check('old_admission_scope_preserves_invocation_observation_role_and_read_operation', all((value in pair for value in ('invocation.arguments', 'observation.roles', 'request.observation_role', 'request.operation'))))
    auth_record = ast.unparse(function(lifecycle, '_authenticated_record_locked'))
    check('old_reflection_original_record_and_signed_terminal_state_authentication', all((value in auth_record for value in ('record.lease_ref() is not lease', '_authenticate_inputs(', 'record.lifecycle_state not in (ISSUED, CONSUMED, INVALIDATED)', 'hmac.compare_digest'))))
    transition = ast.unparse(function(lifecycle, '_transition'))
    check('old_reflection_consumption_requires_consumed_runtime_but_invalidation_does_not', 'if target == CONSUMED:' in transition and '_runtime_state(runtime, authorization, CONSUMED)' in transition and ('target not in (CONSUMED, INVALIDATED)' in transition) and ('record.lifecycle_state != ISSUED' in transition))
    issue = ast.unparse(function(lifecycle, 'issue_synthetic_reflection_execution_lease'))
    check('old_reflection_permanent_one_admission_one_lease_tombstones', 'admission.admission_id in _ADMISSION_LEASES' in issue and '_ADMISSION_LEASES[admission.admission_id] = lease_id' in issue)
    readiness = ast.unparse(function(pinned, 'check_pinned_synthetic_runtime_execution_lease_preconditions'))
    check('pinned_runtime_keeps_false_behavioral_readiness_and_unresolved_consumer', 'record.lifecycle_state == ISSUED, False' in readiness and 'PROOF_UNRESOLVED' in ast.unparse(function(pinned, '_consumer_readiness')))
    result = {'passed': passed, 'failed': failed, 'passed_count': len(passed), 'owner_modules_imported': False, 'capability_objects_constructed': False, 'operational_effects_zero': True, 'success': not failed}
    write_json('frozen_source_checks.json', result)
    return result
if __name__ == '__main__':
    result = source_checks()
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['success'] else 1)
