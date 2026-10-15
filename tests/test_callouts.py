import pytest
from rich.console import Console

from mdok.renderer import DocMarkdown

SAMPLE_ALERT_MD = """
> [!NOTE]
> This is an informative callout box.

> Standard blockquote without alert tag.
"""


def test_callouts_rendering():
    md = DocMarkdown(SAMPLE_ALERT_MD)
    console = Console(width=90, record=True)
    with console.capture() as capture:
        console.print(md)

    output = capture.get()
    assert "NOTE" in output
    assert "informative callout box" in output
    assert "Standard blockquote" in output
