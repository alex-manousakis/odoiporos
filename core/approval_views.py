from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from .models import Signatory, ApplicationParameters, ApprovalDocument
from .views import visible_travels


class ApprovalForm(forms.Form):
    signatory=forms.ModelChoiceField(label='Υπογράφων',queryset=Signatory.objects.filter(is_active=True).order_by('-is_head','name'))



@login_required
def approval_create(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    params=ApplicationParameters.objects.filter(pk=1).first()
    heads=list(Signatory.objects.filter(is_head=True,is_active=True)[:2])
    form=ApprovalForm(request.POST if request.method=='POST' else None,initial={'signatory':heads[0].pk if len(heads)==1 else None})
    from .annual_days import annual_balance
    balance=None
    configuration_errors=[]
    try: balance=annual_balance(travel,params)
    except ValidationError as error: configuration_errors.extend(error.messages)
    if len(heads)!=1: configuration_errors.append('Ορίστε έναν ενεργό προεπιλεγμένο υπογράφοντα στις Υπογραφές.')
    if request.method=='POST' and form.is_valid() and not configuration_errors:
        from .approval_pdf import generate_approval
        try:
            document=generate_approval(travel.pk,request.user,form.cleaned_data['signatory'])
        except ValidationError as error:form.add_error(None,error)
        else:return redirect('core:approval_download',pk=document.pk)
    return render(request,'core/approval_form.html',{'form':form,'travel':travel,'balance':balance,'configuration_errors':configuration_errors,'signature_heading':params.prosfonisiproistamenou if params else ''})


@login_required
def approval_download(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    document=get_object_or_404(ApprovalDocument.objects.filter(travel__in=visible_travels(request.user)),pk=pk)
    response=HttpResponse(bytes(document.content),content_type='application/pdf')
    response['Content-Disposition']=f'attachment; filename="travel-approval-{document.travel_id}-{document.pk}.pdf"'
    response['X-Content-Type-Options']='nosniff'
    response['Cache-Control']='private, no-store'
    return response
