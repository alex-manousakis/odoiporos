from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .forms import TravelForm
from .models import Employee, Travel, TravelStatus


def visible_travels(user):
    from .access import employee_scope, can_action
    qs=Travel.objects.select_related('employee','route','status')
    return qs.filter(employee__in=employee_scope(user)) if can_action(user,'view') else qs.none()


@login_required
def home(request,accounting=False):
    from .travel_search import TravelSearchForm
    from django.core.paginator import Paginator
    from django.db.models import OuterRef, Subquery, DecimalField
    from .models import CalculationSnapshot
    form=TravelSearchForm(request.GET,user=request.user)
    latest=CalculationSnapshot.objects.filter(travel_id=OuterRef('pk'),stage='estimate').order_by('-revision')
    qs=form.apply(visible_travels(request.user)).select_related('employee__department','reason').annotate(estimated_total=Subquery(latest.values('total')[:1],output_field=DecimalField(max_digits=14,decimal_places=2))).order_by('-departure_at','-pk')
    page=Paginator(qs,30).get_page(request.GET.get('page'))
    query=request.GET.copy();query.pop('page',None)
    return render(request,'core/home.html',{'list_title':'Μετακινήσεις (Λογιστήριο)' if accounting else 'Μετακινήσεις','new_travel_route':'core:accounting_create' if accounting else 'core:travel_create','detail_route':'core:accounting_edit' if accounting else 'core:travel_detail','home_route':'core:accounting_home' if accounting else 'core:home','travels':page,'page':page,'search_form':form,'filter_query':query.urlencode()})


@login_required
def travel_create(request):
    from .access import can_action
    if not can_action(request.user,'add'):
        raise PermissionDenied
    return travel_editor(request)


@login_required
def travel_edit(request,pk):
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        if not can_edit_costs(request.user,travel):
            raise PermissionDenied
        return travel_editor(request,travel)


def travel_editor(request,travel=None,read_only=False,accounting=False):
    from .forms import ExpenseFormSet, StayFormSet
    from .models import Route, TravelAttachment, TransportMode, AccommodationType, ApplicationParameters
    from uuid import uuid4
    from pathlib import Path
    post=request.POST if request.method=='POST' else None
    form=TravelForm(post,instance=travel,user=request.user)
    parent_valid=form.is_valid() if post is not None else False
    parent=form.instance
    if post is not None and post.get('automatic_nights')=='1' and parent_valid:
        if (parent.return_at-parent.departure_at).days>366:
            form.add_error(None,'Για διάστημα άνω των 366 ημερών χρειάζεται έλεγχος.')
        else:
            from .night_rows import synchronized_post
            post=synchronized_post(post,parent)
    expenses=ExpenseFormSet(post,instance=parent,prefix='expenses') if post is not None and 'expenses-TOTAL_FORMS' in post and not parent.transport_configured else ExpenseFormSet(instance=parent,prefix='expenses')
    stays=StayFormSet(post,instance=parent,prefix='stays',form_kwargs={'travel':parent}) if post is None or 'stays-TOTAL_FORMS' in post else StayFormSet(instance=parent,prefix='stays',form_kwargs={'travel':parent})
    if read_only:
        expenses.extra=0;stays.extra=0
        for name,field in form.fields.items():
            field.disabled=True
            if hasattr(field,'queryset'):
                field.queryset=field.queryset.model.objects.filter(pk=getattr(parent,name+'_id',None))
        for collection in (expenses,stays):
            for row in collection:
                for name,field in row.fields.items():
                    field.disabled=True
                    if hasattr(field,'queryset') and name not in ('id','travel'):
                        field.queryset=field.queryset.model.objects.filter(pk=getattr(row.instance,name+'_id',None))
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
                calculate_after_save(request,parent)
                return redirect('core:accounting_edit' if accounting else 'core:travel_detail',pk=parent.pk)
    from .calculation import input_state, signature
    calculation=parent.calculations.filter(stage='estimate').order_by('-revision').first() if parent.pk else None
    calculation_stale=bool(calculation and (calculation.algorithm_version!='estimate-3' or calculation.inputs.get('signature')!=signature(input_state(parent))))
    routes=[{'id':r.pk,'name':r.name,'distance_km':str(r.distance_km),'stops':[{'id':n.pk,'city':n.city} for n in r.stops.all()]} for r in Route.objects.filter(is_active=True).prefetch_related('stops')]
    from django.conf import settings
    parameters=ApplicationParameters.objects.filter(pk=1).first()
    default_stay=parameters.default_accommodation if parameters else AccommodationType.objects.filter(legacy_id=getattr(settings,"DEFAULT_ACCOMMODATION_LEGACY_ID",None),is_active=True).first()
    from .accounting import can_adjust_calculations
    return render(request,'core/travel_form.html',{'accounting_mode':accounting,'can_adjust':not read_only and can_adjust_calculations(request.user),'read_only':read_only,'calculation':calculation,'calculation_stale':calculation_stale,'form':form,'travel':parent,'expenses':expenses,'stays':stays,'accommodation_options':{'types':list(AccommodationType.objects.filter(is_active=True).values('id','has_cost')),'default':default_stay.pk if default_stay else None},'routes':routes,'transport_modes':list(TransportMode.objects.all().values('id','has_mileage_cost','has_ticket_cost'))})


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
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        editable=can_edit_costs(request.user,travel)
        if request.method=='POST' and not editable:
            raise PermissionDenied
        return travel_editor(request,travel,read_only=not editable)


