from .number_formats import greek_number
from .date_widgets import GreekDateInput
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from .models import ApplicationParameters
from .views import visible_travels
from .other_document_pdf import render_document

DOCUMENT_TYPES=[('car','Υπεύθυνη δήλωση χρήσης ΙΧ'),('friends','Υπεύθυνη δήλωση διαμονής σε φιλικό σπίτι'),('activity','Αναφορά πεπραγμένων μετακίνησης')]

def friends_nights(travel):
    return travel.overnights.filter(accommodation_type__requires_declaration=True,is_excluded=False).select_related('stop').order_by('date','pk')

def uses_car(travel):
    return bool(travel.transport_id and travel.transport.has_mileage_cost) if travel.transport_configured else travel.expenses.filter(kind='mileage',is_cancelled=False).exists()

class DocumentForm(forms.Form):
    kind=forms.ChoiceField(label='Έγγραφο',choices=DOCUMENT_TYPES)
    print_date=forms.DateField(label='Ημερομηνία εγγράφου',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])

    def __init__(self,*args,travel,**kwargs):
        super().__init__(*args,**kwargs)
        self.fields['kind'].choices=[(key,label) for key,label in DOCUMENT_TYPES if (key!='friends' or friends_nights(travel).exists()) and (key!='car' or uses_car(travel))]

def document_pdf(travel,kind,print_date):
    if kind not in dict(DOCUMENT_TYPES):raise ValidationError('Μη έγκυρο είδος εγγράφου.')
    employee=travel.employee
    params=ApplicationParameters.objects.filter(pk=1).first()
    if not params:raise ValidationError('Λείπουν οι παράμετροι εφαρμογής.')
    fmt=lambda day:day.strftime('%d/%m/%Y') if day else ''
    protocol=' / '.join(x for x in [travel.protocol_number,fmt(travel.protocol_date)] if x)
    data={'kind':kind,'employee':employee,'recipient':params.report_recipient,'place':params.report_place,'address':params.report_address,
        'print_date':fmt(print_date),'birth_date':fmt(employee.birth_date),'protocol':protocol,'destination':travel.route.destination,
        'departure':fmt(travel.departure_at),'return':fmt(travel.return_at),'purpose':travel.purpose,'actions':travel.actions_description,
        'work_dates':fmt(travel.work_starts_at)+((' - '+fmt(travel.work_ends_at)) if travel.work_ends_at!=travel.work_starts_at else ''),
        'declarant':employee.gender.text2 if employee.gender else ''}
    if kind in ('car','friends') and not data['declarant'].strip():raise ValidationError('Συμπληρώστε τη γραμματική προσφώνηση του εργαζομένου.')
    reference=('Η παρούσα δήλωση συνοδεύει την υπ. αρ. πρωτ. '+protocol+' απόφαση έγκρισης μετακίνησης '+params.approval_service_genitive+'.') if protocol else ''
    if kind=='car':
        if not uses_car(travel):raise ValidationError('Η μετακίνηση δεν περιλαμβάνει χρήση ΙΧ.')
        if not employee.gender.text3.strip():raise ValidationError('Συμπληρώστε τη γραμματική προσφώνηση του εργαζομένου.')
        if not employee.car_plate or not employee.car_brand or not employee.driving_license:raise ValidationError('Συμπληρώστε πινακίδα, μάρκα και άδεια οδήγησης στον εργαζόμενο.')
        from .calculation import input_state,signature
        estimate=travel.calculations.filter(stage='estimate').order_by('-revision').first()
        if not estimate or estimate.algorithm_version!='estimate-3' or estimate.inputs.get('signature')!=signature(input_state(travel)):raise ValidationError('Αποθηκεύστε τη μετακίνηση ώστε να υπάρχει ενημερωμένος υπολογισμός.')
        journey=employee.gender.text3+' '+employee.display_name+' με ατομική μου ευθύνη, δηλώνω ότι από '+fmt(travel.departure_at)+' έως '+fmt(travel.return_at)+' μετακινήθηκα για εκτέλεση υπηρεσίας στην/στις τοποθεσία/ες '+travel.route.destination
        journey+=(' με την υπ’ αριθμό '+protocol+' απόφαση έγκρισης μετακίνησης '+params.approval_service_genitive) if protocol else ''
        data.update(car_journey=journey+'.',car_vehicle='Για την εν λόγω μετακίνηση χρησιμοποίησα το με αριθμό κυκλοφορίας '+employee.car_plate+' ΙΧ αυτοκίνητό μου, τύπου '+employee.car_brand+'.',
            driving_license=employee.driving_license,distance=greek_number(estimate.inputs.get('display_distance_km',travel.route.distance_km)),mileage=greek_number(estimate.mileage))
    elif kind=='friends':
        nights=list(friends_nights(travel))
        if not nights:raise ValidationError('Δεν υπάρχουν διανυκτερεύσεις σε φιλικό σπίτι.')
        data['friends_body']='Κατά τη διάρκεια της επίσκεψής μου στην/στις τοποθεσία/ες '+travel.route.destination+' για υπηρεσιακούς λόγους, διανυκτέρευσα σε φιλικό σπίτι τις παρακάτω ημερομηνίες:\n'+'\n'.join(fmt(n.date)+'  '+(n.city or n.stop.city) for n in nights)+('\n'+reference if reference else '')
    elif not travel.actions_description.strip():raise ValidationError('Συμπληρώστε την περιγραφή πεπραγμένων στη μετακίνηση.')
    return render_document(data)

@login_required
def other_documents(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    form=DocumentForm(request.POST if request.method=='POST' else None,travel=travel,initial={'print_date':travel.return_at})
    if request.method=='POST' and form.is_valid():
        try:data=document_pdf(travel,form.cleaned_data['kind'],form.cleaned_data['print_date'])
        except ValidationError as error:form.add_error(None,error.messages)
        else:
            response=HttpResponse(data,content_type='application/pdf')
            response['Content-Disposition']=f'attachment; filename="travel-{travel.pk}-{form.cleaned_data["kind"]}.pdf"'
            response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
            return response
    return render(request,'core/other_documents.html',{'form':form,'travel':travel})
