from django.test import TestCase
from . import tests as fixtures
from .models import Employee,Department,UserAccess

class EmployeeFilterDefaultTests(fixtures.DepartmentAccessTests):

    def link_head(self):
        return Employee.objects.create(user=self.head,display_name='Department head',department=self.department)

    def test_department_head_defaults_to_self_and_can_select_all_or_colleague(self):
        own=self.link_head()
        response=self.client.get('/')
        self.assertEqual(str(response.context['search_form']['employee'].value()),str(own.pk))
        self.assertEqual(response.context['page'].paginator.count,0)
        response=self.client.get('/',{'employee':str(self.employee.pk)})
        self.assertEqual(response.context['page'].paginator.count,1)
        response=self.client.get('/',{'employee':''})
        self.assertEqual(response.context['page'].paginator.count,1)
        self.assertEqual(response.context['search_form']['employee'].value(),'')
        self.assertIn('employee=',response.context['filter_query'])

    def test_other_department_remains_inaccessible(self):
        self.link_head()
        response=self.client.get('/',{'employee':str(self.other.pk)})
        self.assertEqual(response.context['page'].paginator.count,0)
        self.assertIn('employee',response.context['search_form'].errors)

    def test_default_survives_year_filter_and_pagination_query(self):
        own=self.link_head()
        response=self.client.get('/',{'year':'2026','page':'1'})
        self.assertEqual(str(response.context['search_form']['employee'].value()),str(own.pk))
        self.assertIn('employee='+str(own.pk),response.context['filter_query'])

    def test_account_without_employee_uses_existing_scope(self):
        response=self.client.get('/')
        self.assertEqual(response.context['page'].paginator.count,1)
