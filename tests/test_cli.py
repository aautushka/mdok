import pytest
import tempfile
import os
from mdok.cli import parse_args, main


def test_parse_args_defaults():
    args = parse_args([])
    assert args.file == "-"
    assert args.width is None
    assert args.margin is None
    assert args.no_center is False
    assert args.box == "booktabs"


def test_parse_args_overrides():
    args = parse_args(["my_file.md", "-w", "80", "-m", "10", "--no-center", "-b", "rounded", "--no-pager"])
    assert args.file == "my_file.md"
    assert args.width == 80
    assert args.margin == 10
    assert args.no_center is True
    assert args.box == "rounded"
    assert args.no_pager is True


def test_main_with_file(capsys):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("# Hello World\n\nThis is a document test.")
        temp_path = f.name

    try:
        ret = main([temp_path, "--no-pager"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Hello World" in captured.out
        assert "This is a document test." in captured.out
    finally:
        os.remove(temp_path)


def test_parse_args_search_and_pager():
    args = parse_args(["doc.md", "-s", "Heading", "--pager-cmd", "cat"])
    assert args.search == "Heading"
    assert args.pager_cmd == "cat"


def test_parse_args_pager_engine_flags():
    assert parse_args(["doc.md", "--nvim"]).pager == "nvim"
    assert parse_args(["doc.md", "--vim"]).pager == "vim"
    assert parse_args(["doc.md", "--less"]).pager == "less"
    assert parse_args(["doc.md", "-p"]).pager == "auto"
    assert parse_args(["doc.md", "--pager", "less"]).pager == "less"



def test_main_with_pager_cmd(capfd):
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("# Pager Title\n\nContent for pager.")
        temp_path = f.name

    try:
        # Force pager with --pager and --pager-cmd cat
        ret = main([temp_path, "-p", "--pager-cmd", "cat"])
        assert ret == 0
        captured = capfd.readouterr()
        assert "Pager Title" in captured.out
        assert "Content for pager." in captured.out
    finally:
        os.remove(temp_path)


def test_main_with_docx_file(capsys):
    from tests.test_docx import create_in_memory_docx
    docx_bytes = create_in_memory_docx().getvalue()
    with tempfile.NamedTemporaryFile("wb", suffix=".docx", delete=False) as f:
        f.write(docx_bytes)
        temp_path = f.name

    try:
        ret = main([temp_path, "--no-pager"])
        assert ret == 0
        captured = capsys.readouterr()
        assert "Document Title" in captured.out
        assert "Heading 1 Section" in captured.out
        assert "Bold Text" in captured.out
        assert "GitHub Repo" in captured.out
    finally:
        os.remove(temp_path)


def test_main_with_docx_stdin(capsys, monkeypatch):
    import io
    from tests.test_docx import create_in_memory_docx
    docx_bytes = create_in_memory_docx().getvalue()

    class MockStdin:
        def __init__(self, data: bytes):
            self.buffer = io.BytesIO(data)
        def isatty(self):
            return False
        def read(self):
            return self.buffer.read().decode("utf-8", errors="replace")

    monkeypatch.setattr("sys.stdin", MockStdin(docx_bytes))

    ret = main(["-", "--no-pager"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Document Title" in captured.out
    assert "Heading 1 Section" in captured.out


def test_main_editor_pager_zero_leading_margin(monkeypatch):
    captured_output = []

    def fake_spawn_pager(engine, cmd, env, write_fn, term_width, theme=None):
        from rich.console import Console
        import io
        buf = io.StringIO()
        console = Console(file=buf, width=term_width, force_terminal=True)
        write_fn(console)
        captured_output.append((engine, cmd, buf.getvalue()))
        return 0

    monkeypatch.setattr("mdok.cli.spawn_pager", fake_spawn_pager)

    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
        f.write("# Clean Title\n\nSome paragraph text that starts at column 1.")
        temp_path = f.name

    try:
        # Run with --nvim and width=40, margin=10
        ret = main([temp_path, "--nvim", "-w", "40", "-m", "10"])
        assert ret == 0
        engine, cmd, rendered = captured_output[0]
        assert engine == "nvim"
        # The editor cmd should have received left_margin=10 -> vertical resize 9
        assert any("vertical resize 9" in arg for arg in cmd)
        # The rendered text inside the buffer should start at column 1 (no 10 leading spaces)
        lines = [line for line in rendered.splitlines() if "Clean Title" in line or "Some paragraph" in line]
        assert lines, "Expected matching lines in rendered buffer"
        for line in lines:
            import re
            plain = re.sub(r"\x1b\[[0-9;]*m", "", line)
            assert not plain.startswith("          "), f"Line has leading whitespace: {plain!r}"
            assert plain.startswith("#") or plain.startswith("Some") or plain.startswith("Clean")
    finally:
        os.remove(temp_path)



