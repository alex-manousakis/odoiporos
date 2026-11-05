from datetime import date
from decimal import Decimal
from django.test import TestCase
from . import tests as fixtures
from .models import AccommodationType, OvernightStay, ApplicationParameters
from .forms import StayFormSet
from .night_rows import synchronized_post
from django.http import QueryDict

class AutomaticNightTests(TestCase):
    setUp=fixtures.EstimateCalculationTests.setUp

    def post(self,return_on='08/11/2026'):
        self.travel.departure_at=date(2026,11,5)
        self.travel.return_at=date.fromisoformat('-'.join(reversed(return_on.split('/'))))
        self.travel.work_starts_at=min(date(2026,11,6),self.travel.return_at)
        self.travel.work_ends_at=self.travel.return_at
        self.travel.save()
        # Start with rows matching the interval and persist explicit exceptions.
        self.travel.overnights.all().delete()
        friends=AccommodationType.objects.create(name='Friends',has_cost=False,requires_declaration=True)
        params=ApplicationParameters.objects.get(pk=1);params.default_accommodation=friends;params.save()
        return friends

    def normalize(self,values=None):
        data=QueryDict('',mutable=True)
        data.update(values or {})
        return synchronized_post(data,self.travel)

    def test_three_nights_generated_without_javascript(self):
        self.post()
        data=self.normalize()
        formset=StayFormSet(data,instance=self.travel,prefix='stays',form_kwargs={'travel':self.travel})
        self.assertTrue(formset.is_valid(),formset.errors)
        formset.save()
        self.assertEqual(list(self.travel.overnights.order_by('date').values_list('date',flat=True)),[date(2026,11,5),date(2026,11,6),date(2026,11,7)])

    def test_shortening_preserves_matching_rows_and_removes_outside_dates(self):
        friends=self.post()
        for day in (5,6,7):OvernightStay.objects.create(travel=self.travel,date=date(2026,11,day),stop=self.stop,accommodation_type=friends,city='B',is_excluded=day==6)
        kept=self.travel.overnights.get(date=date(2026,11,6))
        self.travel.departure_at=date(2026,11,6);self.travel.return_at=date(2026,11,7)
        formset=StayFormSet(self.normalize(),instance=self.travel,prefix='stays',form_kwargs={'travel':self.travel})
        self.assertTrue(formset.is_valid(),formset.errors);formset.save()
        self.assertEqual(self.travel.overnights.count(),1)
        kept.refresh_from_db();self.assertTrue(kept.is_excluded)

    def test_extension_preserves_cost_and_adds_missing_nights(self):
        self.post('07/11/2026')
        hotel=AccommodationType.objects.get(name='Hotel')
        night=OvernightStay.objects.create(travel=self.travel,date=date(2026,11,5),stop=self.stop,accommodation_type=hotel,city='B',estimated_cost=Decimal('75'))
        self.travel.return_at=date(2026,11,9)
        formset=StayFormSet(self.normalize(),instance=self.travel,prefix='stays',form_kwargs={'travel':self.travel})
        self.assertTrue(formset.is_valid(),formset.errors);formset.save()
        night.refresh_from_db();self.assertEqual(night.estimated_cost,Decimal('75'))
        self.assertEqual(self.travel.overnights.count(),4)

    def test_same_day_trip_removes_all_nights(self):
        self.post('05/11/2026')
        formset=StayFormSet(self.normalize(),instance=self.travel,prefix='stays',form_kwargs={'travel':self.travel})
        self.assertTrue(formset.is_valid(),formset.errors);formset.save()
        self.assertEqual(self.travel.overnights.count(),0)

    def test_excluded_hotel_has_no_cost_or_declaration(self):
        from .calculation import calculate_estimate
        night=self.travel.overnights.get();night.is_excluded=True;night.estimated_cost=None;night.save()
        estimate=calculate_estimate(self.travel.pk,self.user)
        self.assertEqual(estimate.allowed_accommodation,0)
        self.assertEqual(estimate.claimed_accommodation,0)

    def test_existing_date_cannot_be_changed_by_submitted_row(self):
        friends=self.post()
        night=OvernightStay.objects.create(travel=self.travel,date=date(2026,11,5),stop=self.stop,accommodation_type=friends,city='B')
        data=self.normalize({'stays-TOTAL_FORMS':'1','stays-0-id':str(night.pk),'stays-0-date':'07/11/2026','stays-0-stop':str(self.stop.pk),'stays-0-accommodation_type':str(friends.pk)})
        self.assertEqual(data['stays-0-date'],'05/11/2026')
        self.assertEqual(data['stays-TOTAL_FORMS'],'3')

    def test_editor_synchronizes_dates_on_save(self):
        friends=AccommodationType.objects.create(name='Friends',has_cost=False)
        params=ApplicationParameters.objects.get(pk=1);params.default_accommodation=friends;params.save()
        original=self.travel.overnights.get()
        self.client.force_login(self.user)
        payload={'employee':self.employee.pk,'route':self.route.pk,'departure_at':'03/11/2026','return_at':'06/11/2026',
            'work_starts_at':'03/11/2026','work_ends_at':'05/11/2026','automatic_nights':'1','stays-TOTAL_FORMS':'0'}
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(self.travel.overnights.count(),3)
        original.refresh_from_db();self.assertEqual(original.estimated_cost,Decimal('100'))
        payload.update(return_at='04/11/2026',work_ends_at='04/11/2026')
        response=self.client.post(f'/travels/{self.travel.pk}/edit/',payload)
        self.assertEqual(response.status_code,302)
        self.assertEqual(list(self.travel.overnights.values_list('date',flat=True)),[date(2026,11,3)])
