from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from core.models import Gender, Employee
from legacy.models import Gender as LegacyGender, Usr


class Command(BaseCommand):
    help='Import legacy GENDER and fill blank employee links; existing web data is preserved.'

    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        if connections['default'].settings_dict['NAME']!='TRAVEL_WEB_DEV':raise CommandError('Restricted to TRAVEL_WEB_DEV.')
        imported=linked=0
        with transaction.atomic():
            for row in LegacyGender.objects.all():
                _,created=Gender.objects.get_or_create(legacy_id=row.pk,defaults={'name':row.name or str(row.pk),'text1':row.text1 or '','text2':row.text2 or '','text3':row.text3 or ''})
                imported+=created
            for employee in Employee.objects.select_for_update().filter(gender__isnull=True).exclude(legacy_id=None):
                source=Usr.objects.filter(pk=employee.legacy_id,isemployee=1).values('gender_id').first()
                if source and source['gender_id']:
                    gender=Gender.objects.filter(legacy_id=source['gender_id']).first()
                    if gender is None:raise CommandError('Missing gender reference; import rolled back.')
                    employee.gender=gender;employee.save(update_fields=['gender']);linked+=1
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Preview'}: {imported} gender records, {linked} employee links.")
