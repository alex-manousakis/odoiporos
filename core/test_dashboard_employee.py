from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from . import tests as fixtures
from .models import Department,Employee,UserAccess,Travel
from .calculation import calculate_estimate

class DashboardEmployeeTests(TestCase):
    def setUp(self):
        fixtures.EstimateCalculationTests.setUp(self)
        original=calculate_estimate(self.travel.pk,self.user)
        department=Department.objects.create(name='Department C')
        self.employee.department=department;self.employee.save()
        self.head=get_user_model().objects.create_user('dashboard-head')
        self.head_employee=Employee.objects.create(user=self.head,display_name='Head of C',department=department)
        permission=Permission.objects.get(codename='view_travel',content_type__app_label='core')
        self.head.user_permissions.add(permission)
        access=UserAccess.objects.create(user=self.head,scope='department');access.departments.add(department)
        own_trip=Travel.objects.create(employee=self.head_employee,route=self.route,status=self.travel.status,departure_at=date(2026,12,1),return_at=date(2026,12,2),work_starts_at=date(2026,12,1),work_ends_at=date(2026,12,2))
        original.pk=None;original.travel=own_trip;original.total=Decimal('200');original.save()
        outsider=Employee.objects.create(display_name='Forbidden employee',department=Department.objects.create(name='Other department'))
        outside_trip=Travel.objects.create(employee=outsider,route=self.route,status=self.travel.status,departure_at=date(2026,12,1),return_at=date(2026,12,2),work_starts_at=date(2026,12,1),work_ends_at=date(2026,12,2))
        original.pk=None;original.travel=outside_trip;original.total=Decimal('999999');original.save()
        self.outsider=outsider
        self.client.force_login(self.head)

    def test_head_defaults_to_own_figures(self):
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.context['selected_employee'],str(self.head_employee.pk))
        self.assertEqual(response.context['scope_label'],'Head of C')
        self.assertEqual(response.context['total'],Decimal('200'))
        self.assertEqual(response.context['trip_count'],1)
        self.assertTrue(response.context['show_employee_filter'])

    def test_selected_employee_updates_all_panels_and_links(self):
        response=self.client.get('/dashboard/',{'year':2026,'employee':self.employee.pk})
        context=response.context
        self.assertEqual(context['total'],Decimal('410'))
        self.assertEqual(context['monthly'][10]['cost'],Decimal('410'))
        self.assertEqual(context['monthly'][11]['cost'],0)
        self.assertEqual(context['yearly'][0]['cost'],Decimal('410'))
        self.assertEqual(context['destinations'][0]['cost'],Decimal('410'))
        self.assertTrue(all(trip.employee_id==self.employee.pk for trip in context['recent']))
        self.assertTrue(all(trip.employee_id==self.employee.pk for trip in context['upcoming']))
        self.assertContains(response,'employee='+str(self.employee.pk))

    def test_all_selection_is_limited_to_department(self):
        response=self.client.get('/dashboard/',{'year':2026,'employee':''})
        self.assertEqual(response.context['total'],Decimal('610'))
        self.assertEqual(response.context['trip_count'],2)
        self.assertNotContains(response,'Forbidden employee')
        self.assertNotContains(response,'999.999')

    def test_forged_employee_selection_returns_no_data(self):
        for employee in [str(self.outsider.pk),'invalid','999999999999999999999999999']:
            response=self.client.get('/dashboard/',{'year':2026,'employee':employee})
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['trip_count'],0)
            self.assertEqual(response.context['total'],0)
            self.assertTrue(response.context['employee_form'].errors)

    def test_ordinary_employee_has_no_dropdown(self):
        UserAccess.objects.create(user=self.user,scope='own')
        self.user.user_permissions.add(Permission.objects.get(codename='view_travel',content_type__app_label='core'))
        self.client.force_login(self.user)
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertFalse(response.context['show_employee_filter'])
        self.assertEqual(response.context['total'],Decimal('410'))
        self.assertNotContains(response,'id="id_employee"')
