import sys
from pathlib import Path
from xml.sax.saxutils import escape

import reportlab
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def convert(directory):
    files = sorted(Path(directory).glob("*.txt"))
    if not files:
        raise ValueError("No .txt reports found.")
    if any(path.with_suffix(".pdf").exists() for path in files):
        raise FileExistsError("PDF output already exists.")
    font = Path(reportlab.__file__).parent / "fonts" / "Vera.ttf"
    pdfmetrics.registerFont(TTFont("ReportFont", str(font)))
    style = getSampleStyleSheet()["BodyText"]
    style.fontName = "ReportFont"
    for path in files:
        paragraphs = path.read_text(encoding="utf-8").split("\n\n")
        story = []
        for paragraph in paragraphs:
            story.extend([Paragraph(escape(paragraph).replace("\n", "<br/>"), style), Spacer(1, 12)])
        SimpleDocTemplate(str(path.with_suffix(".pdf"))).build(story)


if __name__ == "__main__":
    convert(sys.argv[1] if len(sys.argv) > 1 else "output/reports")
