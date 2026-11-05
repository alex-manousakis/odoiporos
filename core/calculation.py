"""Estimate calculation ported from TravelP.pas; no settlement or approval side effects."""
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_CEILING
import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max, Q
from .models import (Travel, ApplicationParameters, DailyAllowanceRate, AccommodationRate,
                     MileageRate, CalculationSnapshot)

ZERO=Decimal('0.00')


def rounded(value):
    return value.quantize(Decimal('0.01'),rounding=ROUND_HALF_EVEN)


def unique_rate(model,**filters):
    rows=list(model.objects.filter(**filters)[:2])
    labels={'accommodationrate':'Έξοδα διανυκτέρευσης','dailyallowancerate':'Ημερήσια αποζημίωση','mileagerate':'Χιλιομετρική αποζημίωση'}
    criteria=[]
    if 'category_id' in filters:
        from .models import EmployeeCategory
        category=EmployeeCategory.objects.filter(pk=filters['category_id']).first()
        criteria.append('κατηγορία '+(category.name if category else str(filters['category_id'])))
    if 'is_abroad' in filters:
        criteria.append('εξωτερικό' if filters['is_abroad'] else 'Ελλάδα')
    start=filters.get('valid_from__lte');end=filters.get('valid_to__gte')
    if start:
        criteria.append(start.strftime('%d/%m/%Y') if start==end else start.strftime('%d/%m/%Y')+' έως '+end.strftime('%d/%m/%Y'))
    description=labels.get(model._meta.model_name,model._meta.model_name)+': '+', '.join(criteria)
    if not rows:
        raise ValidationError('Δεν βρέθηκε ισχύουσα τιμή. '+description+'. Συμπληρώστε τιμή που καλύπτει τις ημερομηνίες της μετακίνησης.')
    if len(rows)>1:
        raise ValidationError('Βρέθηκαν επικαλυπτόμενες τιμές. '+description+'. Ελέγξτε τα διαστήματα ισχύος.')
    return rows[0]


def input_state(travel):
    # Snapshot only calculation inputs, not employee personal or banking information.
    fields=['employee_id','route_id','departure_at','return_at','work_starts_at','work_ends_at','applied_category_id','category_review_required','mileage_override','transport_id','transport_configured','ticket_cost','transfer_cost']
    parameters=ApplicationParameters.objects.filter(pk=1).values('homedistancelimit','percentageofbudgetinc','roundtotalbudget','budgetdownlimit').first()
    return {'travel':{n:str(getattr(travel,n)) for n in fields},
        'route':list(travel.route.__class__.objects.filter(pk=travel.route_id).values('distance_km','is_abroad','has_daily_allowance','requires_review')),
        'stops':list(travel.route.stops.values('id','sequence','is_abroad','compensation_band')),
        'expenses':list(travel.expenses.order_by('pk').values('id','kind','transport_id','transport__has_mileage_cost','transport__has_ticket_cost','estimated_amount','estimated_transfer_cost','estimated_distance_km','is_cancelled')),
        'nights':list(travel.overnights.order_by('pk').values('id','date','stop_id','city','is_abroad','is_expensive','is_island','compensation_band','accommodation_type__has_cost','estimated_cost','is_excluded')),
        'category_history':list(travel.employee.category_history.values('category_id','valid_from','valid_to')),
        'transport_flags':{'mileage':travel.transport.has_mileage_cost,'ticket':travel.transport.has_ticket_cost} if travel.transport_id else None,
        'parameters':parameters,
        'daily_rates':list(DailyAllowanceRate.objects.order_by('pk').values()),
        'hotel_rates':list(AccommodationRate.objects.order_by('pk').values()),
        'mileage_rates':list(MileageRate.objects.order_by('pk').values())}


def signature(state):
    return hashlib.sha256(json.dumps(state,sort_keys=True,default=str).encode()).hexdigest()


