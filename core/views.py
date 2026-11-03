from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .forms import TravelForm
from .models import Employee, Travel, TravelStatus


def visible_travels(user):
    qs=Travel.objects.select_related('employee','route','status')
    return qs if user.has_perm('core.view_travel') else qs.filter(employee__user=user)


@login_required
def home(request):
    return render(request,'core/home.html',{'travels':visible_travels(request.user).order_by('-created_at')[:100]})


@login_required
def travel_create(request):
    if not request.user.has_perm('core.add_travel') and not Employee.objects.filter(user=request.user,is_active=True).exists():
        raise PermissionDenied
    return travel_editor(request)


@login_required
def travel_edit(request,pk):
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        if not can_edit_costs(request.user,travel):
            raise PermissionDenied
        return travel_editor(request,travel)


def travel_editor(request,travel=None):
    from .forms import ExpenseFormSet, StayFormSet
    from .models import Route, TravelAttachment, TransportMode, AccommodationType
    from uuid import uuid4
    from pathlib import Path
    post=request.POST if request.method=='POST' else None
    form=TravelForm(post,instance=travel,user=request.user)
    parent_valid=form.is_valid() if post is not None else False
    parent=form.instance
    expenses=ExpenseFormSet(post,instance=parent,prefix='expenses') if post is None or 'expenses-TOTAL_FORMS' in post else ExpenseFormSet(instance=parent,prefix='expenses')
    stays=StayFormSet(post,instance=parent,prefix='stays',form_kwargs={'travel':parent}) if post is None or 'stays-TOTAL_FORMS' in post else StayFormSet(instance=parent,prefix='stays',form_kwargs={'travel':parent})
    files=request.FILES.getlist('attachments')
    # Uploaded documents are downloaded through an authenticated view, never served inline.
    for upload in files:
        if upload.size > 10*1024*1024:
            form.add_error(None,'Κάθε συνημμένο πρέπει να είναι έως 10 MB.')
    if len(files)>10:
        form.add_error(None,'Επιτρέπονται έως 10 νέα συνημμένα ανά αποθήκευση.')
    if post is not None:
        children_valid=expenses.is_valid() if expenses.is_bound else True
        children_valid=(stays.is_valid() if stays.is_bound else True) and children_valid
        if parent_valid and children_valid and not form.errors:
            if parent.pk is None:
                parent.status=TravelStatus.objects.filter(legacy_id=1).first()
                if parent.status is None:
                    form.add_error(None,'Δεν υπάρχει αρχική κατάσταση μετακίνησης.')
            if not form.errors:
                written=[]
                try:
                    with transaction.atomic():
                        parent.full_clean();parent.save()
                        if expenses.is_bound: expenses.save()
                        if stays.is_bound: stays.save()
                        for upload in files:
                            attachment=TravelAttachment(travel=parent,original_name=Path(upload.name).name[:255])
                            attachment.file.save(uuid4().hex+Path(upload.name).suffix[:12],upload,save=False)
                            written.append(attachment.file)
                            attachment.save()
                except Exception:
                    for file in written: file.delete(save=False)
                    raise
                return redirect('core:travel_detail',pk=parent.pk)
    routes=[{'id':r.pk,'name':r.name,'stops':[{'id':n.pk,'city':n.city} for n in r.stops.all()]} for r in Route.objects.filter(is_active=True).prefetch_related('stops')]
    from django.conf import settings
    default_stay=AccommodationType.objects.filter(legacy_id=getattr(settings,"DEFAULT_ACCOMMODATION_LEGACY_ID",None),is_active=True).first()
    return render(request,'core/travel_form.html',{'form':form,'travel':parent,'expenses':expenses,'stays':stays,'accommodation_options':{'types':list(AccommodationType.objects.filter(is_active=True).values('id','has_cost')),'default':default_stay.pk if default_stay else None},'routes':routes,'transport_modes':list(TransportMode.objects.filter(is_active=True).values('id','has_mileage_cost','has_ticket_cost'))})


@login_required
def attachment_download(request,pk):
    from .models import TravelAttachment
    from django.http import FileResponse
    attachment=get_object_or_404(TravelAttachment.objects.filter(travel__in=visible_travels(request.user)),pk=pk)
    response=FileResponse(attachment.file.open('rb'),as_attachment=True,filename=attachment.original_name,content_type='application/octet-stream')
    response['X-Content-Type-Options']='nosniff'
    return response


@login_required
def travel_detail(request,pk):
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    return render(request,'core/travel_detail.html',{'travel':travel,'can_edit_costs':can_edit_costs(request.user,travel)})


def can_edit_costs(user,travel):
    allowed=user.has_perm('core.change_travel') or (travel.employee.user_id==user.pk and travel.employee.is_active)
    return allowed and travel.status.legacy_id==1 and travel.approved_at is None and not travel.calculations.filter(frozen_at__isnull=False).exists()


@login_required
def travel_costs(request,pk):
    from .forms import ExpenseFormSet, StayFormSet
    # Lock the parent before checking state and saving both child collections.
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        if not can_edit_costs(request.user,travel):
            raise PermissionDenied
        expenses=ExpenseFormSet(request.POST if request.method=='POST' else None,instance=travel,prefix='expenses')
        stays=StayFormSet(request.POST if request.method=='POST' else None,instance=travel,prefix='stays',form_kwargs={'travel':travel})
        if request.method=='POST':
            expenses_valid=expenses.is_valid()
            stays_valid=stays.is_valid()
            if expenses_valid and stays_valid:
                expenses.save();stays.save()
                return redirect('core:travel_detail',pk=travel.pk)
    return render(request,'core/travel_costs.html',{'travel':travel,'expenses':expenses,'stays':stays})
