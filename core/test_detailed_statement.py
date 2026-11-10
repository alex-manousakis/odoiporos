from datetime import date
from decimal import Decimal
from io import BytesIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from pypdf import PdfReader
from . import tests as fixtures
from .models import SettlementPeriod,ApplicationParameters,Employee,UserAccess,Travel,DetailedStatement,AuditEvent
from .detailed_statement import generate_statement,StatementForm

class DetailedStatementTests(TestCase):
    def setUp(self):
        fixtures.ApprovalPDFTests.setUp(self)
        self.employee.tax_number='123456789';self.employee.iban='GR-TEST-ACCOUNT';self.employee.has_mtpy=True;self.employee.has_geotee=True;self.employee.save()
        self.period=SettlementPeriod.objects.create(name='November 2026',starts_on=date(2026,11,1),ends_on=date(2026,11,30),has_mtpy=True,has_geotee=True)
        params=ApplicationParameters.objects.get(pk=1);params.mtpy=2;params.geotee=5;params.save()

    def generate(self):return generate_statement(self.user,self.employee,self.period,self.signer,date(2026,11,10))

    def test_columns_totals_and_legacy_deduction_rules(self):
        document=self.generate();source=document.source
        self.assertEqual(Decimal(source['daily']),120)
        self.assertEqual(Decimal(source['expenses']),290)
        self.assertEqual(Decimal(source['totals']['total']),410)
        self.assertEqual(Decimal(source['deductions']['mtpy']['amount']),Decimal('2.40'))
        self.assertEqual(Decimal(source['deductions']['geotee']['amount']),Decimal('6.00'))
        self.assertEqual(Decimal(source['net']),Decimal('401.60'))
        self.assertTrue(source['provisional'])
        reader=PdfReader(BytesIO(bytes(document.content)))
        self.assertGreaterEqual(len(reader.pages),2)
        text=' '.join(page.extract_text() for page in reader.pages)
        self.assertNotIn('ΠΡΟΣ ΕΛΕΓΧΟ',text)
        for value in ['ΚΑΤΑΣΤΑΣΗ ΠΛΗΡΩΜΗΣ','401,60','GR-TEST-ACCOUNT','123456789']:self.assertIn(value,text)

    def test_each_deduction_requires_both_employee_and_period_flags(self):
        self.employee.has_mtpy=False;self.employee.save()
        self.period.has_geotee=False;self.period.save()
        source=self.generate().source
        self.assertEqual(Decimal(source['taxes']),0)
        self.assertEqual(Decimal(source['net']),410)

    def test_unknown_deduction_flags_block_instead_of_assuming(self):
        self.employee.has_mtpy=None;self.employee.save()
        with self.assertRaises(ValidationError):self.generate()
        self.assertFalse(DetailedStatement.objects.exists())

    def test_departure_date_inclusive_period_and_latest_revision_once(self):
        from .calculation import calculate_estimate
        calculate_estimate(self.travel.pk,self.user)
        self.period.starts_on=self.travel.departure_at;self.period.ends_on=self.travel.departure_at;self.period.save()
        source=self.generate().source
        self.assertEqual(len(source['rows']),1)
        self.assertEqual(source['rows'][0]['revision'],2)
        self.period.starts_on=date(2026,11,4);self.period.ends_on=date(2026,11,30);self.period.save()
        with self.assertRaises(ValidationError):self.generate()

    def test_scope_and_print_permission_enforced(self):
        outsider=get_user_model().objects.create_user('statement-outsider')
        with self.assertRaises(PermissionDenied):generate_statement(outsider,self.employee,self.period,self.signer,date(2026,11,10))
        outsider.user_permissions.add(Permission.objects.get(codename='print_travel',content_type__app_label='core'),Permission.objects.get(codename='view_travel',content_type__app_label='core'))
        UserAccess.objects.create(user=outsider,scope='own')
        outsider=get_user_model().objects.get(pk=outsider.pk)
        self.client.force_login(outsider)
        response=self.client.post('/reports/detailed-statement/',{'employee':self.employee.pk,'period':self.period.pk,'signatory':self.signer.pk,'print_date':'10/11/2026','export':'download'})
        self.assertEqual(response.status_code,200);self.assertIn('employee',response.context['form'].errors)

    def test_missing_and_stale_calculations_not_silently_omitted(self):
        self.travel.purpose='New purpose';self.travel.save()
        self.travel.expenses.filter(kind='ticket').update(estimated_amount=999)
        with self.assertRaises(ValidationError):self.generate()
        self.assertFalse(DetailedStatement.objects.exists())

    def test_print_and_download_are_private_archived_and_do_not_mark_paid(self):
        self.client.force_login(self.user)
        data={'employee':self.employee.pk,'period':self.period.pk,'signatory':self.signer.pk,'print_date':'10/11/2026','export':'download'}
        response=self.client.post('/reports/detailed-statement/',data)
        self.assertEqual(response.status_code,302)
        downloaded=self.client.get(response.url)
        self.assertEqual(downloaded.status_code,200)
        self.assertIn('attachment',downloaded['Content-Disposition'])
        self.assertIn('no-store',downloaded['Cache-Control'])
        document=DetailedStatement.objects.get();original=bytes(document.content)
        self.employee.iban='CHANGED-LATER';self.employee.save()
        self.assertEqual(self.client.get(response.url).content,original)
        inline=self.client.get(response.url.split('?')[0]);self.assertIn('inline',inline['Content-Disposition'])
        self.assertTrue(AuditEvent.objects.filter(action='create',target_type='core.detailedstatement',actor=self.user).exists())
        self.assertFalse(self.period.items.exists())

    def test_accounting_total_override_is_explicitly_reconciled(self):
        from .models import AccountingAdjustment
        from .user_management import adjustment_permissions
        from .calculation import calculate_estimate
        self.user.user_permissions.add(*adjustment_permissions());self.user=get_user_model().objects.get(pk=self.user.pk)
        AccountingAdjustment.objects.create(travel=self.travel,values={'total':'450'},reason='Manual total',updated_by=self.user)
        calculate_estimate(self.travel.pk,self.user)
        source=self.generate().source
        self.assertEqual(Decimal(source['adjustment']),40)
        self.assertEqual(Decimal(source['net']),Decimal('441.60'))

    def test_personal_default_and_department_filter(self):
        self.client.force_login(self.user)
        response=self.client.get('/reports/detailed-statement/')
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['form'].initial['employee'],self.employee.pk)
        self.assertEqual(response.context['form'].initial['signatory'],self.signer.pk)
        self.assertEqual(self.client.get('/reports/detailed-statement/',{'employee':'not-a-number'}).status_code,200)

    def test_long_purpose_continues_with_one_header_per_page(self):
        self.travel.purpose=('Συνάντηση για την υποστήριξη στη διαχείριση και ολοκλήρωση των πράξεων του προγράμματος και σχεδιασμό ενεργειών τεχνικής υποστήριξης. '*35)
        self.travel.save()
        reader=PdfReader(BytesIO(bytes(self.generate().content)))
        self.assertGreater(len(reader.pages),2)
        for page in reader.pages:self.assertLessEqual(page.extract_text().count('ΑΙΤΙΟΛΟΓΙΑ'),1)
        self.assertIn('401,60',' '.join(page.extract_text() for page in reader.pages))