@transaction.atomic
def calculate_estimate(travel_id,actor):
    travel=Travel.objects.select_for_update().select_related('route','employee').get(pk=travel_id)
    from .views import can_edit_costs
    if not can_edit_costs(actor,travel):
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    params=ApplicationParameters.objects.filter(pk=1).first()
    if not params or params.homedistancelimit is None:
        raise ValidationError('Συμπληρώστε το όριο χιλιομέτρων εντός έδρας στις παραμέτρους.')
    if not travel.departure_at<=travel.work_starts_at<=travel.work_ends_at<=travel.return_at:
        raise ValidationError('Ελέγξτε τις ημερομηνίες ταξιδιού και εργασίας.')
    if travel.category_review_required or not travel.applied_category_id:
        raise ValidationError('Απαιτείται έλεγχος κατηγορίας εργαζομένου για αυτή τη μετακίνηση.')
    history=travel.employee.category_history.filter(category_id=travel.applied_category_id,valid_from__lte=travel.departure_at).filter(Q(valid_to__isnull=True)|Q(valid_to__gte=travel.return_at))
    if history.count()!=1:
        raise ValidationError('Η κατηγορία δεν καλύπτει ολόκληρο το ταξίδι. Απαιτείται έλεγχος.')
    if travel.route.requires_review:
        raise ValidationError('Η διαδρομή είναι σημειωμένη για έλεγχο. Διορθώστε τα χαρακτηριστικά της πριν τον υπολογισμό.')
    stops=list(travel.route.stops.all())
    if not stops:
        raise ValidationError('Η διαδρομή δεν έχει προορισμούς.')
    classes={(s.is_abroad,s.compensation_band) for s in stops}
    if len(classes)!=1 or any(s.is_abroad!=travel.route.is_abroad for s in stops):
        raise ValidationError('Μικτή διαδρομή με διαφορετικές κατηγορίες προορισμών: απαιτείται κατανομή ημερών πριν τον υπολογισμό.')
    start=travel.work_starts_at-timedelta(days=1) if travel.departure_at<travel.work_starts_at else travel.work_starts_at
    end=travel.work_ends_at
    days=(end-start).days+1
    returned_next_day=travel.return_at>travel.work_ends_at
    domestic=abroad=mileage=tickets=other=claimed=allowed=ZERO
    details={'days':days,'allowance_from':str(start),'allowance_to':str(end),'rounding':'ROUND_HALF_EVEN','hotel_estimate_policy':'per_night','rates':[],'nights':[],'expenses':[]}
    if travel.route.has_daily_allowance and travel.route.distance_km>params.homedistancelimit:
        rate=unique_rate(DailyAllowanceRate,category_id=travel.applied_category_id,is_abroad=travel.route.is_abroad,valid_from__lte=start,valid_to__gte=end)
        band=stops[0].compensation_band
        if band not in (1,2,3):raise ValidationError('Μη έγκυρη κατηγορία ημερήσιας αποζημίωσης.')
        per_day=rate.without_overnight if days==1 and not returned_next_day else getattr(rate,'band_'+str(band))
        total=rounded(per_day*days)
        if travel.route.is_abroad:abroad=total
        else:domestic=total
        details['rates'].append({'type':'daily','id':rate.pk,'per_day':str(per_day)})
    if travel.transport_configured:
        mode=travel.transport
        if not mode:raise ValidationError('Επιλέξτε μέσο μετακίνησης.')
        if mode.has_mileage_cost:
            if travel.route.distance_km<=0:raise ValidationError('Η διαδρομή δεν έχει θετική απόσταση.')
            rate_value=travel.mileage_override
            if rate_value is None or rate_value<=0:
                rate=unique_rate(MileageRate,valid_from__lte=start,valid_to__gte=start)
                rate_value=rate.amount_per_km
                details['rates'].append({'type':'mileage','id':rate.pk,'amount':str(rate_value)})
            mileage=rounded(travel.route.distance_km*rate_value)
        if mode.has_ticket_cost:
            if travel.ticket_cost is None or travel.ticket_cost<0 or (travel.transfer_cost or ZERO)<0:raise ValidationError('Ελέγξτε τα κόστη εισιτηρίων και πρόσβασης.')
            tickets=travel.ticket_cost;other=travel.transfer_cost or ZERO
        details['transport']={'id':mode.pk,'name':mode.name,'has_mileage_cost':mode.has_mileage_cost,'has_ticket_cost':mode.has_ticket_cost,'distance_km':str(travel.route.distance_km),'mileage':str(mileage),'tickets':str(tickets),'transfers':str(other)}
    else:
        if travel.expenses.filter(kind='mileage',is_cancelled=False).count()>1:
            raise ValidationError('Only one mileage entry is allowed per full route.')
        for expense in travel.expenses.select_related('transport').filter(is_cancelled=False):
            amount=ZERO
            if expense.kind=='mileage':
                if not expense.transport or not expense.transport.has_mileage_cost or travel.route.distance_km<=0:
                    raise ValidationError('Ελέγξτε μέσο και χιλιόμετρα ΙΧ.')
                rate_value=travel.mileage_override
                if rate_value is None or rate_value<=0:
                    rate=unique_rate(MileageRate,valid_from__lte=start,valid_to__gte=start)
                    rate_value=rate.amount_per_km
                    details['rates'].append({'type':'mileage','id':rate.pk,'amount':str(rate_value)})
                amount=rounded(travel.route.distance_km*rate_value);mileage+=amount
            elif expense.kind in ('ticket','other'):
                if expense.estimated_amount is None or expense.estimated_amount<0:raise ValidationError('Λείπει ποσό δαπάνης.')
                amount=expense.estimated_amount
                if expense.kind=='ticket':
                    if not expense.transport or not expense.transport.has_ticket_cost:raise ValidationError('Μη έγκυρο μέσο εισιτηρίου.')
                    tickets+=amount;other+=expense.estimated_transfer_cost or ZERO
                else:other+=amount
            else:raise ValidationError('Άγνωστο είδος δαπάνης.')
            details['expenses'].append({'id':expense.pk,'amount':str(amount),'airport_transfer':str(expense.estimated_transfer_cost or ZERO)})
    seen=set()
    for night in travel.overnights.select_related('accommodation_type','stop').order_by('date'):
        if night.is_excluded: continue
        if night.date in seen or not travel.departure_at<=night.date<travel.return_at or night.stop.route_id!=travel.route_id:
            raise ValidationError('Ελέγξτε ημερομηνίες και προορισμούς διαμονής.')
        seen.add(night.date)
        limit=cost=ZERO
        if night.accommodation_type.has_cost:
            if night.estimated_cost is None or night.estimated_cost<0:raise ValidationError('Λείπει κόστος ξενοδοχείου.')
            if night.is_expensive and night.is_island:raise ValidationError('Η διαμονή δεν μπορεί να είναι ταυτόχρονα ειδική πόλη και νησί.')
            rate=unique_rate(AccommodationRate,category_id=travel.applied_category_id,is_abroad=night.is_abroad,valid_from__lte=night.date,valid_to__gte=night.date)
            if travel.route.distance_km>rate.minimum_distance_km:
                limit=rate.island_limit if night.is_island else rate.expensive_city_limit if night.is_expensive else rate.standard_limit
            cost=night.estimated_cost;claimed+=cost;allowed+=min(cost,limit)
            details['rates'].append({'type':'hotel','id':rate.pk,'date':str(night.date),'limit':str(limit)})
        details['nights'].append({'id':night.pk,'date':str(night.date),'claimed':str(cost),'limit':str(limit),'allowed':str(min(cost,limit))})
    total=rounded(domestic+abroad+mileage+tickets+other+allowed)
    budget=total*(1+(params.percentageofbudgetinc or ZERO)/100)
    budget=budget.quantize(Decimal('1'),rounding=ROUND_CEILING) if params.roundtotalbudget else rounded(budget)
    budget=rounded(max(budget,params.budgetdownlimit or ZERO))
    state=input_state(travel)
    details.update(signature=signature(state),source=json.loads(json.dumps(state,default=str)))
    revision=(travel.calculations.filter(stage='estimate').aggregate(n=Max('revision'))['n'] or 0)+1
    snapshot=CalculationSnapshot(travel=travel,stage='estimate',revision=revision,calculated_by=actor,algorithm_version='estimate-3',inputs=details,daily_domestic=domestic,daily_abroad=abroad,mileage=mileage,tickets=tickets,other=other,claimed_accommodation=claimed,allowed_accommodation=allowed,total=total,document_budget=budget)
    snapshot.full_clean();snapshot.save()
    return snapshot
