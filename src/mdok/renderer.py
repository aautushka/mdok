import re
from typing import ClassVar, Dict, List, Optional, Tuple, Union
from rich.box import Box
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderResult, Group
from rich.markdown import (
    Markdown,
    MarkdownContext,
    MarkdownElement,
    MarkdownIt,
    TableBodyElement,
    TableHeaderElement,
    TableRowElement,
    TableDataElement,
    Paragraph,
    BlockQuote,
    Heading,
    Link,
    UnknownElement,
)
from rich.segment import Segment
from rich.table import Table
from rich.text import Text, TextType
from rich.panel import Panel
from rich.style import Style

from mdok.theme import BOOKTABS, BOX_STYLES
from mdok.canvas import rstrip_segments


def calculate_smart_column_widths(
    headers: List[str],
    rows: List[List[str]],
    available_width: int,
) -> List[int]:
    """
    Calculates balanced column widths using non-linear volume-weighted allocation.

    - Every column is guaranteed at least its longest unbreakable token + padding
      (atomic badge & token preservation).
    - Unwrapped ideal widths are respected (tables that fit stay compact).
    - Surplus space is distributed via a continuous utility function weighted by
      information volume (total text / rows), ensuring prose/description columns
      receive comfortable reading widths without inflating short token columns.
    """
    col_count = len(headers)
    if col_count == 0:
        return []
    if col_count == 1:
        return [max(3, available_width)]

    min_widths = [0] * col_count
    ideal_widths = [0] * col_count
    total_lens = [0] * col_count

    num_rows = max(1, len(rows))

    badge_pattern = re.compile(r"^([\u2600-\u27bf\U0001f300-\U0001f9ff]\s*\S+)")

    def _token_min(word: str) -> int:
        subparts = [p for p in re.split(r"[-/]", word) if p]
        if subparts:
            return max(cell_len(p) for p in subparts)
        return cell_len(word)

    for c in range(col_count):
        h_text = headers[c] if c < len(headers) else ""
        body_cells = [r[c] if c < len(r) else "" for r in rows]

        b_min = 2
        badge_min = 0
        body_ideal = 0
        body_tot = 0
        has_body_content = False

        # Measure body cells: body cells define ideal width, volume, and primary min-content
        for cell in body_cells:
            plain = str(cell)
            cell_length = cell_len(plain)
            if cell_length > 0:
                has_body_content = True
            body_tot += cell_length
            lines = plain.split("\n")
            for line in lines:
                body_ideal = max(body_ideal, cell_len(line))
                badge_m = badge_pattern.match(line.strip())
                if badge_m:
                    badge_min = max(badge_min, cell_len(badge_m.group(1)))
                for word in line.split():
                    # Token min length, capped at 13 so code signatures don't starve other columns
                    b_min = max(b_min, min(_token_min(word), 13))

        # Measure header: header sets wrap boundary, but does not dictate width
        # if body content is sparse (headers can wrap / fold)
        h_min = 2
        h_ideal = 0
        h_plain = str(h_text)
        for line in h_plain.split("\n"):
            h_ideal = max(h_ideal, cell_len(line))
            badge_m = badge_pattern.match(line.strip())
            if badge_m:
                badge_min = max(badge_min, cell_len(badge_m.group(1)))
            for word in line.split():
                h_min = max(h_min, min(_token_min(word), 13))

        if has_body_content:
            # Atomic badges must never be split. Body tokens and header tokens set min width.
            # Long header tokens fold if body is sparse.
            col_min = max(badge_min, b_min, h_min)
            min_widths[c] = col_min
            ideal_widths[c] = max(min_widths[c], body_ideal, h_ideal)
            total_lens[c] = body_tot
        else:
            col_min = max(badge_min, h_min, 3)
            min_widths[c] = col_min
            ideal_widths[c] = max(min_widths[c], h_ideal)
            total_lens[c] = cell_len(h_plain)

    total_ideal = sum(ideal_widths)
    if total_ideal <= available_width:
        return ideal_widths

    sum_min = sum(min_widths)
    if sum_min >= available_width:
        deficit = sum_min - available_width
        allocated = list(min_widths)
        while deficit > 0:
            candidates = [c for c in range(col_count) if allocated[c] > 3]
            if not candidates:
                break
            best_c = max(candidates, key=lambda c: (allocated[c], -c))
            allocated[best_c] -= 1
            deficit -= 1
        return allocated

    surplus = available_width - sum_min
    extra_wanted = [ideal_widths[c] - min_widths[c] for c in range(col_count)]

    # Continuous volume-weighted utility function
    # Columns with high text volume (narratives, descriptions) receive the lion's share
    # of surplus width, while short token columns remain compact.
    weights = []
    for c in range(col_count):
        if extra_wanted[c] <= 0:
            weights.append(0.0)
        else:
            avg_vol = total_lens[c] / (num_rows + 1)
            weights.append(extra_wanted[c] * (avg_vol ** 1.5))

    sum_weights = sum(weights) or 1.0

    allocated = list(min_widths)
    for c in range(col_count):
        if weights[c] > 0:
            share = int(surplus * (weights[c] / sum_weights))
            allocated[c] += min(share, extra_wanted[c])

    remainder = available_width - sum(allocated)
    while remainder > 0:
        candidates = [
            (total_lens[c], extra_wanted[c] - (allocated[c] - min_widths[c]), c)
            for c in range(col_count)
            if (allocated[c] - min_widths[c]) < extra_wanted[c]
        ]
        if not candidates:
            best_c = max(range(col_count), key=lambda c: total_lens[c])
            allocated[best_c] += remainder
            break
        candidates.sort(reverse=True)
        _, can_add, best_c = candidates[0]
        step = min(remainder, max(1, can_add))
        allocated[best_c] += step
        remainder -= step

    diff = available_width - sum(allocated)
    if diff != 0:
        best_c = max(range(col_count), key=lambda c: total_lens[c])
        allocated[best_c] = max(3, allocated[best_c] + diff)

    return allocated


