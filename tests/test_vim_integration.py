import os
import pty
import select
import shutil
import tempfile
import time
import pytest
from mdok.pager import build_editor_cmd


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_pager_pty_execution():
    """Verify that Vim with +terminal launches cleanly in a real PTY without crashes or blank buffers."""
    with tempfile.NamedTemporaryFile("w", suffix=".ansi", delete=False) as f:
        f.write("\x1b[1;32m# THIS IS THE REAL DOCUMENT\x1b[0m\n\nContent paragraph.\nMore text here.")
        temp_path = f.name

    dump_path = temp_path + ".dump"
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

        base_cmd = build_editor_cmd("vim", temp_path, search_query="paragraph", left_margin=15)
        # Append diagnostic dump and quit
        cmd = base_cmd + [
            "-c",
            f"sleep 500m | call writefile([mode(), screenstring(5, 15), string(&ruler), &signcolumn] + getbufline(g:tb, 1, '$'), '{dump_path}') | qa!",
        ]
        os.execv(cmd[0], cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 3:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            assert os.path.exists(dump_path), "Vim did not write dump file"
            with open(dump_path) as df:
                lines = [line.rstrip("\n") for line in df]
            print("DUMP INFO:", lines[:6])
            assert len(lines) >= 4
            vim_mode, s15, ruler_opt, signcol = lines[0], lines[1], lines[2], lines[3]
            doc_lines = lines[4:]

            # Vim should be in terminal-normal mode ('n')
            assert vim_mode == "n"
            # Separator column (15) must be a clean blank space (non-breaking space \xa0), NOT a vertical bar '|'
            assert s15 in (" ", "\xa0")
            assert s15 != "|"
            # Ruler must be disabled (0)
            assert ruler_opt == "0"
            # Signcolumn must be disabled
            assert signcol == "no"
            # Document content must be present in the buffer
            assert any("THIS IS THE REAL DOCUMENT" in l for l in doc_lines)
            assert any("Content paragraph." in l for l in doc_lines)
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            if os.path.exists(dump_path):
                os.remove(dump_path)
