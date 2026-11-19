"""
Evaluation 3b - the second check on extracted fields.

Re-uses the predictions saved by eval_extraction (each already marked right or wrong against the lawyers'
CUAD labels) and asks the second check (documents.pipeline.understanding.verify_fields) about each contract's
values. A good check flags many wrong values and few right ones.

    python -m evaluation.eval_verifier --pause 8
"""
import argparse
import json
import time

from evaluation.common import RESULTS, save  # noqa: I001  (sets up Django first)

from ai import llm  # noqa: E402
from documents.pipeline.understanding import verify_fields  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pause', type=float, default=8.0)
    args = ap.parse_args()
    saved = json.loads((RESULTS / 'extraction_cuad.json').read_text(encoding='utf-8'))

    rows, failed = [], 0
    for i, c in enumerate(saved['contracts'], 1):
        items = [{'key': k, 'value_text': f['pred'], 'source_quote': f['quote'], 'verdict': f['verdict']}
                 for k, f in c['fields'].items() if f['pred']]
        if not items:
            continue
        checked = verify_fields(items)
        if not checked:
            failed += 1
            print(f'[{i}] check failed (API) - skipped', flush=True)
        for it in items:
            if it['key'] in checked:
                ok, why = checked[it['key']]
                rows.append({'contract': c['title'], 'key': it['key'], 'right': it['verdict'] == 'TP',
                             'flagged': not ok, 'reason': why})
        print(f'[{i}/{len(saved["contracts"])}] {sum(not checked[k][0] for k in checked)} flagged', flush=True)
        time.sleep(args.pause)

    def rate(xs):
        return round(sum(x['flagged'] for x in xs) / len(xs), 3) if xs else None
    wrong, right = [r for r in rows if not r['right']], [r for r in rows if r['right']]
    per_field = {}
    for r in rows:
        f = per_field.setdefault(r['key'], {'wrong': 0, 'wrong_flagged': 0, 'right': 0, 'right_flagged': 0})
        kind = 'right' if r['right'] else 'wrong'
        f[kind] += 1
        f[f'{kind}_flagged'] += r['flagged']
    summary = {
        'model': llm.settings.LLM_MODEL, 'contracts': len(saved['contracts']) - failed, 'checked_values': len(rows),
        'wrong_values': len(wrong), 'wrong_flagged': sum(r['flagged'] for r in wrong), 'wrong_flagged_rate': rate(wrong),
        'right_values': len(right), 'right_flagged': sum(r['flagged'] for r in right), 'right_flagged_rate': rate(right),
        'per_field': per_field, 'api_failures': failed,
        'note': 'Quotes are the first 200 characters saved by eval_extraction, so the check sees slightly less text '
                'than it does inside the pipeline.',
    }
    print(json.dumps({k: v for k, v in summary.items() if k != 'per_field'}, indent=2))
    save('verifier_cuad', {'summary': summary, 'rows': rows})


if __name__ == '__main__':
    main()
