"""
Evaluation 7 - policy compliance check.

16 hand-written contract fact sheets are checked against the demo Contracts Handbook (the same three pages the
demo organization uses as its policy). Each case targets one handbook rule and has a known answer: the NDA term
rule (more than five years needs partner approval), the thirty-day notice rule for commercial contracts, or the
ninety-day notice for office leases. Two cases (an employment contract, a receipt) are not covered by any rule.

Scored, using the same judge() the app runs:
  - target verdict: is the finding for the targeted rule the expected one (OK / ISSUE / UNCLEAR)?
  - issue detection: precision and recall of "this contract breaks a rule" at contract level
  - false issues: ISSUE findings on rules the case does not break (e.g. stamp duty when stamp paper is not mentioned)

    python -m evaluation.eval_policy --pause 12
"""
import argparse
import time
from types import SimpleNamespace

from evaluation.common import save

from ai import llm  # noqa: E402
from django.conf import settings  # noqa: E402
from documents.management.commands.seed_demo import HANDBOOK  # noqa: E402
from documents.pipeline.policy import judge  # noqa: E402

# (title, type, facts, targeted rule, accepted verdicts for it; None = no finding for it is also fine)
CASES = [
    ('NDA - Bright Foods', 'NDA', {'Parties': 'Khan & Associates; Bright Foods Ltd', 'Term': '2 years'},
     'nda_term', {'OK'}),
    ('NDA - Sialkot Sports', 'NDA', {'Parties': 'Khan & Associates; Sialkot Sports', 'Term': '3 years'},
     'nda_term', {'OK'}),
    ('NDA - Delta Textiles', 'NDA', {'Parties': 'Khan & Associates; Delta Textiles', 'Term': '5 years'},
     'nda_term', {'OK'}),
    ('NDA - Orion Ventures', 'NDA', {'Parties': 'Khan & Associates; Orion Ventures', 'Term': '7 years'},
     'nda_term', {'ISSUE'}),
    ('NDA - Northwind Capital', 'NDA', {'Parties': 'Khan & Associates; Northwind Capital', 'Term': '10 years',
                                         'Effective date': '2025-03-01'}, 'nda_term', {'ISSUE'}),
    ('NDA - Lahore Labs', 'NDA', {'Parties': 'Khan & Associates; Lahore Labs', 'Effective date': '2025-05-10'},
     'nda_term', {'UNCLEAR', None}),
    ('Cleaning Services Agreement', 'Service agreement',
     {'Parties': 'Khan & Associates; SparkClean', 'Notice period': '7 days', 'Fee': 'PKR 40,000 per month'},
     'notice', {'ISSUE'}),
    ('Supply Agreement - Punjab Paper', 'Supply agreement',
     {'Parties': 'Khan & Associates; Punjab Paper Mills', 'Notice period': '15 days'}, 'notice', {'ISSUE'}),
    ('IT Support Agreement', 'Service agreement',
     {'Parties': 'Khan & Associates; NetCare', 'Notice period': '30 days', 'Term': '1 year'}, 'notice', {'OK'}),
    ('Distribution Agreement - Indus Traders', 'Distribution agreement',
     {'Parties': 'Khan & Associates; Indus Traders', 'Notice period': '60 days'}, 'notice', {'OK'}),
    ('Consulting Agreement - R. Malik', 'Consulting agreement',
     {'Parties': 'Khan & Associates; Rashid Malik', 'Fee': 'PKR 150,000', 'Effective date': '2025-02-01'},
     'notice', {'UNCLEAR', None}),
    ('Office Lease - Gulberg', 'Lease',
     {'Parties': 'Khan & Associates; Gulberg Properties', 'Notice period': '90 days', 'Rent': 'PKR 350,000 per month'},
     'lease_notice', {'OK'}),
    ('Office Lease - Model Town', 'Lease',
     {'Parties': 'Khan & Associates; Model Town Estates', 'Notice period': '30 days'},
     'lease_notice', {'ISSUE', 'UNCLEAR'}),     # "usually require ninety days": either reading is defensible
    ('NDA - Crescent Bank', 'NDA',
     {'Parties': 'Khan & Associates; Crescent Bank', 'Term': '2 years', 'Notice period': '30 days'},
     'nda_term', {'OK'}),
    ('Employment Contract - Hira Ahmed', 'Employment contract',
     {'Parties': 'Khan & Associates; Hira Ahmed', 'Notice period': '1 month', 'Salary': 'PKR 120,000 per month'},
     None, set()),
    ('Payment Receipt - Stationery', 'Receipt',
     {'Parties': 'Al-Noor Stationers; Khan & Associates', 'Amount': 'PKR 8,500', 'Date': '2025-04-03'},
     None, set()),
]


