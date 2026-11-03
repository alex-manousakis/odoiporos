from django import forms
from django.conf import settings
from django.contrib.auth.decorators import login_required, permission_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .models import Route, RouteStop, ApplicationParameters


class RouteForm(forms.ModelForm):
    class Meta:
        model=Route
        fields=['origin','is_abroad','distance_km','short_description','notes','is_active','has_daily_allowance','requires_review']
        labels={'origin':'Από','is_abroad':'Μετακίνηση στο εξωτερικό','distance_km':'Συνολική απόσταση με επιστροφή (χλμ.)','short_description':'Σύντομη περιγραφή','notes':'Παρατηρήσεις','is_active':'Ενεργή','has_daily_allowance':'Η διαδρομή έχει ημερήσια αποζημίωση','requires_review':'Χρειάζεται έλεγχο'}
        widgets={'notes':forms.Textarea(attrs={'rows':3})}


class StopForm(forms.ModelForm):
    class Meta:
        model=RouteStop
        fields=['city','is_abroad','is_expensive','is_island','compensation_band']
        labels={'city':'Προς','is_abroad':'Η στάση είναι στο εξωτερικό','is_expensive':'Αθήνα / Θεσσαλονίκη ή ειδική πόλη εξωτερικού','is_island':'Είναι σε νησί','compensation_band':'Κατηγορία αποζημίωσης'}

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        parameters=ApplicationParameters.objects.filter(pk=1).first()
        choices=[(1,'Όλες οι λοιπές χώρες'),(2,parameters.countriescomp2 or 'Κατηγορία 2'),(3,parameters.countriescomp3 or 'Κατηγορία 3')] if parameters else getattr(settings,'ROUTE_COMPENSATION_CHOICES',[(1,'Κατηγορία 1'),(2,'Κατηγορία 2'),(3,'Κατηγορία 3')])
        self.fields['is_expensive'].label=('Ειδική πόλη: '+parameters.expensivecitiesingreece+' / '+parameters.expensivecitiesabroad) if parameters else self.fields['is_expensive'].label
        self.fields['compensation_band']=forms.TypedChoiceField(label='Κατηγορία αποζημίωσης',coerce=int,initial=self.instance.compensation_band if self.instance.pk else 1,choices=choices)

    def has_changed(self):
        if not self.instance.pk and self.is_bound and not self.data.get(self.add_prefix('city'),'').strip():
            return False
        return super().has_changed()

    def clean(self):
        data=super().clean()
        if data.get('is_expensive') and data.get('is_island'):
            raise forms.ValidationError('Επιλέξτε ειδική πόλη ή νησί, όχι και τα δύο.')
        if not data.get('is_abroad') and data.get('compensation_band',1)!=1:
            self.add_error('compensation_band','Για στάση στην Ελλάδα επιλέξτε κατηγορία 1.')
        return data


class StopsBase(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors): return
        stops=[f for f in self.forms if f.cleaned_data and not f.cleaned_data.get('DELETE')]
        if not stops:
            raise forms.ValidationError('Συμπληρώστε τουλάχιστον έναν προορισμό.')
        if not self.instance.is_abroad and any(f.cleaned_data.get('is_abroad') for f in stops):
            raise forms.ValidationError('Εσωτερική διαδρομή δεν μπορεί να περιέχει στάση εξωτερικού.')


Stops=forms.inlineformset_factory(Route,RouteStop,form=StopForm,formset=StopsBase,extra=5,max_num=5,validate_max=True,can_delete=True)


@login_required
@permission_required('core.view_route',raise_exception=True)
def route_list(request):
    query=request.GET.get('q','').strip()
    routes=Route.objects.all().order_by('name')
    if query: routes=routes.filter(Q(name__icontains=query)|Q(origin__icontains=query)|Q(destination__icontains=query)|Q(short_description__icontains=query))
    kind=request.GET.get('kind','')
    if kind in ('domestic','abroad'): routes=routes.filter(is_abroad=kind=='abroad')
    return render(request,'core/routes.html',{'page':Paginator(routes,30).get_page(request.GET.get('page')),'q':query,'kind':kind})


@login_required
def route_edit(request,pk=None):
    from django.core.exceptions import PermissionDenied
    if not request.user.has_perm('core.change_route' if pk else 'core.add_route'):
        raise PermissionDenied
    with transaction.atomic():
        route=get_object_or_404(Route.objects.select_for_update(),pk=pk) if pk else Route()
        used=bool(route.pk and route.travels.exists())
        form=RouteForm(request.POST if request.method=='POST' else None,instance=route)
        if used:
            for name,field in form.fields.items():
                if name not in ('short_description','notes','is_active'): field.disabled=True
        valid=form.is_valid() if request.method=='POST' else False
        stops=Stops(request.POST if request.method=='POST' else None,instance=route,prefix='stops')
        if used:
            for row in stops:
                for field in row.fields.values(): field.disabled=True
        if request.method=='POST' and valid and stops.is_valid():
            active=[r for r in stops.forms if r.cleaned_data and not r.cleaned_data.get('DELETE')]
            if not used:
                route.destination='-'.join(r.cleaned_data['city'] for r in active)
                if len(route.destination)>150:
                    form.add_error(None,'Οι προορισμοί υπερβαίνουν τους 150 χαρακτήρες συνολικά.')
                route.name=(route.origin+' - '+route.destination)[:100]
            if not form.errors:
                route.full_clean();route.save()
                if not used:
                    # Preserve existing stop IDs; assign new slots without uniqueness collisions.
                    existing=list(route.stops.order_by('sequence'))
                    for i,stop in enumerate(existing):
                        stop.sequence=1000+i;stop.save(update_fields=['sequence'])
                    objects=stops.save(commit=False)
                    for deleted in stops.deleted_objects: deleted.delete()
                    for i,row in enumerate(active):
                        stop=row.instance;stop.route=route;stop.sequence=i+1;stop.save()
                return redirect('core:routes')
    return render(request,'core/route_form.html',{'form':form,'stops':stops,'route':route,'used':used})
