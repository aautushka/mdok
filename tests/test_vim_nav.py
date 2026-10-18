import os
import pty
import select
import shutil
import sys
import tempfile
import time
import pytest
from mdok.pager import build_editor_cmd


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_terminal_buffer_switching():
    """Verify that Vim with +terminal can switch between two terminal buffers in curwin: 1."""
    with tempfile.NamedTemporaryFile("w", suffix="1.ansi", delete=False) as f1:
        f1.write("DOC 1 CONTENT\n")
        path1 = f1.name

    with tempfile.NamedTemporaryFile("w", suffix="2.ansi", delete=False) as f2:
        f2.write("DOC 2 CONTENT\n")
        path2 = f2.name

    dump_path = path1 + ".dump"
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

        # Vim test sequence:
        # 1. Start term 1
        # 2. Start term 2 in curwin: 1
        # 3. Switch back to buffer 1
        # 4. Dump buffer line to verify DOC 1 CONTENT is restored
        script = (
            f"set hidden | "
            f"let g:b1 = term_start(['cat', '{path1}'], {{'curwin': 1, 'term_finish': 'open'}}) | "
            f"sleep 200m | "
            f"let g:b2 = term_start(['cat', '{path2}'], {{'curwin': 1, 'term_finish': 'open'}}) | "
            f"sleep 200m | "
            f"execute 'buffer ' . g:b1 | "
            f"sleep 200m | "
            f"call writefile([string(bufexists(g:b1)), string(bufexists(g:b2))] + getbufline(g:b1, 1, '$'), '{dump_path}') | "
            f"qa!"
        )
        vim_bin = shutil.which("vim") or "vim"
        cmd = [vim_bin, "--clean", "-c", script]
        os.execv(vim_bin, cmd)
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
            print("DUMP INFO:", lines)
            assert lines[0] == "1", "Buffer 1 does not exist"
            assert lines[1] == "1", "Buffer 2 does not exist"
            assert any("DOC 1 CONTENT" in l for l in lines[2:])
        finally:
            for p in (path1, path2, dump_path):
                if os.path.exists(p):
                    os.remove(p)


