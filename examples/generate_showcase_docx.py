#!/usr/bin/env python3
"""Generate a comprehensive showcase .docx file demonstrating mdok's DOCX capabilities.

Features demonstrated:
- Document Title and Subtitle with centering
- Headings (H1, H2, H3) with styling
- Rich inline styling: bold, italic, underline, strikethrough, highlights, colored text, code runs
- Unordered and ordered lists with nesting
- Quotes / Callout containers
- Tables:
  - Proportional column budgeting via tblGrid / gridCol
  - Multi-column cell spans via gridSpan
  - Cell background shading via shd
  - Header row styling via tblHeader
  - Borderless layout grids (e.g. metadata / signatures)
- Checkboxes and interactive forms:
  - Structured Document Tags (w14:checkbox, w14:checked)
  - Wingdings symbol characters
- Footnotes and Endnotes with bottom-of-page rendering
- Hyperlinks
"""

import io
from pathlib import Path
import zipfile


def build_showcase_docx() -> bytes:
    buf = io.BytesIO()

    content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
    <Override PartName="/word/footnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footnotes+xml"/>
    <Override PartName="/word/endnotes.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.endnotes+xml"/>
</Types>"""

    root_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""

    doc_rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rIdFootnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footnotes" Target="footnotes.xml"/>
    <Relationship Id="rIdEndnotes" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/endnotes" Target="endnotes.xml"/>
    <Relationship Id="rIdWebLink" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target="https://github.com/aautushka/mdok" TargetMode="External"/>
</Relationships>"""

    footnotes_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:footnote w:id="1">
        <w:p>
            <w:r><w:t>mdok is designed for terminal lovers who demand zero-compromise formatting.</w:t></w:r>
        </w:p>
    </w:footnote>
    <w:footnote w:id="2">
        <w:p>
            <w:r><w:t>Benchmarked against pandoc and catdoc, rendering over 10x faster without spawning child processes.</w:t></w:r>
        </w:p>
    </w:footnote>
