# mdok

A small CLI tool for reading Markdown files in the terminal.

Most terminal renderers either stretch text across the entire display width or force it into a rigid, narrow column on the left edge. Tables often fuse rows together, eat technical tags like `<Type>`, or ignore `<br>` line breaks.

`mdok` formats Markdown like a clean document:

- **Proportional width & centering**: Centers text on wide displays with gentle margins and scales comfortably (~75% of terminal width up to ~120 columns).
- **Readable tables**: LaTeX *booktabs* style—horizontal rules, no heavy ASCII borders, soft cell wrapping, alignment support, and row dividers so multiline rows don't run together.
- **Tag & line break handling**: Preserves technical tags (like `<Tag>` or `<Property>`) and respects `<br>` breaks inside cells.
- **Muted colors**: Inline code uses a warm amber (`#e0af68`) on a subtle dark badge instead of bright yellow. Code blocks default to the Nord syntax theme.
- **Automatic pager with Vim navigation**: Pipes into a tuned `less` instance preserving raw ANSI colors (`-R`), smart-case search (`-i`), centered search hits (`-j.5`), and a status line showing document name, position, and search tips.
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

Read a file:

```bash
mdok README.md
```

Pipe from standard input:

```bash
cat doc.md | mdok
```

Jump directly to a search match:

```bash
mdok doc.md -s "Installation"
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
| `w` / `b` | Hop forward / backward word-by-word |
| `0` / `$` | Jump to beginning / end of line |
| `d` / `u` or `Ctrl-D` / `Ctrl-U` | Half-page down / up |
| `g` / `G` | Jump to top / bottom of document |
| `/pattern` / `?pattern` | Search forward / backward |
| `n` / `N` | Next / previous match (cursor lands directly on the match) |
| `e` | Open source markdown file for editing |
| `q` | Exit |
