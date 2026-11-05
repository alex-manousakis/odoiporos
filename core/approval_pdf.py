from .number_formats import greek_number
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from threading import Lock
from xml.sax.saxutils import escape
import hashlib
import os
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from .models import ApplicationParameters, ReportDefinition, ReportText, ApprovalDocument, Travel
from .calculation import input_state, signature

FONT_LOCK=Lock()


def fonts():
    with FONT_LOCK:
        if 'ApprovalGreek' in pdfmetrics.getRegisteredFontNames():return
        candidates=[(os.getenv('APPROVAL_FONT_REGULAR',''),os.getenv('APPROVAL_FONT_BOLD','')),
                    ('C:/Windows/Fonts/arial.ttf','C:/Windows/Fonts/arialbd.ttf'),
                    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')]
        for regular,bold in candidates:
            if regular and Path(regular).is_file() and bold and Path(bold).is_file():
                pdfmetrics.registerFont(TTFont('ApprovalGreek',regular))
                pdfmetrics.registerFont(TTFont('ApprovalGreekBold',bold))
                pdfmetrics.registerFontFamily('ApprovalGreek',normal='ApprovalGreek',bold='ApprovalGreekBold',italic='ApprovalGreek',boldItalic='ApprovalGreekBold')
                return
        raise ValidationError('Δεν βρέθηκε γραμματοσειρά ελληνικών. Ρυθμίστε APPROVAL_FONT_REGULAR και APPROVAL_FONT_BOLD.')


def render_pdf(source):
    fonts()
    stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=85,title='ΑΠΟΦΑΣΗ ΕΓΚΡΙΣΗΣ ΜΕΤΑΚΙΝΗΣΗΣ',author=source['signatory']['name'])
    style=ParagraphStyle('Body',fontName='ApprovalGreek',fontSize=9,leading=12,spaceAfter=7)
    title=ParagraphStyle('Title',parent=style,fontName='ApprovalGreekBold',fontSize=12,leading=16,alignment=TA_CENTER,spaceAfter=12)
    decision_heading=ParagraphStyle('DecisionHeading',parent=title,keepWithNext=True)
    centered=ParagraphStyle('HeadingCentered',parent=style,alignment=TA_CENTER,spaceBefore=5,spaceAfter=10)
    preamble_style=ParagraphStyle('Preamble',parent=style,leftIndent=18,firstLineIndent=0,alignment=TA_JUSTIFY)
    def para(text,sty=style):return Paragraph(escape(str(text)).replace('\n','<br/>'),sty)
    emblem=Image(str(Path(settings.BASE_DIR)/'static/reports/ethnoshmo.png'),width=38,height=38,hAlign='CENTER')
    first_header_line=source['header'].splitlines()[0] if source['header'] else ''
    header_width=min(doc.width,max(38,pdfmetrics.stringWidth(first_header_line,'ApprovalGreek',style.fontSize)))
    emblem_block=Table([[emblem]],colWidths=[header_width],hAlign='LEFT')
    emblem_block.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    decision_markup=escape(source['decision_text'])
    for value in [source['employee']['approval_subject'],source['employee']['speciality']]:
        if value:decision_markup=decision_markup.replace(escape(value),'<b>'+escape(value)+'</b>')
    flow=[emblem_block,Spacer(1,5),para(source['header'])]+([para('Αρ. πρωτ.: '+source['protocol_number']+' · '+source['protocol_date'])] if source['protocol_number'] or source['protocol_date'] else [])+[Spacer(1,10),para('ΑΠΟΦΑΣΗ ΕΓΚΡΙΣΗΣ ΜΕΤΑΚΙΝΗΣΗΣ',title),para(source['employee']['approval_subject'],title),para(source['signature_heading'],centered),para('Έχοντας υπόψη:')]
    for number,text in enumerate(source['preamble'],1):flow.append(para(str(number)+'. '+text['text'],preamble_style))
    flow.extend([para('ΑΠΟΦΑΣΙΖΟΥΜΕ',decision_heading),Paragraph(decision_markup,style),para('Η μετακίνηση αφορά: '+source['purpose'])])
    headings=['Αναχώρηση / επιστροφή','Έναρξη / λήξη εργασιών','Μέσο','Τόπος','Ημέρες εκτός έδρας','Διανυκτερεύσεις']
    values=[source['departure']+'\n'+source['return'],source['work_start']+'\n'+source['work_end'],source['transport'],source['destination'],str(source['away_days']),str(source['overnights'])]
    annual_rows=[('Αριθμός ημερών μετακίνησης και με την παρούσα έγκριση:',source['annual_used']),('Αριθμός ημερών που υπολείπονται:',source['annual_remaining']),('Ανώτατο όριο επιτρεπόμενων ημερών μετακίνησης έτους:',source['annual_limit'])]
    cell_style=ParagraphStyle('TableCentered',parent=style,alignment=TA_CENTER,spaceAfter=0)
    table_rows=[[para(x,cell_style) for x in headings],[para(x,cell_style) for x in values]]+[[para(label),'','','','',para(value,cell_style)] for label,value in annual_rows]
    table=Table(table_rows,colWidths=[87,87,75,100,80,82],repeatRows=1)
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,1),'MIDDLE'),('SPAN',(0,2),(4,2)),('SPAN',(0,3),(4,3)),('SPAN',(0,4),(4,4)),('GRID',(0,0),(-1,-1),.5,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf1f5')),('VALIGN',(0,0),(-1,-1),'TOP'),('VALIGN',(0,0),(-1,1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    flow.extend([table,Spacer(1,12),Paragraph('<b>Η προϋπολογιζόμενη δαπάνη</b> ποσού <b>'+escape(source['budget'])+'</b> ευρώ '+escape(source['budget_text']).replace('\n','<br/>'),style),Spacer(1,25)])
    signature_table=Table([[para('Εσωτερική Διανομή\nΧρονολογικό Αρχείο\n'+source['employee']['department']),para(source['signature_heading']+'\n\n'+source['signatory']['name']+'\n'+source['signatory']['speciality'])]],colWidths=[255,256])
    flow.append(signature_table)
    def footer(canvas,document):
        from reportlab.lib.utils import ImageReader
        canvas.saveState()
        logo_dir=Path(settings.BASE_DIR)/'static'/'reports'
        for name,x,max_width in [('europe.jpg',42,57),('espa-2021-2027.jpg',A4[0]-42-66,66)]:
            image=ImageReader(str(logo_dir/name))
            width,height=image.getSize()
            scale=min(max_width/width,40/height)
            canvas.drawImage(image,x,24,width=width*scale,height=height*scale,mask='auto')
        canvas.setFont('ApprovalGreek',6.5)
        canvas.drawString(42,14,'Ευρωπαϊκή Ένωση / ΕΤΠΑ')
        canvas.drawCentredString(A4[0]/2,42,'Ειδική Υπηρεσία Διαχείρισης')
        canvas.drawCentredString(A4[0]/2,32,'Προγράμματος "Κρήτη"')
        canvas.drawCentredString(A4[0]/2,22,'Δουκός Μποφώρ 7 – 71202 Ηράκλειο')
        canvas.drawRightString(A4[0]-42,10,'Σελίδα '+str(document.page))
        canvas.restoreState()
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


@transaction.atomic
def generate_approval(travel_id,user,signatory):
    from .views import visible_travels
    travel=visible_travels(user).select_for_update().filter(pk=travel_id).first()
    if not travel or not user.has_perm('core.print_travel'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    estimate=travel.calculations.filter(stage='estimate').order_by('-revision').first()
    if not estimate or estimate.algorithm_version!='estimate-3' or estimate.inputs.get('signature')!=signature(input_state(travel)):
        raise ValidationError('Απαιτείται ενημερωμένη εκτίμηση. Αποθηκεύστε ή υπολογίστε ξανά τη μετακίνηση.')
    parameters=ApplicationParameters.objects.filter(pk=1).first()
    if not parameters or parameters.allowedtravelsperyear is None:raise ValidationError('Συμπληρώστε το ετήσιο όριο ημερών στις παραμέτρους.')
    if not signatory.is_active:raise ValidationError('Επιλέξτε ενεργό υπογράφοντα.')
    heading=parameters.prosfonisiproistamenou.strip()
    if not heading:raise ValidationError('Συμπληρώστε την προσφώνηση προϊσταμένου στις παραμέτρους.')
    from .annual_days import annual_balance, counted_days
    balance=annual_balance(travel,parameters)
    prior_days=balance['prior_days']
    if not travel.purpose:raise ValidationError('Please fill in the travel purpose.')
    if not travel.employee.name_genitive:raise ValidationError('Συμπληρώστε το ονοματεπώνυμο εργαζομένου σε γενική.')
    historical=travel.departure_at<=date(2023,12,18)
    preamble_id,budget_id=(1,2) if historical else (11,12)
    preamble=list(ReportText.objects.filter(report__legacy_id=preamble_id).order_by('sort_order','pk').values('id','sort_order','text'))
    budget_rows=list(ReportText.objects.filter(report__legacy_id=budget_id).order_by('sort_order','pk').values('id','sort_order','text'))
    if not preamble or not any(x['text'].strip() for x in preamble) or not budget_rows or not any(x['text'].strip() for x in budget_rows):raise ValidationError('Λείπουν τα κείμενα προοιμίου ή προϋπολογισμού της απόφασης.')
    days=counted_days(travel,estimate,travel.departure_at.year)
    total_days=prior_days+days
    if total_days>parameters.allowedtravelsperyear:raise ValidationError('Η μετακίνηση υπερβαίνει το ετήσιο όριο ημερών.')
    employee=travel.employee
    if not employee.gender or not employee.gender.text1.strip():
        raise ValidationError('Συμπληρώστε το φύλο / γραμματική προσφώνηση του εργαζομένου πριν την εκτύπωση.')
    subject=employee.gender.text1.strip()+' '+employee.name_genitive.strip()
    parts=['Την έγκριση μετακίνησης '+subject]
    if employee.speciality: parts.append('κλάδου '+employee.speciality.name)
    if employee.position: parts.append(employee.position.name_genitive or employee.position.name)
    if employee.department: parts.append('της '+(employee.department.name_genitive or employee.department.name))
    if parameters.approval_service_genitive: parts.append(parameters.approval_service_genitive)
    decision=' '.join(parts)+', με δικαίωμα λήψης οδοιπορικών εξόδων και ημερήσιας αποζημίωσης.'
    fmt=lambda day:day.strftime('%d/%m/%Y') if day else ''
    source={'header':parameters.document_header,'protocol_number':travel.protocol_number,'protocol_date':fmt(travel.protocol_date),'purpose':travel.purpose,
      'decision_text':decision,'employee':{'approval_subject':subject,'gender_id':employee.gender_id,'gender_text1':employee.gender.text1,'id':employee.pk,'name':employee.display_name,'genitive':employee.name_genitive,'department':str(employee.department or ''),'speciality':str(employee.speciality or ''),'position':str(employee.position or '')},
      'preamble':preamble,'budget_rows':budget_rows,'budget_text':'\n'.join(x['text'] for x in budget_rows),'budget':greek_number(estimate.document_budget),
      'departure':fmt(travel.departure_at),'return':fmt(travel.return_at),'work_start':fmt(travel.work_starts_at),'work_end':fmt(travel.work_ends_at),
      'destination':travel.route.destination,'transport':travel.transport.name if travel.transport_configured and travel.transport_id else ', '.join(dict.fromkeys(e.transport.name for e in travel.expenses.select_related('transport').filter(is_cancelled=False) if e.transport)),
      'away_days':days,'overnights':travel.overnights.filter(is_excluded=False).count(),'annual_prior':prior_days,'annual_balance':balance,'annual_used':total_days,'annual_limit':parameters.allowedtravelsperyear,'annual_remaining':parameters.allowedtravelsperyear-total_days,
      'signatory':{'id':signatory.pk,'name':signatory.name,'speciality':signatory.speciality},'signature_heading':heading,'calculation_id':estimate.pk}
    data=render_pdf(source)
    return ApprovalDocument.objects.create(travel=travel,calculation=estimate,created_by=user,content=data,sha256=hashlib.sha256(data).hexdigest(),source=source)
