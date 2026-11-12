from decimal import Decimal
import json,hashlib
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.http import HttpResponse,Http404
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .models import SummaryStatement,SettlementPeriod,Signatory,ApplicationParameters
from .report_branding import default_report_signatory
from .date_widgets import GreekDateInput
from .access import employee_scope,policy
from .views import visible_travels
from .detailed_statement import require_statement_access,build_statement_source
from .summary_statement_pdf import render_summary

KEYS=('expenses','daily','adjustment','gross','mtpy','geotee','taxes','net')

SUMMARY_PERMISSIONS=('core.view_summarystatement','core.print_summarystatement')

def can_print_summary(user):
    return user.is_authenticated and user.is_active and user.has_perms(SUMMARY_PERMISSIONS)

def require_summary_access(user):
    if not can_print_summary(user):raise PermissionDenied
    require_statement_access(user)

class SummaryForm(forms.Form):
    period=forms.ModelChoiceField(label='Περίοδος',queryset=SettlementPeriod.objects.order_by('-starts_on','-pk'))
    signatory=forms.ModelChoiceField(label='Υπογραφή',queryset=Signatory.objects.filter(is_active=True).order_by('-is_head','name'))
    print_date=forms.DateField(label='Ημερομηνία εκτύπωσης',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['period'].label_from_instance=lambda row:row.name+' ('+row.starts_on.strftime('%d/%m/%Y')+' – '+row.ends_on.strftime('%d/%m/%Y')+')'

def add_totals(rows):
    return {key:sum((Decimal(str(row[key])) for row in rows),Decimal(0)) for key in KEYS}

def scope_label(user):
    access=policy(user)
    if user.is_superuser or (access and access.scope=='all'):return 'Όλες οι μονάδες'
    if access and access.scope=='department':return 'Μονάδες: '+', '.join(access.departments.order_by('name').values_list('name',flat=True))
    if access:return 'Ίδιες μετακινήσεις'
    return 'Εργαζόμενοι εντός του ισχύοντος πεδίου πρόσβασης'

@transaction.atomic
def generate_summary(user,period,signatory,print_date):
    require_summary_access(user)
    period=SettlementPeriod.objects.select_for_update().get(pk=period.pk)
    signatory=Signatory.objects.select_for_update().get(pk=signatory.pk)
    if not signatory.is_active:raise ValidationError('Επιλέξτε ενεργό υπογράφοντα.')
    params=ApplicationParameters.objects.filter(pk=1).first()
    if not params:raise ValidationError('Λείπουν οι παράμετροι εφαρμογής.')
    employees=employee_scope(user).filter(travels__in=visible_travels(user).filter(departure_at__gte=period.starts_on,departure_at__lte=period.ends_on)).distinct().order_by('display_name','pk')
    records=[]
    for employee in employees:
        try:item=build_statement_source(user,employee,period,signatory,print_date,require_payment_details=False)
        except ValidationError as error:raise ValidationError(employee.display_name+': '+' '.join(error.messages))
        row={'employee_id':employee.pk,'name':employee.display_name,
            'expenses':item['expenses'],'daily':item['daily'],'adjustment':item['adjustment'],'gross':item['totals']['total'],
            'mtpy':item['deductions']['mtpy']['amount'],'geotee':item['deductions']['geotee']['amount'],'taxes':item['taxes'],'net':item['net'],
            'mtpy_enabled':item['deductions']['mtpy']['enabled'],'geotee_enabled':item['deductions']['geotee']['enabled'],
            'deduction_details':item['deductions'],'provisional':item['provisional'],
            'calculations':[{key:line[key] for key in ('travel_id','calculation_id','stage','revision')} for line in item['rows']]}
        if any(Decimal(str(row[key]))!=0 for key in ('expenses','daily','adjustment','gross')):records.append(row)
    if not records:raise ValidationError('Δεν υπάρχουν μετακινήσεις με ποσά για την περίοδο εντός του πεδίου πρόσβασής σας.')
    without=[row for row in records if not row['mtpy_enabled']]
    with_mtpy=[row for row in records if row['mtpy_enabled']]
    for index,row in enumerate(without+with_mtpy,1):row['number']=index
    geotee=[row for row in records if row['geotee_enabled']]
    totals=add_totals(records)
    source={'period':{'id':period.pk,'name':period.name,'from':period.starts_on.strftime('%d/%m/%Y'),'to':period.ends_on.strftime('%d/%m/%Y'),
            'reference_number':period.reference_number or period.code,'has_mtpy':period.has_mtpy,'has_geotee':period.has_geotee},
        'header':params.document_header,'place':params.report_place,'print_date':print_date.strftime('%d/%m/%Y'),
        'scope':scope_label(user),'employee_ids':[r['employee_id'] for r in records],
        'signatory':{'id':signatory.pk,'name':signatory.name,'speciality':signatory.speciality,'heading':params.prosfonisiproistamenou},
        'rapporteur':params.ekkatharistis,'mtpy_rate':params.mtpy,'geotee_rate':params.geotee,
        'employees':records,'groups':[{'key':'A','employees':without,'totals':add_totals(without)},{'key':'B','employees':with_mtpy,'totals':add_totals(with_mtpy)}],
        'totals':totals,'geotee_employees':geotee,'geotee_totals':add_totals(geotee),
        'provisional':any(r['provisional'] for r in records),'selection_rule':'departure_within_period_inclusive','algorithm':'summary-statement-1'}
    source=json.loads(json.dumps(source,default=str))
    content=render_summary(source)
    return SummaryStatement.objects.create(period=period,signatory=signatory,print_date=print_date,created_by=user,
        content=content,source=source,sha256=hashlib.sha256(content).hexdigest())

@login_required
def summary_form(request):
    require_summary_access(request.user)
    period=SettlementPeriod.objects.filter(is_active=True,starts_on__lte=timezone.localdate()).order_by('-starts_on','-pk').first()
    head=default_report_signatory()
    form=SummaryForm(request.POST if request.method=='POST' else None,initial={'period':period.pk if period else None,'signatory':head.pk if head else None,'print_date':timezone.localdate()})
    if request.method=='POST' and form.is_valid():
        try:document=generate_summary(request.user,form.cleaned_data['period'],form.cleaned_data['signatory'],form.cleaned_data['print_date'])
        except ValidationError as error:form.add_error(None,error.messages)
        else:
            url=reverse('core:summary_statement_download',kwargs={'pk':document.pk})
            return redirect(url+('?download=1' if request.POST.get('export')=='download' else ''))
    return render(request,'core/summary_statement.html',{'form':form,'scope_label':scope_label(request.user)})

@login_required
def summary_download(request,pk):
    require_summary_access(request.user)
    document=get_object_or_404(SummaryStatement,pk=pk)
    identifiers=document.source['employee_ids']
    if not request.user.is_superuser and employee_scope(request.user).filter(pk__in=identifiers).count()!=len(identifiers):raise Http404
    response=HttpResponse(bytes(document.content),content_type='application/pdf')
    mode='attachment' if request.GET.get('download')=='1' else 'inline'
    response['Content-Disposition']=f'{mode}; filename="synoptiki-{document.period_id}-{document.pk}.pdf"'
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    return response
