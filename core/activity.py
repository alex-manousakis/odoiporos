from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django import forms
from .date_widgets import GreekDateInput
from .models import AuditEvent

class AuditFilter(forms.Form):
    actor=forms.CharField(label='Χρήστης',required=False)
    action=forms.ChoiceField(label='Ενέργεια',required=False,choices=[('','Όλες')]+[
        (key,label) for key,label in [('view','Ανάγνωση εγγραφής'),('access','Πρόσβαση σε σελίδα'),
        ('create','Δημιουργία'),('update','Μεταβολή'),('delete','Διαγραφή'),('download','Λήψη εγγράφου'),
        ('permissions','Δικαιώματα'),('login','Σύνδεση'),('logout','Αποσύνδεση'),('login_failed','Αποτυχία σύνδεσης'),('denied','Απόρριψη πρόσβασης'),('error','Σφάλμα')]])
    target_type=forms.CharField(label='Τύπος εγγραφής',required=False)
    target_id=forms.CharField(label='Κωδικός εγγραφής',required=False)
    since=forms.DateField(label='Από',required=False,widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])
    until=forms.DateField(label='Έως',required=False,widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])

@login_required
def activity(request):
    if not request.user.is_superuser: raise PermissionDenied
    form=AuditFilter(request.GET)
    qs=AuditEvent.objects.all()
    if form.is_valid():
        data=form.cleaned_data
        for field in ('action','target_type','target_id'):
            if data[field]: qs=qs.filter(**{field:data[field]})
        if data['actor']: qs=qs.filter(actor_identifier__icontains=data['actor'])
        if data['since']: qs=qs.filter(occurred_at__date__gte=data['since'])
        if data['until']: qs=qs.filter(occurred_at__date__lte=data['until'])
    else: qs=qs.none()
    page=Paginator(qs,50).get_page(request.GET.get('page'))
    labels=dict(form.fields['action'].choices)
    for event in page: event.action_label=labels.get(event.action,event.action)
    query=request.GET.copy();query.pop('page',None)
    return render(request,'core/activity.html',{'form':form,'page':page,'filter_query':query.urlencode()})
