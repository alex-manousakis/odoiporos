from datetime import date
from decimal import Decimal,ROUND_HALF_UP
from io import BytesIO
import hashlib,json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404,redirect,render
from django.urls import reverse
from django.utils import timezone
from .models import Employee,Department,SettlementPeriod,Signatory,ApplicationParameters,DetailedStatement,SettlementItem
from .access import employee_scope,can_action
from .date_widgets import GreekDateInput
from .views import visible_travels
from .calculation import input_state,signature
from .detailed_statement_pdf import render_statement

ZERO=Decimal('0')
NUMERIC_COLUMNS=['near_days','domestic_days','domestic_factor','abroad_days','abroad_factor','tickets','distance','mileage','hotel','other']

def require_statement_access(user):
    if not user.has_perm('core.print_travel') or not can_action(user,'view'):raise PermissionDenied

class StatementForm(forms.Form):
    department=forms.ModelChoiceField(label='Μονάδα',queryset=Department.objects.none(),required=False,empty_label='Όλες οι επιτρεπόμενες μονάδες')
    employee=forms.ModelChoiceField(label='Εργαζόμενος',queryset=Employee.objects.none())
    period=forms.ModelChoiceField(label='Περίοδος',queryset=SettlementPeriod.objects.order_by('-starts_on','-pk'))
    signatory=forms.ModelChoiceField(label='Υπογραφή',queryset=Signatory.objects.filter(is_active=True).order_by('-is_head','name'))
    print_date=forms.DateField(label='Ημερομηνία εκτύπωσης',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])

    def __init__(self,*args,user,department_id='',**kwargs):
        super().__init__(*args,**kwargs)
        allowed=employee_scope(user).select_related('department')
        self.fields['department'].queryset=Department.objects.filter(employee__in=allowed).distinct().order_by('name')
        if department_id:
            allowed=allowed.filter(department_id=department_id) if str(department_id).isdigit() and len(str(department_id))<19 else allowed.none()
        self.fields['employee'].queryset=allowed.order_by('display_name','pk')
        self.fields['period'].label_from_instance=lambda period:period.name+' ('+period.starts_on.strftime('%d/%m/%Y')+' – '+period.ends_on.strftime('%d/%m/%Y')+')'

def daily_factor(snapshot,amount,abroad):
    if not amount:return ZERO
    source=snapshot.inputs.get('source',{})
    category=source.get('travel',{}).get('applied_category_id')
    start=snapshot.inputs.get('allowance_from','');end=snapshot.inputs.get('allowance_to','')
    rates=[r for r in source.get('daily_rates',[]) if str(r['category_id'])==str(category) and bool(r['is_abroad'])==abroad and r['valid_from']<=start and r['valid_to']>=end]
    if len(rates)!=1 or Decimal(str(rates[0]['band_1']))<=0:
        raise ValidationError('Δεν τεκμηριώνεται ο συντελεστής ημερήσιας αποζημίωσης για τη μετακίνηση '+str(snapshot.travel_id)+'. Ελέγξτε τον υπολογισμό της.')
    return amount/Decimal(str(rates[0]['band_1']))

def report_row(travel,snapshot):
    inputs=snapshot.inputs;source=inputs.get('source',{})
    route=(source.get('route') or [{}])[0]
    distance=Decimal(str(inputs.get('display_distance_km',route.get('distance_km',travel.route.distance_km))))
    limit=source.get('parameters',{}).get('homedistancelimit')
    if limit is None:raise ValidationError('Λείπει το όριο εντός έδρας στον υπολογισμό της μετακίνησης '+str(travel.pk)+'.')
    days=Decimal(str(inputs['days']));abroad=bool(route.get('is_abroad',travel.route.is_abroad))
    near=not abroad and Decimal(str(route.get('distance_km',travel.route.distance_km)))<=Decimal(str(limit))
    transport=inputs.get('transport',{}).get('name') or ', '.join(dict.fromkeys(str(e.transport) for e in travel.expenses.all() if e.transport and not e.is_cancelled))
    mileage_enabled=inputs.get('transport',{}).get('has_mileage_cost') or any(e.get('kind')=='mileage' for e in inputs.get('expenses',[]))
    flags=source.get('transport_flags') or {}
    mileage_enabled=mileage_enabled or flags.get('mileage') or snapshot.mileage>0
    row={'travel_id':travel.pk,'calculation_id':snapshot.pk,'stage':snapshot.stage,'revision':snapshot.revision,
        'from':travel.departure_at.strftime('%d/%m/%Y'),'to':travel.return_at.strftime('%d/%m/%Y'),
        'route':travel.route.short_description or travel.route.name,'transport':transport,'purpose':travel.purpose,
        'near_days':days if near else ZERO,'domestic_days':days if not near and not abroad else ZERO,'abroad_days':days if abroad else ZERO,
        'domestic_factor':daily_factor(snapshot,snapshot.daily_domestic,False),'abroad_factor':daily_factor(snapshot,snapshot.daily_abroad,True),
        'daily_domestic':snapshot.daily_domestic,'daily_abroad':snapshot.daily_abroad,
        'tickets':snapshot.tickets,'distance':distance if mileage_enabled else ZERO,'mileage':snapshot.mileage,'hotel':snapshot.allowed_accommodation,'other':snapshot.other,
        'total':snapshot.total}
    return row

