from django import forms
from . import models as m


class TravelForm(forms.ModelForm):
    class Meta:
        model = m.Travel
        fields = ['employee','route','departure_at','return_at','work_starts_at','work_ends_at','reason','purpose','notes']
        labels = {'employee':'Εργαζόμενος','route':'Διαδρομή','departure_at':'Αναχώρηση','return_at':'Επιστροφή','work_starts_at':'Έναρξη εργασιών','work_ends_at':'Λήξη εργασιών','reason':'Αιτία','purpose':'Σκοπός','notes':'Παρατηρήσεις'}
        widgets = {name:forms.DateInput(format='%Y-%m-%d',attrs={'type':'date'}) for name in ['departure_at','return_at','work_starts_at','work_ends_at']}
        widgets.update(purpose=forms.Textarea(attrs={'rows':3}),notes=forms.Textarea(attrs={'rows':2}))

    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['employee'].queryset=m.Employee.objects.filter(is_active=True).order_by('display_name')
        if not user.has_perm('core.add_travel'):
            self.fields['employee'].queryset=self.fields['employee'].queryset.filter(user=user)
        self.fields['route'].queryset=m.Route.objects.filter(is_active=True).order_by('name')
        self.fields['reason'].queryset=m.TravelReason.objects.filter(is_active=True).order_by('name')
        for name in ['departure_at','return_at','work_starts_at','work_ends_at']:
            self.fields[name].input_formats=['%Y-%m-%d']

    def clean(self):
        data=super().clean()
        dates=[data.get(n) for n in ['departure_at','work_starts_at','work_ends_at','return_at']]
        if all(dates) and dates != sorted(dates):
            raise forms.ValidationError('Οι ημερομηνίες πρέπει να είναι: αναχώρηση ≤ έναρξη εργασιών ≤ λήξη εργασιών ≤ επιστροφή.')
        employee=data.get('employee')
        if employee and all(dates):
            start,end=dates[0],dates[-1]
            history=employee.category_history.filter(valid_from__lte=start).filter(m.models.Q(valid_to__isnull=True)|m.models.Q(valid_to__gte=end))
            if history.count()==1:
                self.instance.applied_category=history.get().category
            else:
                self.instance.applied_category=None
            self.instance.category_review_required=self.instance.applied_category_id is None
        return data
