from .date_widgets import GreekDateInput
from django import forms
from django.db.models import Q
from .models import Employee, Department, TravelStatus


class TravelSearchForm(forms.Form):
    statuses=forms.ModelMultipleChoiceField(label='Κατάσταση',queryset=TravelStatus.objects.all(),required=False,widget=forms.CheckboxSelectMultiple)
    employee=forms.ModelChoiceField(label='Εργαζόμενος',queryset=Employee.objects.none(),required=False)
    department=forms.ModelChoiceField(label='Μονάδα',queryset=Department.objects.none(),required=False)
    number=forms.CharField(label='Αριθμός μετακίνησης',required=False)
    protocol=forms.CharField(label='Αριθμός πρωτοκόλλου',required=False)
    year=forms.IntegerField(label='Έτος ταξιδιού',min_value=1900,max_value=9999,required=False)
    created_on=forms.DateField(label='Ημερομηνία δημιουργίας',required=False,widget=GreekDateInput())
    protocol_on=forms.DateField(label='Ημερομηνία πρωτοκόλλου',required=False,widget=GreekDateInput())
    travel_from=forms.DateField(label='Ταξίδι από',required=False,widget=GreekDateInput())
    travel_to=forms.DateField(label='Ταξίδι έως',required=False,widget=GreekDateInput())
    purpose=forms.CharField(label='Σκοπός μετακίνησης',required=False)
    actions=forms.CharField(label='Περιγραφή πεπραγμένων',required=False)
    destination=forms.CharField(label='Προορισμός',required=False)
    review=forms.BooleanField(label='Για έλεγχο διαδρομής',required=False)

    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs)
        from .access import employee_scope
        allowed=employee_scope(user)
        self.fields['employee'].queryset=allowed.order_by('display_name')
        self.fields['department'].queryset=Department.objects.filter(employee__in=allowed).distinct().order_by('name')

    def clean(self):
        data=super().clean()
        if data.get('travel_from') and data.get('travel_to') and data['travel_from']>data['travel_to']:
            raise forms.ValidationError('Η ημερομηνία από δεν μπορεί να είναι μετά την ημερομηνία έως.')
        return data

    def apply(self,qs):
        if not self.is_valid():return qs.none()
        d=self.cleaned_data
        if d['statuses']:qs=qs.filter(status__in=d['statuses'])
        for key,lookup in [('employee','employee'),('department','employee__department'),('protocol','protocol_number__icontains'),('purpose','purpose__icontains'),('actions','actions_description__icontains'),('destination','route__destination__icontains'),('created_on','created_at__date'),('protocol_on','protocol_date')]:
            if d[key]:qs=qs.filter(**{lookup:d[key]})
        if d['number']:
            condition=Q(number__icontains=d['number'])
            if d['number'].isdigit():condition|=Q(pk=int(d['number']))
            qs=qs.filter(condition)
        if d['year']:qs=qs.filter(departure_at__lte=f"{d['year']}-12-31",return_at__gte=f"{d['year']}-01-01")
        if d['travel_from']:qs=qs.filter(return_at__gte=d['travel_from'])
        if d['travel_to']:qs=qs.filter(departure_at__lte=d['travel_to'])
        if d['review']:qs=qs.filter(route__requires_review=True)
        return qs
