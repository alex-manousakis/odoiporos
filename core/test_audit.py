from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.test import TestCase, Client
from .models import Employee, AuditEvent
from .audit import current, emit


class AuditTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser('auditor',password='S3cure-test-password')
        self.user=get_user_model().objects.create_user('ordinary',password='S3cure-test-password')
        self.employee=Employee.objects.create(display_name='Sensitive Person',tax_number='SECRET-TAX')

    def test_employee_reads_are_attributed_without_personal_values_or_query(self):
        self.client.force_login(self.admin)
        response=self.client.get('/employees/',{'q':'Sensitive'})
        self.assertEqual(response.status_code,200)
        self.assertIn('no-store',response['Cache-Control'])
        events=AuditEvent.objects.filter(request_id=response['X-Audit-Request-ID'])
        self.assertTrue(events.filter(action='view',target_type='core.employee',target_id=str(self.employee.pk),actor=self.admin,status_code=200).exists())
        self.assertTrue(events.filter(action='access',route='core:employees').exists())
        for event in events:
            text=str(event.__dict__)
            self.assertNotIn('SECRET-TAX',text)
            self.assertNotIn('Sensitive',text)

    def test_change_field_names_and_rollback(self):
        self.employee.phone='SECRET-PHONE'
        self.employee.save(update_fields=['phone'])
        event=AuditEvent.objects.filter(action='update',target_type='core.employee',target_id=str(self.employee.pk)).first()
        self.assertEqual(event.changed_fields,['phone'])
        self.assertNotIn('SECRET-PHONE',str(event.__dict__))
        before=AuditEvent.objects.count()
        try:
            with transaction.atomic():
                self.employee.delete()
                raise ValueError('rollback')
        except ValueError: pass
        self.assertEqual(AuditEvent.objects.count(),before)

    def test_logs_cannot_be_mutated_by_normal_orm(self):
        event=emit('access')
        for operation in [lambda:event.save(),lambda:event.delete(),lambda:AuditEvent.objects.filter(pk=event.pk).delete(),lambda:AuditEvent.objects.filter(pk=event.pk).update(action='fake')]:
            with self.assertRaises(ValidationError): operation()

    def test_log_view_is_restricted_and_self_audited(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/activity/').status_code,403)
        self.assertTrue(AuditEvent.objects.filter(actor=self.user,action='denied',route='core:activity').exists())
        self.client.force_login(self.admin)
        response=self.client.get('/activity/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Δραστηριότητα')
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin,action='access',route='core:activity').exists())

    def test_login_failure_excludes_supplied_credentials(self):
        self.client.post('/accounts/login/',{'username':'SECRET-USERNAME','password':'SECRET-PASSWORD'})
        event=AuditEvent.objects.filter(action='login_failed').first()
        self.assertIsNotNone(event)
        self.assertNotIn('SECRET-',str(event.__dict__))
        self.assertIsNone(current.get())

    def test_password_and_permission_changes(self):
        self.client.force_login(self.admin)
        response=self.client.post('/accounts/password_change/',{'old_password':'S3cure-test-password','new_password1':'Another-S3cure-password','new_password2':'Another-S3cure-password'})
        self.assertEqual(response.status_code,302)
        event=AuditEvent.objects.filter(action='update',actor=self.admin,target_type='auth.user',target_id=str(self.admin.pk)).first()
        self.assertIn('password',event.changed_fields)
        self.assertNotIn('Another-S3cure-password',str(event.__dict__))
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.first())
        self.assertTrue(AuditEvent.objects.filter(action='permissions',target_type='auth.user',target_id=str(self.user.pk)).exists())

    def test_audit_failure_blocks_response_and_clears_context(self):
        self.client.force_login(self.admin)
        with patch('core.audit.emit',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError): self.client.get('/employees/')
        self.assertIsNone(current.get())

    def test_csrf_rejection_is_logged(self):
        client=Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response=client.post('/employees/new/',{})
        self.assertEqual(response.status_code,403)
        self.assertTrue(AuditEvent.objects.filter(actor=self.admin,action='denied',status_code=403).exists())
