import io
import os
import shlex
import shutil
import subprocess
import tempfile
from typing import Optional, List, Tuple, Callable, Dict
from rich.console import Console


def has_vim_terminal(vim_bin: str) -> bool:
    """Check if vim binary supports +terminal."""
    try:
        res = subprocess.run([vim_bin, "--version"], capture_output=True, text=True, timeout=2)
        return "+terminal" in res.stdout
    except Exception:
        return False


def detect_best_pager() -> str:
    """
    Detect the default pager engine. Defaults to less for clean document presentation.
    (nvim/vim can be chosen explicitly via --pager=nvim or MDOK_PAGER).
    """
    if shutil.which("less"):
        return "less"
    return "stdout"


def build_less_cmd(
    filename: Optional[str] = None,
    search_query: Optional[str] = None,
    less_bin: Optional[str] = None,
) -> List[str]:
    """Build tuned less pager command."""
    bin_path = less_bin or shutil.which("less") or "less"
    doc_name = os.path.basename(filename) if filename and filename != "-" else "mdok"
    prompt = f"[mdok] {doc_name}?lt Line %lt?L/%L.:?pt %pt\\%..: "

    cmd = [
        bin_path,
        "-R",
        "-i",
        "-j.5",
        "-g",
        "-J",
        "--use-color",
        "-DSkY",
        f"-P{prompt}",
    ]
    if search_query:
        cmd.append(f"+/{search_query}")
    return cmd


