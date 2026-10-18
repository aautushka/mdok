# mdok

A document-grade reader for Markdown and Word (`.docx`) files in the terminal.

Most terminal renderers either stretch text across the entire display width or force it into a rigid, narrow column on the left edge. Tables often fuse rows together, eat technical tags like `<Type>`, or ignore `<br>` line breaks. Word documents (`.docx`) piped through pandoc turn into broken ASCII grids, raw `[tags]{.underline}`, and corrupted multi-column tables.

`mdok` formats Markdown and Word documents like clean, readable documents:

- **Word (`.docx`) Reader**: Native OpenXML parser built with Python's standard library (zero heavy binary dependencies). Cleanly renders contracts, agreements, technical specifications, and resumes:
  - **Tables**: Column width allocation via `<w:tblGrid>`, multi-column cell spans (`<w:gridSpan>`), cell background shading (`<w:shd>`), and header rows (`<w:tblHeader>`).
  - **Borderless Layout Tables**: Intelligently renders side-by-side signature and party metadata blocks without ugly grid lines.
  - **Checkboxes & Form Controls**: Structured document checkboxes (`☑` / `☐`) and Wingdings symbols.
  - **Footnotes & Endnotes**: Clean inline citations with reference sections rendered at the bottom.
  - **Try it**: `mdok examples/showcase.docx` or `mdok examples/showcase.md`.
- **Proportional width & centering**: Centers text on wide displays with gentle margins and scales comfortably (~75% of terminal width up to ~120 columns).
- **Readable tables**: LaTeX *booktabs* style—horizontal rules, no heavy ASCII borders, soft cell wrapping, alignment support, and row dividers so multiline rows don't run together.
- **Tag & line break handling**: Preserves technical tags (like `<Tag>` or `<Property>`) and respects `<br>` breaks inside cells.
- **Muted colors**: Inline code uses a warm amber (`#e0af68`) on a subtle dark badge instead of bright yellow. Code blocks default to the Nord syntax theme.
- **Automatic pager with Vim navigation**: Seamless cursor-based reading in Neovim/Vim with text cursor, or tuned `less` with smart-case search and centered matches.
- **GitHub-style callouts**: Renders `> [!NOTE]`, `> [!TIP]`, `> [!WARNING]`, etc.

---

## Installation

```bash
pip install mdok
```

Or from source:

```bash
git clone https://github.com/anton/mdok.git
cd mdok
pip install .
```

For development:

```bash
pip install -e .
```

---

## Usage

Read a Markdown or Word document:

```bash
mdok README.md
mdok contract.docx
```

Pipe from standard input:

```bash
cat doc.md | mdok
cat agreement.docx | mdok
```

Jump directly to a search match:

```bash
mdok doc.md -s "Installation"
mdok contract.docx -s "Termination"
```

### Options

```bash
mdok doc.md -s "Installation"         # Jump directly to search pattern and highlight
mdok doc.md -w 100                    # Explicit document width in columns
mdok doc.md -m 4                      # Explicit left margin
mdok doc.md --no-center               # Align to left edge
mdok doc.md -b rounded                # Table style (booktabs, rounded, simple, minimal, none)
mdok doc.md --code-theme gruvbox-dark # Syntax highlighting theme
mdok doc.md --nvim                    # Force Neovim viewer (true text cursor, libvterm)
mdok doc.md --vim                     # Force Vim viewer (+terminal mode with text cursor)
mdok doc.md --less                    # Force tuned less pager
mdok doc.md --no-pager                # Print directly without pager
mdok doc.md --pager-cmd "bat -p"      # Custom pager command (or use $MDOK_PAGER / $PAGER)
```

### Viewer Engine & Graceful Degradation

`mdok` automatically selects the best available viewer engine for your system:

1. **Neovim (`nvim`)**: If installed, launches in Neovim terminal mode with full 24-bit truecolor fidelity and a **real text cursor** that moves through the document.
2. **Vim (`vim`)**: If `nvim` is absent, detects if Vim is installed with `+terminal` support.
3. **Tuned `less`**: If neither is installed, gracefully degrades to `less` with smart-case search, vertical centering (`-j.5`), left gutter hit marks (`-J`), and vivid highlights (`-DSkY`).
4. **Standard Output**: If no pager binary is found, prints directly to stdout with zero errors.

### Navigation & Search

When viewing documents in `mdok`'s cursor viewer:

| Key | Action |
| --- | --- |
| `h` / `j` / `k` / `l` or Arrows | Move cursor left / down / up / right |
| `w` / `e` / `b` | Hop forward / end of word / backward word-by-word |
| `0` / `$` | Jump to beginning / end of line |
| `Space` or `Ctrl-F` / `Ctrl-B` | Full page down / up |
| `Ctrl-D` / `Ctrl-U` | Half-page down / up (with auto-centering) |
| `gg` / `G` | Jump to top / bottom of document |
| `/pattern` / `?pattern` | Search forward / backward (incremental, case-smart) |
| `n` / `N` | Next / previous match (auto-centered in screen) |
| `v` / `V` then `y` | Visual select and yank text directly to system clipboard |
| `yy` | Yank current line directly to system clipboard |
| `yw` / `yip` | Yank word / paragraph to system clipboard |
| Mouse drag + `y` | Select with mouse and yank to system clipboard |
| `i` / `I` | Open source document file for editing |
| `q` | Exit |
