# mdok

A small CLI tool for reading Markdown files in the terminal.

Most terminal renderers either stretch text across the entire display width or force it into a rigid, narrow column on the left edge. Tables often fuse rows together, eat technical tags like `<Type>`, or ignore `<br>` line breaks.

`mdok` formats Markdown like a clean document:

- **Proportional width & centering**: Centers text on wide displays with gentle margins and scales comfortably (~75% of terminal width up to ~120 columns).
- **Readable tables**: LaTeX *booktabs* style—horizontal rules, no heavy ASCII borders, soft cell wrapping, alignment support, and row dividers so multiline rows don't run together.
- **Tag & line break handling**: Preserves technical tags (like `<Tag>` or `<Property>`) and respects `<br>` breaks inside cells.
- **Muted colors**: Inline code uses a warm amber (`#e0af68`) on a subtle dark badge instead of bright yellow. Code blocks default to the Nord syntax theme.
- **Automatic pager**: Pipes into `less` (with colors preserved) when the document is longer than your terminal screen.
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

### Options

```bash
mdok doc.md -w 100                    # Explicit document width in columns
mdok doc.md -m 4                      # Explicit left margin
mdok doc.md --no-center               # Align to left edge
mdok doc.md -b rounded                # Table style (booktabs, rounded, simple, minimal, none)
mdok doc.md --code-theme gruvbox-dark # Syntax highlighting theme
mdok doc.md --no-pager                # Print directly without pager
```
