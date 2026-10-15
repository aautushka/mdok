import pytest
from rich.console import Console
from mdok.renderer import DocMarkdown, DocParagraph

TABLE_WITH_BR_MD = """
| Command | Usage |
| :--- | :--- |
| `docker run` | Starts a container.<br>Supports multiple flags:<br/>- `-d` for detached<br />- `-p` for ports |
"""


def test_table_br_rendering():
    md = DocMarkdown(TABLE_WITH_BR_MD)
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()

    # The literal strings '<br>', '<br/>', '<br />' should NOT appear in output
    assert "<br>" not in output
    assert "<br/>" not in output
    assert "<br />" not in output

    # The text separated by <br> should be split across lines
    assert "Starts a container." in output
    assert "Supports multiple flags:" in output
    assert "- `-d` for detached" in output or "- -d for detached" in output


def test_paragraph_br_rendering():
    md = DocMarkdown("Line 1<br>Line 2<br />Line 3")
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()

    assert "<br>" not in output
    assert "<br />" not in output
    lines = [line.strip() for line in output.splitlines() if line.strip()]
    assert lines == ["Line 1", "Line 2", "Line 3"]


def test_code_literal_br_not_split():
    md = DocMarkdown("`<br>` and `<br/>`")
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()
    assert "<br>" in output
    assert "<br/>" in output

















