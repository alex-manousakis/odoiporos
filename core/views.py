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
    form=TravelForm(request.POST or None,user=request.user)
    if request.method=='POST' and form.is_valid():
        status=TravelStatus.objects.filter(legacy_id=1).first()
        if status is None:
            form.add_error(None,'Δεν έχει εισαχθεί η αρχική κατάσταση μετακίνησης.')
        else:
            with transaction.atomic():
                travel=form.save(commit=False)
                travel.status=status
                travel.full_clean()
                travel.save()
            return redirect('core:travel_detail',pk=travel.pk)
    return render(request,'core/travel_form.html',{'form':form})


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
