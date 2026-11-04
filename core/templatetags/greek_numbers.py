from django import template
from core.number_formats import greek_number
register=template.Library()
register.filter('greek_number',greek_number)
