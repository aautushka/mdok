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
