from datetime import date
from decimal import Decimal
from django.test import TestCase,override_settings
from django.contrib.auth import get_user_model
from . import tests as fixtures
from .models import UserAccess,Employee,Travel,CalculationSnapshot,AuditEvent
from .calculation import calculate_estimate

class DashboardTests(TestCase):
    setUp=fixtures.EstimateCalculationTests.setUp

    def login(self):
        UserAccess.objects.get_or_create(user=self.user,defaults={'scope':'own'})
        from django.contrib.auth.models import Permission
        self.user.user_permissions.add(Permission.objects.get(codename='view_travel',content_type__app_label='core'))
        self.client.force_login(self.user)

    def test_requires_login_and_is_default_login_destination(self):
        self.assertEqual(self.client.get('/dashboard/').status_code,302)
        from django.conf import settings
        self.assertEqual(settings.LOGIN_REDIRECT_URL,'core:dashboard')

    def test_latest_estimate_counted_once_and_monthly_totals(self):
        calculate_estimate(self.travel.pk,self.user)
        calculate_estimate(self.travel.pk,self.user)
        self.login()
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['total'],Decimal('410'))
        self.assertEqual(response.context['trip_count'],1)
        self.assertEqual(response.context['monthly'][10]['cost'],Decimal('410'))
        self.assertEqual(response.context['destination_count'],1)
        self.assertContains(response,'410,00')
        self.assertTrue(AuditEvent.objects.filter(route='core:dashboard',actor=self.user).exists())

    def test_other_employees_data_is_not_disclosed(self):
        calculate_estimate(self.travel.pk,self.user)
        other=Employee.objects.create(display_name='Hidden person')
        trip=Travel.objects.create(employee=other,route=self.route,status=self.travel.status,departure_at=date(2025,1,1),return_at=date(2025,1,2),work_starts_at=date(2025,1,1),work_ends_at=date(2025,1,2))
        snapshot=self.travel.calculations.first();snapshot.pk=None;snapshot.travel=trip;snapshot.total=Decimal('999999');snapshot.save()
        self.login()
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.context['total'],Decimal('410'))
        self.assertNotIn(2025,response.context['years'])
        self.assertNotContains(response,'Hidden person')
        self.assertNotContains(response,'999.999')

    def test_empty_and_missing_calculations_do_not_invent_costs(self):
        self.login()
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.context['missing'],1)
        self.assertEqual(response.context['total'],0)
        self.assertEqual(response.context['average'],0)
        self.assertContains(response,'δεν έχουν εκτίμηση')
        self.travel.delete()
        response=self.client.get('/dashboard/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['trip_count'],0)

    def test_year_selection_and_invalid_year(self):
        self.login()
        self.assertEqual(self.client.get('/dashboard/',{'year':'garbage'}).status_code,200)
        self.assertEqual(self.client.get('/dashboard/',{'year':'9999'}).status_code,200)
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.context['year'],2026)

    def test_no_trip_permission_has_no_data(self):
        self.client.force_login(self.user)
        UserAccess.objects.create(user=self.user,scope='all')
        response=self.client.get('/dashboard/',{'year':2026})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['trip_count'],0)

    def test_login_from_root_lands_on_dashboard_but_deep_links_are_preserved(self):
        self.user.set_password('Dashboard-Test-Password-123!');self.user.save()
        response=self.client.post('/accounts/login/',{'username':self.user.username,'password':'Dashboard-Test-Password-123!','next':'/'})
        self.assertRedirects(response,'/dashboard/',fetch_redirect_response=False)
        self.client.logout()
        response=self.client.post('/accounts/login/',{'username':self.user.username,'password':'Dashboard-Test-Password-123!','next':f'/travels/{self.travel.pk}/'})
        self.assertRedirects(response,f'/travels/{self.travel.pk}/',fetch_redirect_response=False)
