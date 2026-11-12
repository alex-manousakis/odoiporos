from datetime import date
from decimal import Decimal
from io import BytesIO
from copy import deepcopy
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from pypdf import PdfReader
from . import test_detailed_statement as detailed_fixtures
from .models import Employee,Travel,UserAccess,SummaryStatement,DetailedStatement,ApplicationParameters
from .user_management import adjustment_permissions

def report_permissions():
    return Permission.objects.filter(content_type__app_label='core',codename__in=['view_summarystatement','print_summarystatement'])
from .summary_statement import generate_summary
from .detailed_statement import build_statement_source

class SummaryStatementTests(TestCase):
    def setUp(self):
        detailed_fixtures.DetailedStatementTests.setUp(self)
        self.user.user_permissions.add(Permission.objects.get(codename='view_travel'), *report_permissions())
        self.user=get_user_model().objects.get(pk=self.user.pk)
        UserAccess.objects.create(user=self.user,scope='all')

    def generate(self):return generate_summary(self.user,self.period,self.signer,date(2026,11,10))

    def employee_actual(self,name,mtpy,geotee,daily):
        employee=Employee.objects.create(display_name=name,has_mtpy=mtpy,has_geotee=geotee)
        trip=Travel.objects.create(employee=employee,route=self.route,status=self.travel.status,applied_category=self.category,
            departure_at=date(2026,11,7),return_at=date(2026,11,7),work_starts_at=date(2026,11,7),work_ends_at=date(2026,11,7))
        self.actual(trip,daily)
        return employee,trip

    def actual(self,trip,daily):
        snapshot=self.travel.calculations.filter(stage='estimate').first()
        snapshot.pk=None;snapshot.travel=trip;snapshot.stage='actual';snapshot.revision=1;snapshot.frozen_at=timezone.now()
        snapshot.inputs=deepcopy(snapshot.inputs);snapshot.inputs['days']=1
        snapshot.inputs['allowance_from']=trip.departure_at.isoformat();snapshot.inputs['allowance_to']=trip.return_at.isoformat()
        snapshot.daily_domestic=Decimal(daily);snapshot.daily_abroad=0
        for key in ['mileage','tickets','other','claimed_accommodation','allowed_accommodation']:setattr(snapshot,key,0)
        snapshot.total=Decimal(daily);snapshot.document_budget=Decimal(daily);snapshot.save()

    def test_groups_totals_schedules_and_three_report_pdf(self):
        self.employee_actual('Employee without MTPY',False,True,'40')
        document=self.generate();source=document.source
        self.assertEqual(len(source['groups'][0]['employees']),1)
        self.assertEqual(len(source['groups'][1]['employees']),1)
        self.assertEqual(Decimal(source['totals']['daily']),160)
        self.assertEqual(Decimal(source['totals']['gross']),450)
        self.assertEqual(Decimal(source['totals']['mtpy']),Decimal('2.40'))
        self.assertEqual(Decimal(source['totals']['geotee']),Decimal('8.00'))
        self.assertEqual(Decimal(source['totals']['net']),Decimal('439.60'))
        self.assertEqual(Decimal(source['geotee_totals']['geotee']),Decimal('8.00'))
        self.assertEqual(DetailedStatement.objects.count(),0)
        self.assertNotIn('iban',str(source).lower());self.assertNotIn('tax_number',str(source))
        reader=PdfReader(BytesIO(bytes(document.content)))
        self.assertEqual(len(reader.pages),3)
        self.assertEqual(len(reader.outline),3)
        self.assertIn('ΣΥΝΟΠΤΙΚΗ',reader.pages[0].extract_text())
        self.assertIn('ΚΡΑΤΗΣΕΩΝ ΜΤΠΥ',reader.pages[1].extract_text())
        self.assertIn('ΚΡΑΤΗΣΕΩΝ ΓΕΩΤΕΕ',reader.pages[2].extract_text())

    def test_period_flags_disable_both_deductions_and_reclassify(self):
        self.period.has_mtpy=False;self.period.has_geotee=False;self.period.save()
        source=self.generate().source
        self.assertEqual(len(source['groups'][0]['employees']),1)
        self.assertEqual(len(source['groups'][1]['employees']),0)
        self.assertEqual(Decimal(source['totals']['taxes']),0)
        self.assertEqual(Decimal(source['totals']['net']),410)
        self.assertEqual(source['geotee_employees'],[])

    def test_individual_rounding_is_summed_and_matches_detailed_calculations(self):
        self.actual(self.travel,'.25')
        self.employee_actual('Rounding employee',True,False,'.25')
        self.period.has_geotee=False;self.period.save()
        source=self.generate().source
        self.assertEqual(Decimal(source['totals']['mtpy']),Decimal('.02'))
        individual=build_statement_source(self.user,self.employee,self.period,self.signer,date(2026,11,10))
        self.assertEqual(Decimal(individual['deductions']['mtpy']['amount']),Decimal('.01'))

    def test_report_permissions_and_scope_is_not_expanded(self):
        self.user.user_permissions.remove(*report_permissions());user=get_user_model().objects.get(pk=self.user.pk)
        with self.assertRaises(PermissionDenied):generate_summary(user,self.period,self.signer,date(2026,11,10))
        self.user.user_permissions.add(Permission.objects.get(codename='view_travel'), *report_permissions());self.user=get_user_model().objects.get(pk=self.user.pk)
        access=self.user.travel_access;access.scope='own';access.save()
        self.employee_actual('OUTSIDE-SCOPE',True,True,'9999')
        source=self.generate().source
        self.assertEqual(source['employee_ids'],[self.employee.pk])
        self.assertEqual(Decimal(source['totals']['gross']),410)
        self.assertNotIn('OUTSIDE-SCOPE',str(source))

    def test_download_rechecks_every_employee_and_archived_bytes_unchanged(self):
        self.employee_actual('Second employee',False,True,'40')
        self.client.force_login(self.user)
        response=self.client.post('/reports/summary-statement/',{'period':self.period.pk,'signatory':self.signer.pk,'print_date':'10/11/2026','export':'download'})
        self.assertEqual(response.status_code,302)
        first=self.client.get(response.url);self.assertEqual(first.status_code,200)
        self.assertIn('attachment',first['Content-Disposition']);self.assertIn('no-store',first['Cache-Control'])
        self.employee.display_name='Changed later';self.employee.save()
        self.assertEqual(self.client.get(response.url).content,first.content)
        access=self.user.travel_access;access.scope='own';access.save()
        self.assertEqual(self.client.get(response.url).status_code,404)

    def test_invalid_employee_data_blocks_whole_export(self):
        employee,trip=self.employee_actual('Unknown deduction setting',None,False,'40')
        with self.assertRaises(ValidationError):self.generate()
        self.assertFalse(SummaryStatement.objects.exists())

    def test_zero_cost_employees_not_in_payroll(self):
        self.employee_actual('ZERO-COST',False,False,'0')
        source=self.generate().source
        self.assertEqual(len(source['employees']),1)
        self.assertNotIn('ZERO-COST',str(source))

    def test_adjustment_rights_do_not_grant_report_access(self):
        self.user.user_permissions.remove(*report_permissions())
        self.user.user_permissions.add(*adjustment_permissions())
        user=get_user_model().objects.get(pk=self.user.pk)
        with self.assertRaises(PermissionDenied):generate_summary(user,self.period,self.signer,date(2026,11,10))

    def test_report_permissions_are_editable_in_user_management(self):
        from .user_management import editable_permissions
        self.assertEqual(editable_permissions().filter(content_type__model='summarystatement').count(),2)
        self.user.is_superuser=True;self.user.save()
        self.client.force_login(self.user)
        response=self.client.get('/users/'+str(self.user.pk)+'/edit/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'Εκτ. Συνοπτικής Κατάστασης')

    def test_shared_head_parameter_is_default_for_all_report_forms(self):
        from .models import Signatory
        deputy=Signatory.objects.create(name='Configured head',is_active=True)
        params=ApplicationParameters.objects.get(pk=1)
        params.organization_head=deputy;params.prosfonisiproistamenou='Shared signature heading';params.save()
        self.client.force_login(self.user)
        for url in ['/reports/summary-statement/','/reports/detailed-statement/',f'/travels/{self.travel.pk}/approval/']:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.context['form'].initial['signatory'],deputy.pk)
        self.assertEqual(self.generate().source['signatory']['heading'],'Shared signature heading')

    def test_statement_emblems_are_embedded(self):
        from .detailed_statement import generate_statement
        detailed=generate_statement(self.user,self.employee,self.period,self.signer,date(2026,11,10))
        reader=PdfReader(BytesIO(bytes(detailed.content)))
        self.assertGreater(len(reader.pages[0].images),0)
        summary=PdfReader(BytesIO(bytes(self.generate().content)))
        for page in summary.pages:self.assertGreater(len(page.images),0)

    def test_filter_defaults_and_menu_permissions(self):
        self.client.force_login(self.user)
        response=self.client.get('/reports/summary-statement/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['form'].initial['signatory'],self.signer.pk)
        self.assertContains(self.client.get('/'),'Εκτ. Συνοπτικής Κατάστασης')
        self.user.user_permissions.remove(*report_permissions())
        self.assertEqual(self.client.get('/reports/summary-statement/').status_code,403)
