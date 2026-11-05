from collections import defaultdict, Counter
from decimal import Decimal
from django.contrib.auth.decorators import login_required
from django.db.models import OuterRef, Subquery
from django.shortcuts import render
from django.utils import timezone
from .models import CalculationSnapshot
from .views import visible_travels

MONTHS=['Ιαν','Φεβ','Μάρ','Απρ','Μάι','Ιούν','Ιούλ','Αύγ','Σεπ','Οκτ','Νοέ','Δεκ']

@login_required
def dashboard(request):
    today=timezone.localdate()
    latest=CalculationSnapshot.objects.filter(travel_id=OuterRef('pk'),stage='estimate').order_by('-revision')
    trips=list(visible_travels(request.user).select_related('employee__department').annotate(dashboard_total=Subquery(latest.values('total')[:1])).order_by('-departure_at','-pk'))
    years=sorted({today.year,*[trip.departure_at.year for trip in trips]},reverse=True)
    try: year=int(request.GET.get('year',today.year))
    except (ValueError,TypeError): year=today.year
    if year not in years:year=today.year
    selected=[trip for trip in trips if trip.departure_at.year==year]
    total=sum((trip.dashboard_total for trip in selected if trip.dashboard_total is not None),Decimal(0))
    calculated=sum(trip.dashboard_total is not None for trip in selected)
    monthly=[{'label':label,'month':index+1,'cost':Decimal(0),'count':0} for index,label in enumerate(MONTHS)]
    annual=defaultdict(lambda:{'cost':Decimal(0),'count':0})
    destinations=defaultdict(lambda:{'cost':Decimal(0),'count':0})
    for trip in trips:
        annual[trip.departure_at.year]['count']+=1
        annual[trip.departure_at.year]['cost']+=trip.dashboard_total or Decimal(0)
    for trip in selected:
        cost=trip.dashboard_total or Decimal(0)
        row=monthly[trip.departure_at.month-1];row['count']+=1;row['cost']+=cost
        destination=trip.route.destination or trip.route.name
        destinations[destination]['count']+=1;destinations[destination]['cost']+=cost
    peak=max((row['cost'] for row in monthly),default=Decimal(0))
    for row in monthly:row['height']=float(row['cost']/peak*100) if peak else 0
    yearly=[{'year':key,**annual[key]} for key in sorted(annual)]
    annual_peak=max((row['cost'] for row in yearly),default=Decimal(0))
    for row in yearly:row['width']=float(row['cost']/annual_peak*100) if annual_peak else 0
    top=[{'name':key,**values} for key,values in sorted(destinations.items(),key=lambda item:(-item[1]['count'],item[0]))[:5]]
    for row in top:row['width']=row['count']/top[0]['count']*100
    busiest=max(monthly,key=lambda row:row['count']) if selected else None
    upcoming=sorted((trip for trip in trips if trip.departure_at>=today),key=lambda trip:(trip.departure_at,trip.pk))[:5]
    states=Counter(str(trip.status) for trip in selected)
    previous=annual.get(year-1)
    change=(total-previous['cost'])/previous['cost']*100 if previous and previous['cost'] else None
    current_month=monthly[today.month-1] if year==today.year else None
    return render(request,'core/dashboard.html',{'year':year,'years':years,'trip_count':len(selected),'total':total,
        'average':total/calculated if calculated else Decimal(0),'missing':len(selected)-calculated,
        'monthly':monthly,'yearly':yearly,'destination_count':len(destinations),'destinations':top,'busiest':busiest,'current_month':current_month,
        'upcoming':upcoming,'recent':selected[:5],'states':states.items(),'change':change})


from django.contrib.auth.views import LoginView
from django.urls import reverse

class DashboardLoginView(LoginView):
    def get_success_url(self):
        target=super().get_success_url()
        # A login started at the trip-list root should also land on the overview.
        # Keep explicit links to individual records and other protected pages.
        return reverse('core:dashboard') if target==reverse('core:home') else target
