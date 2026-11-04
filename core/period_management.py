from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404,redirect,render
from .models import SettlementPeriod
from .date_widgets import GreekDateInput


class PeriodForm(forms.ModelForm):
    class Meta:
        model=SettlementPeriod
        fields=['code','name','starts_on','ends_on','reference_number','has_mtpy','has_geotee','is_active']
        labels={'name':'Περιγραφή','starts_on':'Έναρξη','ends_on':'Λήξη'}
        widgets={'starts_on':GreekDateInput(),'ends_on':GreekDateInput()}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        if self.instance.pk and self.instance.items.exists():
            self.fields['starts_on'].disabled=True;self.fields['ends_on'].disabled=True


@login_required
@permission_required('core.view_settlementperiod',raise_exception=True)
def period_list(request):
    query=request.GET.get('q','').strip()
    records=SettlementPeriod.objects.order_by('-starts_on','-pk')
    if query:records=records.filter(name__icontains=query)
    return render(request,'core/periods.html',{'page':Paginator(records,30).get_page(request.GET.get('page')),'q':query})


@login_required
def period_edit(request,pk=None):
    if not request.user.has_perm('core.change_settlementperiod' if pk else 'core.add_settlementperiod'):raise PermissionDenied
    with transaction.atomic():
        period=get_object_or_404(SettlementPeriod.objects.select_for_update(),pk=pk) if pk else SettlementPeriod()
        form=PeriodForm(request.POST if request.method=='POST' else None,instance=period)
        closed=bool(period.closed_at)
        if closed:
            if request.method=='POST':raise PermissionDenied
            for field in form.fields.values():field.disabled=True
        if request.method=='POST' and form.is_valid():
            form.save();return redirect('core:periods')
    return render(request,'core/period_form.html',{'form':form,'period':period,'closed':closed})
