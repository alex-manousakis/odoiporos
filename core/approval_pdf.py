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
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
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
    doc=SimpleDocTemplate(stream,pagesize=A4,rightMargin=42,leftMargin=42,topMargin=35,bottomMargin=55,title='ΑΠΟΦΑΣΗ ΕΓΚΡΙΣΗΣ ΜΕΤΑΚΙΝΗΣΗΣ',author=source['signatory']['name'])
    style=ParagraphStyle('Body',fontName='ApprovalGreek',fontSize=9,leading=12,spaceAfter=7)
    title=ParagraphStyle('Title',parent=style,fontName='ApprovalGreekBold',fontSize=12,leading=16,alignment=TA_CENTER,spaceAfter=12)
    def para(text,sty=style):return Paragraph(escape(str(text)).replace('\n','<br/>'),sty)
    flow=[para(source['header']),para('Αρ. πρωτ.: '+source['protocol_number']+' · '+source['protocol_date']),Spacer(1,10),para('ΑΠΟΦΑΣΗ ΕΓΚΡΙΣΗΣ ΜΕΤΑΚΙΝΗΣΗΣ',title),para(source['employee']['genitive'],title),para(source['signature_heading']),para('Έχοντας υπόψη:')]
    for number,text in enumerate(source['preamble'],1):flow.append(para(str(number)+'. '+text['text']))
    flow.extend([para('ΑΠΟΦΑΣΙΖΟΥΜΕ',title),para('Εγκρίνουμε τη μετακίνηση: '+source['employee']['name']+' · '+source['employee']['speciality']+' · '+source['employee']['position']+' · '+source['employee']['department']+', με δικαίωμα λήψης οδοιπορικών εξόδων και ημερήσιας αποζημίωσης.'),PageBreak(),para('Η μετακίνηση αφορά: '+source['purpose'])])
    headings=['Αναχώρηση / επιστροφή','Έναρξη / λήξη εργασιών','Μέσο','Τόπος','Ημέρες εκτός έδρας','Διανυκτερεύσεις']
    values=[source['departure']+' / '+source['return'],source['work_start']+' / '+source['work_end'],source['transport'],source['destination'],str(source['away_days']),str(source['overnights'])]
    table=Table([[para(x) for x in headings],[para(x) for x in values]],colWidths=[87,87,75,100,80,82],repeatRows=1)
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.grey),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf1f5')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    flow.extend([table,Spacer(1,18),para('Αριθμός ημερών μετακίνησης και με την παρούσα έγκριση: '+str(source['annual_used'])),para('Αριθμός ημερών που υπολείπονται: '+str(source['annual_remaining'])),para('Ανώτατο όριο επιτρεπόμενων ημερών μετακίνησης έτους: '+str(source['annual_limit'])),Spacer(1,12),para('Η προϋπολογιζόμενη δαπάνη ποσού '+source['budget']+' ευρώ '+source['budget_text']),Spacer(1,25)])
    signature_table=Table([[para('Εσωτερική Διανομή\nΧρονολογικό Αρχείο\n'+source['employee']['department']),para(source['signature_heading']+'\n\n'+source['signatory']['name']+'\n'+source['signatory']['speciality'])]],colWidths=[255,256])
    flow.append(signature_table)
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('ApprovalGreek',7)
        canvas.drawString(42,30,'Ειδική Υπηρεσία Διαχείρισης Προγράμματος "Κρήτη"')
        canvas.drawRightString(A4[0]-42,30,'Σελίδα '+str(document.page));canvas.restoreState()
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()


@transaction.atomic
def generate_approval(travel_id,user,signatory,heading,prior_days):
    from .views import visible_travels
    travel=visible_travels(user).select_for_update().filter(pk=travel_id).first()
    if not travel or not user.has_perm('core.print_travel'):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    estimate=travel.calculations.filter(stage='estimate').order_by('-revision').first()
    if not estimate or estimate.algorithm_version!='estimate-2' or estimate.inputs.get('signature')!=signature(input_state(travel)):
        raise ValidationError('Απαιτείται ενημερωμένη εκτίμηση. Αποθηκεύστε ή υπολογίστε ξανά τη μετακίνηση.')
    parameters=ApplicationParameters.objects.filter(pk=1).first()
    if not parameters or parameters.allowedtravelsperyear is None:raise ValidationError('Συμπληρώστε το ετήσιο όριο ημερών στις παραμέτρους.')
    if not travel.protocol_number or not travel.protocol_date or not travel.purpose:raise ValidationError('Συμπληρώστε αριθμό/ημερομηνία πρωτοκόλλου και σκοπό μετακίνησης.')
    if not travel.employee.name_genitive:raise ValidationError('Συμπληρώστε το ονοματεπώνυμο εργαζομένου σε γενική.')
    historical=travel.departure_at<=date(2023,12,18)
    preamble_id,budget_id=(1,2) if historical else (11,12)
    preamble=list(ReportText.objects.filter(report__legacy_id=preamble_id).order_by('sort_order','pk').values('id','sort_order','text'))
    budget_rows=list(ReportText.objects.filter(report__legacy_id=budget_id).order_by('sort_order','pk').values('id','sort_order','text'))
    if not preamble or not any(x['text'].strip() for x in preamble) or not budget_rows or not any(x['text'].strip() for x in budget_rows):raise ValidationError('Λείπουν τα κείμενα προοιμίου ή προϋπολογισμού της απόφασης.')
    days=int(estimate.inputs['days']) if travel.route.has_daily_allowance and travel.route.distance_km>parameters.homedistancelimit else 0
    total_days=prior_days+days
    if total_days>parameters.allowedtravelsperyear:raise ValidationError('Η μετακίνηση υπερβαίνει το ετήσιο όριο ημερών.')
    employee=travel.employee
    fmt=lambda day:day.strftime('%d/%m/%Y')
    source={'header':parameters.document_header,'protocol_number':travel.protocol_number,'protocol_date':fmt(travel.protocol_date),'purpose':travel.purpose,
      'employee':{'id':employee.pk,'name':employee.display_name,'genitive':employee.name_genitive,'department':str(employee.department or ''),'speciality':str(employee.speciality or ''),'position':str(employee.position or '')},
      'preamble':preamble,'budget_rows':budget_rows,'budget_text':'\n'.join(x['text'] for x in budget_rows),'budget':format(estimate.document_budget,'.2f').replace('.',','),
      'departure':fmt(travel.departure_at),'return':fmt(travel.return_at),'work_start':fmt(travel.work_starts_at),'work_end':fmt(travel.work_ends_at),
      'destination':travel.route.destination,'transport':', '.join(dict.fromkeys(e.transport.name for e in travel.expenses.select_related('transport').filter(is_cancelled=False) if e.transport)),
      'away_days':days,'overnights':travel.overnights.count(),'annual_prior':prior_days,'annual_used':total_days,'annual_limit':parameters.allowedtravelsperyear,'annual_remaining':parameters.allowedtravelsperyear-total_days,
      'signatory':{'id':signatory.pk,'name':signatory.name,'speciality':signatory.speciality},'signature_heading':heading,'calculation_id':estimate.pk}
    data=render_pdf(source)
    return ApprovalDocument.objects.create(travel=travel,calculation=estimate,created_by=user,content=data,sha256=hashlib.sha256(data).hexdigest(),source=source)
