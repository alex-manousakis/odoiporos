from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from core.models import ReportDefinition, ReportText
from legacy.models import Reportname, Reportscript


class Command(BaseCommand):
    help='Import legacy report groups and ordered texts. Existing legacy IDs are never overwritten.'

    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        if connections['default'].settings_dict['NAME']!='TRAVEL_WEB_DEV':raise CommandError('Restricted to TRAVEL_WEB_DEV.')
        definitions=texts=0
        with transaction.atomic():
            for source in Reportname.objects.all():
                _,created=ReportDefinition.objects.get_or_create(legacy_id=source.pk,defaults={'name':source.name or str(source.pk)})
                definitions+=created
            for source in Reportscript.objects.all():
                report=ReportDefinition.objects.filter(legacy_id=source.reportname).first()
                if report is None:raise CommandError(f'Missing report group for legacy script {source.pk}. Import rolled back.')
                _,created=ReportText.objects.get_or_create(legacy_id=source.pk,defaults={'report':report,'sort_order':source.sortorder,'text':source.text or ''})
                texts+=created
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Preview'}: {definitions} report groups, {texts} text rows. Existing web values preserved.")
