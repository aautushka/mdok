import io
import os
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union, BinaryIO

from rich import box
from rich.box import Box
from rich.cells import cell_len
from rich.console import Console, ConsoleOptions, RenderResult, RenderableType, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.segment import Segment
from rich.style import Style
from rich.table import Table
from rich.text import Text

from mdok.theme import BOOKTABS, BOX_STYLES, DEFAULT_THEME
from mdok.renderer import calculate_smart_column_widths

# XML Namespaces
NS = {
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
    "w14": "http://schemas.microsoft.com/office/word/2010/wordml",
    "v": "urn:schemas-microsoft-com:vml",
}

# Superscript & Subscript mapping tables
SUPERSCRIPT_MAP = str.maketrans({
    "0": "⁰", "1": "¹", "2": "²", "3": "³", "4": "⁴",
    "5": "⁵", "6": "⁶", "7": "⁷", "8": "⁸", "9": "⁹",
    "+": "⁺", "-": "⁻", "=": "⁼", "(": "⁽", ")": "⁾",
    "n": "ⁿ", "i": "ⁱ",
})

SUBSCRIPT_MAP = str.maketrans({
    "0": "₀", "1": "₁", "2": "₂", "3": "₃", "4": "₄",
    "5": "₅", "6": "₆", "7": "₇", "8": "₈", "9": "₉",
    "+": "₊", "-": "₋", "=": "₌", "(": "₍", ")": "₎",
    "a": "ₐ", "e": "ₑ", "o": "ₒ", "x": "ₓ",
})

MONOSPACE_FONTS = {
    "consolas", "courier", "courier new", "menlo", "monaco",
    "liberation mono", "source code pro", "fira code", "jetbrains mono",
    "dejavu sans mono", "lucida console", "monospace",
}


def _local_tag(elem: ET.Element) -> str:
    """Return the local tag name without namespace."""
    if elem is None or not elem.tag:
        return ""
    return elem.tag.split("}")[-1]


def _is_truthy(val: Optional[str]) -> bool:
    """Evaluate whether an XML attribute value represents a truthy flag."""
    if val is None:
        return True
    val = val.lower().strip()
    return val not in ("0", "false", "none", "off", "no", "nil")


def _parse_color(val: Optional[str]) -> Optional[str]:
    """Parse a 6-digit hex color into a valid CSS-like hex string."""
    if not val:
        return None
    val = val.strip()
    if val.lower() in ("auto", "none", "transparent"):
        return None
    if re.match(r"^[0-9a-fA-F]{6}$", val):
        return f"#{val}"
    return None


def _parse_shading(shd_elem: Optional[ET.Element]) -> Optional[str]:
    """Extract background fill color from a <w:shd> element."""
    if shd_elem is None:
        return None
    fill = shd_elem.attrib.get(f"{{{NS['w']}}}fill") or shd_elem.attrib.get("fill")
    color = _parse_color(fill)
    if color and color.lower() not in ("#000000", "#ffffff"):
        return color
    return None


