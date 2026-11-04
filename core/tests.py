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
        response=self.client.post(self.url,self.payload)
        self.assertEqual(response.status_code,302, response.context['expenses'].errors if response.status_code==200 else '')
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


class DepartmentAccessTests(TravelEntryTests):
    def setUp(self):
        super().setUp()
        from .models import Department, UserAccess
        from django.contrib.auth.models import Permission
        self.department=Department.objects.create(name='Unit A')
        self.employee.department=self.department;self.employee.save()
        self.other.department=Department.objects.create(name='Unit B');self.other.save()
        self.head=get_user_model().objects.create_user(username='head')
        self.access=UserAccess.objects.create(user=self.head,scope='department')
        self.access.departments.add(self.department)
        self.head.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='view_travel'))
        self.client.force_login(self.user)
        self.client.post('/travels/new/',self.data)
        self.travel=Travel.objects.get()
        self.client.force_login(self.head)

    test_requires_login=None
    test_create_and_view_own_travel=None
    test_employee_cannot_submit_for_someone_else=None
    test_invalid_date_order_is_rejected=None
    test_missing_historical_category_requires_review=None
    test_cannot_view_another_employees_travel=None

    def test_head_can_view_unit_not_other_units(self):
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/').status_code,200)
        Travel.objects.filter(pk=self.travel.pk).update(employee=self.other)
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/').status_code,404)

    def test_view_only_head_cannot_edit(self):
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/edit/').status_code,403)

    def test_travel_permission_does_not_allow_user_management(self):
        self.assertEqual(self.client.get('/users/').status_code,403)
        self.assertEqual(self.client.post('/users/new/',{'username':'attacker'}).status_code,403)

    def test_superuser_sees_matrix(self):
        admin=get_user_model().objects.create_superuser(username='test-admin',password='test-password-123')
        self.client.force_login(admin)
        self.assertEqual(self.client.get('/users/').status_code,200)
        self.assertEqual(self.client.get(f'/users/{self.head.pk}/edit/').status_code,200)

    def test_department_creator_cannot_post_other_unit_employee(self):
        from django.contrib.auth.models import Permission
        self.head.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='add_travel'))
        self.assertEqual(self.client.post('/travels/new/',{**self.data,'employee':self.other.pk}).status_code,200)
        self.assertEqual(Travel.objects.count(),1)

    def test_explicit_own_scope_limits_global_view_permission(self):
        self.access.scope='own';self.access.save()
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/').status_code,404)


    def test_admin_creates_department_head_with_password(self):
        from django.contrib.auth.models import Permission
        from .models import UserAccess
        admin=get_user_model().objects.create_superuser(username='test-admin',password='test-password-123')
        self.client.force_login(admin)
        permission=Permission.objects.get(content_type__app_label='core',codename='view_travel')
        response=self.client.post('/users/new/',{'username':'new-head','password':'Strong-test-password-456!','is_active':'on','scope':'department','departments':[self.department.pk],'permissions':[permission.pk]})
        self.assertEqual(response.status_code,302)
        user=get_user_model().objects.get(username='new-head')
        self.assertTrue(user.check_password('Strong-test-password-456!'))
        self.assertFalse(user.is_superuser)
        self.assertEqual(UserAccess.objects.get(user=user).departments.get(),self.department)
        self.assertTrue(user.has_perm('core.view_travel'))


class TemplateCompilationTests(SimpleTestCase):
    def test_all_project_templates_compile(self):
        from pathlib import Path
        from django.conf import settings
        from django.template.loader import get_template
        root=Path(settings.BASE_DIR)/'templates'
        for path in root.rglob('*.html'):
            with self.subTest(template=str(path.relative_to(root))):
                get_template(path.relative_to(root).as_posix())


class RouteManagementTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='route-admin',password='Test-Password-123')
        self.client.force_login(self.admin)
        self.data={'origin':'Heraklion','distance_km':'664','is_active':'on','has_daily_allowance':'on','stops-TOTAL_FORMS':'5','stops-INITIAL_FORMS':'0','stops-0-city':'Athens','stops-0-compensation_band':'1','stops-0-is_expensive':'on'}

    def test_create_domestic_route(self):
        response=self.client.post('/routes/new/',self.data)
        self.assertEqual(response.status_code,302)
        route=Route.objects.get()
        self.assertEqual(route.destination,'Athens')
        self.assertEqual(route.stops.get().sequence,1)
        self.assertTrue(route.stops.get().is_expensive)
        self.assertEqual(self.client.get('/routes/').status_code,200)
        self.assertEqual(self.client.get(f'/routes/{route.pk}/edit/').status_code,200)

    def test_create_abroad_with_domestic_stop(self):
        data={**self.data,'is_abroad':'on','stops-1-city':'Brussels','stops-1-is_abroad':'on','stops-1-compensation_band':'2'}
        self.assertEqual(self.client.post('/routes/new/',data).status_code,302)
        route=Route.objects.get()
        self.assertEqual(route.stops.count(),2)
        self.assertFalse(route.stops.first().is_abroad)
        self.assertTrue(route.stops.last().is_abroad)

    def test_requires_destination(self):
        response=self.client.post('/routes/new/',{**self.data,'stops-0-city':''})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Route.objects.exists())

    def test_conflicting_flags_are_rejected(self):
        response=self.client.post('/routes/new/',{**self.data,'stops-0-is_island':'on'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(Route.objects.exists())

    def test_permission_required(self):
        user=get_user_model().objects.create_user(username='no-route-rights')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/routes/').status_code,403)
        self.assertEqual(self.client.post('/routes/new/',self.data).status_code,403)

    def test_unused_route_can_be_edited_preserving_stop_id(self):
        self.client.post('/routes/new/',self.data)
        route=Route.objects.get();stop=route.stops.get()
        data={**self.data,'stops-TOTAL_FORMS':'1','stops-INITIAL_FORMS':'1','stops-0-id':str(stop.pk),'stops-0-city':'Thessaloniki'}
        self.assertEqual(self.client.post(f'/routes/{route.pk}/edit/',data).status_code,302)
        route.refresh_from_db();stop.refresh_from_db()
        self.assertEqual(route.destination,'Thessaloniki')
        self.assertEqual(stop.sequence,1)


class ApplicationParametersTests(TestCase):
    def test_admin_can_save_parameters(self):
        from .models import ApplicationParameters
        user=get_user_model().objects.create_superuser(username='params-admin',password='Test-Password-123')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/parameters/').status_code,200)
        response=self.client.post('/parameters/',{'countriescomp2':'Group two','countriescomp3':'Group three','travelnumdigits':'5','document_header':'Organization header','approval_service_genitive':'of the service'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(ApplicationParameters.objects.get(pk=1).countriescomp2,'Group two')

    def test_no_permission_cannot_read_or_write(self):
        self.client.force_login(get_user_model().objects.create_user(username='params-denied'))
        self.assertEqual(self.client.get('/parameters/').status_code,403)
        self.assertEqual(self.client.post('/parameters/',{}).status_code,403)

    def test_read_only_user_cannot_save(self):
        from django.contrib.auth.models import Permission
        user=get_user_model().objects.create_user(username='params-reader')
        user.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='view_applicationparameters'))
        self.client.force_login(user)
        self.assertEqual(self.client.get('/parameters/').status_code,200)
        self.assertEqual(self.client.post('/parameters/',{}).status_code,403)

    def test_route_labels_follow_database_parameters(self):
        from .models import ApplicationParameters
        from .route_management import StopForm
        ApplicationParameters.objects.create(pk=1,countriescomp2='Updated countries')
        self.assertIn((2,'Updated countries'),list(StopForm().fields['compensation_band'].choices))


class EmployeeManagementTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='employee-admin',password='Test-Password-123')
        self.client.force_login(self.admin)
        self.category=EmployeeCategory.objects.create(name='Category A')
        self.data={'display_name':'Test Employee','first_name':'Test','last_name':'Employee','is_active':'on','new_category':self.category.pk,'category_from':'2026-11-03'}

    def test_create_employee_and_initial_category(self):
        self.assertEqual(self.client.post('/employees/new/',self.data).status_code,302)
        employee=Employee.objects.get()
        self.assertEqual(employee.category_history.get().category,self.category)
        self.assertEqual(self.client.get('/employees/').status_code,200)
        self.assertEqual(self.client.get(f'/employees/{employee.pk}/edit/').status_code,200)

    def test_category_change_closes_previous_interval(self):
        self.client.post('/employees/new/',self.data)
        employee=Employee.objects.get()
        other=EmployeeCategory.objects.create(name='Category B')
        response=self.client.post(f'/employees/{employee.pk}/edit/',{**self.data,'new_category':other.pk,'category_from':'2026-12-01'})
        self.assertEqual(response.status_code,302)
        self.assertEqual(employee.category_history.first().valid_to,date(2026,11,30))
        self.assertEqual(employee.category_history.count(),2)

    def test_backdated_category_change_is_rejected(self):
        self.client.post('/employees/new/',self.data)
        employee=Employee.objects.get()
        other=EmployeeCategory.objects.create(name='Category B')
        self.assertEqual(self.client.post(f'/employees/{employee.pk}/edit/',{**self.data,'new_category':other.pk,'category_from':'2026-11-02'}).status_code,200)
        self.assertEqual(employee.category_history.count(),1)

    def test_employee_permissions_required(self):
        user=get_user_model().objects.create_user(username='ordinary')
        self.client.force_login(user)
        self.assertEqual(self.client.get('/employees/').status_code,403)
        self.assertEqual(self.client.post('/employees/new/',self.data).status_code,403)

    def test_department_editor_cannot_view_other_department_or_link_account(self):
        from .models import Department, UserAccess
        from django.contrib.auth.models import Permission
        department=Department.objects.create(name='Unit A')
        other=Department.objects.create(name='Unit B')
        employee=Employee.objects.create(display_name='Other employee',department=other)
        editor=get_user_model().objects.create_user(username='unit-editor')
        access=UserAccess.objects.create(user=editor,scope='department');access.departments.add(department)
        editor.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='change_employee'))
        self.client.force_login(editor)
        self.assertEqual(self.client.get(f'/employees/{employee.pk}/edit/').status_code,404)
        employee.department=department;employee.save()
        data={**self.data,'department':department.pk,'user':self.admin.pk}
        self.assertEqual(self.client.post(f'/employees/{employee.pk}/edit/',data).status_code,302)
        employee.refresh_from_db()
        self.assertIsNone(employee.user_id)


