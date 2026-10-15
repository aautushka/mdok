# Architecture & Design Overview

Markdown readers in the terminal often suffer from two extremes: either stretching across an ultra-wide display into an unreadable wall of text, or hard-clamping to a rigid 80-character column pinned awkwardly to the left margin.

`mda` solves this by introducing a **responsive document canvas** that floats in the center of the terminal, maintaining optimal typographic line lengths (75–90 characters) while adapting gracefully on narrower screens.

---

## Performance & Feature Comparison

Here is how different terminal markdown engines handle document formatting and table layouts:

| Engine | Responsive Margins | Table Alignment | Border Style | Memory Footprint |
| :--- | :---: | :---: | :--- | ---: |
| **Glow** | ✖ Pinned Left | Basic | Heavy Lipgloss Grid | ~45 MB |
| **mdcat** | ✖ Full Terminal | None | ASCII Wireframe | ~12 MB |
| **mdv** | ✖ Broken Wrapping | None | Primitive 80s Grid | ~28 MB |
| **mda (Rich)** | ✔ Centered Page | Full (:---:) | Clean Booktabs | ~18 MB |

> [!NOTE]
> All column dimensions are computed proportionally based on cell contents and terminal budget, with automatic soft-wrapping for descriptive text.

---

## Code Example

Syntax highlighting uses Pygments themes with language tags:

```python
from mda.canvas import calculate_dimensions

def preview_canvas(term_width: int = 140):
    doc_width, left_margin = calculate_dimensions(term_width)
    print(f"Reading width: {doc_width} cols | Left margin: {left_margin} cols")
```

> [!TIP]
> You can change the table border style on the fly using `--box rounded` or `--box minimal`.
