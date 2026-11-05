from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import Permission
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from . import tests as fixtures
from .models import AccountingAdjustment, AuditEvent, Employee, UserAccess, EmployeeCategoryHistory
from .calculation import calculate_estimate
from .forms import TravelForm

class AccountingTests(TestCase):
    setUp=fixtures.EstimateCalculationTests.setUp

    def grant(self,user=None):
        user=user or self.user
        user.user_permissions.add(*Permission.objects.filter(content_type__app_label='core',codename__in=['view_accountingadjustment','add_accountingadjustment','change_accountingadjustment','view_travel','add_travel','change_travel']))
        return get_user_model().objects.get(pk=user.pk)

    def test_new_trip_defaults_to_logged_in_employee(self):
        form=TravelForm(user=self.user)
        self.assertEqual(form.initial['employee'],self.employee.pk)
        self.client.force_login(self.user)
        response=self.client.get('/travels/new/')
        self.assertEqual(response.context['form'].initial['employee'],self.employee.pk)

    def test_accounting_access_is_explicit_and_menu_hidden(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get('/accounting/travels/').status_code,403)
        self.assertEqual(self.client.get(f'/accounting/travels/{self.travel.pk}/adjustment/').status_code,403)
        self.assertNotContains(self.client.get('/'),'Μετακινήσεις (Λογιστήριο)')
        self.user=self.grant();self.client.force_login(self.user)
        self.assertEqual(self.client.get('/accounting/travels/').status_code,200)
        self.assertNotContains(self.client.get('/'),'Μετακινήσεις (Λογιστήριο)')
        self.assertContains(self.client.get(f'/travels/{self.travel.pk}/'),f'/accounting/travels/{self.travel.pk}/adjustment/')

    def test_other_organization_costs_override_and_recalculate_totals(self):
        self.user=self.grant();self.client.force_login(self.user)
        response=self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'is_active':'on','reason':'Flight and one night paid by inviting organization','tickets':'0','allowed_accommodation':'40'})
        self.assertEqual(response.status_code,302)
        snapshot=self.travel.calculations.latest('revision')
        self.assertEqual(snapshot.tickets,0)
        self.assertEqual(snapshot.allowed_accommodation,40)
        self.assertEqual(snapshot.total,Decimal('250'))
        self.assertEqual(snapshot.document_budget,Decimal('250'))
        self.assertEqual(Decimal(snapshot.inputs['accounting']['automatic']['tickets']),120)
        self.assertTrue(AuditEvent.objects.filter(action='create',target_type='core.accountingadjustment',actor=self.user).exists())
        repeated=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(repeated.total,Decimal('250'))

    def test_reason_required_and_invalid_amounts_rejected_atomically(self):
        self.user=self.grant();self.client.force_login(self.user)
        url=f'/accounting/travels/{self.travel.pk}/adjustment/'
        self.assertEqual(self.client.post(url,{'tickets':'0','is_active':'on'}).status_code,200)
        self.assertEqual(self.client.post(url,{'reason':'Test','tickets':'-1','is_active':'on'}).status_code,200)
        self.assertFalse(AccountingAdjustment.objects.exists())

    def test_restore_automatic_and_preserve_snapshot_history(self):
        self.user=self.grant();self.client.force_login(self.user)
        url=f'/accounting/travels/{self.travel.pk}/adjustment/'
        self.client.post(url,{'reason':'Third-party flight','tickets':'0','is_active':'on'})
        adjusted=self.travel.calculations.latest('revision')
        response=self.client.post(url,{'reason':'Third-party coverage cancelled'})
        self.assertEqual(response.status_code,302)
        latest=self.travel.calculations.latest('revision')
        self.assertEqual(latest.tickets,120)
        adjusted.refresh_from_db();self.assertEqual(adjusted.tickets,0)

    def test_employee_cannot_modify_adjusted_trip_or_inject_override(self):
        staff=self.grant(get_user_model().objects.create_user('accountant'))
        UserAccess.objects.create(user=staff,scope='all')
        self.client.force_login(staff)
        self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'reason':'Covered flight','tickets':'0','is_active':'on'})
        self.client.force_login(self.user)
        self.assertEqual(self.client.post(f'/travels/{self.travel.pk}/edit/',{}).status_code,403)
        self.assertEqual(self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'tickets':'100'}).status_code,403)
        self.assertEqual(AccountingAdjustment.objects.get().values['tickets'],'0')

    def test_scope_and_frozen_calculation_are_respected(self):
        self.user=self.grant();UserAccess.objects.create(user=self.user,scope='own')
        other=Employee.objects.create(display_name='Other')
        self.travel.employee=other;self.travel.save()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/accounting/travels/{self.travel.pk}/adjustment/').status_code,404)
        self.travel.employee=self.employee;self.travel.save()
        from django.utils import timezone
        snap=calculate_estimate(self.travel.pk,self.user);snap.frozen_at=timezone.now();snap.save()
        self.assertEqual(self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'reason':'No','tickets':'0'}).status_code,403)

    def test_accounting_can_create_for_another_scoped_employee(self):
        self.user=self.grant();UserAccess.objects.create(user=self.user,scope='all')
        other=Employee.objects.create(display_name='Other')
        from datetime import date
        EmployeeCategoryHistory.objects.create(employee=other,category=self.category,valid_from=date(2026,1,1))
        self.client.force_login(self.user)
        response=self.client.post('/accounting/travels/new/',{'employee':other.pk,'route':self.route.pk,'departure_at':'03/11/2026','return_at':'05/11/2026','work_starts_at':'03/11/2026','work_ends_at':'05/11/2026','purpose':'Accounting entry'})
        self.assertEqual(response.status_code,302)
        from .models import Travel
        self.assertTrue(Travel.objects.filter(employee=other).exists())


class AccountingApprovalTests(TestCase):
    setUp=fixtures.ApprovalPDFTests.setUp

    def test_manual_days_and_budget_are_used_in_pdf(self):
        user=AccountingTests.grant(self)
        self.client.force_login(user)
        response=self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'is_active':'on','reason':'Inviting organization covers some costs','days':'1','document_budget':'90,00','tickets':'0'})
        self.assertEqual(response.status_code,302)
        from .approval_pdf import generate_approval
        document=generate_approval(self.travel.pk,user,self.signer)
        self.assertEqual(document.source['budget'],'90,00')
        self.assertEqual(document.source['away_days'],1)
        self.assertEqual(document.source['annual_used'],1)

    def test_failed_calculation_does_not_save_adjustment(self):
        user=AccountingTests.grant(self)
        self.route.requires_review=True;self.route.save()
        self.client.force_login(user)
        response=self.client.post(f'/accounting/travels/{self.travel.pk}/adjustment/',{'is_active':'on','reason':'Test failure','tickets':'0'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(AccountingAdjustment.objects.exists())