class DocTableElement(MarkdownElement):
    """
    Enhanced Table element with:
    - Clean Booktabs borders (or configurable box style)
    - Row separation lines to prevent multi-line rows fusing together
    - Respected column alignments (left, center, right)
    - Soft word wrapping without breaking layout
    - Smart column width budgeting (wide tables don't vertically collapse)
    """

    box_style: ClassVar[Box] = BOOKTABS
    show_lines: ClassVar[bool] = True

    def __init__(self) -> None:
        self.header: Optional[TableHeaderElement] = None
        self.body: Optional[TableBodyElement] = None

    def on_child_close(self, context: MarkdownContext, child: MarkdownElement) -> bool:
        if isinstance(child, TableHeaderElement):
            self.header = child
        elif isinstance(child, TableBodyElement):
            self.body = child
        else:
            raise RuntimeError(f"Unexpected child in table: {type(child)}")
        return False

    def get_column_data(self) -> Tuple[List[str], List[List[str]]]:
        headers: List[str] = []
        if self.header is not None and self.header.row is not None:
            for cell in self.header.row.cells:
                headers.append(cell.content.plain)
        elif self.body is not None and self.body.rows:
            headers = [f"Col {i+1}" for i in range(len(self.body.rows[0].cells))]

        rows: List[List[str]] = []
        if self.body is not None:
            for row in self.body.rows:
                rows.append([cell.content.plain for cell in row.cells])
        return headers, rows

    def get_ideal_width(self) -> int:
        headers, rows = self.get_column_data()
        col_count = len(headers)
        if col_count == 0:
            return 0
        ideal_widths = [0] * col_count
        for c in range(col_count):
            h_text = headers[c] if c < len(headers) else ""
            all_cells = [h_text] + [r[c] if c < len(r) else "" for r in rows]
            c_ideal = 2
            for cell in all_cells:
                plain = str(cell)
                for line in plain.split("\n"):
                    c_ideal = max(c_ideal, cell_len(line))
            ideal_widths[c] = c_ideal + 2
        extra = max(0, col_count - 1)
        return sum(ideal_widths) + extra

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        table = Table(
            box=self.box_style,
            show_lines=self.show_lines,
            pad_edge=False,
            style="markdown.table.border",
            show_edge=False,
            collapse_padding=False,
            padding=(0, 1),
            expand=False,
        )

        headers, rows = self.get_column_data()
        column_count = len(headers)

        if self.header is not None and self.header.row is not None:
            for cell in self.header.row.cells:
                heading = cell.content.copy()
                heading.stylize("markdown.table.header")
                justify = getattr(cell, "justify", "left")
                table.add_column(
                    heading,
                    justify=justify,
                    overflow="fold",
                    no_wrap=False,
                )
        elif self.body is not None and self.body.rows:
            for cell in self.body.rows[0].cells:
                justify = getattr(cell, "justify", "left")
                table.add_column(justify=justify, overflow="fold", no_wrap=False)

        if self.body is not None:
            for row in self.body.rows:
                row_content = [cell.content for cell in row.cells]
                while len(row_content) < column_count:
                    row_content.append(Text(""))
                table.add_row(*row_content[:column_count])

        # Apply smart column widths
        if column_count > 0:
            extra = table._extra_width
            total_padding = sum(table._get_padding_width(i) for i in range(column_count))
            avail = max(column_count * 3, options.max_width - extra - total_padding)
            col_widths = calculate_smart_column_widths(headers, rows, avail)
            for col, w in zip(table.columns, col_widths):
                col.width = w

        yield Text("")  # Spacing before table
        yield table
        yield Text("")  # Spacing after table


