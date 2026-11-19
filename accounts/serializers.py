from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from .models import Department, Membership, Role


class DepartmentSerializer(serializers.ModelSerializer):
    member_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Department
        fields = ('id', 'name', 'member_count')


class MemberSerializer(serializers.ModelSerializer):
    """A person in the organization (User + Membership flattened)."""
    id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True, default=None)
    full_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Membership
        fields = ('id', 'username', 'email', 'first_name', 'last_name', 'full_name', 'is_active',
                  'role', 'department', 'department_name', 'job_title', 'avatar')

    def get_avatar(self, m):
        if not m.avatar:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(m.avatar.url) if request else m.avatar.url

    def get_full_name(self, m):
        return m.user.get_full_name() or m.user.username


class MemberCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField(required=False, allow_blank=True)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=Role.choices, default=Role.EMPLOYEE)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    job_title = serializers.CharField(required=False, allow_blank=True, max_length=120)

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError('This username is already taken.')
        return v

    def validate_password(self, v):
        validate_password(v)
        return v


class MemberUpdateSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=Role.choices, required=False)
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), required=False, allow_null=True)
    job_title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    is_active = serializers.BooleanField(required=False)


class RegisterOrganizationSerializer(serializers.Serializer):
    organization_name = serializers.CharField(max_length=200)
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(write_only=True)

    def validate_username(self, v):
        if User.objects.filter(username__iexact=v).exists():
            raise serializers.ValidationError('This username is already taken.')
        return v

    def validate_email(self, v):
        if User.objects.filter(email__iexact=v).exists():
            raise serializers.ValidationError('This email is already registered.')
        return v

    def validate_password(self, v):
        validate_password(v)
        return v


class MeSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    email = serializers.EmailField(required=False)
    job_title = serializers.CharField(required=False, allow_blank=True, max_length=120)
    avatar = serializers.ImageField(required=False, allow_null=True)

    def validate_avatar(self, f):
        if f and f.size > 2 * 1024 * 1024:
            raise serializers.ValidationError('Avatar must be 2 MB or smaller.')
        return f


def me_payload(user, request=None):
    m = user.membership
    avatar = m.avatar.url if m.avatar else None
    if avatar and request is not None:
        avatar = request.build_absolute_uri(avatar)
    return {
        'id': user.id, 'username': user.username, 'email': user.email,
        'first_name': user.first_name, 'last_name': user.last_name,
        'full_name': user.get_full_name() or user.username,
        'job_title': m.job_title, 'avatar': avatar,
        'role': m.role, 'role_label': m.get_role_display(),
        'organization': {'id': m.organization_id, 'name': m.organization.name},
        'department': {'id': m.department_id, 'name': m.department.name} if m.department_id else None,
        'can': {
            'upload': m.can_upload, 'verify': m.can_verify, 'view_audit': m.can_view_audit,
            'manage_team': m.is_admin, 'see_everything': m.sees_everything,
        },
    }
