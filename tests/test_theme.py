import pytest
from rich.console import Console
from rich.style import Style
from mdok.theme import DEFAULT_THEME
from mdok.renderer import DocMarkdown


def test_code_style_in_theme():
    style = DEFAULT_THEME.styles.get("markdown.code")
    assert style is not None

def test_inline_code_rendering():
    md = DocMarkdown("Here is `inline_code()` in prose.")
    console = Console(theme=DEFAULT_THEME, record=True, width=80)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()
    assert "inline_code()" in output

def test_available_pygments_styles():
    from pygments.styles import get_all_styles
    styles = set(get_all_styles())
    assert "gruvbox-dark" in styles
    assert "dracula" in styles
    assert "nord" in styles

def test_code_block_with_nord():
    code_md = "```python\ndef hello(name: str):\n    print(f'Hello {name}')\n```"
    md = DocMarkdown(code_md, code_theme="nord")
    console = Console(theme=DEFAULT_THEME, record=True, width=80)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()
    assert "hello" in output




