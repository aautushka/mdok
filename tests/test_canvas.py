import pytest
from rich.console import Console
from rich.text import Text

from mdok.canvas import CanvasConfig, calculate_dimensions, DocumentCanvas


def test_calculate_dimensions_wide_terminal():
    # On a wide screen (180 columns), document width scales proportionally
    # up to cap_width (124) with generous margins, avoiding an artificial narrow wall
    cfg = CanvasConfig()
    doc_width, left_margin = calculate_dimensions(180, cfg)
    assert doc_width == 124
    assert left_margin == (180 - 124) // 2


def test_calculate_dimensions_medium_terminal():
    # On medium screen (100 columns), doc_width should adapt nicely (~84 columns)
    cfg = CanvasConfig()
    doc_width, left_margin = calculate_dimensions(100, cfg)
    assert 80 <= doc_width <= 90
    assert left_margin == (100 - doc_width) // 2


def test_calculate_dimensions_narrow_terminal():
    # On narrow screen (60 columns), doc_width should maximize usable space
    cfg = CanvasConfig()
    doc_width, left_margin = calculate_dimensions(60, cfg)
    assert doc_width == 56
    assert left_margin == 2


def test_calculate_dimensions_explicit_width_and_margin():
    cfg = CanvasConfig(max_width=75, margin=10)
    doc_width, left_margin = calculate_dimensions(120, cfg)
    assert doc_width == 75
    assert left_margin == 10


def test_calculate_dimensions_no_center():
    cfg = CanvasConfig(center=False)
    doc_width, left_margin = calculate_dimensions(140, cfg)
    assert doc_width == 103
    assert left_margin == 0


def test_document_canvas_renders_margin():
    console = Console(width=100, record=True)
    text = Text("Hello Document")
    canvas = DocumentCanvas(text, doc_width=50, left_margin=15)

    with console.capture() as capture:
        console.print(canvas)

    output = capture.get()
    lines = output.splitlines()
    assert len(lines) >= 1
    # Check that the first line starts with 15 spaces
    assert lines[0].startswith(" " * 15 + "Hello Document")


def test_document_canvas_no_trailing_whitespace():
    # Verify that text rendered inside DocumentCanvas does not end with trailing spaces
    console = Console(width=100, record=True)
    # Paragraph with left justify (which historically padded spaces)
    text = Text("Line 1\n\nLine 2 is longer than line one", justify="left")
    canvas = DocumentCanvas(text, doc_width=60, left_margin=10)

    with console.capture() as capture:
        console.print(canvas)

    output = capture.get()
    lines = output.splitlines()
    for line in lines:
        if line.strip():  # non-empty line
            assert not line.endswith(" "), f"Line has trailing whitespace: {line!r}"
            assert line.startswith(" " * 10)
        else:  # empty / blank line
            assert line == "", f"Blank line has phantom spaces: {line!r}"


def test_doc_markdown_canvas_no_trailing_whitespace():
    # Verify that DocMarkdown with canvas layout does not emit trailing spaces
    from mdok.renderer import DocMarkdown
    console = Console(width=100, record=True)
    md_text = "# Header\n\nThis is a paragraph with several words.\n\n- Bullet 1\n- Bullet 2"
    doc_md = DocMarkdown(
        md_text,
        doc_width=60,
        left_margin=10,
        term_width=100,
    )

    with console.capture() as capture:
        console.print(doc_md)

    output = capture.get()
    lines = output.splitlines()
    for line in lines:
        if line.strip():
            assert not line.endswith(" "), f"Line has trailing whitespace: {line!r}"
        else:
            assert line == "", f"Blank line has phantom spaces: {line!r}"
