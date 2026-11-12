from datetime import date
from decimal import Decimal
from copy import deepcopy
from io import BytesIO
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied,ValidationError
from django.utils import timezone
from pypdf import PdfReader
from . import test_detailed_statement as fixtures
from .models import Employee,Travel,Department,UserAccess,EmployeeRecordCard,AuditEvent,SettlementItem,SettlementPeriod
from .employee_card import generate_card,EmployeeCardForm

class EmployeeRecordCardTests(TestCase):
    def setUp(self):
        fixtures.DetailedStatementTests.setUp(self)
        self.user.user_permissions.add(*Permission.objects.filter(content_type__app_label='core',codename__in=['view_travel','view_employeerecordcard','print_employeerecordcard']))
        self.user=get_user_model().objects.get(pk=self.user.pk)
        self.department=Department.objects.create(name='Department C')
        self.employee.department=self.department;self.employee.save()
        self.access=UserAccess.objects.create(user=self.user,scope='department');self.access.departments.add(self.department)
        self.colleague=Employee.objects.create(display_name='Subordinate',department=self.department)
        self.outside=Employee.objects.create(display_name='Other department',department=Department.objects.create(name='Other unit'))
        self.colleague_trip=self.trip(self.colleague)
        self.trip(self.outside)

    def trip(self,employee,departure=date(2026,11,5),returned=date(2026,11,7),total='150'):
        trip=Travel.objects.create(employee=employee,route=self.route,status=self.travel.status,applied_category=self.category,
            departure_at=departure,return_at=returned,work_starts_at=departure,work_ends_at=returned)
        snapshot=self.travel.calculations.first();snapshot.pk=None;snapshot.travel=trip;snapshot.stage='actual';snapshot.revision=1;snapshot.frozen_at=timezone.now()
        snapshot.inputs=deepcopy(snapshot.inputs);snapshot.inputs.update(days=(returned-departure).days+1,allowance_from=departure.isoformat(),allowance_to=returned.isoformat(),display_overnights=2)
        snapshot.daily_domestic=120;snapshot.daily_abroad=0;snapshot.mileage=10;snapshot.tickets=5;snapshot.other=5;snapshot.allowed_accommodation=10;snapshot.claimed_accommodation=10;snapshot.total=Decimal(total);snapshot.document_budget=999;snapshot.save()
        return trip

    def generate(self,employees=None,starts=date(2026,11,1),ends=date(2026,11,30)):
        return generate_card(self.user,employees or [self.colleague.pk],starts,ends)

    def test_head_can_export_subordinates_without_accounting_rights(self):
        document=self.generate();card=document.source['cards'][0];row=card['rows'][0]
        self.assertEqual(Decimal(row['transport']),20)
        self.assertEqual(Decimal(row['daily']),120)
        self.assertEqual(Decimal(row['hotel']),10)
        self.assertEqual(Decimal(row['total']),150) # total cost, not approval document budget
        self.assertEqual(Decimal(row['nights']),2)
        self.assertEqual(Decimal(card['totals']['factor']),3)
        self.assertEqual(document.employees.get(),self.colleague)
        self.assertNotIn('iban',str(document.source).lower())
        self.assertNotIn('tax_number',str(document.source))
        reader=PdfReader(BytesIO(bytes(document.content)));self.assertEqual(len(reader.pages),1)
        self.assertGreater(float(reader.pages[0].mediabox.width),float(reader.pages[0].mediabox.height))
        text=reader.pages[0].extract_text()
        for fragment in ['Καρτέλα Εργαζομένου','Subordinate','05/11/2026','150,00','ΣΥΝΟΛΑ']:self.assertIn(fragment,text)

    def test_scope_applies_to_form_forged_posts_and_direct_generation(self):
        form=EmployeeCardForm(user=self.user)
        self.assertIn(self.colleague,form.fields['employees'].queryset)
        self.assertNotIn(self.outside,form.fields['employees'].queryset)
        with self.assertRaises(PermissionDenied):self.generate([self.outside.pk])
        self.client.force_login(self.user)
        response=self.client.post('/reports/employee-card/',{'employees':[self.colleague.pk,self.outside.pk],'starts_on':'01/11/2026','ends_on':'30/11/2026'})
        self.assertEqual(response.status_code,200)
        self.assertIn('employees',response.context['form'].errors)
        self.assertFalse(EmployeeRecordCard.objects.exists())

    def test_own_user_cannot_export_colleague_and_report_permission_is_required(self):
        self.access.scope='own';self.access.save()
        with self.assertRaises(PermissionDenied):self.generate()
        self.user.user_permissions.remove(Permission.objects.get(codename='print_employeerecordcard'))
        user=get_user_model().objects.get(pk=self.user.pk)
        with self.assertRaises(PermissionDenied):generate_card(user,[self.employee.pk],date(2026,1,1),date(2026,12,31))
        self.client.force_login(user)
        self.assertEqual(self.client.get('/reports/employee-card/').status_code,403)
        self.assertNotContains(self.client.get('/'),'href="/reports/employee-card/"')

    def test_range_overlap_inclusive_full_amounts_and_validated_dates(self):
        spanning=self.trip(self.colleague,date(2026,10,20),date(2026,12,5),'75')
        before=self.trip(self.colleague,date(2026,10,1),date(2026,10,31),'20')
        source=self.generate(starts=date(2026,11,7),ends=date(2026,11,7)).source
        rows=source['cards'][0]['rows']
        self.assertEqual({row['travel_id'] for row in rows},{self.colleague_trip.pk,spanning.pk})
        self.assertEqual(Decimal(source['cards'][0]['totals']['total']),225)
        form=EmployeeCardForm({'employees':[self.colleague.pk],'starts_on':'12/11/2026','ends_on':'01/11/2026'},user=self.user)
        self.assertFalse(form.is_valid());self.assertIn('ends_on',form.errors)
        with self.assertRaises(ValidationError):self.generate(starts=date(2026,12,1),ends=date(2026,11,1))

    def test_multiple_employees_have_separate_cards_and_empty_card(self):
        empty=Employee.objects.create(display_name='No trips employee',department=self.department,is_active=False)
        document=self.generate([self.employee.pk,self.colleague.pk,empty.pk])
        reader=PdfReader(BytesIO(bytes(document.content)));self.assertEqual(len(reader.pages),3)
        self.assertTrue(any('Δεν υπάρχουν μετακινήσεις' in p.extract_text() for p in reader.pages))
        self.assertTrue(any('Subordinate' in p.extract_text() for p in reader.pages))
        form=EmployeeCardForm(user=self.user);self.assertIn(empty,form.fields['employees'].queryset)
        form=EmployeeCardForm({'starts_on':'01/01/2026','ends_on':'12/11/2026'},user=self.user)
        self.assertFalse(form.is_valid());self.assertIn('employees',form.errors)

    def test_stale_or_missing_estimate_blocks_export_and_actual_is_preferred(self):
        self.travel.expenses.filter(kind='ticket').update(estimated_amount=999)
        with self.assertRaises(ValidationError):self.generate([self.employee.pk])
        self.assertFalse(EmployeeRecordCard.objects.exists())
        self.travel.calculations.all().delete()
        with self.assertRaises(ValidationError):self.generate([self.employee.pk])
        # The colleague's frozen actual remains printable even if current input data changed.
        self.colleague_trip.ticket_cost=800;self.colleague_trip.save()
        self.assertEqual(self.generate().source['cards'][0]['rows'][0]['stage'],'actual')

    def test_settled_calculation_from_any_period_is_used(self):
        actual=self.colleague_trip.calculations.get()
        SettlementItem.objects.create(period=self.period,calculation=actual)
        source=self.generate().source
        self.assertEqual(source['cards'][0]['rows'][0]['calculation_id'],actual.pk)

    def test_download_is_archived_audited_and_rechecks_current_scope(self):
        self.client.force_login(self.user)
        response=self.client.post('/reports/employee-card/',{'employees':[self.colleague.pk],'starts_on':'01/11/2026','ends_on':'30/11/2026','export':'download'})
        self.assertEqual(response.status_code,302)
        pdf=self.client.get(response.url);self.assertEqual(pdf.status_code,200)
        self.assertIn('attachment',pdf['Content-Disposition']);self.assertIn('no-store',pdf['Cache-Control'])
        self.colleague.display_name='Renamed later';self.colleague.save()
        self.assertEqual(self.client.get(response.url).content,pdf.content)
        self.assertTrue(AuditEvent.objects.filter(actor=self.user,target_type='core.employeerecordcard',action='create').exists())
        self.assertTrue(AuditEvent.objects.filter(actor=self.user,action='download',route='core:employee_card_download').exists())
        self.access.departments.clear()
        self.assertEqual(self.client.get(response.url).status_code,404)
        self.user.user_permissions.remove(Permission.objects.get(codename='print_employeerecordcard'))
        self.assertEqual(self.client.get(response.url).status_code,403)

    def test_defaults_navigation_and_permission_matrix(self):
        self.client.force_login(self.user)
        response=self.client.get('/reports/employee-card/');self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['form'].initial['starts_on'],date(timezone.localdate().year,1,1))
        self.assertEqual(response.context['form'].initial['employees'],[self.employee.pk])
        self.assertContains(self.client.get('/'),'href="/reports/employee-card/"')
        from .user_management import editable_permissions,MODULE_LABELS
        self.assertEqual(editable_permissions().filter(content_type__model='employeerecordcard').count(),2)
        self.assertEqual(MODULE_LABELS['employeerecordcard'],'Καρτέλα Εργαζομένου')

    def test_long_card_repeats_headers_without_duplicating_amounts(self):
        from .employee_card_pdf import render_employee_cards
        source=self.generate().source
        card=source['cards'][0];original=card['rows'][0]
        card['rows']=[deepcopy(original) for _ in range(70)]
        card['totals']={key:str(Decimal(value)*70) for key,value in card['totals'].items()}
        reader=PdfReader(BytesIO(render_employee_cards(source)))
        self.assertGreater(len(reader.pages),1)
        text=''.join(page.extract_text() for page in reader.pages)
        self.assertEqual(text.count('150,00'),70)
        self.assertEqual(text.count('ΣΥΝΟΛΑ'),1)
        for page in reader.pages:
            page_text=page.extract_text()
            self.assertEqual(page_text.count('Καρτέλα Εργαζομένου'),1)
            self.assertEqual(page_text.count('Subordinate'),1)
            self.assertEqual(page_text.count('ΑΝΑΧΩΡΗΣΗ'),1)
