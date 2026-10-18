import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import pytest


@pytest.mark.skipif(not shutil.which("nvim"), reason="nvim not installed")
def test_nvim_save_no_hit_enter():
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    with open(src_md, "w") as f:
        f.write("# Hello\n\nContent here.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "--no-center", "-w", "80"
    ], check=True)

    # We will test running nvim interactively with pty, sending 'e', ':w\r', and checking if 'Press ENTER' appears.
    nvim_bin = shutil.which("nvim")
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        os.execv(nvim_bin, [
            nvim_bin, "-u", "NORC",
            "-c", f"source {ansi_path}.vim",
            "-c", "call MdokEditSource()",
        ])
    else:
        os.close(slave)
        time.sleep(0.5)
        # Send ':w\r'
        os.write(master, b":w\r")
        time.sleep(0.5)
        # Read output
        out = b""
        start = time.time()
        while time.time() - start < 1.0:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break
        os.write(master, b":qa!\r")
        time.sleep(0.2)
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)
        shutil.rmtree(tmpdir, ignore_errors=True)

        decoded = out.decode("utf-8", errors="replace")
        print(f"OUTPUT:\n{decoded}")
        assert "Press ENTER" not in decoded and "continue" not in decoded


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_save_no_hit_enter():
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    with open(src_md, "w") as f:
        f.write("# Hello\n\nContent here.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "--no-center", "-w", "80"
    ], check=True)

    vim_bin = shutil.which("vim")
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        os.execv(vim_bin, [
            vim_bin, "--clean", "-u", "NORC",
            "-c", f"source {ansi_path}.vim",
            "-c", "call MdokEditSource()",
        ])
    else:
        os.close(slave)
        time.sleep(0.5)
        os.write(master, b":w\r")
        time.sleep(0.5)
        out = b""
        start = time.time()
        while time.time() - start < 1.0:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    out += chunk
                except OSError:
                    break
        os.write(master, b":qa!\r")
        time.sleep(0.2)
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)
        shutil.rmtree(tmpdir, ignore_errors=True)

        decoded = out.decode("utf-8", errors="replace")
        assert "Press ENTER" not in decoded and "continue" not in decoded
