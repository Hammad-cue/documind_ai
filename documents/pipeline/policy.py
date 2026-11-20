"""
Policy compliance check: compare a record's extracted facts with the rules written in the organization's
policy documents (reference documents marked "use as policy", e.g. an internal contracts handbook).

Each finding names the rule, says whether the record complies (OK / ISSUE / UNCLEAR), explains why in one
sentence and quotes the rule with its page, so a person can verify it. Like extracted fields, the quote is
checked against the policy text (grounding); findings whose rule cannot be found in the policy are dropped.
"""
from django.utils import timezone

from ai import llm
from documents.models import Chunk, Document, PolicyFinding
from documents.schema import FIELD_LABELS

from .understanding import ground

MAX_PASSAGES = 12


def policy_documents(organization_id):
    return Document.objects.filter(organization_id=organization_id, use_as_policy=True, is_archived=False,
                                   current_version__isnull=False)


def _passages(record, facts_text, policies):
    """All policy passages if there are few; otherwise the ones closest in meaning to the record."""
    qs = Chunk.objects.filter(version_id__in=policies.values('current_version_id')).select_related('version__document')
    if qs.count() <= MAX_PASSAGES:
        return list(qs.order_by('version_id', 'sequence'))
    from pgvector.django import CosineDistance

    from ai.embeddings import embed_query
    q = embed_query(f'{record.doc_type} {record.title}\n{facts_text}')
    return list(qs.annotate(d=CosineDistance('embedding', q)).order_by('d')[:MAX_PASSAGES])


def judge(title, doc_type, facts, passages):
    """Ask the LLM which policy rules apply and whether the facts comply. Returns grounded, de-duplicated
    findings: [{'rule', 'status', 'detail', 'quote', 'passage'}] (passage = the chunk holding the rule)."""
    # passages are labelled P1, P2... so they cannot be confused with the policy's own section numbers
    numbered = '\n\n'.join(f'[P{i}] {c.version.document.title}, page {c.page_start}\n{c.text}'
                           for i, c in enumerate(passages, 1))
    prompt = f"""You check an organization's contract against its own internal policies.

CONTRACT: {title} ({doc_type or 'agreement'})
Facts extracted from it:
{facts}

POLICY PASSAGES:
{numbered}

Work in two steps.
1. Find every SPECIFIC requirement in the policy passages that applies to this kind of contract: limits on
   duration or term, minimum or maximum notice periods, required approvals, required form (e.g. stamp paper),
   required documents. A rule written for another kind of document does not apply (e.g. a lease rule does not
   apply to an NDA, an NDA rule does not apply to a lease). Skip general legal explanations (what a contract
   is, consideration, capacity) unless the facts show a problem with them.
2. Compare each applicable requirement with the facts:
   "ok"      the facts show the contract follows it
   "issue"   the facts show it breaks it, or it needs an approval the policy requires (e.g. a longer term)
   "unclear" it applies but the facts do not say enough to decide
Compare numbers carefully: 15 days is LESS than thirty days; 7 years is MORE than five years.
Use "issue" only when the facts SHOW the requirement is broken. If the facts simply do not mention it (for
example nothing says whether stamp paper was used), the status is "unclear", not "issue".
Give exactly one finding per requirement; never split one requirement into several findings.

Return JSON: {{"findings": [{{"rule": "short name of the rule", "status": "ok|issue|unclear",
"detail": "one sentence comparing the contract's fact with the rule", "source": "P<number of the passage>",
"quote": "the rule's exact words copied from that passage (max 30 words)"}}]}}
Put issues first. At most 6 findings. If no specific requirement applies, return {{"findings": []}}."""
    out = llm.chat_json([{'role': 'user', 'content': prompt}], max_tokens=900, temperature=0.0, deadline=60)

    findings = []
    for f in (out.get('findings') or [])[:6]:
        try:
            src = passages[int(str(f.get('source', '')).strip().upper().lstrip('P')) - 1]
        except (TypeError, ValueError, IndexError):
            src = None
        status = str(f.get('status', '')).upper()
        if status not in PolicyFinding.Status.values:
            continue
        quote = str(f.get('quote') or '')[:500]
        if src is None or not ground(quote, src.text):
            # the model may have numbered the passage wrongly: look for the quote in the others
            src = next((c for c in passages if ground(quote, c.text)), None)
            if src is None:       # a rule we cannot find in the policy is not shown
                continue
        findings.append({'rule': str(f.get('rule') or '')[:300], 'status': status,
                         'detail': str(f.get('detail') or '')[:600], 'quote': quote, 'passage': src})

    # one finding per rule: if two cite the same rule text, keep the most serious one
    severity = {'ISSUE': 0, 'UNCLEAR': 1, 'OK': 2}
    norm = lambda q: ' '.join(q.lower().replace('.', ' ').split())
    kept = []
    for f in sorted(findings, key=lambda f: severity[f['status']]):
        q = norm(f['quote'])
        same_rule = any(k['passage'].version.document is f['passage'].version.document
                        and (q in norm(k['quote']) or norm(k['quote']) in q) for k in kept)
        if not same_rule:         # e.g. two findings quoting halves of the same sentence
            kept.append(f)
    return kept



def check_policies(version, notify_people=True):
    """Check one record version against the organization's policies. Returns the saved findings."""
    record = version.document
    if record.kind != Document.Kind.RECORD or record.use_as_policy or not llm.is_configured():
        return []
    policies = policy_documents(record.organization_id)
    fields = list(version.fields.all())
    if not policies.exists() or not fields:
        return []
    facts = '\n'.join(f'- {FIELD_LABELS.get(f.key, f.label)}: {f.value_text}' for f in fields)
    passages = _passages(record, facts, policies)
    if not passages:
        return []
    findings = [PolicyFinding(version=version, rule=f['rule'], status=f['status'], detail=f['detail'],
                              policy_document=f['passage'].version.document, policy_page=f['passage'].page_start,
                              policy_quote=f['quote'], grounded=True)
                for f in judge(record.title, record.doc_type, facts, passages)]

    version.policy_findings.all().delete()
    PolicyFinding.objects.bulk_create(findings)
    version.policy_checked_at = timezone.now()
    version.save(update_fields=['policy_checked_at'])

    issues = [f for f in findings if f.status == PolicyFinding.Status.ISSUE]
    if issues and notify_people:
        from notifications.models import Notification
        from notifications.service import notify, people_to_remind
        first = issues[0]
        notify(people_to_remind(record), Notification.Kind.POLICY,
               f'{record.title}: {len(issues)} policy issue{"s" if len(issues) > 1 else ""}',
               f'{first.rule}: {first.detail}', record, f'/app/documents/{record.id}',
               dedupe_key=f'policy:{version.id}:{len(issues)}')
    return findings


def recheck_organization(organization_id):
    """Run after a policy document changes: re-check every current record of the organization."""
    records = Document.objects.filter(organization_id=organization_id, kind=Document.Kind.RECORD, is_archived=False,
                                      use_as_policy=False, current_version__isnull=False).select_related('current_version')
    checked = 0
    for doc in records:
        try:
            check_policies(doc.current_version)
            checked += 1
        except llm.LLMError:
            continue
    return checked
