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


class TravelCostEntryTests(TravelEntryTests):
    def setUp(self):
        super().setUp()
        from .models import TransportMode, AccommodationType, RouteStop
        self.transport=TransportMode.objects.create(name='Plane',code='P',has_ticket_cost=True)
        self.hotel=AccommodationType.objects.create(name='Hotel',code='H',has_cost=True)
        self.stop=RouteStop.objects.create(route=self.route,sequence=1,city='B')
        self.client.force_login(self.user)
        self.client.post('/travels/new/',{**self.data,'return_at':'2026-11-05'})
        self.travel=Travel.objects.get()
        self.url=f'/travels/{self.travel.pk}/costs/'
        self.payload={
            'expenses-TOTAL_FORMS':'1','expenses-INITIAL_FORMS':'0',
            'expenses-0-kind':'ticket','expenses-0-transport':str(self.transport.pk),'expenses-0-estimated_amount':'120.50',
            'stays-TOTAL_FORMS':'1','stays-INITIAL_FORMS':'0',
            'stays-0-date':'2026-11-03','stays-0-stop':str(self.stop.pk),
            'stays-0-accommodation_type':str(self.hotel.pk),'stays-0-estimated_cost':'80',
        }

    # Parent tests are exercised separately; this class tests the cost workflow.
    test_requires_login=None
    test_create_and_view_own_travel=None
    test_employee_cannot_submit_for_someone_else=None
    test_invalid_date_order_is_rejected=None
    test_missing_historical_category_requires_review=None
    test_cannot_view_another_employees_travel=None

    def test_save_costs_and_stay(self):
        self.assertEqual(self.client.get(self.url).status_code,200)
        self.assertEqual(self.client.post(self.url,self.payload).status_code,302)
        self.assertEqual(self.travel.expenses.get().estimated_amount,Decimal('120.50'))
        self.assertEqual(self.travel.overnights.get().city,'B')
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/').status_code,200)

    def test_invalid_stay_rolls_back_both_collections(self):
        response=self.client.post(self.url,{**self.payload,'stays-0-date':'2026-11-05'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(self.travel.expenses.exists())
        self.assertFalse(self.travel.overnights.exists())

    def test_cannot_select_stop_from_another_route(self):
        from .models import RouteStop
        other=Route.objects.create(name='Other',origin='X',destination='Y')
        stop=RouteStop.objects.create(route=other,sequence=1,city='Y')
        self.assertEqual(self.client.post(self.url,{**self.payload,'stays-0-stop':str(stop.pk)}).status_code,200)
        self.assertFalse(self.travel.overnights.exists())

    def test_approved_travel_is_locked(self):
        from django.utils import timezone
        Travel.objects.filter(pk=self.travel.pk).update(approved_at=timezone.now())
        self.assertEqual(self.client.post(self.url,self.payload).status_code,403)
        self.assertFalse(self.travel.expenses.exists())

    def test_other_employee_cannot_edit(self):
        Travel.objects.filter(pk=self.travel.pk).update(employee=self.other)
        self.assertEqual(self.client.post(self.url,self.payload).status_code,404)

    def test_mileage_requires_distance_and_no_manual_amount(self):
        response=self.client.post(self.url,{**self.payload,'expenses-0-kind':'mileage'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(self.travel.expenses.exists())


class UnifiedTravelTests(TravelCostEntryTests):
    def test_unified_create_with_children(self):
        response=self.client.get('/travels/new/')
        self.assertContains(response,'generate-nights')
        response=self.client.post('/travels/new/',{**self.data,'return_at':'2026-11-05',**self.payload,'protocol_number':'123'})
        self.assertEqual(response.status_code,302)
        created=Travel.objects.exclude(pk=self.travel.pk).get()
        self.assertEqual(created.protocol_number,'123')
        self.assertEqual(created.expenses.count(),1)
        self.assertEqual(created.overnights.count(),1)

    def test_invalid_child_prevents_parent_changes(self):
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',{**self.data,'return_at':'2026-11-05',**self.payload,'purpose':'Changed','stays-0-date':'2026-11-06'})
        self.assertEqual(response.status_code,200)
        self.travel.refresh_from_db()
        self.assertEqual(self.travel.purpose,'Test')
        self.assertFalse(self.travel.expenses.exists())

    def test_edit_protocol_and_actions(self):
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',{**self.data,'return_at':'2026-11-05',**self.payload,'protocol_number':'456','protocol_date':'2026-11-01','actions_description':'Completed'})
        self.assertEqual(response.status_code,302)
        self.travel.refresh_from_db()
        self.assertEqual(self.travel.actions_description,'Completed')
        self.assertEqual(self.travel.protocol_date,date(2026,11,1))

    def test_attachment_requires_travel_access(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from django.test import override_settings
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            response=self.client.post(f'/travels/{self.travel.pk}/edit/',{**self.data,'return_at':'2026-11-05',**self.payload,'attachments':SimpleUploadedFile('receipt.txt',b'receipt')})
            self.assertEqual(response.status_code,302)
            attachment=self.travel.attachments.get()
            url=f'/attachments/{attachment.pk}/download/'
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertIn('attachment',response['Content-Disposition'])
            for closer in response._resource_closers:
                closer()
            Travel.objects.filter(pk=self.travel.pk).update(employee=self.other)
            self.assertEqual(self.client.get(url).status_code,404)


class AirportTransferTests(SimpleTestCase):
    def test_transfer_field_has_money_precision(self):
        from .models import TravelExpense
        field=TravelExpense._meta.get_field('estimated_transfer_cost')
        self.assertEqual(field.decimal_places,2)
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            field.clean(Decimal('-1'),None)


class OvernightTypeTests(TravelCostEntryTests):
    def test_friends_stay_clears_stale_cost(self):
        from .models import AccommodationType
        friends=AccommodationType.objects.create(name='Friends',code='F',has_cost=False)
        response=self.client.post(self.url,{**self.payload,'stays-0-accommodation_type':str(friends.pk),'stays-0-estimated_cost':'80'})
        self.assertEqual(response.status_code,302)
        self.assertIsNone(self.travel.overnights.get().estimated_cost)

    def test_hotel_requires_cost(self):
        response=self.client.post(self.url,{**self.payload,'stays-0-estimated_cost':''})
        self.assertEqual(response.status_code,200)
        self.assertFalse(self.travel.overnights.exists())

    def test_edit_has_dated_stay_table(self):
        response=self.client.get(f'/travels/{self.travel.pk}/edit/')
        self.assertContains(response,'class="stay-table"')
        self.assertContains(response,'accommodation-data')


class BlankExpenseEditTests(TravelCostEntryTests):
    def test_unused_expense_rows_do_not_block_edit(self):
        payload={**self.data,'return_at':'2026-11-05',**self.payload,'purpose':'Updated purpose',
                 'expenses-TOTAL_FORMS':'3','expenses-1-kind':'ticket','expenses-2-kind':'ticket'}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertEqual(response.status_code,302)
        self.travel.refresh_from_db()
        self.assertEqual(self.travel.purpose,'Updated purpose')
        self.assertEqual(self.travel.expenses.count(),1)

    def test_incomplete_real_expense_has_visible_error(self):
        payload={**self.data,'return_at':'2026-11-05',**self.payload,'expenses-0-estimated_amount':''}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertContains(response,'role="alert"')
        self.assertFalse(self.travel.expenses.exists())