class EmployeeDeclarationDetailsTests(EmployeeManagementTests):
    def test_declaration_details_round_trip(self):
        data={**self.data,'id_number':'AB123456','tax_number':'001234567','father_name':'Father','mother_name':'Mother','birth_place':'City','birth_date':'1980-02-03','phone':'2101234567','city':'Town','address':'Street','address_number':'12A','postal_code':'00100','driving_license':'LICENSE-123','car_brand':'Brand','iban':'GR00123','email':'employee@example.com'}
        self.assertEqual(self.client.post('/employees/new/',data).status_code,302)
        employee=Employee.objects.get()
        self.assertEqual(employee.tax_number,'001234567')
        self.assertEqual(employee.birth_date,date(1980,2,3))
        self.assertEqual(employee.driving_license,'LICENSE-123')
        response=self.client.get(f'/employees/{employee.pk}/edit/')
        self.assertContains(response,'AB123456')
        self.assertContains(response,'03/02/1980')


class EstimateCalculationTests(TestCase):
    def setUp(self):
        from .models import ApplicationParameters,RouteStop,DailyAllowanceRate,MileageRate,AccommodationRate,TransportMode,TravelExpense,AccommodationType,OvernightStay
        self.user=get_user_model().objects.create_user(username='estimate-user')
        self.employee=Employee.objects.create(display_name='Estimate employee',user=self.user)
        self.category=EmployeeCategory.objects.create(name='Cat')
        EmployeeCategoryHistory.objects.create(employee=self.employee,category=self.category,valid_from=date(2026,1,1))
        self.route=Route.objects.create(name='Route',origin='A',destination='B',distance_km='400')
        self.stop=RouteStop.objects.create(route=self.route,sequence=1,city='B')
        status=TravelStatus.objects.create(name='New',legacy_id=1)
        self.travel=Travel.objects.create(employee=self.employee,route=self.route,status=status,applied_category=self.category,departure_at=date(2026,11,3),return_at=date(2026,11,5),work_starts_at=date(2026,11,3),work_ends_at=date(2026,11,5))
        ApplicationParameters.objects.create(pk=1,homedistancelimit=80)
        self.rate=DailyAllowanceRate.objects.create(category=self.category,is_abroad=False,valid_from=date(2026,1,1),valid_to=date(2026,12,31),without_overnight=20,band_1=40,band_2=30,band_3=20)
        MileageRate.objects.create(valid_from=date(2026,1,1),valid_to=date(2026,12,31),amount_per_km=Decimal('0.2'))
        AccommodationRate.objects.create(category=self.category,is_abroad=False,valid_from=date(2026,1,1),valid_to=date(2026,12,31),minimum_distance_km=50,standard_limit=80,expensive_city_limit=100,island_limit=90)
        car=TransportMode.objects.create(name='Car',code='C',has_mileage_cost=True)
        plane=TransportMode.objects.create(name='Plane',code='P',has_ticket_cost=True)
        TravelExpense.objects.create(travel=self.travel,kind='mileage',transport=car,estimated_distance_km=400)
        TravelExpense.objects.create(travel=self.travel,kind='ticket',transport=plane,estimated_amount=120,estimated_transfer_cost=10)
        hotel=AccommodationType.objects.create(name='Hotel',code='H',has_cost=True)
        OvernightStay.objects.create(travel=self.travel,date=date(2026,11,3),stop=self.stop,city='B',accommodation_type=hotel,estimated_cost=100)

    def test_estimate_breakdown_and_revision(self):
        from .calculation import calculate_estimate
        result=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(result.daily_domestic,Decimal('120'))
        self.assertEqual(result.mileage,Decimal('80'))
        self.assertEqual(result.allowed_accommodation,Decimal('80'))
        self.assertEqual(result.total,Decimal('410'))
        self.assertEqual(calculate_estimate(self.travel.pk,self.user).revision,2)

    def test_same_day_uses_without_overnight_rate(self):
        from .calculation import calculate_estimate
        self.travel.overnights.all().delete()
        self.travel.return_at=self.travel.work_ends_at=self.travel.departure_at;self.travel.save()
        self.assertEqual(calculate_estimate(self.travel.pk,self.user).daily_domestic,Decimal('20'))

    def test_missing_and_overlapping_rates_are_rejected(self):
        from .calculation import calculate_estimate
        from django.core.exceptions import ValidationError
        self.rate.delete()
        with self.assertRaises(ValidationError):calculate_estimate(self.travel.pk,self.user)
        self.assertFalse(self.travel.calculations.exists())

    def test_changed_inputs_mark_snapshot_stale(self):
        from .calculation import calculate_estimate,input_state,signature
        result=calculate_estimate(self.travel.pk,self.user)
        self.travel.expenses.filter(kind='ticket').update(estimated_amount=200)
        self.assertNotEqual(result.inputs['signature'],signature(input_state(self.travel)))

    def test_wrong_user_cannot_calculate(self):
        from .calculation import calculate_estimate
        from django.core.exceptions import PermissionDenied
        other=get_user_model().objects.create_user(username='outsider')
        with self.assertRaises(PermissionDenied):calculate_estimate(self.travel.pk,other)

    def test_endpoint_requires_post_and_renders_breakdown(self):
        self.client.force_login(self.user)
        url=f'/travels/{self.travel.pk}/calculate/'
        self.assertEqual(self.client.get(url).status_code,405)
        self.assertEqual(self.client.post(url).status_code,302)
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/').status_code,200)


    def test_overlapping_daily_rates_are_rejected(self):
        from .calculation import calculate_estimate
        from django.core.exceptions import ValidationError
        self.rate.pk=None;self.rate.save()
        with self.assertRaises(ValidationError):calculate_estimate(self.travel.pk,self.user)

    def test_abroad_band_and_special_hotel_limit(self):
        from .calculation import calculate_estimate
        from .models import AccommodationRate
        self.route.is_abroad=True;self.route.save()
        self.stop.is_abroad=True;self.stop.compensation_band=2;self.stop.save()
        self.rate.is_abroad=True;self.rate.save()
        AccommodationRate.objects.filter(category=self.category).update(is_abroad=True)
        self.travel.overnights.update(is_abroad=True,is_expensive=True)
        result=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(result.daily_abroad,Decimal('90'))
        self.assertEqual(result.daily_domestic,Decimal('0'))
        self.assertEqual(result.allowed_accommodation,Decimal('100'))

    def test_budget_uplift_ceiling_and_minimum(self):
        from .calculation import calculate_estimate
        from .models import ApplicationParameters
        ApplicationParameters.objects.filter(pk=1).update(percentageofbudgetinc=10,roundtotalbudget=True,budgetdownlimit=500)
        self.assertEqual(calculate_estimate(self.travel.pk,self.user).document_budget,Decimal('500'))


class AccommodationRateManagementTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_superuser(username='hotel-admin',password='Test-Password-123')
        self.client.force_login(self.admin)
        self.category=EmployeeCategory.objects.create(name='Hotel category')
        self.data={'category':self.category.pk,'valid_from':'2026-01-01','valid_to':'2026-12-31','minimum_distance_km':'50','standard_limit':'80','expensive_city_limit':'100','island_limit':'90'}

    def test_create_and_list(self):
        from .models import AccommodationRate
        self.assertEqual(self.client.post('/accommodation-rates/new/',self.data).status_code,302)
        self.assertEqual(AccommodationRate.objects.get().standard_limit,Decimal('80'))
        self.assertEqual(self.client.get('/accommodation-rates/').status_code,200)
        rate=AccommodationRate.objects.get()
        self.assertEqual(self.client.get(f'/accommodation-rates/{rate.pk}/edit/').status_code,200)

    def test_overlap_rejected_including_shared_boundary(self):
        from .models import AccommodationRate
        self.client.post('/accommodation-rates/new/',self.data)
        response=self.client.post('/accommodation-rates/new/',{**self.data,'valid_from':'2026-12-31','valid_to':'2027-12-31'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(AccommodationRate.objects.count(),1)

    def test_adjacent_period_and_abroad_are_allowed(self):
        from .models import AccommodationRate
        self.client.post('/accommodation-rates/new/',self.data)
        self.assertEqual(self.client.post('/accommodation-rates/new/',{**self.data,'valid_from':'2027-01-01','valid_to':'2027-12-31'}).status_code,302)
        self.assertEqual(self.client.post('/accommodation-rates/new/',{**self.data,'is_abroad':'on'}).status_code,302)
        self.assertEqual(AccommodationRate.objects.count(),3)

    def test_invalid_dates_and_negative_amounts_rejected(self):
        from .models import AccommodationRate
        response=self.client.post('/accommodation-rates/new/',{**self.data,'valid_to':'2025-12-31','standard_limit':'-1'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(AccommodationRate.objects.exists())

    def test_existing_period_can_be_edited_without_self_overlap(self):
        from .models import AccommodationRate
        self.client.post('/accommodation-rates/new/',self.data)
        rate=AccommodationRate.objects.get()
        self.assertEqual(self.client.post(f'/accommodation-rates/{rate.pk}/edit/',{**self.data,'standard_limit':'85'}).status_code,302)
        rate.refresh_from_db();self.assertEqual(rate.standard_limit,Decimal('85'))

    def test_read_only_permission_cannot_create_or_edit(self):
        from django.contrib.auth.models import Permission
        reader=get_user_model().objects.create_user(username='hotel-reader')
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='view_accommodationrate'))
        self.client.force_login(reader)
        self.assertEqual(self.client.get('/accommodation-rates/').status_code,200)
        self.assertEqual(self.client.post('/accommodation-rates/new/',self.data).status_code,403)


class RouteMileageTests(TravelCostEntryTests):
    def test_mileage_uses_route_distance_without_employee_input(self):
        from .models import TransportMode
        self.route.distance_km=Decimal('450.50');self.route.save()
        car=TransportMode.objects.create(name='Car',code='CAR',has_mileage_cost=True)
        payload={**self.payload,'expenses-0-kind':'mileage','expenses-0-transport':str(car.pk),'expenses-0-estimated_amount':''}
        self.assertEqual(self.client.post(self.url,payload).status_code,302)
        self.assertEqual(self.travel.expenses.get().estimated_distance_km,Decimal('450.50'))

    def test_posted_mileage_cannot_override_route_distance(self):
        from .models import TransportMode
        self.route.distance_km=Decimal('450.50');self.route.save()
        car=TransportMode.objects.create(name='Car',code='CAR',has_mileage_cost=True)
        payload={**self.payload,'expenses-0-kind':'mileage','expenses-0-transport':str(car.pk),'expenses-0-estimated_amount':'','expenses-0-estimated_distance_km':'9999'}
        self.assertEqual(self.client.post(self.url,payload).status_code,302)
        self.assertEqual(self.travel.expenses.get().estimated_distance_km,Decimal('450.50'))


class AutomaticEstimateTests(EstimateCalculationTests):
    def test_save_runs_calculation_without_button(self):
        from .models import CalculationSnapshot
        self.client.force_login(self.user)
        payload={'employee':self.employee.pk,'route':self.route.pk,'departure_at':'2026-11-03','return_at':'2026-11-05','work_starts_at':'2026-11-03','work_ends_at':'2026-11-05','purpose':'Updated'}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.travel.calculations.count(),1)
        self.assertEqual(self.travel.calculations.get().total,Decimal('410'))

    def test_missing_rate_preserves_saved_changes_and_warns(self):
        self.rate.delete()
        self.client.force_login(self.user)
        payload={'employee':self.employee.pk,'route':self.route.pk,'departure_at':'2026-11-03','return_at':'2026-11-05','work_starts_at':'2026-11-03','work_ends_at':'2026-11-05','purpose':'Saved despite missing rate'}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload,follow=True)
        self.assertEqual(response.status_code,200)
        self.travel.refresh_from_db()
        self.assertEqual(self.travel.purpose,'Saved despite missing rate')
        self.assertFalse(self.travel.calculations.exists())
        self.assertContains(response,'estimate could not be updated')


