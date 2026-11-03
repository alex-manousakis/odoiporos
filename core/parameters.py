from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from .models import ApplicationParameters


class ParametersForm(forms.ModelForm):
    class Meta:
        model=ApplicationParameters
        exclude=['id']

    def clean_travelnumdigits(self):
        value=self.cleaned_data['travelnumdigits']
        if value is not None and not 1<=value<=20:
            raise forms.ValidationError('Επιλέξτε από 1 έως 20 ψηφία.')
        return value


@login_required
def parameters_edit(request):
    change=request.user.has_perm('core.change_applicationparameters')
    if not change and not request.user.has_perm('core.view_applicationparameters'):
        raise PermissionDenied
    if request.method=='POST' and not change:
        raise PermissionDenied
    with transaction.atomic():
        instance=ApplicationParameters.objects.select_for_update().filter(pk=1).first() or ApplicationParameters(pk=1)
        form=ParametersForm(request.POST if request.method=='POST' else None,instance=instance)
        if not change:
            for field in form.fields.values(): field.disabled=True
        if request.method=='POST' and form.is_valid():
            form.save()
            return redirect('core:parameters')
    return render(request,'core/parameters.html',{'form':form,'can_change':change})
