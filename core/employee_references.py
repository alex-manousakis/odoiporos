from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from .models import Position, EmployeeCategory, Speciality, Department, Signatory, TravelReason


REFERENCES={
    'departments':(Department,'Μονάδες'),
    'signatories':(Signatory,'Υπογραφές'),
    'travel_reasons':(TravelReason,'Λόγοι μετακίνησης'),
    'positions':(Position,'Θέσεις'),
    'employee_categories':(EmployeeCategory,'Κατηγορίες εργαζομένων'),
    'specialities':(Speciality,'Ειδικότητες'),
}


def definition(kind):
    if kind not in REFERENCES:raise Http404
    return REFERENCES[kind]


def reference_form(model):
    fields=['name']+(['name_genitive'] if model in (Position,Department) else [])+(['responsible','sort_order'] if model is Department else [])+(['speciality'] if model is Signatory else [])+['is_active']
    return forms.modelform_factory(model,fields=fields,labels={'name':'Περιγραφή','name_genitive':'Περιγραφή σε γενική (για τα έγγραφα)','is_active':'Ενεργή εγγραφή'})


def context(kind):
    return {'title':definition(kind)[1],'list_name':'core:'+kind,'create_name':'core:'+kind+'_create','edit_name':'core:'+kind+'_edit'}


@login_required
def reference_list(request,kind):
    model,title=definition(kind)
    if not request.user.has_perm('core.view_'+model._meta.model_name):raise PermissionDenied
    query=request.GET.get('q','').strip();state=request.GET.get('state','')
    records=model.objects.order_by('sort_order','name','pk') if model is Department else model.objects.order_by('name','pk')
    if query:records=records.filter(name__icontains=query)
    if state in ('active','inactive'):records=records.filter(is_active=state=='active')
    page=Paginator(records,30).get_page(request.GET.get('page'))
    filters=request.GET.copy();filters.pop('page',None)
    return render(request,'core/employee_reference_list.html',{**context(kind),'page':page,'q':query,'state':state,'has_genitive':model in (Position,Department),'is_department':model is Department,'is_signatory':model is Signatory,'can_add':request.user.has_perm('core.add_'+model._meta.model_name),'can_change':request.user.has_perm('core.change_'+model._meta.model_name),'filter_query':filters.urlencode()})


@login_required
def reference_edit(request,kind,pk=None):
    model,title=definition(kind)
    if not request.user.has_perm('core.'+('change_' if pk else 'add_')+model._meta.model_name):raise PermissionDenied
    with transaction.atomic():
        record=get_object_or_404(model.objects.select_for_update(),pk=pk) if pk else model()
        form=reference_form(model)(request.POST if request.method=='POST' else None,instance=record)
        if request.method=='POST' and form.is_valid():
            form.save()
            return redirect('core:'+kind)
    return render(request,'core/employee_reference_form.html',{**context(kind),'form':form,'record':record})
