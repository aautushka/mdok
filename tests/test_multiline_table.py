import pytest
from rich.console import Console
from mdok.renderer import DocMarkdown

MULTILINE_TABLE_MD = """
| Condition | Error Message | Solution |
| :--- | :--- | :--- |
| Channel Inversion: on() on output stream | engine: on() handler error! Stream '...' is an outbound channel. Outbound channels invoke events via send(); they cannot implement them via on(...). | Invoke via send() or register on an input channel. |
| Stream Missing Property: emit() on read-only stream | engine: emit<Tag>() failed! Field '...' on stream does not have a writer (<HAS-WRITER>false</HAS-WRITER>). Only fields with writers can be written via emit(). | Enable <HAS-WRITER>true</HAS-WRITER> in config or avoid calling emit(). |
| Missing Inbound Handler: on() on emitter | engine: on() handler error! Field '...' has no receiver. | Enable <HAS-WRITER>true</HAS-WRITER> in config. |
"""


def test_multiline_table_preserves_row_separation():
    # By default, show_lines=True should insert horizontal divider lines
    # between rows so long multiline rows never fuse together
    md = DocMarkdown(MULTILINE_TABLE_MD, box_style="booktabs", show_lines=True)
    console = Console(width=120, record=True, _environ={})
    with console.capture() as capture:
        console.print(md)
    output = capture.get()

    # Verify horizontal divider line exists between rows
    assert "─" in output
    # Verify rows are present
    assert "Channel" in output
    assert "Inversion:" in output
    assert "Stream" in output
    assert "Missing" in output
    assert "Inbound" in output


def test_preserves_technical_tags_in_tables():
    # Verify technical tags like <Tag> and <HAS-WRITER> are NOT stripped by the parser
    md = DocMarkdown(MULTILINE_TABLE_MD, box_style="booktabs")
    console = Console(width=120, record=True, _environ={})
    with console.capture() as capture:
        console.print(md)
    output = capture.get()

    assert "<Tag>" in output
    assert "<HAS-WRITER>" in output
    assert "</HAS-WRITER>" in output
