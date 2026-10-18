import argparse
import io
import sys
import os
import shutil
import zipfile
from typing import Optional, List, Tuple, Union
from rich.console import Console
from rich.theme import Theme

from mdok import __version__
from mdok.theme import DEFAULT_THEME, BOX_STYLES
from mdok.canvas import CanvasConfig, calculate_dimensions, DocumentCanvas
from mdok.renderer import DocMarkdown
from mdok.docx import DocxDocument
from mdok.pager import build_pager_cmd, should_use_pager, spawn_pager



def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mdok",
        description="Document-grade Markdown & Word (.docx) Reader for the terminal.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Markdown or Word (.docx) file to read, or '-' for standard input (default: '-')",
    )
    parser.add_argument(
        "-w",
        "--width",
        type=int,
        default=None,
        help="Max document reading width (default: auto ~88 chars on wide displays)",
    )
    parser.add_argument(
        "-m",
        "--margin",
        type=int,
        default=None,
        help="Explicit left margin in columns (default: auto-centered)",
    )
    parser.add_argument(
        "--no-center",
        action="store_true",
        help="Disable centering and align to left edge",
    )
    parser.add_argument(
        "-b",
        "--box",
        choices=list(BOX_STYLES.keys()),
        default="booktabs",
        help="Table box style: booktabs (default), minimal, rounded, simple, simple_head, none",
    )
    parser.add_argument(
        "--no-lines",
        action="store_true",
        help="Hide horizontal row divider lines in tables",
    )
    parser.add_argument(
        "--code-theme",
        default="nord",
        help="Pygments code syntax highlighting theme (default: nord)",
    )
    parser.add_argument(
        "-s",
        "--search",
        type=str,
        default=None,
        help="Initial search pattern to jump to and highlight (Vim style)",
    )
    parser.add_argument(
        "-p",
        "--pager",
        nargs="?",
        const="auto",
        choices=["auto", "nvim", "vim", "less"],
        default=None,
        help="Pager engine: auto (best cursor engine: nvim -> vim -> less), nvim, vim, or less",
    )
    parser.add_argument(
        "--nvim",
        action="store_const",
        dest="pager",
        const="nvim",
        help="Force Neovim pager (terminal buffer with text cursor, q to quit)",
    )
    parser.add_argument(
        "--vim",
        action="store_const",
        dest="pager",
        const="vim",
        help="Force Vim pager (+terminal mode with text cursor, q to quit)",
    )
    parser.add_argument(
        "--less",
        action="store_const",
        dest="pager",
        const="less",
        help="Force tuned less pager (smart-case search, yellow highlights)",
    )
    parser.add_argument(
        "--no-pager",
        action="store_true",
        help="Disable pager and print directly to terminal",
    )
    parser.add_argument(
        "--pager-cmd",
        type=str,
        default=None,
        help="Custom pager command (default: auto-configured engine)",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser.parse_args(args)


def is_docx_source(file_arg: str, raw_bytes: Optional[bytes] = None) -> bool:
    """Checks whether the input represents a Word (.docx) document."""
    if file_arg != "-" and file_arg.lower().endswith(".docx"):
        return True
    if raw_bytes and raw_bytes.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw_bytes), "r") as z:
                return "word/document.xml" in z.namelist()
        except Exception:
            return False
    if file_arg != "-":
        path = os.path.expanduser(file_arg)
        if os.path.exists(path) and os.path.isfile(path):
            try:
                with open(path, "rb") as f:
                    header = f.read(4)
                if header == b"PK\x03\x04":
                    with zipfile.ZipFile(path, "r") as z:
                        return "word/document.xml" in z.namelist()
            except Exception:
                return False
    return False


def read_content(file_arg: str) -> str:
    """Read textual content for backward-compatibility."""
    text, _ = read_input(file_arg)
    return text or ""


