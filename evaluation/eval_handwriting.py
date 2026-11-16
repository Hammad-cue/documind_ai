"""
Evaluation 4 — handwriting: Tesseract vs the vision-language model, by Character / Word Error Rate.

Without real scans, a *synthetic* set is generated: receipts, affidavit lines and notes written in ten
handwriting-style fonts, slightly rotated, with uneven ink and scanner noise. This is easier than real
handwriting, so treat it as a sanity check. For the report, also run it on real scans:

    python -m evaluation.eval_handwriting                      # synthetic set (generated once)
    python -m evaluation.eval_handwriting --folder path/to/real # your scans: image + same-name .txt transcript
"""
import argparse
import random
import time
from pathlib import Path

from evaluation.common import ROOT, save

from ai import llm, ocr  # noqa: E402
from django.conf import settings  # noqa: E402

SYNTH = ROOT / 'ml' / 'data' / 'handwriting_synthetic'
FONTS = ['segoesc.ttf', 'segoepr.ttf', 'Inkfree.ttf', 'LHANDW.TTF', 'BRADHITC.TTF', 'FREESCPT.TTF', 'ITCKRIST.TTF',
         'MISTRAL.TTF', 'PRISTINA.TTF', 'TEMPSITC.TTF']
NAMES = ['Imran Qureshi', 'Ayesha Noor', 'Bilal Ahmed', 'Sana Riaz', 'Usman Tariq', 'Hira Ahmed', 'Kamran Malik', 'Nadia Hussain',
         'Faisal Iqbal', 'Zainab Raza', 'Tariq Mehmood', 'Mariam Siddiqui']
PLACES = ['45-B Gulberg III, Lahore', 'Plot 12, F-7 Markaz, Islamabad', 'House 9, DHA Phase 5, Karachi', 'Shop 3, Saddar, Rawalpindi',
          'Flat 21, Model Town, Lahore', 'Office 7, Blue Area, Islamabad']
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']


def _text(rng):
    a, b = rng.sample(NAMES, 2)
    amount = f'PKR {rng.randrange(10, 900) * 1000:,}'
    d = f'{rng.randint(1, 28)} {rng.choice(MONTHS)} {rng.randint(2019, 2026)}'
    kind = rng.randrange(3)
    if kind == 0:
        return [f'Receipt', f'I, {a}, received {amount}', f'from {b} as advance rent', f'for {rng.choice(PLACES)}.', f'Dated: {d}', f'Signature: {a}']
    if kind == 1:
        return [f'Affidavit', f'I, {a}, solemnly declare that', f'the vehicle sold to {b} on {d}', f'was free of all liabilities.',
                f'Deponent: {a}']
    return [f'Note of agreement', f'{a} will pay {b} {amount}', f'in {rng.randint(2, 12)} monthly instalments', f'starting {d}.',
            f'Witness: {rng.choice(NAMES)}']


