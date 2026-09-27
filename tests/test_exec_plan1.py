"""EXEC-01 red/green, zero mutation preparation, and verified local recovery."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import socket
import stat
import threading
import types
from dataclasses import FrozenInstanceError
from pathlib import Path
from unittest.mock import Mock

import pytest

from patching import patch_plan_executor as executor
from patching import patch_plan_transaction as transaction
from tests.test_harness_blackbox_http import harness

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    def deny(*args, **kwargs):
        raise AssertionError('EXEC.PLAN.1 forbids external network')
    monkeypatch.setattr(socket.socket, 'connect', deny)
    monkeypatch.setattr(socket, 'create_connection', deny)


def create(path='created.txt', content='partial write\n'):
    return {'op': 'create_file', 'relative_path': path, 'content': content}


def replace(path='a.txt', old='old', new='new'):
    return {'op': 'replace_snippet', 'relative_path': path,
            'target_snippet': old, 'patched_snippet': new}


def tree(root):
    return {p.relative_to(root).as_posix(): p.read_bytes() if p.is_file() else None
            for p in root.rglob('*')}


def mutation_spy(monkeypatch):
    spy = Mock(side_effect=AssertionError('mutation before complete preparation'))
    for method in ('write_bytes', 'mkdir', 'unlink', 'rmdir', 'chmod'):
        monkeypatch.setattr(Path, method, spy)
    return spy


def assert_rejected(result, spy, code='invalid_plan_schema'):
    assert result['success'] is False and result['code'] == code
    assert result['mutation_attempted'] is False
    assert result['recovery_attempted'] is False
    assert result['rollback_performed'] is False
    assert result['remaining_changed_paths'] == []
    assert spy.call_count == 0
    json.dumps(result)


def post(harness, plan, endpoint='/apply_patch_plan'):
    return harness.client.post(endpoint, headers=harness.headers, data={
        'repo_path': str(harness.repo), 'patch_style': 'balanced', 'apply_policy': 'ask',
        'patch': json.dumps({'patch_basis': 'explicit_change_request', 'patch_plan': plan}),
    })


def test_exact_audit_pre_http500_and_partial_file(harness, monkeypatch):
    from tests._exec_plan1_maintenance import before_exec_plan1
    from web import app as wa
    from web.routes import patch_routes
    from core import run_lifecycle
    old_source = before_exec_plan1('patching/patch_plan_executor.py')
    assert hashlib.sha256(old_source).hexdigest() == 'b1a874c1de5818c80981bd2eb27f996e4d252f7728421d6d38a84427b0b75222'
    old = types.ModuleType('_exec_plan1_original_executor')
    exec(compile(old_source, old.__name__, 'exec'), old.__dict__)
    route_tree = ast.parse(before_exec_plan1('web/routes/patch_routes.py'))
    route = next(n for n in route_tree.body if isinstance(n, ast.FunctionDef) and n.name == 'apply_patch_plan_route')
    route.decorator_list = []
    namespace = dict(patch_routes.__dict__)
    exec(compile(ast.Module(body=[route], type_ignores=[]), '_original_route', 'exec'), namespace)
    monkeypatch.setitem(wa.app.view_functions, 'patch_routes.apply_patch_plan_route', namespace['apply_patch_plan_route'])
    monkeypatch.setattr(run_lifecycle, 'apply_patch_plan', old.apply_patch_plan)
    monkeypatch.setitem(wa.app.config, 'PROPAGATE_EXCEPTIONS', False)
    response = post(harness, [create(), {'op': 7, 'relative_path': 'other.txt'}])
    assert response.status_code == 500 and not response.is_json
    assert (harness.repo / 'created.txt').read_bytes() == b'partial write\n'
    assert harness.calls == []


def test_exact_audit_post_json_zero_mutations_whole_repo_unchanged(harness, monkeypatch):
    before = tree(harness.repo)
    spy = mutation_spy(monkeypatch)
    response = post(harness, [create(), {'op': 7, 'relative_path': 'other.txt'}])
    assert response.status_code == 200 and response.is_json
    assert_rejected(response.get_json(), spy)
    assert response.get_json()['failed_op_index'] == 1
    assert tree(harness.repo) == before and harness.calls == []


@pytest.mark.parametrize('ordinal', [0, 1, 2])
def test_invalid_first_middle_last_never_starts_transaction(tmp_path, monkeypatch, ordinal):
    plan = [create('first.txt'), create('middle.txt'), create('last.txt')]
    plan[ordinal]['op'] = 7
    spy = mutation_spy(monkeypatch)
    snapshot = Mock(side_effect=AssertionError('no snapshot for malformed schema'))
    monkeypatch.setattr(executor, 'snapshot_targets', snapshot)
    result = executor.apply_patch_plan(str(tmp_path), plan)
    assert_rejected(result, spy)
    assert result['failed_op_index'] == ordinal and snapshot.call_count == 0


WRONG_TYPES = [None, True, False, 7, 1.5, [], {}]


@pytest.mark.parametrize('value', WRONG_TYPES)
@pytest.mark.parametrize('field', ['op', 'relative_path', 'file', 'content', 'target_snippet', 'patched_snippet'])
def test_high_risk_type_matrix(tmp_path, monkeypatch, field, value):
    op = replace() if 'snippet' in field else create('last.txt')
    op[field] = value
    spy = mutation_spy(monkeypatch)
    result = executor.apply_patch_plan(str(tmp_path), [create(), op])
    assert_rejected(result, spy)


@pytest.mark.parametrize('plan', [None, True, 7, 'ops', {}, {'ops': []}, [], [None], [True], [7], [[]]])
def test_outer_and_operation_object_types(tmp_path, monkeypatch, plan):
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), plan), spy)


@pytest.mark.parametrize('field', ['op', 'relative_path', 'target_snippet', 'patched_snippet'])
def test_missing_required_fields(tmp_path, monkeypatch, field):
    op = replace()
    del op[field]
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), [create(), op]), spy)


@pytest.mark.parametrize('kind', ['delete_file', 'write', 'CREATE_FILE', '', 'rename_file'])
def test_unsupported_operation_is_not_added_or_ignored(tmp_path, monkeypatch, kind):
    op = create('last.txt')
    op['op'] = kind
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), [create(), op]), spy, 'unsupported_operation')


@pytest.mark.parametrize('field', ['content', 'relative_path', 'target_snippet', 'patched_snippet'])
def test_unencodable_json_string_rejected_before_write(tmp_path, monkeypatch, field):
    op = replace() if 'snippet' in field else create('last.txt')
    op[field] = '\ud800'
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), [create(), op]), spy)


@pytest.mark.parametrize('path', ['../out.txt', 'a/../out.txt', '..\\out.txt', '/external.txt',
                                 'C:\\external.txt', 'C:relative.txt', '\\\\host\\share\\x.txt',
                                 '\\rooted.txt', '.git/config', '.env', 'tests/test_a.py', '.', 'x\x00z'])
def test_one_unsafe_target_rejects_whole_plan(tmp_path, monkeypatch, path):
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), [create(), create(path)]), spy, 'unsafe_target')


def junction(source, alias):
    if os.name == 'nt':
        import _winapi
        _winapi.CreateJunction(str(source), str(alias))
    else:
        alias.symlink_to(source, target_is_directory=True)


def test_reparse_escape_rejected_before_mutation(tmp_path, monkeypatch):
    repo = tmp_path / 'repo'
    outside = tmp_path / 'outside'
    repo.mkdir()
    outside.mkdir()
    junction(outside, repo / 'alias')
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(repo), [create(), create('alias/x.txt')]), spy, 'unsafe_target')


def test_prepared_state_immutable_normalized_detached_and_compatible_extras(tmp_path):
    physical = tmp_path / 'src'
    physical.mkdir()
    junction(physical, tmp_path / 'alias')
    raw = {'op': ' create_file ', 'relative_path': '', 'file': 'alias/a.txt',
           'comment': {'arbitrary': [True]}, 'overwrite': True}
    plan = transaction.prepare_patch_plan(tmp_path, [raw])
    assert isinstance(plan.operations, tuple)
    assert plan.operations[0].relative_path == 'src/a.txt'
    assert plan.operations[0].content == ''
    assert not (physical / 'a.txt').exists()
    with pytest.raises(FrozenInstanceError):
        plan.operations[0].content = 'changed'
    raw['file'] = '../escape.txt'
    raw['content'] = 'changed after prepare'
    result = executor.execute_prepared_patch_plan(plan)
    assert result['success'] and (physical / 'a.txt').read_bytes() == b''
    assert 'overwrite' not in result['applied_ops'][0]


def test_multiple_files_and_same_target_order(tmp_path):
    (tmp_path / 'existing.txt').write_bytes(b'old\r\nkeep\r\n')
    plan = [replace('existing.txt', 'old', 'new'), create('pkg/new.txt', 'one\n'),
            replace('pkg/new.txt', 'one', 'two'), replace('existing.txt', 'new', 'final')]
    result = executor.apply_patch_plan(str(tmp_path), plan)
    assert result['success'] and not result['recovery_attempted']
    assert result['mutation_attempted'] and result['remaining_changed_paths'] == []
    assert (tmp_path / 'existing.txt').read_bytes() == b'final\r\nkeep\r\n'
    assert (tmp_path / 'pkg/new.txt').read_bytes() == b'two\n'
    assert [op['op'] for op in result['applied_ops']] == [op['op'] for op in plan]


def test_snapshot_once_for_repeated_targets_and_hardlinks(tmp_path, monkeypatch):
    path = tmp_path / 'a.txt'
    original = b'old\r\n'
    path.write_bytes(original)
    os.link(path, tmp_path / 'b.txt')
    plan = transaction.prepare_patch_plan(tmp_path, [replace('a.txt'), replace('a.txt'), replace('b.txt')])
    read = Path.read_bytes
    calls = []
    def record(path):
        calls.append(path)
        return read(path)
    monkeypatch.setattr(Path, 'read_bytes', record)
    baselines = transaction.snapshot_targets(plan)
    assert len(baselines) == len(calls) == 1
    assert baselines[0].paths == (path, tmp_path / 'b.txt')
    assert baselines[0].before_bytes == original
    assert baselines[0].before_sha256 == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize('original', [b'', b'old\n', b'old\r\n', b'old', b'old\x00tail',
                                     'old café 한글\n'.encode(), b'\xff\xfe\x00\r\n'])
def test_later_runtime_exception_recovers_all_baseline_bytes(tmp_path, monkeypatch, original):
    a, b = tmp_path / 'a.txt', tmp_path / 'b.txt'
    a.write_bytes(original)
    b.write_bytes(b'old B\n')
    write = Path.write_bytes
    def fault(path, data):
        if path == b and data.startswith(b'new'):
            # A valid operation can fail after an unrelated bounded mutation.
            a.unlink()
            raise OSError('injected later write failure')
        return write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', fault)
    result = executor.apply_patch_plan(str(tmp_path), [create('new/deep/file.txt'), replace('b.txt'), replace('a.txt')])
    assert result['code'] == 'execution_failed' and result['mutation_attempted']
    assert result['recovery_attempted'] and result['recovery_complete']
    assert result['remaining_changed_paths'] == result['remaining_created_directories'] == []
    assert a.read_bytes() == original and b.read_bytes() == b'old B\n'
    assert not (tmp_path / 'new').exists()


@pytest.mark.parametrize('recovery_fault', ['raise', 'silent_noop'])
def test_incomplete_recovery_independently_reports_actual_changed_path(tmp_path, monkeypatch, recovery_fault):
    (tmp_path / 'a.txt').write_bytes(b'old A\r\n')
    (tmp_path / 'b.txt').write_bytes(b'old B\n')
    write, restore = Path.write_bytes, transaction.restore_target
    def fail_second(path, data):
        if path.name == 'b.txt' and data == b'new B\n':
            raise PermissionError('private injected failure')
        return write(path, data)
    def fail_restore(path, baseline):
        if path.name == 'a.txt':
            if recovery_fault == 'raise':
                raise PermissionError('private injected restore failure')
            return
        return restore(path, baseline)
    monkeypatch.setattr(Path, 'write_bytes', fail_second)
    monkeypatch.setattr(transaction, 'restore_target', fail_restore)
    result = executor.apply_patch_plan(str(tmp_path), [replace('a.txt'), replace('b.txt')])
    assert result['code'] == 'recovery_incomplete' and result['failure_code'] == 'execution_failed'
    assert result['recovery_attempted'] and result['recovery_complete'] is False
    assert result['remaining_changed_paths'] == ['a.txt']
    assert (tmp_path / 'a.txt').read_bytes() == b'new A\r\n'
    assert (tmp_path / 'b.txt').read_bytes() == b'old B\n'
    # DATA.ROLLBACK.1 maintenance: the frozen transaction facts remain the
    # same, while the generic success flag now consumes their measured failure.
    assert result['rollback_performed'] is False and result['patch_ops_rollback_protected'] is True
    assert result['rollback_attempted'] is True
    assert result['rollback_status'] == 'incomplete'
    assert 'private injected' not in json.dumps(result)
    assert 'rolled back successfully' not in result['message']


def test_all_snapshots_complete_before_first_write(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_bytes(b'old A')
    (tmp_path / 'b.txt').write_bytes(b'old B')
    read = Path.read_bytes
    def unreadable(path):
        if path.name == 'b.txt':
            raise PermissionError('snapshot denied')
        return read(path)
    monkeypatch.setattr(Path, 'read_bytes', unreadable)
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.apply_patch_plan(str(tmp_path), [replace('a.txt'), replace('b.txt')]), spy, 'execution_failed')


def test_partial_write_then_raise_restores_every_target(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_bytes(b'old A\r\n')
    (tmp_path / 'b.txt').write_bytes(b'old B\n')
    before = tree(tmp_path)
    write = Path.write_bytes
    def partial(path, data):
        if path.name == 'b.txt' and data.startswith(b'new'):
            write(path, data[:2])
            raise OSError('partial binary write')
        return write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', partial)
    result = executor.apply_patch_plan(str(tmp_path), [replace('a.txt'), replace('b.txt')])
    assert result['code'] == 'execution_failed' and result['recovery_complete']
    assert result['remaining_changed_paths'] == [] and tree(tmp_path) == before


@pytest.mark.parametrize('stage', ['diff', 'safe_validation', 'validation_snapshot'])
def test_unexpected_post_write_exceptions_contained(tmp_path, monkeypatch, stage):
    from core.validation_execution import SafeValidationCommand
    target = tmp_path / 'a.txt'
    target.write_bytes(b'old\r\n')
    def crash(*args, **kwargs):
        raise RuntimeError('untrusted internal detail')
    options = {}
    if stage == 'diff':
        monkeypatch.setattr(executor, '_make_diff', crash)
    else:
        options['safe_validation_command'] = SafeValidationCommand(command=['python', 'check.py'], cwd=tmp_path, timeout_sec=20)
        monkeypatch.setattr(executor, 'run_safe_validation_command' if stage == 'safe_validation' else 'snapshot_repo_files', crash)
    result = executor.apply_patch_plan(str(tmp_path), [replace()], **options)
    assert result['code'] == 'execution_failed' and result['recovery_complete']
    assert target.read_bytes() == b'old\r\n'
    assert 'untrusted internal detail' not in json.dumps(result)


def test_failure_after_created_parent_before_file_cleans_parent(tmp_path, monkeypatch):
    def crash(*args, **kwargs):
        raise PermissionError('cannot create file')
    monkeypatch.setattr(Path, 'write_bytes', crash)
    result = executor.apply_patch_plan(str(tmp_path), [create('new/deep/a.txt')])
    assert result['recovery_complete'] and result['remaining_changed_paths'] == []
    assert not (tmp_path / 'new').exists()


def test_directory_creation_exception_cannot_hide_unverified_side_effect(tmp_path, monkeypatch):
    mkdir = Path.mkdir
    def creates_then_raises(path, *args, **kwargs):
        mkdir(path, *args, **kwargs)
        raise OSError('directory created but completion failed')
    monkeypatch.setattr(Path, 'mkdir', creates_then_raises)
    result = executor.apply_patch_plan(str(tmp_path), [create('new/a.txt')])
    assert result['code'] == 'recovery_incomplete'
    assert result['remaining_changed_paths'] == []
    assert result['remaining_created_directories'] == ['new']
    assert (tmp_path / 'new').is_dir()


def test_same_target_failure_restores_original_once_and_created_absence(tmp_path, monkeypatch):
    (tmp_path / 'a.txt').write_bytes(b'old\r\n')
    plan = [replace('a.txt', 'old', 'middle'), replace('a.txt', 'middle', 'final'),
            create('pkg/new.txt', 'one'), replace('pkg/new.txt', 'one', 'two'),
            create('pkg/new.txt', 'duplicate')]
    result = executor.apply_patch_plan(str(tmp_path), plan)
    assert result['code'] == 'precondition_failed' and result['recovery_complete']
    assert (tmp_path / 'a.txt').read_bytes() == b'old\r\n'
    assert not (tmp_path / 'pkg').exists()


def test_preexisting_and_nonempty_directories_never_deleted(tmp_path, monkeypatch):
    existing = tmp_path / 'existing'
    existing.mkdir()
    write = Path.write_bytes
    def fault(path, data):
        if path.name == 'late.txt':
            write(tmp_path / 'new' / 'unrelated.txt', b'concurrent or validation output')
            raise OSError('later failure')
        return write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', fault)
    result = executor.apply_patch_plan(str(tmp_path), [create('existing/a.txt'), create('new/a.txt'), create('late.txt')])
    assert result['code'] == 'recovery_incomplete'
    assert result['remaining_changed_paths'] == []
    assert result['remaining_created_directories'] == ['new']
    assert existing.is_dir() and list(existing.iterdir()) == []
    assert (tmp_path / 'new/unrelated.txt').read_bytes() == b'concurrent or validation output'


def test_containment_rechecked_after_preparation(tmp_path, monkeypatch):
    repo, outside = tmp_path / 'repo', tmp_path / 'outside'
    repo.mkdir()
    outside.mkdir()
    parent = repo / 'src'
    parent.mkdir()
    prepared = transaction.prepare_patch_plan(repo, [create('src/a.txt')])
    parent.rmdir()
    junction(outside, parent)
    spy = mutation_spy(monkeypatch)
    assert_rejected(executor.execute_prepared_patch_plan(prepared), spy, 'unsafe_target')


def test_mode_preserved_on_success_and_recovery(tmp_path):
    target = tmp_path / 'a.txt'
    target.write_bytes(b'old\n')
    target.chmod(0o755)
    mode = stat.S_IMODE(target.stat().st_mode)
    result = executor.apply_patch_plan(str(tmp_path), [replace('a.txt')])
    assert result['success'] and stat.S_IMODE(target.stat().st_mode) == mode
    result = executor.apply_patch_plan(str(tmp_path), [replace('a.txt', 'new', 'last'), replace('missing.txt')])
    assert result['recovery_complete'] and target.read_bytes() == b'new\n'
    assert stat.S_IMODE(target.stat().st_mode) == mode


def test_process_local_lock_covers_snapshot_through_execution(tmp_path, monkeypatch):
    started, release, second_snapshotted = threading.Event(), threading.Event(), threading.Event()
    write, snapshot = Path.write_bytes, executor.snapshot_targets
    def held_write(path, data):
        if path.name == 'first.txt':
            started.set()
            assert release.wait(5)
        return write(path, data)
    def observe(plan):
        if plan.operations[0].target.name == 'second.txt':
            second_snapshotted.set()
        return snapshot(plan)
    monkeypatch.setattr(Path, 'write_bytes', held_write)
    monkeypatch.setattr(executor, 'snapshot_targets', observe)
    results = []
    threads = [threading.Thread(target=lambda name=name: results.append(executor.apply_patch_plan(str(tmp_path), [create(name)])))
               for name in ('first.txt', 'second.txt')]
    threads[0].start()
    assert started.wait(5)
    threads[1].start()
    try:
        assert not second_snapshotted.wait(0.15)
    finally:
        release.set()
        for thread in threads:
            thread.join(5)
    assert len(results) == 2 and all(r['success'] for r in results)
    assert second_snapshotted.is_set()


@pytest.mark.parametrize('endpoint', ['/apply_patch_plan', '/test_patch_plan'])
@pytest.mark.parametrize('payload', [None, True, 7, [], {}, {'patch_plan': 7},
                                     {'patch_plan': [create(), {'op': ['create_file'], 'relative_path': 'last.txt'}]}])
def test_http_outer_and_nested_schema_json(harness, monkeypatch, endpoint, payload):
    before = tree(harness.repo)
    spy = mutation_spy(monkeypatch)
    response = harness.client.post(endpoint, headers=harness.headers, data={
        'repo_path': str(harness.repo), 'patch_style': 'balanced', 'patch': json.dumps(payload),
    })
    assert response.status_code == 200 and response.is_json
    assert_rejected(response.get_json(), spy)
    assert tree(harness.repo) == before and harness.calls == []


@pytest.mark.parametrize('recovery_fails', [False, True])
def test_real_http_runtime_failure_returns_json_and_local_truth(harness, monkeypatch, recovery_fails):
    target = harness.repo / 'app.py'
    original = target.read_bytes()
    write = Path.write_bytes
    def fail(path, data):
        if path == harness.repo / 'later.txt':
            raise OSError('bounded runtime fault')
        if recovery_fails and path == target and data == original:
            raise OSError('bounded restore fault')
        return write(path, data)
    monkeypatch.setattr(Path, 'write_bytes', fail)
    response = post(harness, [replace('app.py', 'value + 1', 'value + 2'), create('later.txt')])
    assert response.status_code == 200 and response.is_json
    result = response.get_json()
    assert result['success'] is False and result['recovery_attempted']
    assert result['recovery_complete'] is (not recovery_fails)
    assert result['remaining_changed_paths'] == (['app.py'] if recovery_fails else [])
    assert (target.read_bytes() == original) is (not recovery_fails)
    if recovery_fails:
        assert 'was rolled back' not in result['message']
        assert result['code'] == 'recovery_incomplete'
    assert harness.calls == []


def test_real_http_valid_multifile_plan_keeps_success_semantics(harness):
    response = post(harness, [create('one.txt', 'one\n'), create('pkg/two.txt', 'two\r\n'),
                              replace('one.txt', 'one', 'final')])
    assert response.status_code == 200 and response.is_json
    result = response.get_json()
    assert result['success'] and result['mutation_attempted']
    assert not result['recovery_attempted'] and result['remaining_changed_paths'] == []
    assert (harness.repo / 'one.txt').read_bytes() == b'final\n'
    assert (harness.repo / 'pkg/two.txt').read_bytes() == b'two\r\n'
    assert harness.calls == []


@pytest.mark.parametrize('endpoint', ['/apply_patch_plan', '/test_patch_plan'])
def test_http_unsafe_path_preserves_gate_and_local_rejection_status(harness, endpoint):
    before = tree(harness.repo)
    response = post(harness, [create(), create('../outside.txt')], endpoint)
    assert response.status_code == 200 and response.is_json
    result = response.get_json()
    assert result['code'] == 'unsafe_target' and result['success'] is False
    assert not result['mutation_attempted'] and not result['recovery_attempted']
    assert result['patch_safety']['ok'] is False
    assert tree(harness.repo) == before and harness.calls == []


def test_no_new_repository_walks_or_undo_authority():
    source = (ROOT / 'patching/patch_plan_transaction.py').read_text()
    tree = ast.parse(source)
    calls = {n.func.attr for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    assert calls.isdisjoint({'rglob', 'glob', 'walk', 'iterdir', 'read_text', 'write_text'})
    assert 'undo_backup' not in source and 'backup_id' not in source


def test_exact_entry_reversal_and_frozen_surfaces():
    from tests._exec_plan1_maintenance import before_exec_plan1
    fixture = json.loads((ROOT / 'tests/fixtures/exec_plan1_frozen_boundaries.json').read_text())
    for name, digest in fixture['sha256'].items():
        assert hashlib.sha256(before_exec_plan1(name)).hexdigest() == digest, name


def test_registry_records_only_this_phase_and_preserves_picker():
    from core.phase_registry import load_phase_registry, validate_phase_registry
    from core.phase_picker import pick_phase_candidates
    registry = load_phase_registry(str(ROOT / 'docs/roadmap/phase_registry.json'))
    assert validate_phase_registry(registry)['is_valid']
    phases = [p for p in registry['phases'] if p['phase_id'] == 'EXEC.PLAN.1']
    assert len(phases) == 1 and phases[0]['status'] == 'complete' and phases[0]['track'] == 'HARDEN'
    assert not phases[0]['model_calls_allowed'] and not phases[0]['network_allowed']
    assert pick_phase_candidates(registry)['top_recommendation']['phase_id'] == 'DOGFOOD.1B'
