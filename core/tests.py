from decimal import Decimal
from django.test import SimpleTestCase
from .accommodation import reimbursable_amount


class AccommodationTests(SimpleTestCase):
    def test_total_receipt_pools_only_covered_limits(self):
        self.assertEqual(reimbursable_amount(breakdown="total", claimed_amount="160", nightly_limits=["80", "80"]), Decimal("160.00"))

    def test_itemized_receipt_caps_each_night(self):
        self.assertEqual(reimbursable_amount(breakdown="per_night", claimed_amount="160", nightly_limits=["80", "80"], nightly_costs=["100", "60"]), Decimal("140.00"))

    def test_itemized_total_must_reconcile(self):
        with self.assertRaises(ValueError):
            reimbursable_amount(breakdown="per_night", claimed_amount="160", nightly_limits=["80", "80"], nightly_costs=["80", "60"])

    def test_total_receipt_is_capped(self):
        self.assertEqual(reimbursable_amount(breakdown="total", claimed_amount="200", nightly_limits=["80", "80"]), Decimal("160.00"))

    def test_rejects_invalid_amounts_and_missing_nights(self):
        for invalid in ["-1", "NaN", "Infinity", "1.001", 1.2]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                reimbursable_amount(breakdown="total", claimed_amount=invalid, nightly_limits=["80"])
        with self.assertRaises(ValueError):
            reimbursable_amount(breakdown="total", claimed_amount="0", nightly_limits=[])


from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Employee, EmployeeCategory, EmployeeCategoryHistory, Route, TravelStatus, Travel
from datetime import date


class TravelEntryTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user(username='employee-test')
        self.employee=Employee.objects.create(display_name='Test employee',user=self.user)
        self.other=Employee.objects.create(display_name='Other employee')
        category=EmployeeCategory.objects.create(name='Test category')
        EmployeeCategoryHistory.objects.create(employee=self.employee,category=category,valid_from=date(2026,11,2))
        self.route=Route.objects.create(name='Test route',origin='A',destination='B')
        TravelStatus.objects.create(name='New',legacy_id=1)
        self.data={'employee':self.employee.pk,'route':self.route.pk,'departure_at':'2026-11-03','work_starts_at':'2026-11-03','work_ends_at':'2026-11-03','return_at':'2026-11-03','purpose':'Test'}

    def test_requires_login(self):
        self.assertEqual(self.client.get('/').status_code,302)
        self.assertEqual(self.client.get('/travels/new/').status_code,302)

    def test_create_and_view_own_travel(self):
        self.client.force_login(self.user)
        response=self.client.post('/travels/new/',self.data)
        self.assertEqual(response.status_code,302)
        travel=Travel.objects.get()
        self.assertEqual(travel.departure_at, date(2026,11,3))
        self.assertIsNotNone(travel.applied_category_id)
        self.assertFalse(travel.category_review_required)
        self.assertEqual(self.client.get(response.url).status_code,200)
        self.assertEqual(self.client.get('/').status_code,200)

    def test_employee_cannot_submit_for_someone_else(self):
        self.client.force_login(self.user)
        response=self.client.post('/travels/new/',{**self.data,'employee':self.other.pk})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Travel.objects.exists())

    def test_invalid_date_order_is_rejected(self):
        self.client.force_login(self.user)
        self.client.post('/travels/new/',{**self.data,'return_at':'2026-11-02'})
        self.assertFalse(Travel.objects.exists())

    def test_missing_historical_category_requires_review(self):
        self.client.force_login(self.user)
        old={key:(value.replace('2026-11-03','2026-10-03') if isinstance(value,str) else value) for key,value in self.data.items()}
        self.assertEqual(self.client.post('/travels/new/',old).status_code,302)
        self.assertTrue(Travel.objects.get().category_review_required)

    def test_cannot_view_another_employees_travel(self):
        self.client.force_login(self.user)
        self.client.post('/travels/new/',self.data)
        travel=Travel.objects.get()
        Travel.objects.filter(pk=travel.pk).update(employee=self.other)
        self.assertEqual(self.client.get(f'/travels/{travel.pk}/').status_code,404)