def generate(n=30, seed=3):
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    SYNTH.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    fonts_dir = Path('C:/Windows/Fonts')
    usable = [f for f in FONTS if (fonts_dir / f).exists()] or [None]
    for i in range(n):
        font_name = usable[i % len(usable)]
        lines = _text(rng)
        size = rng.randint(38, 48)
        font = ImageFont.truetype(str(fonts_dir / font_name), size) if font_name else ImageFont.load_default()
        img = Image.new('RGB', (1500, 160 + len(lines) * int(size * 1.9)), tuple(rng.randint(236, 252) for _ in range(3)))
        draw = ImageDraw.Draw(img)
        ink = rng.choice([(20, 30, 95), (25, 25, 30), (15, 45, 110)])
        y = 70
        for line in lines:
            draw.text((80 + rng.randint(-12, 12), y + rng.randint(-4, 4)), line, font=font, fill=ink)
            y += int(size * 1.9)
        img = img.rotate(rng.uniform(-2.2, 2.2), expand=True, fillcolor=(245, 243, 236)).filter(ImageFilter.GaussianBlur(0.6))
        noise = Image.effect_noise(img.size, 18).convert('RGB')
        img = Image.blend(img, noise, 0.06)
        stem = f'synthetic_{i + 1:02d}_{(font_name or "default").split(".")[0].lower()}'
        img.save(SYNTH / f'{stem}.png')
        (SYNTH / f'{stem}.txt').write_text('\n'.join(lines), encoding='utf-8')
    return SYNTH


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--folder', help='folder of image + .txt pairs (default: generated synthetic set)')
    args = ap.parse_args()
    folder = Path(args.folder) if args.folder else (SYNTH if any(SYNTH.glob('*.png')) else generate())
    from PIL import Image

    rows = []
    for img_path in sorted(p for p in folder.iterdir() if p.suffix.lower() in ('.png', '.jpg', '.jpeg', '.tif', '.tiff')):
        ref_path = img_path.with_suffix('.txt')
        if not ref_path.exists():
            continue
        ref = ref_path.read_text(encoding='utf-8')
        image = Image.open(img_path)
        t0 = time.perf_counter()
        t_text, t_conf, _ = ocr.tesseract(image)
        t_ms = (time.perf_counter() - t0) * 1000
        t0 = time.perf_counter()
        try:
            v_text = llm.vision_transcribe(image)
        except llm.LLMError as exc:
            print(f'vision failed on {img_path.name}: {exc}')
            v_text = None   # API failure: excluded from the vision averages, not scored as 100% error
        v_ms = (time.perf_counter() - t0) * 1000
        time.sleep(6.5)  # stay under the free-tier limit of ~10 vision requests per minute
        # what the pipeline would actually do: vision model only when Tesseract is unsure
        routed = v_text if (t_conf < settings.HANDWRITING_CONFIDENCE_THRESHOLD and v_text is not None) else t_text
        row = {'file': img_path.name, 'font': img_path.stem.split('_', 2)[-1], 'tesseract_conf': round(t_conf, 1),
               'tesseract_cer': round(cer(ref, t_text), 4), 'tesseract_wer': round(wer(ref, t_text), 4),
               'vision_cer': round(cer(ref, v_text), 4) if v_text is not None else None,
               'vision_wer': round(wer(ref, v_text), 4) if v_text is not None else None,
               'pipeline_cer': round(cer(ref, routed), 4), 'sent_to_vision': t_conf < settings.HANDWRITING_CONFIDENCE_THRESHOLD,
               'tesseract_ms': round(t_ms), 'vision_ms': round(v_ms)}
        rows.append(row)
        vis = f"{row['vision_cer']:.3f}" if row['vision_cer'] is not None else 'n/a (API failed)'
        print(f"{img_path.name:42s} tesseract CER {row['tesseract_cer']:.3f} ({row['tesseract_conf']:.0f}%) | vision CER {vis}")

    def mean(k):
        vals = [r[k] for r in rows if r[k] is not None]
        return round(sum(vals) / len(vals), 4) if vals else None
    summary = {k: mean(k) for k in ('tesseract_cer', 'tesseract_wer', 'vision_cer', 'vision_wer', 'pipeline_cer', 'tesseract_ms', 'vision_ms')}
    if summary['vision_cer'] is None:
        print('Every vision call failed (quota?). Not saving — try again later.')
        return
    summary.update(images=len(rows), vision_api_failures=sum(r['vision_cer'] is None for r in rows), sent_to_vision=sum(r['sent_to_vision'] for r in rows),
                   vision_model=f'{settings.VISION_PROVIDER}/{settings.VISION_MODEL}',
                   dataset='synthetic handwriting-style fonts' if folder == SYNTH else str(folder))
    print(summary)
    save('handwriting_synthetic' if folder == SYNTH else 'handwriting_real', {'summary': summary, 'rows': rows})


if __name__ == '__main__':
    main()
