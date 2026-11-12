from pathlib import Path
from xml.sax.saxutils import escape
from django.conf import settings
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle
from .models import ApplicationParameters, Signatory

def default_report_signatory():
    params=ApplicationParameters.objects.select_related('organization_head').filter(pk=1).first()
    if params and params.organization_head_id:
        return params.organization_head if params.organization_head.is_active else None
    heads=list(Signatory.objects.filter(is_head=True,is_active=True)[:2])
    return heads[0] if len(heads)==1 else None

def government_header(text,style):
    first_line=next(iter(text.splitlines()),'')
    width=max(32,stringWidth(first_line,style.fontName,style.fontSize))
    emblem=Image(str(Path(settings.BASE_DIR)/'static/reports/ethnoshmo.png'),width=30,height=30,hAlign='CENTER')
    block=Table([[emblem]],colWidths=[width],hAlign='LEFT')
    block.setStyle(TableStyle([('ALIGN',(0,0),(-1,-1),'CENTER')]+[(name,(0,0),(-1,-1),0) for name in ('LEFTPADDING','RIGHTPADDING','TOPPADDING','BOTTOMPADDING')]))
    return [block,Spacer(1,3),Paragraph(escape(text).replace('\n','<br/>'),style)]
