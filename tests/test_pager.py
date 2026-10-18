import os
import shutil
import pytest
from mdok.pager import (
    build_pager_cmd,
    should_use_pager,
    detect_best_pager,
    resolve_pager,
    build_less_cmd,
    build_editor_cmd,
    spawn_pager,
)


def test_build_less_cmd():
    cmd = build_less_cmd("README.md", search_query="Installation")
    assert "less" in cmd[0]
    assert "-R" in cmd
    assert "-i" in cmd
    assert "-j.5" in cmd
    assert "-g" in cmd
    assert "-J" in cmd
    assert "--use-color" in cmd
    assert "-DSkY" in cmd
    assert "+/Installation" in cmd
    has_prompt = any(arg.startswith("-P") for arg in cmd)
    assert has_prompt


def test_build_editor_cmd_nvim():
    cmd = build_editor_cmd("nvim", "/tmp/test.ansi", filename="README.md", search_query="Installation")
    assert "nvim" in cmd[0]
    assert "--clean" not in cmd  # User's personal config/plugins should load
    assert any("terminal cat /tmp/test.ansi" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> Q :qa!<CR>" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> G :call MdokJumpToEnd()<CR>" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> <Space> <C-f>" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> n nzz" in arg for arg in cmd)
    assert any("ignorecase" in arg for arg in cmd)
    assert any("clipboard^=unnamed,unnamedplus" in arg for arg in cmd)
    assert any("mouse=a" in arg for arg in cmd)
    assert any("Installation" in arg for arg in cmd)
    assert any("MdokEditSource" in arg for arg in cmd)


def test_build_editor_cmd_preserves_temp_file_placeholder():
    cmd = build_editor_cmd("nvim", "{TEMP_FILE}")
    # Must NOT turn {TEMP_FILE} into /path/to/cwd/{TEMP_FILE}
    assert any("terminal cat {TEMP_FILE}" in arg for arg in cmd)
    assert not any(os.getcwd() in arg for arg in cmd)


def test_build_editor_cmd_vim():
    cmd = build_editor_cmd("vim", "/tmp/test.ansi", filename="README.md", search_query="Installation")
    assert "vim" in cmd[0]
    assert "--clean" not in cmd  # User's personal config/plugins should load
    assert any("startify_disable_at_vimenter" in arg for arg in cmd)
    assert any("term_start" in arg for arg in cmd)
    assert any("exit_cb" in arg for arg in cmd)
    assert any("timer_start" in arg for arg in cmd)
    assert any("clipboard^=unnamed,unnamedplus" in arg for arg in cmd)
    assert any("mouse=a" in arg for arg in cmd)
    assert any("Installation" in arg for arg in cmd)
    assert any("q :call MdokSmartQuit()<CR>" in arg for arg in cmd)
    assert any("Q :qa!<CR>" in arg for arg in cmd)
    assert any("G :call MdokJumpToEnd()<CR>" in arg for arg in cmd)
    assert any("nnoremap <buffer> <silent> <Space> <C-f>" in arg for arg in cmd)
    assert any("ignorecase" in arg for arg in cmd)
    # TermClose is a Neovim event; Vim throws E216 if used
    assert not any("TermClose" in arg for arg in cmd)


def test_build_editor_cmd_nvim_with_left_margin():
    cmd = build_editor_cmd("nvim", "/tmp/test.ansi", filename="README.md", left_margin=20)
    assert any("leftabove vnew" in arg for arg in cmd)
    assert any("vertical resize 19" in arg for arg in cmd)
    assert any("winfixwidth" in arg for arg in cmd)
    assert any("fillchars+=vert:" in arg for arg in cmd)
    assert any("WinSeparator" in arg for arg in cmd)
    assert any("WinClosed" in arg and "qa!" in arg for arg in cmd)


def test_build_editor_cmd_vim_with_left_margin():
    cmd = build_editor_cmd("vim", "/tmp/test.ansi", filename="README.md", left_margin=15)
    assert any("leftabove vnew" in arg for arg in cmd)
    assert any("vertical resize 14" in arg for arg in cmd)
    assert any("winfixwidth" in arg for arg in cmd)
    assert any("fillchars=vert:\u00a0,eob:\\ " in arg for arg in cmd)
    assert any("clear VertSplit" in arg for arg in cmd)
    assert any("clear WinSeparator" in arg for arg in cmd)
    assert any("noruler" in arg for arg in cmd)
    assert any("BufWipeout" in arg and "qa!" in arg for arg in cmd)


def test_detect_best_pager_hierarchy(monkeypatch):
    # Case 1: less is available
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/bin/{cmd}" if cmd == "less" else None)
    assert detect_best_pager() == "less"

    # Case 2: nothing available
    monkeypatch.setattr(shutil, "which", lambda cmd: None)
    assert detect_best_pager() == "stdout"


def test_resolve_pager_with_explicit_less(monkeypatch):
    # Even if nvim is available, pager_opt="less" forces less
    monkeypatch.setattr(shutil, "which", lambda cmd: f"/bin/{cmd}")
    engine, custom = resolve_pager(pager_opt="less")
    assert engine == "less"
    assert custom is None


def test_resolve_pager_with_custom_cmd():
    engine, custom = resolve_pager(pager_cmd="bat --paging=always")
    assert engine == "custom"
    assert custom == ["bat", "--paging=always"]


def test_resolve_pager_respects_mdok_pager_env(monkeypatch):
    monkeypatch.setenv("MDOK_PAGER", "less")
    engine, custom = resolve_pager()
    assert engine == "less"


def test_build_pager_cmd_returns_tuple():
    engine, cmd, env = build_pager_cmd("README.md", pager_opt="less")
    assert engine == "less"
    assert "less" in cmd[0]
    assert "-R" in cmd


def test_spawn_pager_streams_content(capfd):
    cmd = ["cat"]
    env = {}

    def write_fn(console):
        console.print("Paging test output")

    ret = spawn_pager("custom", cmd, env, write_fn, term_width=80)
    assert ret == 0
    captured = capfd.readouterr()
    assert "Paging test output" in captured.out


def test_should_use_pager():
    # Force pager on
    assert should_use_pager(is_tty=True, force_pager=True, no_pager=False, line_count=5, term_height=24) is True
    # Force pager off
    assert should_use_pager(is_tty=True, force_pager=False, no_pager=True, line_count=50, term_height=24) is False
    # Non-tty output should not page by default
    assert should_use_pager(is_tty=False, force_pager=False, no_pager=False, line_count=50, term_height=24) is False
    # Auto-detection: line count exceeds terminal height - 2
    assert should_use_pager(is_tty=True, force_pager=False, no_pager=False, line_count=23, term_height=24) is True
    # Auto-detection: line count fits in terminal
    assert should_use_pager(is_tty=True, force_pager=False, no_pager=False, line_count=10, term_height=24) is False
