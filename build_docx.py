#!/usr/bin/env python3
"""
Build a professionally formatted Chinese contract DOCX from the markdown.
- Title: 黑体 / 22pt / centered / bold
- Article headings (## 第X条): 黑体 / 16pt / bold
- Sub-headings (### X.Y): 黑体 / 13pt / bold
- Body: 宋体 / 12pt
- Bold runs preserved
- Lists indented properly
"""
import re
from pathlib import Path
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn

SRC = Path(__file__).parent / "03-contract-formal.md"
OUT = Path(__file__).parent / "03-contract-formal.docx"

FONT_HEI = "黑体"
FONT_SONG = "宋体"


def set_run_font(run, font_name, size_pt, bold=False, color=None):
    run.font.name = font_name
    # East Asian font setting must be set via rPr
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        from docx.oxml import OxmlElement
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), font_name)
    rFonts.set(qn("w:ascii"), font_name)
    rFonts.set(qn("w:hAnsi"), font_name)
    run.font.size = Pt(size_pt)
    run.bold = bold
    if color:
        run.font.color.rgb = color


def add_inline(paragraph, text, base_font, base_size, base_bold=False):
    """Parse **bold** markers and add styled runs to paragraph."""
    parts = re.split(r"(\*\*[^*]+\*\*)", text)
    for part in parts:
        if not part:
            continue
        if part.startswith("**") and part.endswith("**"):
            run = paragraph.add_run(part[2:-2])
            set_run_font(run, base_font, base_size, bold=True)
        else:
            run = paragraph.add_run(part)
            set_run_font(run, base_font, base_size, bold=base_bold)


def add_title(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(18)
    run = p.add_run(text)
    set_run_font(run, FONT_HEI, 22, bold=True)


def add_meta(doc, text):
    """Contract number / signing date metadata, right-aligned-ish or normal."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(2)
    add_inline(p, text, FONT_SONG, 11)


def add_article_heading(doc, text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(8)
    run = p.add_run(text)
    set_run_font(run, FONT_HEI, 16, bold=True)


def add_sub_heading(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(8)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    set_run_font(run, FONT_HEI, 13, bold=True)


def add_section_heading(doc, text):
    """For 缔约双方, 附件, 签署 etc. - non-article H2"""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_run_font(run, FONT_HEI, 15, bold=True)


def add_body(doc, text, indent_cm=0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.5
    if indent_cm:
        p.paragraph_format.left_indent = Cm(indent_cm)
    # First-line indent for body paragraphs starting with article numbers
    if re.match(r"^\d+\.\d+", text) or re.match(r"^\d+\.\d+\.\d+", text):
        p.paragraph_format.first_line_indent = Cm(0)
    else:
        p.paragraph_format.first_line_indent = Cm(0.74)  # 2 chars at 12pt
    add_inline(p, text, FONT_SONG, 12)


def add_list_item(doc, text, indent_cm=0.74):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.5
    p.paragraph_format.left_indent = Cm(indent_cm + 0.5)
    p.paragraph_format.first_line_indent = Cm(-0.5)
    # Add bullet manually
    run = p.add_run("• ")
    set_run_font(run, FONT_SONG, 12)
    add_inline(p, text, FONT_SONG, 12)


def add_divider(doc):
    """Skip --- horizontal rule visually; just add spacing."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)


def add_signature_block(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.line_spacing = 1.8
    add_inline(p, text, FONT_SONG, 12)


def set_default_paragraph_font(doc):
    """Set document's default style to 宋体 12pt."""
    style = doc.styles["Normal"]
    style.font.name = FONT_SONG
    style.font.size = Pt(12)
    rPr = style.element.get_or_add_rPr()
    from docx.oxml import OxmlElement
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), FONT_SONG)
    rFonts.set(qn("w:ascii"), FONT_SONG)
    rFonts.set(qn("w:hAnsi"), FONT_SONG)


def set_page_margins(doc):
    for section in doc.sections:
        section.top_margin = Cm(2.5)
        section.bottom_margin = Cm(2.5)
        section.left_margin = Cm(2.8)
        section.right_margin = Cm(2.8)


def main():
    md = SRC.read_text(encoding="utf-8")
    lines = md.split("\n")

    doc = Document()
    set_default_paragraph_font(doc)
    set_page_margins(doc)

    i = 0
    in_signoff = False
    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        # Skip horizontal rule
        if line.strip() == "---":
            add_divider(doc)
            i += 1
            continue

        # H1 title
        if line.startswith("# ") and not line.startswith("## "):
            add_title(doc, line[2:].strip())
            i += 1
            continue

        # H2 — article or named section
        if line.startswith("## "):
            txt = line[3:].strip()
            if txt.startswith("第") and ("条" in txt):
                add_article_heading(doc, txt.replace("　", " "))
            else:
                add_section_heading(doc, txt)
                if "签署" in txt or "附件" in txt:
                    in_signoff = True
            i += 1
            continue

        # H3 — sub-heading like ### 4.1
        if line.startswith("### "):
            add_sub_heading(doc, line[4:].strip().replace("　", " "))
            i += 1
            continue

        # Bullet list item
        if line.startswith("- "):
            add_list_item(doc, line[2:].strip())
            i += 1
            continue

        # Body paragraph (could span multiple lines but in this markdown each is single-line)
        # Replace fullwidth space (　) with normal indentation
        body_text = line.replace("　", " ")
        if in_signoff:
            add_signature_block(doc, body_text)
        else:
            add_body(doc, body_text)
        i += 1

    doc.save(OUT)
    print(f"Generated: {OUT} ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
