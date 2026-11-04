from decimal import Decimal, InvalidOperation, localcontext
import re
from django import forms


def greek_number(value,places=2):
    if value is None or value=='':return ''
    try:
        number=Decimal(str(value))
        if not number.is_finite():return str(value)
        return format(number,f',.{int(places)}f').translate(str.maketrans({',':'.','.':','}))
    except (InvalidOperation,ValueError,TypeError):return value


class GreekNumberInput(forms.TextInput):
    def __init__(self,*args,decimal_places=2,**kwargs):
        super().__init__(*args,**kwargs)
        self.decimal_places=decimal_places
        self.attrs.update({'inputmode':'decimal','data-greek-number':'true'})
        self.attrs.pop('step',None)

    def format_value(self,value):
        # On an invalid bound form, retain the user's original input.
        if isinstance(value,str):
            if ',' in value:return value
            return greek_number(value,self.decimal_places)
        return greek_number(value,self.decimal_places)

    def value_from_datadict(self,data,files,name):
        value=super().value_from_datadict(data,files,name)
        if not isinstance(value,str):return value
        value=value.strip()
        if ',' in value:
            # Greek grouping must be valid; never silently reinterpret malformed input.
            if not re.fullmatch(r'[+-]?(?:\d+|\d{1,3}(?:\.\d{3})+),\d+',value):return value
            return value.replace('.','').replace(',','.')
        if re.fullmatch(r'[+-]?[1-9]\d{0,2}(?:\.\d{3})+',value):return value.replace('.','')
        return value


class GreekNumberFormMixin:
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        for field in self.fields.values():
            if isinstance(field,forms.DecimalField):
                field.localize=False
                field.widget=GreekNumberInput(attrs=field.widget.attrs.copy(),decimal_places=field.decimal_places or 2)
