from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER,TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,KeepTogether,Flowable
from .approval_pdf import fonts
from .report_branding import government_header
from .number_formats import greek_number

WIDTH=A4[0]-50

class SectionBookmark(Flowable):
    def __init__(self,key,title):
        Flowable.__init__(self);self.key=key;self.title=title;self.width=0;self.height=0
    def draw(self):
        self.canv.bookmarkPage(self.key);self.canv.addOutlineEntry(self.title,self.key,level=0)

def render_summary(source):
    fonts();stream=BytesIO()
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=25,rightMargin=25,topMargin=25,bottomMargin=30,title='ΣΥΝΟΠΤΙΚΗ ΚΑΤΑΣΤΑΣΗ ΔΑΠΑΝΩΝ ΚΑΙ ΚΡΑΤΗΣΕΩΝ',author=source['signatory']['name'])
    body=ParagraphStyle('SummaryBody',fontName='ApprovalGreek',fontSize=7.1,leading=8.8,spaceAfter=4)
    heading=ParagraphStyle('SummaryHeading',parent=body,fontName='ApprovalGreekBold',fontSize=8.5,leading=11,spaceBefore=6,spaceAfter=5,keepWithNext=True)
    title=ParagraphStyle('SummaryTitle',parent=heading,alignment=TA_CENTER,fontSize=10,leading=13,spaceAfter=7)
    header=ParagraphStyle('SummaryHeader',parent=body,fontName='ApprovalGreekBold',fontSize=6.2,leading=7.5,alignment=TA_CENTER,spaceAfter=0)
    cell=ParagraphStyle('SummaryCell',parent=body,spaceAfter=0)
    right=ParagraphStyle('SummaryRight',parent=cell,alignment=TA_RIGHT)
    bold=ParagraphStyle('SummaryBold',parent=cell,fontName='ApprovalGreekBold')
    bold_right=ParagraphStyle('SummaryBoldRight',parent=right,fontName='ApprovalGreekBold')
    center=ParagraphStyle('SummaryCenter',parent=body,alignment=TA_CENTER)
    def para(text,style=body):return Paragraph(escape(str(text or '')).replace('\n','<br/>'),style)
    def money(value):return greek_number(value)+' €'
    def percent(value):return greek_number(value).rstrip('0').rstrip(',')+'%' if value is not None else ''
    group_labels=['Α. Υπάλληλοι χωρίς κράτηση ΜΤΠΥ','Β. Υπάλληλοι με κράτηση ΜΤΠΥ'+(' '+percent(source['mtpy_rate']) if source['mtpy_rate'] is not None else '')]
    if not source['period']['has_mtpy']:group_labels[1]+=' (ανενεργή στην περίοδο)'
    adjustment=any(Decimal(row['adjustment']) for row in source['employees'])

    def report_header(key,text):
        period=source['period']
        period_label=period['name']
        if not all(date in period_label for date in (period['from'],period['to'])):
            period_label+='\n'+period['from']+' – '+period['to']
        period_style=ParagraphStyle('SummaryPeriod',parent=body,fontName='ApprovalGreekBold',fontSize=8.2,leading=10.2)
        info=[Spacer(1,33),para(source['place']+', '+source['print_date']),
            Paragraph('Α/Α: <b>'+escape(str(period['reference_number'] or '—'))+'</b>',body),
            Spacer(1,5),para(period_label,period_style)]
        table=Table([[government_header(source['header'],body),info]],colWidths=[WIDTH*.58,WIDTH*.42])
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        return [SectionBookmark(key,text),table,para(text,title),Spacer(1,5)]

    def table_style(table,total_rows):
        commands=[('BOX',(0,0),(-1,-1),.6,colors.black),('INNERGRID',(0,0),(-1,-1),.25,colors.HexColor('#c5cbd0')),('BACKGROUND',(0,0),(-1,0),colors.HexColor('#edf2f6')),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]
        for row in total_rows:commands.append(('BACKGROUND',(0,row),(-1,row),colors.HexColor('#edf2f6')))
        table.setStyle(TableStyle(commands));return table

    def employee_table(employees,totals,schedule=None,renumber=False):
        if schedule:
            cols=[('number','Α/Α',22),('name','ΟΝΟΜΑΤΕΠΩΝΥΜΟ',WIDTH*.57),('daily','ΗΜΕΡΗΣΙΑ ΑΠΟΖΗΜΙΩΣΗ',WIDTH*.22),(schedule,'ΜΤΠΥ' if schedule=='mtpy' else 'ΓΕΩΤΕΕ',WIDTH*.21-22)]
        else:
            cols=[('number','Α/Α',20),('name','ΟΝΟΜΑΤΕΠΩΝΥΜΟ',123),('expenses','ΕΞΟΔΑ ΜΕΤΑΚΙΝΗΣΗΣ',56),('daily','ΗΜΕΡΗΣΙΑ ΑΠΟΖΗΜΙΩΣΗ',56)]
            if adjustment:cols.append(('adjustment','ΛΟΓΙΣΤΙΚΕΣ ΠΡΟΣΑΡΜΟΓΕΣ',46))
            cols += [('gross','ΣΥΝΟΛΟ',56),('mtpy','ΜΤΠΥ',43),('geotee','ΓΕΩΤΕΕ',43),('taxes','ΣΥΝΟΛΟ ΚΡΑΤΗΣΕΩΝ',51),('net','ΠΛΗΡΩΤΕΟ',57)]
        scale=WIDTH/sum(width for _,_,width in cols)
        rows=[[para(label,header) for _,label,_ in cols]]
        for index,employee in enumerate(employees,1):
            row=[]
            for key,_,_ in cols:
                value=str(index if renumber else employee['number']) if key=='number' else employee['name'] if key=='name' else money(employee[key])
                row.append(para(value,bold if key=='name' else cell if key=='number' else right))
            rows.append(row)
        if not employees:
            rows.append([para('—',cell),para('Δεν υπάρχουν εργαζόμενοι στην κατηγορία.',cell)]+[para(money(0),right) for _ in cols[2:]])
        rows.append([para('',bold),para('ΣΥΝΟΛΑ',bold)]+[para(money(totals[key]),bold_right) for key,_,_ in cols[2:]])
        return table_style(Table(rows,colWidths=[w*scale for _,_,w in cols],repeatRows=1),[-1])

    def category_totals(schedule=None):
        keys=['daily',schedule] if schedule else ['expenses','daily']+(['adjustment'] if adjustment else [])+['gross','mtpy','geotee','taxes','net']
        labels={'expenses':'ΕΞΟΔΑ ΜΕΤΑΚΙΝΗΣΗΣ','daily':'ΗΜΕΡΗΣΙΑ ΑΠΟΖΗΜΙΩΣΗ','adjustment':'ΛΟΓ. ΠΡΟΣΑΡΜΟΓΕΣ','gross':'ΣΥΝΟΛΟ','mtpy':'ΜΤΠΥ','geotee':'ΓΕΩΤΕΕ','taxes':'ΣΥΝΟΛΟ ΚΡΑΤΗΣΕΩΝ','net':'ΚΑΘΑΡΟ ΠΟΣΟ'}
        left=WIDTH*.54 if schedule else WIDTH*.28
        widths=[left]+[(WIDTH-left)/len(keys)]*len(keys)
        rows=[[para('ΑΙΤΙΟΛΟΓΙΑ',header)]+[para(labels[key],header) for key in keys]]
        for index,group in enumerate(source['groups']):rows.append([para(group_labels[index],cell)]+[para(money(group['totals'][key]),right) for key in keys])
        rows.append([para('ΓΕΝΙΚΑ ΣΥΝΟΛΑ',bold)]+[para(money(source['totals'][key]),bold_right) for key in keys])
        return table_style(Table(rows,colWidths=widths,repeatRows=1),[-1])

    def signatures():
        signer=source['signatory']
        left=[para(signer['heading'],center),Spacer(1,34),para(signer['name']+'\n'+signer['speciality'],center)]
        right_block=[para('Ο εισηγητής για την εκκαθάριση',center),Spacer(1,34),para(source['rapporteur'],center)]
        table=Table([[left,right_block]],colWidths=[WIDTH/2,WIDTH/2])
        table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP')]))
        return KeepTogether([Spacer(1,12),table])

    flow=report_header('summary','ΣΥΝΟΠΤΙΚΗ ΚΑΤΑΣΤΑΣΗ ΔΑΠΑΝΩΝ ΚΑΙ ΚΡΑΤΗΣΕΩΝ')
    for index,group in enumerate(source['groups']):flow += [para(group_labels[index],heading),employee_table(group['employees'],group['totals']),Spacer(1,5)]
    flow += [Spacer(1,4),category_totals(),signatures(),PageBreak()]
    flow += report_header('mtpy','ΚΑΤΑΣΤΑΣΗ ΑΠΟΔΟΣΗΣ ΚΡΑΤΗΣΕΩΝ ΜΤΠΥ')
    if not source['period']['has_mtpy']:flow.append(para('Η κράτηση ΜΤΠΥ δεν εφαρμόζεται στην επιλεγμένη περίοδο.'))
    for index,group in enumerate(source['groups']):flow += [para(group_labels[index],heading),employee_table(group['employees'],group['totals'],schedule='mtpy'),Spacer(1,5)]
    flow += [Spacer(1,4),category_totals(schedule='mtpy'),signatures(),PageBreak()]
    flow += report_header('geotee','ΚΑΤΑΣΤΑΣΗ ΑΠΟΔΟΣΗΣ ΚΡΑΤΗΣΕΩΝ ΓΕΩΤΕΕ')
    if not source['period']['has_geotee']:flow.append(para('Η κράτηση ΓΕΩΤΕΕ δεν εφαρμόζεται στην επιλεγμένη περίοδο.'))
    flow += [para('Υπάλληλοι με κράτηση ΓΕΩΤΕΕ'+(' '+percent(source['geotee_rate']) if source['geotee_rate'] is not None else ''),heading),employee_table(source['geotee_employees'],source['geotee_totals'],schedule='geotee',renumber=True),signatures()]
    def footer(canvas,document):
        canvas.saveState();canvas.setFont('ApprovalGreek',6.5)
        canvas.drawString(25,16,source['period']['name']);canvas.drawRightString(A4[0]-25,16,'Σελίδα '+str(document.page));canvas.restoreState()
    doc.build(flow,onFirstPage=footer,onLaterPages=footer)
    return stream.getvalue()
