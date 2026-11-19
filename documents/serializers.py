from rest_framework import serializers

from .models import Document, DocumentVersion, FieldEdit, RecordField


class VersionSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DocumentVersion
        fields = ('id', 'number', 'original_filename', 'file_type', 'file_size', 'page_count', 'marked_handwritten',
                  'change_note', 'uploaded_by_name', 'uploaded_at', 'status', 'error', 'processing_log', 'processed_at')

    def get_uploaded_by_name(self, v):
        return v.uploaded_by.get_full_name() or v.uploaded_by.username if v.uploaded_by else None


class FieldSerializer(serializers.ModelSerializer):
    edit_count = serializers.IntegerField(source='edits.count', read_only=True)

    class Meta:
        model = RecordField
        fields = ('id', 'key', 'label', 'value_text', 'value_date', 'value_number', 'confidence', 'source_page',
                  'source_quote', 'grounded', 'status', 'review_reason', 'updated_at', 'edit_count')


class FieldEditSerializer(serializers.ModelSerializer):
    edited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = FieldEdit
        fields = ('id', 'old_value', 'new_value', 'old_status', 'new_status', 'reason', 'edited_by_name', 'edited_at')

    def get_edited_by_name(self, e):
        return (e.edited_by.get_full_name() or e.edited_by.username) if e.edited_by else 'system'


class DocumentListSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', default=None, read_only=True)
    uploaded_by_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    version_count = serializers.IntegerField(read_only=True, default=1)
    file_type = serializers.SerializerMethodField()
    needs_review = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Document
        fields = ('id', 'title', 'kind', 'doc_type', 'summary', 'access_level', 'department', 'department_name',
                  'uploaded_by_name', 'status', 'version_count', 'file_type', 'needs_review', 'created_at', 'updated_at')

    def _latest(self, d):
        if not hasattr(d, '_latest_cache'):
            d._latest_cache = d.latest_version
        return d._latest_cache

    def get_uploaded_by_name(self, d):
        return (d.uploaded_by.get_full_name() or d.uploaded_by.username) if d.uploaded_by else None

    def get_status(self, d):
        v = self._latest(d)
        return v.status if v else None

    def get_file_type(self, d):
        v = self._latest(d)
        return v.file_type if v else None


ROMAN = set('IVXLCDM')


def _heading_case(text):
    """'CHAPTER II' -> 'Chapter II', 'PART 3' -> 'Part 3' (Roman numerals stay upper case)."""
    words = text.split()
    return ' '.join(w if (set(w.upper()) <= ROMAN or any(ch.isdigit() for ch in w)) and i else w.capitalize()
                    for i, w in enumerate(words))


class DocumentDetailSerializer(DocumentListSerializer):
    versions = VersionSerializer(many=True, read_only=True)
    current_version_number = serializers.IntegerField(source='current_version.number', default=None, read_only=True)
    record_fields = serializers.SerializerMethodField()
    clauses = serializers.SerializerMethodField()
    allowed_users = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()

    outline = serializers.SerializerMethodField()

    class Meta(DocumentListSerializer.Meta):
        fields = DocumentListSerializer.Meta.fields + ('kind_locked', 'versions', 'current_version_number',
                                                       'record_fields', 'clauses', 'allowed_users', 'can_edit', 'outline')

    def get_outline(self, d):
        """Top-level sections of a reference document (e.g. the chapters of an Act) with the page each starts on.
        A table of contents mentions every chapter first, so the *last* run of passages under a heading is the
        real chapter."""
        if d.kind != 'REFERENCE' or not d.current_version_id:
            return None
        runs, cur, passages = {}, None, 0
        for c in d.current_version.chunks.order_by('sequence').values('section_path', 'page_start', 'text'):
            passages += 1
            top = c['section_path'].split(' > ')[0].strip()
            if not top:
                cur = None
                continue
            if cur is None or cur['key'] != top:
                lines = [l.strip() for l in c['text'].splitlines() if l.strip()]
                name = lines[1] if len(lines) > 1 and lines[0] == top and lines[1].isupper() and len(lines[1]) > 3 else ''
                cur = {'key': top, 'title': _heading_case(top), 'name': name.capitalize(), 'page': c['page_start']}
                runs[top] = cur          # later runs replace earlier ones
        sections = [{k: r[k] for k in ('title', 'name', 'page')} for r in sorted(runs.values(), key=lambda r: r['page'])][:60]
        return {'sections': sections, 'passages': passages, 'pages': d.current_version.page_count}

    def get_clauses(self, d):
        """Clause types found by the fine-tuned classifier, grouped: [{label, count, pages, snippet, confidence}]."""
        if not d.current_version_id:
            return []
        groups = {}
        for c in d.current_version.chunks.exclude(clause_label='').order_by('sequence'):
            g = groups.setdefault(c.clause_label, {'label': c.clause_label, 'count': 0, 'pages': [], 'snippet': c.text[:300],
                                                   'confidence': c.clause_confidence or 0})
            g['count'] += 1
            if c.page_start not in g['pages']:
                g['pages'].append(c.page_start)
            g['confidence'] = max(g['confidence'], c.clause_confidence or 0)
        return sorted(groups.values(), key=lambda g: g['pages'][0])

    def get_record_fields(self, d):
        if not d.current_version_id:
            return []
        return FieldSerializer(d.current_version.fields.all(), many=True).data

    def get_allowed_users(self, d):
        return [{'id': u.id, 'username': u.username, 'full_name': u.get_full_name() or u.username}
                for u in d.allowed_users.all()]

    def get_can_edit(self, d):
        from .access import can_edit
        return can_edit(self.context['request'].user, d)


class DocumentUpdateSerializer(serializers.Serializer):
    title = serializers.CharField(max_length=255, required=False)
    doc_type = serializers.CharField(max_length=120, required=False, allow_blank=True)
    kind = serializers.ChoiceField(choices=[Document.Kind.RECORD, Document.Kind.REFERENCE], required=False)
    access_level = serializers.ChoiceField(choices=Document.Access.choices, required=False)
    department = serializers.IntegerField(required=False, allow_null=True)
    allowed_user_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
