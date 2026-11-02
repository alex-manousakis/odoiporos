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
    return render(request,'core/travel_detail.html',{'travel':travel})