BR_PATTERN = re.compile(r"(?i)<br\s*/?>")


class DocTableDataElement(TableDataElement):
    """
    Table data cell supporting <br>, <br/>, <br /> HTML line breaks
    inside table cells.
    """

    def on_text(self, context: MarkdownContext, text: TextType) -> None:
        code_style = context.console.get_style("markdown.code", default=None)
        is_code = code_style is not None and context.current_style == code_style
        if isinstance(text, str) and not is_code:
            parts = BR_PATTERN.split(text)
            if len(parts) > 1:
                for i, part in enumerate(parts):
                    if i > 0:
                        self.content.append("\n")
                    if part:
                        self.content.append(part, context.current_style)
                return
            self.content.append(text, context.current_style)
        elif isinstance(text, str):
            self.content.append(text, context.current_style)
        else:
            self.content.append_text(text)


class DocParagraph(Paragraph):
    """
    Paragraph supporting <br>, <br/>, <br /> HTML line breaks.
    """

    def on_text(self, context: MarkdownContext, text: TextType) -> None:
        code_style = context.console.get_style("markdown.code", default=None)
        is_code = code_style is not None and context.current_style == code_style
        if isinstance(text, str) and not is_code:
            parts = BR_PATTERN.split(text)
            if len(parts) > 1:
                for i, part in enumerate(parts):
                    if i > 0:
                        self.text.append("\n")
                    if part:
                        self.text.append(part, context.current_style)
                return
            self.text.append(text, context.current_style)
        elif isinstance(text, str):
            self.text.append(text, context.current_style)
        else:
            self.text.append_text(text)

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Standard Rich Paragraph sets justify="left" if not specified, which forces
        # line wrapping to pad trailing spaces across the full width. Setting justify to None
        # preserves clean natural wrapping without phantom trailing spaces on yank.
        self.text.justify = None
        yield self.text




ALERT_TYPES = {
    "[!NOTE]": ("NOTE", "cyan", "ℹ"),
    "[!TIP]": ("TIP", "green", "💡"),
    "[!IMPORTANT]": ("IMPORTANT", "magenta", "★"),
    "[!WARNING]": ("WARNING", "#e0af68", "⚠"),
    "[!CAUTION]": ("CAUTION", "red", "✖"),
}



class DocBlockQuote(BlockQuote):
    """
    Enhanced blockquote supporting GitHub-style alert callouts:
    > [!NOTE]
    > [!TIP]
    > [!WARNING]
    > [!IMPORTANT]
    > [!CAUTION]
    """

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Check if blockquote starts with an alert marker
        raw_text = ""
        for el in self.elements:
            if hasattr(el, "text"):
                raw_text = str(el.text).strip()
                break

        first_word = raw_text.split()[0].upper() if raw_text else ""
        if first_word in ALERT_TYPES:
            label, color, icon = ALERT_TYPES[first_word]
            # Strip the marker prefix from the first element's text
            for el in self.elements:
                if hasattr(el, "text") and hasattr(el.text, "plain"):
                    idx = el.text.plain.upper().find(first_word)
                    if idx != -1:
                        cut = idx + len(first_word)
                        # Slice text past marker and strip leading space
                        stripped_plain = el.text.plain[cut:].lstrip()
                        el.text = Text(stripped_plain)
                    break

            content_renderables = list(self.elements)
            panel = Panel(
                Group(*content_renderables),
                title=f"[{color} bold]{icon} {label}[/]",
                title_align="left",
                border_style=f"dim {color}",
                padding=(0, 1),
            )
            yield panel
        else:
            # Fall back to standard blockquote rendering
            yield from super().__rich_console__(console, options)


