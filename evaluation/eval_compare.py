"""
Evaluation 8 - comparison questions.

A. Routing: 20 comparison questions and 20 look-alikes that must NOT be treated as comparisons (explaining the
   difference between two legal concepts, single-record lookups, lists of values, document searches). Scored for
   the LLM router (as used by the app) and for the keyword rules alone.
B. Tables: 7 comparison questions asked through the full engine as the demo admin, on the demo organization's
   records. Each case lists the records that should appear and, per compared point, the value each record should
   show (None = the record does not state it). Also checked: every filled cell's quote is found on its page.

    python -m evaluation.eval_compare --pause 10
"""
import argparse
import re
import time

from evaluation.common import save

from ai import llm  # noqa: E402
from assistant import engine, router  # noqa: E402
from django.conf import settings  # noqa: E402
from django.contrib.auth.models import User  # noqa: E402
from documents.models import Page  # noqa: E402
from documents.pipeline.understanding import ground  # noqa: E402

COMPARISONS = [
    'Compare the termination notice in all our NDAs',
    'Compare the NDAs with Acme and Orion',
    'How do our leases differ on rent and notice?',
    'Compare the confidentiality obligations in our NDAs',
    'Compare the termination rights in the NDA and the lease',
    'Show the expiry dates of all our contracts side by side',
    'How do our contracts differ on governing law?',
    'Compare the duration of the Acme and Orion NDAs',
    'Compare the governing law of the courier agreement and the supply agreement',
    'Put the notice periods of all our commercial contracts side by side',
    'How do the payment terms differ across our service agreements?',
    'Compare the renewal terms in our leases',
    'Compare the NDA with Acme and the NDA with Orion on term and notice',
    'What are the differences between our NDAs?',
    'Compare the signing dates of the employment contract and the lease',
    'Contrast the confidentiality clauses of the Acme and Orion NDAs',
    'Acme NDA versus Orion NDA: which is stricter on confidentiality?',
    'Compare the contract value of our supply and courier agreements',
    'How do our NDAs compare on governing law?',
    'Give me a side-by-side of the expiry dates in our leases and NDAs',
]
LOOK_ALIKES = [
    ('What is the difference between a void and a voidable agreement?', 'KNOWLEDGE'),
    ('How does a counter-offer differ from an acceptance?', 'KNOWLEDGE'),
    ('Compare void agreements with voidable contracts under the Contract Act', 'KNOWLEDGE'),
    ('What is the difference between coercion and undue influence?', 'KNOWLEDGE'),
    ('How does the Contract Act treat minors compared to persons of unsound mind?', 'KNOWLEDGE'),
    ('What does the Acme NDA say about confidentiality?', 'KNOWLEDGE'),
    ('Does the handbook allow NDAs longer than five years?', 'KNOWLEDGE'),
    ('What are the confidentiality obligations in the Orion NDA?', 'KNOWLEDGE'),
    ('When was the NDA with Acme signed?', 'LOOKUP'),
    ('Which contracts expire in 2027?', 'LOOKUP'),
    ('What is the notice period in the Orion NDA?', 'LOOKUP'),
    ('List the expiry dates of all our leases', 'LOOKUP'),
    ('Who are the parties to the office lease?', 'LOOKUP'),
    ('What is the term of the NDA with Orion?', 'LOOKUP'),
    ('What is the monthly fee in the courier agreement?', 'LOOKUP'),
    ('Find the lease for the Lahore office', 'SEARCH'),
    ('Show me all handwritten documents', 'SEARCH'),
    ('Find the courier agreement', 'SEARCH'),
    ('Open the contracts handbook', 'SEARCH'),
    ('Find agreements that mention arbitration', 'SEARCH'),
]

ACME, ORION, LEASE = 'NDA - Acme Corp', 'NDA - Orion Ventures', 'Office Lease - Gulberg Lahore'
COURIER, SUPPLY = 'Courier Services Agreement - FastTrack Logistics', 'Supply Agreement - Delta Traders'
EMPLOY, RECEIPT = 'Employment Contract - Hira Ahmed', 'Security Deposit Receipt (handwritten)'
# question, expected records, {column hint: {record: expected words or None}}
TABLES = [
    ('Compare the termination notice in all our NDAs', {ACME, ORION},
     {'notice': {ACME: '60 days', ORION: None}}),
    ('How do our contracts differ on governing law and expiry?', {ACME, ORION, LEASE, COURIER, SUPPLY, EMPLOY, RECEIPT},
     {'law': {ACME: 'pakistan', ORION: 'pakistan', COURIER: 'pakistan', SUPPLY: 'pakistan', LEASE: None, EMPLOY: None,
              RECEIPT: None},
      'expir': {ACME: '31 march 2028', ORION: '2 september 2032', COURIER: '11 december 2026', SUPPLY: '30 june 2027',
                LEASE: '30 june 2027', EMPLOY: None, RECEIPT: None}}),
    ('Compare the confidentiality obligations in the NDAs with Acme and Orion', {ACME, ORION},
     {'confiden': {ACME: 'confiden', ORION: None}}),
    ('Compare the duration of the Acme and Orion NDAs', {ACME, ORION},
     {'term|duration': {ACME: '3 years', ORION: '7 years'}}),
    ('Compare the notice periods of the courier agreement and the supply agreement', {COURIER, SUPPLY},
     {'notice': {COURIER: '30 days', SUPPLY: '15 days'}}),
    ('Compare the purpose of our NDAs', {ACME, ORION},
     {'purpose': {ACME: 'software', ORION: 'renewable'}}),
    ('Compare the governing law of the NDA with Acme and the lease', {ACME, LEASE},
     {'law': {ACME: 'pakistan', LEASE: None}}),
]


