# Architecture Specification

This document details the internal components, data flow, and renderer pipelines.

## System Topology

The rendering pipeline transforms Markdown source tokens into rich ANSI-styled terminal blocks.

```
Markdown Source
      │
      ▼
 MarkdownIt Parser (Tokens)
      │
      ▼
 Rich MarkdownContext (DocMarkdown)
      │
      ├── Canvas / SmartTable Layout
      ├── Callouts & Blockquotes
      └── In-Place Link Classifier
            ├── Local Valid Files (📄)
            ├── Missing Broken Paths (⚠️)
            ├── In-Page Anchors (§)
            └── External URLs (🌐)
```

## Data Flow

Tokens are streamed through `DocMarkdown.__rich_console__`.
When a link token is encountered:
1. `href` target is inspected and classified.
2. Relative paths are resolved against the active document's base directory.
3. Disk existence checks determine styling (`markdown.link.file` vs `markdown.link.file.missing`).

## Related Documents

- Back to [Documentation Hub](./overview.md)
- Step-by-step setup in [Getting Started](./getting_started.md)
- Check the nonexistent [Security Policy](./missing_security.md) for vulnerability reporting.