class DocHeading(Heading):
    """Heading rendered without trailing space padding."""

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        # Standard Rich Heading centers h1 and h2 by setting text.justify="center",
        # which pads both sides with spaces across the entire options.max_width.
        # When rendered in left-aligned documents or pagers, left-aligned headings
        # without padding provide clean visual reading and zero phantom whitespace on yank.
        self.text.justify = None
        yield self.text


class DocMarkdown(Markdown):
    """
    Markdown renderer configured with document-grade elements and smart wide table breakout.
    """
    elements = Markdown.elements.copy()
    elements["heading_open"] = DocHeading
    elements["table_open"] = DocTableElement
    elements["td_open"] = DocTableDataElement
    elements["th_open"] = DocTableDataElement
    elements["paragraph_open"] = DocParagraph
    elements["blockquote_open"] = DocBlockQuote

    def __init__(
        self,
        markup: str,
        code_theme: str = "nord",
        box_style: str = "booktabs",
        show_lines: bool = True,
        doc_width: Optional[int] = None,
        left_margin: int = 0,
        term_width: Optional[int] = None,
        **kwargs,
    ) -> None:
        # Avoid calling super().__init__(markup, ...) because that invokes MarkdownIt()
        # and parses markup fully once, only for us to parse it again immediately below.
        self.markup = markup
        self.code_theme = code_theme
        self.justify = kwargs.get("justify")
        self.style = kwargs.get("style", "none")
        self.hyperlinks = kwargs.get("hyperlinks", True)
        self.inline_code_lexer = kwargs.get("inline_code_lexer")
        self.inline_code_theme = kwargs.get("inline_code_theme")

        # Parse with html_inline and html_block disabled so technical tags
        # (like C++ templates <Tag> or XML tags <HAS-SETTER>) are preserved as plain text
        parser = (
            MarkdownIt()
            .enable("strikethrough")
            .enable("table")
            .disable("html_inline", "html_block")
        )
        self.parsed = parser.parse(markup)

        # Configure table box style and row separation
        selected_box = BOX_STYLES.get(box_style, BOOKTABS)
        DocTableElement.box_style = selected_box
        DocTableElement.show_lines = show_lines

        self.doc_width = doc_width
        self.left_margin = left_margin
        self.term_width = term_width or doc_width
        self.has_canvas_layout = doc_width is not None

    def _render_top_element(
        self,
        console: Console,
        options: ConsoleOptions,
        element: MarkdownElement,
        need_new_line: bool,
        new_line_segment: Segment,
    ) -> RenderResult:
        if need_new_line:
            yield new_line_segment

        # Check for table breakout
        if isinstance(element, DocTableElement) and self.doc_width is not None:
            ideal_w = element.get_ideal_width()
            if ideal_w > self.doc_width:
                # Table wants more width than the standard document column.
                # Allow a moderate breakout to prevent suffocated columns, but strictly
                # cap it to a human-readable width (max 136 cols) to avoid unreadable
                # edge-to-edge blowout across ultrawide monitors.
                term_w = self.term_width or self.doc_width
                readable_table_cap = max(self.doc_width, 136)
                max_table_w = min(readable_table_cap, max(self.doc_width, term_w - 6))
                target_w = min(ideal_w, max_table_w)
                target_margin = max(0, (term_w - target_w) // 2) if self.left_margin > 0 else 0
                elem_options = options.update_width(target_w)
                elem_margin = target_margin
            else:
                elem_options = options.update_width(self.doc_width)
                elem_margin = self.left_margin
        elif self.doc_width is not None:
            elem_options = options.update_width(self.doc_width)
            elem_margin = self.left_margin
        else:
            elem_options = options
            elem_margin = 0

        lines = console.render_lines(element, elem_options, pad=False)
        margin_prefix = " " * elem_margin if elem_margin > 0 else ""
        margin_segment = Segment(margin_prefix) if margin_prefix else None

        for line in lines:
            stripped = rstrip_segments(line)
            if margin_segment and stripped:
                yield margin_segment
                for seg in stripped:
                    yield seg
                yield Segment.line()
            elif not stripped:
                yield Segment.line()
            else:
                for seg in stripped:
                    yield seg
                yield Segment.line()

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render markdown to the console, with breakout support for wide tables."""
        if not self.has_canvas_layout:
            yield from super().__rich_console__(console, options)
            return

        style = console.get_style(self.style, default="none")
        options = options.update(height=None)
        context = MarkdownContext(
            console,
            options,
            style,
            inline_code_lexer=self.inline_code_lexer,
            inline_code_theme=self.inline_code_theme,
        )
        tokens = self.parsed
        inline_style_tags = self.inlines
        new_line = False
        _new_line_segment = Segment.line()

        for token in self._flatten_tokens(tokens):
            node_type = token.type
            tag = token.tag

            entering = token.nesting == 1
            exiting = token.nesting == -1
            self_closing = token.nesting == 0

            if node_type == "text":
                context.on_text(token.content, node_type)
            elif node_type == "hardbreak":
                context.on_text("\n", node_type)
            elif node_type == "softbreak":
                context.on_text(" ", node_type)
            elif node_type == "link_open":
                href = str(token.attrs.get("href", ""))
                if self.hyperlinks:
                    link_style = console.get_style("markdown.link_url", default="none")
                    link_style += Style(link=href)
                    context.enter_style(link_style)
                else:
                    context.stack.push(Link.create(self, token))
            elif node_type == "html_inline":
                if token.content == "<kbd>":
                    kbd_style = console.get_style("markdown.kbd", default="bold")
                    context.enter_style(kbd_style)
                elif token.content == "</kbd>":
                    context.leave_style()
                else:
                    continue
            elif node_type == "link_close":
                if self.hyperlinks:
                    context.leave_style()
                else:
                    element = context.stack.pop()
                    assert isinstance(element, Link)
                    link_style = console.get_style("markdown.link", default="none")
                    context.enter_style(link_style)
                    context.on_text(element.text.plain, node_type)
                    context.leave_style()
                    context.on_text(" (", node_type)
                    link_url_style = console.get_style(
                        "markdown.link_url", default="none"
                    )
                    context.enter_style(link_url_style)
                    context.on_text(element.href, node_type)
                    context.leave_style()
                    context.on_text(")", node_type)
            elif (
                tag in inline_style_tags
                and node_type != "fence"
                and node_type != "code_block"
            ):
                if entering:
                    context.enter_style(f"markdown.{tag}")
                elif exiting:
                    context.leave_style()
                else:
                    context.enter_style(f"markdown.{tag}")
                    if token.content:
                        context.on_text(token.content, node_type)
                    context.leave_style()
            else:
                element_class = self.elements.get(token.type) or UnknownElement
                element = element_class.create(self, token)

                if entering or self_closing:
                    context.stack.push(element)
                    element.on_enter(context)

                if exiting:
                    element = context.stack.pop()
                    should_render = not context.stack or (
                        context.stack
                        and context.stack.top.on_child_close(context, element)
                    )
                    if should_render:
                        if not context.stack:
                            yield from self._render_top_element(
                                console, options, element, new_line, _new_line_segment
                            )
                        else:
                            if new_line:
                                yield _new_line_segment
                            yield from console.render(element, context.options)
                elif self_closing:
                    context.stack.pop()
                    text = token.content
                    if text is not None:
                        element.on_text(context, text)

                    should_render = (
                        not context.stack
                        or context.stack
                        and context.stack.top.on_child_close(context, element)
                    )
                    if should_render:
                        if not context.stack:
                            yield from self._render_top_element(
                                console, options, element, new_line and node_type != "inline", _new_line_segment
                            )
                        else:
                            if new_line and node_type != "inline":
                                yield _new_line_segment
                            yield from console.render(element, context.options)

                if exiting or self_closing:
                    element.on_leave(context)
                    new_line = element.new_line
