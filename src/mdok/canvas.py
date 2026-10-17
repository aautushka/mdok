import shutil
from dataclasses import dataclass
from typing import Optional, Tuple, List
from rich.console import Console, ConsoleOptions, RenderResult, RenderableType
from rich.segment import Segment
from rich.measure import Measurement


@dataclass
class CanvasConfig:
    """Configuration for document canvas layout."""
    max_width: Optional[int] = None
    min_width: int = 70
    cap_width: int = 124
    ratio: float = 0.74
    margin: Optional[int] = None
    center: bool = True


def calculate_dimensions(
    terminal_width: int,
    config: Optional[CanvasConfig] = None,
) -> Tuple[int, int]:
    """
    Calculate (doc_width, left_margin) based on terminal width and config.

    Rules:
    - Narrow screens (<= 82): maximize width with minimal 2-char gutter.
    - Medium screens (83-105): generous 80-85% width.
    - Wide screens (> 105): proportional document sheet (~74% width) up to cap_width (default 124),
      avoiding both full-screen blowout and artificial narrow text walls.
    """
    cfg = config or CanvasConfig()

    if cfg.max_width is not None:
        doc_w = min(cfg.max_width, terminal_width)
    else:
        if terminal_width <= 82:
            doc_w = max(30, terminal_width - 4)
        elif terminal_width <= 105:
            doc_w = min(terminal_width - 6, max(76, int(terminal_width * 0.84)))
        else:
            proportional = int(terminal_width * cfg.ratio)
            doc_w = min(cfg.cap_width, max(88, proportional))
            doc_w = min(doc_w, terminal_width - 12)

    doc_w = max(20, min(doc_w, terminal_width))

    if cfg.margin is not None:
        left_margin = max(0, min(cfg.margin, terminal_width - doc_w))
    elif cfg.center:
        left_margin = max(0, (terminal_width - doc_w) // 2)
    else:
        left_margin = 0

    return doc_w, left_margin


def rstrip_segments(line: List[Segment]) -> List[Segment]:
    """Trim unstyled trailing whitespace from a rendered line to avoid phantom spaces in editors and pagers."""
    if not line:
        return []
    res = list(line)
    while res:
        last = res[-1]
        # Preserve visual padding in colored boxes (panels, shaded cells)
        if last.style and last.style.bgcolor is not None:
            break
        text = last.text.rstrip(" ")
        if not text:
            res.pop()
        else:
            if text != last.text:
                res[-1] = Segment(text, last.style, last.control)
            break
    return res


class DocumentCanvas:
    """
    Renders a renderable constrained to `doc_width` and indented by `left_margin`.
    This provides a centered 'sheet of paper' reading experience.
    """

    def __init__(
        self,
        renderable: RenderableType,
        doc_width: int,
        left_margin: int,
    ) -> None:
        self.renderable = renderable
        self.doc_width = doc_width
        self.left_margin = left_margin

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        if getattr(self.renderable, "has_canvas_layout", False):
            # Renderable manages its own margins and widths (including table breakout)
            yield from console.render(self.renderable, options)
            return

        # Constrain the inner document to doc_width
        doc_options = options.update_width(self.doc_width)
        lines = console.render_lines(self.renderable, doc_options, pad=False)

        margin_prefix = " " * self.left_margin if self.left_margin > 0 else ""
        margin_segment = Segment(margin_prefix) if margin_prefix else None

        for line in lines:
            stripped = rstrip_segments(line)
            if margin_segment and stripped:
                yield margin_segment
                for segment in stripped:
                    yield segment
                yield Segment.line()
            elif not stripped:
                # Clean blank line with zero trailing spaces
                yield Segment.line()
            else:
                for segment in stripped:
                    yield segment
                yield Segment.line()
