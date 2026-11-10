from datetime import date
from io import BytesIO
from django.test import TestCase
from django.core.exceptions import ValidationError
from pypdf import PdfReader
from .test_other_document_formats import OtherDocumentFormatTests
from .other_documents import document_pdf,DocumentForm
from .models import AccommodationType

class CombinedDocumentTests(OtherDocumentFormatTests):
    def test_car_protocol_has_single_slash_and_dot_date(self):
        self.personal_details()
        text=' '.join(p.extract_text() for p in self.reader('car').pages)
        self.assertIn('123/01.11.2026',text)
        self.assertNotIn('123 / 01/11/2026',text)
        self.assertIn('03/11/2026',text)

    def test_all_is_default_and_combines_applicable_reports(self):
        self.personal_details();self.friends()
        from .calculation import calculate_estimate
        calculate_estimate(self.travel.pk,self.user)
        self.travel.actions_description='Completed activities';self.travel.save()
        form=DocumentForm(travel=self.travel)
        self.assertEqual(form['kind'].value(),'all')
        reader=self.reader('all')
        self.assertEqual(len(reader.pages),3)
        self.assertIn('ABC123',reader.pages[0].extract_text())
        self.assertIn('άρθρο 8 Ν.1599/1986',reader.pages[1].extract_text())
        self.assertIn('ΑΝΑΦΟΡΑ ΠΕΠΡΑΓΜΕΝΩΝ',reader.pages[2].extract_text())
        self.assertEqual(len(reader.outline),3)

    def test_all_omits_friends_when_not_entered(self):
        self.personal_details();self.travel.actions_description='Completed';self.travel.save()
        self.assertEqual(len(self.reader('all').pages),2)

    def test_all_omits_car_for_public_transport_only(self):
        self.personal_details();self.travel.expenses.filter(kind='mileage').update(is_cancelled=True)
        self.travel.actions_description='Completed';self.travel.save()
        reader=self.reader('all');self.assertEqual(len(reader.pages),1)
        self.assertIn('ΑΝΑΦΟΡΑ ΠΕΠΡΑΓΜΕΝΩΝ',reader.pages[0].extract_text())

    def test_combined_export_reports_missing_data_instead_of_silently_skipping(self):
        self.personal_details()
        with self.assertRaises(ValidationError):document_pdf(self.travel,'all',date(2026,11,5))

    def test_combined_download_endpoint(self):
        self.personal_details();self.travel.actions_description='Completed';self.travel.save()
        self.client.force_login(self.user)
        response=self.client.post(f'/travels/{self.travel.pk}/documents/',{'kind':'all','print_date':'05/11/2026'})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response['Content-Type'],'application/pdf')
        self.assertIn('-all.pdf',response['Content-Disposition'])
        self.assertEqual(len(PdfReader(BytesIO(response.content)).pages),2)
