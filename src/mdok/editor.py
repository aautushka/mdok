import json
import os
import re
import sys
from typing import List, Dict, Any, Optional, Tuple

# Pattern matching ANSI escape sequences and OSC 8 hyperlinks
ANSI_ESCAPE_RE = re.compile(
    r"\x1b\[[0-9;]*[a-zA-Z]|\x1b\]8;;[^\x1b]*\x1b\\|\x1b\]8;;\x1b\\"
)

# Pattern matching mdok link format in plain text: [icon text]
MDOK_LINK_RE = re.compile(r"\[([📄⚠️§🌐]\ufe0f?)\s*([^\]]+)\]")


def strip_ansi(text: str) -> str:
    """Strip ANSI escape sequences from rendered text."""
    return ANSI_ESCAPE_RE.sub("", text)


def build_link_manifest(
    ansi_content: str, links: List[Dict[str, Any]]
) -> Tuple[Dict[int, List[Dict[str, Any]]], Dict[str, Dict[str, Any]]]:
    """
    Parse rendered ANSI content line-by-line to map line numbers and column ranges
    to the corresponding link metadata.
    """
    links_by_line: Dict[int, List[Dict[str, Any]]] = {}
    links_by_text: Dict[str, Dict[str, Any]] = {}

    # Build initial text-based index from parser links
    for link in links:
        txt = link.get("text", "").strip().lstrip("\ufe0f").strip()
        if txt and txt not in links_by_text:
            links_by_text[txt] = link

    lines = ansi_content.splitlines()
    link_idx = 0

    for line_idx, raw_line in enumerate(lines, start=1):
        clean = strip_ansi(raw_line)
        for match in MDOK_LINK_RE.finditer(clean):
            icon = match.group(1)
            inner_text = match.group(2).strip().lstrip("\ufe0f").strip()
            prefix_bytes = len(clean[:match.start()].encode("utf-8"))
            match_bytes = len(match.group(0).encode("utf-8"))
            col_start = prefix_bytes + 1  # 1-based UTF-8 byte index matching Vim col('.')
            col_end = prefix_bytes + match_bytes


            # Find matching metadata: by text first, or sequential
            matched_link = links_by_text.get(inner_text)
            if not matched_link and link_idx < len(links):
                matched_link = links[link_idx]
                link_idx += 1

            if matched_link:
                item = {
                    "col_start": col_start,
                    "col_end": col_end,
                    "icon": icon,
                    "text": inner_text,
                    "type": matched_link.get("type", "file"),
                    "target": matched_link.get("target", ""),
                    "href": matched_link.get("href", ""),
                    "exists": 1 if matched_link.get("exists", False) else 0,
                }
                links_by_line.setdefault(line_idx, []).append(item)
                if inner_text not in links_by_text:
                    links_by_text[inner_text] = item

    return links_by_line, links_by_text


