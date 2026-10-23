"""Pure validation harness for RUNTIME.JAVA.PINNED.1A.

Runs frozen/new semantic tests with real process/network effects denied.
Repository maintenance Python and temporary pytest fixtures are separate from
operational runtime effects. This harness issues no provider capabilities.
"""
from __future__ import annotations
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import platform
import time
import uuid

ROOT = Path(__file__).resolve().parents[4]
PHASE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True
os.environ['PYTEST_DISABLE_PLUGIN_AUTOLOAD'] = '1'

FROZEN_TESTS = [
    'tests/test_runtime_java_requirement_pinned1.py',
    'tests/test_runtime_java_discovery_contract1.py',
    'tests/test_runtime_java_discovery_diag1.py',
    'tests/test_runtime_java1.py',
    'tests/test_runtime_java1_discovery.py',
    'tests/test_runtime_java1_governance.py',
    'tests/test_runtime_java_compat1.py',
    'tests/test_runtime_java1d.py',
    'tests/test_runtime_java1d_retry.py',
    'tests/test_runtime_sandbox_bind1.py',
    'tests/test_runtime_java1c.py',
    'tests/test_synthetic_runtime_authorization.py',
    'tests/test_patch_candidate_behavior_executor1r.py',
    'tests/test_patch_candidate_behavior_executor1r_retry.py',
    'tests/test_patch_candidate_behavior_executor1r_lifecycle_retry.py',
]
REGISTRY_TESTS = ['tests/test_phase_registry.py', 'tests/test_phase_picker.py']

class Results:
    def __init__(self):
        self.collected = 0
        self.passed = 0
        self.skipped = 0
        self.failures = []
        self.suites = {}
    def pytest_collection_finish(self, session):
        self.collected = len(session.items)
    def pytest_runtest_logreport(self, report):
        suite = self.suites.setdefault(report.nodeid.split('::')[0], {'passed':0, 'failed':0, 'skipped':0})
        if report.failed:
            self.failures.append({'nodeid':report.nodeid, 'when':report.when, 'outcome':report.outcome, 'detail':str(report.longrepr)})
            suite['failed'] += 1
        elif report.when == 'call' and report.passed:
            self.passed += 1
            suite['passed'] += 1
        elif report.skipped:
            self.skipped += 1
            suite['skipped'] += 1

mode = sys.argv[1]
started = time.monotonic()
stream = io.StringIO()
active = [True]
real_effect_attempts = []
def audit_denial(event, args):
    if active[0] and (event in {'subprocess.Popen','os.system','os.exec','os.posix_spawn','os.spawn','pty.spawn','os.startfile','socket.connect','socket.bind','socket.sendto','socket.sendmsg'} or event.startswith('os.startfile/')):
        real_effect_attempts.append(event)
        raise AssertionError('Pinned target pure validation denied real effect: ' + event)
sys.addaudithook(audit_denial)

from tests._preflight_runtime1_guard import no_runtime_effects
# Avoid Python Windows metadata fallback issuing a shell `ver` during imports.
# Values come from process/OS APIs; this changes maintenance harness only.
if sys.platform == 'win32':
    windows_version = sys.getwindowsversion()
    platform._uname_cache = platform.uname_result('Windows', os.environ.get('COMPUTERNAME', ''),
        str(windows_version.major), '.'.join(map(str, windows_version[:3])),
        os.environ.get('PROCESSOR_ARCHITECTURE', ''))
if mode == 'benchmark_check':
    import runpy
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        with no_runtime_effects(strict=False) as guard:
            sys.argv = ['benchmarks/run_benchmarks.py', '--check']
            try:
                runpy.run_path(str(ROOT/'benchmarks/run_benchmarks.py'), run_name='__main__')
            except SystemExit as error:
                exit_code = int(error.code or 0)
            else:
                exit_code = 0
    result = {'mode':mode,'exit_code':exit_code,'real_effect_attempts':real_effect_attempts,'denied_attempts':guard.denied_attempts}
else:
    import pytest
    if mode.startswith('registry_'):
        test_files = REGISTRY_TESTS
    elif mode.startswith('frozen_'):
        test_files = FROZEN_TESTS
    elif mode == 'new_target_inspection':
        test_files = ['tests/test_runtime_java_pinned_target_inspection.py', 'tests/test_runtime_java_pinned_target_archive.py']
    else:
        raise ValueError(mode)
    temp_root = PHASE / ('validation_temp_' + mode + '_' + uuid.uuid4().hex)
    temp_root.mkdir(exist_ok=False)
    tempfile.tempdir = str(temp_root)
    args = ['-q','-p','no:cacheprovider','--basetemp='+str(temp_root/'pytest'), *test_files]
    plugin = Results()
    with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
        with no_runtime_effects(strict=False) as guard:
            exit_code = int(pytest.main(args, plugins=[plugin]))
    result = {'mode':mode,'exit_code':exit_code,'collected':plugin.collected,'passed':plugin.passed,'skipped':plugin.skipped,'failures':plugin.failures,'suites':plugin.suites,'test_files':test_files,'pytest_arguments':args,'real_effect_attempts':real_effect_attempts,'denied_attempts':guard.denied_attempts,'registry_projection_plugin_used':False}
active[0] = False
result['elapsed_seconds'] = round(time.monotonic()-started,3)
result['scope'] = 'Pure host maintenance and fabricated in-memory fixture evidence only; this validation harness performs no live target inspection, Docker/Java, runtime authorization, leases, executor, or apply. Root separately owns one authorized exact-target live proof after pure gates.'
(PHASE/(mode+'.txt')).write_text(stream.getvalue(),encoding='utf-8')
(PHASE/(mode+'.json')).write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:result[k] for k in ['mode','exit_code','collected','passed','skipped','real_effect_attempts','denied_attempts','elapsed_seconds'] if k in result}))
sys.exit(exit_code)
