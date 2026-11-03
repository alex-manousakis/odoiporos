from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from .models import ReportDefinition, ReportText


class TextForm(forms.ModelForm):
    class Meta:
        model=ReportText
        fields=['sort_order','text']
        widgets={'text':forms.Textarea(attrs={'rows':4})}


TextRows=forms.inlineformset_factory(ReportDefinition,ReportText,form=TextForm,extra=2,can_delete=True,max_num=1000,validate_max=True)


@login_required
def report_texts(request):
    if not request.user.has_perm('core.view_reporttext'):raise PermissionDenied
    reports=ReportDefinition.objects.order_by('legacy_id','pk')
    selected=request.POST.get('report') if request.method=='POST' else request.GET.get('report')
    if selected and not selected.isdigit():
        from django.http import Http404
        raise Http404
    with transaction.atomic():
        report=get_object_or_404(ReportDefinition.objects.select_for_update(),pk=selected) if selected else reports.first()
        rows=TextRows(request.POST if request.method=='POST' else None,instance=report,prefix='texts') if report else None
        if rows:
            for row in rows:
                editing=bool(row.instance.pk)
                permitted=request.user.has_perm('core.change_reporttext' if editing else 'core.add_reporttext')
                for name,field in row.fields.items():
                    if name not in ('id','report','DELETE'):field.disabled=not permitted
                row.fields['DELETE'].disabled=not request.user.has_perm('core.delete_reporttext')
            if request.method=='POST' and rows.is_valid():
                # Disabled fields ignore forged values; explicitly reject unauthorized changes.
                if not any(request.user.has_perm('core.'+a+'_reporttext') for a in ('add','change','delete')):raise PermissionDenied
                rows.save()
                return redirect(reverse('core:report_texts')+'?report='+str(report.pk))
    return render(request,'core/report_texts.html',{'reports':reports,'report':report,'rows':rows})
