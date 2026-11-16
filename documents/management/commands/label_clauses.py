from django.core.management.base import BaseCommand

from ai import clauses
from documents.models import Chunk, Document


class Command(BaseCommand):
    help = 'Label the clauses of already-processed records with the fine-tuned clause classifier.'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Relabel chunks that already have a label.')

    def handle(self, *args, **opts):
        if not clauses.is_available():
            self.stderr.write('No trained model found at CLAUSE_MODEL_DIR. Train one with ml/train_clause_classifier.py first.')
            return
        docs = Document.objects.filter(kind=Document.Kind.RECORD, current_version__isnull=False, is_archived=False)
        chunks = Chunk.objects.filter(version_id__in=docs.values('current_version_id'))
        if not opts['all']:
            chunks = chunks.filter(clause_label='')
        chunks = list(chunks)
        labels = clauses.classify([c.text for c in chunks])
        for c, (label, conf) in zip(chunks, labels):
            c.clause_label, c.clause_confidence = label or '', conf
        Chunk.objects.bulk_update(chunks, ['clause_label', 'clause_confidence'])
        found = sum(1 for lab, _ in labels if lab)
        self.stdout.write(self.style.SUCCESS(f'Labelled {found} of {len(chunks)} clauses.'))
