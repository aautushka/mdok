import io
import os
from pathlib import Path
import zipfile
import pytest
from rich.console import Console

from mdok.docx import DocxDocument, NumberingTracker
from mdok.canvas import CanvasConfig, calculate_dimensions, DocumentCanvas
from mdok.theme import DEFAULT_THEME
from mdok.cli import main

SAMPLE_DOCX = os.path.expanduser("~/Downloads/Termination_agreement_template.docx")


def create_in_memory_docx() -> io.BytesIO:
    """Creates a full valid docx archive in memory with formatting, lists, tables, and links."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        # [Content_Types].xml
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
                <Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>
            </Types>""",
        )

        # _rels/.rels
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )

        # word/_rels/document.xml.rels
        z.writestr(
            "word/_rels/document.xml.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>
                <Relationship Id="rIdLink1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://github.com/aautushka/mdok" TargetMode="External"/>
            </Relationships>""",
        )

        # word/numbering.xml
        z.writestr(
            "word/numbering.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:abstractNum w:abstractNumId="0">
                    <w:lvl w:ilvl="0">
                        <w:start w:val="1"/>
                        <w:numFmt w:val="decimal"/>
                        <w:lvlText w:val="%1."/>
                    </w:lvl>
                </w:abstractNum>
                <w:abstractNum w:abstractNumId="1">
                    <w:lvl w:ilvl="0">
                        <w:start w:val="1"/>
                        <w:numFmt w:val="bullet"/>
                        <w:lvlText w:val="•"/>
                    </w:lvl>
                </w:abstractNum>
                <w:num w:numId="10">
                    <w:abstractNumId w:val="0"/>
                </w:num>
                <w:num w:numId="20">
                    <w:abstractNumId w:val="1"/>
                </w:num>
            </w:numbering>""",
        )

        # word/document.xml
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                        xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
                <w:body>
                    <!-- Title -->
                    <w:p>
                        <w:pPr><w:pStyle w:val="Title"/></w:pPr>
                        <w:r><w:t>Document Title</w:t></w:r>
                    </w:p>
                    
                    <!-- Headings -->
                    <w:p>
                        <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
                        <w:r><w:t>Heading 1 Section</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr><w:pStyle w:val="Heading2"/></w:pPr>
                        <w:r><w:t>Heading 2 Subsection</w:t></w:r>
                    </w:p>

                    <!-- Formatted text runs -->
                    <w:p>
                        <w:r><w:rPr><w:b/></w:rPr><w:t>Bold Text </w:t></w:r>
                        <w:r><w:rPr><w:i/></w:rPr><w:t>Italic Text </w:t></w:r>
                        <w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>Underline Text </w:t></w:r>
                        <w:r><w:rPr><w:strike/></w:rPr><w:t>Strikethrough Text </w:t></w:r>
                        <w:r><w:rPr><w:rFonts w:ascii="Consolas"/></w:rPr><w:t>code_snippet()</w:t></w:r>
                        <w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr><w:t>2</w:t></w:r>
                    </w:p>

                    <!-- Hyperlink -->
                    <w:p>
                        <w:r><w:t>Visit our </w:t></w:r>
                        <w:hyperlink r:id="rIdLink1">
                            <w:r><w:t>GitHub Repo</w:t></w:r>
                        </w:hyperlink>
                    </w:p>

                    <!-- Numbered list items -->
                    <w:p>
                        <w:pPr>
                            <w:numPr><w:ilvl w:val="0"/><w:numId w:val="10"/></w:numPr>
                        </w:pPr>
                        <w:r><w:t>First numbered step</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr>
                            <w:numPr><w:ilvl w:val="0"/><w:numId w:val="10"/></w:numPr>
                        </w:pPr>
                        <w:r><w:t>Second numbered step</w:t></w:r>
                    </w:p>

                    <!-- Bullet list items -->
                    <w:p>
                        <w:pPr>
                            <w:numPr><w:ilvl w:val="0"/><w:numId w:val="20"/></w:numPr>
                        </w:pPr>
                        <w:r><w:t>Bullet point alpha</w:t></w:r>
                    </w:p>

                    <!-- Borderless 2-column layout table -->
                    <w:tbl>
                        <w:tblPr>
                            <w:tblBorders>
                                <w:left w:val="none"/>
                                <w:right w:val="none"/>
                                <w:insideH w:val="none"/>
                                <w:insideV w:val="none"/>
                            </w:tblBorders>
                        </w:tblPr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Left Column</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Right Column</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Value A</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Value B</w:t></w:r></w:p></w:tc>
                        </w:tr>
                    </w:tbl>

                    <!-- Bordered data table -->
                    <w:tbl>
                        <w:tblPr>
                            <w:tblBorders>
                                <w:top w:val="single"/>
                                <w:bottom w:val="single"/>
                                <w:insideH w:val="single"/>
                            </w:tblBorders>
                        </w:tblPr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Header 1</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Header 2</w:t></w:r></w:p></w:tc>
                        </w:tr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Cell 1</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>Cell 2</w:t></w:r></w:p></w:tc>
                        </w:tr>
                    </w:tbl>

                    <!-- Single-column borderless table (should unnest as paragraphs) -->
                    <w:tbl>
                        <w:tblPr>
                            <w:tblBorders>
                                <w:left w:val="none"/>
                                <w:right w:val="none"/>
                                <w:insideH w:val="none"/>
                                <w:insideV w:val="none"/>
                            </w:tblBorders>
                        </w:tblPr>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>Unnested paragraph text</w:t></w:r></w:p></w:tc>
                        </w:tr>
                    </w:tbl>
                </w:body>
            </w:document>""",
        )

    buf.seek(0)
    return buf


def test_docx_document_in_memory():
    docx_bytes = create_in_memory_docx().getvalue()
    doc = DocxDocument(docx_bytes)
    
    console = Console(theme=DEFAULT_THEME, width=100)
    lines = list(console.render_lines(doc, console.options))
    full_text = "\n".join("".join(seg.text for seg in line) for line in lines)

    # Verify content parsed properly
    assert "Document Title" in full_text
    assert "Heading 1 Section" in full_text
    assert "Heading 2 Subsection" in full_text
    assert "Bold Text" in full_text
    assert "Italic Text" in full_text
    assert "Underline Text" in full_text
    assert "code_snippet()" in full_text
    assert "GitHub Repo" in full_text
    assert "1. First numbered step" in full_text
    assert "2. Second numbered step" in full_text
    assert "• Bullet point alpha" in full_text
    assert "Left Column" in full_text and "Right Column" in full_text
    assert "Header 1" in full_text and "Header 2" in full_text
    assert "Unnested paragraph text" in full_text


def test_docx_sample_file():
    if not os.path.exists(SAMPLE_DOCX):
        pytest.skip(f"Sample file not found at {SAMPLE_DOCX}")

    doc = DocxDocument(SAMPLE_DOCX)
    console = Console(theme=DEFAULT_THEME, width=90)
    lines = list(console.render_lines(doc, console.options))
    full_text = "\n".join("".join(seg.text for seg in line) for line in lines)

    assert "TERMINATION AGREEMENT" in full_text
    assert "date: 31 July 2026" in full_text
    assert "“Company”:" in full_text
    assert "Steve Jobs" in full_text
    assert "“Contractor”:" in full_text
    assert "Daniel Foster" in full_text
    assert "WHEREAS" in full_text


def test_docx_canvas_centering():
    docx_bytes = create_in_memory_docx().getvalue()
    doc = DocxDocument(docx_bytes)
    
    config = CanvasConfig(max_width=60, center=True)
    doc_w, left_m = calculate_dimensions(100, config)
    canvas = DocumentCanvas(doc, doc_width=doc_w, left_margin=left_m)

    console = Console(theme=DEFAULT_THEME, width=100)
    lines = list(console.render_lines(canvas, console.options))
    rendered = ["".join(seg.text for seg in line) for line in lines]
    
    # Check that non-empty lines start with left margin indentation
    for line in rendered:
        if line.strip():
            assert line.startswith(" " * left_m)


def test_real_world_docx_files():
    import glob
    files = glob.glob(os.path.expanduser("~/Downloads/*.docx"))
    console = Console(theme=DEFAULT_THEME, width=90)
    for f in files:
        try:
            doc = DocxDocument(f)
            # Render lines to make sure no exceptions during rich console rendering
            lines = list(console.render_lines(doc, console.options))
            assert len(lines) > 0
        except Exception as e:
            pytest.fail(f"Failed rendering {f}: {e}")


def test_docx_advanced_table_features():
    """Test tblGrid proportional widths, gridSpan, cell shading, and repeated headers."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
            </Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <!-- Advanced Table with gridCol, gridSpan, shading, tblHeader -->
                    <w:tbl>
                        <w:tblPr>
                            <w:tblBorders>
                                <w:top w:val="single"/>
                                <w:bottom w:val="single"/>
                                <w:insideH w:val="single"/>
                            </w:tblBorders>
                        </w:tblPr>
                        <w:tblGrid>
                            <w:gridCol w:w="2000"/>
                            <w:gridCol w:w="4000"/>
                            <w:gridCol w:w="4000"/>
                        </w:tblGrid>
                        <!-- Header row with tblHeader and shading -->
                        <w:tr>
                            <w:trPr><w:tblHeader/></w:trPr>
                            <w:tc>
                                <w:tcPr><w:shd w:fill="2B303C"/></w:tcPr>
                                <w:p><w:r><w:t>Col 1 Header</w:t></w:r></w:p>
                            </w:tc>
                            <w:tc>
                                <w:tcPr><w:shd w:fill="2B303C"/></w:tcPr>
                                <w:p><w:r><w:t>Col 2 Header</w:t></w:r></w:p>
                            </w:tc>
                            <w:tc>
                                <w:tcPr><w:shd w:fill="2B303C"/></w:tcPr>
                                <w:p><w:r><w:t>Col 3 Header</w:t></w:r></w:p>
                            </w:tc>
                        </w:tr>
                        <!-- Data row with gridSpan=2 across cols 2 & 3 -->
                        <w:tr>
                            <w:tc>
                                <w:p><w:r><w:t>Item A</w:t></w:r></w:p>
                            </w:tc>
                            <w:tc>
                                <w:tcPr><w:gridSpan w:val="2"/><w:shd w:fill="3C4048"/></w:tcPr>
                                <w:p><w:r><w:t>Merged description across two columns</w:t></w:r></w:p>
                            </w:tc>
                        </w:tr>
                    </w:tbl>
                </w:body>
            </w:document>""",
        )

    buf.seek(0)
    doc = DocxDocument(buf.getvalue(), doc_width=80)
    console = Console(theme=DEFAULT_THEME, width=90)
    lines = list(console.render_lines(doc, console.options))
    full_text = "\n".join("".join(seg.text for seg in line) for line in lines)

    assert "Col 1 Header" in full_text
    assert "Col 2 Header" in full_text
    assert "Col 3 Header" in full_text
    assert "Item A" in full_text
    assert "Merged description" in full_text
    assert "columns" in full_text


def test_docx_checkboxes_and_footnotes():
    """Test content control checkboxes (w14:checkbox, wingdings symbols) and footnotes/endnotes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
                <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
            </Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )
        z.writestr(
            "word/footnotes.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:footnote w:type="separator" w:id="-1"/>
                <w:footnote w:id="1">
                    <w:p><w:r><w:t>Footnote reference explanation text</w:t></w:r></w:p>
                </w:footnote>
            </w:footnotes>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
                        xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml">
                <w:body>
                    <!-- Checked checkbox -->
                    <w:p>
                        <w:sdt>
                            <w:sdtPr>
                                <w14:checkbox>
                                    <w14:checked w14:val="1"/>
                                </w14:checkbox>
                            </w:sdtPr>
                            <w:sdtContent>
                                <w:r><w:t>Accept terms and conditions</w:t></w:r>
                            </w:sdtContent>
                        </w:sdt>
                    </w:p>
                    <!-- Unchecked checkbox -->
                    <w:p>
                        <w:sdt>
                            <w:sdtPr>
                                <w14:checkbox>
                                    <w14:checked w14:val="0"/>
                                </w14:checkbox>
                            </w:sdtPr>
                            <w:sdtContent>
                                <w:r><w:t>Optional newsletter subscription</w:t></w:r>
                            </w:sdtContent>
                        </w:sdt>
                    </w:p>
                    <!-- Wingdings symbol checkbox -->
                    <w:p>
                        <w:r>
                            <w:sym w:font="Wingdings" w:char="F0FE"/>
                        </w:r>
                        <w:r><w:t> Signed by party</w:t></w:r>
                    </w:p>
                    <!-- Paragraph with footnote reference -->
                    <w:p>
                        <w:r><w:t>Special legal clause</w:t></w:r>
                        <w:footnoteReference w:id="1"/>
                    </w:p>
                </w:body>
            </w:document>""",
        )

    buf.seek(0)
    doc = DocxDocument(buf.getvalue(), doc_width=80)
    console = Console(theme=DEFAULT_THEME, width=90)
    lines = list(console.render_lines(doc, console.options))
    full_text = "\n".join("".join(seg.text for seg in line) for line in lines)

    # Checkbox rendering
    assert "☑" in full_text or "[x]" in full_text
    assert "Accept terms and conditions" in full_text
    assert "☐" in full_text or "[ ]" in full_text
    assert "Optional newsletter subscription" in full_text
    assert "Signed by party" in full_text

    # Footnote rendering
    assert "[1]" in full_text
    assert "Footnotes" in full_text
    assert "Footnote reference explanation text" in full_text


def test_showcase_docx_file():
    """Verify that examples/showcase.docx renders cleanly and comprehensively."""
    showcase_path = Path(__file__).parent.parent / "examples" / "showcase.docx"
    assert showcase_path.exists(), "examples/showcase.docx must exist"

    doc = DocxDocument(showcase_path, doc_width=80)
    console = Console(theme=DEFAULT_THEME, width=90)
    lines = list(console.render_lines(doc, console.options))
    full_text = "\n".join("".join(seg.text for seg in line) for line in lines)

    assert "mdok Word Document Engine Showcase" in full_text
    assert "Typography & Inline Styling" in full_text
    assert "Lists & Interactive Checkboxes" in full_text
    assert "☑" in full_text
    assert "☐" in full_text
    assert "Blockquotes & Notes" in full_text
    assert "Data Tables with Widths, Shading & Merged Cells" in full_text
    assert "Borderless Two-Column Layout Blocks" in full_text
    assert "Authorized Signatory" in full_text
    assert "Footnotes" in full_text
    assert "Endnotes" in full_text


def test_docx_deduce_width_geometry():
    """Verify width deduction based on OpenXML page size, margins, styles, and tables."""
    # 1. Standard US Letter with 1" margins (9360 dxa printable, default 11pt font)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
            </Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <w:p><w:r><w:t>Standard document</w:t></w:r></w:p>
                    <w:sectPr>
                        <w:pgSz w:w="12240" w:h="15840"/>
                        <w:pgMar w:left="1440" w:right="1440"/>
                    </w:sectPr>
                </w:body>
            </w:document>""",
        )
    buf.seek(0)
    doc_letter = DocxDocument(buf.getvalue())
    assert 80 <= doc_letter.doc_width <= 86

    # 2. Landscape Document
    buf_land = io.BytesIO()
    with zipfile.ZipFile(buf_land, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
            </Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <w:p><w:r><w:t>Landscape document</w:t></w:r></w:p>
                    <w:sectPr>
                        <w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/>
                        <w:pgMar w:left="1440" w:right="1440"/>
                    </w:sectPr>
                </w:body>
            </w:document>""",
        )
    buf_land.seek(0)
    doc_land = DocxDocument(buf_land.getvalue())
    assert doc_land.doc_width >= 105

    # 3. Document with wide 6-column table requiring horizontal expansion
    buf_tbl = io.BytesIO()
    with zipfile.ZipFile(buf_tbl, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
            </Types>""",
        )
        z.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
                <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
            </Relationships>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <w:tbl>
                        <w:tblGrid>
                            <w:gridCol w:w="1800"/>
                            <w:gridCol w:w="1800"/>
                            <w:gridCol w:w="1800"/>
                            <w:gridCol w:w="1800"/>
                            <w:gridCol w:w="1800"/>
                            <w:gridCol w:w="1800"/>
                        </w:tblGrid>
                        <w:tr>
                            <w:tc><w:p><w:r><w:t>C1</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>C2</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>C3</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>C4</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>C5</w:t></w:r></w:p></w:tc>
                            <w:tc><w:p><w:r><w:t>C6</w:t></w:r></w:p></w:tc>
                        </w:tr>
                    </w:tbl>
                </w:body>
            </w:document>""",
        )
    buf_tbl.seek(0)
    doc_tbl = DocxDocument(buf_tbl.getvalue())
    assert doc_tbl.doc_width >= 94

    # 4. Terminal width bounding (narrow terminal limits maximum width)
    doc_bounded = DocxDocument(buf_tbl.getvalue(), term_width=70)
    assert doc_bounded.doc_width <= 68


def test_cli_docx_disregards_width_option(capsys):
    """Verify that mdok CLI disregards -w/--width for DOCX files and deduces document width."""
    showcase_path = Path(__file__).parent.parent / "examples" / "showcase.docx"
    assert showcase_path.exists()

    # Pass -w 35 on CLI -- for markdown this would crush text to 35 cols.
    # For docx, -w is disregarded and natural width (~80-90 cols) is preserved.
    ret = main([str(showcase_path), "-w", "35", "--no-pager"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "mdok Word Document Engine Showcase" in captured.out
    assert "Typography & Inline Styling" in captured.out


def test_docx_text_alignment_justification_softening():
    """Verify that justified text ('both'/'distribute') is softened to 'left' while center/right are kept."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
                <Default Extension="xml" ContentType="application/xml"/>
                <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
            </Types>""",
        )
        z.writestr(
            "word/document.xml",
            """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
            <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                <w:body>
                    <w:p>
                        <w:pPr><w:jc w:val="both"/></w:pPr>
                        <w:r><w:t>Justified text softened to left</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr><w:jc w:val="distribute"/></w:pPr>
                        <w:r><w:t>Distribute text softened to left</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr><w:jc w:val="center"/></w:pPr>
                        <w:r><w:t>Centered heading</w:t></w:r>
                    </w:p>
                    <w:p>
                        <w:pPr><w:jc w:val="right"/></w:pPr>
                        <w:r><w:t>Right aligned date</w:t></w:r>
                    </w:p>
                </w:body>
            </w:document>""",
        )
    buf.seek(0)
    doc = DocxDocument(buf.getvalue())
    elements = [doc._parse_paragraph(p)[0] for p in doc.body_elements]
    assert len(elements) == 4
    # both -> natural left (None to avoid trailing whitespace padding)
    assert elements[0].justify is None
    # distribute -> natural left (None to avoid trailing whitespace padding)
    assert elements[1].justify is None
    # center -> center
    assert elements[2].justify == "center"
    # right -> right
    assert elements[3].justify == "right"
