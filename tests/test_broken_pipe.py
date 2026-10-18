import subprocess
import sys
import pytest

def test_spawn_pager_broken_pipe_no_stderr():
    code = """
import sys
import subprocess
from mdok.pager import spawn_pager

def write_fn(console):
    for i in range(10000):
        console.print(f"Line {i} " + "x" * 100)

cmd = ["head", "-n", "2"]
ret = spawn_pager("custom", cmd, {}, write_fn, term_width=80)
sys.exit(ret)
"""
    res = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    print("RETURN CODE:", res.returncode)
    print("STDOUT:\n" + res.stdout)
    print("STDERR:\n" + res.stderr)
    assert res.returncode == 0
    assert "BrokenPipeError" not in res.stderr
    assert "Exception ignored while finalizing file" not in res.stderr


def test_cli_broken_pipe_no_stderr():
    res = subprocess.run(
        [sys.executable, "-m", "mdok.cli", "README.md", "--pager-cmd", "head -n 2"],
        capture_output=True,
        text=True,
    )
    print("CLI RETURN CODE:", res.returncode)
    print("CLI STDERR:\n" + res.stderr)
    assert res.returncode == 0
    assert "BrokenPipeError" not in res.stderr
    assert "Exception ignored while finalizing file" not in res.stderr