class NumberingTracker:
    """Tracks and formats multi-level numbered and bulleted lists."""

    def __init__(self, numbering_xml: Optional[bytes] = None) -> None:
        # (num_id, ilvl) -> (num_fmt, lvl_text, start_val)
        self.levels: Dict[Tuple[str, int], Tuple[str, str, int]] = {}
        # (num_id, ilvl) -> current_count
        self.counters: Dict[Tuple[str, int], int] = {}
        if numbering_xml:
            self._parse_numbering(numbering_xml)

    def _parse_numbering(self, xml_bytes: bytes) -> None:
        try:
            root = ET.fromstring(xml_bytes)
        except Exception:
            return

        # 1. Map abstractNumId -> dict of ilvl -> (numFmt, lvlText, start)
        abstract_map: Dict[str, Dict[int, Tuple[str, str, int]]] = {}
        for abs_num in root.findall(".//w:abstractNum", NS):
            abs_id = abs_num.attrib.get(f"{{{NS['w']}}}abstractNumId")
            if not abs_id:
                continue
            lvl_map: Dict[int, Tuple[str, str, int]] = {}
            for lvl in abs_num.findall("w:lvl", NS):
                try:
                    ilvl = int(lvl.attrib.get(f"{{{NS['w']}}}ilvl", "0"))
                except ValueError:
                    continue
                num_fmt_elem = lvl.find("w:numFmt", NS)
                num_fmt = num_fmt_elem.attrib.get(f"{{{NS['w']}}}val", "bullet") if num_fmt_elem is not None else "bullet"
                lvl_text_elem = lvl.find("w:lvlText", NS)
                lvl_text = lvl_text_elem.attrib.get(f"{{{NS['w']}}}val", "%1.") if lvl_text_elem is not None else "%1."
                start_elem = lvl.find("w:start", NS)
                try:
                    start_val = int(start_elem.attrib.get(f"{{{NS['w']}}}val", "1")) if start_elem is not None else 1
                except ValueError:
                    start_val = 1
                lvl_map[ilvl] = (num_fmt, lvl_text, start_val)
            abstract_map[abs_id] = lvl_map

        # 2. Map numId -> abstractNumId
        for num in root.findall(".//w:num", NS):
            num_id = num.attrib.get(f"{{{NS['w']}}}numId")
            abs_id_elem = num.find("w:abstractNumId", NS)
            if not num_id or abs_id_elem is None:
                continue
            abs_id = abs_id_elem.attrib.get(f"{{{NS['w']}}}val")
            if abs_id and abs_id in abstract_map:
                for ilvl, fmt_tuple in abstract_map[abs_id].items():
                    self.levels[(num_id, ilvl)] = fmt_tuple

    def get_prefix(self, num_id: str, ilvl: int) -> Tuple[str, str]:
        """
        Returns (prefix_text, item_type) where item_type is 'bullet' or 'number'.
        """
        fmt_tuple = self.levels.get((num_id, ilvl))
        indent = "  " * ilvl

        if not fmt_tuple:
            # Default bullet
            bullet_char = "•" if ilvl % 2 == 0 else "⁃"
            return f"{indent}{bullet_char} ", "bullet"

        num_fmt, lvl_text, start_val = fmt_tuple
        num_fmt = num_fmt.lower()

        if num_fmt == "bullet":
            bullet_char = "•" if ilvl % 2 == 0 else "⁃"
            return f"{indent}{bullet_char} ", "bullet"

        # Numbered item
        key = (num_id, ilvl)
        if key not in self.counters:
            self.counters[key] = start_val
        else:
            self.counters[key] += 1
        count = self.counters[key]

        # Reset deeper levels
        for d in range(ilvl + 1, 10):
            self.counters.pop((num_id, d), None)

        if num_fmt == "decimal":
            formatted = str(count)
        elif num_fmt == "lowerletter":
            formatted = chr(ord("a") + ((count - 1) % 26))
        elif num_fmt == "upperletter":
            formatted = chr(ord("A") + ((count - 1) % 26))
        elif num_fmt == "lowerroman":
            formatted = self._to_roman(count).lower()
        elif num_fmt == "upperroman":
            formatted = self._to_roman(count)
        else:
            formatted = str(count)

        # Substitute %1, %2, etc. in lvl_text
        prefix_str = lvl_text.replace(f"%{ilvl + 1}", formatted)
        # Fallback if pattern didn't match
        if "%" in prefix_str:
            prefix_str = re.sub(r"%\d+", formatted, prefix_str)
        if not prefix_str.endswith(" "):
            prefix_str += " "

        return f"{indent}{prefix_str}", "number"

    @staticmethod
    def _to_roman(n: int) -> str:
        val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
        syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
        roman = ""
        i = 0
        while n > 0 and i < len(val):
            for _ in range(n // val[i]):
                roman += syms[i]
                n -= val[i]
            i += 1
        return roman or str(n)


class DocxDocument:
    """
    High-fidelity Microsoft Word (.docx) document renderer for mdok.

    Parses OpenXML structure and renders native terminal typography:
    - Bold, italic, underline, strikethrough, color, highlight, code font.
    - TrueColor hyperlinks with clickable URLs.
    - Title, headings, blockquotes, and dividers.
    - Multi-level bulleted and numbered lists with indentation.
    - Intelligent table rendering:
      * Borderless / side-by-side signature & party layout tables.
      * Bordered data tables with booktabs styling and smart column widths.
      * Single-column table unnesting to avoid ugly boxes.
    """

    def __init__(
        self,
        source: Union[str, Path, BinaryIO, bytes],
        box_style: str = "booktabs",
        show_lines: bool = True,
        hyperlinks: bool = True,
        doc_width: Optional[int] = None,
        term_width: Optional[int] = None,
    ) -> None:
        self.box_style = box_style
        self.show_lines = show_lines
        self.hyperlinks = hyperlinks
        self.term_width = term_width

        self.rel_map: Dict[str, str] = {}
        self.numbering: Optional[NumberingTracker] = None
        self.body_elements: List[ET.Element] = []
        self.footnotes: Dict[str, str] = {}
        self.endnotes: Dict[str, str] = {}

        # Geometry & style attributes for automatic width deduction
        self.page_width_dxa: Optional[int] = None
        self.page_height_dxa: Optional[int] = None
        self.left_margin_dxa: Optional[int] = None
        self.right_margin_dxa: Optional[int] = None
        self.is_landscape: bool = False
        self.default_font_sz: Optional[int] = None
        self.table_specs: List[Dict[str, Any]] = []

        self._load(source)

        if doc_width is not None:
            self.doc_width = doc_width
        else:
            self.doc_width = self.deduce_width(term_width=term_width)

    def deduce_width(self, term_width: Optional[int] = None) -> int:
        """
        Deduce the natural document width from OpenXML page geometry, margins,
        font sizing, table column allocations, and content density.
        """
        # 1. Page geometry in dxa (1 inch = 1440 dxa)
        # Default US Letter: 12240 x 15840 dxa (8.5 x 11 in)
        page_w_dxa = self.page_width_dxa or 12240
        left_m_dxa = self.left_margin_dxa if self.left_margin_dxa is not None else 1440
        right_m_dxa = self.right_margin_dxa if self.right_margin_dxa is not None else 1440

        printable_dxa = max(2880, page_w_dxa - left_m_dxa - right_m_dxa)

        # 2. Font sizing
        # sz is in half-points (e.g. 22 = 11pt, 24 = 12pt, 20 = 10pt)
        # In typical Latin fonts (Calibri, Aptos, Times), char advance ≈ font_pts * 0.51 * 20 dxa/pt
        font_sz = self.default_font_sz or 22
        char_dxa = max(80.0, font_sz * 5.1)

        # Base character columns from page text body
        base_cols = int(round(printable_dxa / char_dxa))

        # Respect landscape orientation
        if self.is_landscape:
            base_cols = max(base_cols, 105)

        # 3. Inspect tables in the document
        max_table_cols = 0
        for tbl in self.table_specs:
            grid_widths = tbl.get("grid_widths", [])
            col_count = tbl.get("col_count", 0)

            if grid_widths and sum(grid_widths) > 0:
                tbl_dxa = sum(grid_widths)
                tbl_cols = int(round(tbl_dxa / char_dxa))
                max_table_cols = max(max_table_cols, tbl_cols)

            # Each table column needs reasonable breathing room
            if col_count > 1:
                min_for_cols = col_count * 14 + (col_count - 1) * 2
                max_table_cols = max(max_table_cols, min_for_cols)

        if max_table_cols > base_cols:
            base_cols = max_table_cols

        # 4. Clamp to standard document boundaries
        min_allowed = 60
        max_allowed = 135 if self.is_landscape else 115
        doc_cols = max(min_allowed, min(base_cols, max_allowed))

        # 5. Constrain by terminal width if available
        if term_width is not None and term_width > 0:
            doc_cols = min(doc_cols, max(30, term_width - 2))

        return doc_cols

    def _load(self, source: Union[str, Path, BinaryIO, bytes]) -> None:
        if isinstance(source, (str, Path)):
            zf = zipfile.ZipFile(os.path.expanduser(str(source)), "r")
        elif isinstance(source, bytes):
            zf = zipfile.ZipFile(io.BytesIO(source), "r")
        else:
            zf = zipfile.ZipFile(source, "r")

        with zf:
            namelist = set(zf.namelist())
            if "word/document.xml" not in namelist:
                raise ValueError("Not a valid Word (.docx) document: word/document.xml missing.")

            # Load document relationships (hyperlinks)
            if "word/_rels/document.xml.rels" in namelist:
                rels_xml = zf.read("word/_rels/document.xml.rels")
                try:
                    rels_root = ET.fromstring(rels_xml)
                    for rel in rels_root:
                        r_id = rel.attrib.get("Id")
                        target = rel.attrib.get("Target")
                        if r_id and target:
                            self.rel_map[r_id] = target
                except Exception:
                    pass

            # Load numbering
            num_xml = zf.read("word/numbering.xml") if "word/numbering.xml" in namelist else None
            self.numbering = NumberingTracker(num_xml)

            # Load styles if present (to find default font size)
            if "word/styles.xml" in namelist:
                try:
                    styles_root = ET.fromstring(zf.read("word/styles.xml"))
                    doc_defaults = styles_root.find("w:docDefaults", NS)
                    if doc_defaults is not None:
                        sz_elem = doc_defaults.find(".//w:sz", NS)
                        if sz_elem is not None:
                            val = sz_elem.attrib.get(f"{{{NS['w']}}}val") or sz_elem.attrib.get("w:val") or sz_elem.attrib.get("val")
                            if val and val.isdigit():
                                self.default_font_sz = int(val)
                    if self.default_font_sz is None:
                        # Try normal style
                        for style in styles_root.findall("w:style", NS):
                            s_id = style.attrib.get(f"{{{NS['w']}}}styleId") or style.attrib.get("w:styleId")
                            if s_id in ("Normal", "default"):
                                sz_elem = style.find(".//w:sz", NS)
                                if sz_elem is not None:
                                    val = sz_elem.attrib.get(f"{{{NS['w']}}}val") or sz_elem.attrib.get("w:val") or sz_elem.attrib.get("val")
                                    if val and val.isdigit():
                                        self.default_font_sz = int(val)
                                        break
                except Exception:
                    pass

            # Load footnotes
            if "word/footnotes.xml" in namelist:
                try:
                    fn_root = ET.fromstring(zf.read("word/footnotes.xml"))
                    for fn in fn_root.findall("w:footnote", NS):
                        fn_id = fn.attrib.get(f"{{{NS['w']}}}id") or fn.attrib.get("id")
                        fn_type = fn.attrib.get(f"{{{NS['w']}}}type") or fn.attrib.get("type")
                        if fn_type in ("separator", "continuationSeparator"):
                            continue
                        texts = [t.text for t in fn.findall(".//w:t", NS) if t.text]
                        if fn_id and texts:
                            self.footnotes[fn_id] = "".join(texts).strip()
                except Exception:
                    pass

            # Load endnotes
            if "word/endnotes.xml" in namelist:
                try:
                    en_root = ET.fromstring(zf.read("word/endnotes.xml"))
                    for en in en_root.findall("w:endnote", NS):
                        en_id = en.attrib.get(f"{{{NS['w']}}}id") or en.attrib.get("id")
                        en_type = en.attrib.get(f"{{{NS['w']}}}type") or en.attrib.get("type")
                        if en_type in ("separator", "continuationSeparator"):
                            continue
                        texts = [t.text for t in en.findall(".//w:t", NS) if t.text]
                        if en_id and texts:
                            self.endnotes[en_id] = "".join(texts).strip()
                except Exception:
                    pass

            # Load document.xml
            doc_xml = zf.read("word/document.xml")
            doc_root = ET.fromstring(doc_xml)
            body = doc_root.find("w:body", NS)
            if body is not None:
                self.body_elements = list(body)

                # Extract page geometry from sectPr
                sect_elements = body.findall(".//w:sectPr", NS)
                for sect in sect_elements:
                    pgSz = sect.find("w:pgSz", NS)
                    if pgSz is not None:
                        w_val = pgSz.attrib.get(f"{{{NS['w']}}}w") or pgSz.attrib.get("w:w") or pgSz.attrib.get("w")
                        h_val = pgSz.attrib.get(f"{{{NS['w']}}}h") or pgSz.attrib.get("w:h") or pgSz.attrib.get("h")
                        orient = pgSz.attrib.get(f"{{{NS['w']}}}orient") or pgSz.attrib.get("w:orient") or pgSz.attrib.get("orient")
                        if w_val and w_val.isdigit():
                            self.page_width_dxa = int(w_val)
                        if h_val and h_val.isdigit():
                            self.page_height_dxa = int(h_val)
                        if orient == "landscape" or (self.page_width_dxa and self.page_height_dxa and self.page_width_dxa > self.page_height_dxa):
                            self.is_landscape = True

                    pgMar = sect.find("w:pgMar", NS)
                    if pgMar is not None:
                        l_val = pgMar.attrib.get(f"{{{NS['w']}}}left") or pgMar.attrib.get("w:left") or pgMar.attrib.get("left")
                        r_val = pgMar.attrib.get(f"{{{NS['w']}}}right") or pgMar.attrib.get("w:right") or pgMar.attrib.get("right")
                        if l_val and l_val.isdigit():
                            self.left_margin_dxa = int(l_val)
                        if r_val and r_val.isdigit():
                            self.right_margin_dxa = int(r_val)

                # Extract table metrics
                for tbl in body.findall(".//w:tbl", NS):
                    grid = tbl.find("w:tblGrid", NS)
                    grid_widths = []
                    if grid is not None:
                        for col in grid.findall("w:gridCol", NS):
                            w_str = col.attrib.get(f"{{{NS['w']}}}w") or col.attrib.get("w:w") or col.attrib.get("w")
                            if w_str and w_str.isdigit():
                                grid_widths.append(int(w_str))
                    row_counts = [len(r.findall("w:tc", NS)) for r in tbl.findall("w:tr", NS)]
                    max_cols = max(row_counts) if row_counts else len(grid_widths)
                    self.table_specs.append({
                        "grid_widths": grid_widths,
                        "col_count": max(max_cols, len(grid_widths)),
                    })

    def _extract_runs_text(self, parent_elem: ET.Element) -> Text:
        """Parse text runs inside a paragraph or hyperlink, applying styles."""
        res = Text()

        for child in parent_elem:
            tag = _local_tag(child)

            if tag == "hyperlink":
                r_id = child.attrib.get(f"{{{NS['r']}}}id") or child.attrib.get("r:id") or child.attrib.get("id")
                url = self.rel_map.get(r_id, "") if r_id else ""
                link_text = self._extract_runs_text(child)
                if self.hyperlinks and url:
                    link_text.stylize(Style(link=url, underline=True, color="cyan"))
                else:
                    link_text.stylize(Style(underline=True, color="cyan"))
                res.append(link_text)

            elif tag == "r":
                r_text, r_style = self._parse_run(child)
                if r_text:
                    res.append(r_text, style=r_style)

            elif tag == "fldSimple":
                # Simple field (e.g. page numbers or dates)
                field_text = self._extract_runs_text(child)
                res.append(field_text)

            elif tag == "sdt":
                # Structured document tag (e.g. checkbox or content control)
                # Check for checkbox in sdtPr
                sdtPr = child.find("w:sdtPr", NS)
                chk = None
                if sdtPr is not None:
                    chk = sdtPr.find("w14:checkbox", NS)
                    if chk is None:
                        chk = sdtPr.find(".//w14:checkbox", NS)
                if chk is not None:
                    checked_elem = chk.find("w14:checked", NS)
                    is_checked = False
                    if checked_elem is not None:
                        c_val = checked_elem.attrib.get(f"{{{NS['w14']}}}val") or checked_elem.attrib.get("val")
                        is_checked = _is_truthy(c_val)
                    res.append("☑ " if is_checked else "☐ ", style="bold cyan" if is_checked else "dim white")

                sdt_content = child.find("w:sdtContent", NS)
                if sdt_content is not None:
                    res.append(self._extract_runs_text(sdt_content))

            elif tag == "footnoteReference":
                fn_id = child.attrib.get(f"{{{NS['w']}}}id") or child.attrib.get("id")
                if fn_id and fn_id in self.footnotes:
                    res.append(f"[{fn_id}]", style="cyan")

            elif tag == "endnoteReference":
                en_id = child.attrib.get(f"{{{NS['w']}}}id") or child.attrib.get("id")
                if en_id and en_id in self.endnotes:
                    res.append(f"[{en_id}]", style="cyan")

        return res

    def _parse_run(self, r_elem: ET.Element) -> Tuple[str, Optional[Style]]:
        """Parse a single <w:r> run and return (text, rich_style)."""
        rPr = r_elem.find("w:rPr", NS)

        bold = False
        italic = False
        underline = False
        strike = False
        color: Optional[str] = None
        bgcolor: Optional[str] = None
        is_code = False
        vert_align: Optional[str] = None

        if rPr is not None:
            # Bold
            b_elem = rPr.find("w:b", NS)
            if b_elem is not None and _is_truthy(b_elem.attrib.get(f"{{{NS['w']}}}val")):
                bold = True

            # Italic
            i_elem = rPr.find("w:i", NS)
            if i_elem is not None and _is_truthy(i_elem.attrib.get(f"{{{NS['w']}}}val")):
                italic = True

            # Underline
            u_elem = rPr.find("w:u", NS)
            if u_elem is not None:
                u_val = u_elem.attrib.get(f"{{{NS['w']}}}val", "single")
                if _is_truthy(u_val):
                    underline = True

            # Strike
            s_elem = rPr.find("w:strike", NS)
            if s_elem is None:
                s_elem = rPr.find("w:dstrike", NS)
            if s_elem is not None and _is_truthy(s_elem.attrib.get(f"{{{NS['w']}}}val")):
                strike = True

            # Color
            col_elem = rPr.find("w:color", NS)
            if col_elem is not None:
                c_val = col_elem.attrib.get(f"{{{NS['w']}}}val", "").strip()
                color = _parse_color(c_val)

            # Highlight
            hi_elem = rPr.find("w:highlight", NS)
            if hi_elem is not None:
                h_val = hi_elem.attrib.get(f"{{{NS['w']}}}val", "").strip().lower()
                if h_val and h_val != "none":
                    if h_val in ("yellow", "green", "cyan", "magenta", "blue", "red", "darkBlue", "darkCyan"):
                        bgcolor = "grey23" if h_val == "yellow" else "grey15"
                    else:
                        bgcolor = "grey23"

            # Monospace / Code Font
            font_elem = rPr.find("w:rFonts", NS)
            if font_elem is not None:
                for k in ("ascii", "hAnsi", "cs"):
                    f_name = font_elem.attrib.get(f"{{{NS['w']}}}{k}", "").strip().lower()
                    if f_name in MONOSPACE_FONTS:
                        is_code = True
                        break

            # Superscript / Subscript
            vert_elem = rPr.find("w:vertAlign", NS)
            if vert_elem is not None:
                vert_align = vert_elem.attrib.get(f"{{{NS['w']}}}val", "").strip().lower()

        # Collect text parts
        parts = []
        for child in r_elem:
            c_tag = _local_tag(child)
            if c_tag == "t":
                txt = child.text or ""
                if vert_align == "superscript":
                    txt = txt.translate(SUPERSCRIPT_MAP)
                elif vert_align == "subscript":
                    txt = txt.translate(SUBSCRIPT_MAP)
                parts.append(txt)
            elif c_tag == "sym":
                font = child.attrib.get(f"{{{NS['w']}}}font") or child.attrib.get("font") or ""
                char = child.attrib.get(f"{{{NS['w']}}}char") or child.attrib.get("char") or ""
                if "wingdings" in font.lower():
                    sym_map = {"F0FE": "☑", "F0A8": "☒", "F0A7": "☐", "F0E0": "✉", "F071": "✓"}
                    parts.append(sym_map.get(char.upper(), "•"))
                else:
                    try:
                        parts.append(chr(int(char, 16)))
                    except Exception:
                        parts.append("•")
            elif c_tag == "tab":
                parts.append("    ")
            elif c_tag in ("br", "cr"):
                parts.append("\n")
            elif c_tag == "drawing":
                # Inline image or shape marker
                parts.append(" [🖼 ] ")
            elif c_tag == "footnoteReference":
                fn_id = child.attrib.get(f"{{{NS['w']}}}id") or child.attrib.get("id")
                if fn_id and fn_id in self.footnotes:
                    parts.append(f"[{fn_id}]")
            elif c_tag == "endnoteReference":
                en_id = child.attrib.get(f"{{{NS['w']}}}id") or child.attrib.get("id")
                if en_id and en_id in self.endnotes:
                    parts.append(f"[{en_id}]")

        text = "".join(parts)
        if not text:
            return "", None

        # Build style
        style = Style(
            bold=bold,
            italic=italic,
            underline=underline,
            strike=strike,
            color=color,
            bgcolor=bgcolor,
        )

        if is_code:
            code_style = Style(color="#e0af68", bgcolor="grey15")
            style = style + code_style

        return text, style

    def _parse_paragraph(self, p_elem: ET.Element) -> Tuple[Optional[RenderableType], bool]:
        """
        Parses a <w:p> element.
        Returns (renderable, is_blank).
        """
        pPr = p_elem.find("w:pPr", NS)
        style_name = ""
        justify = "left"
        num_pr = None

        if pPr is not None:
            # Paragraph style
            p_style_elem = pPr.find("w:pStyle", NS)
            if p_style_elem is not None:
                style_name = p_style_elem.attrib.get(f"{{{NS['w']}}}val", "").lower()

            # Alignment: preserve center and right, but soften justified ("both" / "distribute")
            # to natural "left" alignment to prevent gaping whitespace holes in monospace terminals.
            jc_elem = pPr.find("w:jc", NS)
            if jc_elem is not None:
                jc_val = jc_elem.attrib.get(f"{{{NS['w']}}}val", "").lower()
                jc_map = {"center": "center", "right": "right", "both": "left", "distribute": "left"}
                justify = jc_map.get(jc_val, "left")

            # Numbering / Bullets
            num_pr = pPr.find("w:numPr", NS)

        # Extract runs
        p_text = self._extract_runs_text(p_elem)
        raw_text = p_text.plain

        # Check if empty
        if not raw_text.strip():
            # Check for horizontal rule in paragraph
            if pPr is not None and pPr.find(".//w:bottom", NS) is not None:
                return Rule(style="markdown.hr"), False
            return None, True

        # Heading detection
        if style_name in ("title", "documenttitle") or "title" in style_name:
            p_text.justify = "center" if justify == "left" else justify
            p_text.stylize("bold bright_white")
            group = Group(
                Text(""),
                p_text,
                Rule(style="dim cyan"),
                Text(""),
            )
            return group, False

        elif style_name in ("subtitle",):
            p_text.justify = "center" if justify == "left" else justify
            p_text.stylize("dim italic white")
            return p_text, False

        elif "heading 1" in style_name or style_name in ("heading1", "h1"):
            p_text.stylize("bold bright_white underline")
            p_text.justify = justify if justify != "left" else None
            return Group(Text(""), p_text, Text("")), False

        elif "heading 2" in style_name or style_name in ("heading2", "h2"):
            p_text.stylize("bold cyan")
            p_text.justify = justify if justify != "left" else None
            return Group(Text(""), p_text), False

        elif "heading 3" in style_name or style_name in ("heading3", "h3"):
            p_text.stylize("bold white")
            p_text.justify = justify if justify != "left" else None
            return Group(Text(""), p_text), False

        elif any(f"heading {i}" in style_name or style_name == f"heading{i}" for i in range(4, 7)):
            p_text.stylize("bold dim white")
            p_text.justify = justify if justify != "left" else None
            return p_text, False

        # Blockquote detection
        if "quote" in style_name or (pPr is not None and pPr.find("w:pBdr/w:left", NS) is not None):
            quote_text = p_text
            quote_text.stylize("dim italic white")
            panel = Panel(
                quote_text,
                box=box.SIMPLE,
                border_style="dim cyan",
                padding=(0, 1),
            )
            return panel, False

        # Numbering / Bullet list item
        if num_pr is not None and self.numbering is not None:
            ilvl_elem = num_pr.find("w:ilvl", NS)
            numid_elem = num_pr.find("w:numId", NS)
            try:
                ilvl = int(ilvl_elem.attrib.get(f"{{{NS['w']}}}val", "0")) if ilvl_elem is not None else 0
            except ValueError:
                ilvl = 0
            num_id = numid_elem.attrib.get(f"{{{NS['w']}}}val", "1") if numid_elem is not None else "1"

            prefix, item_type = self.numbering.get_prefix(num_id, ilvl)
            item_style = "markdown.item.bullet" if item_type == "bullet" else "markdown.item.number"
            item_text = Text(prefix, style=item_style) + p_text
            return item_text, False

        # Normal paragraph
        p_text.justify = justify if justify != "left" else None
        return p_text, False

    def _is_table_borderless(self, tbl_elem: ET.Element) -> bool:
        """Determines whether a table is borderless (used for layout or signature blocks)."""
        tblPr = tbl_elem.find("w:tblPr", NS)
        if tblPr is not None:
            tblBorders = tblPr.find("w:tblBorders", NS)
            if tblBorders is not None:
                # Check inside borders
                inside_h = tblBorders.find("w:insideH", NS)
                inside_v = tblBorders.find("w:insideV", NS)
                left = tblBorders.find("w:left", NS)
                right = tblBorders.find("w:right", NS)

                h_none = inside_h is not None and not _is_truthy(inside_h.attrib.get(f"{{{NS['w']}}}val"))
                v_none = inside_v is not None and not _is_truthy(inside_v.attrib.get(f"{{{NS['w']}}}val"))
                l_none = left is not None and not _is_truthy(left.attrib.get(f"{{{NS['w']}}}val"))
                r_none = right is not None and not _is_truthy(right.attrib.get(f"{{{NS['w']}}}val"))

                if h_none and v_none and l_none and r_none:
                    return True

        # Check if every cell explicitly turns off borders
        all_cells_nil = True
        cell_count = 0
        for cell in tbl_elem.findall(".//w:tc", NS):
            cell_count += 1
            tcBorders = cell.find("w:tcPr/w:tcBorders", NS)
            if tcBorders is None:
                all_cells_nil = False
                break
            for b_name in ("top", "bottom", "left", "right"):
                b = tcBorders.find(f"w:{b_name}", NS)
                if b is not None and _is_truthy(b.attrib.get(f"{{{NS['w']}}}val")):
                    all_cells_nil = False
                    break
            if not all_cells_nil:
                break

        if cell_count > 0 and all_cells_nil:
            return True

        return False

    def _parse_table(self, tbl_elem: ET.Element) -> Optional[RenderableType]:
        """
        Parses a <w:tbl> element into a Rich Table or unnested paragraphs.
        Supports:
          - Proportional column widths from <w:tblGrid>
          - Horizontal cell spanning (<w:gridSpan>)
          - Cell background shading (<w:shd>)
          - Explicit table header rows (<w:tblHeader>)
          - Borderless layout grids vs bordered data tables
        """
        rows = tbl_elem.findall("w:tr", NS)
        if not rows:
            return None

        # Extract column widths from <w:tblGrid> if present
        grid_col_widths: List[int] = []
        tblGrid = tbl_elem.find("w:tblGrid", NS)
        if tblGrid is not None:
            for gcol in tblGrid.findall("w:gridCol", NS):
                try:
                    w_val = int(gcol.attrib.get(f"{{{NS['w']}}}w", "0"))
                    grid_col_widths.append(w_val)
                except ValueError:
                    grid_col_widths.append(0)

        # Detect total columns in table (taking gridSpan into account)
        max_cols = 0
        for row in rows:
            r_cols = 0
            for cell in row.findall("w:tc", NS):
                gspan = 1
                tcPr = cell.find("w:tcPr", NS)
                if tcPr is not None:
                    gspan_elem = tcPr.find("w:gridSpan", NS)
                    if gspan_elem is not None:
                        try:
                            gspan = max(1, int(gspan_elem.attrib.get(f"{{{NS['w']}}}val", "1")))
                        except ValueError:
                            gspan = 1
                r_cols += gspan
            if r_cols > max_cols:
                max_cols = r_cols

        col_count = max(len(grid_col_widths), max_cols)
        if col_count == 0:
            return None

        is_borderless = self._is_table_borderless(tbl_elem)

        # Single-column table with no borders: unnest as direct paragraphs!
        if col_count == 1 and is_borderless:
            elements: List[RenderableType] = []
            for row in rows:
                for cell in row.findall("w:tc", NS):
                    for p in cell.findall("w:p", NS):
                        rend, is_blank = self._parse_paragraph(p)
                        if rend is not None:
                            elements.append(rend)
                            elements.append(Text(""))
            return Group(*elements) if elements else None

        # Parse rows, handling gridSpan and cell shading
        table_data: List[List[Text]] = []
        table_shading: List[List[Optional[str]]] = []
        raw_headers: List[str] = []
        raw_rows: List[List[str]] = []
        has_tbl_header = False

        for r_idx, row in enumerate(rows):
            # Check for header row specification
            trPr = row.find("w:trPr", NS)
            is_header_row = False
            if trPr is not None and trPr.find("w:tblHeader", NS) is not None:
                is_header_row = True
                has_tbl_header = True

            row_texts: List[Text] = []
            row_shd: List[Optional[str]] = []
            row_raw: List[str] = []

            for cell in row.findall("w:tc", NS):
                tcPr = cell.find("w:tcPr", NS)
                gspan = 1
                cell_bg: Optional[str] = None
                if tcPr is not None:
                    gspan_elem = tcPr.find("w:gridSpan", NS)
                    if gspan_elem is not None:
                        try:
                            gspan = max(1, int(gspan_elem.attrib.get(f"{{{NS['w']}}}val", "1")))
                        except ValueError:
                            gspan = 1
                    cell_bg = _parse_shading(tcPr.find("w:shd", NS))

                cell_p_list: List[Text] = []
                for p in cell.findall("w:p", NS):
                    p_text = self._extract_runs_text(p)
                    if p_text.plain.strip():
                        cell_p_list.append(p_text)
                    elif cell_p_list:
                        cell_p_list.append(Text(""))

                combined = Text("\n").join(cell_p_list) if cell_p_list else Text("")
                if cell_bg:
                    combined.stylize(Style(bgcolor=cell_bg))

                # Place into first column of span
                row_texts.append(combined)
                row_shd.append(cell_bg)
                row_raw.append(combined.plain)

                # For spanned columns, fill empty placeholder cells
                for _ in range(gspan - 1):
                    empty_t = Text("")
                    if cell_bg:
                        empty_t.stylize(Style(bgcolor=cell_bg))
                    row_texts.append(empty_t)
                    row_shd.append(cell_bg)
                    row_raw.append("")

            # Pad row to col_count
            while len(row_texts) < col_count:
                row_texts.append(Text(""))
                row_shd.append(None)
                row_raw.append("")

            table_data.append(row_texts)
            table_shading.append(row_shd)

            if r_idx == 0 or is_header_row:
                if not raw_headers:
                    raw_headers = row_raw
                else:
                    raw_rows.append(row_raw)
            else:
                raw_rows.append(row_raw)

        if is_borderless:
            # Layout table (e.g. side-by-side signature & party metadata blocks)
            grid = Table.grid(padding=(0, 2), expand=True)
            for _ in range(col_count):
                grid.add_column()

            for row_texts in table_data:
                grid.add_row(*row_texts)

            return Group(Text(""), grid, Text(""))

        # Data table with borders
        box_style = BOX_STYLES.get(self.box_style, BOOKTABS)
        tbl = Table(
            box=box_style,
            show_header=True,
            show_lines=self.show_lines,
            border_style="markdown.table.border",
            header_style="markdown.table.header",
            padding=(0, 1),
            expand=False,
        )

        # Smart column width allocation
        # If tblGrid provided dxa widths for all columns, use proportional distribution
        col_widths: Optional[List[int]] = None
        if len(grid_col_widths) == col_count and sum(grid_col_widths) > 0:
            total_dxa = sum(grid_col_widths)
            # Reserve cell padding
            usable_w = max(self.doc_width - (col_count * 2 + 1), col_count * 4)
            prop_widths = [max(4, int(usable_w * (w / total_dxa))) for w in grid_col_widths]
            # Ensure sum doesn't drastically exceed doc_width
            if sum(prop_widths) <= self.doc_width:
                col_widths = prop_widths

        if not col_widths:
            col_widths = calculate_smart_column_widths(
                headers=raw_headers if raw_headers else [""] * col_count,
                rows=raw_rows,
                available_width=self.doc_width,
            )

        for c_idx in range(col_count):
            w = col_widths[c_idx] if c_idx < len(col_widths) else None
            h_text = table_data[0][c_idx] if table_data and c_idx < len(table_data[0]) else Text("")
            tbl.add_column(header=h_text, width=w)

        # Add data rows (from row 1 onwards)
        for row_texts in table_data[1:]:
            tbl.add_row(*row_texts)

        return Group(Text(""), tbl, Text(""))

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Render all document elements cleanly onto the console."""
        last_was_blank = False

        for child in self.body_elements:
            tag = _local_tag(child)

            if tag == "p":
                rend, is_blank = self._parse_paragraph(child)
                if is_blank:
                    if not last_was_blank:
                        yield Segment.line()
                        last_was_blank = True
                else:
                    last_was_blank = False
                    if rend is not None:
                        yield from console.render(rend, options)

            elif tag == "tbl":
                last_was_blank = False
                tbl_rend = self._parse_table(child)
                if tbl_rend is not None:
                    yield from console.render(tbl_rend, options)

            elif tag == "sdt":
                # Structured document tag at root level
                content = child.find("w:sdtContent", NS)
                if content is not None:
                    for sub_child in content:
                        sub_tag = _local_tag(sub_child)
                        if sub_tag == "p":
                            rend, is_blank = self._parse_paragraph(sub_child)
                            if is_blank:
                                if not last_was_blank:
                                    yield Segment.line()
                                    last_was_blank = True
                            else:
                                last_was_blank = False
                                if rend is not None:
                                    yield from console.render(rend, options)
                        elif sub_tag == "tbl":
                            last_was_blank = False
                            tbl_rend = self._parse_table(sub_child)
                            if tbl_rend is not None:
                                yield from console.render(tbl_rend, options)

        # Render footnotes if present
        if self.footnotes:
            yield Segment.line()
            yield from console.render(Rule(title="Footnotes", style="dim cyan"), options)
            for fn_id, fn_text in sorted(self.footnotes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else str(x[0])):
                t = Text()
                t.append(f"[{fn_id}] ", style="cyan")
                t.append(fn_text, style="dim white")
                yield from console.render(t, options)

        # Render endnotes if present
        if self.endnotes:
            yield Segment.line()
            yield from console.render(Rule(title="Endnotes", style="dim cyan"), options)
            for en_id, en_text in sorted(self.endnotes.items(), key=lambda x: int(x[0]) if x[0].isdigit() else str(x[0])):
                t = Text()
                t.append(f"[{en_id}] ", style="cyan")
                t.append(en_text, style="dim white")
                yield from console.render(t, options)
