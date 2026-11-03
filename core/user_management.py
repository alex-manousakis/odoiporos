from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Permission
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from .models import Employee, Department, UserAccess


MODULE_LABELS = {'travel': 'Διαχείριση μετακινήσεων', 'employee': 'Διαχείριση εργαζομένων', 'department': 'Διαχείριση μονάδων', 'route': 'Διαχείριση διαδρομών', 'routestop': 'Στάσεις διαδρομών', 'transportmode': 'Τρόποι μετακίνησης', 'accommodationtype': 'Τύποι διαμονής', 'employeecategory': 'Κατηγορίες εργαζομένων', 'employeecategoryhistory': 'Ιστορικό κατηγορίας εργαζομένου', 'speciality': 'Ειδικότητες', 'position': 'Θέσεις εργαζομένων', 'travelreason': 'Λόγοι μετακίνησης', 'travelstatus': 'Καταστάσεις μετακίνησης', 'dailyallowancerate': 'Ημερήσιες αποζημιώσεις', 'accommodationrate': 'Όρια κόστους διαμονής', 'mileagerate': 'Τιμές χιλιομετρικής αποζημίωσης', 'travelexpense': 'Δαπάνες μετακίνησης', 'overnightstay': 'Διανυκτερεύσεις', 'accommodationreceipt': 'Παραστατικά διαμονής', 'calculationsnapshot': 'Ιστορικό υπολογισμών', 'settlementperiod': 'Περίοδοι εκκαθάρισης', 'settlementitem': 'Εγγραφές εκκαθάρισης', 'travelattachment': 'Συνημμένα μετακίνησης'}

def editable_permissions():
    # Authentication and security administration remain superuser-only.
    return Permission.objects.filter(content_type__app_label='core').exclude(content_type__model='useraccess').select_related('content_type').order_by('content_type__model','codename')


class UserForm(forms.ModelForm):
    password=forms.CharField(label='Νέος κωδικός πρόσβασης',required=False,widget=forms.PasswordInput)
    employee=forms.ModelChoiceField(label='Σύνδεση με εργαζόμενο',queryset=Employee.objects.none(),required=False)
    scope=forms.ChoiceField(label='Πρόσβαση στις μετακινήσεις',choices=UserAccess.Scope.choices)
    departments=forms.ModelMultipleChoiceField(label='Μονάδες',queryset=Department.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    permissions=forms.ModelMultipleChoiceField(queryset=editable_permissions(),required=False,widget=forms.CheckboxSelectMultiple)

    class Meta:
        model=get_user_model()
        fields=['username','first_name','last_name','email','is_active']
        labels={'username':'Όνομα χρήστη','first_name':'Όνομα','last_name':'Επώνυμο','email':'Email','is_active':'Ενεργός'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        from django.db.models import Q
        self.fields['employee'].queryset=Employee.objects.filter(Q(user__isnull=True)|Q(user_id=self.instance.pk)).order_by('display_name')
        if self.instance.pk:
            access=UserAccess.objects.filter(user=self.instance).first()
            self.initial.update(employee=Employee.objects.filter(user=self.instance).first(),scope=access.scope if access else 'own',departments=access.departments.all() if access else [],permissions=self.instance.user_permissions.all())

    def clean(self):
        data=super().clean()
        if not self.instance.pk and not data.get('password'):
            self.add_error('password','Συμπληρώστε κωδικό για νέο χρήστη.')
        if data.get('password'):
            validate_password(data['password'],self.instance)
        if data.get('scope')=='department' and not data.get('departments'):
            self.add_error('departments','Επιλέξτε τουλάχιστον μία μονάδα.')
        return data


@login_required
def users(request):
    if not request.user.is_superuser:
        raise PermissionDenied
    return render(request,'core/users.html',{'users':get_user_model().objects.order_by('username')})


@login_required
def user_edit(request,pk=None):
    if not request.user.is_superuser:
        raise PermissionDenied
    with transaction.atomic():
        user=get_object_or_404(get_user_model().objects.select_for_update(),pk=pk) if pk else get_user_model()()
        form=UserForm(request.POST if request.method=='POST' else None,instance=user)
        if request.method=='POST' and form.is_valid():
            if user.is_superuser:
                form.add_error(None,'Οι λογαριασμοί διαχειριστή συστήματος τροποποιούνται από το Django admin.')
            else:
                user=form.save(commit=False)
                if form.cleaned_data['password']: user.set_password(form.cleaned_data['password'])
                user.save()
                # The matrix is authoritative: remove inherited grants that would override it.
                user.groups.clear()
                user.user_permissions.set(form.cleaned_data['permissions'])
                Employee.objects.filter(user=user).update(user=None)
                employee=form.cleaned_data['employee']
                if employee:
                    employee=Employee.objects.select_for_update().get(pk=employee.pk)
                    if employee.user_id and employee.user_id!=user.pk:
                        raise PermissionDenied
                    employee.user=user;employee.save(update_fields=['user'])
                access,_=UserAccess.objects.update_or_create(user=user,defaults={'scope':form.cleaned_data['scope']})
                access.departments.set(form.cleaned_data['departments'] if access.scope=='department' else [])
                return redirect('core:users')
        selected=set(str(x.pk) for x in form.initial.get('permissions',[]))
        if form.is_bound: selected=set(request.POST.getlist('permissions'))
        modules={}
        for permission in editable_permissions():
            action=permission.codename.split('_',1)[0]
            modules.setdefault(permission.content_type.model,{'name':MODULE_LABELS.get(permission.content_type.model, permission.content_type.name),'cells':{}})['cells'][action]={'id':permission.pk,'selected':str(permission.pk) in selected}
        rows=[{'name':r['name'],'cells':[r['cells'].get(a) for a in ['view','add','change','delete']]} for r in modules.values()]
    return render(request,'core/user_form.html',{'form':form,'rows':rows,'target_user':user})
