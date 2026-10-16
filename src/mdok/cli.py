import argparse
import sys
import os
import shutil
from typing import Optional, List
from rich.console import Console
from rich.theme import Theme

from mdok import __version__
from mdok.theme import DEFAULT_THEME, BOX_STYLES
from mdok.canvas import CanvasConfig, calculate_dimensions, DocumentCanvas
from mdok.renderer import DocMarkdown
from mdok.pager import build_pager_cmd, should_use_pager, spawn_pager



def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="mdok",
        description="Document-grade Markdown Reader for the terminal.",
    )
    parser.add_argument(
        "file",
        nargs="?",
        default="-",
        help="Markdown file to read, or '-' for standard input (default: '-')",
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


def read_content(file_arg: str) -> str:
    if file_arg == "-":
        if sys.stdin.isatty():
            # Nothing piped and stdin is a tty
            return ""
        return sys.stdin.read()
    
    path = os.path.expanduser(file_arg)
    if not os.path.exists(path):
        sys.stderr.write(f"Error: file not found: {file_arg}\n")
        sys.exit(1)
    
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    content = read_content(args.file)
    if not content:
        if args.file == "-":
            sys.stderr.write("mdok: no input provided via stdin or file. Use 'mdok --help' for usage.\n")
            return 1
        return 0

    # Determine terminal dimensions
    is_tty = sys.stdout.isatty()
    term_width, term_height = shutil.get_terminal_size(fallback=(100, 24))

    # Canvas layout calculations
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

    # Build document
    markdown_doc = DocMarkdown(
        content,
        code_theme=args.code_theme,
        box_style=args.box,
        show_lines=not args.no_lines,
        doc_width=doc_width,
        left_margin=left_margin,
        term_width=term_width,
    )

    canvas = DocumentCanvas(
        renderable=markdown_doc,
        doc_width=doc_width,
        left_margin=left_margin,
    )

    console = Console(theme=DEFAULT_THEME, width=term_width)

    # Determine whether to page
    force_pager = True if (args.pager is not None or args.search) else None
    if not is_tty or args.no_pager or force_pager:
        line_count = 0
    else:
        # Fast line count estimate: source lines * wrapping factor, or measure lines
        raw_lines = content.count("\n") + 1
        if raw_lines > (term_height - 2):
            line_count = raw_lines
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
        )
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
