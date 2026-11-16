"""Shared helpers for the evaluation scripts (Django setup, text normalisation, saving results)."""
import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')

import django  # noqa: E402

django.setup()

RESULTS = ROOT / 'evaluation' / 'results'
DATA = ROOT / 'evaluation' / 'data'

STOP = set('the a an of and or to in on for by with this that be is are as at any its it from such shall will may'.split())


def tokens(text, drop_stop=True):
    words = re.findall(r'[a-z0-9]+', (text or '').lower())
    return [w for w in words if not (drop_stop and w in STOP)]


def overlap(part, whole):
    """Share of `part`'s tokens that also appear in `whole` (0..1)."""
    p = tokens(part)
    if not p:
        return 0.0
    w = set(tokens(whole))
    return sum(t in w for t in p) / len(p)


def save(name, payload):
    RESULTS.mkdir(parents=True, exist_ok=True)
    payload = {'name': name, 'created': time.strftime('%Y-%m-%d %H:%M'), **payload}
    path = RESULTS / f'{name}.json'
    path.write_text(json.dumps(payload, indent=2, default=str), encoding='utf-8')
    print(f'\nsaved {path.relative_to(ROOT)}')
    return path


def prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {'precision': round(p, 3), 'recall': round(r, 3), 'f1': round(f, 3), 'tp': tp, 'fp': fp, 'fn': fn}
