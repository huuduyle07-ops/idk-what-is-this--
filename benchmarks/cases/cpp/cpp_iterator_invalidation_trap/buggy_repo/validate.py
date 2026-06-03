import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
IS_WINDOWS = platform.system() == "Windows"
EXE = HERE / ("validation_test.exe" if IS_WINDOWS else "validation_test")
NTSTATUS_ERROR_THRESHOLD = 0xC0000000


def gxx_runtime_env():
    env = os.environ.copy()
    if not IS_WINDOWS:
        return env
    gxx = shutil.which("g++")
    if not gxx:
        return env
    gxx_dir = str(Path(gxx).resolve().parent)
    if env.get("PATH", "").split(os.pathsep)[0].lower() != gxx_dir.lower():
        env["PATH"] = gxx_dir + os.pathsep + env.get("PATH", "")
    return env


def run_and_forward(cmd, env=None):
    result = subprocess.run(
        cmd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    if result.stdout:
        sys.stdout.write(result.stdout)
    if result.stderr:
        sys.stderr.write(result.stderr)
    sys.stdout.flush()
    sys.stderr.flush()
    return result.returncode


def is_windows_av_crash(rc):
    if not IS_WINDOWS or rc <= 0:
        return False
    return (rc & 0xFFFFFFFF) >= NTSTATUS_ERROR_THRESHOLD


compile_cmd = [
    "g++",
    str(HERE / "main.cpp"),
    str(HERE / "filter.cpp"),
    "-std=c++17",
    "-o",
    str(EXE),
]

try:
    if EXE.exists():
        EXE.unlink()
except OSError:
    pass

runtime_env = gxx_runtime_env()
exit_code = 0
try:
    rc = run_and_forward(compile_cmd, env=runtime_env)
    if rc != 0:
        print(f"compile failed (exit {rc})", file=sys.stderr)
        exit_code = rc
    else:
        rc = run_and_forward([str(EXE)], env=runtime_env)
        if is_windows_av_crash(rc):
            print(
                f"validation_test crashed with NTSTATUS {rc} (0x{rc & 0xFFFFFFFF:08X}); "
                "retrying once after AV-scan delay.",
                file=sys.stderr,
            )
            time.sleep(1.5)
            rc = run_and_forward([str(EXE)], env=runtime_env)
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
