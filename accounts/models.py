from django.contrib.auth.models import User
from django.db import models


class Organization(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Department(models.Model):
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='departments')
    name = models.CharField(max_length=120)

    class Meta:
        unique_together = ('organization', 'name')
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.organization})'


class Role(models.TextChoices):
    ADMIN = 'ADMIN', 'Admin'            # manages people, sees everything in the org
    MANAGER = 'MANAGER', 'Manager'      # uploads, verifies extracted records
    EMPLOYEE = 'EMPLOYEE', 'Employee'   # uploads and queries what they can access
    AUDITOR = 'AUDITOR', 'Auditor'      # read-only access to everything + audit log


class Membership(models.Model):
    """Links a Django user to exactly one organization with one role."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='membership')
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE, related_name='memberships')
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)
    job_title = models.CharField(max_length=120, blank=True)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} @ {self.organization} [{self.role}]'

    # ---- capability helpers (single source of truth for RBAC) ----
    @property
    def is_admin(self):
        return self.role == Role.ADMIN

    @property
    def sees_everything(self):
        return self.role in (Role.ADMIN, Role.AUDITOR)

    @property
    def can_upload(self):
        return self.role in (Role.ADMIN, Role.MANAGER, Role.EMPLOYEE)

    @property
    def can_verify(self):
        return self.role in (Role.ADMIN, Role.MANAGER)

    @property
    def can_view_audit(self):
        return self.role in (Role.ADMIN, Role.AUDITOR)
