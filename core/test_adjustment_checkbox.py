from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group,Permission
from .models import UserAccess
from .user_management import UserForm,adjustment_permissions,editable_permissions
from .accounting import can_adjust_calculations

class AdjustmentCheckboxTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('checkbox-admin',password='Secure-Password-123!')
        self.user=get_user_model().objects.create_user('checkbox-user')
        UserAccess.objects.create(user=self.user,scope='own')
        self.client.force_login(self.admin)

    def save(self,enabled):
        data={'username':self.user.username,'first_name':'','last_name':'','email':'','scope':'own','is_active':'on'}
        if enabled:data['allow_calculation_adjustments']='on'
        return self.client.post(f'/users/{self.user.pk}/edit/',data)

    def test_checkbox_grants_and_revokes_backend_permissions(self):
        self.assertEqual(self.save(True).status_code,302)
        user=get_user_model().objects.get(pk=self.user.pk)
        self.assertTrue(can_adjust_calculations(user))
        self.assertEqual(user.travel_access.scope,'own')
        self.assertEqual(self.save(False).status_code,302)
        self.assertFalse(can_adjust_calculations(get_user_model().objects.get(pk=self.user.pk)))

    def test_permission_matrix_does_not_duplicate_checkbox(self):
        self.assertFalse(editable_permissions().filter(content_type__model='accountingadjustment').exists())
        response=self.client.get(f'/users/{self.user.pk}/edit/')
        self.assertContains(response,'name="allow_calculation_adjustments"')
        self.assertNotContains(response,'Μετακινήσεις (Λογιστήριο) —')

    def test_existing_group_permissions_and_inactive_accounts_display_correctly(self):
        group=Group.objects.create(name='Existing accounting rights')
        group.permissions.set(adjustment_permissions());self.user.groups.add(group)
        self.user.is_active=False;self.user.save()
        form=UserForm(instance=self.user)
        self.assertTrue(form.initial['allow_calculation_adjustments'])
        self.assertFalse(can_adjust_calculations(self.user))

    def test_ordinary_user_cannot_grant_permission_to_self(self):
        self.client.force_login(self.user)
        self.assertEqual(self.save(True).status_code,403)
        self.assertFalse(adjustment_permissions().filter(user=self.user).exists())