@transaction.atomic
def generate_statement(user,employee,period,signatory,print_date):
    require_statement_access(user)
    employee=get_object_or_404(employee_scope(user).select_for_update().select_related('department','speciality','position'),pk=employee.pk)
    period=SettlementPeriod.objects.select_for_update().get(pk=period.pk)
    signatory=Signatory.objects.select_for_update().get(pk=signatory.pk)
    params=ApplicationParameters.objects.filter(pk=1).first()
    if not params:raise ValidationError('Λείπουν οι παράμετροι εφαρμογής.')
    if not signatory.is_active:raise ValidationError('Επιλέξτε ενεργό υπογράφοντα.')
    if not employee.tax_number or not employee.iban:raise ValidationError('Συμπληρώστε ΑΦΜ και IBAN στον εργαζόμενο πριν από την εκτύπωση.')
    trips=list(visible_travels(user).filter(employee=employee,departure_at__gte=period.starts_on,departure_at__lte=period.ends_on).select_for_update().prefetch_related('expenses__transport','calculations').order_by('departure_at','pk'))
    if not trips:raise ValidationError('Δεν υπάρχουν μετακινήσεις του εργαζομένου με αναχώρηση μέσα στην περίοδο.')
    rows=[]
    for travel in trips:
        settled=SettlementItem.objects.filter(calculation__travel=travel).select_related('calculation').first()
        if settled and settled.period_id!=period.pk:raise ValidationError('Η μετακίνηση '+str(travel.pk)+' ανήκει σε άλλη περίοδο εκκαθάρισης.')
        candidates=list(travel.calculations.all())
        actual=[s for s in candidates if s.stage=='actual' and s.frozen_at]
        estimates=[s for s in candidates if s.stage=='estimate']
        chosen=settled.calculation if settled else max(actual,key=lambda s:s.revision) if actual else max(estimates,key=lambda s:s.revision) if estimates else None
        if not chosen:raise ValidationError('Η μετακίνηση '+str(travel.pk)+' δεν έχει υπολογισμό. Αποθηκεύστε την πρώτα.')
        if chosen.stage=='estimate' and (chosen.algorithm_version!='estimate-3' or chosen.inputs.get('signature')!=signature(input_state(travel))):
            raise ValidationError('Η εκτίμηση της μετακίνησης '+str(travel.pk)+' δεν είναι ενημερωμένη. Αποθηκεύστε την ξανά.')
        rows.append(report_row(travel,chosen))
    totals={key:sum((row[key] for row in rows),ZERO) for key in NUMERIC_COLUMNS+['daily_domestic','daily_abroad','total']}
    daily=totals['daily_domestic']+totals['daily_abroad']
    expenses=sum(totals[key] for key in ('tickets','mileage','hotel','other'))
    adjustment=totals['total']-daily-expenses
    deductions={}
    for field,label in [('mtpy','ΜΤΠΥ'),('geotee','ΓΕΩΤΕΕ')]:
        enabled=getattr(period,'has_'+field)
        employee_flag=getattr(employee,'has_'+field)
        rate=getattr(params,field)
        if enabled and employee_flag is None:raise ValidationError('Ορίστε την υπαγωγή του εργαζομένου σε κράτηση '+label+'.')
        if enabled and employee_flag and rate is None:raise ValidationError('Συμπληρώστε το ποσοστό '+label+' στις παραμέτρους.')
        effective=bool(enabled and employee_flag)
        amount=(daily*rate/100).quantize(Decimal('.01'),rounding=ROUND_HALF_UP) if effective else ZERO
        deductions[field]={'enabled':effective,'period_enabled':enabled,'employee_enabled':employee_flag,'percentage':rate or ZERO,'amount':amount}
    taxes=sum((x['amount'] for x in deductions.values()),ZERO)
    net=totals['total']-taxes
    if net<0:raise ValidationError('Οι κρατήσεις υπερβαίνουν το συνολικό ποσό. Ελέγξτε τις προσαρμογές και τα ποσοστά.')
    source={'employee':{'id':employee.pk,'name':employee.display_name,'speciality':str(employee.speciality or ''),'position':(employee.position.name_genitive or employee.position.name) if employee.position else '',
        'department':(employee.department.name_genitive or employee.department.name) if employee.department else '', 'tax_number':employee.tax_number,'iban':employee.iban},
        'period':{'id':period.pk,'name':period.name,'from':period.starts_on.strftime('%d/%m/%Y'),'to':period.ends_on.strftime('%d/%m/%Y'),'year':str(period.starts_on.year) if period.starts_on.year==period.ends_on.year else str(period.starts_on.year)+'-'+str(period.ends_on.year),'reference_number':period.reference_number},
        'header':params.document_header,'place':params.report_place,'service':params.approval_service_genitive,'signatory':{'id':signatory.pk,'name':signatory.name,'speciality':signatory.speciality,'heading':params.prosfonisiproistamenou},
        'print_date':print_date.strftime('%d/%m/%Y'),'rows':rows,'totals':totals,'daily':daily,'expenses':expenses,'adjustment':adjustment,'deductions':deductions,'taxes':taxes,'net':net,
        'provisional':any(row['stage']=='estimate' for row in rows),'selection_rule':'departure_within_period_inclusive','algorithm':'detailed-statement-1'}
    source=json.loads(json.dumps(source,default=str))
    content=render_statement(source)
    return DetailedStatement.objects.create(employee=employee,period=period,signatory=signatory,print_date=print_date,created_by=user,content=content,source=source,sha256=hashlib.sha256(content).hexdigest())

