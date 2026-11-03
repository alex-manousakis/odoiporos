from django.db.models import Q
from .models import Employee, UserAccess


def policy(user):
    return UserAccess.objects.filter(user=user).first() if user.is_authenticated else None


def employee_scope(user):
    qs=Employee.objects.all()
    if not user.is_active:
        return qs.none()
    if user.is_superuser:
        return qs
    access=policy(user)
    if access:
        if access.scope=='all':
            return qs
        if access.scope=='department':
            return qs.filter(Q(user=user)|Q(department__in=access.departments.all()))
        return qs.filter(user=user)
    # Preserve existing accounts until explicitly configured in user management.
    if user.has_perm('core.view_travel') or user.has_perm('core.add_travel'):
        return qs
    return qs.filter(user=user)


def can_action(user,action):
    if not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if policy(user):
        return user.has_perm(f'core.{action}_travel')
    return user.has_perm(f'core.{action}_travel') or Employee.objects.filter(user=user,is_active=True).exists()


def navigation(request):
    return {"can_create_travel": can_action(request.user, "add")}