class ReportTextManagementTests(TestCase):
    def setUp(self):
        from .models import ReportDefinition,ReportText
        self.admin=get_user_model().objects.create_superuser(username='report-admin',password='Test-Password-123')
        self.client.force_login(self.admin)
        self.report=ReportDefinition.objects.create(name='Approval preamble',legacy_id=1)
        self.row=ReportText.objects.create(report=self.report,sort_order=1,text='Original')
        self.data={'report':self.report.pk,'texts-TOTAL_FORMS':'2','texts-INITIAL_FORMS':'1','texts-0-id':self.row.pk,'texts-0-sort_order':'2','texts-0-text':'Updated','texts-1-sort_order':'1','texts-1-text':'New first paragraph'}

    def test_add_edit_and_order(self):
        self.assertEqual(self.client.get('/report-texts/').status_code,200)
        self.assertEqual(self.client.post('/report-texts/',self.data).status_code,302)
        self.assertEqual(list(self.report.texts.values_list('text',flat=True)),['New first paragraph','Updated'])

    def test_delete_permission_applied(self):
        self.assertEqual(self.client.post('/report-texts/',{**self.data,'texts-0-DELETE':'on'}).status_code,302)
        self.assertFalse(self.report.texts.filter(pk=self.row.pk).exists())

    def test_no_permission_denied(self):
        self.client.force_login(get_user_model().objects.create_user(username='report-denied'))
        self.assertEqual(self.client.get('/report-texts/').status_code,403)
        self.assertEqual(self.client.post('/report-texts/',self.data).status_code,403)

    def test_read_only_user_cannot_forge_changes(self):
        from django.contrib.auth.models import Permission
        reader=get_user_model().objects.create_user(username='report-reader')
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='view_reporttext'))
        self.client.force_login(reader)
        self.assertEqual(self.client.get('/report-texts/').status_code,200)
        self.assertEqual(self.client.post('/report-texts/',self.data).status_code,403)
        self.row.refresh_from_db();self.assertEqual(self.row.text,'Original')

    def test_change_only_user_cannot_delete_or_add(self):
        from django.contrib.auth.models import Permission
        editor=get_user_model().objects.create_user(username='report-editor')
        editor.user_permissions.add(*Permission.objects.filter(content_type__app_label='core',codename__in=['view_reporttext','change_reporttext']))
        self.client.force_login(editor)
        self.assertEqual(self.client.post('/report-texts/',{**self.data,'texts-0-DELETE':'on'}).status_code,302)
        self.row.refresh_from_db();self.assertEqual(self.row.text,'Updated')
        self.assertEqual(self.report.texts.count(),1)