@login_required
def statement_form(request):
    require_statement_access(request.user)
    data=request.POST if request.method=='POST' else request.GET
    own=employee_scope(request.user).filter(user=request.user).first()
    period=SettlementPeriod.objects.filter(is_active=True,starts_on__lte=timezone.localdate()).order_by('-starts_on','-pk').first()
    head=Signatory.objects.filter(is_head=True,is_active=True).first()
    initial={'employee':own.pk if own else None,'period':period.pk if period else None,'signatory':head.pk if head else None,'print_date':timezone.localdate()}
    if request.method=='GET':
        for key in initial:
            if key in data:initial[key]=data[key]
        initial['department']=data.get('department','')
    form=StatementForm(data if request.method=='POST' else None,user=request.user,department_id=data.get('department',''),initial=initial)
    candidate=str(initial.get('employee') or '')
    if request.method=='GET' and candidate and (not candidate.isdigit() or len(candidate)>18 or not form.fields['employee'].queryset.filter(pk=candidate).exists()):form.initial['employee']=None
    if request.method=='POST' and form.is_valid():
        try:document=generate_statement(request.user,form.cleaned_data['employee'],form.cleaned_data['period'],form.cleaned_data['signatory'],form.cleaned_data['print_date'])
        except ValidationError as error:form.add_error(None,error.messages)
        else:
            url=reverse('core:detailed_statement_download',kwargs={'pk':document.pk})
            return redirect(url+('?download=1' if request.POST.get('export')=='download' else ''))
    return render(request,'core/detailed_statement.html',{'form':form})

@login_required
def statement_download(request,pk):
    require_statement_access(request.user)
    document=get_object_or_404(DetailedStatement.objects.filter(employee__in=employee_scope(request.user)),pk=pk)
    response=HttpResponse(bytes(document.content),content_type='application/pdf')
    disposition='attachment' if request.GET.get('download')=='1' else 'inline'
    response['Content-Disposition']=f'{disposition}; filename="analytiki-{document.employee_id}-{document.period_id}-{document.pk}.pdf"'
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    return response