def build_editor_cmd(
    editor_type: str,
    temp_file: str,
    filename: Optional[str] = None,
    search_query: Optional[str] = None,
    left_margin: int = 0,
) -> List[str]:
    """Build nvim or vim command to view the rendered document in terminal mode."""
    bin_name = "nvim" if editor_type == "nvim" else "vim"
    bin_path = shutil.which(bin_name) or bin_name
    abs_temp = temp_file if temp_file == "{TEMP_FILE}" else os.path.abspath(temp_file)

    if editor_type == "nvim":
        # In Neovim, :terminal executes its argument in the user's shell ($SHELL).
        # Any ' | ' after :terminal would be passed directly to the shell unless escaped or split!
        # We run settings and mappings first via -c, then launch terminal cat via a separate -c.
        setup_cmds = [
            "silent! set termguicolors clipboard^=unnamed,unnamedplus mouse=a laststatus=0 noruler noshowcmd nonumber norelativenumber signcolumn=no showtabline=0 noswapfile nowrap ignorecase smartcase incsearch hlsearch",
            "silent! set fillchars=vert:\u00a0,eob:\\ ",
            "highlight! clear VertSplit | highlight! link VertSplit Normal",
            "silent! highlight! clear WinSeparator | silent! highlight! link WinSeparator Normal",
        ]
        if left_margin > 1:
            margin_width = left_margin - 1
            setup_cmds.extend([
                "silent! set fillchars+=vert:\\ ",
                "leftabove vnew",
                f"vertical resize {margin_width}",
                "setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth",
                "execute 'nnoremap <buffer> <silent> q :qa!<CR>'",
                "execute 'nnoremap <buffer> <silent> <LeftMouse> <Cmd>wincmd l<CR>'",
                "execute 'nnoremap <buffer> <silent> <C-w>h <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w><Left> <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w>w <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w>W <Nop>'",
                "wincmd l",
            ])

        setup_cmds.extend([
            "nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>",
            "nnoremap <buffer> <silent> Q :qa!<CR>",
            "nnoremap <buffer> <silent> G :call MdokJumpToEnd()<CR>",
            "nnoremap <buffer> <silent> b :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> B :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> u :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> <BS> :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> <C-o> :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> <C-t> :call MdokGoBack()<CR>",
            "nnoremap <buffer> <silent> <Space> <C-f>",
            "nnoremap <buffer> <silent> n nzz",
            "nnoremap <buffer> <silent> N Nzz",
            "nnoremap <buffer> <silent> <C-d> <C-d>zz",
            "nnoremap <buffer> <silent> <C-u> <C-u>zz",
            "tnoremap <buffer> <silent> <Esc> <C-\\><C-n>",
            f"nnoremap <buffer> <silent> L :!less -R -i -j.5 -g -J --use-color -DSkY {abs_temp}<CR>",
        ])
        if filename and filename != "-":
            abs_orig = os.path.abspath(filename)
            setup_cmds.append(f"nnoremap <buffer> <silent> e :edit {abs_orig}<CR>")

        nav_action = f"\\<C-\\>\\<C-n>gg/{search_query}\\<CR>" if search_query else "\\<C-\\>\\<C-n>gg"

        cmd = [
            bin_path,
            "-c", " | ".join(setup_cmds),
            "-c", f"autocmd TermOpen * setlocal nonumber norelativenumber signcolumn=no foldcolumn=0 colorcolumn= | if filereadable('{abs_temp}.vim') | execute 'source ' . fnameescape('{abs_temp}.vim') | endif",
            "-c", f"autocmd TermClose * call feedkeys(\"{nav_action}\", \"n\") | if filereadable('{abs_temp}.vim') | execute 'source ' . fnameescape('{abs_temp}.vim') | endif",
            "-c", f"terminal cat {abs_temp}",
        ]
        if left_margin > 1:
            cmd.extend(["-c", "autocmd WinClosed * qa!"])
    else:
        # Standard Vim with +terminal
        nav_action = f"\\<C-W>Ngg/{search_query}\\<CR>" if search_query else "\\<C-W>Ngg"
        init_cmds = [
            "silent! set termguicolors clipboard^=unnamed,unnamedplus mouse=a laststatus=0 noruler noshowcmd nonumber norelativenumber noswapfile nowrap lazyredraw ignorecase smartcase incsearch hlsearch",
            "silent! set fillchars=vert:\u00a0,eob:\\ ",
            "highlight! clear VertSplit | highlight! link VertSplit Normal",
            "silent! highlight! clear WinSeparator | silent! highlight! link WinSeparator Normal",
        ]
        if left_margin > 1:
            margin_width = left_margin - 1
            init_cmds.extend([
                "leftabove vnew",
                f"vertical resize {margin_width}",
                "setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 colorcolumn= winfixwidth",
                "execute 'nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>'",
                "execute 'nnoremap <buffer> <silent> Q :qa!<CR>'",
                "execute 'nnoremap <buffer> <silent> <LeftMouse> <Cmd>wincmd l<CR>'",
                "execute 'nnoremap <buffer> <silent> <C-w>h <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w><Left> <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w>w <Nop>'",
                "execute 'nnoremap <buffer> <silent> <C-w>W <Nop>'",
                "wincmd l",
            ])

        init_cmds.extend([
            f"let g:tb = term_start(['cat', '{abs_temp}'], {{'curwin': 1, 'term_finish': 'open', 'exit_cb': {{j, s -> timer_start(20, {{-> feedkeys(\"{nav_action}\", \"tx!\")}})}}}})",
            "setlocal nonumber norelativenumber signcolumn=no foldcolumn=0 colorcolumn=",
            f"if filereadable('{abs_temp}.vim') | execute 'source ' . fnameescape('{abs_temp}.vim') | endif",
            "execute 'nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>'",
            "execute 'nnoremap <buffer> <silent> Q :qa!<CR>'",
            "execute 'nnoremap <buffer> <silent> G :call MdokJumpToEnd()<CR>'",
            "execute 'nnoremap <buffer> <silent> b :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> B :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> u :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> <BS> :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> <C-o> :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> <C-t> :call MdokGoBack()<CR>'",
            "execute 'nnoremap <buffer> <silent> <Space> <C-f>'",
            "execute 'nnoremap <buffer> <silent> n nzz'",
            "execute 'nnoremap <buffer> <silent> N Nzz'",
            "execute 'nnoremap <buffer> <silent> <C-d> <C-d>zz'",
            "execute 'nnoremap <buffer> <silent> <C-u> <C-u>zz'",
            "execute 'nnoremap <buffer> <silent> <C-w>h <Nop>'",
            "execute 'nnoremap <buffer> <silent> <C-w><Left> <Nop>'",
            "execute 'nnoremap <buffer> <silent> <C-w>w <Nop>'",
            "execute 'nnoremap <buffer> <silent> <C-w>W <Nop>'",
            f"execute 'nnoremap <buffer> <silent> L :!less -R -i -j.5 -g -J --use-color -DSkY {abs_temp}<CR>'",
        ])
        if left_margin > 1:
            init_cmds.append("execute 'autocmd BufWipeout <buffer> qa!'")
        if filename and filename != "-":
            abs_orig = os.path.abspath(filename)
            init_cmds.append(f"execute 'nnoremap <buffer> <silent> e :edit {abs_orig}<CR>'")

        cmd = [
            bin_path,
            "--cmd", "let g:startify_disable_at_vimenter = 1",
            "-c", " | ".join(init_cmds),
        ]
        if left_margin > 1:
            cmd.extend(["-c", "autocmd WinClosed * qa!"])

    return cmd


