import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import pytest


@pytest.mark.skipif(not shutil.which("nvim"), reason="nvim not installed")
def test_nvim_tab_and_buffer_cleanliness():
    """Verify that editing, repeated saves, reloads, and tab switching in Neovim never leak extra tabs or listed buffers."""
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    dump_path = os.path.join(tmpdir, "dump.txt")
    script_file = os.path.join(tmpdir, "test.vim")

    with open(src_md, "w") as f:
        f.write("# Clean Tab Test\n\nInitial body.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "--no-center", "-w", "80"
    ], check=True)

    buftabline_plugin = os.path.expanduser("~/.vim/bundle/vim-buftabline/plugin/buftabline.vim")
    buftabline_src = f"source {buftabline_plugin}" if os.path.exists(buftabline_plugin) else ""

    test_harness = f"""
set nocompatible
set hidden
{buftabline_src}

execute 'terminal cat {ansi_path}'
sleep 300m
call feedkeys("\\<C-\\>\\<C-n>", "nx!")
source {ansi_path}.vim
sleep 200m

let s:log = []
function! s:fmt_bufs()
  let l:res = []
  for b in getbufinfo({{'buflisted': 1}})
    call add(l:res, b.bufnr . ':' . fnamemodify(b.name, ':t'))
  endfor
  return join(l:res, ', ')
endfunction

call add(s:log, 'initial: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 1. Press e to open edit tab
call MdokEditSource()
sleep 300m
call add(s:log, 'after_e1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 2. Pressing e again when already open must not duplicate tab
call MdokEditSource()
sleep 200m
call add(s:log, 'after_e2_same: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 3. Write 1
write
sleep 300m
call add(s:log, 'after_write1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 4. Switch to viewer tab (triggers reload)
tabprevious
sleep 500m
call add(s:log, 'after_tabprev1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 5. Switch back to edit tab
tabnext
sleep 300m

" 6. Write 2
write
sleep 300m
call add(s:log, 'after_write2: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 7. Switch to viewer tab (triggers 2nd reload)
tabprevious
sleep 500m
call add(s:log, 'after_tabprev2: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 8. Close edit tab using bdelete (closing buffer must close tab, not leave [no file])
tabnext
bdelete
sleep 500m
call add(s:log, 'after_bdelete: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

call writefile(s:log, '{dump_path}')
qa!
"""
    with open(script_file, "w") as sf:
        sf.write(test_harness)

    nvim_bin = shutil.which("nvim") or "nvim"
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        cmd = [nvim_bin, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(nvim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 8:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            assert os.path.exists(dump_path), "dump file not written"
            with open(dump_path) as df:
                lines = [l.rstrip("\n") for l in df.readlines()]
            log_dict = dict(l.split(": ", 1) for l in lines)
            assert log_dict.get("initial") == "tabs=1 bufs=[]", f"Unexpected initial state: {log_dict.get('initial')}"
            assert "tabs=2" in log_dict.get("after_e1", "")
            assert "doc.md" in log_dict.get("after_e1", "")
            assert log_dict.get("after_e2_same") == log_dict.get("after_e1"), "Duplicate tab created"
            assert "tabs=2" in log_dict.get("after_tabprev1", "")
            assert "doc.ansi" not in log_dict.get("after_tabprev1", ""), "ANSI terminal leaked into listed buffers"
            assert "tabs=2" in log_dict.get("after_tabprev2", "")
            assert "doc.ansi" not in log_dict.get("after_tabprev2", ""), "ANSI terminal leaked on second reload"
            assert log_dict.get("after_bdelete") == "tabs=1 bufs=[]", f"Unexpected after bdelete: {log_dict.get('after_bdelete')}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_tab_and_buffer_cleanliness():
    """Verify that editing, repeated saves, reloads, and tab switching in Vim never leak extra tabs or listed buffers."""
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    dump_path = os.path.join(tmpdir, "dump.txt")
    script_file = os.path.join(tmpdir, "test.vim")

    with open(src_md, "w") as f:
        f.write("# Clean Vim Tab Test\n\nInitial body.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "--no-center", "-w", "80"
    ], check=True)

    test_harness = f"""
set nocompatible
set hidden

let g:tb = term_start(['cat', '{ansi_path}'], {{'curwin': 1, 'term_finish': 'open'}})
sleep 300m
call feedkeys("\\<C-W>N", "tx!")
source {ansi_path}.vim
sleep 200m

let s:log = []
function! s:fmt_bufs()
  let l:res = []
  for b in getbufinfo({{'buflisted': 1}})
    call add(l:res, b.bufnr . ':' . fnamemodify(b.name, ':t'))
  endfor
  return join(l:res, ', ')
endfunction

call add(s:log, 'initial: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 1. Press e
call MdokEditSource()
sleep 300m
call add(s:log, 'after_e1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 2. Pressing e again when already open must not duplicate tab
call MdokEditSource()
sleep 200m
call add(s:log, 'after_e2_same: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 3. Write 1
write
sleep 300m
call add(s:log, 'after_write1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 4. Switch to viewer tab (triggers reload)
tabprevious
sleep 500m
call add(s:log, 'after_tabprev1: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 5. Switch back to edit tab
tabnext
sleep 300m

" 6. Write 2
write
sleep 300m
call add(s:log, 'after_write2: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 7. Switch to viewer tab (triggers 2nd reload)
tabprevious
sleep 500m
call add(s:log, 'after_tabprev2: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

" 8. Close edit tab using bdelete
tabnext
bdelete
sleep 500m
call add(s:log, 'after_bdelete: tabs=' . tabpagenr('$') . ' bufs=[' . s:fmt_bufs() . ']')

call writefile(s:log, '{dump_path}')
qa!
"""
    with open(script_file, "w") as sf:
        sf.write(test_harness)

    vim_bin = shutil.which("vim") or "vim"
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        cmd = [vim_bin, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(vim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 8:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            assert os.path.exists(dump_path), "dump file not written"
            with open(dump_path) as df:
                lines = [l.rstrip("\n") for l in df.readlines()]
            log_dict = dict(l.split(": ", 1) for l in lines)
            assert log_dict.get("initial") == "tabs=1 bufs=[]", f"Unexpected initial state: {log_dict.get('initial')}"
            assert "tabs=2" in log_dict.get("after_e1", "")
            assert "doc.md" in log_dict.get("after_e1", "")
            assert log_dict.get("after_e2_same") == log_dict.get("after_e1"), "Duplicate tab created"
            assert "tabs=2" in log_dict.get("after_tabprev1", "")
            assert "doc.ansi" not in log_dict.get("after_tabprev1", ""), "ANSI terminal leaked into listed buffers"
            assert "tabs=2" in log_dict.get("after_tabprev2", "")
            assert "doc.ansi" not in log_dict.get("after_tabprev2", ""), "ANSI terminal leaked on second reload"
            assert log_dict.get("after_bdelete") == "tabs=1 bufs=[]", f"Unexpected after bdelete: {log_dict.get('after_bdelete')}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.skipif(not shutil.which("nvim"), reason="nvim not installed")
def test_nvim_centered_gutter_preserved_after_edit():
    """Verify that in centered mode, editing and closing raw markdown preserves the left margin gutter."""
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    dump_path = os.path.join(tmpdir, "dump.txt")
    script_file = os.path.join(tmpdir, "test.vim")

    with open(src_md, "w") as f:
        f.write("# Centered Doc\n\nCentered test content.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "-w", "60"
    ], check=True)

    test_harness = f"""
set nocompatible
set hidden

leftabove vnew
vertical resize 12
setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth
let b:mdok_margin = 1
let w:mdok_margin = 1
let g:mdok_margin_width = 12
silent! noautocmd file mdok://margin
wincmd l

let b:mdok_viewer = 1
let w:mdok_viewer = 1
execute 'terminal cat {ansi_path}'
sleep 300m
call feedkeys("\\<C-\\>\\<C-n>", "nx!")
source {ansi_path}.vim
sleep 200m

let s:log = []
function! s:record_state(tag)
  let l:wins = winnr('$')
  let l:tabs = tabpagenr('$')
  let l:margin_ok = (getbufvar(winbufnr(1), 'mdok_margin', 0) == 1) ? 1 : 0
  call add(s:log, a:tag . ': tabs=' . l:tabs . ' wins=' . l:wins . ' margin=' . l:margin_ok)
endfunction

call s:record_state('initial')

" 1. Press e to open edit tab
call MdokEditSource()
sleep 300m
call s:record_state('after_e')

" 2. Save
write
sleep 300m
call s:record_state('after_write')

" 3. Switch back to viewer tab to trigger reload
tabprevious
sleep 500m
call s:record_state('after_tabprev')

" 4. Switch back to edit tab and close via bdelete
tabnext
bdelete
sleep 500m
call s:record_state('after_bdelete')

call writefile(s:log, '{dump_path}')
qa!
"""
    with open(script_file, "w") as sf:
        sf.write(test_harness)

    nvim_bin = shutil.which("nvim") or "nvim"
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        cmd = [nvim_bin, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(nvim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 8:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            assert os.path.exists(dump_path), "dump file not written"
            with open(dump_path) as df:
                lines = [l.rstrip("\n") for l in df.readlines()]
            log_dict = dict(l.split(": ", 1) for l in lines)
            assert log_dict.get("initial") == "tabs=1 wins=2 margin=1", f"Unexpected initial state: {log_dict.get('initial')}"
            assert log_dict.get("after_e") == "tabs=2 wins=1 margin=0", f"Unexpected edit state: {log_dict.get('after_e')}"
            assert log_dict.get("after_tabprev") == "tabs=2 wins=2 margin=1", f"Unexpected tabprev state: {log_dict.get('after_tabprev')}"
            assert log_dict.get("after_bdelete") == "tabs=1 wins=2 margin=1", f"Margin gutter was lost after edit close: {log_dict.get('after_bdelete')}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_centered_gutter_preserved_after_edit():
    """Verify that in centered mode in Vim, editing and closing raw markdown preserves the left margin gutter."""
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    dump_path = os.path.join(tmpdir, "dump.txt")
    script_file = os.path.join(tmpdir, "test.vim")

    with open(src_md, "w") as f:
        f.write("# Centered Vim Doc\n\nCentered test content.\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "-w", "60"
    ], check=True)

    test_harness = f"""
set nocompatible
set hidden

leftabove vnew
vertical resize 12
setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth
let b:mdok_margin = 1
let w:mdok_margin = 1
let g:mdok_margin_width = 12
silent! noautocmd file mdok://margin
wincmd l

let g:tb = term_start(['cat', '{ansi_path}'], {{'curwin': 1, 'term_finish': 'open'}})
let b:mdok_viewer = 1
let w:mdok_viewer = 1
sleep 300m
call feedkeys("\\<C-W>N", "tx!")
source {ansi_path}.vim
sleep 200m

let s:log = []
function! s:record_state(tag)
  let l:wins = winnr('$')
  let l:tabs = tabpagenr('$')
  let l:margin_ok = (getbufvar(winbufnr(1), 'mdok_margin', 0) == 1) ? 1 : 0
  call add(s:log, a:tag . ': tabs=' . l:tabs . ' wins=' . l:wins . ' margin=' . l:margin_ok)
endfunction

call s:record_state('initial')

" 1. Press e to open edit tab
call MdokEditSource()
sleep 300m
call s:record_state('after_e')

" 2. Save
write
sleep 300m
call s:record_state('after_write')

" 3. Switch back to viewer tab to trigger reload
tabprevious
sleep 500m
call s:record_state('after_tabprev')

" 4. Switch back to edit tab and close via bdelete
tabnext
bdelete
sleep 500m
call s:record_state('after_bdelete')

call writefile(s:log, '{dump_path}')
qa!
"""
    with open(script_file, "w") as sf:
        sf.write(test_harness)

    vim_bin = shutil.which("vim") or "vim"
    master, slave = pty.openpty()
    p = os.fork()
    if p == 0:
        os.close(master)
        os.setsid()
        os.dup2(slave, 0)
        os.dup2(slave, 1)
        os.dup2(slave, 2)
        os.close(slave)
        os.environ["TERM"] = "xterm-256color"
        cmd = [vim_bin, "--clean", "-u", "NORC", "-S", script_file]
        os.execv(vim_bin, cmd)
    else:
        os.close(slave)
        start = time.time()
        while time.time() - start < 8:
            r, _, _ = select.select([master], [], [], 0.1)
            if r:
                try:
                    data = os.read(master, 1024)
                    if not data:
                        break
                except OSError:
                    break
        try:
            os.kill(p, 9)
        except OSError:
            pass
        os.close(master)

        try:
            assert os.path.exists(dump_path), "dump file not written"
            with open(dump_path) as df:
                lines = [l.rstrip("\n") for l in df.readlines()]
            log_dict = dict(l.split(": ", 1) for l in lines)
            assert log_dict.get("initial") == "tabs=1 wins=2 margin=1", f"Unexpected initial state: {log_dict.get('initial')}"
            assert log_dict.get("after_e") == "tabs=2 wins=1 margin=0", f"Unexpected edit state: {log_dict.get('after_e')}"
            assert log_dict.get("after_tabprev") == "tabs=2 wins=2 margin=1", f"Unexpected tabprev state: {log_dict.get('after_tabprev')}"
            assert log_dict.get("after_bdelete") == "tabs=1 wins=2 margin=1", f"Margin gutter was lost after edit close: {log_dict.get('after_bdelete')}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.mark.skipif(not shutil.which("vim"), reason="vim not installed")
def test_vim_gutter_divider_cleanliness():
    """Verify that in Vim centered mode, no visible divider line appears between margin and preview across edit cycles."""
    tmpdir = tempfile.mkdtemp()
    src_md = os.path.join(tmpdir, "doc.md")
    ansi_path = os.path.join(tmpdir, "doc.ansi")
    dump_path = os.path.join(tmpdir, "dump.txt")
    script_file = os.path.join(tmpdir, "test.vim")

    with open(src_md, "w") as f:
        f.write("# Hello\n\nSome text content\n")

    subprocess.run([
        sys.executable, "-m", "mdok.cli",
        "--render-ansi", ansi_path,
        src_md,
        "-w", "40"
    ], check=True)

    test_harness = f"""
set nocompatible
silent! set termguicolors clipboard^=unnamed,unnamedplus mouse=a laststatus=0 noruler noshowcmd nonumber norelativenumber showtabline=1 noswapfile nowrap lazyredraw ignorecase smartcase incsearch hlsearch
silent! set fillchars=vert:\u00a0,eob:\\ 
highlight! clear VertSplit | highlight! link VertSplit Normal
silent! highlight! clear WinSeparator | silent! highlight! link WinSeparator Normal

leftabove vnew
vertical resize 10
setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth
let b:mdok_margin = 1
let w:mdok_margin = 1
let g:mdok_margin_width = 10
silent! noautocmd file mdok://margin
wincmd l

let g:tb = term_start(['cat', '{ansi_path}'], {{'curwin': 1, 'term_finish': 'open'}})
setlocal nonumber norelativenumber signcolumn=no foldcolumn=0 colorcolumn= nobuflisted bufhidden=wipe
let b:mdok_viewer = 1
let w:mdok_viewer = 1
source {ansi_path}.vim
sleep 300m

let s:log = []
function! s:record_split_info(tag)
  let l:vs_hl = execute('highlight VertSplit')
  let l:fc = &fillchars
  call add(s:log, a:tag . ' fillchars=' . string(l:fc) . ' VertSplit=' . string(trim(l:vs_hl)))
endfunction

call s:record_split_info('initial')

call MdokEditSource()
sleep 300m
call s:record_split_info('after_edit_open')

write
sleep 300m

tabprevious
sleep 500m
call s:record_split_info('after_tabprev')

tabnext
bdelete
sleep 500m
call s:record_split_info('after_close_edit')

call writefile(s:log, '{dump_path}')
qa!
"""
    with open(script_file, "w") as sf:
        sf.write(test_harness)

    vim_bin = shutil.which("vim")
    subprocess.run([vim_bin, "-S", script_file], check=True, timeout=10)
    try:
        assert os.path.exists(dump_path), "dump file not written"
        with open(dump_path) as df:
            lines = [l.rstrip("\n") for l in df.readlines()]
        log_dict = dict(l.split(" ", 1) for l in lines)
        for state in ["initial", "after_tabprev", "after_close_edit"]:
            info = log_dict.get(state, "")
            assert "links to Normal" in info, f"VertSplit not linked to Normal in {state}: {info}"
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