def routing(pause):
    items = [(q, True) for q in COMPARISONS] + [(q, False) for q, _ in LOOK_ALIKES]
    out = {}
    for name, predict in (('keyword', router.heuristic_plan), ('llm', router.plan_query)):
        rows = []
        for i, (q, is_cmp) in enumerate(items):
            if name == 'llm' and i:
                time.sleep(pause)
            plan = predict(q)
            rows.append({'q': q, 'comparison': is_cmp, 'intent': plan['intent'], 'method': plan.get('method'),
                         'fields': plan.get('fields'), 'records': plan.get('records'), 'aspect': plan.get('aspect')})
        tp = sum(r['comparison'] and r['intent'] == 'COMPARE' for r in rows)
        fp = sum(not r['comparison'] and r['intent'] == 'COMPARE' for r in rows)
        out[name] = {'comparisons_routed': f'{tp}/{len(COMPARISONS)}', 'recall': round(tp / len(COMPARISONS), 3),
                     'look_alikes_routed_as_comparison': f'{fp}/{len(LOOK_ALIKES)}',
                     'precision': round(tp / (tp + fp), 3) if tp + fp else None,
                     'misses': [r for r in rows if (r['intent'] == 'COMPARE') != r['comparison']], 'rows': rows}
        print(f"{name}: comparisons {tp}/{len(COMPARISONS)}, false comparisons {fp}/{len(LOOK_ALIKES)}")
        for r in out[name]['misses']:
            print('   miss:', r['intent'], '|', r['q'])
    return out


def norm(s):
    return ' '.join(re.sub(r'[,]', '', (s or '').lower()).split())


def tables(pause):
    user = User.objects.get(username='demo_admin')
    cases, cells_ok, cells_n, filled, grounded = [], 0, 0, 0, 0
    for i, (q, want_rows, want) in enumerate(TABLES):
        if i:
            time.sleep(pause)
        started = time.perf_counter()
        out = engine.answer(user, q)
        secs = time.perf_counter() - started
        got_rows = {r['document_title'] for r in out['results']} if out['intent'] == 'COMPARE' else set()
        cols = out['plan'].get('columns', [])
        checks = []
        for hint, per_row in want.items():
            col = next((c for c in cols if re.search(hint, (c['key'] + ' ' + c['label']).lower())), None)
            for title, words in per_row.items():
                row = next((r for r in out['results'] if r.get('document_title') == title), None) if col else None
                value = row['cells'][col['key']]['value'] if row else None
                ok = row is not None and (norm(words) in norm(value) if words else not value)
                checks.append({'column': hint, 'record': title, 'expected': words, 'got': value, 'ok': ok})
        for r in out['results'] if out['intent'] == 'COMPARE' else []:
            for c in r['cells'].values():
                if c['value'] and c['page']:
                    filled += 1
                    page = Page.objects.filter(version__document_id=r['document_id'], version__number=r['version'],
                                               number=c['page']).first()
                    grounded += bool(page and ground(c['quote'], page.text))
        cells_ok += sum(c['ok'] for c in checks)
        cells_n += len(checks)
        case = {'q': q, 'intent': out['intent'], 'rows_ok': got_rows == want_rows, 'missing_rows': sorted(want_rows - got_rows),
                'extra_rows': sorted(got_rows - want_rows), 'columns': [c['label'] for c in cols], 'cells': checks,
                'answer': out['answer'], 'seconds': round(secs, 1)}
        cases.append(case)
        print(f"{q}\n   {out['intent']} rows {'ok' if case['rows_ok'] else 'WRONG ' + str(case['missing_rows']) + str(case['extra_rows'])}"
              f"  cells {sum(c['ok'] for c in checks)}/{len(checks)}  {secs:.1f}s")
        for c in checks:
            if not c['ok']:
                print(f"     x {c['record']} / {c['column']}: expected {c['expected']!r}, got {c['got']!r}")
    return {'cases': cases, 'summary': {
        'questions': len(cases), 'routed_compare': sum(c['intent'] == 'COMPARE' for c in cases),
        'right_records': sum(c['rows_ok'] for c in cases), 'cells_correct': f'{cells_ok}/{cells_n}',
        'cell_accuracy': round(cells_ok / cells_n, 3) if cells_n else None,
        'filled_cells_grounded': f'{grounded}/{filled}',
        'mean_seconds': round(sum(c['seconds'] for c in cases) / len(cases), 1)}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pause', type=float, default=10.0)
    args = ap.parse_args()
    if not llm.is_configured():
        raise SystemExit('No LLM configured')
    r = routing(args.pause)
    time.sleep(args.pause)
    t = tables(args.pause * 1.5)
    print('\n', t['summary'])
    save('compare', {'model': f'{settings.LLM_PROVIDER}/{settings.LLM_MODEL}', 'routing': r, 'tables': t})


if __name__ == '__main__':
    main()
