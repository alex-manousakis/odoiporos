import json
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connections, transaction
from core import models as m


def decimal(value, places=2):
    if value is None:
        raise ValueError("Missing numeric value")
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_EVEN)


class Command(BaseCommand):
    help = "Import reference data only. Default is dry-run; existing legacy IDs are never overwritten."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true')
        parser.add_argument('--category-as-of', required=True, type=date.fromisoformat)

    def handle(self, *args, **options):
        if connections['default'].settings_dict['NAME'] != 'TRAVEL_WEB_DEV':
            raise CommandError('Import is restricted to TRAVEL_WEB_DEV.')
        report = {'mode': 'apply' if options['apply'] else 'dry-run', 'created': {}, 'existing': {}, 'issues': [], 'category_as_of': str(options['category_as_of'])}

        def rows(table):
            # Fixed internal table names only; deliberately excludes login/password fields.
            query = ('SELECT USR,CODE,FIRSTNAME,LASTNAME,NAME,NAMEGENIKI,DEPARTMENT,CATEGORY,SPECIALITY,POSITION,EMAIL,IBAN,CARPLATE,ISACTIVE FROM USR WHERE ISEMPLOYEE=1'
                     if table == 'USR' else f'SELECT * FROM [{table}]')
            with connections['travel'].cursor() as c:
                c.execute(query)
                names = [col[0].upper() for col in c.description]
                return [dict(zip(names, row)) for row in c.fetchall()]

        def save(model, old_id, values):
            obj = model.objects.filter(legacy_id=old_id).first()
            key = model.__name__
            if obj:
                report['existing'][key] = report['existing'].get(key, 0) + 1
                return obj, False
            obj = model(legacy_id=old_id, **values)
            obj.full_clean()
            obj.save()
            report['created'][key] = report['created'].get(key, 0) + 1
            return obj, True

        def ref(model, value):
            if value is None:
                return None
            return model.objects.get(legacy_id=value)

        def process(table, callback):
            for row in rows(table):
                try:
                    with transaction.atomic():
                        callback(row)
                except Exception as exc:
                    # No raw exception values: they may contain employee details.
                    report['issues'].append({'table': table, 'legacy_id': row.get(table), 'error_type': type(exc).__name__})

        with transaction.atomic():
            for table, model in [('CATEGORY',m.EmployeeCategory),('DEPARTMENT',m.Department),('SPECIALITY',m.Speciality),('POSITION',m.Position),('REASON',m.TravelReason),('STATUS',m.TravelStatus),('TRANSPORT',m.TransportMode),('OVERNIGHTPLACE',m.AccommodationType)]:
                def named(r, model=model, table=table):
                    v = {'name': r.get('NAME') or r.get('STATUSNAME') or '', 'is_active': r.get('ISACTIVE',1) == 1}
                    if table in ('DEPARTMENT','POSITION'):
                        v['name_genitive'] = r.get('NAMEGENIKI') or ''
                    if table in ('TRANSPORT','OVERNIGHTPLACE'):
                        v['code'] = r.get('CODE') or ''
                    if table == 'TRANSPORT':
                        v.update(has_mileage_cost=r['HASPRIVATECOST']==1, has_ticket_cost=r['HASPUBLICCOST']==1)
                    if table == 'OVERNIGHTPLACE':
                        v.update(has_cost=r['HASCOST']==1, requires_declaration=r['NEEDRESPSTATEMENT']==1)
                    save(model,r[table],v)
                process(table,named)

            def employee(r):
                v = {target:r[source] or '' for target,source in [('code','CODE'),('first_name','FIRSTNAME'),('last_name','LASTNAME'),('display_name','NAME'),('name_genitive','NAMEGENIKI'),('email','EMAIL'),('iban','IBAN'),('car_plate','CARPLATE')]}
                v.update(department=ref(m.Department,r['DEPARTMENT']), speciality=ref(m.Speciality,r['SPECIALITY']), position=ref(m.Position,r['POSITION']), is_active=r['ISACTIVE']==1)
                obj, created = save(m.Employee,r['USR'],v)
                if created and r['CATEGORY'] is not None:
                    history=m.EmployeeCategoryHistory(employee=obj, category=ref(m.EmployeeCategory,r['CATEGORY']),valid_from=options['category_as_of'])
                    history.full_clean(); history.save()
            process('USR',employee)

            def route(r):
                cities=[x.strip() for x in (r['TOCITY'] or '').split('-') if x.strip()]
                lists=[[x.strip() for x in (r[field] or '').split('-')] for field in ['EXPENSIVE','IS_IN_ISLAND','COMPCATEGORY']]
                # Delphi stores five padded flag slots; only occupied destination slots are meaningful.
                if not cities or any(len(v)<len(cities) for v in lists):
                    raise ValueError('Missing destination flags')
                expensive,islands,bands=[[int(x) for x in v[:len(cities)]] for v in lists]
                if any(x not in (0,1) for x in expensive+islands) or any(x not in (0,1,2,3) for x in bands):
                    raise ValueError('Invalid flags')
                # Legacy ABROAD is route-wide: multi-stop foreign routes need per-stop review.
                review=r['FORCHECK']==1 or (r['ABROAD']==1 and len(cities)>1) or any(a and b for a,b in zip(expensive,islands))
                obj,created=save(m.Route,r['ROUTE'],dict(name=(r['FROMCITY']+' - '+r['TOCITY'])[:100],origin=r['FROMCITY'],destination=r['TOCITY'],distance_km=decimal(r['DISTANCE']),is_abroad=r['ABROAD']==1,has_daily_allowance=r['HASDAILYCOMPENSATION']==1,requires_review=review,notes=r['COMMENTS'] or '',is_active=r['ISACTIVE']==1))
                if created:
                    for i,city in enumerate(cities):
                        stop=m.RouteStop(route=obj,sequence=i+1,city=city,is_abroad=r['ABROAD']==1,is_expensive=bool(expensive[i]),is_island=bool(islands[i]),compensation_band=bands[i])
                        stop.full_clean();stop.save()
                if review:
                    report['issues'].append({'table':'ROUTE','legacy_id':r['ROUTE'],'error_type':'RouteNeedsReview'})
            process('ROUTE',route)

            def daily(r):
                save(m.DailyAllowanceRate,r['DAILYCOMPENSATION'],dict(category=ref(m.EmployeeCategory,r['CATEGORY']),is_abroad=r['ABROAD']==1,valid_from=r['VALIDFROM'],valid_to=r['VALIDTO'],without_overnight=decimal(r['COMPWITHOUTOVERNIGHT']),band_1=decimal(r['COMP']),band_2=decimal(r['COMP2']),band_3=decimal(r['COMP3'])))
            process('DAILYCOMPENSATION',daily)
            def hotel(r):
                save(m.AccommodationRate,r['HOTELCOST'],dict(category=ref(m.EmployeeCategory,r['CATEGORY']),is_abroad=r['ABROAD']==1,valid_from=r['VALIDFROM'],valid_to=r['VALIDTO'],minimum_distance_km=decimal(r['OVERNIGHTDISTANCELIMIT']),standard_limit=decimal(r['HOTELCOSTLIMIT']),expensive_city_limit=decimal(r['HOTELCOSTEXPCITYLIMIT']),island_limit=decimal(r['HOTELCOSTISLAND'])))
            process('HOTELCOST',hotel)
            process('KMALLOWANCE',lambda r:save(m.MileageRate,r['KMALLOWANCE'],dict(valid_from=r['FROMDATE'],valid_to=r['TODATE'],amount_per_km=decimal(r['AMOUNT'],4))))
            if not options['apply']:
                transaction.set_rollback(True)
        target=Path(settings.BASE_DIR)/'docs'/('import-applied.json' if options['apply'] else 'import-preview.json')
        target.write_text(json.dumps(report,indent=2),encoding='utf-8')
        self.stdout.write(json.dumps(report,indent=2))
