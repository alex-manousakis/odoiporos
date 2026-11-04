from .number_formats import GreekNumberFormMixin
from .date_widgets import GreekDateInput
from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .models import DailyAllowanceRate, EmployeeCategory, ApplicationParameters


class DailyAllowanceRateForm(GreekNumberFormMixin, forms.ModelForm):
    class Meta:
        model=DailyAllowanceRate
        fields=['category','is_abroad','valid_from','valid_to','without_overnight','band_1','band_2','band_3']
        labels={'category':'Κατηγορία εργαζομένου','is_abroad':'Εξωτερικό','valid_from':'Ενεργό από','valid_to':'Ενεργό έως (συμπεριλαμβάνεται)','without_overnight':'Χωρίς διανυκτέρευση (€)','band_1':'Κατηγορία προορισμού 1 (€)','band_2':'Κατηγορία προορισμού 2 (€)','band_3':'Κατηγορία προορισμού 3 (€)'}
        widgets={name:GreekDateInput() for name in ['valid_from','valid_to']}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for name in ['valid_from','valid_to']:self.fields[name].input_formats=['%d/%m/%Y','%Y-%m-%d']
        parameters=ApplicationParameters.objects.filter(pk=1).first()
        if parameters:
            self.fields['band_1'].help_text='Εξωτερικό: λοιπές χώρες.'
            self.fields['band_2'].help_text=parameters.countriescomp2
            self.fields['band_3'].help_text=parameters.countriescomp3

    def clean(self):
        data=super().clean()
        start=data.get('valid_from');end=data.get('valid_to');category=data.get('category')
        if start and end and end<start:
            self.add_error('valid_to','Η λήξη δεν μπορεί να προηγείται της έναρξης.')
        elif start and end and category:
            overlaps=DailyAllowanceRate.objects.filter(category=category,is_abroad=data.get('is_abroad',False),valid_from__lte=end,valid_to__gte=start).exclude(pk=self.instance.pk)
            if overlaps.exists():
                self.add_error(None,'Υπάρχει επικάλυψη με άλλη τιμή για την ίδια κατηγορία και Ελλάδα/εξωτερικό. Οι ημερομηνίες έναρξης και λήξης περιλαμβάνονται στο διάστημα.')
        return data


@login_required
@permission_required('core.view_dailyallowancerate',raise_exception=True)
def rate_list(request):
    rates=DailyAllowanceRate.objects.select_related('category').order_by('category__name','is_abroad','-valid_from')
    category=request.GET.get('category','');kind=request.GET.get('kind','');period=request.GET.get('period','')
    if category.isdigit():rates=rates.filter(category_id=int(category))
    if kind in ('domestic','abroad'):rates=rates.filter(is_abroad=kind=='abroad')
    if period=='current':rates=rates.filter(valid_from__lte=timezone.localdate(),valid_to__gte=timezone.localdate())
    return render(request,'core/daily_allowances.html',{'page':Paginator(rates,30).get_page(request.GET.get('page')),'categories':EmployeeCategory.objects.order_by('name'),'category':category,'kind':kind,'period':period})


@login_required
def rate_edit(request,pk=None):
    if not request.user.has_perm('core.change_dailyallowancerate' if pk else 'core.add_dailyallowancerate'):
        raise PermissionDenied
    with transaction.atomic():
        # Serialize rate writers even when adding the first period; locking only matching
        # rate rows does not protect an empty date range against concurrent inserts.
        if request.method=='POST':list(EmployeeCategory.objects.select_for_update().order_by('pk'))
        rate=get_object_or_404(DailyAllowanceRate.objects.select_for_update(),pk=pk) if pk else DailyAllowanceRate()
        form=DailyAllowanceRateForm(request.POST if request.method=='POST' else None,instance=rate)
        if request.method=='POST' and form.is_valid():
            form.save()
            return redirect('core:daily_allowances')
    return render(request,'core/daily_allowance_form.html',{'form':form,'rate':rate})
