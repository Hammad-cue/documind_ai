"""
CUAD v1 (Contract Understanding Atticus Dataset): 510 commercial contracts, 41 clause categories marked by lawyers.
Downloaded once from the Hugging Face hub into ml/data/cuad/ (git-ignored).
"""
import json
import random

from evaluation.common import ROOT

CUAD_PATH = ROOT / 'ml' / 'data' / 'cuad' / 'CUAD_v1' / 'CUAD_v1.json'
PAGE_CHARS = 3000   # CUAD gives plain text without pages, so we cut it into ~A4-sized pseudo-pages


def ensure_downloaded():
    if not CUAD_PATH.exists():
        from huggingface_hub import hf_hub_download
        hf_hub_download('theatticusproject/cuad', 'CUAD_v1/CUAD_v1.json', repo_type='dataset', local_dir=str(ROOT / 'ml' / 'data' / 'cuad'))
    return CUAD_PATH


def load():
    data = json.loads(ensure_downloaded().read_text(encoding='utf-8'))['data']
    contracts = []
    for c in data:
        para = c['paragraphs'][0]
        gold = {}
        for q in para['qas']:
            category = q['id'].split('__')[-1]
            gold[category] = [a['text'].strip() for a in q['answers'] if a['text'].strip()]
        contracts.append({'title': c['title'], 'text': para['context'], 'gold': gold})
    return contracts


def sample(n, seed=7, max_chars=60000):
    """A fixed, reproducible sample (skipping the very longest contracts to keep LLM costs sane)."""
    pool, seen = [], set()
    for c in load():   # CUAD lists a few contracts twice; keep the first copy only
        if len(c['text']) <= max_chars and c['title'] not in seen:
            seen.add(c['title'])
            pool.append(c)
    random.Random(seed).shuffle(pool)
    return pool[:n]


def pages(text, size=PAGE_CHARS):
    """Cut text into pseudo-pages on line boundaries. Returns list of (number, text)."""
    out, buf = [], ''
    for line in text.splitlines(keepends=True):
        if len(buf) + len(line) > size and buf:
            out.append(buf)
            buf = ''
        buf += line
    if buf.strip():
        out.append(buf)
    return [(i + 1, t) for i, t in enumerate(out)]
