"""Orchestrates the full ingestion pipeline for one DocumentVersion."""
import time
import traceback

from django.db import connection, transaction
from django.utils import timezone

from ai import clauses, embeddings, llm
from documents.models import Chunk, Document, DocumentVersion, Page, RecordField

from . import changes, chunking, extract, policy, understanding


class _Log:
    def __init__(self):
        self.steps = []

    def step(self, name, started, **info):
        self.steps.append({'step': name, 'ms': int((time.perf_counter() - started) * 1000), **info})


def process_version(version_id):
    version = DocumentVersion.objects.select_related('document').get(pk=version_id)
    document = version.document
    log = _Log()
    version.status = DocumentVersion.Status.PROCESSING
    version.error = ''
    version.save(update_fields=['status', 'error'])

    try:
        # 1. text extraction (digital / OCR / handwriting)
        t = time.perf_counter()
        result = extract.extract(version)
        sources = {}
        for p in result.pages:
            sources[p.source] = sources.get(p.source, 0) + 1
        log.step('extract', t, pages=result.page_count, sources=sources)

        if not any(p.text.strip() for p in result.pages):
            raise extract.ExtractionError('No readable text found in the document.')

        with transaction.atomic():
            version.pages.all().delete()
            version.chunks.all().delete()
            version.fields.all().delete()
            Page.objects.bulk_create([
                Page(version=version, number=p.number, text=p.text, source=p.source, ocr_confidence=p.confidence)
                for p in result.pages
            ])
            version.page_count = result.page_count
            version.save(update_fields=['page_count'])

        # 2. classification (record vs reference)
        t = time.perf_counter()
        info = understanding.classify(result.pages, result.page_count)
        if not document.kind_locked or document.kind == Document.Kind.UNKNOWN:
            document.kind = info['kind']
        if not document.kind_locked or not document.doc_type:
            document.doc_type = info['doc_type']
        document.summary = info['summary'] or document.summary
        log.step('classify', t, kind=document.kind, doc_type=document.doc_type, method=info.get('method'),
                 user_locked=document.kind_locked)
        document.save(update_fields=['kind', 'doc_type', 'summary', 'updated_at'])

        # 3. structure-aware chunking + embeddings
        t = time.perf_counter()
        chunks = chunking.chunk_pages([(p.number, p.text) for p in result.pages])
        vectors = embeddings.embed_texts([f'{c.section_path}\n{c.text}' if c.section_path else c.text for c in chunks])
        labels = [(None, None)] * len(chunks)
        if document.kind == Document.Kind.RECORD and clauses.is_available():
            labels = clauses.classify([c.text for c in chunks])
        Chunk.objects.bulk_create([
            Chunk(version=version, sequence=c.sequence, section_path=c.section_path[:500], heading=c.heading[:300],
                  text=c.text, page_start=c.page_start, page_end=c.page_end, embedding=v,
                  clause_label=lab or '', clause_confidence=conf)
            for c, v, (lab, conf) in zip(chunks, vectors, labels)
        ])
        with connection.cursor() as cur:
            cur.execute(
                "UPDATE documents_chunk SET search_vector = "
                "setweight(to_tsvector('english', coalesce(section_path, '')), 'A') || "
                "setweight(to_tsvector('english', text), 'B') WHERE version_id = %s", [version.pk])
        log.step('chunk_embed', t, chunks=len(chunks), clause_model=clauses.is_available())

        # 4. structured record extraction (records only)
        if document.kind == Document.Kind.RECORD:
            t = time.perf_counter()
            if llm.is_configured():
                try:
                    fields = understanding.extract_fields(result.pages)
                    RecordField.objects.bulk_create([RecordField(version=version, **f) for f in fields])
                    log.step('extract_fields', t, fields=len(fields),
                             needs_review=sum(f['status'] == 'NEEDS_REVIEW' for f in fields))
                except llm.LLMError as exc:
                    log.step('extract_fields', t, error=str(exc)[:300])
            else:
                log.step('extract_fields', t, skipped='LLM not configured')

        # 5. publish: this version becomes the searchable one
        version.status = DocumentVersion.Status.READY
        version.processed_at = timezone.now()
        version.processing_log = log.steps
        version.save(update_fields=['status', 'processed_at', 'processing_log'])
        latest_ready = document.versions.filter(status=DocumentVersion.Status.READY).order_by('-number').first()
        document.current_version = latest_ready
        document.save(update_fields=['current_version', 'updated_at'])

        # 6. extras that need the published version; failures here never undo the processing above
        extras = []
        if version.number > 1:
            t = time.perf_counter()
            try:
                changes.summarize_new_version(version)
                extras.append(('change_summary', t, {}))
            except llm.LLMError as exc:
                extras.append(('change_summary', t, {'error': str(exc)[:200]}))
        if document.kind == Document.Kind.RECORD and latest_ready == version:
            t = time.perf_counter()
            try:
                found = policy.check_policies(version)
                extras.append(('policy_check', t, {'findings': len(found),
                                                   'issues': sum(f.status == 'ISSUE' for f in found)}))
            except llm.LLMError as exc:
                extras.append(('policy_check', t, {'error': str(exc)[:200]}))
        if document.use_as_policy and latest_ready == version:
            t = time.perf_counter()
            extras.append(('policy_recheck_all_records', t, {'records': policy.recheck_organization(document.organization_id)}))
        if extras:
            for name, started, info in extras:
                log.step(name, started, **info)
            version.processing_log = log.steps
            version.save(update_fields=['processing_log'])
        return version

    except Exception as exc:
        version.status = DocumentVersion.Status.FAILED
        version.error = f'{exc.__class__.__name__}: {exc}'[:2000]
        log.steps.append({'step': 'error', 'trace': traceback.format_exc()[-1500:]})
        version.processing_log = log.steps
        version.save(update_fields=['status', 'error', 'processing_log'])
        raise