@pytest.mark.skipif(not shutil.which("nvim"), reason="nvim not installed")
def test_nvim_terminal_buffer_switching():
    """Verify that Neovim can switch between two terminal buffers."""
    with tempfile.NamedTemporaryFile("w", suffix="1.ansi", delete=False) as f1:
        f1.write("NVIM DOC 1 CONTENT\n")
        path1 = f1.name

    with tempfile.NamedTemporaryFile("w", suffix="2.ansi", delete=False) as f2:
        f2.write("NVIM DOC 2 CONTENT\n")
        path2 = f2.name

    dump_path = path1 + ".dump"
    script_file = path1 + ".vim"
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

        vim_script = (
            f"set hidden\n"
            f"execute 'terminal cat {path1}'\n"
            f"let g:b1 = bufnr('%')\n"
            f"sleep 200m\n"
            f"enew\n"
            f"execute 'terminal cat {path2}'\n"
            f"let g:b2 = bufnr('%')\n"
            f"sleep 200m\n"
            f"execute 'buffer ' . g:b1\n"
            f"sleep 200m\n"
            f"call writefile([string(bufexists(g:b1)), string(bufexists(g:b2))] + getbufline(g:b1, 1, '$'), '{dump_path}')\n"
            f"qa!\n"
        )
        script_file = path1 + ".vim"
        with open(script_file, "w") as sf:
            sf.write(vim_script)

        nvim_bin = shutil.which("nvim") or "nvim"
        cmd = [nvim_bin, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(nvim_bin, cmd)
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
            assert os.path.exists(dump_path), "Neovim did not write dump file"
            with open(dump_path) as df:
                lines = [line.rstrip("\n") for line in df]
            print("NVIM DUMP INFO:", lines)
            assert lines[0] == "1", "Buffer 1 does not exist"
            assert lines[1] == "1", "Buffer 2 does not exist"
            assert any("NVIM DOC 1 CONTENT" in l for l in lines[2:])
        finally:
            for p in (path1, path2, dump_path, script_file):
                if os.path.exists(p):
                    os.remove(p)


def test_vim_link_manifest():
    """Verify that links are properly classified and manifest is built for overview.md."""
    import subprocess
    import json
    from mdok.editor import build_link_manifest

    doc_path = os.path.abspath("examples/docs/overview.md")
    with tempfile.NamedTemporaryFile("w", suffix=".ansi", delete=False) as f:
        ansi_path = f.name

    try:
        res = subprocess.run(
            [sys.executable, "-m", "mdok.cli", "--render-ansi", ansi_path, doc_path],
            capture_output=True,
            text=True,
        )
        assert res.returncode == 0, f"Render failed: {res.stderr}"

        companion_path = f"{ansi_path}.vim"
        assert os.path.exists(companion_path), "Companion .vim script was not generated"

        with open(companion_path) as cf:
            content = cf.read()

        assert "b:mdok_links_by_line" in content
        assert "getting_started.md" in content
        assert "MdokFollowLink" in content
    finally:
        for p in (ansi_path, f"{ansi_path}.vim"):
            if os.path.exists(p):
                os.remove(p)


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_e2e_gf_navigation():
    """Verify in Vim that pressing gf on a link opens the rendered child document."""
    doc_path = os.path.abspath("examples/docs/overview.md")
    with tempfile.NamedTemporaryFile("w", suffix=".ansi", delete=False) as f:
        ansi_path = f.name

    dump_path = ansi_path + ".dump"
    companion_path = f"{ansi_path}.vim"

    import subprocess
    res = subprocess.run(
        [sys.executable, "-m", "mdok.cli", "--render-ansi", ansi_path, doc_path],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Render failed: {res.stderr}"

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

        test_script = (
            f"set hidden\n"
            f"let g:tb = term_start(['cat', '{ansi_path}'], {{'curwin': 1, 'term_finish': 'open'}})\n"
            f"source {companion_path}\n"
            f"sleep 300m\n"
            f"call feedkeys(\"\\<C-W>N\", 'tx!')\n"
            f"call search('Getting Started')\n"
            f"call MdokFollowLink()\n"
            f"sleep 600m\n"
            f"let g:child_lines = getbufline(bufnr('%'), 1, '$')\n"
            f"call MdokGoBack()\n"
            f"sleep 400m\n"
            f"let g:parent_lines = getbufline(bufnr('%'), 1, '$')\n"
            f"call writefile(['CHILD:'] + g:child_lines + ['PARENT:'] + g:parent_lines, '{dump_path}')\n"
            f"qa!\n"
        )
        test_vim_file = ansi_path + ".test.vim"
        with open(test_vim_file, "w") as tf:
            tf.write(test_script)

        vim_bin = shutil.which("vim") or "vim"
        cmd = [vim_bin, "--clean", "-S", test_vim_file]
        os.execv(vim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 5:
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
                content = df.read()
            child_part, parent_part = content.split("PARENT:", 1)
            assert "Getting Started Guide" in child_part or "Installation" in child_part
            assert "Project Documentation Overview" in parent_part
        finally:
            for path in (ansi_path, companion_path, dump_path, ansi_path + ".test.vim"):
                if os.path.exists(path):
                    os.remove(path)


@pytest.mark.skipif(not shutil.which("nvim"), reason="nvim not installed")
def test_nvim_e2e_gf_navigation():
    """Verify in Neovim that pressing gf on a link opens the rendered child document."""
    doc_path = os.path.abspath("examples/docs/overview.md")
    with tempfile.NamedTemporaryFile("w", suffix=".ansi", delete=False) as f:
        ansi_path = f.name

    dump_path = ansi_path + ".dump"
    companion_path = f"{ansi_path}.vim"

    import subprocess
    res = subprocess.run(
        [sys.executable, "-m", "mdok.cli", "--render-ansi", ansi_path, doc_path],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"Render failed: {res.stderr}"

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

        test_script = (
            f"set hidden\n"
            f"execute 'terminal cat {ansi_path}'\n"
            f"source {companion_path}\n"
            f"sleep 300m\n"
            f"call search('Getting Started')\n"
            f"call MdokFollowLink()\n"
            f"sleep 600m\n"
            f"let g:child_lines = getbufline(bufnr('%'), 1, '$')\n"
            f"call MdokGoBack()\n"
            f"sleep 400m\n"
            f"let g:parent_lines = getbufline(bufnr('%'), 1, '$')\n"
            f"call writefile(['NVIM_CHILD:'] + g:child_lines + ['NVIM_PARENT:'] + g:parent_lines, '{dump_path}')\n"
            f"qa!\n"
        )
        test_vim_file = ansi_path + ".test.vim"
        with open(test_vim_file, "w") as tf:
            tf.write(test_script)

        nvim_bin = shutil.which("nvim") or "nvim"
        cmd = [nvim_bin, "--clean", "-u", "NORC", "-S", test_vim_file]
        os.execv(nvim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 5:
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
            assert os.path.exists(dump_path), "Neovim did not write dump file"
            with open(dump_path) as df:
                content = df.read()
            child_part, parent_part = content.split("NVIM_PARENT:", 1)
            assert "Getting Started Guide" in child_part or "Installation" in child_part
            assert "Project Documentation Overview" in parent_part
        finally:
            for path in (ansi_path, companion_path, dump_path, ansi_path + ".test.vim"):
                if os.path.exists(path):
                    os.remove(path)


def test_cli_vim_link_navigation():
    """Test actual mdok CLI with --vim and check buffer mappings and link following."""
    if not shutil.which("vim"):
        pytest.skip("vim not installed")

    doc_path = os.path.abspath("examples/docs/architecture.md")
    master, slave = pty.openpty()
    dump_path = os.path.abspath("vim_test_dump.txt")
    if os.path.exists(dump_path):
        os.remove(dump_path)

    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        cmd = [sys.executable, "-m", "mdok.cli", "--vim", "--no-center", doc_path]
        os.execve(sys.executable, cmd, env)
    else:
        os.close(slave)
        output_chunks = []
        try:
            time.sleep(0.8)
            while True:
                r, _, _ = select.select([master], [], [], 0.05)
                if not r:
                    break
                chunk = os.read(master, 2048)
                if not chunk:
                    break
                output_chunks.append(chunk)

            # Move to Documentation Hub link
            os.write(master, b"/Documentation Hub\r")
            time.sleep(0.3)
            # Dismiss any prompt and check state
            cmd_check = (
                f":silent! call writefile(["
                f"'bufnr: ' . bufnr('%'), "
                f"'map_gf: ' . maparg('gf', 'n'), "
                f"'has_manifest: ' . string(exists('b:mdok_links_by_text')), "
                f"'getline: ' . getline('.'), "
                f"'col: ' . col('.') "
                f"], '{dump_path}')\r"
            )
            os.write(master, cmd_check.encode())
            time.sleep(0.4)
            os.write(master, b"\r")
            time.sleep(0.2)
            # Press gf to follow the link
            os.write(master, b"gf")
            time.sleep(0.8)
            # Check state after gf
            cmd_after = (
                f":silent! call writefile(readfile('{dump_path}') + ["
                f"'after_bufnr: ' . bufnr('%'), "
                f"'after_line1: ' . getline(1)"
                f"], '{dump_path}')\r"
            )
            os.write(master, cmd_after.encode())
            time.sleep(0.4)
            os.write(master, b"\r")
            time.sleep(0.2)
            os.write(master, b":qa!\r")
            time.sleep(0.3)
            while True:
                r, _, _ = select.select([master], [], [], 0.05)
                if not r:
                    break
                chunk = os.read(master, 2048)
                if not chunk:
                    break
                output_chunks.append(chunk)
        finally:
            try:
                os.kill(p, 9)
            except OSError:
                pass
            os.close(master)

        assert os.path.exists(dump_path), "Vim did not write dump file"
        with open(dump_path) as f:
            dump_content = f.read()
        print(">>> VIM CLI STATE DUMP <<<\n" + dump_content)
        if os.path.exists(dump_path):
            os.remove(dump_path)

        assert "map_gf: :call MdokFollowLink()<CR>" in dump_content
        assert "has_manifest: 1" in dump_content


def test_cli_nvim_link_navigation():
    """Test actual mdok CLI with --nvim and check buffer mappings and link following."""
    if not shutil.which("nvim"):
        pytest.skip("nvim not installed")

    doc_path = os.path.abspath("examples/docs/architecture.md")
    master, slave = pty.openpty()
    dump_path = os.path.abspath("nvim_test_dump.txt")
    if os.path.exists(dump_path):
        os.remove(dump_path)

    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        env = os.environ.copy()
        env["TERM"] = "xterm-256color"
        env["COLUMNS"] = "100"
        env["LINES"] = "30"
        cmd = [sys.executable, "-m", "mdok.cli", "--nvim", "--no-center", doc_path]
        os.execve(sys.executable, cmd, env)
    else:
        os.close(slave)
        output_chunks = []
        try:
            time.sleep(0.8)
            while True:
                r, _, _ = select.select([master], [], [], 0.05)
                if not r:
                    break
                chunk = os.read(master, 2048)
                if not chunk:
                    break
                output_chunks.append(chunk)

            # Move to Documentation Hub link
            os.write(master, b"/Documentation Hub\r")
            time.sleep(0.3)
            # Inspect nvim state
            cmd_check = (
                f":silent! call writefile(["
                f"'bufnr: ' . bufnr('%'), "
                f"'map_gf: ' . maparg('gf', 'n'), "
                f"'has_manifest: ' . string(exists('b:mdok_links_by_text')), "
                f"'getline: ' . getline('.'), "
                f"'col: ' . col('.') "
                f"], '{dump_path}')\r"
            )
            os.write(master, cmd_check.encode())
            time.sleep(0.4)
            os.write(master, b"\r")
            time.sleep(0.2)
            # Press gf
            os.write(master, b"gf")
            time.sleep(0.8)
            # Dump after gf
            cmd_after = (
                f":silent! call writefile(readfile('{dump_path}') + ["
                f"'after_bufnr: ' . bufnr('%'), "
                f"'after_line1: ' . getline(1)"
                f"], '{dump_path}')\r"
            )
            os.write(master, cmd_after.encode())
            time.sleep(0.4)
            os.write(master, b"\r")
            time.sleep(0.2)
            os.write(master, b":qa!\r")
            time.sleep(0.3)
            while True:
                r, _, _ = select.select([master], [], [], 0.05)
                if not r:
                    break
                chunk = os.read(master, 2048)
                if not chunk:
                    break
                output_chunks.append(chunk)
        finally:
            try:
                os.kill(p, 9)
            except OSError:
                pass
            os.close(master)

        assert os.path.exists(dump_path), "Neovim did not write dump file"
        with open(dump_path) as f:
            dump_content = f.read()
        print("NVIM CLI STATE DUMP:\n", dump_content)
        if os.path.exists(dump_path):
            os.remove(dump_path)

        assert "map_gf: :call MdokFollowLink()<CR>" in dump_content
        assert "has_manifest: 1" in dump_content


@pytest.mark.parametrize("engine", ["vim", "nvim"])
def test_smart_quit_and_jump_to_end(engine):
    """Verify MdokJumpToEnd skips trailing blank lines and MdokSmartQuit pops back."""
    bin_path = shutil.which(engine)
    if not bin_path:
        pytest.skip(f"{engine} not installed")

    with tempfile.NamedTemporaryFile("w", suffix="1.ansi", delete=False) as f1:
        f1.write("ROOT DOC Line 1\nROOT DOC Line 2 [📄 Child Doc]\nROOT DOC Line 3\n")
        path1 = f1.name

    with tempfile.NamedTemporaryFile("w", suffix="2.ansi", delete=False) as f2:
        f2.write("CHILD DOC Line 1\nCHILD DOC Line 2\nCHILD DOC Line 3\nCHILD DOC Line 4\n")
        path2 = f2.name

    dump_path = path1 + ".dump"
    script_file = path1 + ".vim"

    from mdok.editor import generate_vim_script
    base_script = generate_vim_script(
        ansi_path=path1,
        source_file=None,
        links_by_line={},
        links_by_text={},
        editor_type=engine,
    )

    test_harness = f"""
set nocompatible
{base_script}

function! TestFlow() abort
  if has('nvim')
    execute 'terminal cat {path1}'
  else
    let g:b1 = term_start(['cat', '{path1}'], {{'curwin': 1, 'term_finish': 'open'}})
  endif
  let g:buf1 = bufnr('%')
  sleep 300m
  if has('nvim')
    call feedkeys("\\<C-\\>\\<C-n>", "n")
  else
    call feedkeys("\\<C-W>N", "n")
  endif

  " Push nav stack and open child doc
  call add(g:mdok_nav_stack, {{'buf': g:buf1, 'pos': [0, 2, 5, 0], 'file': '', 'ansi': ''}})
  if has('nvim')
    enew
    execute 'terminal cat {path2}'
  else
    let g:b2 = term_start(['cat', '{path2}'], {{'curwin': 1, 'term_finish': 'open'}})
  endif
  let g:buf2 = bufnr('%')
  sleep 300m
  if has('nvim')
    call feedkeys("\\<C-\\>\\<C-n>", "n")
  else
    call feedkeys("\\<C-W>N", "n")
  endif

  " Test Jump to End on child doc
  call MdokJumpToEnd()
  let l:child_end_ln = line('.')
  let l:child_end_txt = getline('.')

  " Test Smart Quit (should go back to root doc)
  call MdokSmartQuit()
  sleep 300m
  let l:restored_buf = bufnr('%')
  let l:restored_txt = getline('.')

  call writefile([string(l:child_end_ln), l:child_end_txt, string(l:restored_buf == g:buf1), l:restored_txt], '{dump_path}')
  qa!
endfunction

autocmd VimEnter * call timer_start(50, {{-> TestFlow()}})
"""

    with open(script_file, "w") as sf:
        sf.write(test_harness)

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
        cmd = [bin_path, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(bin_path, cmd)
    else:
        os.close(slave)
        output_chunks = []
        start = time.time()
        while time.time() - start < 5:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                    output_chunks.append(data)
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            raw_out = b"".join(output_chunks).decode("utf-8", errors="replace")
            assert os.path.exists(dump_path), f"{engine} test harness did not write dump file. Vim output:\n{raw_out}"
            with open(dump_path) as df:
                lines = [l.rstrip("\n") for l in df.readlines()]
            assert lines[0] == "4", f"Expected jump to line 4, got {lines[0]}"
            assert "CHILD DOC Line 4" in lines[1]
            assert lines[2] == "1", "Did not restore root buffer"
            assert "ROOT DOC Line 2" in lines[3]
        finally:
            for p in (path1, path2, dump_path, script_file):
                if os.path.exists(p):
                    os.remove(p)