class ApprovalPDFTests(TestCase):
    def setUp(self):
        EstimateCalculationTests.setUp(self)
        from .models import ApplicationParameters,ReportDefinition,ReportText,Signatory
        from .calculation import calculate_estimate
        from django.contrib.auth.models import Permission
        ApplicationParameters.objects.filter(pk=1).update(allowedtravelsperyear=200)
        from .models import Gender
        self.employee.gender=Gender.objects.create(name='Male',text1='\u03c4\u03bf\u03c5')
        self.employee.name_genitive='Test genitive';self.employee.save()
        self.travel.protocol_number='123';self.travel.protocol_date=date(2026,11,1);self.travel.purpose='Seminar';self.travel.save()
        report=ReportDefinition.objects.create(legacy_id=11,name='Preamble')
        self.script=ReportText.objects.create(report=report,sort_order=1,text='First legal paragraph & plain text')
        report=ReportDefinition.objects.create(legacy_id=12,name='Budget')
        ReportText.objects.create(report=report,sort_order=1,text='Funding paragraph')
        self.signer=Signatory.objects.create(name='Test signer',speciality='Head')
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='print_travel'))
        calculate_estimate(self.travel.pk,self.user)

    def test_pdf_contains_scripts_and_archives_original_bytes(self):
        from .approval_pdf import generate_approval
        from pypdf import PdfReader
        from io import BytesIO
        document=generate_approval(self.travel.pk,self.user,self.signer,'Head of service',10)
        data=bytes(document.content)
        self.assertTrue(data.startswith(b'%PDF-'))
        reader=PdfReader(BytesIO(data))
        self.assertEqual(len(reader.pages),1)
        for page in reader.pages:
            images=page['/Resources']['/XObject'].get_object()
            self.assertGreaterEqual(sum(obj.get_object().get('/Subtype')=='/Image' for obj in images.values()),2)
        text=' '.join(page.extract_text() for page in reader.pages)
        self.assertIn('First legal paragraph & plain text',text)
        self.assertIn('Funding paragraph',text)
        self.assertIn('\u0391\u03a0\u039f\u03a6\u0391\u03a3\u0397',text)
        self.assertIn('410,00',text)
        self.script.text='Changed later';self.script.save()
        document.refresh_from_db()
        self.assertEqual(bytes(document.content),data)
        self.assertEqual(document.source['annual_used'],13)

    def test_stale_estimate_blocks_generation(self):
        from .approval_pdf import generate_approval
        from django.core.exceptions import ValidationError
        self.travel.expenses.filter(kind='ticket').update(estimated_amount=999)
        with self.assertRaises(ValidationError):generate_approval(self.travel.pk,self.user,self.signer,'Head',0)
        self.assertFalse(self.travel.approval_documents.exists())

    def test_download_scope_and_print_permission(self):
        from .approval_pdf import generate_approval
        document=generate_approval(self.travel.pk,self.user,self.signer,'Head',0)
        self.client.force_login(self.user)
        response=self.client.get(f'/approvals/{document.pk}/download/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        outsider=get_user_model().objects.create_user(username='pdf-outsider')
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/approvals/{document.pk}/download/').status_code,403)

    def test_form_creates_document(self):
        self.client.force_login(self.user)
        url=f'/travels/{self.travel.pk}/approval/'
        self.assertEqual(self.client.get(url).status_code,200)
        response=self.client.post(url,{'signatory':self.signer.pk,'heading':'Head','prior_days':5})
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.travel.approval_documents.count(),1)


class OptionalApprovalProtocolTests(ApprovalPDFTests):
    def test_print_without_protocol(self):
        from .approval_pdf import generate_approval
        self.travel.protocol_number='';self.travel.protocol_date=None;self.travel.save()
        document=generate_approval(self.travel.pk,self.user,self.signer,'Head',0)
        self.assertTrue(bytes(document.content).startswith(b'%PDF-'))
        self.assertEqual(document.source['protocol_date'],'')

    def test_print_with_only_protocol_number(self):
        from .approval_pdf import generate_approval
        self.travel.protocol_date=None;self.travel.save()
        document=generate_approval(self.travel.pk,self.user,self.signer,'Head',0)
        self.assertEqual(document.source['protocol_number'],'123')


