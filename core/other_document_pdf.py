"""Layouts based on the user-supplied LOIPA_EGGRAFA.pdf (three report types)."""
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.utils import ImageReader
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, KeepTogether
from .approval_pdf import fonts

WIDTH=A4[0]-106
DECLARATION_NOTES=[
    '(1) Αναγράφεται από τον ενδιαφερόμενο πολίτη ή Αρχή ή η Υπηρεσία του δημόσιου τομέα, που απευθύνεται η αίτηση.',
    '(2) Αναγράφεται ολογράφως.',
    '(3) «Όποιος εν γνώσει του δηλώνει ψευδή γεγονότα ή αρνείται ή αποκρύπτει τα αληθινά με έγγραφη υπεύθυνη δήλωση του άρθρου 8 τιμωρείται με φυλάκιση τουλάχιστον τριών μηνών. Εάν ο υπαίτιος αυτών των πράξεων σκόπευε να προσπορίσει στον εαυτόν του ή σε άλλον περιουσιακό όφελος βλάπτοντας τρίτον ή σκόπευε να βλάψει άλλον, τιμωρείται με κάθειρξη μέχρι 10 ετών.»',
    '(4) Σε περίπτωση ανεπάρκειας χώρου η δήλωση συνεχίζεται στην πίσω όψη της και υπογράφεται από τον δηλούντα ή την δηλούσα.'
]
ACTIVITY_NOTES=[
    '(1) Εφόσον η μετακίνηση αφορά τη συμμετοχή σε συνέδριο, ημερίδα, ή εκπαίδευση επισυνάπτεται κατά περίπτωση αποδεικτικό εγγραφής, βεβαίωση συμμετοχής και πρόγραμμα.',
    '(2) Ο μετακινούμενος περιγράφει τις δραστηριότητες στις οποίες συμμετείχε κατά την μετακίνησή του (δεν απαιτείται όταν η μετακίνηση γίνεται για συμμετοχή σε συνέδριο και υπάρχει πρόγραμμα).'
]

def styles():
    body=ParagraphStyle('OtherBody',fontName='ApprovalGreek',fontSize=10,leading=15,spaceAfter=8)
    return {
        'body':body,
        'car':ParagraphStyle('CarBody',parent=body,alignment=TA_JUSTIFY,leading=25),
        'title':ParagraphStyle('OtherTitle',parent=body,fontName='ApprovalGreekBold',fontSize=13,leading=18,alignment=TA_CENTER,spaceAfter=16,keepWithNext=True),
        'center':ParagraphStyle('OtherCentered',parent=body,alignment=TA_CENTER),
        'small':ParagraphStyle('OtherSmall',parent=body,fontSize=8.5,leading=11,spaceAfter=5),
        'note':ParagraphStyle('OtherNote',parent=body,fontSize=6.8,leading=8.3,spaceAfter=0),
        'label':ParagraphStyle('OtherLabel',parent=body,fontSize=7.6,leading=9,spaceAfter=0),
        'value':ParagraphStyle('OtherValue',parent=body,fontName='ApprovalGreekBold',fontSize=8.1,leading=10,spaceAfter=0),
        'cell':ParagraphStyle('OtherCell',parent=body,fontSize=9.5,leading=12,spaceAfter=0),
    }

def para(text,style):
    return Paragraph(escape(str(text or '')).replace('\n','<br/>'),style)

def draw_notes(canvas,notes,style,x,y,width):
    block=para('\n'.join(notes),style)
    _,height=block.wrap(width,A4[1])
    block.drawOn(canvas,x,y)
    return height

def signature(data,sty,with_place=False):
    date=(''+data['place']+', ' if with_place and data['place'] else 'Ημερομηνία: ')+data['print_date']
    sig_style=sty['center'] if with_place else ParagraphStyle('DeclarationSignature',parent=sty['center'],fontSize=8.5,leading=11,spaceAfter=0)
    block=[para(date,sig_style),Spacer(1,30 if with_place else 12),para(data['declarant'],sig_style)]
    if not with_place:block += [Spacer(1,38),para('(Υπογραφή)',sig_style)]
    table=Table([['',block]],colWidths=[WIDTH*.62,WIDTH*.38])
    table.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
    return KeepTogether(table)

