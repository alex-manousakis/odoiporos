from .number_formats import GreekNumberFormMixin
from .date_widgets import GreekDateInput
from django import forms
from . import models as m


class TravelForm(GreekNumberFormMixin, forms.ModelForm):
    confirm_transport_replacement = forms.BooleanField(label='Επιβεβαιώνω την αντικατάσταση των παλιών επιμέρους εκτιμήσεων με το επιλεγμένο μέσο και ποσά',required=False)
    class Meta:
        model = m.Travel
        fields = ['employee','route','departure_at','return_at','work_starts_at','work_ends_at','protocol_number','protocol_date','reason','purpose','actions_description','notes','transport','ticket_cost','transfer_cost']
        labels = {'employee':'Εργαζόμενος','route':'Διαδρομή','departure_at':'Αναχώρηση','return_at':'Επιστροφή','work_starts_at':'Έναρξη εργασιών','work_ends_at':'Λήξη εργασιών','reason':'Αιτία','purpose':'Σκοπός','notes':'Παρατηρήσεις'}
        widgets = {name:GreekDateInput() for name in ['departure_at','return_at','work_starts_at','work_ends_at']}
        widgets.update(protocol_date=GreekDateInput(),actions_description=forms.Textarea(attrs={'rows':3}),purpose=forms.Textarea(attrs={'rows':3}),notes=forms.Textarea(attrs={'rows':2}))

    def __init__(self,*args,user,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['transport'].label='Μέσο μετακίνησης'
        self.fields['ticket_cost'].label='Κόστος εισιτηρίων (€)'
        self.fields['transfer_cost'].label='Μετρό / ταξί από και προς αεροδρόμιο (€)'
        self.fields['transport'].queryset=m.TransportMode.objects.filter(m.models.Q(is_active=True)|m.models.Q(pk=self.instance.transport_id)).order_by('name')
        legacy=self.instance.expenses.filter(is_cancelled=False) if self.instance.pk else m.TravelExpense.objects.none()
        self.legacy_transport_review=not self.instance.transport_configured and (legacy.filter(kind='other').exists() or legacy.values('transport_id').distinct().count()>1)
        if not self.legacy_transport_review:self.fields.pop('confirm_transport_replacement')
        self.fields['protocol_number'].label='Αριθμός πρωτοκόλλου'
        self.fields['protocol_date'].label='Ημερομηνία πρωτοκόλλου'
        self.fields['actions_description'].label='Περιγραφή πεπραγμένων'
        from .access import employee_scope
        self.fields['employee'].queryset=employee_scope(user).filter(is_active=True).order_by('display_name')
        self.fields['route'].queryset=m.Route.objects.filter(is_active=True).order_by('name')
        self.fields['reason'].queryset=m.TravelReason.objects.filter(is_active=True).order_by('name')
        for name in ['departure_at','return_at','work_starts_at','work_ends_at']:
            self.fields[name].input_formats=['%d/%m/%Y','%Y-%m-%d']

    def clean(self):
        data=super().clean()
        if 'transport_section' in self.data or data.get('transport') or self.instance.transport_configured:
            transport=data.get('transport')
            if not transport:self.add_error('transport','Επιλέξτε μέσο μετακίνησης.')
            else:
                if transport.has_mileage_cost:
                    route=data.get('route')
                    if route and route.distance_km<=0:self.add_error('route','Η διαδρομή πρέπει να έχει θετική απόσταση για χιλιομετρική αποζημίωση.')
                if transport.has_ticket_cost:
                    if data.get('ticket_cost') is None:self.add_error('ticket_cost','Συμπληρώστε το κόστος εισιτηρίων.')
                    if data.get('transfer_cost') is None:data['transfer_cost']=0
                else:
                    # Unsupported submitted costs cannot influence calculation.
                    data['ticket_cost']=None;data['transfer_cost']=None
                if self.legacy_transport_review and not data.get('confirm_transport_replacement'):
                    self.add_error('confirm_transport_replacement','Ελέγξτε τις παλιές δαπάνες και επιβεβαιώστε τη νέα εκτίμηση.')
                self.instance.transport_configured=True
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


class ExpenseForm(GreekNumberFormMixin, forms.ModelForm):
    class Meta:
        model=m.TravelExpense
        fields=['kind','transport','description','estimated_amount','estimated_transfer_cost','estimated_distance_km']
        labels={'kind':'Είδος','transport':'Μέσο μετακίνησης','description':'Περιγραφή','estimated_amount':'Εκτιμώμενο ποσό (€)','estimated_distance_km':'Χιλιόμετρα ΙΧ'}

    def __init__(self,*args,travel=None,**kwargs):
        self.travel=travel
        super().__init__(*args,**kwargs)
        self.fields["estimated_distance_km"].disabled=True
        self.fields["estimated_distance_km"].initial=travel.route.distance_km if travel and travel.route_id else None
        self.fields["estimated_distance_km"].help_text="Distance from the selected route, including return."
        self.fields['estimated_transfer_cost'].label='Μετρό / ταξί από και προς αεροδρόμιο (€)'
        self.fields['kind'].choices=[('', '---------'),('ticket','Εισιτήριο'),('mileage','Χιλιομετρική αποζημίωση'),('other','Λοιπά έξοδα')]
        self.fields['transport'].queryset=m.TransportMode.objects.filter(is_active=True).order_by('name')

    def has_changed(self):
        # Extra rows may have only the old browser-default kind='ticket'.
        # A type choice alone is not a new expense and must not block parent edits.
        if not self.instance.pk and self.is_bound:
            meaningful = ['transport','description','estimated_amount','estimated_transfer_cost','estimated_distance_km']
            if not any(self.data.get(self.add_prefix(name), '').strip() for name in meaningful):
                return False
        return super().has_changed()

    def clean(self):
        data=super().clean()
        kind=data.get('kind');transport=data.get('transport')
        if data.get('estimated_transfer_cost') is not None and (kind!='ticket' or not transport or not transport.has_ticket_cost):
            self.add_error('estimated_transfer_cost','Το κόστος πρόσβασης συμπληρώνεται μόνο μαζί με εισιτήριο δημόσιου μέσου.')
        if kind=='mileage':
            if not transport or not transport.has_mileage_cost:
                self.add_error('transport','Επιλέξτε μέσο με χιλιομετρική αποζημίωση.')
            route=self.travel.route if self.travel and self.travel.route_id else None
            if not route or route.distance_km<=0:
                self.add_error('transport','The selected route must have a positive distance for mileage reimbursement.')
            else:
                data['estimated_distance_km']=route.distance_km
            if data.get('estimated_amount') is not None:
                self.add_error('estimated_amount','Το ποσό χιλιομετρικής αποζημίωσης θα υπολογιστεί από την τιμή ανά χιλιόμετρο.')
        elif kind:
            if data.get('estimated_amount') is None:
                self.add_error('estimated_amount','Συμπληρώστε το εκτιμώμενο ποσό.')
            data['estimated_distance_km']=None
            if kind=='ticket' and (not transport or not transport.has_ticket_cost):
                self.add_error('transport','Επιλέξτε μέσο με κόστος εισιτηρίου.')
        return data


class OvernightForm(GreekNumberFormMixin, forms.ModelForm):
    class Meta:
        model=m.OvernightStay
        fields=['date','stop','accommodation_type','estimated_cost']
        labels={'date':'Νύχτα διαμονής','stop':'Τόπος διαμονής','accommodation_type':'Τύπος διαμονής','estimated_cost':'Εκτιμώμενο κόστος (€)'}
        widgets={'date':GreekDateInput()}

    def __init__(self,*args,travel,**kwargs):
        self.travel=travel
        super().__init__(*args,**kwargs)
        self.fields['date'].input_formats=['%d/%m/%Y','%Y-%m-%d']
        self.fields['stop'].queryset=travel.route.stops.all() if travel.route_id else m.RouteStop.objects.none()
        self.fields['stop'].label_from_instance=lambda stop:stop.city
        self.fields['accommodation_type'].queryset=m.AccommodationType.objects.filter(is_active=True).order_by('name')

    def clean(self):
        data=super().clean()
        day=data.get('date');stop=data.get('stop');kind=data.get('accommodation_type');cost=data.get('estimated_cost')
        if day and self.travel.departure_at and self.travel.return_at and not self.travel.departure_at <= day < self.travel.return_at:
            self.add_error('date','Η νύχτα πρέπει να είναι από την αναχώρηση έως την προηγουμένη της επιστροφής.')
        if kind and not kind.has_cost:
            data['estimated_cost']=None
            self.instance.estimated_cost=None
        if kind and kind.has_cost and cost is None:
            self.add_error('estimated_cost','Συμπληρώστε εκτιμώμενο κόστος.')
        if stop:
            for name in ['city','is_abroad','is_expensive','is_island','compensation_band']:
                setattr(self.instance,name,getattr(stop,name))
        return data


class OvernightFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        dates=[]
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE'):
                day=form.cleaned_data.get('date')
                if day in dates:
                    raise forms.ValidationError('Κάθε νύχτα διαμονής καταχωρίζεται μία φορά.')
                dates.append(day)


class ExpenseInlineFormSet(forms.BaseInlineFormSet):
    def get_form_kwargs(self,index):
        kwargs=super().get_form_kwargs(index)
        kwargs['travel']=self.instance
        return kwargs

    def clean(self):
        super().clean()
        if any(self.errors):return
        mileage=[f for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE') and f.cleaned_data.get('kind')=='mileage' and not f.instance.is_cancelled]
        if len(mileage)>1:
            raise forms.ValidationError('Only one mileage entry is allowed: the route distance already includes the return.')


ExpenseFormSet=forms.inlineformset_factory(m.Travel,m.TravelExpense,form=ExpenseForm,formset=ExpenseInlineFormSet,extra=2,can_delete=True)
StayFormSet=forms.inlineformset_factory(m.Travel,m.OvernightStay,form=OvernightForm,formset=OvernightFormSet,extra=2,can_delete=True)