class ApprovalGenderTests(ApprovalPDFTests):
    def test_uses_gender_article_in_heading_and_decision(self):
        from .approval_pdf import generate_approval
        from .models import Gender
        for article in ['\u03c4\u03bf\u03c5','\u03c4\u03b7\u03c2']:
            with self.subTest(article=article):
                self.employee.gender=Gender.objects.create(name=article,text1=article)
                self.employee.save()
                document=generate_approval(self.travel.pk,self.user,self.signer,'Head',0)
                self.assertEqual(document.source['employee']['approval_subject'],article+' Test genitive')
                self.assertIn(article+' Test genitive',document.source['decision_text'])

    def test_missing_gender_requires_explicit_selection(self):
        from .approval_pdf import generate_approval
        from django.core.exceptions import ValidationError
        self.employee.gender=None;self.employee.save()
        with self.assertRaises(ValidationError):generate_approval(self.travel.pk,self.user,self.signer,'Head',0)


class TripTabbedWorkflowTests(TravelCostEntryTests):
    def test_open_trip_shows_input_and_calculation_tabs(self):
        response=self.client.get(f'/travels/{self.travel.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'id="trip-input-panel"')
        self.assertContains(response,'id="trip-calculation-panel"')
        self.assertContains(response,'id="trip-editor"')
        self.assertFalse(response.context['read_only'])

    def test_locked_trip_opens_read_only_and_rejects_post(self):
        from django.utils import timezone
        Travel.objects.filter(pk=self.travel.pk).update(approved_at=timezone.now())
        url=f'/travels/{self.travel.pk}/'
        response=self.client.get(url)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['read_only'])
        self.assertContains(response,'class="trip-editor-fields" disabled')
        self.assertNotContains(response,'js/travel-form.js')
        self.assertEqual(self.client.post(url,{'purpose':'Forged change'}).status_code,403)
        self.travel.refresh_from_db();self.assertEqual(self.travel.purpose,'Test')

    def test_view_only_user_has_read_only_form(self):
        from .models import UserAccess
        from django.contrib.auth.models import Permission
        reader=get_user_model().objects.create_user(username='trip-reader')
        UserAccess.objects.create(user=reader,scope='all')
        reader.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='view_travel'))
        self.client.force_login(reader)
        response=self.client.get(f'/travels/{self.travel.pk}/')
        self.assertTrue(response.context['read_only'])
        self.assertEqual(self.client.post(f'/travels/{self.travel.pk}/edit/',self.data).status_code,403)