def rule_of(quote):
    q = ' '.join(quote.lower().split())
    if 'five years' in q or 'two years' in q:
        return 'nda_term'
    if 'ninety days' in q:
        return 'lease_notice'
    if 'thirty days' in q:
        return 'notice'
    if 'stamp' in q:
        return 'stamp'
    if 'signed nda' in q:
        return 'nda_use'
    return 'other'


def passages():
    doc = SimpleNamespace(title='Contracts Handbook')
    return [SimpleNamespace(text=t, page_start=i, version=SimpleNamespace(document=doc)) for i, t in enumerate(HANDBOOK, 1)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pause', type=float, default=12.0)
    args = ap.parse_args()
    ps = passages()
    rows = []
    for i, (title, kind, facts, target, accepted) in enumerate(CASES, 1):
        if i > 1:
            time.sleep(args.pause)
        text = '\n'.join(f'- {k}: {v}' for k, v in facts.items())
        started = time.perf_counter()
        try:
            found = judge(title, kind, text, ps)
            error = None
        except llm.LLMError as exc:
            found, error = [], str(exc)[:200]
        secs = time.perf_counter() - started
        verdicts = [(rule_of(f['quote']), f['status']) for f in found]
        got = next((s for r, s in verdicts if r == target), None) if target else None
        correct = (got in accepted) if target else True
        expect_issue = target is not None and accepted == {'ISSUE'}
        false_issues = [r for r, s in verdicts if s == 'ISSUE' and r != target]
        if target and got == 'ISSUE' and 'ISSUE' not in accepted:
            false_issues.append(target)
        rows.append({'title': title, 'target': target, 'accepted': sorted(a or 'none' for a in accepted), 'got': got,
                     'correct': correct, 'expect_issue': expect_issue, 'flagged': any(s == 'ISSUE' for _, s in verdicts),
                     'false_issues': false_issues, 'findings': [
                         {'rule': f['rule'], 'status': f['status'], 'detail': f['detail'], 'quote': f['quote']} for f in found],
                     'seconds': round(secs, 1), 'error': error})
        print(f'{i:2d}. {title:40s} target={target!s:12s} got={got!s:8s} {"ok" if correct else "WRONG"}'
              f'{"  false issue: " + ", ".join(false_issues) if false_issues else ""}{"  ERROR " + error if error else ""}')

    scored = [r for r in rows if not r['error']]
    targeted = [r for r in scored if r['target']]
    must_flag = [r for r in scored if r['expect_issue']]
    flagged = [r for r in scored if r['flagged']]
    tp = sum(r['flagged'] and r['expect_issue'] for r in scored)
    # Model Town lease (issue or unclear both accepted) is left out of the precision count
    flagged_scored = [r for r in flagged if r['expect_issue'] or 'ISSUE' not in r['accepted']]
    summary = {
        'cases': len(rows), 'errors': len(rows) - len(scored),
        'target_verdict_accuracy': round(sum(r['correct'] for r in targeted) / len(targeted), 3) if targeted else None,
        'target_correct': sum(r['correct'] for r in targeted), 'targeted': len(targeted),
        'issue_recall': round(tp / len(must_flag), 3) if must_flag else None,
        'issue_precision': round(tp / len(flagged_scored), 3) if flagged_scored else None,
        'contracts_with_false_issues': sum(bool(r['false_issues']) for r in scored),
        'findings_total': sum(len(r['findings']) for r in scored),
        'mean_seconds': round(sum(r['seconds'] for r in scored) / len(scored), 1) if scored else None,
    }
    print('\n', summary)
    save('policy_check', {'model': f'{settings.LLM_PROVIDER}/{settings.LLM_MODEL}', 'summary': summary, 'cases': rows})


if __name__ == '__main__':
    main()
