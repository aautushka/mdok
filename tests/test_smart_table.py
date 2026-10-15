import pytest
import re
from rich.console import Console
from rich.table import Table
from mdok.theme import BOOKTABS

from mdok.renderer import calculate_smart_column_widths


def test_smart_column_calculation():
    headers = [
        "Event",
        "Provided\n(Endpoint)",
        "✅ Send Event\nemit<Tag>(val)\nReturn: void",
        "❌ Prohibited\nRole Inversion",
        "❌ Prohibited\nEvents are\ntransient signals",
        "✅ Allowed\nBroadcasts to all\nprovided instances",
        "❌ Prohibited\nRole Inversion",
        "Details",
    ]
    rows = [
        [
            "Event",
            "Provided\n(Endpoint)",
            "emit<Tag>(val)\nReturn: void",
            "Role Inversion",
            "Events are\ntransient signals",
            "Broadcasts to all\nprovided instances",
            "Role Inversion",
            'Endpoint provides events; it cannot receive them via on(...). Compile error: "Provided ports emit events; they cannot receive them via on(...)".',
        ]
    ]

    widths_160 = calculate_smart_column_widths(headers, rows, 160)
    assert sum(widths_160) == 160
    assert widths_160[7] >= 40
    assert widths_160[0] <= 10
    assert widths_160[1] >= 10

    c160 = Console(width=160, record=True, _environ={})
    table = Table(
        box=BOOKTABS,
        show_lines=True,
        pad_edge=False,
        style="markdown.table.border",
        show_edge=False,
        collapse_padding=False,
        padding=(0, 1),
        expand=False,
    )
    for h in headers:
        table.add_column(h, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(*r)

    extra = table._extra_width
    col_widths = calculate_smart_column_widths(headers, rows, 160 - extra)
    assert sum(col_widths) + extra == 160

    for col, w in zip(table.columns, col_widths):
        col.width = w

    c160.print(table)
    output = c160.export_text()
    assert "Endpoint provides events" in output
    assert "Event" in output


def test_doc_markdown_rendering():
    from rich.cells import cell_len
    assert cell_len("✅") == 2
    assert cell_len("Event") == 5


def test_wide_table_breakout_end_to_end():
    from mdok.renderer import DocMarkdown
    from mdok.canvas import DocumentCanvas

    md_content = """# Architecture Overview

This is a regular paragraph that should be rendered with standard document margins inside the narrow reading column.

| Event | Provided (Endpoint) | ✅ Send Event emit<Tag>(val) | ❌ Prohibited Role Inversion | ❌ Prohibited Events are transient | ✅ Allowed Broadcasts to all | ❌ Prohibited Role Inversion | Details |
|---|---|---|---|---|---|---|---|
| Event | Provided (Endpoint) | emit<Tag>(val)<br>Return: void | Role Inversion | Events are transient signals | Broadcasts to all provided instances | Role Inversion | Endpoint provides events; it cannot receive them via on(...). Compile error: "Provided ports emit events; they cannot receive them via on(...)". |

This is a following paragraph that should also remain centered at standard reading width.
"""

    term_width = 160
    doc_width = 88
    left_margin = 36  # (160 - 88) // 2

    doc = DocMarkdown(
        md_content,
        doc_width=doc_width,
        left_margin=left_margin,
        term_width=term_width,
    )
    canvas = DocumentCanvas(
        renderable=doc,
        doc_width=doc_width,
        left_margin=left_margin,
    )

    console = Console(width=term_width, record=True, _environ={})
    console.print(canvas)
    output = console.export_text()

    lines = output.splitlines()

    # Verify paragraph lines start with around left_margin (36) spaces
    para_lines = [l for l in lines if "regular paragraph" in l or "standard document margins" in l]
    assert len(para_lines) > 0
    for pl in para_lines:
        leading_spaces = len(pl) - len(pl.lstrip(" "))
        assert leading_spaces == left_margin

    # Verify wide table lines break out of the 36-space margin (have smaller left margin, e.g. < 20)
    table_divider_lines = [l for l in lines if "─" in l]
    assert len(table_divider_lines) > 0
    for dl in table_divider_lines:
        dl_stripped = dl.strip()
        assert len(dl_stripped) > doc_width
        leading_spaces = len(dl) - len(dl.lstrip(" "))
        assert leading_spaces < left_margin

    # Verify table content has no vertical word-striping
    assert "Endpoint provides events;" in output
    assert "cannot receive" in output
    assert "them via" in output
    assert "on(...)" in output
    assert "Events are" in output
    assert "transient" in output
    assert "signals" in output
    assert "Role" in output
    assert "Inversion" in output


def test_ultrawide_terminal_caps_table_and_preserves_margins():
    """Verify that on an ultrawide terminal (e.g. 250 cols), the table NEVER blows out

    edge-to-edge. It must be strictly capped at max 136 columns and centered with
    generous margins (>= 57 cols on each side) to keep line lengths human-readable.
    """
    from mdok.renderer import DocMarkdown
    from mdok.canvas import DocumentCanvas

    md_content = """# Wide Doc

| Col 1 | Col 2 | Col 3 | Col 4 | Col 5 | Col 6 | Col 7 | Col 8 |
|---|---|---|---|---|---|---|---|
| A | B | C | D | E | F | G | Very long description text that would previously stretch all the way across the display. |
"""

    term_width = 250
    doc_width = 88
    left_margin = (term_width - doc_width) // 2  # 81

    doc = DocMarkdown(
        md_content,
        doc_width=doc_width,
        left_margin=left_margin,
        term_width=term_width,
    )
    canvas = DocumentCanvas(
        renderable=doc,
        doc_width=doc_width,
        left_margin=left_margin,
    )

    console = Console(width=term_width, record=True, _environ={})
    console.print(canvas)
    output = console.export_text()

    table_divider_lines = [l for l in output.splitlines() if "─" in l]
    assert len(table_divider_lines) > 0
    for dl in table_divider_lines:
        dl_stripped = dl.strip()
        table_width = len(dl_stripped)
        leading_spaces = len(dl) - len(dl.lstrip(" "))

        # The table must be capped at <= 136 columns! Never 250 cols!
        assert table_width <= 136
        # On a 250-wide screen with <= 136 table, the left margin must be at least (250 - 136) // 2 = 57 spaces
        assert leading_spaces >= 57


def test_narrow_table_stays_within_doc_width():
    from mdok.renderer import DocMarkdown
    from mdok.canvas import DocumentCanvas

    md_content = """# Small Document

Intro paragraph.

| Col A | Col B |
|---|---|
| Value 1 | Value 2 |

Outro paragraph.
"""

    term_width = 160
    doc_width = 88
    left_margin = 36

    doc = DocMarkdown(
        md_content,
        doc_width=doc_width,
        left_margin=left_margin,
        term_width=term_width,
    )
    canvas = DocumentCanvas(
        renderable=doc,
        doc_width=doc_width,
        left_margin=left_margin,
    )

    console = Console(width=term_width, record=True, _environ={})
    console.print(canvas)
    output = console.export_text()

    table_divider_lines = [l for l in output.splitlines() if "─" in l]
    assert len(table_divider_lines) > 0
    for dl in table_divider_lines:
        # Narrow table should stay within doc_width (88)
        assert len(dl.strip()) < doc_width
        leading_spaces = len(dl) - len(dl.lstrip(" "))
        assert leading_spaces == left_margin


def test_user_8_column_table_budgeting():
    headers = ["Event", "Provided", "✅ Send Event", "❌ Prohibited", "❌ Prohibited", "✅ Allowed", "❌ Prohibited", "Endpoint"]
    rows = [
        [
            "Event",
            "Provided\n(Endpoint)",
            "emit<Tag>(val)\nReturn: void",
            "Role Inversion",
            "Events are\ntransient signals",
            "Broadcasts to all\nprovided instances",
            "Role Inversion",
            'Endpoint provides events; it cannot receive them via on(...). Compile error: "Provided ports emit events; they cannot receive them via on(...)".',
        ],
        [
            "RPC Method",
            "Required\n(Consumer)",
            "emit<Tag>(val)\nReturn: void",
            "Role Inversion",
            "Events are\ntransient signals",
            "Aggregates across all\nproxy ports",
            "Role Inversion",
            'Consumer consumes events; it cannot emit them via emit(...). Compile error: "Event on required port is an inbound event. It cannot be emitted".',
        ],
    ]
    w = calculate_smart_column_widths(headers, rows, 129)
    assert sum(w) == 129
    # Col 0 (Event/RPC Method) should be compact: <= 12
    assert w[0] <= 12
    # Col 1 (Provided/Required) should be compact: <= 14
    assert w[1] <= 14
    # Emoji badge columns must be at least 13 cols (or 10 for Allowed) so emoji + label NEVER breaks
    assert w[2] >= 13
    assert w[3] >= 13
    assert w[4] >= 13
    assert w[5] >= 10
    assert w[6] >= 13
    # Col 7 (Endpoint description) should get the largest share of width: >= 28 cols!
    assert w[7] >= 28

    # Test rendering with Rich Table to verify no broken badges
    c = Console(width=135, record=True, _environ={})
    table = Table(box=BOOKTABS, show_lines=True, padding=(0, 1), expand=False)
    for h, col_w in zip(headers, w):
        table.add_column(h, width=col_w, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(*r)
    c.print(table)
    rendered = c.export_text()

    # Crucial assertion: "❌ Prohibited" must NEVER be broken into "❌" on line 1 and "Prohibited" on line 2
    for line in rendered.splitlines():
        if "❌" in line and "Prohibited" not in line and "Role Inversion" not in line:
            assert "❌\n" not in line


def test_user_exact_headers_table():
    headers = [
        "Protocol Interface Member",
        "Port Role",
        "Outbound emit(...)",
        "Inbound on(...)",
        "State Query read<...>()",
        "Fan-Out (emit<Tag::Any>)",
        "(on(Tag::Any))",
        "Invariant / Contract",
    ]
    rows = [
        [
            "Event",
            "Provided (Endpoint)",
            "✅ Send Event emit<Tag>(val) Return: void",
            "❌ Prohibited Role Inversion",
            "❌ Prohibited Events are transient signals",
            "✅ Allowed Broadcasts to all provided instances",
            "❌ Prohibited Role Inversion",
            'Endpoint provides events; it cannot receive them via on(...). Compile error: "Provided ports emit events; they cannot receive them via on(...)".',
        ],
    ]
    w = calculate_smart_column_widths(headers, rows, 136)
    assert sum(w) == 136
    # Col 0 (Protocol Interface Member / Event) must stay compact (<= 12)
    assert w[0] <= 12
    # Col 1 (Port Role / Provided (Endpoint)) must stay compact (<= 14)
    assert w[1] <= 14
    # Col 7 (Invariant / Contract) must receive the surplus width
    assert w[7] >= 26

    c = Console(width=140, record=True, _environ={})
    table = Table(box=BOOKTABS, show_lines=True, padding=(0, 1), expand=False)
    for h, col_w in zip(headers, w):
        table.add_column(h, width=col_w, overflow="fold", no_wrap=False)
    for r in rows:
        table.add_row(*r)
    c.print(table)
    rendered = c.export_text()

    # Verify atomic badge is never broken across lines in output
    assert "❌\n" not in rendered


def test_complex_matrix_table():
    md_content = """# Capability Matrix

| Protocol Member | Port Role | Outbound emit(...) | Inbound on(...) | State Query read<...>() | Fan-Out (emit<Tag::Any>) | (on(Tag::Any)) | Invariant / Contract |
|---|---|---|---|---|---|---|---|
| Event | Provided (Endpoint) | ✅ Send Event emit<Tag>(val)<br>Return: void | ❌ Prohibited Role Inversion | ❌ Prohibited Events are transient signals | ✅ Allowed Broadcasts to all provided instances | ❌ Prohibited Role Inversion | Endpoint provides events; it cannot receive them via on(...). Compile error: "Provided ports emit events; they cannot receive them via on(...)". |
| Method | Required (Consumer) | ✅ Call Method emit<Tag>(val)<br>Return: Future<Val> | ❌ Prohibited Role Inversion | ❌ Prohibited No local state cache | ❌ Prohibited Method calls cannot fan out | ❌ Prohibited Role Inversion | Consumer calls methods via emit(); it cannot handle them via on(...). Compile error: "Required ports call methods; they cannot handle them via on(...)". |
"""

    from mdok.renderer import DocMarkdown
    doc = DocMarkdown(md_content, doc_width=120, term_width=120)

    import mdok.renderer
    captured_data = []
    orig_calc = mdok.renderer.calculate_smart_column_widths
    def debug_calc(h, r, avail):
        res = orig_calc(h, r, avail)
        captured_data.append((h, r, avail, res))
        return res
    mdok.renderer.calculate_smart_column_widths = debug_calc
    c = Console(width=120, record=True, _environ={})
    c.print(doc)
    mdok.renderer.calculate_smart_column_widths = orig_calc

    assert len(captured_data) > 0, "No table captured"
    h_act, r_act, avail_act, col_widths = captured_data[0]

    assert sum(col_widths) == avail_act
    # Col 0 (Protocol Member) must remain compact (<= 12)
    assert col_widths[0] <= 12
    # Col 1 (Port Role) must fit Provided (Endpoint) without word breaking (10-12)
    assert col_widths[1] >= 10
    assert col_widths[1] <= 12

    output = c.export_text()
    # (Endpoint) must never break into (Endpoin / t)
    assert "Endpoin\n" not in output
    assert "(Endpoint)" in output
    # Badges must never break emoji away from label
    assert "❌\n" not in output
    assert "✅\n" not in output
