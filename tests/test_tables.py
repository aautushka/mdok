import pytest
from rich.console import Console

from mdok.renderer import DocMarkdown
from mdok.theme import BOX_STYLES



SAMPLE_TABLE_MD = """
| Feature | Alignment | Description |
| :--- | :---: | ---: |
| Left Col | Centered | $12,345.00 |
| Long Text | Mid | A somewhat longer text to verify wrapping behavior |
"""


def test_table_rendering():
    md = DocMarkdown(SAMPLE_TABLE_MD, box_style="booktabs")
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)

    output = capture.get()
    # Check that table headers and cells are present
    assert "Feature" in output
    assert "Alignment" in output
    assert "Description" in output
    assert "Left Col" in output
    assert "Centered" in output
    assert "$12,345.00" in output


def test_table_box_styles():
    for style_name in ["booktabs", "rounded", "minimal", "simple"]:
        md = DocMarkdown(SAMPLE_TABLE_MD, box_style=style_name)
        console = Console(width=90, record=True)
        with console.capture() as capture:
            console.print(md)
        output = capture.get()
        assert "Feature" in output


def test_table_bracketed_content():
    md_text = """
| Code | Type | Value |
|---|---|---|
| items[0] | std::vector<int>[N] | [Const] 42 |
"""
    md = DocMarkdown(md_text)
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()
    assert "items[0]" in output
    assert "std::vector<int>[N]" in output
    assert "[Const] 42" in output

