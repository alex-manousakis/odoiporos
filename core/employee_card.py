"""Employee travel cards; saved calculations only, always within the viewer's scope."""
from datetime import date
from decimal import Decimal
import hashlib,json
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied,ValidationError
from django.db import transaction
from django.http import Http404,HttpResponse
from django.shortcuts import render,redirect,get_object_or_404
from django.urls import reverse
from django.utils import timezone
from .models import Employee,EmployeeRecordCard
from .access import employee_scope,can_action
from .views import visible_travels
from .date_widgets import GreekDateInput
from .detailed_statement import statement_calculation,report_row
from .employee_card_pdf import render_employee_cards

CARD_PERMISSIONS=('core.view_employeerecordcard','core.print_employeerecordcard')
NUMBERS=('near_days','domestic_days','abroad_days','factor','daily','nights','hotel','transport','total')

def can_print_employee_card(user):
    return user.is_authenticated and user.is_active and can_action(user,'view') and user.has_perms(CARD_PERMISSIONS)

def require_card_access(user):
    if not can_print_employee_card(user):raise PermissionDenied

class EmployeeCardForm(forms.Form):
    starts_on=forms.DateField(label='Από ημερομηνία',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])
    ends_on=forms.DateField(label='Έως ημερομηνία',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])
    employees=forms.ModelMultipleChoiceField(label='Εργαζόμενοι',queryset=Employee.objects.none(),widget=forms.CheckboxSelectMultiple)

    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs)
        # Include inactive employees so historical cards remain available.
        self.fields['employees'].queryset=employee_scope(user).select_related('department').order_by('display_name','pk')
        self.fields['employees'].label_from_instance=lambda employee:employee.display_name+(' — '+employee.department.name if employee.department else '')

    def clean(self):
        data=super().clean()
        if data.get('starts_on') and data.get('ends_on') and data['ends_on']<data['starts_on']:
            self.add_error('ends_on','Η έως ημερομηνία πρέπει να είναι ίση ή μεταγενέστερη της από ημερομηνίας.')
        return data

def card_row(travel,snapshot):
    row=report_row(travel,snapshot)
    row.update(origin=travel.route.origin,destination=travel.route.destination,
        work_from=travel.work_starts_at.strftime('%d/%m/%Y'),work_to=travel.work_ends_at.strftime('%d/%m/%Y'),
        factor=row['domestic_factor']+row['abroad_factor'],daily=snapshot.daily_domestic+snapshot.daily_abroad,
        nights=Decimal(str(snapshot.inputs.get('display_overnights',len(snapshot.inputs.get('nights',[]))))),
        transport=snapshot.mileage+snapshot.tickets+snapshot.other)
    keys=('travel_id','calculation_id','stage','revision','from','to','origin','destination','work_from','work_to',*NUMBERS)
    return {key:row[key] for key in keys}

@transaction.atomic
def generate_card(user,employee_ids,starts_on,ends_on):
    require_card_access(user)
    if ends_on<starts_on:raise ValidationError('Ελέγξτε τις ημερομηνίες του διαστήματος.')
    ids=set(employee_ids)
    if not ids:raise ValidationError('Επιλέξτε τουλάχιστον έναν εργαζόμενο.')
    employees=list(employee_scope(user).select_for_update().filter(pk__in=ids).order_by('display_name','pk'))
    if len(employees)!=len(ids):raise PermissionDenied
    cards=[]
    for employee in employees:
        # Any trip overlapping the requested range; amounts are for the whole trip.
        travels=visible_travels(user).filter(employee=employee,departure_at__lte=ends_on,return_at__gte=starts_on).select_for_update().prefetch_related('calculations','expenses__transport').order_by('return_at','departure_at','pk')
        rows=[]
        for travel in travels:
            try:rows.append(card_row(travel,statement_calculation(travel)))
            except ValidationError as error:raise ValidationError(employee.display_name+': '+' '.join(error.messages))
        totals={key:sum((row[key] for row in rows),Decimal(0)) for key in NUMBERS}
        cards.append({'employee_id':employee.pk,'name':employee.display_name,'rows':rows,'totals':totals})
    source={'from':starts_on.strftime('%d/%m/%Y'),'to':ends_on.strftime('%d/%m/%Y'),'print_date':timezone.localdate().strftime('%d/%m/%Y'),
        'employee_ids':[e.pk for e in employees],'cards':cards,'selection_rule':'trip_overlaps_range_inclusive_full_amounts','algorithm':'employee-card-1',
        'provisional':any(row['stage']=='estimate' for card in cards for row in card['rows'])}
    source=json.loads(json.dumps(source,default=str))
    content=render_employee_cards(source)
    document=EmployeeRecordCard.objects.create(starts_on=starts_on,ends_on=ends_on,created_by=user,content=content,source=source,sha256=hashlib.sha256(content).hexdigest())
    document.employees.set(employees)
    return document

@login_required
def card_form(request):
    require_card_access(request.user)
    today=timezone.localdate()
    own=employee_scope(request.user).filter(user=request.user).first()
    form=EmployeeCardForm(request.POST if request.method=='POST' else None,user=request.user,
        initial={'starts_on':date(today.year,1,1),'ends_on':today,'employees':[own.pk] if own else []})
    if request.method=='POST' and form.is_valid():
        try:document=generate_card(request.user,form.cleaned_data['employees'].values_list('pk',flat=True),form.cleaned_data['starts_on'],form.cleaned_data['ends_on'])
        except ValidationError as error:form.add_error(None,error.messages)
        else:return redirect(reverse('core:employee_card_download',kwargs={'pk':document.pk})+('?download=1' if request.POST.get('export')=='download' else ''))
    return render(request,'core/employee_card.html',{'form':form})

@login_required
def card_download(request,pk):
    require_card_access(request.user)
    document=get_object_or_404(EmployeeRecordCard,pk=pk)
    ids=document.source['employee_ids']
    if employee_scope(request.user).filter(pk__in=ids).count()!=len(ids):raise Http404
    response=HttpResponse(bytes(document.content),content_type='application/pdf')
    disposition='attachment' if request.GET.get('download')=='1' else 'inline'
    response['Content-Disposition']=f'{disposition}; filename="employee-card-{document.pk}.pdf"'
    response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
    return response
