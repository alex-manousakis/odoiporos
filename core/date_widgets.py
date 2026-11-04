from datetime import date, datetime
from django.forms import DateInput


class GreekDateInput(DateInput):
    """Explicit Greek display; normalize submitted dates for Django date fields."""
    input_type='text'

    def __init__(self,attrs=None,format=None):
        attrs={**(attrs or {}),'type':'text','placeholder':'dd/mm/yyyy','data-greek-date':'true','inputmode':'numeric','maxlength':'10'}
        super().__init__(attrs=attrs,format='%d/%m/%Y')

    def format_value(self,value):
        if isinstance(value,str):
            for fmt in ('%Y-%m-%d','%d/%m/%Y'):
                try:return datetime.strptime(value,fmt).strftime('%d/%m/%Y')
                except ValueError:pass
            return value
        return super().format_value(value)

    def value_from_datadict(self,data,files,name):
        value=super().value_from_datadict(data,files,name)
        if isinstance(value,str):
            try:return datetime.strptime(value.strip(),'%d/%m/%Y').strftime('%Y-%m-%d')
            except ValueError:pass
        return value
