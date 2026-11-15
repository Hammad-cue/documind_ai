"""Step 1 of the pipeline: get text out of every page of an uploaded file."""
from dataclasses import dataclass, field

from django.conf import settings

from ai import ocr

MIN_DIGITAL_CHARS = 40   # a PDF page with less text than this is treated as scanned


@dataclass
class PageText:
    number: int
    text: str
    source: str                    # DIGITAL / OCR / HANDWRITING
    confidence: float | None = None
    note: str = ''
    tesseract_text: str = ''       # kept for evaluation (Tesseract vs vision model)


@dataclass
class Extraction:
    pages: list = field(default_factory=list)
    page_count: int = 0


class ExtractionError(Exception):
    pass


def _ocr_page(number, image, force_handwriting):
    r = ocr.read_image(image, force_handwriting=force_handwriting)
    return PageText(number, r.text, r.source, r.confidence, r.note, r.tesseract_text)


def extract_pdf(path, force_handwriting=False):
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(path)
    try:
        n = len(pdf)
        if n > settings.MAX_PAGES:
            raise ExtractionError(f'PDF has {n} pages; the limit is {settings.MAX_PAGES}.')
        pages = []
        for i in range(n):
            page = pdf[i]
            text = page.get_textpage().get_text_bounded() or ''
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            if not force_handwriting and len(text.strip()) >= MIN_DIGITAL_CHARS:
                pages.append(PageText(i + 1, text, 'DIGITAL'))
            else:
                image = page.render(scale=300 / 72).to_pil()
                pages.append(_ocr_page(i + 1, image, force_handwriting))
        return Extraction(pages, n)
    finally:
        pdf.close()


def extract_docx(path):
    import docx
    d = docx.Document(path)
    blocks = [p.text for p in d.paragraphs if p.text.strip()]
    for table in d.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                blocks.append(' | '.join(cells))
    # DOCX has no fixed pages; group into pseudo-pages of ~3000 characters.
    pages, buf, size = [], [], 0
    for b in blocks:
        buf.append(b)
        size += len(b)
        if size >= 3000:
            pages.append('\n'.join(buf))
            buf, size = [], 0
    if buf:
        pages.append('\n'.join(buf))
    return Extraction([PageText(i + 1, t, 'DIGITAL') for i, t in enumerate(pages)], len(pages))


def extract_image(path, force_handwriting=False):
    from PIL import Image, ImageOps
    image = ImageOps.exif_transpose(Image.open(path))
    return Extraction([_ocr_page(1, image, force_handwriting)], 1)


def extract(version):
    path = version.file.path
    if version.file_type == 'PDF':
        return extract_pdf(path, version.marked_handwritten)
    if version.file_type == 'DOCX':
        return extract_docx(path)
    if version.file_type == 'IMAGE':
        return extract_image(path, version.marked_handwritten)
    raise ExtractionError(f'Unsupported file type {version.file_type}')
