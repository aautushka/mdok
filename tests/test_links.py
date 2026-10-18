import os
import tempfile
import pytest
from rich.console import Console
from mdok.theme import DEFAULT_THEME
from mdok.renderer import DocMarkdown


def test_classify_link_types():
    with tempfile.TemporaryDirectory() as tmpdir:
        existing_file = os.path.join(tmpdir, "guide.md")
        with open(existing_file, "w") as f:
            f.write("# Guide")

        doc_file = os.path.join(tmpdir, "index.md")
        md = DocMarkdown("", source_path=doc_file)

        # 1. Existing local file
        link_type, exists, path = md.classify_link("guide.md")
        assert link_type == "file"
        assert exists is True
        assert path == "guide.md"

        # 2. Missing local file
        link_type, exists, path = md.classify_link("nonexistent.md")
        assert link_type == "file"
        assert exists is False
        assert path == "nonexistent.md"

        # 3. Same-document anchor
        link_type, exists, path = md.classify_link("#installation")
        assert link_type == "anchor"
        assert exists is False

        # 4. External web link
        link_type, exists, path = md.classify_link("https://github.com/astral-sh/uv")
        assert link_type == "external"
        assert exists is False


def test_render_local_file_link_existing():
    with tempfile.TemporaryDirectory() as tmpdir:
        existing_file = os.path.join(tmpdir, "setup.md")
        with open(existing_file, "w") as f:
            f.write("# Setup")

        doc_file = os.path.join(tmpdir, "readme.md")
        content = "Please see the [Setup Guide](setup.md) for instructions."
        md = DocMarkdown(content, source_path=doc_file, doc_width=80)

        console = Console(theme=DEFAULT_THEME, record=True, width=80)
        with console.capture() as capture:
            console.print(md)
        output = capture.get()

        # Should render [📄 Setup Guide]
        assert "[📄 Setup Guide]" in output
        # Should NOT dump the raw URL in parentheses into the prose
        assert "(setup.md)" not in output


def test_render_local_file_link_missing():
    with tempfile.TemporaryDirectory() as tmpdir:
        doc_file = os.path.join(tmpdir, "readme.md")
        content = "See [Legacy Notes](missing_notes.md) here."
        md = DocMarkdown(content, source_path=doc_file, doc_width=80)

        console = Console(theme=DEFAULT_THEME, record=True, width=80)
        with console.capture() as capture:
            console.print(md)
        output = capture.get()

        # Should render warning icon for missing target
        assert "[⚠️ Legacy Notes]" in output
        assert "(missing_notes.md)" not in output


def test_render_anchor_and_external_links():
    content = "Jump to [§ Quickstart](#quickstart) or visit [Website](https://example.com)."
    md = DocMarkdown(content, doc_width=80)

    console = Console(theme=DEFAULT_THEME, record=True, width=80)
    with console.capture() as capture:
        console.print(md)
    output = capture.get()

    # Anchor link has § badge
    assert "§" in output
    # External link has 🌐 badge
    assert "[🌐 Website]" in output
    # Clean sentence without raw URL dumped
    assert "(https://example.com)" not in output


def test_render_empty_link_label_uses_target_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        existing_file = os.path.join(tmpdir, "config.json")
        with open(existing_file, "w") as f:
            f.write("{}")

        doc_file = os.path.join(tmpdir, "readme.md")
        content = "Config is at [](config.json)."
        md = DocMarkdown(content, source_path=doc_file, doc_width=80)

        console = Console(theme=DEFAULT_THEME, record=True, width=80)
        with console.capture() as capture:
            console.print(md)
        output = capture.get()

        assert "[📄 config.json]" in output


def test_subtle_brackets_and_distinct_text_style():
    with tempfile.TemporaryDirectory() as tmpdir:
        existing_file = os.path.join(tmpdir, "doc.md")
        with open(existing_file, "w") as f:
            f.write("# Doc")

        content = "Read the [Documentation](doc.md) here."
        md = DocMarkdown(content, source_path=existing_file, doc_width=80)
        console = Console(theme=DEFAULT_THEME, width=80)

        # Inspect rendered segments
        segments = list(console.render(md))
        # Find segment for '[' and ']'
        bracket_segs = [s for s in segments if s.text in ("[", "]")]
        assert len(bracket_segs) == 2

        # Find segment with the file link text
        link_segs = [s for s in segments if "Documentation" in s.text]
        assert len(link_segs) == 1

        bracket_style = bracket_segs[0].style
        link_style = link_segs[0].style

        # Brackets must be dimmed / subtle
        assert bracket_style.dim is True

        # Link text must be distinct (bold) and not dimmed
        assert link_style.bold is True
        assert link_style.dim is not True