class TravelListSearchTests(TravelCostEntryTests):
    def test_filters_and_actions(self):
        Travel.objects.filter(pk=self.travel.pk).update(protocol_number='ABC-123',purpose='Conference')
        response=self.client.get('/',{'protocol':'ABC','purpose':'Conference','year':'2026'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertContains(response,'selected-trip')
        self.assertEqual(self.client.get('/',{'year':'2025'}).context['page'].paginator.count,0)

    def test_invalid_filters_show_errors_and_no_results(self):
        response=self.client.get('/',{'travel_from':'2026-12-01','travel_to':'2026-01-01'})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['search_form'].errors)
        self.assertEqual(response.context['page'].paginator.count,0)

    def test_scope_cannot_be_widened_by_employee_filter(self):
        response=self.client.get('/',{'employee':self.other.pk})
        self.assertTrue(response.context['search_form'].errors)
        self.assertEqual(response.context['page'].paginator.count,0)

    def test_date_range_matches_overlapping_trip(self):
        response=self.client.get('/',{'travel_from':'2026-11-04','travel_to':'2026-11-04'})
        self.assertEqual(response.context['page'].paginator.count,1)


class OtherDocumentTests(ApprovalPDFTests):
    def test_activity_document_from_list(self):
        from io import BytesIO
        from pypdf import PdfReader
        self.travel.actions_description='Completed meeting and training';self.travel.save()
        self.client.force_login(self.user)
        url=f'/travels/{self.travel.pk}/documents/'
        self.assertEqual(self.client.get(url).status_code,200)
        response=self.client.post(url,{'kind':'activity','print_date':'2026-11-05'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('Completed meeting and training',text)

    def test_car_declaration(self):
        self.employee.car_plate='ABC123';self.employee.car_brand='Brand';self.employee.driving_license='DL123';self.employee.gender.text3='Declarant';self.employee.gender.text2='Signature';self.employee.gender.save();self.employee.save()
        self.client.force_login(self.user)
        response=self.client.post(f'/travels/{self.travel.pk}/documents/',{'kind':'car','print_date':'2026-11-05'})
        self.assertEqual(response['Content-Type'],'application/pdf')

    def test_other_documents_permission_required(self):
        self.client.force_login(get_user_model().objects.create_user(username='documents-outsider'))
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/documents/').status_code,403)


    def test_friends_declaration_uses_only_relevant_nights(self):
        from .models import AccommodationType
        from io import BytesIO
        from pypdf import PdfReader
        friends=AccommodationType.objects.create(name='Friends',code='FR',has_cost=False,requires_declaration=True)
        self.travel.overnights.update(accommodation_type=friends)
        self.employee.gender.text2='Signature';self.employee.gender.text3='Declarant';self.employee.gender.save()
        self.client.force_login(self.user)
        response=self.client.post(f'/travels/{self.travel.pk}/documents/',{'kind':'friends','print_date':'2026-11-05'})
        self.assertEqual(response['Content-Type'],'application/pdf')
        text=' '.join(p.extract_text() for p in PdfReader(BytesIO(response.content)).pages)
        self.assertIn('03/11/2026',text)

    def test_print_permission_does_not_bypass_trip_scope(self):
        from django.contrib.auth.models import Permission
        outsider=get_user_model().objects.create_user(username='documents-print-outsider')
        outsider.user_permissions.add(Permission.objects.get(content_type__app_label='core',codename='print_travel'))
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(f'/travels/{self.travel.pk}/documents/').status_code,404)


class GreekDateInputTests(SimpleTestCase):
    def test_display_and_submission(self):
        from .date_widgets import GreekDateInput
        from django import forms
        class Sample(forms.Form):
            day=forms.DateField(widget=GreekDateInput(),input_formats=['%Y-%m-%d'])
        form=Sample({'day':'04/11/2026'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data['day'],date(2026,11,4))
        self.assertIn('04/11/2026',str(Sample(initial={'day':date(2026,11,4)})))
        self.assertFalse(Sample({'day':'31/02/2026'}).is_valid())

    def test_snapshot_display(self):
        from .templatetags.greek_dates import greek_date
        self.assertEqual(greek_date('2026-11-04'),'04/11/2026')


class TripYearDropdownTests(TravelCostEntryTests):
    def test_year_dropdown_contains_only_visible_trip_years(self):
        from .travel_search import TravelSearchForm
        form=TravelSearchForm(user=self.user)
        self.assertEqual(list(form.fields['year'].choices)[1:],[(2026,'2026')])
        self.assertEqual(form.fields['year'].widget.input_type,'select')
        self.assertNotIn(2025,[value for value,label in form.fields['year'].choices])

    def test_cross_year_trip_includes_both_years(self):
        from .travel_search import TravelSearchForm
        Travel.objects.filter(pk=self.travel.pk).update(return_at=date(2027,1,2))
        self.assertEqual(list(TravelSearchForm(user=self.user).fields['year'].choices)[1:],[(2027,'2027'),(2026,'2026')])


class SingleTransportTests(EstimateCalculationTests):
    def test_combined_mode_calculates_both_components_once(self):
        from .models import TransportMode
        from .calculation import calculate_estimate
        mode=TransportMode.objects.create(name='Car and ferry',code='CF',has_mileage_cost=True,has_ticket_cost=True)
        self.travel.transport=mode;self.travel.transport_configured=True;self.travel.ticket_cost=Decimal('120');self.travel.transfer_cost=Decimal('10');self.travel.save()
        result=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(result.mileage,Decimal('80'))
        self.assertEqual(result.tickets,Decimal('120'))
        self.assertEqual(result.other,Decimal('10'))
        self.assertEqual(result.total,Decimal('410'))

    def test_no_cost_mode_ignores_legacy_charges(self):
        from .models import TransportMode
        from .calculation import calculate_estimate
        mode=TransportMode.objects.create(name='Service car',code='SC')
        self.travel.transport=mode;self.travel.transport_configured=True;self.travel.save()
        result=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(result.mileage,0)
        self.assertEqual(result.tickets,0)
        self.assertEqual(result.other,0)

    def test_single_transport_form_and_server_flags(self):
        from .models import TransportMode
        mode=TransportMode.objects.create(name='Private car',code='PC',has_mileage_cost=True)
        self.travel.transport=mode;self.travel.transport_configured=True;self.travel.save()
        self.client.force_login(self.user)
        response=self.client.get(f'/travels/{self.travel.pk}/')
        self.assertNotContains(response,'name="expenses-0-kind"')
        payload={'transport_section':'1','employee':self.employee.pk,'route':self.route.pk,'departure_at':'03/11/2026','return_at':'05/11/2026','work_starts_at':'03/11/2026','work_ends_at':'05/11/2026','transport':mode.pk,'ticket_cost':'999','transfer_cost':'999'}
        self.assertEqual(self.client.post(f'/travels/{self.travel.pk}/edit/',payload).status_code,302)
        self.travel.refresh_from_db()
        self.assertIsNone(self.travel.ticket_cost)
        self.assertIsNone(self.travel.transfer_cost)
        self.assertEqual(self.travel.calculations.latest('revision').tickets,0)

    def test_ticket_mode_requires_ticket_amount(self):
        from .models import TransportMode
        mode=TransportMode.objects.create(name='Airplane',code='AIR',has_ticket_cost=True)
        self.travel.transport=mode;self.travel.transport_configured=True;self.travel.save()
        self.client.force_login(self.user)
        payload={'transport_section':'1','employee':self.employee.pk,'route':self.route.pk,'departure_at':'03/11/2026','return_at':'05/11/2026','work_starts_at':'03/11/2026','work_ends_at':'05/11/2026','transport':mode.pk}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertEqual(response.status_code,200)
        self.assertIn('ticket_cost',response.context['form'].errors)