def car_layout(data,sty):
    flow=[para('ΥΠΕΥΘΥΝΗ ΔΗΛΩΣΗ',sty['title']),Spacer(1,24),
        Paragraph('<b>ΠΡΟΣ: Την '+escape(data['recipient'])+'</b>',sty['body']),Spacer(1,28),
        para(data['car_journey'],sty['car']),Spacer(1,24),para(data['car_vehicle'],sty['car'])]
    for label,value in [('Αριθμός Αδείας οδήγησης',data['driving_license']),('Χιλιόμετρα',data['distance']),('Κόστος',data['mileage'])]:
        flow.append(para(label+': '+value,sty['car']))
    flow.extend([Spacer(1,55),signature(data,sty,with_place=True)])
    return flow

def identity_table(data,sty):
    e=data['employee']
    specs=[
        [('ΠΡΟΣ(1):',70,False),(data['recipient'],WIDTH-70,True)],
        [('Ο – Η Όνομα:',70,False),(e.first_name,158,True),('Επώνυμο:',50,False),(e.last_name,WIDTH-278,True)],
        [('Όνομα και Επώνυμο Πατέρα:',130,False),(e.father_name,WIDTH-130,True)],
        [('Όνομα και Επώνυμο Μητέρας:',130,False),(e.mother_name,WIDTH-130,True)],
        [('Ημερομηνία γέννησης(2):',130,False),(data['birth_date'],WIDTH-130,True)],
        [('Τόπος Γέννησης:',130,False),(e.birth_place,WIDTH-130,True)],
        [('Αριθμός Δελτίου Ταυτότητας:',130,False),(e.id_number,150,True),('Τηλ:',30,False),(e.phone,WIDTH-310,True)],
        [('Τόπος Κατοικίας:',85,False),(e.city,110,True),('Οδός:',30,False),(e.address,105,True),('Αριθ:',25,False),(e.address_number,28,True),('ΤΚ:',20,False),(e.postal_code,WIDTH-403,True)],
        [('Αρ. Τηλεομοιοτύπου (Fax):',130,False),(e.fax,100,True),('Δ/νση Ηλεκτρ. Ταχυδρομείου (Email):',85,False),(e.email,WIDTH-315,True)],
    ]
    rows=[]
    for cells in specs:
        row=Table([[para(text,sty['value'] if bold else sty['label']) for text,_,bold in cells]],colWidths=[width for _,width,_ in cells],minRowHeights=[20])
        row.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),3),('RIGHTPADDING',(0,0),(-1,-1),3),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
        rows.append([row])
    result=Table(rows,colWidths=[WIDTH])
    result.setStyle(TableStyle([('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0),('TOPPADDING',(0,0),(-1,-1),0),('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    return result

def friends_layout(data,sty):
    emblem=Image(str(Path(settings.BASE_DIR)/'static/reports/ethnoshmo.png'),width=28,height=28,hAlign='CENTER')
    notice=para('Η ακρίβεια των στοιχείων που υποβάλλονται με αυτή τη δήλωση μπορεί να ελεγχθεί με βάση το αρχείο άλλων υπηρεσιών (άρθρο 8 παρ. 4 Ν. 1599/1986)',ParagraphStyle('DeclarationNotice',parent=sty['note'],fontSize=8,leading=9.5,alignment=TA_CENTER))
    box=Table([[notice]],colWidths=[WIDTH]);box.setStyle(TableStyle([('BOX',(0,0),(-1,-1),.5,colors.black),('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5)]))
    return [emblem,Spacer(1,5),para('ΥΠΕΥΘΥΝΗ ΔΗΛΩΣΗ',sty['title']),para('(άρθρο 8 Ν.1599/1986)',sty['center']),Spacer(1,10),box,Spacer(1,10),identity_table(data,sty),Spacer(1,13),
        para('Με ατομική μου ευθύνη και γνωρίζοντας τις κυρώσεις (3), που προβλέπονται από τις διατάξεις της παρ. 6 του άρθρου 22 του Ν. 1599/1986, δηλώνω ότι:',sty['small']),Spacer(1,6),para(data['friends_body'],sty['small']),para('(4)',ParagraphStyle('DeclarationContinued',parent=sty['small'],alignment=TA_RIGHT,fontSize=7)),Spacer(1,18),signature(data,sty)]

def activity_layout(data,sty):
    rows=[]
    for number,label,value in [
        ('1.','Αρ. πρωτ. Απόφασης Μετακίνησης:',data['protocol']),
        ('2.','Τόπος Μετακίνησης:',data['destination']),
        ('3.','Ημερομηνίες Μετακίνησης:',data['departure']+' - '+data['return']),
        ('4.','Ημερομηνία Εργασιών:',data['work_dates']),
        ('5.','Ονοματεπώνυμο Μετακινούμενου:',data['employee'].display_name),
        ('6.','Σκοπός Μετακίνησης(1):',data['purpose']),
        ('7.','Περιγραφή πεπραγμένων (2):',data['actions']),
    ]:rows.append([para(number,sty['cell']),para(label,sty['cell']),para(value,sty['cell'])])
    table=Table(rows,colWidths=[17,153,WIDTH-170],minRowHeights=[28]*len(rows),splitByRow=1,splitInRow=1)
    table.setStyle(TableStyle([('GRID',(0,0),(-1,-1),.5,colors.black),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('LEFTPADDING',(0,0),(-1,-1),4),('RIGHTPADDING',(0,0),(-1,-1),4),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    return [para('ΑΝΑΦΟΡΑ ΠΕΠΡΑΓΜΕΝΩΝ ΜΕΤΑΚΙΝΗΣΗΣ',sty['title']),table,Spacer(1,24),KeepTogether([
        para('8. Υπογραφή Μετακινούμενου: __________________________________________',sty['body']),Spacer(1,5),para('9. Ημερομηνία: '+data['print_date'],sty['body'])])]

def activity_footer(canvas,data,sty):
    canvas.setStrokeColor(colors.black);canvas.setLineWidth(.5)
    height=draw_notes(canvas,ACTIVITY_NOTES,sty['note'],53,106,WIDTH)
    canvas.line(53,110+height,230,110+height)
    left,bottom,width,height=31,30,A4[0]-62,65
    canvas.rect(left,bottom,width,height);canvas.line(left+96,bottom,left+96,bottom+height);canvas.line(left+width-96,bottom,left+width-96,bottom+height)
    directory=Path(settings.BASE_DIR)/'static/reports'
    for name,x,limit in [('europe.jpg',left+22,53),('espa-2021-2027.jpg',left+width-86,76)]:
        reader=ImageReader(str(directory/name));w,h=reader.getSize();scale=min(limit/w,42/h)
        canvas.drawImage(reader,x,bottom+20,width=w*scale,height=h*scale,mask='auto')
    canvas.setFont('ApprovalGreek',6)
    canvas.drawCentredString(left+48,bottom+10,'Ευρωπαϊκή Ένωση');canvas.drawCentredString(left+48,bottom+3,'ΕΤΠΑ')
    center=para(data['recipient']+'\n'+data['address'],ParagraphStyle('ActivityFooterCentered',parent=sty['note'],alignment=TA_CENTER,fontSize=7.4,leading=10));_,h=center.wrap(width-210,55)
    center.drawOn(canvas,left+106,bottom+(height-h)/2)

def render_document(data):
    fonts();sty=styles();stream=BytesIO();kind=data['kind']
    doc=SimpleDocTemplate(stream,pagesize=A4,leftMargin=53,rightMargin=53,
        topMargin=65 if kind=='car' else 56 if kind=='activity' else 48,bottomMargin=185 if kind=='activity' else 205 if kind=='friends' else 55,
        title='ΑΝΑΦΟΡΑ ΠΕΠΡΑΓΜΕΝΩΝ ΜΕΤΑΚΙΝΗΣΗΣ' if kind=='activity' else 'ΥΠΕΥΘΥΝΗ ΔΗΛΩΣΗ',author=data['employee'].display_name)
    def page(canvas,document):
        canvas.saveState()
        if kind=='friends':
            canvas.setLineWidth(.6);canvas.rect(31,74,A4[0]-62,A4[1]-79)
            draw_notes(canvas,DECLARATION_NOTES,ParagraphStyle('DeclarationNotes',parent=sty['note'],fontSize=8.5,leading=10.5),53,105,WIDTH)
        elif kind=='activity':activity_footer(canvas,data,sty)
        canvas.restoreState()
    flow={'car':car_layout,'friends':friends_layout,'activity':activity_layout}[kind](data,sty)
    doc.build(flow,onFirstPage=page,onLaterPages=page)
    return stream.getvalue()
