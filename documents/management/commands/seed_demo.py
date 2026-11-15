"""
Create a demo organization with users, departments and sample documents.

    python manage.py seed_demo            # create (skips if it already exists)
    python manage.py seed_demo --reset    # delete the demo org and recreate it

Demo users (password = DEMO_PASSWORD env var, default below):
    demo_admin (Admin), demo_manager (Manager, Legal), demo_employee (Employee, Legal),
    demo_hr (Employee, HR), demo_auditor (Auditor)
"""
import hashlib
import os

from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Department, Membership, Organization, Role
from documents.models import Document, DocumentVersion
from documents.pipeline.queue import enqueue
from documents.testutils import make_pdf

DEMO_PASSWORD = os.environ.get('DEMO_PASSWORD', 'DemoPass-2026!')
ORG_SLUG = 'demo-khan-associates'

NDA = [
    'MUTUAL NON-DISCLOSURE AGREEMENT\n\nThis Mutual Non-Disclosure Agreement (the "Agreement") is made between\n'
    'Khan & Associates, Lahore ("Company") and Acme Corp (Private) Limited, Karachi ("Acme").\n\n'
    '1. Purpose\nThe parties wish to evaluate a possible software development partnership and may\n'
    'disclose confidential information to each other for that purpose.\n\n'
    '2. Definition of Confidential Information\nConfidential Information means all technical, financial and business\n'
    'information disclosed by either party, whether oral, written or electronic, that is marked\nconfidential or would reasonably be understood to be confidential.',
    '3. Obligations\nThe receiving party shall hold Confidential Information in strict confidence and\n'
    'shall not disclose it to any third party without prior written consent.\n\n'
    '4. Term\nThis Agreement takes effect on 1 April 2025 and remains in force for a period of\n'
    'two (2) years, ending on 31 March 2027.\n\n'
    '5. Termination\nEither party may terminate this Agreement by giving thirty (30) days written notice.\n\n'
    '6. Governing Law\nThis Agreement is governed by the laws of Pakistan and the courts of Lahore\nshall have exclusive jurisdiction.',
    'IN WITNESS WHEREOF the parties have signed this Agreement on 12 March 2025.\n\n'
    'For Khan & Associates: Ali Khan, Managing Partner\n'
    'For Acme Corp (Private) Limited: Sara Malik, Director Operations',
]

LEASE = [
    'LEASE AGREEMENT (OFFICE PREMISES)\n\nThis Lease Agreement is made at Lahore between Mr. Imran Qureshi ("Lessor")\n'
    'and Khan & Associates ("Lessee") for the office at 45-B Gulberg III, Lahore.\n\n'
    '1. Rent\nThe monthly rent is PKR 350,000, payable in advance on the 5th of every month.\n\n'
    '2. Security Deposit\nThe Lessee has paid a refundable security deposit of PKR 1,050,000.',
    '3. Period of Lease\nThe lease commences on 1 July 2024 and expires on 30 June 2027.\n'
    'The lease shall renew automatically for one year unless either party objects in writing.\n\n'
    '4. Termination\nEither party may terminate the lease with ninety (90) days written notice.\n\n'
    'Signed at Lahore on 20 June 2024.\nLessor: Imran Qureshi    Lessee: Ali Khan, Managing Partner',
]

EMPLOYMENT = [
    'EMPLOYMENT CONTRACT\n\nThis contract is between Khan & Associates ("Employer") and Ms. Hira Ahmed ("Employee").\n\n'
    '1. Position\nThe Employee is appointed as Associate Lawyer in the Corporate Department.\n\n'
    '2. Salary\nThe gross monthly salary is PKR 280,000.\n\n'
    '3. Probation\nThe first three months of employment are a probation period.\n\n'
    '4. Notice\nAfter probation, either party may end employment with one month written notice.\n\n'
    'Effective date: 1 September 2025. Signed on 25 August 2025 by Ali Khan and Hira Ahmed.',
]

HANDBOOK = [
    'KHAN & ASSOCIATES CONTRACTS HANDBOOK\nInternal reference guide for associates\n\n'
    'CHAPTER I\nFORMATION OF CONTRACTS\n\n'
    '1. Offer and acceptance\nA contract is formed when a clear offer is accepted without changes. An acceptance that\n'
    'adds new terms is a counter-offer and does not create a contract until it is accepted.\n\n'
    '2. Consideration\nEvery agreement must be supported by consideration, meaning something of value given\n'
    'by each party. An agreement made without consideration is void, except where it is in writing,\n'
    'registered, and made out of natural love and affection between near relatives.',
    '3. Capacity\nA person who is a minor or of unsound mind cannot enter into a binding contract.\n'
    'Agreements with minors are void and cannot be enforced against them.\n\n'
    'CHAPTER II\nCONFIDENTIALITY AND NDAS\n\n'
    '4. When to use an NDA\nAssociates must put a signed NDA in place before sharing any client information with\n'
    'a prospective partner, vendor or investor.\n\n'
    '5. Standard NDA term\nOur standard NDA term is two years. Any term longer than five years needs partner approval.',
    'CHAPTER III\nTERMINATION AND NOTICE\n\n'
    '6. Notice periods\nCommercial contracts should allow termination with at least thirty days written notice.\n'
    'Leases of office premises usually require ninety days notice.\n\n'
    '7. Stamp duty\nAgreements executed in Punjab must be written on stamp paper of the correct value under the\n'
    'Stamp Act. An unstamped agreement may not be admissible as evidence until the duty and penalty are paid.',
]


