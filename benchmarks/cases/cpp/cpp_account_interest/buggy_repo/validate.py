import platform
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = HERE / ("validation_test.exe" if platform.system() == "Windows" else "validation_test")

compile_cmd = [
    "g++",
    str(HERE / "main.cpp"),
    str(HERE / "interest.cpp"),
    "-std=c++17",
    "-o",
    str(EXE),
]

try:
    subprocess.run(compile_cmd, check=True)
    subprocess.run([str(EXE)], check=True)
    print("OK")
except subprocess.CalledProcessError as e:
    sys.exit(e.returncode)
finally:
    try:
        EXE.unlink()
    except FileNotFoundError:
        pass
