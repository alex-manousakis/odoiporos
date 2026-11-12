from io import BytesIO
from decimal import Decimal
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER,TA_RIGHT
from reportlab.lib.pagesizes import A4,landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,PageBreak
from .approval_pdf import fonts
from .number_formats import greek_number

def render_employee_cards(source):
    fonts();stream=BytesIO();page_width,page_height=landscape(A4);width=page_width-42
    doc=SimpleDocTemplate(stream,pagesize=landscape(A4),leftMargin=21,rightMargin=21,topMargin=61,bottomMargin=32,
        title='Καρτέλα Εργαζομένου',author='Οδοιπόρος')
    cell=ParagraphStyle('CardCell',fontName='ApprovalGreek',fontSize=7.1,leading=8.8,spaceAfter=0)
    right=ParagraphStyle('CardNumber',parent=cell,alignment=TA_RIGHT)
    center=ParagraphStyle('CardCenter',parent=cell,alignment=TA_CENTER)
    header=ParagraphStyle('CardHeader',parent=center,fontName='ApprovalGreekBold',fontSize=6.6,leading=8.2)
    name=ParagraphStyle('CardName',parent=cell,fontName='ApprovalGreekBold',fontSize=9,leading=12)
    bold=ParagraphStyle('CardTotal',parent=right,fontName='ApprovalGreekBold')
    def para(text,style=cell):return Paragraph(escape(str(text or '')).replace('\n','<br/>'),style)
    def num(value,places=2):return greek_number(value,places)
    columns=[('origin','ΑΠΟ',67),('destination','ΠΡΟΣ',82),('dates','ΑΝΑΧΩΡΗΣΗ – ΕΠΙΣΤΡΟΦΗ',111),('work','ΕΝΑΡΞΗ – ΛΗΞΗ ΕΡΓΑΣΙΩΝ',111),
        ('days','ΕΝΤΟΣ / ΕΚΤΟΣ / ΕΞΩΤ.',47),('factor','ΣΥΝΤ.',35),('daily','ΗΜΕΡ. ΑΠΟΖ.',60),('nights','ΔΙΑΝΥΚΤ.',42),
        ('hotel','ΚΟΣΤΟΣ ΔΙΑΝ.',62),('transport','ΚΟΣΤΟΣ ΜΕΤΑΚΙΝΗΣΗΣ',69),('total','ΣΥΝΟΛΙΚΟ ΚΟΣΤΟΣ',69)]
    widths=[w*width/sum(c[2] for c in columns) for _,_,w in columns]
    flow=[]
    for index,card in enumerate(source['cards']):
        if index:flow.append(PageBreak())
        rows=[[para(card['name'],name)]+['']*(len(columns)-1),[para(label,header) for _,label,_ in columns]]
        for row in card['rows']:
            values=[]
            for key,_,_ in columns:
                if key=='dates':value=row['from']+' – '+row['to']
                elif key=='work':value=row['work_from']+' – '+row['work_to']
                elif key=='days':value='/'.join(num(row[k],0) for k in ('near_days','domestic_days','abroad_days'))
                elif key in ('origin','destination'):value=row[key]
                elif key=='nights':value=num(row[key],0)
                else:value=num(row[key])
                values.append(para(value,cell if key in ('origin','destination') else center if key in ('dates','work','days') else right))
            rows.append(values)
        commands=[('SPAN',(0,0),(-1,0)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),('BACKGROUND',(0,1),(-1,1),colors.HexColor('#edf2f6')),
            ('LINEBELOW',(0,1),(-1,1),.6,colors.black),('LINEBELOW',(0,2),(-1,-1),.25,colors.HexColor('#d7dde2'))]
        if not card['rows']:
            rows.append([para('Δεν υπάρχουν μετακινήσεις στο επιλεγμένο διάστημα.')]+['']*(len(columns)-1))
            commands.append(('SPAN',(0,2),(-1,2)))
        totals=card['totals']
        rows.append([para('ΣΥΝΟΛΑ',name),'','','',para('/'.join(num(totals[k],0) for k in ('near_days','domestic_days','abroad_days')),header)]+
            [para(num(totals[key],0 if key=='nights' else 2),bold) for key in ('factor','daily','nights','hotel','transport','total')])
        commands += [('SPAN',(0,-1),(3,-1)),('LINEABOVE',(0,-1),(-1,-1),.7,colors.black),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#edf2f6'))]
        table=Table(rows,colWidths=widths,repeatRows=2,splitByRow=1,splitInRow=1)
        table.setStyle(TableStyle(commands));flow.append(table)
    def page_header(canvas,document):
        canvas.saveState();canvas.setFont('ApprovalGreekBold',12)
        canvas.drawCentredString(page_width/2,page_height-25,'Καρτέλα Εργαζομένου')
        canvas.setFont('ApprovalGreek',8)
        canvas.drawCentredString(page_width/2,page_height-41,'Από '+source['from']+' έως '+source['to'])
        canvas.setFont('ApprovalGreek',7)
        canvas.drawString(21,17,source['print_date']);canvas.drawRightString(page_width-21,17,'Σελίδα: '+str(document.page));canvas.restoreState()
    doc.build(flow,onFirstPage=page_header,onLaterPages=page_header)
    return stream.getvalue()
