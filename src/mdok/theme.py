from dataclasses import dataclass
from typing import Dict
from rich import box
from rich.box import Box
from rich.theme import Theme

# Clean Booktabs Box: top rule, header separator, bottom rule, no vertical bars.
BOOKTABS = box.HORIZONTALS

BOX_STYLES: Dict[str, Box] = {
    "booktabs": box.HORIZONTALS,
    "simple": box.SIMPLE,
    "simple_head": box.SIMPLE_HEAD,
    "minimal": box.MINIMAL,
    "rounded": box.ROUNDED,
    "none": box.ASCII,
}

# Subtle, elegant document theme (not neon/flashy)
DEFAULT_THEME = Theme({
    "markdown.h1": "bold bright_white underline",
    "markdown.h1.border": "dim cyan",
    "markdown.h2": "bold cyan",
    "markdown.h3": "bold white",
    "markdown.h4": "bold dim white",
    "markdown.h5": "italic dim white",
    "markdown.h6": "dim white",
    "markdown.hr": "dim bright_black",
    "markdown.item.bullet": "cyan",
    "markdown.item.number": "dim cyan",
    "markdown.block_quote": "dim italic white",
    "markdown.block_quote.border": "dim cyan",
    "markdown.link": "underline cyan",
    "markdown.link_url": "dim underline bright_blue",
    "markdown.link.bracket": "dim #6272a4",
    "markdown.link.file": "bold bright_cyan",
    "markdown.link.file.missing": "bold red",
    "markdown.link.anchor": "italic cyan",
    "markdown.link.external": "underline bright_blue",
    "markdown.table.border": "dim bright_black",
    "markdown.table.header": "bold white",
    "markdown.code": "#e0af68 on grey15",
    "markdown.code_block": "none",
})
