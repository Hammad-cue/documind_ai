"""
Handwriting evaluation: Tesseract vs the vision-language model, measured by Character Error
Rate (CER) and Word Error Rate (WER).

Dataset layout (small set is fine, e.g. 30-50 images):
    ml/data/handwriting/
        receipt_01.jpg   receipt_01.txt   <- ground-truth transcription you typed by hand
        affidavit_02.png affidavit_02.txt
        ...
Public option: a sample of lines/pages from the IAM Handwriting Database (register at fki.inf.unibe.ch).

    python ml/eval_handwriting.py ml/data/handwriting
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def norm(s):
    return ' '.join(s.lower().split())


def cer(ref, hyp):
    ref, hyp = norm(ref), norm(hyp)
    return edit_distance(ref, hyp) / max(1, len(ref))


def wer(ref, hyp):
    ref, hyp = norm(ref).split(), norm(hyp).split()
    return edit_distance(ref, hyp) / max(1, len(ref))


def main(folder):
    import django
    django.setup()
    from PIL import Image
    from ai import llm, ocr

    rows = []
    images = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff'))
    for img_path in images:
        gt_path = img_path.with_suffix('.txt')
        if not gt_path.exists():
            print(f'skip {img_path.name}: no ground truth .txt')
            continue
        ref = gt_path.read_text(encoding='utf-8')
        image = Image.open(img_path)
        t0 = time.perf_counter()
        t_text, t_conf, _ = ocr.tesseract(image)
        t_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        try:
            v_text = llm.vision_transcribe(image)
        except llm.LLMError as exc:
            v_text = ''
            print(f'vision failed on {img_path.name}: {exc}')
        v_ms = (time.perf_counter() - t0) * 1000
        rows.append({'file': img_path.name, 'tesseract_conf': round(t_conf, 1),
                     'tesseract_cer': cer(ref, t_text), 'tesseract_wer': wer(ref, t_text), 'tesseract_ms': round(t_ms),
                     'vision_cer': cer(ref, v_text), 'vision_wer': wer(ref, v_text), 'vision_ms': round(v_ms)})
        r = rows[-1]
        print(f"{img_path.name:30s} tesseract CER {r['tesseract_cer']:.3f} | vision CER {r['vision_cer']:.3f}")

    if not rows:
        print('No image/.txt pairs found.')
        return
    mean = lambda k: sum(r[k] for r in rows) / len(rows)
    summary = {k: round(mean(k), 4) for k in ('tesseract_cer', 'tesseract_wer', 'vision_cer', 'vision_wer',
                                                 'tesseract_ms', 'vision_ms')}
    summary['images'] = len(rows)
    out = ROOT / 'runs' / f'handwriting-{time.strftime("%Y%m%d-%H%M%S")}.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({'summary': summary, 'rows': rows}, indent=2))
    print(json.dumps(summary, indent=2), f'\nsaved {out}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else str(ROOT / 'data' / 'handwriting'))
