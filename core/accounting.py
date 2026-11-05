from decimal import Decimal, ROUND_CEILING, ROUND_HALF_EVEN
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, render, redirect
from .models import AccountingAdjustment
from .number_formats import GreekNumberFormMixin

AMOUNTS={'daily_domestic':'Ημερήσια αποζημίωση Ελλάδας (€)','daily_abroad':'Ημερήσια αποζημίωση εξωτερικού (€)',
    'mileage':'Χιλιομετρική αποζημίωση (€)','tickets':'Εισιτήρια (€)','other':'Πρόσβαση αεροδρομίου / λοιπά (€)',
    'claimed_accommodation':'Δηλωμένο κόστος διαμονής (€)','allowed_accommodation':'Αποζημίωση διαμονής (€)',
    'total':'Συνολικό κόστος (€)','document_budget':'Προϋπολογισμός απόφασης (€)'}
NUMBERS={'days':'Ημέρες υπολογισμού','distance_km':'Απόσταση υπολογισμού (χλμ.)','overnights':'Διανυκτερεύσεις υπολογισμού'}

ADJUSTMENT_PERMISSIONS=tuple('core.'+action+'_accountingadjustment' for action in ('view','add','change'))

def can_adjust_calculations(user):
    return user.is_authenticated and user.is_active and user.has_perms(ADJUSTMENT_PERMISSIONS)

def require_access(user):
    if not can_adjust_calculations(user): raise PermissionDenied

class AdjustmentForm(GreekNumberFormMixin,forms.Form):
    is_active=forms.BooleanField(label='Εφαρμογή χειροκίνητων προσαρμογών',required=False,initial=True)
    reason=forms.CharField(label='Αιτιολογία προσαρμογών',widget=forms.Textarea(attrs={'rows':3}),max_length=2000)

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from .number_formats import GreekNumberInput
        for name,label in {**AMOUNTS,**NUMBERS}.items():
            self.fields[name]=forms.DecimalField(label=label,min_value=0,max_digits=14,decimal_places=2,required=False,widget=GreekNumberInput()) if name not in ('days','overnights') else forms.IntegerField(label=label,min_value=0,max_value=366,required=False)

def adjustment_state(travel):
    row=AccountingAdjustment.objects.filter(travel=travel).first()
    return {'id':row.pk,'is_active':row.is_active,'values':row.values,'updated_at':str(row.updated_at)} if row else None

def apply_adjustment(travel,actor,details,amounts,parameters):
    row=AccountingAdjustment.objects.filter(travel=travel,is_active=True).select_related('updated_by').first()
    if not row:return amounts
    automatic={name:str(value) for name,value in amounts.items()}
    values=row.values
    for name in AMOUNTS:
        if name in values:amounts[name]=Decimal(str(values[name]))
    if 'total' not in values:
        amounts['total']=sum(amounts[name] for name in ('daily_domestic','daily_abroad','mileage','tickets','other','allowed_accommodation'))
    if 'document_budget' not in values:
        budget=amounts['total']*(1+(parameters.percentageofbudgetinc or Decimal(0))/100)
        budget=budget.quantize(Decimal('1'),rounding=ROUND_CEILING) if parameters.roundtotalbudget else budget.quantize(Decimal('.01'),rounding=ROUND_HALF_EVEN)
        amounts['document_budget']=max(budget,parameters.budgetdownlimit or Decimal(0))
    automatic.update(days=details['days'],distance_km=str(travel.route.distance_km),overnights=len(details['nights']))
    if 'days' in values:details['days']=int(values['days'])
    details['display_distance_km']=values.get('distance_km',str(travel.route.distance_km))
    details['display_overnights']=int(values.get('overnights',len(details['nights'])))
    details['accounting']={'id':row.pk,'values':values,'automatic':automatic,'reason':row.reason,'updated_by_id':row.updated_by_id,'updated_at':str(row.updated_at)}
    return amounts

@login_required
def accounting_home(request):
    require_access(request.user)
    from .views import home
    return home(request)

@login_required
def accounting_create(request):
    require_access(request.user)
    from .access import can_action
    from .views import travel_editor
    if not can_action(request.user,'add'):raise PermissionDenied
    return travel_editor(request)

@login_required
def accounting_edit(request,pk):
    require_access(request.user)
    from .views import visible_travels,can_edit_costs,travel_editor
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        editable=can_edit_costs(request.user,travel)
        if request.method=='POST' and not editable:raise PermissionDenied
        return travel_editor(request,travel,read_only=not editable)

@login_required
def accounting_adjustment(request,pk):
    require_access(request.user)
    from .views import visible_travels,can_edit_costs
    from .calculation import calculate_estimate
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        row=AccountingAdjustment.objects.filter(travel=travel).first()
        if not request.user.has_perm('core.'+('change' if row else 'add')+'_accountingadjustment') or not can_edit_costs(request.user,travel):raise PermissionDenied
        initial={**(row.values if row else {}),'is_active':row.is_active if row else True,'reason':row.reason if row else ''}
        form=AdjustmentForm(request.POST if request.method=='POST' else None,initial=initial)
        snapshot=travel.calculations.filter(stage='estimate').order_by('-revision').first()
        if request.method=='POST' and form.is_valid():
            values={name:str(form.cleaned_data[name]) for name in {**AMOUNTS,**NUMBERS} if form.cleaned_data.get(name) is not None}
            if 'days' in values and travel.departure_at.year!=travel.return_at.year:
                form.add_error('days','Σε μετακίνηση μεταξύ δύο ετών διατηρήστε τον αυτόματο αριθμό ημερών.')
            else:
                try:
                    with transaction.atomic():
                        row=row or AccountingAdjustment(travel=travel)
                        row.values=values;row.reason=form.cleaned_data['reason'];row.is_active=form.cleaned_data['is_active'];row.updated_by=request.user
                        row.full_clean();row.save()
                        calculate_estimate(travel.pk,request.user)
                except ValidationError as error:form.add_error(None,error.messages)
                else:return redirect('core:travel_detail',pk=pk)
        baseline=snapshot.inputs.get('accounting',{}).get('automatic',{}) if snapshot else {}
        rows=[]
        for name,label in {**AMOUNTS,**NUMBERS}.items():
            value=baseline.get(name,getattr(snapshot,name,None) if snapshot else None)
            if value is None and snapshot:
                value=snapshot.inputs.get('days') if name=='days' else len(snapshot.inputs['nights']) if name=='overnights' else snapshot.inputs['source']['route'][0]['distance_km']
            rows.append({'field':form[name],'automatic':value})
    return render(request,'core/accounting_adjustment.html',{'travel':travel,'form':form,'rows':rows})
