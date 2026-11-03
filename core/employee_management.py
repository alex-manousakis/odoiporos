from datetime import timedelta
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from .models import Employee, EmployeeCategory, EmployeeCategoryHistory, Department
from .access import employee_scope, policy


def employees_for(user):
    return employee_scope(user) if policy(user) and not user.is_superuser else Employee.objects.all()


class EmployeeForm(forms.ModelForm):
    new_category=forms.ModelChoiceField(label='Νέα κατηγορία (προαιρετική αλλαγή)',queryset=EmployeeCategory.objects.filter(is_active=True),required=False)
    category_from=forms.DateField(label='Ισχύει από',required=False,widget=forms.DateInput(attrs={'type':'date'},format='%Y-%m-%d'),input_formats=['%Y-%m-%d'])

    class Meta:
        model=Employee
        fields=['code','first_name','last_name','display_name','name_genitive','gender','department','speciality','position','id_number','tax_number','father_name','mother_name','birth_place','birth_date','phone','city','address','address_number','postal_code','fax','email','driving_license','car_brand','iban','car_plate','is_active','user']
        widgets={'birth_date':forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'})}
        labels={'code':'Κωδικός','first_name':'Όνομα','last_name':'Επώνυμο','display_name':'Ονοματεπώνυμο','name_genitive':'Ονοματεπώνυμο σε γενική','department':'Μονάδα','speciality':'Ειδικότητα','position':'Θέση','email':'Email','iban':'IBAN','car_plate':'Αριθμός κυκλοφορίας ΙΧ','is_active':'Ενεργός','user':'Λογαριασμός χρήστη'}

    def __init__(self,*args,actor,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['birth_date'].input_formats=['%Y-%m-%d']
        if not actor.is_superuser:
            # Linking another login to an employee also changes access to travel data.
            self.fields['user'].disabled=True
        else:
            self.fields['user'].queryset=get_user_model().objects.filter(Q(employee__isnull=True)|Q(pk=self.instance.user_id)).order_by('username')
        access=policy(actor)
        if access and not actor.is_superuser:
            if access.scope=='department':
                self.fields['department'].queryset=access.departments.all()
                self.fields['department'].required=True
            elif access.scope=='own':
                self.fields['department'].disabled=True

    def clean(self):
        data=super().clean()
        category=data.get('new_category');start=data.get('category_from')
        if bool(category)!=bool(start):
            raise forms.ValidationError('Συμπληρώστε κατηγορία και ημερομηνία έναρξης μαζί.')
        if start and self.instance.pk:
            history=self.instance.category_history.order_by('-valid_from').first()
            if history and start<=history.valid_from:
                self.add_error('category_from','Η νέα κατηγορία πρέπει να αρχίζει μετά την τελευταία εγγραφή ιστορικού.')
            if history and history.category_id==category.pk:
                self.add_error('new_category','Η κατηγορία είναι ήδη η τελευταία καταχωρισμένη.')
        return data


@login_required
def employee_list(request):
    if not request.user.has_perm('core.view_employee'): raise PermissionDenied
    qs=employees_for(request.user).select_related('department','user').order_by('display_name')
    query=request.GET.get('q','').strip()
    if query:qs=qs.filter(Q(display_name__icontains=query)|Q(code__icontains=query)|Q(email__icontains=query))
    department=request.GET.get('department','')
    if department.isdigit():qs=qs.filter(department_id=int(department))
    state=request.GET.get('state','')
    if state in ('active','inactive'):qs=qs.filter(is_active=state=='active')
    departments=Department.objects.filter(employee__in=employees_for(request.user)).distinct().order_by('name')
    return render(request,'core/employees.html',{'page':Paginator(qs,30).get_page(request.GET.get('page')),'q':query,'departments':departments,'department':department,'state':state})


@login_required
def employee_edit(request,pk=None):
    if not request.user.has_perm('core.change_employee' if pk else 'core.add_employee'):raise PermissionDenied
    access=policy(request.user)
    if not pk and access and access.scope=='own' and not request.user.is_superuser:raise PermissionDenied
    with transaction.atomic():
        employee=get_object_or_404(employees_for(request.user).select_for_update(),pk=pk) if pk else Employee()
        form=EmployeeForm(request.POST if request.method=='POST' else None,instance=employee,actor=request.user)
        if request.method=='POST' and form.is_valid():
            employee=form.save()
            category=form.cleaned_data['new_category'];start=form.cleaned_data['category_from']
            if category:
                previous=employee.category_history.order_by('-valid_from').first()
                if previous and (previous.valid_to is None or previous.valid_to>=start):
                    previous.valid_to=start-timedelta(days=1)
                    previous.full_clean();previous.save(update_fields=['valid_to'])
                entry=EmployeeCategoryHistory(employee=employee,category=category,valid_from=start)
                entry.full_clean();entry.save()
            return redirect('core:employees')
        history=employee.category_history.select_related('category').order_by('-valid_from') if employee.pk else []
    return render(request,'core/employee_form.html',{'form':form,'employee':employee,'history':history})