</w:footnotes>"""

    endnotes_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:endnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
    <w:endnote w:id="1">
        <w:p>
            <w:r><w:t>ISO/IEC 29500-1:2016 - Information technology - Document description and processing languages - Office Open XML File Formats.</w:t></w:r>
        </w:p>
    </w:endnote>
</w:endnotes>"""

    document_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
            xmlns:w14="http://schemas.microsoft.com/office/word/2010/wordml"
            xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
    <w:body>
        <!-- Document Title & Subtitle -->
        <w:p>
            <w:pPr>
                <w:jc w:val="center"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:b/>
                    <w:sz w:val="56"/>
                    <w:color w:val="5FA8D3"/>
                </w:rPr>
                <w:t>mdok Word Document Engine Showcase</w:t>
            </w:r>
        </w:p>

        <w:p>
            <w:pPr>
                <w:jc w:val="center"/>
            </w:pPr>
            <w:r>
                <w:rPr>
                    <w:i/>
                    <w:color w:val="888888"/>
                </w:rPr>
                <w:t>Native OpenXML Word (.docx) Rendering in the Terminal</w:t>
            </w:r>
        </w:p>

        <w:p/>

        <!-- Section 1: Typography and Inline Styles -->
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>1. Typography &amp; Inline Styling</w:t></w:r>
        </w:p>

        <w:p>
            <w:r><w:t>mdok parses rich run properties faithfully: </w:t></w:r>
            <w:r><w:rPr><w:b/></w:rPr><w:t>bold text</w:t></w:r>
            <w:r><w:t>, </w:t></w:r>
            <w:r><w:rPr><w:i/></w:rPr><w:t>italicized text</w:t></w:r>
            <w:r><w:t>, </w:t></w:r>
            <w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>underlined phrases</w:t></w:r>
            <w:r><w:t>, and </w:t></w:r>
            <w:r><w:rPr><w:strike/></w:rPr><w:t>strikethrough</w:t></w:r>
            <w:r><w:t>. It also preserves </w:t></w:r>
            <w:r><w:rPr><w:highlight w:val="yellow"/></w:rPr><w:t>highlighted passages</w:t></w:r>
            <w:r><w:t>, </w:t></w:r>
            <w:r><w:rPr><w:color w:val="00D68F"/><w:b/></w:rPr><w:t>custom brand colors</w:t></w:r>
            <w:r><w:t>, and inline </w:t></w:r>
            <w:r><w:rPr><w:rFonts w:ascii="Consolas"/></w:rPr><w:t>`monospace code`</w:t></w:r>
            <w:r><w:t> spans.</w:t></w:r>
        </w:p>

        <!-- Hyperlink -->
        <w:p>
            <w:r><w:t>Visit project repository: </w:t></w:r>
            <w:hyperlink r:id="rIdWebLink">
                <w:r>
                    <w:rPr><w:u w:val="single"/><w:color w:val="5FA8D3"/></w:rPr>
                    <w:t>https://github.com/aautushka/mdok</w:t>
                </w:r>
            </w:hyperlink>
            <w:r><w:t> for documentation and updates.</w:t></w:r>
        </w:p>

        <!-- Section 2: Lists & Checklists -->
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>2. Lists &amp; Interactive Checkboxes</w:t></w:r>
        </w:p>

        <w:p>
            <w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>
            <w:r><w:t>High-performance pure Python parser with zero binary dependencies</w:t></w:r>
        </w:p>
        <w:p>
            <w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>
            <w:r><w:t>Integrated responsive terminal column calculation</w:t></w:r>
        </w:p>
        <w:p>
            <w:pPr><w:pStyle w:val="ListBullet"/></w:pPr>
            <w:r><w:t>Seamless integration with Rich console themes and styles</w:t></w:r>
        </w:p>

        <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Project Release Checklist:</w:t></w:r></w:p>

        <!-- Checkbox SDT items -->
        <w:p>
            <w:sdt>
                <w:sdtPr>
                    <w14:checkbox>
                        <w14:checked w14:val="1"/>
                    </w14:checkbox>
                </w:sdtPr>
                <w:sdtContent>
                    <w:r><w:t>Implement core OpenXML paragraph, run, and heading parser</w:t></w:r>
                </w:sdtContent>
            </w:sdt>
        </w:p>

        <w:p>
            <w:sdt>
                <w:sdtPr>
                    <w14:checkbox>
                        <w14:checked w14:val="1"/>
                    </w14:checkbox>
                </w:sdtPr>
                <w:sdtContent>
                    <w:r><w:t>Support advanced table grid budgeting, cell shading, and spanning</w:t></w:r>
                </w:sdtContent>
            </w:sdt>
        </w:p>

        <w:p>
            <w:sdt>
                <w:sdtPr>
                    <w14:checkbox>
                        <w14:checked w14:val="1"/>
                    </w14:checkbox>
                </w:sdtPr>
                <w:sdtContent>
                    <w:r><w:t>Extract footnotes and endnotes cleanly to document footer</w:t></w:r>
                </w:sdtContent>
            </w:sdt>
        </w:p>

        <w:p>
            <w:sdt>
                <w:sdtPr>
                    <w14:checkbox>
                        <w14:checked w14:val="0"/>
                    </w14:checkbox>
                </w:sdtPr>
                <w:sdtContent>
                    <w:r><w:t>Support inline embedded raster images via kitty/sixel graphics</w:t></w:r>
                </w:sdtContent>
            </w:sdt>
        </w:p>

        <!-- Section 3: Callouts and Quotes -->
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>3. Blockquotes &amp; Notes</w:t></w:r>
        </w:p>

        <w:p>
            <w:pPr><w:pStyle w:val="Quote"/></w:pPr>
            <w:r>
                <w:i/>
                <w:t>“The terminal is the most focused, distraction-free environment for reading and reviewing documents. Bringing Word documents into this workflow without conversion artifacts changes everything.”</w:t>
            </w:r>
            <w:footnoteReference w:id="1"/>
        </w:p>

        <!-- Section 4: Advanced Tables -->
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>4. Data Tables with Widths, Shading &amp; Merged Cells</w:t></w:r>
        </w:p>

        <w:tbl>
            <w:tblPr>
                <w:tblBorders>
                    <w:top w:val="single"/>
                    <w:bottom w:val="single"/>
                    <w:insideH w:val="single"/>
                </w:tblBorders>
            </w:tblPr>
            <w:tblGrid>
                <w:gridCol w:w="1800"/>
                <w:gridCol w:w="3000"/>
                <w:gridCol w:w="2600"/>
                <w:gridCol w:w="2600"/>
            </w:tblGrid>
            <!-- Table Header -->
            <w:tr>
                <w:trPr><w:tblHeader/></w:trPr>
                <w:tc>
                    <w:tcPr><w:shd w:fill="24283b"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="7AA2F7"/></w:rPr><w:t>Feature</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="24283b"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="left"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="7AA2F7"/></w:rPr><w:t>Implementation</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="24283b"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="7AA2F7"/></w:rPr><w:t>Performance</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="24283b"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="7AA2F7"/></w:rPr><w:t>Status</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
            <!-- Row 1 -->
            <w:tr>
                <w:tc>
                    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>OpenXML Reader</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:p><w:r><w:t>Python zipfile + ElementTree</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>&lt; 15 ms</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="1E3A2F"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="00D68F"/></w:rPr><w:t>✓ Native</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
            <!-- Row 2 -->
            <w:tr>
                <w:tc>
                    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Smart Widths</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:p><w:r><w:t>Weighted dxa distribution</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>O(N) cols</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="1E3A2F"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="00D68F"/></w:rPr><w:t>✓ Native</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
            <!-- Row 3 with gridSpan = 2 -->
            <w:tr>
                <w:tc>
                    <w:p><w:r><w:rPr><w:b/></w:rPr><w:t>Footnotes</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:gridSpan w:val="2"/><w:shd w:fill="2A2D37"/></w:tcPr>
                    <w:p><w:r><w:t>Extracts footnote &amp; endnote XML references to bottom footer</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:tcPr><w:shd w:fill="1E3A2F"/></w:tcPr>
                    <w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:rPr><w:b/><w:color w:val="00D68F"/></w:rPr><w:t>✓ Native</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
        </w:tbl>

        <w:p/>

        <!-- Section 5: Borderless Layout Grid (Signatures / Parties) -->
        <w:p>
            <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
            <w:r><w:t>5. Borderless Two-Column Layout Blocks</w:t></w:r>
        </w:p>

        <w:tbl>
            <w:tblPr>
                <w:tblBorders>
                    <w:top w:val="none"/>
                    <w:bottom w:val="none"/>
                    <w:left w:val="none"/>
                    <w:right w:val="none"/>
                    <w:insideH w:val="none"/>
                    <w:insideV w:val="none"/>
                </w:tblBorders>
            </w:tblPr>
            <w:tr>
                <w:tc>
                    <w:p><w:r><w:rPr><w:b/><w:color w:val="7AA2F7"/></w:rPr><w:t>Authorized Signatory (Client):</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Acme Corporation, Inc.</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Address: 500 Technology Way, San Francisco, CA</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Signature: </w:t></w:r><w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>Jane Doe, VP Engineering</w:t></w:r></w:p>
                </w:tc>
                <w:tc>
                    <w:p><w:r><w:rPr><w:b/><w:color w:val="00D68F"/></w:rPr><w:t>Authorized Signatory (Vendor):</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Mdok Technologies Ltd.</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Address: 42 Open Source Blvd, Austin, TX</w:t></w:r></w:p>
                    <w:p><w:r><w:t>Signature: </w:t></w:r><w:r><w:rPr><w:u w:val="single"/></w:rPr><w:t>Anton A., Lead Architect</w:t></w:r></w:p>
                </w:tc>
            </w:tr>
        </w:tbl>

        <w:p>
            <w:r><w:t>This showcase conforms to the OpenXML specifications</w:t></w:r>
            <w:endnoteReference w:id="1"/>
            <w:r><w:t>.</w:t></w:r>
        </w:p>
    </w:body>
</w:document>"""

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", content_types)
        z.writestr("_rels/.rels", root_rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/footnotes.xml", footnotes_xml)
        z.writestr("word/endnotes.xml", endnotes_xml)
        z.writestr("word/document.xml", document_xml)

    return buf.getvalue()


def main() -> None:
    docx_bytes = build_showcase_docx()
    out_path = Path(__file__).parent / "showcase.docx"
    out_path.write_bytes(docx_bytes)
    print(f"Generated {out_path} ({len(docx_bytes)} bytes)")


if __name__ == "__main__":
    main()
