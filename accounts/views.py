import uuid

from django.contrib.auth.models import User
from django.db import transaction
from django.db.models import Count
from django.utils.text import slugify
from rest_framework import status, viewsets
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from audit.models import AuditEvent
from audit.service import record

from .models import Department, Membership, Organization, Role
from .permissions import IsOrgAdmin, IsOrgMember
from .serializers import (DepartmentSerializer, MemberCreateSerializer, MemberSerializer, MemberUpdateSerializer,
                          MeSerializer, RegisterOrganizationSerializer, me_payload)


class RegisterOrganizationView(APIView):
    """Creates a new organization and makes the person who registers its first admin."""
    permission_classes = [AllowAny]

    def post(self, request):
        s = RegisterOrganizationSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        with transaction.atomic():
            slug = f"{slugify(d['organization_name'])[:60] or 'org'}-{uuid.uuid4().hex[:6]}"
            org = Organization.objects.create(name=d['organization_name'], slug=slug)
            user = User.objects.create_user(username=d['username'], email=d['email'], password=d['password'],
                                            first_name=d.get('first_name', ''), last_name=d.get('last_name', ''))
            Membership.objects.create(user=user, organization=org, role=Role.ADMIN)
        return Response({'detail': 'Organization created. You can now sign in.'}, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            user = User.objects.filter(username=request.data.get('username')).first()
            if user is not None and not hasattr(user, 'membership'):
                return Response({'detail': 'This account is not part of an organization.'}, status=403)
            if user is not None:
                record(user, AuditEvent.Action.LOGIN, request=request, label=user.username)
        return response


class MeView(APIView):
    permission_classes = [IsOrgMember]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get(self, request):
        return Response(me_payload(request.user, request))

    def patch(self, request):
        s = MeSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        user, m = request.user, request.user.membership
        for f in ('first_name', 'last_name', 'email'):
            if f in s.validated_data:
                setattr(user, f, s.validated_data[f])
        user.save()
        if 'job_title' in s.validated_data:
            m.job_title = s.validated_data['job_title']
        if 'avatar' in s.validated_data:
            m.avatar = s.validated_data['avatar']
        m.save()
        return Response(me_payload(user, request))


class DepartmentViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentSerializer

    def get_permissions(self):
        return [IsOrgMember()] if self.action in ('list', 'retrieve') else [IsOrgAdmin()]

    def get_queryset(self):
        org = self.request.user.membership.organization_id
        return Department.objects.filter(organization_id=org).annotate(member_count=Count('members'))

    def perform_create(self, serializer):
        dept = serializer.save(organization=self.request.user.membership.organization)
        record(self.request.user, AuditEvent.Action.DEPARTMENT_CHANGE, dept, self.request, change='created')

    def perform_update(self, serializer):
        dept = serializer.save()
        record(self.request.user, AuditEvent.Action.DEPARTMENT_CHANGE, dept, self.request, change='renamed')

    def perform_destroy(self, instance):
        record(self.request.user, AuditEvent.Action.DEPARTMENT_CHANGE, instance, self.request, change='deleted')
        instance.delete()


class MemberViewSet(viewsets.ViewSet):
    """People in the organization. Everyone can list (needed for sharing); only admins change."""

    def get_permissions(self):
        return [IsOrgMember()] if self.action == 'list' else [IsOrgAdmin()]

    def _org(self):
        return self.request.user.membership.organization

    def list(self, request):
        qs = Membership.objects.filter(organization=self._org()).select_related('user', 'department') \
            .order_by('user__username')
        return Response(MemberSerializer(qs, many=True).data)

    def create(self, request):
        s = MemberCreateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        dept = d.get('department')
        if dept is not None and dept.organization_id != self._org().id:
            return Response({'department': 'Unknown department.'}, status=400)
        with transaction.atomic():
            user = User.objects.create_user(username=d['username'], email=d.get('email', ''), password=d['password'],
                                            first_name=d.get('first_name', ''), last_name=d.get('last_name', ''))
            m = Membership.objects.create(user=user, organization=self._org(), role=d['role'], department=dept,
                                          job_title=d.get('job_title', ''))
        record(request.user, AuditEvent.Action.MEMBER_ADD, user, request, label=user.username, role=m.role)
        return Response(MemberSerializer(m).data, status=201)

    def partial_update(self, request, pk=None):
        m = Membership.objects.filter(organization=self._org(), user_id=pk).select_related('user').first()
        if m is None:
            return Response(status=404)
        s = MemberUpdateSerializer(data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        removing_admin = m.role == Role.ADMIN and (d.get('role', Role.ADMIN) != Role.ADMIN or d.get('is_active') is False)
        if removing_admin and Membership.objects.filter(organization=m.organization, role=Role.ADMIN,
                                                        user__is_active=True).count() <= 1:
            return Response({'detail': 'The organization must keep at least one active admin.'}, status=400)
        if 'department' in d and d['department'] is not None and d['department'].organization_id != m.organization_id:
            return Response({'department': 'Unknown department.'}, status=400)
        before = {'role': m.role, 'department': m.department_id, 'is_active': m.user.is_active}
        for f in ('role', 'department', 'job_title'):
            if f in d:
                setattr(m, f, d[f])
        m.save()
        if 'is_active' in d:
            m.user.is_active = d['is_active']
            m.user.save(update_fields=['is_active'])
        after = {'role': m.role, 'department': m.department_id, 'is_active': m.user.is_active}
        record(request.user, AuditEvent.Action.MEMBER_UPDATE, m.user, request, label=m.user.username,
               before=before, after=after)
        return Response(MemberSerializer(m).data)
