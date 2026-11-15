"""
Printed OCR (Tesseract) and handwriting recognition (vision-language model).

Decision rule per page image:
  1. Run Tesseract and compute mean word confidence.
  2. If the uploader marked the document as handwritten, OR confidence is below
     HANDWRITING_CONFIDENCE_THRESHOLD, OR Tesseract found almost no words,
     send the image to the vision model instead.
"""
from dataclasses import dataclass

from django.conf import settings

from . import llm


@dataclass
class OcrResult:
    text: str
    source: str            # 'OCR' or 'HANDWRITING'
    confidence: float | None
    tesseract_text: str
    tesseract_confidence: float | None
    note: str = ''


def tesseract(image):
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    gray = image.convert('L')
    data = pytesseract.image_to_data(gray, output_type=pytesseract.Output.DICT)
    confs = [float(c) for c, w in zip(data['conf'], data['text']) if str(w).strip() and float(c) >= 0]
    text = pytesseract.image_to_string(gray)
    mean_conf = sum(confs) / len(confs) if confs else 0.0
    return text.strip(), mean_conf, len(confs)


def read_image(image, force_handwriting=False):
    try:
        t_text, t_conf, n_words = tesseract(image)
    except Exception as exc:  # Tesseract missing or failed
        t_text, t_conf, n_words = '', None, 0
        tess_error = str(exc)
    else:
        tess_error = ''

    looks_handwritten = force_handwriting or t_conf is None or t_conf < settings.HANDWRITING_CONFIDENCE_THRESHOLD or n_words < 5
    if looks_handwritten and llm.is_configured(settings.VISION_PROVIDER):
        try:
            text = llm.vision_transcribe(image)
            return OcrResult(text, 'HANDWRITING', None, t_text, t_conf,
                             note='vision model' + (f' (tesseract error: {tess_error})' if tess_error else ''))
        except llm.LLMError as exc:
            note = f'vision model failed, kept Tesseract output: {exc}'
            return OcrResult(t_text, 'OCR', t_conf, t_text, t_conf, note=note)
    return OcrResult(t_text, 'OCR', t_conf, t_text, t_conf, note=tess_error)
