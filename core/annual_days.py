"""Annual approval balance; based on trips, never on the number of PDFs printed."""
from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import Travel

def counted_days(travel, snapshot, year):
    data=snapshot.inputs
    manual=data.get('accounting',{}).get('values',{}).get('days')
    if manual is not None and travel.departure_at.year==travel.return_at.year:
        return int(manual) if year==travel.departure_at.year else 0
    source=data.get('source',{})
    route=(source.get('route') or [{}])[0]
    parameters=source.get('parameters') or {}
    # Use calculation-time eligibility so later route/rate changes do not rewrite history.
    eligible=route.get('has_daily_allowance',travel.route.has_daily_allowance)
    distance=Decimal(str(route.get('distance_km',travel.route.distance_km)))
    limit=parameters.get('homedistancelimit')
    if limit is None: raise ValidationError('Λείπει το όριο εντός έδρας από αποθηκευμένο υπολογισμό. Υπολογίστε ξανά τη μετακίνηση '+str(travel.pk)+'.')
    if not eligible or distance<=Decimal(str(limit)): return 0
    try:
        start=date.fromisoformat(data['allowance_from'])
        end=date.fromisoformat(data['allowance_to'])
    except (KeyError,TypeError,ValueError):
        raise ValidationError('Λείπουν οι ημερομηνίες υπολογισμού για τη μετακίνηση '+str(travel.pk)+'. Υπολογίστε την ξανά.')
    return max(0,(min(end,date(year,12,31))-max(start,date(year,1,1))).days+1)

def annual_balance(travel,parameters):
    if not parameters or not parameters.installation_year:
        raise ValidationError('Συμπληρώστε το έτος έναρξης εφαρμογής στις παραμέτρους.')
    year=travel.departure_at.year
    opening=travel.employee.opening_travel_days if year==parameters.installation_year else 0
    # Chronological order; ties have a stable record-ID order. All existing statuses
    # (new/finalized/checked) count; there is currently no cancelled-trip status.
    earlier=Travel.objects.filter(employee_id=travel.employee_id,
        departure_at__lte=date(year,12,31),return_at__gte=date(year,1,1)).exclude(pk=travel.pk).filter(
        Q(departure_at__lt=travel.departure_at)|Q(departure_at=travel.departure_at,pk__lt=travel.pk)
    ).select_related('route').prefetch_related('calculations').order_by('departure_at','pk')
    rows=[]
    for previous in earlier:
        snapshots=[x for x in previous.calculations.all() if x.stage=='estimate']
        if not snapshots:
            raise ValidationError('Η προηγούμενη μετακίνηση '+str(previous.pk)+' δεν έχει υπολογισμό. Αποθηκεύστε την πριν εκτυπώσετε την απόφαση.')
        snapshot=max(snapshots,key=lambda x:x.revision)
        stored=snapshot.inputs.get('source',{}).get('travel',{})
        if any(stored.get(name)!=str(getattr(previous,name)) for name in ('departure_at','return_at','work_starts_at','work_ends_at')):
            raise ValidationError('Ο υπολογισμός της προηγούμενης μετακίνησης '+str(previous.pk)+' δεν συμφωνεί με τις ημερομηνίες της. Αποθηκεύστε την ξανά.')
        rows.append({'travel_id':previous.pk,'calculation_id':snapshot.pk,'days':counted_days(previous,snapshot,year)})
    recorded=sum(x['days'] for x in rows)
    return {'year':year,'installation_year':parameters.installation_year,'opening_days':opening,'recorded_days':recorded,'prior_days':opening+recorded,'trips':rows}
