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

  if has('nvim') || g:mdok_editor ==# 'nvim'
    function! s:patch_buftabline() abort
      if exists('*buftabline#update') || filereadable(expand('~/.vim/bundle/vim-buftabline/plugin/buftabline.vim'))
        function! buftabline#update(zombie) abort
          set tabline=
          if tabpagenr('$') > 1
            silent! set showtabline=2
            return
          endif
          let l:show = get(g:, 'buftabline_show', 2)
          if 0 == l:show
            silent! set showtabline=1
            return
          elseif 1 == l:show
            if exists('*buftabline#user_buffers')
              let l:bufnums = filter(buftabline#user_buffers(), 'v:val != a:zombie')
              let &g:showtabline = 1 + ( len(l:bufnums) > 1 )
            endif
          elseif 2 == l:show
            silent! set showtabline=2
          endif
          if exists('*buftabline#render')
            set tabline=%!buftabline#render()
          endif
        endfunction
      endif
    endfunction
    silent! call s:patch_buftabline()
    augroup MdokNvimBuftablinePatch
      autocmd!
      autocmd VimEnter,TabEnter,BufEnter,BufWritePost * silent! call s:patch_buftabline()
    augroup END
  endif

  function! s:apply_clean_split() abort
    silent! set fillchars=vert:\u00a0,eob:\\ 
    if has('nvim') || g:mdok_editor ==# 'nvim'
      silent! set fillchars+=vert:\\ 
    endif
    silent! highlight! clear VertSplit
    silent! highlight! link VertSplit Normal
    silent! highlight! clear WinSeparator
    silent! highlight! link WinSeparator Normal
  endfunction
  silent! call s:apply_clean_split()

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

  function! s:find_viewer_window() abort
    for l:w in range(1, winnr('$'))
      if getwinvar(l:w, 'mdok_viewer', 0) || getbufvar(winbufnr(l:w), 'mdok_viewer', 0)
        return l:w
      endif
    endfor
    for l:w in range(1, winnr('$'))
      if !getwinvar(l:w, 'mdok_margin', 0) && !getbufvar(winbufnr(l:w), 'mdok_margin', 0)
        return l:w
      endif
    endfor
    return winnr('$')
  endfunction

  function! s:is_buf_displayed(bufnr) abort
    if exists('*win_findbuf')
      return !empty(win_findbuf(a:bufnr))
    endif
    return bufwinnr(a:bufnr) != -1
  endfunction

  function! s:can_wipeout_buffer(bufnr) abort
    if !bufexists(a:bufnr) || getbufvar(a:bufnr, '&modified')
      return 0
    endif
    if s:is_buf_displayed(a:bufnr)
      return 0
    endif
    if getbufvar(a:bufnr, 'mdok_margin', 0) || getbufvar(a:bufnr, 'mdok_viewer', 0)
      return 0
    endif
    let l:btype = getbufvar(a:bufnr, '&buftype')
    if l:btype ==# 'terminal' || l:btype ==# 'nofile'
      return 0
    endif
    let l:name = bufname(a:bufnr)
    if empty(l:name) || l:name =~# '^\\[No Name\\]' || l:name =~# '^\\[no file\\]'
      return 1
    endif
    return 0
  endfunction

  function! s:open_rendered_doc(target_file) abort
    let l:target_win = s:find_viewer_window()
    if l:target_win > 0 && l:target_win <= winnr('$')
      execute l:target_win . 'wincmd w'
    endif

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

    let l:old_buf = bufnr('%')
    if has('nvim') || g:mdok_editor ==# 'nvim'
      enew
      setlocal nobuflisted bufhidden=wipe
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      let l:init_s = l:new_ansi . '.vim'
      let l:tb = bufnr('%')
      execute 'terminal cat ' . fnameescape(l:new_ansi)
      setlocal nobuflisted bufhidden=wipe
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      if l:old_buf != l:tb && bufexists(l:old_buf) && !getbufvar(l:old_buf, 'mdok_margin', 0)
        silent! execute 'bwipeout! ' . l:old_buf
      endif
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
      setlocal nobuflisted bufhidden=wipe
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      if l:old_buf != l:tb && bufexists(l:old_buf) && !getbufvar(l:old_buf, 'mdok_margin', 0)
        silent! execute 'bwipeout! ' . l:old_buf
      endif
      let l:init_s = l:new_ansi . '.vim'
      if filereadable(l:init_s)
        execute 'source ' . fnameescape(l:init_s)
      endif
    endif

    let l:mwidth = get(g:, 'mdok_margin_width', 0)
    if l:mwidth > 0
      for l:w in range(1, winnr('$'))
        if getwinvar(l:w, 'mdok_margin', 0) || getbufvar(winbufnr(l:w), 'mdok_margin', 0)
          execute l:w . 'wincmd w'
          execute 'vertical resize ' . l:mwidth
          execute l:target_win . 'wincmd w'
          break
        endif
      endfor
    endif
    silent! call s:apply_clean_split()
  endfunction

  function! MdokGoBack() abort
    if empty(g:mdok_nav_stack)
      echohl WarningMsg | echo "mdok: At beginning of navigation history" | echohl None
      return
    endif

    let l:target_win = s:find_viewer_window()
    if l:target_win > 0 && l:target_win <= winnr('$')
      execute l:target_win . 'wincmd w'
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

    let l:mwidth = get(g:, 'mdok_margin_width', 0)
    if l:mwidth > 0
      for l:w in range(1, winnr('$'))
        if getwinvar(l:w, 'mdok_margin', 0) || getbufvar(winbufnr(l:w), 'mdok_margin', 0)
          execute l:w . 'wincmd w'
          execute 'vertical resize ' . l:mwidth
          execute l:target_win . 'wincmd w'
          break
        endif
      endfor
    endif
    silent! call s:apply_clean_split()
  endfunction

  function! MdokSmartQuit() abort
    if !empty(g:mdok_nav_stack)
      call MdokGoBack()
    else
      qa!
    endif
  endfunction

  function! MdokLastContentLine() abort
    if exists('b:mdok_last_content_line') && b:mdok_last_content_line > 0
      return b:mdok_last_content_line
    endif
    let l:ln = line('$')
    while l:ln > 1
      let l:txt = getline(l:ln)
      if l:txt !~# '^\\s*$' && l:txt !~# '^\\[Process exited'
        break
      endif
      let l:ln -= 1
    endwhile
    let b:mdok_last_content_line = l:ln
    return l:ln
  endfunction

  function! MdokDown(cnt) abort
    let l:last = MdokLastContentLine()
    let l:cur = line('.')
    if l:cur >= l:last
      return
    endif
    let l:step = min([a:cnt, l:last - l:cur])
    execute 'normal! ' . l:step . 'j'
  endfunction

  function! MdokHalfPageDown() abort
    let l:last = MdokLastContentLine()
    execute "normal! \\<C-d>"
    if line('.') > l:last
      execute l:last
    endif
    normal! zz
  endfunction

  function! MdokPageDown() abort
    let l:last = MdokLastContentLine()
    execute "normal! \\<C-f>"
    if line('.') > l:last
      execute l:last
    endif
    normal! zz
  endfunction

  function! MdokParagraphDown() abort
    let l:last = MdokLastContentLine()
    normal! }}
    if line('.') > l:last
      execute l:last
    endif
  endfunction

  function! MdokJumpToEnd() abort
    if v:count > 0
      execute v:count
      normal! zz
      return
    endif
    execute MdokLastContentLine()
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

  function! s:get_clean_text(text) abort
    " Strip box/border characters and unicode symbols
    let l:t = substitute(a:text, '[\x7c\u2500-\u257f\u2550-\u256c\u2022\u00b7]', ' ', 'g')
    " Strip link tags [icon text]
    let l:t = substitute(l:t, '\\%uFE0F\\?', '', 'g')
    let l:t = substitute(l:t, '\\[[📄⚠️§🌐]', '', 'g')
    let l:t = substitute(l:t, '\\]', '', 'g')
    " Strip markdown bullets/dashes at line start
    let l:t = substitute(l:t, '^\\s*[*+-]\\s\\+', '', '')
    " Collapse spaces and trim
    let l:t = substitute(l:t, '\\s\\+', ' ', 'g')
    return trim(l:t)
  endfunction

  function! MdokEditSource() abort
    let l:src = get(b:, 'mdok_source_file', '')
    if empty(l:src)
      let l:src = get(b:, 'mdok_source_path', '')
    endif
    if empty(l:src) || !filereadable(l:src)
      echohl WarningMsg | echo "mdok: Source file not available for editing" | echohl None
      return
    endif

    let l:src_full = fnamemodify(l:src, ':p')
    if fnamemodify(expand('%:p'), ':p') ==# l:src_full
      echohl MoreMsg | echo "mdok: Already editing source file" | echohl None
      return
    endif

    " Jump to tab if source file is already open
    for l:t in range(1, tabpagenr('$'))
      let l:buflist = tabpagebuflist(l:t)
      for l:b in l:buflist
        if fnamemodify(bufname(l:b), ':p') ==# l:src_full
          execute l:t . 'tabnext'
          return
        endif
      endfor
    endfor

    let l:ansi = get(b:, 'mdok_ansi_file', '')
    let l:viewer_tab = tabpagenr()
    let l:viewer_win = s:find_viewer_window()
    let l:viewer_buf = bufnr('%')
    let l:rendered_line = line('.')
    let l:rendered_total = max([1, line('$')])
    let l:ratio = (1.0 * l:rendered_line) / l:rendered_total
    let l:raw_line = getline('.')
    let l:clean = s:get_clean_text(l:raw_line)

    " Open source file in a new tab for native editing
    silent! execute 'tabedit ' . fnameescape(l:src)

    " Buffer-local metadata for the editing tab
    let b:mdok_target_ansi = l:ansi
    let b:mdok_source_path = l:src
    let b:mdok_viewer_tab = l:viewer_tab
    let b:mdok_viewer_win = l:viewer_win
    let b:mdok_viewer_buf = l:viewer_buf

    " Configure edit buffer settings
    set laststatus=2
    set showtabline=2
    setlocal number
    setlocal bufhidden=delete
    silent! syntax enable
    silent! filetype detect

    " Close tab when buffer-close commands are executed
    cnoreabbrev <buffer> <expr> bd (getcmdtype() ==# ':' && getcmdline() =~# '^bd!\\?$') ? 'tabclose' . (getcmdline() =~# '!$' ? '!' : '') : 'bd'
    cnoreabbrev <buffer> <expr> bdelete (getcmdtype() ==# ':' && getcmdline() =~# '^bdelete!\\?$') ? 'tabclose' . (getcmdline() =~# '!$' ? '!' : '') : 'bdelete'
    cnoreabbrev <buffer> <expr> bw (getcmdtype() ==# ':' && getcmdline() =~# '^bw!\\?$') ? 'tabclose' . (getcmdline() =~# '!$' ? '!' : '') : 'bw'
    cnoreabbrev <buffer> <expr> bwipeout (getcmdtype() ==# ':' && getcmdline() =~# '^bwipeout!\\?$') ? 'tabclose' . (getcmdline() =~# '!$' ? '!' : '') : 'bwipeout'

    " Attach save hook to re-render ANSI document in background
    augroup MdokSourceEdit
      autocmd! * <buffer>
      autocmd BufWritePost <buffer> call s:on_source_written()
      autocmd BufDelete,BufWipeout <buffer> call s:on_source_buf_deleted()
    augroup END

    " Locate matching line in source buffer
    let l:matched = 0
    if len(l:clean) >= 3
      " 1. Exact case-insensitive substring
      let l:pat = '\\c' . escape(l:clean, '\\/~.*^$[]')
      if search(l:pat, 'cw') > 0
        let l:matched = 1
      endif

      " 2. Multi-word pattern (first and last significant words)
      if !l:matched
        let l:words = split(l:clean, '\\W\\+')
        let l:long_words = filter(l:words, 'len(v:val) >= 3')
        if len(l:long_words) >= 2
          let l:w1 = l:long_words[0]
          let l:w2 = l:long_words[-1]
          let l:pat = '\\c' . escape(l:w1, '\\/~.*^$[]') . '.\\{{0,60\\}}' . escape(l:w2, '\\/~.*^$[]')
          if search(l:pat, 'cw') > 0
            let l:matched = 1
          endif
        endif
      endif

      " 3. Longest word
      if !l:matched
        let l:longest = ''
        for l:w in split(l:clean, '\\W\\+')
          if len(l:w) > len(l:longest)
            let l:longest = l:w
          endif
        endfor
        if len(l:longest) >= 4
          let l:pat = '\\c' . escape(l:longest, '\\/~.*^$[]')
          if search(l:pat, 'cw') > 0
            let l:matched = 1
          endif
        endif
      endif
    endif

    " 4. Fallback to proportional line position
    if !l:matched
      let l:target_ln = max([1, float2nr(round(l:ratio * line('$')))])
      execute l:target_ln
    endif

    normal! zz
  endfunction

  function! s:on_source_written() abort
    if has('nvim') || g:mdok_editor ==# 'nvim'
      silent! call s:patch_buftabline()
    endif

    let l:ansi = get(b:, 'mdok_target_ansi', '')
    let l:src = get(b:, 'mdok_source_path', '')
    if empty(l:ansi) || empty(l:src)
      return
    endif

    " Re-render the ANSI output in the background via CLI
    let l:cmd = shellescape(g:mdok_python) . ' -m mdok.cli --render-ansi ' . shellescape(l:ansi) . ' ' . shellescape(l:src) . ' ' . g:mdok_cli_opts
    let l:out = system(l:cmd)
    if v:shell_error != 0
      redraw
      echohl ErrorMsg | echomsg "mdok re-render error: " . l:out | echohl None
      return
    endif

    " Record reload request for viewer tab
    let g:mdok_reload_pending = 1
    let g:mdok_reload_ansi = l:ansi
    let g:mdok_reload_src = l:src
    let g:mdok_reload_tab = get(b:, 'mdok_viewer_tab', 1)
    let g:mdok_reload_win = get(b:, 'mdok_viewer_win', s:find_viewer_window())
    let g:mdok_reload_buf = get(b:, 'mdok_viewer_buf', 0)
    let g:mdok_reload_text = s:get_clean_text(getline('.'))
    let g:mdok_reload_ratio = (1.0 * line('.')) / max([1, line('$')])

    redraw
    echohl MoreMsg | echomsg "mdok: Re-rendered document preview" | echohl None
  endfunction

  function! s:on_source_buf_deleted() abort
    call timer_start(10, {{-> s:close_empty_tabs()}})
  endfunction

  function! s:close_empty_tabs() abort
    for l:t in range(tabpagenr('$'), 2, -1)
      let l:bufs = tabpagebuflist(l:t)
      if len(l:bufs) == 1
        let l:b = l:bufs[0]
        let l:name = bufname(l:b)
        let l:btype = getbufvar(l:b, '&buftype')
        let l:mod = getbufvar(l:b, '&modified')
        if (empty(l:name) || l:name =~# '^\\[No Name\\]' || l:name =~# '^\\[no file\\]') && !l:mod && l:btype !=# 'terminal' && l:btype !=# 'nofile'
          silent! execute l:t . 'tabclose!'
          if s:can_wipeout_buffer(l:b)
            silent! execute 'bwipeout! ' . l:b
          endif
        endif
      endif
    endfor
    for l:b in range(1, bufnr('$'))
      if s:can_wipeout_buffer(l:b)
        silent! execute 'bwipeout! ' . l:b
      endif
    endfor
  endfunction

  function! s:on_tab_enter()
    silent! call s:close_empty_tabs()
    if tabpagenr() == get(g:, 'mdok_reload_tab', 1)
      set laststatus=0
      silent! call s:apply_clean_split()
      if tabpagenr('$') == 1
        set showtabline=1
      endif
      if get(g:, 'mdok_reload_pending', 0)
        let g:mdok_reload_pending = 0
        silent! call s:reload_viewer_buffer()
      endif
    endif
  endfunction

  function! s:reload_viewer_buffer() abort
    let l:target_win = s:find_viewer_window()
    if l:target_win > 0 && l:target_win <= winnr('$')
      execute l:target_win . 'wincmd w'
    endif

    let l:ansi = g:mdok_reload_ansi
    let l:src = g:mdok_reload_src
    let l:target_text = g:mdok_reload_text
    let l:target_ratio = g:mdok_reload_ratio
    let l:init_s = l:ansi . '.vim'
    let l:old_buf = bufnr('%')

    if getbufvar(l:old_buf, 'mdok_margin', 0)
      return
    endif

    if has('nvim') || g:mdok_editor ==# 'nvim'
      enew
      setlocal nobuflisted bufhidden=wipe
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      let l:tb = bufnr('%')
      execute 'terminal cat ' . fnameescape(l:ansi)
      setlocal nobuflisted bufhidden=wipe nonumber norelativenumber signcolumn=no foldcolumn=0
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      if l:old_buf != l:tb && bufexists(l:old_buf) && !getbufvar(l:old_buf, 'mdok_margin', 0)
        silent! execute 'bwipeout! ' . l:old_buf
      endif
      execute 'autocmd TermClose <buffer> call timer_start(20, {{-> s:on_reload_done(' . string(l:target_text) . ', ' . string(l:target_ratio) . ', ' . string(l:init_s) . ')}})'
      if filereadable(l:init_s)
        execute 'source ' . fnameescape(l:init_s)
      endif
    else
      let l:tb = term_start(['cat', l:ansi], {{
        \\ 'curwin': 1,
        \\ 'term_finish': 'open',
        \\ 'exit_cb': {{j, s -> timer_start(20, {{-> s:on_reload_done(l:target_text, l:target_ratio, l:init_s)}})}}
      \\ }})
      setlocal nobuflisted bufhidden=wipe nonumber norelativenumber signcolumn=no foldcolumn=0
      let b:mdok_viewer = 1
      let w:mdok_viewer = 1
      if l:old_buf != l:tb && bufexists(l:old_buf) && !getbufvar(l:old_buf, 'mdok_margin', 0)
        silent! execute 'bwipeout! ' . l:old_buf
      endif
      if filereadable(l:init_s)
        execute 'source ' . fnameescape(l:init_s)
      endif
    endif

    let l:mwidth = get(g:, 'mdok_margin_width', 0)
    if l:mwidth > 0
      for l:w in range(1, winnr('$'))
        if getwinvar(l:w, 'mdok_margin', 0) || getbufvar(winbufnr(l:w), 'mdok_margin', 0)
          execute l:w . 'wincmd w'
          setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth
          execute 'vertical resize ' . l:mwidth
          execute l:target_win . 'wincmd w'
          break
        endif
      endfor
    endif
    silent! call s:apply_clean_split()
  endfunction

  function! s:on_reload_done(target_text, target_ratio, init_s) abort
    let l:target_win = s:find_viewer_window()
    if l:target_win > 0 && l:target_win <= winnr('$')
      execute l:target_win . 'wincmd w'
    endif

    if has('nvim') || g:mdok_editor ==# 'nvim'
      call feedkeys("\\<C-\\\\>\\<C-n>", "n")
    else
      call feedkeys("\\<C-W>N", "tx!")
    endif

    if filereadable(a:init_s)
      execute 'source ' . fnameescape(a:init_s)
    endif

    let b:mdok_viewer = 1
    let w:mdok_viewer = 1
    unlet! b:mdok_last_content_line

    let l:mwidth = get(g:, 'mdok_margin_width', 0)
    if l:mwidth > 0
      for l:w in range(1, winnr('$'))
        if getwinvar(l:w, 'mdok_margin', 0) || getbufvar(winbufnr(l:w), 'mdok_margin', 0)
          execute l:w . 'wincmd w'
          setlocal buftype=nofile nobuflisted nomodifiable nonumber norelativenumber signcolumn=no foldcolumn=0 winfixwidth
          execute 'vertical resize ' . l:mwidth
          execute l:target_win . 'wincmd w'
          break
        endif
      endfor
    endif
    silent! call s:apply_clean_split()

    call timer_start(30, {{-> s:position_reloaded_cursor(a:target_text, a:target_ratio)}})
  endfunction

  function! s:position_reloaded_cursor(target_text, target_ratio) abort
    let l:matched = 0
    if len(a:target_text) >= 3
      let l:pat = '\\c' . escape(a:target_text, '\\/~.*^$[]')
      if search(l:pat, 'cw') > 0
        let l:matched = 1
      endif
    endif

    if !l:matched
      let l:target_ln = max([1, float2nr(round(a:target_ratio * MdokLastContentLine()))])
      execute l:target_ln
    endif

    normal! zz
  endfunction

  function! s:cleanup_temp_files() abort
    for l:f in g:mdok_temp_files
      if filereadable(l:f)
        call delete(l:f)
      endif
    endfor
  endfunction

  augroup MdokGlobal
    autocmd!
    autocmd VimLeavePre * call s:cleanup_temp_files()
    autocmd TabEnter * call s:on_tab_enter()
    autocmd ColorScheme * if exists('*s:apply_clean_split') | call s:apply_clean_split() | endif
  augroup END
endif

" Buffer-local link configuration
setlocal nobuflisted bufhidden=wipe
silent! call s:apply_clean_split()
if has('nvim') || g:mdok_editor ==# 'nvim'
  silent! call matchadd('Ignore', '\\[Process exited \\d\\+\\]')
endif
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
nnoremap <buffer> <silent> i :call MdokEditSource()<CR>
nnoremap <buffer> <silent> I :call MdokEditSource()<CR>
nnoremap <buffer> <silent> q :call MdokSmartQuit()<CR>
nnoremap <buffer> <silent> Q :qa!<CR>
nnoremap <buffer> <silent> G :call MdokJumpToEnd()<CR>
nnoremap <buffer> <silent> j :<C-u>call MdokDown(v:count1)<CR>
nnoremap <buffer> <silent> <Down> :<C-u>call MdokDown(v:count1)<CR>
nnoremap <buffer> <silent> <C-d> :<C-u>call MdokHalfPageDown()<CR>
nnoremap <buffer> <silent> <C-f> :<C-u>call MdokPageDown()<CR>
nnoremap <buffer> <silent> <Space> :<C-u>call MdokPageDown()<CR>
nnoremap <buffer> <silent> <PageDown> :<C-u>call MdokPageDown()<CR>
nnoremap <buffer> <silent> }} :<C-u>call MdokParagraphDown()<CR>
nnoremap <buffer> <silent> n nzz
nnoremap <buffer> <silent> N Nzz
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
