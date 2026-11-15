"""Helpers shared by the test suites: an org with departments/roles and tiny generated files."""
import io

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile

from accounts.models import Department, Membership, Organization, Role


def make_pdf(pages):
    """Build a minimal valid PDF with one text page per string (no external libraries)."""
    objects = []

    def add(body):
        objects.append(body)
        return len(objects)

    font = add(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
    page_ids, kids_placeholder = [], None
    pages_id = add(b'')  # placeholder, filled below
    for text in pages:
        lines = text.split('\n')
        ops = ['BT', '/F1 11 Tf', '14 TL', '50 780 Td']
        for line in lines:
            safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            ops.append(f'({safe}) Tj T*')
        ops.append('ET')
        stream = '\n'.join(ops).encode('latin-1')
        content = add(b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream')
        page_ids.append(add(f'<< /Type /Page /Parent {pages_id} 0 R /MediaBox [0 0 612 842] '
                            f'/Resources << /Font << /F1 {font} 0 R >> >> /Contents {content} 0 R >>'.encode()))
    kids = ' '.join(f'{i} 0 R' for i in page_ids)
    objects[pages_id - 1] = f'<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>'.encode()
    catalog = add(f'<< /Type /Catalog /Pages {pages_id} 0 R >>'.encode())

    out = io.BytesIO()
    out.write(b'%PDF-1.4\n')
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f'{i} 0 obj\n'.encode() + body + b'\nendobj\n')
    xref = out.tell()
    out.write(f'xref\n0 {len(objects) + 1}\n0000000000 65535 f \n'.encode())
    for off in offsets:
        out.write(f'{off:010d} 00000 n \n'.encode())
    out.write(f'trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode())
    return out.getvalue()


def make_docx(paragraphs):
    import docx
    d = docx.Document()
    for p in paragraphs:
        d.add_paragraph(p)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def pdf_upload(name, pages):
    return SimpleUploadedFile(name, make_pdf(pages), content_type='application/pdf')


def docx_upload(name, paragraphs):
    return SimpleUploadedFile(name, make_docx(paragraphs),
                              content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document')


class OrgFixture:
    """Org A: admin, legal manager, legal employee, hr employee, auditor. Org B: outsider."""

    def __init__(self):
        self.org = Organization.objects.create(name='Acme Legal', slug='acme-legal')
        self.legal = Department.objects.create(organization=self.org, name='Legal')
        self.hr = Department.objects.create(organization=self.org, name='HR')
        self.admin = self._user('admin', Role.ADMIN, None)
        self.manager = self._user('legal_manager', Role.MANAGER, self.legal)
        self.legal_emp = self._user('legal_emp', Role.EMPLOYEE, self.legal)
        self.hr_emp = self._user('hr_emp', Role.EMPLOYEE, self.hr)
        self.auditor = self._user('auditor', Role.AUDITOR, None)
        self.other_org = Organization.objects.create(name='Other Co', slug='other-co')
        self.outsider = self._user('outsider', Role.ADMIN, None, org=self.other_org)

    def _user(self, username, role, dept, org=None):
        u = User.objects.create_user(username=username, password='Test-pass-123')
        Membership.objects.create(user=u, organization=org or self.org, role=role, department=dept)
        return u
