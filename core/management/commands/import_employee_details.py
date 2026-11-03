from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from core.models import Employee
from legacy.models import Usr

FIELD_MAP = {'id_number': 'idno', 'tax_number': 'vatno', 'father_name': 'fathername', 'mother_name': 'mothername', 'birth_place': 'placeofbirth', 'birth_date': 'dateofbirth', 'phone': 'phone', 'city': 'city', 'address': 'address', 'address_number': 'addressnum', 'postal_code': 'zip', 'fax': 'fax', 'driving_license': 'drivinglicense', 'car_brand': 'carbrand', 'email': 'email', 'iban': 'iban', 'car_plate': 'carplate'}


class Command(BaseCommand):
    help='Fill blank employee declaration details from legacy USR. Existing web values are preserved.'

    def add_arguments(self,parser):
        parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        if connections['default'].settings_dict['NAME']!='TRAVEL_WEB_DEV':
            raise CommandError('Import is restricted to TRAVEL_WEB_DEV.')
        changed=0;field_count=0
        with transaction.atomic():
            for employee in Employee.objects.select_for_update().exclude(legacy_id=None):
                source=Usr.objects.filter(usr=employee.legacy_id,isemployee=1).values(*FIELD_MAP.values()).first()
                if source is None: continue
                values={}
                for target,legacy in FIELD_MAP.items():
                    current=getattr(employee,target)
                    value=source[legacy]
                    if current not in (None,'') or value in (None,''): continue
                    if isinstance(value,str): value=value.strip()
                    if value not in (None,''):values[target]=value
                if values:
                    Employee.objects.filter(pk=employee.pk).update(**values)
                    changed+=1;field_count+=len(values)
            if not options['apply']: transaction.set_rollback(True)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Preview'}: {changed} employees, {field_count} blank fields filled. No existing values overwritten.")
