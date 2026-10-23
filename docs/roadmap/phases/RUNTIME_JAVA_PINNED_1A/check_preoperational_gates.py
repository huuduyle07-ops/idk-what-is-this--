"""Read-only preoperational gates; does not import or invoke target owners."""
from pathlib import Path
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[4]
PHASE=Path(__file__).resolve().parent
SAFETY_FILES=[
    'core/runtime_java_pinned_target_inspection.py',
    'core/runtime_java_pinned_target_archive.py',
    'scripts/replay_runtime_java_pinned1a.py',
    'tests/test_runtime_java_pinned_target_inspection.py',
    'tests/test_runtime_java_pinned_target_archive.py',
    'core/runtime_java_pinned_requirement.py',
    'core/sandboxed_java_toolchain_discovery.py',
    'core/candidate_runtime_sandbox.py',
    'core/sandboxed_java_positive_probe.py',
]

def result(name):
    p=PHASE/name
    return json.loads(p.read_text(encoding='utf-8-sig')) if p.exists() else None

compilation=[]
errors=[]
for rel in SAFETY_FILES:
    p=ROOT/rel
    try:
        raw=p.read_bytes()
        compile(raw,str(p),'exec')
        compilation.append({'path':rel,'sha256':hashlib.sha256(raw).hexdigest(),'size_bytes':len(raw)})
    except Exception as error:
        errors.append({'path':rel,'error':str(error)})
focused=result('new_target_inspection.json')
frozen=result('frozen_after.json')
benchmark=result('benchmark_check.json')
registry_baseline=result('registry_baseline.json')
registry_after=result('registry_after.json')
ids=lambda r: sorted(f['nodeid'] for f in r['failures']) if r else None
whitespace_errors=[]
authored=[ROOT/rel for rel in SAFETY_FILES if rel.startswith(('core/runtime_java_pinned_target','tests/test_runtime_java_pinned_target','scripts/replay_runtime_java_pinned1a'))]+[p for p in PHASE.iterdir() if p.is_file() and p.suffix in {'.py','.md','.json'}]
for path in authored:
    raw=path.read_bytes()
    if raw and not raw.endswith(b'\n'):
        whitespace_errors.append({'path':path.relative_to(ROOT).as_posix(),'issue':'missing final newline'})
    for line_number,line in enumerate(raw.decode('utf-8-sig').splitlines(),1):
        if line.rstrip(' \t')!=line:
            whitespace_errors.append({'path':path.relative_to(ROOT).as_posix(),'line':line_number,'issue':'trailing whitespace'})
git_check=result('git_diff_check.json')
checks={
    'focused_new_target_tests_passed':focused is not None and focused['exit_code']==0,
    'frozen_pure_regressions_passed':frozen is not None and frozen['exit_code']==0,
    'benchmark_structure_check_passed':benchmark is not None and benchmark['exit_code']==0,
    'registry_picker_has_no_new_failures':registry_after is not None and ids(registry_baseline)==ids(registry_after),
    'safety_code_compiles_in_memory':not errors,
    'authored_whitespace_passed':not whitespace_errors,
    'git_diff_check_passed':git_check is not None and git_check['exit_code']==0,
}
output={
    'phase_id':'RUNTIME.JAVA.PINNED.1A',
    'pure_gates_ready':all(checks.values()),
    'checks':checks,
    'focused_tests_passed':focused.get('passed') if focused else None,
    'frozen_tests_passed':frozen.get('passed') if frozen else None,
    'in_memory_compilation':{'files':compilation,'errors':errors,'code_executed':False},
    'preoperational_artifact_whitespace':{'checked_files':[p.relative_to(ROOT).as_posix() for p in authored],'issues':whitespace_errors,'passed':not whitespace_errors},
    'operational_calls_performed_by_this_gate':0,
    'note':'Gate only records pure test, benchmark and compile results. Root owns the separately authorized single exact-target operational proof; no inspection, Docker or execution occurs here.',
}
(PHASE/'pure_preoperational_gates.json').write_text(json.dumps(output,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'pure_gates_ready':output['pure_gates_ready'],'checks':checks,'focused_tests_passed':output['focused_tests_passed'],'frozen_tests_passed':output['frozen_tests_passed'],'compilation_errors':errors}))
sys.exit(0 if output['pure_gates_ready'] else 1)
