from datetime import date,timedelta
from io import BytesIO
from django.test import TestCase
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from . import tests as fixtures
from .models import AccommodationType,OvernightStay,ApplicationParameters
from .other_documents import DocumentForm,document_pdf

class OtherDocumentFormatTests(TestCase):
    setUp=fixtures.ApprovalPDFTests.setUp

    def personal_details(self):
        employee=self.employee
        employee.first_name='Example first';employee.last_name='Example last'
        employee.father_name='Example father';employee.mother_name='Example mother'
        employee.birth_date=date(1980,1,2);employee.birth_place='Example birthplace'
        employee.address='Example street';employee.address_number='10';employee.city='Example city'
        employee.postal_code='12345';employee.phone='123456789';employee.fax='987654321';employee.email='example@example.test'
        employee.tax_number='PRIVATE-TAX-ID';employee.iban='NEVER-PRINT-BANK-ACCOUNT'
        employee.car_plate='ABC123';employee.car_brand='Example car';employee.driving_license='DL123';employee.save()
        employee.gender.text2='Ο Δηλών';employee.gender.text3='Ο κάτωθι υπογεγραμμένος';employee.gender.save()
        return employee

    def reader(self,kind):
        return PdfReader(BytesIO(document_pdf(self.travel,kind,date(2026,11,5))))

    def friends(self):
        friend=AccommodationType.objects.create(name='ΦΙΛΙΚΟ ΣΠΙΤΙ',has_cost=False,requires_declaration=True)
        night=self.travel.overnights.get();night.accommodation_type=friend;night.estimated_cost=None;night.save()
        return night

    def test_car_matches_simple_declaration_and_preserves_greek_amounts(self):
        self.personal_details()
        reader=self.reader('car');self.assertEqual(len(reader.pages),1)
        text=reader.pages[0].extract_text()
        for value in ['ΥΠΕΥΘΥΝΗ ΔΗΛΩΣΗ','ΠΡΟΣ:','ABC123','Example car','DL123','80,00','05/11/2026','Ο Δηλών']:self.assertIn(value,text)
        self.assertNotIn('Example father',text)

    def test_friends_form_has_personal_grid_and_notes_without_unneeded_bank_data(self):
        self.personal_details();self.friends()
        reader=self.reader('friends');self.assertEqual(len(reader.pages),1)
        text=reader.pages[0].extract_text()
        for value in ['άρθρο 8 Ν.1599/1986','Example first','Example last','Example father','Example mother','Example street','02/01/1980','Fax','example@example.test','03/11/2026','(Υπογραφή)','(4)']:self.assertIn(value,text)
        self.assertNotIn('PRIVATE-TAX-ID',text)
        self.assertNotIn('NEVER-PRINT-BANK-ACCOUNT',text)

    def test_friends_choice_absent_for_hotels_or_excluded_friends_and_forged_post_rejected(self):
        self.personal_details()
        kinds=dict(DocumentForm(travel=self.travel).fields['kind'].choices)
        self.assertNotIn('friends',kinds)
        self.client.force_login(self.user)
        response=self.client.post(f'/travels/{self.travel.pk}/documents/',{'kind':'friends','print_date':'05/11/2026'})
        self.assertEqual(response.status_code,200);self.assertNotEqual(response['Content-Type'],'application/pdf')
        with self.assertRaises(ValidationError):document_pdf(self.travel,'friends',date(2026,11,5))
        night=self.friends()
        self.assertIn('friends',dict(DocumentForm(travel=self.travel).fields['kind'].choices))
        night.is_excluded=True;night.save()
        self.assertNotIn('friends',dict(DocumentForm(travel=self.travel).fields['kind'].choices))

    def test_declaration_lists_only_entered_friend_nights(self):
        self.personal_details();self.friends()
        hotel=AccommodationType.objects.get(name='Hotel')
        OvernightStay.objects.create(travel=self.travel,stop=self.stop,accommodation_type=hotel,date=date(2026,11,4),city='HOTEL-ONLY-CITY',estimated_cost=80)
        text=' '.join(page.extract_text() for page in self.reader('friends').pages)
        self.assertIn('03/11/2026',text);self.assertNotIn('04/11/2026',text);self.assertNotIn('HOTEL-ONLY-CITY',text)

    def test_activity_numbered_rows_footer_and_logos(self):
        self.travel.actions_description='Activities completed & verified';self.travel.save()
        reader=self.reader('activity');self.assertEqual(len(reader.pages),1)
        text=reader.pages[0].extract_text()
        for value in ['ΑΝΑΦΟΡΑ ΠΕΠΡΑΓΜΕΝΩΝ ΜΕΤΑΚΙΝΗΣΗΣ','Αρ. πρωτ. Απόφασης','Σκοπός Μετακίνησης','Activities completed & verified','8. Υπογραφή','9. Ημερομηνία','Ευρωπαϊκή Ένωση','71202']:self.assertIn(value,text)
        images=reader.pages[0]['/Resources']['/XObject'].get_object()
        self.assertGreaterEqual(sum(obj.get_object().get('/Subtype')=='/Image' for obj in images.values()),2)

    def test_long_activity_wraps_to_multiple_pages_with_repeated_footer(self):
        self.travel.actions_description=('A detailed description of the completed service meeting. '*20+'\n')*12;self.travel.save()
        reader=self.reader('activity');self.assertGreater(len(reader.pages),1)
        for page in reader.pages:self.assertIn('Ευρωπαϊκή Ένωση',page.extract_text())

    def test_report_configuration_controls_recipient_place_and_address(self):
        self.personal_details()
        params=ApplicationParameters.objects.get(pk=1);params.report_recipient='Custom recipient';params.report_place='Custom place';params.report_address='Custom address';params.save()
        car=' '.join(page.extract_text() for page in self.reader('car').pages)
        self.assertIn('Custom recipient',car);self.assertIn('Custom place',car)
        self.travel.actions_description='Done';self.travel.save()
        activity=' '.join(page.extract_text() for page in self.reader('activity').pages)
        self.assertIn('Custom address',activity)
