from django.core.management.base import BaseCommand, CommandError
from django.db import transaction, connections
from core.models import Department, SettlementPeriod
from legacy.models import Department as OldDepartment, Period


class Command(BaseCommand):
    help='Fill missing department details and import legacy periods; no history is marked settled or closed.'

    def add_arguments(self,parser):parser.add_argument('--apply',action='store_true')

    def handle(self,*args,**options):
        if connections['default'].settings_dict['NAME']!='TRAVEL_WEB_DEV':raise CommandError('Restricted to TRAVEL_WEB_DEV.')
        departments=periods=skipped=0
        with transaction.atomic():
            for old in OldDepartment.objects.all():
                department=Department.objects.filter(legacy_id=old.pk).first()
                if department:
                    fields=[]
                    if not department.responsible and old.responsible:department.responsible=old.responsible;fields.append('responsible')
                    if department.sort_order==0 and old.sortorder is not None:department.sort_order=old.sortorder;fields.append('sort_order')
                    if fields:department.save(update_fields=fields);departments+=1
            for old in Period.objects.all():
                if not old.fromdate or not old.todate or old.todate<old.fromdate:skipped+=1;continue
                _,created=SettlementPeriod.objects.get_or_create(legacy_id=old.pk,defaults={'name':old.name or str(old.pk),'code':old.code or '', 'starts_on':old.fromdate,'ends_on':old.todate,'reference_number':old.aa or '', 'has_mtpy':old.hasmtpy==1,'has_geotee':old.hasgeotee==1,'is_active':old.isactive==1})
                periods+=created
            if not options['apply']:transaction.set_rollback(True)
        self.stdout.write(f"{'Applied' if options['apply'] else 'Preview'}: {departments} departments enriched; {periods} periods created; {skipped} periods skipped due to missing/invalid dates. No settlements or closure inferred.")
