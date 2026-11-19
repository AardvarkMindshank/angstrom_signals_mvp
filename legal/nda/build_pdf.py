"""
Turn an NDA written as simple Markdown (# title, ## heading, ### sub-heading, - bullet, **bold**, paragraphs) into the
PDF testers sign: A4, the header line and page number on every page.

  python legal/nda/build_pdf.py legal/nda/nda_v3.md legal/nda/Angstrom_Signals_Private_Beta_NDA_v3.pdf "V3.0"

A signed version's PDF is never rebuilt: its fingerprint is on every signed copy (README.md).
"""

import re
import sys

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer

NAVY = colors.HexColor("#0b2d6b")
BASE = ParagraphStyle("base", fontName="Helvetica", fontSize=9.6, leading=13.6, spaceAfter=5)
TITLE = ParagraphStyle("title", parent=BASE, fontName="Helvetica-Bold", fontSize=17, leading=21, alignment=TA_CENTER,
                       textColor=NAVY, spaceAfter=2)
SUBTITLE = ParagraphStyle("subtitle", parent=BASE, fontName="Helvetica-Bold", fontSize=11.5, leading=15,
                          alignment=TA_CENTER, textColor=NAVY, spaceAfter=3)
H2 = ParagraphStyle("h2", parent=BASE, fontName="Helvetica-Bold", fontSize=11.5, leading=15, textColor=NAVY,
                    spaceBefore=9, spaceAfter=4)
H3 = ParagraphStyle("h3", parent=BASE, fontName="Helvetica-Bold", fontSize=10, leading=14, spaceBefore=4, spaceAfter=3)
CENTRE = ParagraphStyle("centre", parent=BASE, alignment=TA_CENTER, textColor=colors.HexColor("#475569"))


def inline(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def flowables(markdown: str) -> list:
    out, bullets, first_heading = [], [], True

    def flush():
        if bullets:
            out.append(ListFlowable([ListItem(Paragraph(inline(b), BASE), leftIndent=12) for b in bullets],
                                    bulletType="bullet", start="•", leftIndent=14, bulletFontSize=8))
            bullets.clear()

    lines = markdown.splitlines()
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith("- "):
            bullets.append(s[2:])
            continue
        flush()
        if not s:
            continue
        if s.startswith("# "):
            out.append(Paragraph(inline(s[2:]), TITLE))
        elif s.startswith("## ") and first_heading:
            out.append(Paragraph(inline(s[3:]), SUBTITLE))
            first_heading = False
        elif s.startswith("## "):
            out.append(Paragraph(inline(s[3:]), H2))
        elif s.startswith("### "):
            out.append(Paragraph(inline(s[4:]), H3))
        elif i == 2:                                   # the line under the title block
            out.append(Paragraph(inline(s), CENTRE))
            out.append(Spacer(1, 6))
        else:
            out.append(Paragraph(inline(s), BASE))
    flush()
    return out


def build(source: str, target: str, version_label: str) -> None:
    header = f"ANGSTROM SIGNALS  |  PRIVATE BETA AGREEMENT  |  {version_label}"

    def page(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.HexColor("#64748b"))
        canvas.drawString(20 * mm, A4[1] - 12 * mm, header)
        canvas.drawRightString(A4[0] - 20 * mm, 10 * mm, f"Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(target, pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm,
                            bottomMargin=18 * mm, title="Angstrom Signals Private Beta NDA", author="Angstrom Signals")
    doc.build(flowables(open(source, encoding="utf-8").read()), onFirstPage=page, onLaterPages=page)


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else "")