def read_input(file_arg: str) -> Tuple[Optional[str], Optional[Union[str, bytes]]]:
    """
    Reads input from standard input or file.
    Returns (markdown_text, docx_source). Exactly one will be non-None if input exists.
    """
    if file_arg == "-":
        if sys.stdin.isatty():
            return None, None
        try:
            raw_bytes = sys.stdin.buffer.read()
        except AttributeError:
            raw_bytes = sys.stdin.read().encode("utf-8")
        if not raw_bytes:
            return None, None
        if is_docx_source("-", raw_bytes):
            return None, raw_bytes
        return raw_bytes.decode("utf-8", errors="replace"), None

    path = os.path.expanduser(file_arg)
    if not os.path.exists(path):
        sys.stderr.write(f"Error: file not found: {file_arg}\n")
        sys.exit(1)

    if is_docx_source(path):
        return None, path

    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read(), None


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    content_text, docx_source = read_input(args.file)
    if content_text is None and docx_source is None:
        if args.file == "-":
            sys.stderr.write("mdok: no input provided via stdin or file. Use 'mdok --help' for usage.\n")
            return 1
        return 0

    # Determine terminal dimensions
    is_tty = sys.stdout.isatty()
    term_width, term_height = shutil.get_terminal_size(fallback=(100, 24))

    # Build document
    if docx_source is not None:
        # Word (.docx) is a pre-formatted document encoding exact page geometry,
        # margins, styles, tables, and typography. Disregard -w / args.width and
        # deduce the natural document layout width automatically.
        document_renderable = DocxDocument(
            docx_source,
            box_style=args.box,
            show_lines=not args.no_lines,
            term_width=term_width,
        )
        doc_width = document_renderable.doc_width

        if args.margin is not None:
            left_margin = max(0, min(args.margin, term_width - doc_width))
        elif args.no_center or (not is_tty and args.margin is None):
            left_margin = 0
        else:
            left_margin = max(0, (term_width - doc_width) // 2)
    else:
        # Markdown canvas layout calculations
        config = CanvasConfig(
            max_width=args.width,
            margin=args.margin,
            center=not args.no_center if is_tty else False,
        )
        doc_width, left_margin = calculate_dimensions(term_width, config)

        # If piped to another process (not a tty) and user didn't specify width/margin,
        # don't pad with left margin
        if not is_tty and args.margin is None and not args.no_center:
            left_margin = 0

        document_renderable = DocMarkdown(
            content_text,
            code_theme=args.code_theme,
            box_style=args.box,
            show_lines=not args.no_lines,
            doc_width=doc_width,
            left_margin=left_margin,
            term_width=term_width,
        )

    canvas = DocumentCanvas(
        renderable=document_renderable,
        doc_width=doc_width,
        left_margin=left_margin,
    )

    console = Console(theme=DEFAULT_THEME, width=term_width)

    # Determine whether to page
    force_pager = True if (args.pager is not None or args.search) else None
    if not is_tty or args.no_pager or force_pager:
        line_count = 0
    else:
        if content_text is not None:
            raw_lines = content_text.count("\n") + 1
            if raw_lines > (term_height - 2):
                line_count = raw_lines
            else:
                line_count = sum(1 for _ in console.render_lines(canvas, console.options))
        else:
            line_count = sum(1 for _ in console.render_lines(canvas, console.options))

    use_pager = should_use_pager(
        is_tty=is_tty,
        force_pager=force_pager,
        no_pager=args.no_pager,
        line_count=line_count,
        term_height=term_height,
    )

    if use_pager:
        engine, cmd, env = build_pager_cmd(
            filename=args.file,
            search_query=args.search,
            pager_cmd=args.pager_cmd,
            pager_opt=args.pager,
            left_margin=left_margin,
        )
        if engine in ("nvim", "vim") and left_margin > 0:
            if hasattr(document_renderable, "left_margin"):
                document_renderable.left_margin = 0
            if hasattr(document_renderable, "term_width"):
                document_renderable.term_width = max(doc_width, term_width - left_margin)
            canvas.left_margin = 0

        return spawn_pager(
            engine=engine,
            cmd=cmd,
            env=env,
            write_fn=lambda p_console: p_console.print(canvas),
            term_width=term_width,
            theme=DEFAULT_THEME,
        )
    else:
        console.print(canvas)
        return 0


if __name__ == "__main__":
    sys.exit(main())
