from datetime import date, datetime
from django import template
register=template.Library()


@register.filter
def greek_date(value):
    if not value:return ''
    if isinstance(value,(date,datetime)):return value.strftime('%d/%m/%Y')
    try:return date.fromisoformat(str(value)).strftime('%d/%m/%Y')
    except (TypeError,ValueError):return value
