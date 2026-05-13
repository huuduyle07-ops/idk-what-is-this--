import platform
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
EXE = HERE / ("validation_test.exe" if IS_WINDOWS else "validation_test")

# Windows NTSTATUS error codes start at 0xC0000000. When an EXE crashes with
# one of these (access violation, dll-not-found, etc.) on first launch from a
# tempdir, the cause is usually AV real-time scanning injecting into the
# fresh binary, not a real bug. Retry once after a short pause.
NTSTATUS_ERROR_THRESHOLD = 0xC0000000


def run_and_forward(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    return result.returncode


def is_windows_av_crash(rc: int) -> bool:
    if not IS_WINDOWS or rc <= 0:
        return False
    return (rc & 0xFFFFFFFF) >= NTSTATUS_ERROR_THRESHOLD


compile_cmd = [
    "g++",
    str(HERE / "main.cpp"),
    str(HERE / "interest.cpp"),
    "-std=c++17",
    "-o",
    str(EXE),
]

# Drop any leftover binary so g++ writes fresh; avoids a locked-file scenario
# where an orphaned EXE from a previous run is partially overwritten.
try:
    if EXE.exists():
        EXE.unlink()
except OSError:
    pass

exit_code = 0
try:
    rc = run_and_forward(compile_cmd)
    if rc != 0:
        print(f"compile failed (exit {rc})", file=sys.stderr)
        exit_code = rc
    else:
        rc = run_and_forward([str(EXE)])
        if is_windows_av_crash(rc):
            print(
                f"validation_test crashed with NTSTATUS {rc} (0x{rc & 0xFFFFFFFF:08X}); "
                "retrying once after AV-scan delay.",
                file=sys.stderr,
            )
            time.sleep(1.5)
            rc = run_and_forward([str(EXE)])
        if rc != 0:
            print(f"validation_test failed (exit {rc})", file=sys.stderr)
            exit_code = rc
        else:
            print("OK")
finally:
    try:
        if EXE.exists():
            EXE.unlink()
    except OSError:
        pass

sys.exit(exit_code)
