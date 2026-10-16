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

