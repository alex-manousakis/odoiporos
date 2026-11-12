from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER,TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether
from .approval_pdf import fonts
from .report_branding import government_header
from .number_formats import greek_number

WIDTH=A4[0]-50

class StatementTable(Table):
    def split(self,available_width,available_height):
        parts=super().split(available_width,available_height)
        def has_content(value):
            if isinstance(value,(tuple,list)):return any(has_content(item) for item in value)
            return bool(str(getattr(value,'text',value) or '').strip())
        # ReportLab can split a row into an empty fragment when only its repeated
        # header and padding fit. Move it to the next page instead of orphaning it.
        if len(parts)>1:
            first=parts[0]
            repeated=first.repeatRows if isinstance(first.repeatRows,int) else len(first.repeatRows)
            if first._cellvalues[repeated:] and not any(has_content(cell) for row in first._cellvalues[repeated:] for cell in row):return []
        return parts


def render_statement(source):
    fonts();stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=25,rightMargin=25,topMargin=25,bottomMargin=35,title='ΑΝΑΛΥΤΙΚΗ ΚΑΤΑΣΤΑΣΗ ΟΔΟΙΠΟΡΙΚΩΝ',author=source['employee']['name'])
    body=ParagraphStyle('StatementBody',fontName='ApprovalGreek',fontSize=8,leading=10.5,spaceAfter=6)
    title=ParagraphStyle('StatementTitle',parent=body,fontName='ApprovalGreekBold',fontSize=9,leading=12,alignment=TA_CENTER,spaceAfter=9)
    cell=ParagraphStyle('StatementCell',parent=body,fontSize=7.8,leading=9.5,spaceAfter=0)
    header=ParagraphStyle('StatementHeader',parent=cell,fontName='ApprovalGreekBold',fontSize=6.4,leading=8,alignment=TA_CENTER)
    numeric=ParagraphStyle('StatementNumeric',parent=cell,alignment=TA_RIGHT,fontSize=7.2)
    summary_style=ParagraphStyle('StatementSummary',parent=body,fontSize=9,leading=13,spaceAfter=0)
    center=ParagraphStyle('StatementCentered',parent=body,alignment=TA_CENTER)
    def para(value,style=body):return Paragraph(escape(str(value or '')).replace('\n','<br/>'),style)
    period=source['period'];employee=source['employee'];totals=source['totals']
    heading=Table([[government_header(source['header'],body),para('ΟΙΚΟΝΟΜΙΚΟ ΕΤΟΣ: '+str(period['year'])+'\nΔΙΑΣΤΗΜΑ: '+period['name']+'\n'+period['from']+' – '+period['to']+'\nΕΔΡΑ: '+source['place'])]],colWidths=[WIDTH*.63,WIDTH*.37])
    heading.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    flow=[heading,Spacer(1,9),para('ΚΑΤΑΣΤΑΣΗ ΠΛΗΡΩΜΗΣ ΔΑΠΑΝΗΣ ΟΔΟΙΠΟΡΙΚΩΝ ΚΑΙ ΗΜΕΡΗΣΙΑΣ ΑΠΟΖΗΜΙΩΣΗΣ',title),para('(ΗΜΕΡΟΛΟΓΙΑΚΗ ΚΑΤΑΣΤΑΣΗ)',center),para('του αναφερόμενου υπαλλήλου, για μετάβαση και εκτέλεση υπηρεσίας εντός και εκτός έδρας, στο Εσωτερικό και Εξωτερικό',center)]
    identity=employee['name']
    if employee['speciality']:identity+=', κλάδου '+employee['speciality']
    if employee['position']:identity+=', '+employee['position']
    if employee['department']:identity+=' της '+employee['department']
    if source['service']:identity+=' '+source['service']
    identity_markup='<b>'+escape(employee['name'])+'</b>'+escape(identity[len(employee['name']):])
    bank_markup='ΑΦΜ: <b>'+escape(employee['tax_number'])+'</b>    Λογαρ. Τράπεζας (IBAN): <b>'+escape(employee['iban'])+'</b>'
    flow += [Spacer(1,8),Paragraph(identity_markup,body),Paragraph(bank_markup,body),Spacer(1,8)]
    columns=[('dates','ΗΜΕΡ/ΝΙΕΣ ΜΕΤ/ΣΗΣ',49),('route','ΤΟΠΟΣ / ΜΕΣΟ ΜΕΤ/ΣΗΣ',56),('purpose','ΑΙΤΙΟΛΟΓΙΑ',94),
        ('near_days','ΗΜΕΡΕΣ ΕΝΤΟΣ ΕΔΡΑΣ ΕΣ/ΚΟΥ',32),('domestic_days','ΗΜΕΡΕΣ ΕΚΤΟΣ ΕΔΡΑΣ ΕΣ/ΚΟΥ',32),('domestic_factor','ΣΥΝ/ΤΗΣ ΗΜ/ΣΙΑΣ ΑΠ/ΣΗΣ ΕΣ/ΚΟΥ',31),
        ('abroad_days','ΗΜΕΡΕΣ ΕΚΤΟΣ ΕΔΡΑΣ ΕΞ/ΚΟΥ',32),('abroad_factor','ΣΥΝ/ΤΗΣ ΗΜ/ΣΙΑΣ ΑΠ/ΣΗΣ ΕΞ/ΚΟΥ',31),('tickets','ΑΞΙΑ ΕΙΣ/ΙΩΝ',37),
        ('distance','ΧΛΜ',30),('mileage','ΧΛΜ ΑΠΟΖ/ΣΗ',37),('hotel','ΕΞΟΔΑ ΔΙΑΝ/ΣΗΣ',39),('other','ΕΞΟΔΑ ΔΙΑΦΟΡΑ (ΜΕΤΡΟ, ΤΑΞΙ, ΚΛΠ)',37)]
    scale=WIDTH/sum(c[2] for c in columns)
    widths=[width*scale for _,_,width in columns]
    rows=[[para(label,header) for _,label,_ in columns]]
    for row in source['rows']:
        # Split unusually long reasons into bounded continuation rows. This keeps
        # all text while avoiding oversized table cells and duplicated amounts.
        pending=[para(row['purpose'],cell)];fragments=[]
        while pending:
            paragraph=pending.pop(0)
            _,height=paragraph.wrap(widths[2]-4,100000)
            if height<=260:
                fragments.append(paragraph)
            else:
                split=paragraph.split(widths[2]-4,260)
                if not split:raise ValueError('Unable to split trip purpose for statement layout.')
                fragments.append(split[0]);pending=split[1:]+pending
        for part,fragment in enumerate(fragments):
            values=[]
            for key,_,_ in columns:
                if key=='purpose':
                    values.append(fragment);continue
                if part:
                    value='(συνέχεια)' if key=='dates' else ''
                elif key=='dates':value=row['from']+' –\n'+row['to']
                elif key=='route':value=row['route']+' / '+row['transport']
                else:value=greek_number(row[key],0 if key in ('near_days','domestic_days','abroad_days') else 2)
                values.append(para(value,cell if key in ('dates','route') else numeric))
            rows.append(values)
    rows.append([para('ΓΕΝΙΚΑ ΣΥΝΟΛΑ',header),'','']+[para(greek_number(totals[key],0 if key in ('near_days','domestic_days','abroad_days') else 2),numeric) for key,_,_ in columns[3:]])
    table=StatementTable(rows,colWidths=widths,repeatRows=1,splitByRow=1,splitInRow=0)
    table.setStyle(TableStyle([('LINEBEFORE',(1,0),(-1,-1),.3,colors.HexColor('#c5cbd0')),('BOX',(0,0),(-1,-1),.6,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2f6')),('LINEBELOW',(0,0),(-1,0),.5,colors.black),('LINEBELOW',(0,1),(-1,-2),.3,colors.HexColor('#c5cbd0')),('SPAN',(0,-1),(2,-1)),('LINEABOVE',(0,-1),(-1,-1),.7,colors.black),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#edf2f6')),('LEFTPADDING',(0,0),(-1,-1),2),('RIGHTPADDING',(0,0),(-1,-1),2),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    flow += [table,PageBreak()]
    summaries=[
        ('1. ΣΥΝ/ΣΤΗΣ ΗΜΕΡΗΣΙΑΣ ΑΠΟΖ/ΣΗΣ ΕΣΩΤΕΡΙΚΟΥ',totals['domestic_factor'],totals['daily_domestic']),
        ('2. ΣΥΝ/ΣΤΗΣ ΗΜΕΡΗΣΙΑΣ ΑΠΟΖ/ΣΗΣ ΕΞΩΤΕΡΙΚΟΥ',totals['abroad_factor'],totals['daily_abroad']),
        ('3. ΗΜΕΡΗΣΙΑ ΑΠΟΖ.',None,source['daily']),('4. ΕΞΟΔΑ ΜΕΤΑΚΙΝΗΣΗΣ',None,source['expenses'])]
    if Decimal(source['adjustment']):summaries.append(('ΛΟΙΠΕΣ ΛΟΓΙΣΤΙΚΕΣ ΠΡΟΣΑΡΜΟΓΕΣ',None,source['adjustment']))
    summaries += [('ΣΥΝΟΛΟ',None,totals['total']),('ΜΤΠΥ',None,source['deductions']['mtpy']['amount']),('ΓΕΩΤΕΕ',None,source['deductions']['geotee']['amount']),('ΣΥΝΟΛΟ ΚΡΑΤΗΣΕΩΝ',None,source['taxes']),('ΚΑΘΑΡΟ ΠΛΗΡΩΤΕΟ ΠΟΣΟ ΔΙΚΑΙΟΥΧΟΥ',None,source['net'])]
    summary=Table([[para(label,summary_style),para(greek_number(factor) if factor is not None else '',summary_style),para(greek_number(amount),ParagraphStyle('StatementSumRight',parent=summary_style,alignment=TA_RIGHT))] for label,factor,amount in summaries],colWidths=[WIDTH*.68,WIDTH*.12,WIDTH*.2])
    summary.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.6,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LINEBELOW',(0,0),(-1,-1),.3,colors.HexColor('#c5cbd0')),('TOPPADDING',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),9),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#edf2f6'))]))
    day_totals=Table([
        [para('ΣΥΝΟΛΟ ΗΜ. ΕΝΤΟΣ ΕΔΡΑΣ ΕΣΩΤΕΡΙΚΟΥ:',summary_style),para(greek_number(totals['near_days'],0),center)],
        [para('ΣΥΝΟΛΟ ΗΜ. ΕΚΤΟΣ ΕΔΡΑΣ ΕΣΩΤ./ΕΞΩΤ.:',summary_style),para(greek_number(Decimal(totals['domestic_days'])+Decimal(totals['abroad_days']),0),center)],
    ],colWidths=[WIDTH*.85,WIDTH*.15])
    day_totals.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.6,colors.black),('INNERGRID',(0,0),(-1,-1),.3,colors.HexColor('#c5cbd0')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7)]))
    flow += [para('ΣΥΓΚΕΝΤΡΩΤΙΚΑ ΠΟΣΑ ΚΑΙ ΚΡΑΤΗΣΕΙΣ',title),summary,Spacer(1,16),day_totals]
    signature=source['signatory']
    left=[para('Η ως άνω μετακίνηση έγινε σύμφωνα με την υποπαράγραφο Δ9 της παραγράφου Δ του άρθρου 2 του Ν. 4336/2015 (94 Α΄).'),Spacer(1,12),para('ΘΕΩΡΗΘΗΚΕ\nΗ ΠΡΑΓΜΑΤΟΠΟΙΗΣΗ ΤΩΝ ΜΕΤΑΚΙΝΗΣΕΩΝ\nΚΑΘΩΣ ΚΑΙ Η ΑΚΡΙΒΕΙΑ ΤΩΝ\nΧΙΛΙΟΜΕΤΡΙΚΩΝ ΑΠΟΣΤΑΣΕΩΝ ΤΟΥ\nΜΕΤΑΚΙΝΟΥΜΕΝΟΥ ΥΠΑΛΛΗΛΟΥ',center),Spacer(1,18),para(signature['heading'],center),Spacer(1,50),para(signature['name']+'\n'+signature['speciality'],center)]
    right=[para(source['place']+', '+source['print_date'],center),Spacer(1,95),para('Δικαιούχος',center),Spacer(1,65),para(employee['name'],center)]
    signatures=Table([[left,right]],colWidths=[WIDTH/2,WIDTH/2])
    signatures.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3)]))
    flow += [Spacer(1,12),KeepTogether([signatures])]
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('ApprovalGreek',6.5)
        canvas.drawString(25,17,employee['name']+' · '+period['name'])
        canvas.drawRightString(A4[0]-25,17,'Σελίδα '+str(document.page));canvas.restoreState()
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
