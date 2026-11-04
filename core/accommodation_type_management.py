from django import forms
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .models import AccommodationType


class AccommodationTypeForm(forms.ModelForm):
    class Meta:
        model=AccommodationType
        fields=['code','name','has_cost','requires_declaration','is_active']
        labels={'code':'Κωδικός','name':'Περιγραφή','has_cost':'Έχει κόστος διαμονής','requires_declaration':'Απαιτεί υπεύθυνη δήλωση','is_active':'Ενεργός'}

    def clean_code(self):
        value=self.cleaned_data['code'].strip()
        if AccommodationType.objects.filter(code__iexact=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('Υπάρχει ήδη τύπος διαμονής με αυτόν τον κωδικό.')
        return value


@login_required
@permission_required('core.view_accommodationtype',raise_exception=True)
def accommodation_list(request):
    code=request.GET.get('code','').strip();name=request.GET.get('name','').strip();state=request.GET.get('state','')
    modes=AccommodationType.objects.order_by('code','pk')
    if code:modes=modes.filter(code__icontains=code)
    if name:modes=modes.filter(name__icontains=name)
    if state in ('active','inactive'):modes=modes.filter(is_active=state=='active')
    page=Paginator(modes,30).get_page(request.GET.get('page'))
    query=request.GET.copy();query.pop('page',None)
    return render(request,'core/accommodation_types.html',{'page':page,'code':code,'name':name,'state':state,'filter_query':query.urlencode()})


@login_required
def accommodation_edit(request,pk=None):
    if not request.user.has_perm('core.change_accommodationtype' if pk else 'core.add_accommodationtype'):
        raise PermissionDenied
    with transaction.atomic():
        if request.method=='POST':list(AccommodationType.objects.select_for_update().order_by('pk').values_list('pk',flat=True))
        mode=get_object_or_404(AccommodationType,pk=pk) if pk else AccommodationType()
        form=AccommodationTypeForm(request.POST if request.method=='POST' else None,instance=mode)
        if request.method=='POST' and form.is_valid():
            form.save()
            return redirect('core:accommodation_types')
    return render(request,'core/accommodation_type_form.html',{'form':form,'mode':mode})
