"""
Evaluation 3c - calculating the expiry date from the start date and the term.

Only contracts where the first extraction run found no expiry date can change (the calculation never replaces
a written expiry date), so those contracts are extracted again and the expiry field is scored twice on the
SAME run: without the calculated value and with it. Contracts whose expiry was already right are carried over.

    python -m evaluation.eval_expiry --pause 30
"""
import argparse
import json
import time

from evaluation import cuad  # noqa: I001  (sets up Django first)
from evaluation.common import RESULTS, save
from evaluation.eval_extraction import FIELD_MAP, evidence_matches, value_matches

from ai import llm  # noqa: E402
from documents.pipeline.extract import PageText  # noqa: E402
from documents.pipeline.understanding import extract_fields  # noqa: E402


def verdict(pred, spans):
    if not spans and not pred:
        return 'TN'
    if pred and not spans:
        return 'FP'
    if spans and not pred:
        return 'FN'
    ok = evidence_matches(pred['source_quote'], spans) or value_matches('expiry_date', pred['value_text'], spans)
    return 'TP' if ok else 'WRONG'


def prf(vs):
    tp = vs.count('TP')
    fp = vs.count('FP') + vs.count('WRONG')
    fn = vs.count('FN') + vs.count('WRONG')
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {'tp': tp, 'fp': fp, 'fn': fn, 'precision': round(p, 3), 'recall': round(r, 3),
            'f1': round(2 * p * r / (p + r), 3) if p + r else 0.0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=40)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--pause', type=float, default=30.0)
    args = ap.parse_args()

    saved = {c['title']: c for c in json.loads((RESULTS / 'extraction_cuad.json').read_text(encoding='utf-8'))['contracts']}
    cat = FIELD_MAP['expiry_date']
    before, without_calc, with_calc, rows, skipped = [], [], [], [], []
    for i, c in enumerate(cuad.sample(args.n, args.seed), 1):
        old = saved.get(c['title'])
        if not old:
            continue
        old_v = old['fields']['expiry_date']['verdict']
        before.append(old_v)
        if old_v not in ('FN', 'TN'):          # expiry already found: the calculation cannot change it
            without_calc.append(old_v)
            with_calc.append(old_v)
            continue
        pages = [PageText(n, t, 'DIGITAL') for n, t in cuad.pages(c['text'])]
        try:
            fields = {f['key']: f for f in extract_fields(pages, verify=False)}
        except llm.LLMError as exc:
            skipped.append({'title': c['title'], 'error': str(exc)[:200]})
            before.pop()
            print(f'[{i}] SKIPPED {c["title"][:60]}: {exc}', flush=True)
            time.sleep(args.pause)
            continue
        spans = c['gold'].get(cat, [])
        pred = fields.get('expiry_date')
        calculated = bool(pred and pred.get('review_reason', '').startswith('Calculated'))
        v_with = verdict(pred, spans)
        v_without = verdict(None if calculated else pred, spans)
        with_calc.append(v_with)
        without_calc.append(v_without)
        rows.append({'contract': c['title'], 'before': old_v, 'without_calculation': v_without, 'with_calculation': v_with,
                     'calculated': calculated, 'pred': pred['value_text'] if pred else None,
                     'term': (fields.get('term') or {}).get('value_text'), 'gold': [s[:200] for s in spans[:2]]})
        print(f'[{i}] {old_v} -> without {v_without} / with {v_with}{" (calculated)" if calculated else ""}  {c["title"][:50]}', flush=True)
        time.sleep(args.pause)

    summary = {'model': llm.settings.LLM_MODEL, 'contracts': len(with_calc), 're_extracted': len(rows),
               'calculated_values': sum(r['calculated'] for r in rows),
               'calculated_right': sum(r['calculated'] and r['with_calculation'] == 'TP' for r in rows),
               'calculated_wrong': sum(r['calculated'] and r['with_calculation'] != 'TP' for r in rows),
               'first_run': prf(before), 'without_calculation': prf(without_calc), 'with_calculation': prf(with_calc),
               'skipped': skipped}
    print(json.dumps(summary, indent=2))
    save('expiry_cuad', {'summary': summary, 'rows': rows})


if __name__ == '__main__':
    main()
