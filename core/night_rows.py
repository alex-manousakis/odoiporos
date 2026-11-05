from datetime import timedelta
from .models import ApplicationParameters, AccommodationType

def synchronized_post(post,travel):
    if not travel.route_id or not travel.departure_at or not travel.return_at: return post
    count=(travel.return_at-travel.departure_at).days
    if not 0<=count<=366: return post
    data=post.copy()
    existing=list(travel.overnights.order_by('pk')) if travel.pk else []
    submitted={};new={}
    try: total=min(int(post.get('stays-TOTAL_FORMS',0)),1000)
    except ValueError: total=0
    from datetime import datetime
    for index in range(total):
        prefix=f'stays-{index}-'
        values={name:post.get(prefix+name,'') for name in ['id','date','stop','accommodation_type','estimated_cost','is_excluded']}
        if values['id']: submitted[values['id']]=values
        else:
            for fmt in ('%d/%m/%Y','%Y-%m-%d'):
                try: day=datetime.strptime(values['date'],fmt).date();new[day]=values;break
                except ValueError: pass
    params=ApplicationParameters.objects.filter(pk=1).first()
    default=params.default_accommodation if params and params.default_accommodation_id else AccommodationType.objects.filter(is_active=True).order_by('pk').first()
    stop=travel.route.stops.order_by('sequence','pk').first()
    wanted={travel.departure_at+timedelta(days=i) for i in range(count)}
    rows=[]
    for night in existing:
        values=submitted.get(str(night.pk),{name:str(getattr(night,name+'_id') or '') if name in ('stop','accommodation_type') else getattr(night,name) for name in ['stop','accommodation_type','estimated_cost','is_excluded']})
        values={**values,'id':night.pk,'date':night.date.strftime('%d/%m/%Y'),'DELETE':'on' if night.date not in wanted else ''}
        rows.append(values);wanted.discard(night.date)
    for day in sorted(wanted):
        values=new.get(day,{'stop':stop.pk if stop else '', 'accommodation_type':default.pk if default else '', 'estimated_cost':'','is_excluded':''})
        rows.append({**values,'id':'','date':day.strftime('%d/%m/%Y'),'DELETE':''})
    for key in list(data):
        if key.startswith('stays-'): del data[key]
    data['stays-TOTAL_FORMS']=str(len(rows));data['stays-INITIAL_FORMS']=str(len(existing))
    data['stays-MIN_NUM_FORMS']='0';data['stays-MAX_NUM_FORMS']='1000'
    for index,row in enumerate(rows):
        for name,value in row.items(): data[f'stays-{index}-{name}']='' if value is None else str(value)
    return data
