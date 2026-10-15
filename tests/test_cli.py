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
