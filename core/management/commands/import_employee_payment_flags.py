from django.core.management.base import BaseCommand,CommandError
from django.db import connections,transaction
from core.models import Employee
from legacy.models import Usr

class Command(BaseCommand):
    help='Fill unknown employee deduction flags from legacy USR; never overwrite configured values.'
    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')
    def handle(self,*args,**options):
        if connections['default'].settings_dict['NAME']!='TRAVEL_WEB_DEV':raise CommandError('Import is restricted to TRAVEL_WEB_DEV.')
        changed=0
        with transaction.atomic():
            for employee in Employee.objects.select_for_update().exclude(legacy_id=None):
                source=Usr.objects.filter(usr=employee.legacy_id,isemployee=1).values('hasmtpy','hasgeotee').first()
                if source is None:continue
                fields=[]
                for target,legacy in [('has_mtpy','hasmtpy'),('has_geotee','hasgeotee')]:
                    if getattr(employee,target) is None and source[legacy] in (0,1):
                        setattr(employee,target,bool(source[legacy]));fields.append(target)
                if fields:employee.save(update_fields=fields);changed+=1
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Preview'}: {changed} employees. Configured web values preserved.")
