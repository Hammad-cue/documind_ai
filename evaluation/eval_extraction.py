"""
Evaluation 1 — record field extraction on CUAD.

For each sampled contract the real pipeline function (documents.pipeline.understanding.extract_fields)
reads the contract and returns fields with a verbatim quote and page. We compare against the lawyers' spans:

  detection   : did we return the field when (and only when) the contract contains it?
  correct     : detected AND our quote overlaps the lawyers' span (>= 50% of its words),
                or the value itself matches (same date / same parties / same jurisdiction)
  grounding   : precision of predictions whose quote was found on the page vs. those that weren't
  review queue: share of wrong predictions that the system had already routed to human review

    python -m evaluation.eval_extraction --n 25
"""
import argparse
import time

from evaluation import cuad
from evaluation.common import overlap, prf, save, tokens

from ai import llm  # noqa: E402  (Django is set up by evaluation.common)
from documents.pipeline.extract import PageText
from documents.pipeline.understanding import extract_fields, parse_date

FIELD_MAP = {
    'parties': 'Parties',
    'signed_date': 'Agreement Date',
    'effective_date': 'Effective Date',
    'expiry_date': 'Expiration Date',
    'auto_renewal': 'Renewal Term',
    'notice_period': 'Notice Period To Terminate Renewal',
    'governing_law': 'Governing Law',
}


def value_matches(key, value, spans):
    if key == 'signed_date':
        d = parse_date(value)
        return d is not None and any(parse_date(s) == d for s in spans)
    if key == 'parties':
        gold = set(tokens(' '.join(spans)))
        pred = [t for t in tokens(value) if t not in {'inc', 'ltd', 'llc', 'corp', 'corporation', 'company', 'co'}]
        return bool(pred) and sum(t in gold for t in pred) / len(pred) >= 0.5
    if key == 'governing_law':
        pred = [t for t in tokens(value) if t not in {'laws', 'law', 'state', 'commonwealth', 'courts', 'court', 'united', 'states'}]
        return bool(pred) and all(t in set(tokens(' '.join(spans))) for t in pred)
    return False


def evidence_matches(quote, spans):
    return bool(quote) and any(overlap(quote, s) >= 0.5 or overlap(s, quote) >= 0.5 for s in spans)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--n', type=int, default=25)
    ap.add_argument('--seed', type=int, default=7)
    args = ap.parse_args()

    contracts = cuad.sample(args.n, args.seed)
    counts = {k: {'tp': 0, 'fp': 0, 'fn': 0, 'tn': 0} for k in FIELD_MAP}
    grounded = {'right': 0, 'wrong': 0}
    ungrounded = {'right': 0, 'wrong': 0}
    wrong_flagged = wrong_total = right_flagged = right_total = 0
    rows, skipped, seconds = [], [], []

    for i, c in enumerate(contracts, 1):
        pages = [PageText(n, t, 'DIGITAL') for n, t in cuad.pages(c['text'])]
        started = time.perf_counter()
        for attempt in range(2):
            try:
                fields = {f['key']: f for f in extract_fields(pages)}
                break
            except llm.LLMError as exc:
                if attempt:
                    skipped.append({'title': c['title'], 'error': str(exc)[:200]})
                    fields = None
                else:
                    time.sleep(60)  # free-tier rate limit: wait and retry once
        if fields is None:
            print(f'[{i}/{len(contracts)}] SKIPPED {c["title"][:60]}')
            continue
        seconds.append(time.perf_counter() - started)

        row = {'title': c['title'], 'fields': {}}
        for key, cat in FIELD_MAP.items():
            spans = c['gold'].get(cat, [])
            pred = fields.get(key)
            if not spans and not pred:
                counts[key]['tn'] += 1
                verdict = 'TN'
            elif pred and not spans:
                counts[key]['fp'] += 1
                verdict = 'FP'
            elif spans and not pred:
                counts[key]['fn'] += 1
                verdict = 'FN'
            else:
                ok = evidence_matches(pred['source_quote'], spans) or value_matches(key, pred['value_text'], spans)
                if ok:
                    counts[key]['tp'] += 1
                    verdict = 'TP'
                else:
                    counts[key]['fp'] += 1
                    counts[key]['fn'] += 1
                    verdict = 'WRONG'
            if pred:
                right = verdict == 'TP'
                bucket = grounded if pred['grounded'] else ungrounded
                bucket['right' if right else 'wrong'] += 1
                flagged = pred['status'] == 'NEEDS_REVIEW'
                if right:
                    right_total += 1
                    right_flagged += flagged
                else:
                    wrong_total += 1
                    wrong_flagged += flagged
            row['fields'][key] = {'verdict': verdict, 'pred': pred['value_text'] if pred else None,
                                  'quote': (pred or {}).get('source_quote', '')[:200], 'gold': [s[:200] for s in spans[:2]]}
        rows.append(row)
        tp = sum(1 for f in row['fields'].values() if f['verdict'] in ('TP', 'TN'))
        print(f'[{i}/{len(contracts)}] {tp}/{len(FIELD_MAP)} right · {seconds[-1]:.1f}s · {c["title"][:60]}')

    per_field = {k: {**prf(v['tp'], v['fp'], v['fn']), 'tn': v['tn']} for k, v in counts.items()}
    total = prf(sum(v['tp'] for v in counts.values()), sum(v['fp'] for v in counts.values()), sum(v['fn'] for v in counts.values()))
    precision = lambda b: round(b['right'] / (b['right'] + b['wrong']), 3) if b['right'] + b['wrong'] else None
    summary = {
        'contracts_evaluated': len(rows), 'contracts_skipped': len(skipped), 'model': llm.settings.LLM_MODEL,
        'micro': total, 'per_field': per_field,
        'grounding': {'grounded_precision': precision(grounded), 'ungrounded_precision': precision(ungrounded),
                      'grounded': grounded, 'ungrounded': ungrounded},
        'review_queue': {'wrong_predictions_flagged': f'{wrong_flagged}/{wrong_total}',
                         'right_predictions_flagged': f'{right_flagged}/{right_total}'},
        'seconds_per_contract': round(sum(seconds) / len(seconds), 1) if seconds else None,
    }
    print('\nmicro', total)
    for k, v in per_field.items():
        print(f'  {k:15s} P {v["precision"]:.2f}  R {v["recall"]:.2f}  F1 {v["f1"]:.2f}')
    print('grounding', summary['grounding'])
    print('review queue', summary['review_queue'])
    save('extraction_cuad', {'summary': summary, 'skipped': skipped, 'contracts': rows})


if __name__ == '__main__':
    main()
