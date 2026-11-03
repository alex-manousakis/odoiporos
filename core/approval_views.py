from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Signatory, ApplicationParameters, ApprovalDocument
from .views import visible_travels


class ApprovalForm(forms.Form):
    signatory=forms.ModelChoiceField(label='Υπογράφων',queryset=Signatory.objects.filter(is_active=True))
    heading=forms.CharField(label='Προσφώνηση / ιδιότητα υπογραφής',max_length=255)
    prior_days=forms.IntegerField(label='Επιβεβαιωμένες ημέρες εκτός έδρας του έτους πριν από αυτή τη μετακίνηση',min_value=0,help_text='Δεν έχουν μεταφερθεί ιστορικές μετακινήσεις. Συμπληρώστε τον επιβεβαιωμένο αριθμό, χωρίς την παρούσα μετακίνηση.')


@login_required
def approval_create(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    params=ApplicationParameters.objects.filter(pk=1).first()
    form=ApprovalForm(request.POST if request.method=='POST' else None,initial={'heading':params.prosfonisiproistamenou if params else ''})
    if request.method=='POST' and form.is_valid():
        from .approval_pdf import generate_approval
        try:
            document=generate_approval(travel.pk,request.user,form.cleaned_data['signatory'],form.cleaned_data['heading'],form.cleaned_data['prior_days'])
        except ValidationError as error:form.add_error(None,error)
        else:return redirect('core:approval_download',pk=document.pk)
    return render(request,'core/approval_form.html',{'form':form,'travel':travel})


@login_required
def approval_download(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    document=get_object_or_404(ApprovalDocument.objects.filter(travel__in=visible_travels(request.user)),pk=pk)
    response=HttpResponse(bytes(document.content),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="travel-approval-{document.travel_id}-{document.pk}.pdf"'
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store'
    return response
