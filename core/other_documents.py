from .number_formats import greek_number
from .date_widgets import GreekDateInput
from io import BytesIO
from xml.sax.saxutils import escape
from django import forms
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from .approval_pdf import fonts
from .models import ApplicationParameters
from .views import visible_travels


class DocumentForm(forms.Form):
    kind=forms.ChoiceField(label='Έγγραφο',choices=[('car','Υπεύθυνη δήλωση χρήσης ΙΧ'),('friends','Υπεύθυνη δήλωση διαμονής σε φιλικό σπίτι'),('activity','Έκθεση πεπραγμένων')])
    print_date=forms.DateField(label='Ημερομηνία εγγράφου',widget=GreekDateInput(),input_formats=['%d/%m/%Y','%Y-%m-%d'])


def document_pdf(travel,kind,print_date):
    fonts();employee=travel.employee
    params=ApplicationParameters.objects.filter(pk=1).first()
    if not params:raise ValidationError('Λείπουν οι παράμετροι εφαρμογής.')
    fmt=lambda day:day.strftime('%d/%m/%Y') if day else ''
    details=[]
    if kind in ('car','friends'):
        if not employee.gender or not employee.gender.text2 or not employee.gender.text3:
            raise ValidationError('Συμπληρώστε τη γραμματική προσφώνηση του εργαζομένου.')
        details=[('Όνομα / Επώνυμο',employee.first_name+' '+employee.last_name),('Πατέρας / Μητέρα',employee.father_name+' / '+employee.mother_name),('Ημερομηνία / τόπος γέννησης',fmt(employee.birth_date)+' / '+employee.birth_place),('Ταυτότητα / ΑΦΜ',employee.id_number+' / '+employee.tax_number),('Κατοικία',employee.address+' '+employee.address_number+', '+employee.postal_code+' '+employee.city),('Τηλέφωνο / email',employee.phone+' / '+employee.email)]
    protocol=' / '.join(x for x in [travel.protocol_number,fmt(travel.protocol_date)] if x)
    reference=(' Η παρούσα συνοδεύει την απόφαση έγκρισης μετακίνησης '+protocol+'.') if protocol else ''
    if kind=='car':
        if not employee.car_plate or not employee.car_brand or not employee.driving_license:raise ValidationError('Συμπληρώστε πινακίδα, μάρκα και άδεια οδήγησης στον εργαζόμενο.')
        if not ((travel.transport_configured and travel.transport_id and travel.transport.has_mileage_cost) or (not travel.transport_configured and travel.expenses.filter(kind='mileage',is_cancelled=False).exists())):raise ValidationError('Η μετακίνηση δεν περιλαμβάνει χρήση ΙΧ.')
        from .calculation import input_state,signature
        estimate=travel.calculations.filter(stage='estimate').order_by('-revision').first()
        if not estimate or estimate.algorithm_version!='estimate-3' or estimate.inputs.get('signature')!=signature(input_state(travel)):raise ValidationError('Αποθηκεύστε τη μετακίνηση ώστε να υπάρχει ενημερωμένος υπολογισμός.')
        body=employee.gender.text3+' '+employee.display_name+' με ατομική μου ευθύνη, δηλώνω ότι από '+fmt(travel.departure_at)+' έως '+fmt(travel.return_at)+' μετακινήθηκα για εκτέλεση υπηρεσίας στην/στις τοποθεσία/ες '+travel.route.destination+'. Για την εν λόγω μετακίνηση χρησιμοποίησα το με αριθμό κυκλοφορίας '+employee.car_plate+' ΙΧ αυτοκίνητό μου, τύπου '+employee.car_brand+'. Αριθμός αδείας οδήγησης: '+employee.driving_license+'. Χιλιόμετρα: '+greek_number(travel.route.distance_km)+'. Κόστος χιλιομετρικής αποζημίωσης: '+greek_number(estimate.mileage)+' ευρώ.'+reference
    elif kind=='friends':
        nights=list(travel.overnights.filter(accommodation_type__requires_declaration=True,is_excluded=False).order_by('date'))
        if not nights:raise ValidationError('Δεν υπάρχουν διανυκτερεύσεις σε φιλικό σπίτι.')
        body='Με ατομική μου ευθύνη δηλώνω ότι κατά τη διάρκεια της επίσκεψής μου στην/στις τοποθεσία/ες '+travel.route.destination+' για υπηρεσιακούς λόγους, διανυκτέρευσα σε φιλικό σπίτι τις παρακάτω ημερομηνίες:\n'+'\n'.join(fmt(n.date)+' — '+n.city for n in nights)+reference
    else:
        if not travel.actions_description.strip():raise ValidationError('Συμπληρώστε την περιγραφή πεπραγμένων στη μετακίνηση.')
        body='Εργαζόμενος: '+employee.display_name+'\nΔιαδρομή: '+travel.route.name+'\nΤαξίδι: '+fmt(travel.departure_at)+' έως '+fmt(travel.return_at)+'\nΕργασίες: '+fmt(travel.work_starts_at)+' έως '+fmt(travel.work_ends_at)+'\nΣκοπός: '+travel.purpose+'\n\n'+travel.actions_description
    title='ΕΚΘΕΣΗ ΠΕΠΡΑΓΜΕΝΩΝ' if kind=='activity' else 'ΥΠΕΥΘΥΝΗ ΔΗΛΩΣΗ'
    style=ParagraphStyle('OtherBody',fontName='ApprovalGreek',fontSize=10,leading=15,spaceAfter=10)
    heading=ParagraphStyle('OtherHeading',parent=style,fontName='ApprovalGreekBold',alignment=TA_CENTER,fontSize=13)
    paragraph=lambda text:Paragraph(escape(text).replace('\n','<br/>'),style)
    flow=[paragraph(params.document_header),Spacer(1,16),Paragraph(title,heading),Spacer(1,14)]
    if details:
        table=Table([[paragraph(k),paragraph(v)] for k,v in details],colWidths=[160,350]);table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LINEBELOW',(0,0),(-1,-1),.3,'#bbbbbb')]))
        flow.extend([table,Spacer(1,18)])
    flow.extend([paragraph(body),Spacer(1,25),paragraph('Ημερομηνία: '+fmt(print_date)),paragraph((employee.gender.text2 if employee.gender else 'Υπογραφή')+'\n\n'+employee.display_name)])
    stream=BytesIO();SimpleDocTemplate(stream,pagesize=A4,leftMargin=42,rightMargin=42,topMargin=35,bottomMargin=45,title=title).build(flow)
    return stream.getvalue()


@login_required
def other_documents(request,pk):
    if not request.user.has_perm('core.print_travel'):raise PermissionDenied
    travel=get_object_or_404(visible_travels(request.user),pk=pk)
    form=DocumentForm(request.POST if request.method=='POST' else None,initial={'print_date':travel.return_at})
    if request.method=='POST' and form.is_valid():
        try:data=document_pdf(travel,form.cleaned_data['kind'],form.cleaned_data['print_date'])
        except ValidationError as error:form.add_error(None,error)
        else:
            response=HttpResponse(data,content_type='application/pdf')
            response['Content-Disposition']=f'attachment; filename="travel-{travel.pk}-{form.cleaned_data["kind"]}.pdf"'
            response['Cache-Control']='private, no-store';response['X-Content-Type-Options']='nosniff'
            return response
    return render(request,'core/other_documents.html',{'form':form,'travel':travel})
