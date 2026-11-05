from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from . import tests as fixtures
from .models import Employee,UserAccess,Department,EmployeeCategoryHistory,Travel
from .forms import TravelForm
from .views import can_edit_costs
from .access import can_modify_travel
from .user_management import adjustment_permissions

class TripWriteScopeTests(TestCase):
    setUp=fixtures.EstimateCalculationTests.setUp

    def head(self):
        department=Department.objects.create(name='Department')
        self.employee.department=department;self.employee.save()
        head=get_user_model().objects.create_user('department-head')
        own=Employee.objects.create(display_name='Head employee',user=head,department=department)
        EmployeeCategoryHistory.objects.create(employee=own,category=self.category,valid_from=date(2026,1,1))
        access=UserAccess.objects.create(user=head,scope='department');access.departments.add(department)
        head.user_permissions.add(*Permission.objects.filter(content_type__app_label='core',codename__in=['view_travel','add_travel','change_travel','delete_travel']))
        self.client.force_login(head)
        return head,own

    def test_head_sees_department_but_cannot_edit_recalculate_or_delete_others(self):
        head,own=self.head()
        response=self.client.get(f'/travels/{self.travel.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['read_only'])
        self.assertFalse(can_edit_costs(head,self.travel))
        self.assertFalse(can_modify_travel(head,self.travel,'delete'))
        self.assertEqual(self.client.post(f'/travels/{self.travel.pk}/edit/',{}).status_code,403)
        self.assertEqual(self.client.post(f'/travels/{self.travel.pk}/costs/',{}).status_code,403)
        from .calculation import calculate_estimate
        from django.core.exceptions import PermissionDenied
        with self.assertRaises(PermissionDenied):calculate_estimate(self.travel.pk,head)

    def test_create_selects_only_head_and_rejects_other_employee_post(self):
        head,own=self.head()
        response=self.client.get('/travels/new/')
        self.assertEqual(response.context['form'].initial['employee'],own.pk)
        self.assertEqual(list(response.context['form'].fields['employee'].queryset),[own])
        payload={'employee':self.employee.pk,'route':self.route.pk,'departure_at':'03/11/2026','return_at':'05/11/2026','work_starts_at':'03/11/2026','work_ends_at':'05/11/2026'}
        response=self.client.post('/travels/new/',payload)
        self.assertEqual(response.status_code,200)
        self.assertIn('employee',response.context['form'].errors)
        self.assertEqual(Travel.objects.count(),1)
        payload['employee']=own.pk
        self.assertEqual(self.client.post('/travels/new/',payload).status_code,302)
        trip=Travel.objects.get(employee=own)
        self.assertTrue(can_edit_costs(head,trip))

    def test_accounting_can_modify_scoped_others_but_not_other_departments(self):
        head,own=self.head();head.user_permissions.add(*adjustment_permissions())
        head=get_user_model().objects.get(pk=head.pk)
        self.assertTrue(can_edit_costs(head,self.travel))
        self.assertIn(self.employee,TravelForm(user=head).fields['employee'].queryset)
        other=Employee.objects.create(display_name='Outside scope')
        self.travel.employee=other;self.travel.save()
        self.assertFalse(can_edit_costs(head,self.travel))
        self.assertFalse(can_modify_travel(head,self.travel,'delete'))
