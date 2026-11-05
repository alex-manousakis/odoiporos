from copy import deepcopy
from datetime import date
from django.test import TestCase
from django.core.exceptions import ValidationError
from .tests import ApprovalPDFTests
from .models import ApplicationParameters, Signatory, Travel, CalculationSnapshot
from .annual_days import annual_balance, counted_days
from .approval_pdf import generate_approval

class AnnualApprovalTests(TestCase):
    setUp=ApprovalPDFTests.setUp

    def balance(self):
        self.travel.employee.refresh_from_db()
        return annual_balance(self.travel,ApplicationParameters.objects.get(pk=1))

    def previous(self,start=date(2026,10,1),end=date(2026,10,2),employee=None):
        trip=Travel.objects.create(employee=employee or self.employee,route=self.route,status=self.travel.status,
            departure_at=start,return_at=end,work_starts_at=start,work_ends_at=end)
        original=self.travel.calculations.first()
        inputs=deepcopy(original.inputs)
        inputs['source']['travel'].update(departure_at=start.isoformat(),return_at=end.isoformat(),work_starts_at=start.isoformat(),work_ends_at=end.isoformat())
        inputs.update(allowance_from=start.isoformat(),allowance_to=end.isoformat(),days=(end-start).days+1)
        original.pk=None;original.travel=trip;original.revision=1;original.inputs=inputs;original.save()
        return trip

    def test_opening_balance_only_applies_to_installation_year(self):
        self.employee.opening_travel_days=12;self.employee.save()
        self.assertEqual(self.balance()['prior_days'],12)
        ApplicationParameters.objects.filter(pk=1).update(installation_year=2025)
        self.assertEqual(self.balance()['prior_days'],0)

    def test_previous_trips_count_once_regardless_of_revisions_and_pdfs(self):
        previous=self.previous()
        snapshot=previous.calculations.first();snapshot.pk=None;snapshot.revision=2;snapshot.save()
        self.employee.opening_travel_days=10;self.employee.save()
        first=generate_approval(self.travel.pk,self.user,self.signer)
        second=generate_approval(self.travel.pk,self.user,self.signer)
        self.assertEqual(first.source['annual_prior'],12)
        self.assertEqual(second.source['annual_used'],15)
        self.assertEqual(len(second.source['annual_balance']['trips']),1)

    def test_future_other_employee_and_other_year_do_not_count(self):
        from .models import Employee
        self.previous(start=date(2026,12,1),end=date(2026,12,2))
        self.previous(employee=Employee.objects.create(display_name='Another employee'))
        self.previous(start=date(2025,10,1),end=date(2025,10,2))
        self.assertEqual(self.balance()['prior_days'],0)

    def test_year_boundary_allocates_only_days_in_report_year(self):
        self.previous(start=date(2025,12,30),end=date(2026,1,2))
        self.assertEqual(self.balance()['prior_days'],2)

    def test_head_default_deputy_choice_and_posted_totals_ignored(self):
        deputy=Signatory.objects.create(name='Deputy')
        self.client.force_login(self.user)
        url=f'/travels/{self.travel.pk}/approval/'
        response=self.client.get(url)
        self.assertEqual(response.context['form'].initial['signatory'],self.signer.pk)
        self.assertNotContains(response,'name="heading"')
        self.assertNotContains(response,'name="prior_days"')
        response=self.client.post(url,{'signatory':deputy.pk,'heading':'Injected heading','prior_days':199})
        self.assertEqual(response.status_code,302)
        document=self.travel.approval_documents.get()
        self.assertEqual(document.source['signature_heading'],'Head of service')
        self.assertEqual(document.source['signatory']['id'],deputy.pk)
        self.assertEqual(document.source['annual_used'],3)

    def test_missing_configuration_shows_error_without_crashing(self):
        self.signer.is_head=False;self.signer.save()
        ApplicationParameters.objects.filter(pk=1).update(installation_year=None)
        self.client.force_login(self.user)
        response=self.client.get(f'/travels/{self.travel.pk}/approval/')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['configuration_errors'])

    def test_head_is_unique_and_active_in_management_validation(self):
        with self.assertRaises(ValidationError):Signatory(name='Another head',is_head=True).full_clean()
        self.signer.is_active=False
        with self.assertRaises(ValidationError):self.signer.full_clean()

    def test_limit_cannot_be_bypassed_and_missing_previous_estimate_blocks(self):
        self.employee.opening_travel_days=199;self.employee.save()
        with self.assertRaises(ValidationError):generate_approval(self.travel.pk,self.user,self.signer)
        self.employee.opening_travel_days=0;self.employee.save()
        previous=self.previous();previous.calculations.all().delete()
        with self.assertRaises(ValidationError):self.balance()

    def test_previous_changed_dates_require_updated_calculation(self):
        previous=self.previous()
        previous.return_at=date(2026,10,3);previous.save()
        with self.assertRaises(ValidationError):self.balance()