def generate_vim_script(
    ansi_path: str,
    source_file: Optional[str],
    links_by_line: Dict[int, List[Dict[str, Any]]],
    links_by_text: Dict[str, Dict[str, Any]],
    editor_type: str,
    doc_width: Optional[int] = None,
    box_style: Optional[str] = None,
    code_theme: Optional[str] = None,
    no_lines: bool = False,
) -> str:
    """
    Generate companion Vimscript that configures buffer-local link maps,
    navigation stack, 'gf' link following, and '<C-o>' back-navigation.
    """
    abs_ansi = os.path.abspath(ansi_path)
    abs_source = os.path.abspath(source_file) if source_file and source_file != "-" else ""
    python_bin = sys.executable

    # Serialize links to JSON for safe vim evaluation
    line_json = json.dumps(links_by_line)
    text_json = json.dumps(links_by_text)

    # Build cli opts to pass when rendering child documents
    cli_opts = ["--no-center"]
    if doc_width:
        cli_opts.extend(["-w", str(doc_width)])
    if box_style:
        cli_opts.extend(["-b", box_style])
    if code_theme:
        cli_opts.extend(["--code-theme", code_theme])
    if no_lines:
        cli_opts.append("--no-lines")
    cli_opts_str = " ".join(cli_opts)

    script = f'''" mdok navigation script
set hidden

if !exists('g:mdok_nav_init')
  let g:mdok_nav_init = 1
  let g:mdok_nav_stack = []
  let g:mdok_temp_files = []
  let g:mdok_python = '{python_bin}'
  let g:mdok_cli_opts = '{cli_opts_str}'
  let g:mdok_editor = '{editor_type}'

  function! s:find_link_at(line_num, col, line_text) abort
    " 1. Line and column lookup
    if exists('b:mdok_links_by_line')
      let l:k = string(a:line_num)
      let l:items = has_key(b:mdok_links_by_line, l:k) ? b:mdok_links_by_line[l:k] : (has_key(b:mdok_links_by_line, a:line_num) ? b:mdok_links_by_line[a:line_num] : [])
      for l:it in l:items
        if a:col >= l:it.col_start && a:col <= l:it.col_end
          return l:it
        endif
      endfor
      if len(l:items) == 1
        return l:items[0]
      endif
      let l:closest = {{}}
      let l:min_dist = 999999
      for l:it in l:items
        let l:dist = min([abs(a:col - l:it.col_start), abs(a:col - l:it.col_end)])
        if l:dist < l:min_dist
          let l:min_dist = l:dist
          let l:closest = l:it
        endif
      endfor
      if !empty(l:closest)
        return l:closest
      endif
    endif

    " 2. Match pattern on current line
    if exists('b:mdok_links_by_text')
      let l:pat = '\\[[📄⚠️§🌐]\\%uFE0F\\?\\s*\\([^]]\\+\\)\\]'
      let l:start = 0
      while 1
        let l:idx = match(a:line_text, l:pat, l:start)
        if l:idx == -1
          break
        endif
        let l:m = matchstr(a:line_text, l:pat, l:start)
        let l:m_len = len(l:m)
        let l:s_col = l:idx + 1
        let l:e_col = l:idx + l:m_len
        if a:col >= l:s_col && a:col <= l:e_col
          let l:inner = substitute(l:m, '^\\[[📄⚠️§🌐]\\%uFE0F\\?\\s*', '', '')
          let l:inner = substitute(l:inner, '\\]$', '', '')
          let l:inner = trim(l:inner)
          if has_key(b:mdok_links_by_text, l:inner)
            return b:mdok_links_by_text[l:inner]
          endif
        endif
        let l:start = l:idx + max([1, l:m_len])
      endwhile

      " 3. Substring match fallback
      for [l:k, l:v] in items(b:mdok_links_by_text)
        if stridx(a:line_text, l:k) != -1
          return l:v
        endif
      endfor
    endif

    return {{}}
  endfunction

  function! MdokFollowLink() abort
    let l:ln = line('.')
    let l:cl = col('.')
    let l:lt = getline('.')
    let l:link = s:find_link_at(l:ln, l:cl, l:lt)

    if empty(l:link)
      try
        normal! gf
      catch
        echohl WarningMsg | echo "mdok: No link under cursor" | echohl None
      endtry
      return
    endif

    let l:type = get(l:link, 'type', '')
    let l:target = get(l:link, 'target', '')

    if l:type ==# 'file'
      if !get(l:link, 'exists', 0)
        echohl ErrorMsg | echo "mdok: Target file not found: " . l:target | echohl None
        return
      endif
      call s:open_rendered_doc(l:target)
    elseif l:type ==# 'anchor'
      call s:jump_to_anchor(l:link)
    elseif l:type ==# 'external'
      call s:open_external_url(l:target)
    endif
  endfunction

  function! s:open_rendered_doc(target_file) abort
    let l:cur_buf = bufnr('%')
    let l:cur_pos = getpos('.')
    let l:cur_file = get(b:, 'mdok_source_file', '')
    let l:cur_ansi = get(b:, 'mdok_ansi_file', '')

    call add(g:mdok_nav_stack, {{
      \\ 'buf': l:cur_buf,
      \\ 'pos': l:cur_pos,
      \\ 'file': l:cur_file,
      \\ 'ansi': l:cur_ansi
    \\ }})

    let l:new_ansi = tempname() . '.ansi'
    call add(g:mdok_temp_files, l:new_ansi)
    call add(g:mdok_temp_files, l:new_ansi . '.vim')

    let l:cmd = shellescape(g:mdok_python) . ' -m mdok.cli --render-ansi ' . shellescape(l:new_ansi) . ' ' . shellescape(a:target_file) . ' ' . g:mdok_cli_opts
    let l:out = system(l:cmd)
    if v:shell_error != 0 || !filereadable(l:new_ansi)
      call remove(g:mdok_nav_stack, -1)
      echohl ErrorMsg | echo "mdok render error: " . l:out | echohl None
      return
    endif

    if has('nvim') || g:mdok_editor ==# 'nvim'
      enew
      let l:init_s = l:new_ansi . '.vim'
      let l:tb = bufnr('%')
      execute 'terminal cat ' . fnameescape(l:new_ansi)
      execute 'autocmd TermClose <buffer> call feedkeys("\\<C-\\\\>\\<C-n>gg", "n") | if filereadable(' . string(l:init_s) . ') | execute "source " . fnameescape(' . string(l:init_s) . ') | endif'
      if filereadable(l:init_s)
        execute 'source ' . fnameescape(l:init_s)
      endif
    else
      let l:tb = term_start(['cat', l:new_ansi], {{
        \\ 'curwin': 1,
        \\ 'term_finish': 'open',
        \\ 'exit_cb': {{j, s -> timer_start(20, {{-> feedkeys("\\<C-W>Ngg", "tx!")}})}}
      \\ }})
      let l:init_s = l:new_ansi . '.vim'
      if filereadable(l:init_s)
        execute 'source ' . fnameescape(l:init_s)
      endif
    endif
  endfunction

  function! MdokGoBack() abort
    if empty(g:mdok_nav_stack)
      echohl WarningMsg | echo "mdok: At beginning of navigation history" | echohl None
      return
    endif

    let l:prev = remove(g:mdok_nav_stack, -1)
    let l:pbuf = l:prev.buf

    if bufexists(l:pbuf)
      execute 'buffer ' . l:pbuf
      if has('nvim') || g:mdok_editor ==# 'nvim'
        call feedkeys("\\<C-\\\\>\\<C-n>", "n")
      else
        call feedkeys("\\<C-W>N", "n")
      endif
      call setpos('.', l:prev.pos)
      normal! zz
    else
      if !empty(l:prev.file) && filereadable(l:prev.file)
        call s:open_rendered_doc(l:prev.file)
        call setpos('.', l:prev.pos)
        normal! zz
      endif
    endif
  endfunction

  function! MdokSmartQuit() abort
    if !empty(g:mdok_nav_stack)
      call MdokGoBack()
    else
      qa!
    endif
  endfunction

  function! MdokJumpToEnd() abort
    if v:count > 0
      execute v:count
      normal! zz
      return
    endif
    let l:ln = line('$')
    while l:ln > 1
      let l:txt = getline(l:ln)
      if l:txt !~# '^\\s*$' && l:txt !~# '^\\[Process exited'
        break
      endif
      let l:ln -= 1
    endwhile
    execute l:ln
    normal! zz
  endfunction

  function! s:jump_to_anchor(link) abort
    let l:target = get(a:link, 'target', '')
    let l:heading = substitute(l:target, '^#', '', '')
    let l:heading = substitute(l:heading, '-', ' ', 'g')

    let l:cur_buf = bufnr('%')
    let l:cur_pos = getpos('.')
    call add(g:mdok_nav_stack, {{
      \\ 'buf': l:cur_buf,
      \\ 'pos': l:cur_pos,
      \\ 'file': get(b:, 'mdok_source_file', ''),
      \\ 'ansi': get(b:, 'mdok_ansi_file', '')
    \\ }})

    let @/ = l:heading
    let l:found = search('\\c' . escape(l:heading, '\\'), 'W')
    if l:found == 0
      let l:txt = get(a:link, 'text', '')
      if !empty(l:txt)
        let l:found = search('\\c' . escape(l:txt, '\\'), 'W')
      endif
    endif

    if l:found > 0
      normal! zz
    else
      echohl WarningMsg | echo "mdok: Heading not found: " . l:target | echohl None
    endif
  endfunction

  function! s:open_external_url(url) abort
    if has('mac')
      call system('open ' . shellescape(a:url))
    elseif has('unix')
      call system('xdg-open ' . shellescape(a:url) . ' > /dev/null 2>&1 &')
    elseif has('win32') || has('win64')
      call system('cmd /c start ' . shellescape(a:url))
    endif
    echo "mdok: Opened " . a:url
  endfunction

  function! MdokEditSource() abort
    let l:src = get(b:, 'mdok_source_file', '')
    if !empty(l:src) && filereadable(l:src)
      execute 'edit ' . fnameescape(l:src)
    else
      echohl WarningMsg | echo "mdok: Source file not available for editing" | echohl None
    endif
  endfunction

  function! s:cleanup_temp_files() abort
    for l:f in g:mdok_temp_files
      if filereadable(l:f)
        call delete(l:f)
      endif
    endfor
  endfunction

  autocmd VimLeavePre * call s:cleanup_temp_files()
endif

" Buffer-local link configuration
call add(g:mdok_temp_files, '{abs_ansi}')
call add(g:mdok_temp_files, '{abs_ansi}.vim')
let b:mdok_source_file = '{abs_source}'
let b:mdok_ansi_file = '{abs_ansi}'
let b:mdok_links_by_line = json_decode('{line_json}')
let b:mdok_links_by_text = json_decode('{text_json}')

" Keybindings for active buffer
nnoremap <buffer> <silent> gf :call MdokFollowLink()<CR>
nnoremap <buffer> <silent> <CR> :call MdokFollowLink()<CR>
nnoremap <buffer> <silent> <C-o> :call MdokGoBack()<CR>
nnoremap <buffer> <silent> <C-t> :call MdokGoBack()<CR>
nnoremap <buffer> <silent> b :call MdokGoBack()<CR>
nnoremap <buffer> <silent> B :call MdokGoBack()<CR>
nnoremap <buffer> <silent> u :call MdokGoBack()<CR>
nnoremap <buffer> <silent> <BS> :call MdokGoBack()<CR>
nnoremap <buffer> <silent> e :call MdokEditSource()<CR>
nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>
nnoremap <buffer> <silent> Q :qa!<CR>
nnoremap <buffer> <silent> G :call MdokJumpToEnd()<CR>
nnoremap <buffer> <silent> <Space> <C-f>
nnoremap <buffer> <silent> n nzz
nnoremap <buffer> <silent> N Nzz
nnoremap <buffer> <silent> <C-d> <C-d>zz
nnoremap <buffer> <silent> <C-u> <C-u>zz
nnoremap <buffer> <silent> <C-w>h <Nop>
nnoremap <buffer> <silent> <C-w><Left> <Nop>
nnoremap <buffer> <silent> <C-w>w <Nop>
nnoremap <buffer> <silent> <C-w>W <Nop>
nnoremap <buffer> <silent> L :!less -R -i -j.5 -g -J --use-color -DSkY {abs_ansi}<CR>
tnoremap <buffer> <silent> <Esc> <C-\\><C-n>
'''
    return script


def write_vim_companion(
    ansi_path: str,
    source_file: Optional[str],
    links: List[Dict[str, Any]],
    editor_type: str,
    doc_width: Optional[int] = None,
    box_style: Optional[str] = None,
    code_theme: Optional[str] = None,
    no_lines: bool = False,
) -> str:
    """
    Generate and save the .vim companion script for an ANSI rendered document.
    Returns the path to the written script.
    """
    with open(ansi_path, "r", encoding="utf-8", errors="replace") as f:
        ansi_content = f.read()

    links_by_line, links_by_text = build_link_manifest(ansi_content, links)
    vim_script = generate_vim_script(
        ansi_path=ansi_path,
        source_file=source_file,
        links_by_line=links_by_line,
        links_by_text=links_by_text,
        editor_type=editor_type,
        doc_width=doc_width,
        box_style=box_style,
        code_theme=code_theme,
        no_lines=no_lines,
    )

    companion_path = f"{ansi_path}.vim"
    with open(companion_path, "w", encoding="utf-8") as f:
        f.write(vim_script)

    return companion_path
