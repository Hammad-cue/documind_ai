"""
What changed between two versions of a document: the line-by-line difference of every page and of the
extracted facts, plus a short plain-English summary written by the LLM from that difference.
"""
import difflib

from django.core.cache import cache

from ai import llm
from documents.schema import FIELD_KEYS, FIELD_LABELS


def diff_versions(a, b):
    """Field changes and per-page text differences from version a to version b."""
    fa = {f.key: f for f in a.fields.all()}
    fb = {f.key: f for f in b.fields.all()}
    field_changes = []
    for key in FIELD_KEYS:
        va = fa[key].value_text if key in fa else None
        vb = fb[key].value_text if key in fb else None
        if va != vb:
            field_changes.append({'key': key, 'label': FIELD_LABELS[key], 'from': va, 'to': vb})
    pa = {p.number: p.text for p in a.pages.all()}
    pb = {p.number: p.text for p in b.pages.all()}
    page_changes = []
    for n in sorted(set(pa) | set(pb)):
        ta, tb = pa.get(n, ''), pb.get(n, '')
        if ta == tb:
            continue
        ratio = difflib.SequenceMatcher(None, ta, tb, autojunk=False).quick_ratio() if ta and tb else 0.0
        diff = list(difflib.unified_diff(ta.splitlines(), tb.splitlines(), lineterm='', n=0))[2:60]
        page_changes.append({'page': n, 'similarity': round(ratio, 3),
                             'status': 'added' if not ta else 'removed' if not tb else 'changed', 'diff': diff})
    return {'a': a.number, 'b': b.number, 'field_changes': field_changes, 'page_changes': page_changes,
            'pages_a': len(pa), 'pages_b': len(pb)}


def summarize(diff, title='', budget=8000):
    """2-6 bullet points describing the changes, most important first, with page references."""
    if not diff['field_changes'] and not diff['page_changes']:
        return 'The two versions are identical.'
    if not llm.is_configured():
        return ''
    facts = '\n'.join(f"- {c['label']}: {c['from'] or '(none)'} -> {c['to'] or '(none)'}" for c in diff['field_changes'])
    pages, used = [], 0
    for p in diff['page_changes']:
        block = f"Page {p['page']} ({p['status']}):\n" + '\n'.join(p['diff'])
        if used + len(block) > budget:
            pages.append(f"(further changes on {len(diff['page_changes']) - len(pages)} more page(s) not shown)")
            break
        pages.append(block)
        used += len(block)
    prompt = f"""Summarize what changed between version {diff['a']} and version {diff['b']} of the document "{title}".
Lines starting with '-' were removed, lines starting with '+' were added.

Changed key facts:
{facts or '(none)'}

Text differences:
{chr(10).join(pages)}

Write 2 to 6 short bullet points in plain English, most important first (money, dates, duration, parties,
obligations, termination). Give the old and the new value where there is one, and the page like "(p. 2)".
Mention only what the differences show; ignore pure formatting or line-break changes. Markdown bullets only."""
    return llm.chat([{'role': 'user', 'content': prompt}], max_tokens=500, temperature=0.1, deadline=40).strip()


def summary_between(a, b, title=''):
    """Summary for any pair of versions; cached, because versions never change once processed."""
    key = f'change-summary:{a.id}:{b.id}'
    text = cache.get(key)
    if text is None:
        text = summarize(diff_versions(a, b), title)
        if text:
            cache.set(key, text, 30 * 24 * 3600)
    return text


def summarize_new_version(version):
    """Called after a new version is processed: compare it with the previous ready version and store the summary."""
    previous = version.document.versions.filter(status='READY', number__lt=version.number).order_by('-number').first()
    if previous is None:
        return ''
    text = summarize(diff_versions(previous, version), version.document.title)
    version.change_summary = text
    version.change_summary_from = previous.number
    version.save(update_fields=['change_summary', 'change_summary_from'])
    return text