def handwritten_note_png():
    """A 'handwritten' receipt rendered with a script font (for demonstrating the handwriting path)."""
    from io import BytesIO
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new('RGB', (1400, 900), (252, 250, 240))
    d = ImageDraw.Draw(img)
    font_path = 'C:/Windows/Fonts/segoesc.ttf'
    font = ImageFont.truetype(font_path, 44) if os.path.exists(font_path) else ImageFont.load_default()
    lines = ['Receipt of Security Deposit', '', 'I, Imran Qureshi, received PKR 1,050,000 from',
             'Khan & Associates as security deposit for the office', 'at 45-B Gulberg III, Lahore.', '',
             'Dated: 20 June 2024', 'Signature: Imran Qureshi']
    y = 80
    for line in lines:
        d.text((90, y), line, font=font, fill=(25, 35, 90))
        y += 90
    buf = BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Create a demo organization with sample legal documents.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true')

    def handle(self, *args, **opts):
        if opts['reset']:
            Organization.objects.filter(slug=ORG_SLUG).delete()
            User.objects.filter(username__startswith='demo_').delete()
        if Organization.objects.filter(slug=ORG_SLUG).exists():
            self.stdout.write('Demo organization already exists (use --reset to recreate).')
            return

        with transaction.atomic():
            org = Organization.objects.create(name='Khan & Associates (Demo)', slug=ORG_SLUG)
            legal = Department.objects.create(organization=org, name='Legal')
            hr = Department.objects.create(organization=org, name='HR')
            users = {}
            for username, role, dept, first, last, title in [
                ('demo_admin', Role.ADMIN, None, 'Ali', 'Khan', 'Managing Partner'),
                ('demo_manager', Role.MANAGER, legal, 'Sana', 'Riaz', 'Senior Associate'),
                ('demo_employee', Role.EMPLOYEE, legal, 'Bilal', 'Ahmed', 'Associate'),
                ('demo_hr', Role.EMPLOYEE, hr, 'Ayesha', 'Noor', 'HR Officer'),
                ('demo_auditor', Role.AUDITOR, None, 'Usman', 'Tariq', 'External Auditor'),
            ]:
                u = User.objects.create_user(username=username, password=DEMO_PASSWORD, first_name=first, last_name=last,
                                             email=f'{username}@example.com')
                Membership.objects.create(user=u, organization=org, role=role, department=dept, job_title=title)
                users[username] = u

        files = [
            ('NDA - Acme Corp', 'nda_acme.pdf', make_pdf(NDA), Document.Access.ORG, legal, None, False, 'demo_manager'),
            ('Office Lease - Gulberg Lahore', 'office_lease.pdf', make_pdf(LEASE), Document.Access.ORG, None, None, False, 'demo_admin'),
            ('Employment Contract - Hira Ahmed', 'employment_hira.pdf', make_pdf(EMPLOYMENT), Document.Access.DEPARTMENT, hr, None, False, 'demo_hr'),
            ('Contracts Handbook', 'contracts_handbook.pdf', make_pdf(HANDBOOK), Document.Access.ORG, legal, Document.Kind.REFERENCE, False, 'demo_manager'),
            ('Security Deposit Receipt (handwritten)', 'deposit_receipt.png', handwritten_note_png(), Document.Access.ORG, None, None, True, 'demo_admin'),
        ]
        for title, filename, content, access, dept, kind, handwritten, uploader in files:
            doc = Document.objects.create(organization=org, title=title, access_level=access, department=dept,
                                          uploaded_by=users[uploader], kind=kind or Document.Kind.UNKNOWN,
                                          kind_locked=bool(kind))
            v = DocumentVersion(document=doc, number=1, original_filename=filename,
                                file_type='IMAGE' if filename.endswith('.png') else 'PDF', file_size=len(content),
                                sha256=hashlib.sha256(content).hexdigest(), uploaded_by=users[uploader],
                                marked_handwritten=handwritten)
            v.file.save(filename, ContentFile(content), save=False)
            v.save()
            enqueue(v)
            self.stdout.write(f'  queued {title}')

        self.stdout.write(self.style.SUCCESS(
            'Demo organization created. Users: demo_admin, demo_manager, demo_employee, demo_hr, demo_auditor '
            '(password: DEMO_PASSWORD env var or the default in documents/management/commands/seed_demo.py). '
            'Make sure `python manage.py run_worker` is running to process the documents.'))