def resolve_pager(
    pager_opt: Optional[str] = None,
    pager_cmd: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[str, Optional[List[str]]]:
    """
    Resolve which pager engine to use with graceful degradation.
    Returns (engine, custom_cmd_or_None).
    """
    environ = os.environ if env is None else env

    # 1. Explicit --pager-cmd
    if pager_cmd:
        parts = shlex.split(pager_cmd)
        base = os.path.basename(parts[0]) if parts else ""
        if base in ("nvim", "vim"):
            return base, parts
        return "custom", parts

    # 2. Explicit MDOK_PAGER env var
    mdok_pager = environ.get("MDOK_PAGER")
    if mdok_pager:
        parts = shlex.split(mdok_pager)
        base = os.path.basename(parts[0]) if parts else ""
        if base in ("nvim", "vim", "less"):
            return base, parts
        return "custom", parts

    # 3. Explicit CLI pager choice
    if pager_opt and pager_opt != "auto":
        choice = pager_opt.lower()
        if choice == "nvim":
            if shutil.which("nvim"):
                return "nvim", None
            choice = "vim"
        if choice == "vim":
            vim_bin = shutil.which("vim")
            if vim_bin and has_vim_terminal(vim_bin):
                return "vim", None
            choice = "less"
        if choice == "less":
            if shutil.which("less"):
                return "less", None
            return "stdout", None

    # 4. If standard PAGER is set to something other than less/more, respect it
    sys_pager = environ.get("PAGER")
    if sys_pager:
        parts = shlex.split(sys_pager)
        base = os.path.basename(parts[0]) if parts else ""
        if base not in ("less", "more", ""):
            return "custom", parts

    # 5. Default auto-detection with graceful degradation
    return detect_best_pager(), None


def build_pager_cmd(
    filename: Optional[str] = None,
    search_query: Optional[str] = None,
    pager_cmd: Optional[str] = None,
    pager_opt: Optional[str] = None,
    temp_file: Optional[str] = None,
    left_margin: int = 0,
) -> Tuple[str, List[str], Dict[str, str]]:
    """Build the engine, command list, and environment for launching the pager."""
    env = os.environ.copy()
    engine, custom_cmd = resolve_pager(pager_opt=pager_opt, pager_cmd=pager_cmd, env=env)

    if engine == "custom" and custom_cmd:
        return engine, custom_cmd, env
    elif engine in ("nvim", "vim"):
        cmd = build_editor_cmd(
            editor_type=engine,
            temp_file=temp_file or "{TEMP_FILE}",
            filename=filename,
            search_query=search_query,
            left_margin=left_margin,
        )
        return engine, cmd, env
    elif engine == "less":
        cmd = build_less_cmd(
            filename=filename,
            search_query=search_query,
        )
        return engine, cmd, env
    else:
        return "stdout", [], env


def should_use_pager(
    is_tty: bool,
    force_pager: Optional[bool],
    no_pager: bool,
    line_count: int,
    term_height: int,
) -> bool:
    """Determine whether output should be routed through a pager."""
    if not is_tty:
        return bool(force_pager)
    if no_pager:
        return False
    if force_pager:
        return True
    return line_count > (term_height - 2)


def spawn_pager(
    engine: str,
    cmd: List[str],
    env: Dict[str, str],
    write_fn: Callable[[Console], None],
    term_width: int,
    theme=None,
    companion_fn: Optional[Callable[[str], None]] = None,
) -> int:
    """Launch the pager engine (nvim, vim, less, custom, or direct stdout)."""
    if engine == "stdout" or not cmd:
        fallback_console = Console(theme=theme, width=term_width)
        write_fn(fallback_console)
        return 0

    if engine in ("nvim", "vim"):
        tmp = tempfile.NamedTemporaryFile("w", suffix=".ansi", encoding="utf-8", delete=False)
        tmp_path = tmp.name
        tmp.close()
        try:
            buf = io.StringIO()
            tmp_console = Console(file=buf, theme=theme, width=term_width, force_terminal=True)
            write_fn(tmp_console)
            content = buf.getvalue().rstrip() + "\n"
            with open(tmp_path, "w", encoding="utf-8") as f_out:
                f_out.write(content)

            if companion_fn:
                companion_fn(tmp_path)

            full_cmd = [arg.replace("{TEMP_FILE}", tmp_path) for arg in cmd]
            return subprocess.call(full_cmd, env=env)
        except FileNotFoundError:
            fallback_console = Console(theme=theme, width=term_width)
            write_fn(fallback_console)
            return 0
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
                if os.path.exists(f"{tmp_path}.vim"):
                    os.remove(f"{tmp_path}.vim")
            except OSError:
                pass

    try:
        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=env,
        )
    except FileNotFoundError:
        fallback_console = Console(theme=theme, width=term_width)
        write_fn(fallback_console)
        return 0

    try:
        pager_console = Console(
            file=proc.stdin,
            theme=theme,
            width=term_width,
            force_terminal=True,
        )
        write_fn(pager_console)
        if proc.stdin:
            proc.stdin.close()
        return proc.wait()
    except (BrokenPipeError, KeyboardInterrupt):
        try:
            if proc.stdin:
                proc.stdin.close()
            proc.terminate()
        except OSError:
            pass
        return 0
    except Exception:
        if proc.stdin:
            proc.stdin.close()
        proc.wait()
        return 0