def can_edit_costs(user,travel):
    from .access import can_action, employee_scope
    allowed=can_action(user,'change') and employee_scope(user).filter(pk=travel.employee_id).exists()
    from .models import AccountingAdjustment
    from .accounting import can_adjust_calculations
    if AccountingAdjustment.objects.filter(travel=travel,is_active=True).exists() and not can_adjust_calculations(user):
        return False
    return allowed and travel.status.legacy_id==1 and travel.approved_at is None and not travel.calculations.filter(frozen_at__isnull=False).exists()


@login_required
def travel_costs(request,pk):
    from .forms import ExpenseFormSet, StayFormSet
    # Lock the parent before checking state and saving both child collections.
    with transaction.atomic():
        travel=get_object_or_404(visible_travels(request.user).select_for_update(),pk=pk)
        if not can_edit_costs(request.user,travel):
            raise PermissionDenied
        if travel.transport_configured:
            if request.method=='POST':raise PermissionDenied
            return redirect('core:travel_detail',pk=travel.pk)
        expenses=ExpenseFormSet(request.POST if request.method=='POST' else None,instance=travel,prefix='expenses')
        stays=StayFormSet(request.POST if request.method=='POST' else None,instance=travel,prefix='stays',form_kwargs={'travel':travel})
        if request.method=='POST':
            expenses_valid=expenses.is_valid()
            stays_valid=stays.is_valid()
            if expenses_valid and stays_valid:
                expenses.save();stays.save()
                calculate_after_save(request,travel)
                return redirect('core:travel_detail',pk=travel.pk)
    return render(request,'core/travel_costs.html',{'travel':travel,'expenses':expenses,'stays':stays})


@login_required
def travel_calculate(request,pk):
    from django.views.decorators.http import require_POST
    from django.http import HttpResponseNotAllowed
    from django.core.exceptions import ValidationError
    from django.contrib import messages
    from .calculation import calculate_estimate
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    try:
        calculate_estimate(travel.pk,request.user)
        messages.success(request,'Ο υπολογισμός εκτίμησης αποθηκεύτηκε.')
    except ValidationError as error:
        messages.error(request,' '.join(error.messages))
    return redirect('core:travel_detail',pk=pk)


def calculate_after_save(request,travel):
    from django.contrib import messages
    from django.core.exceptions import ValidationError, PermissionDenied
    from .calculation import calculate_estimate
    try:
        calculate_estimate(travel.pk,request.user)
    except ValidationError as error:
        messages.warning(request,'Travel saved, but the estimate could not be updated: '+' '.join(error.messages))
    except PermissionDenied:
        messages.warning(request,'Travel saved. Your account does not have permission to calculate its estimate.')
    else:
        messages.success(request,'Travel saved and estimated cost calculated automatically.')
