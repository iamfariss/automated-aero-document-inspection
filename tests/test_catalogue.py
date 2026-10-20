import io,json,tempfile,unittest,zipfile
from pathlib import Path
from unittest.mock import patch
from catalogue import Catalogue

def pdf_bytes():
    import pypdfium2 as pdfium
    with pdfium.PdfDocument.new() as pdf:
        page=pdf.new_page(200,200)
        page.close()
        out=io.BytesIO();pdf.save(out)
        return out.getvalue()

class CatalogueTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.catalogue=Catalogue(self.root/'library')

    def tearDown(self):
        self.temp.cleanup()

    def archive(self,members):
        path=self.root/'input.zip'
        with zipfile.ZipFile(path,'w') as z:
            for name,raw in members.items():z.writestr(name,raw)
        return path

    def test_import_is_idempotent_and_content_deduplicated(self):
        raw=pdf_bytes()
        path=self.archive({'Specs/TEST/TEST_A.pdf':raw,'Specs/TEST/TEST_B.pdf':raw,'Specs/TEST/readme.doc':b'not executed'})
        self.catalogue.import_zip(path)
        self.catalogue.import_zip(path)
        summary=self.catalogue.summary()
        self.assertEqual(summary['total'],3)
        self.assertEqual(summary['unique_pdfs'],1)
        self.assertEqual(len(list((self.catalogue.root/'files').iterdir())),1)
        self.assertEqual(self.catalogue.pdf(1)[1],raw)

    def test_path_escape_rejected_before_writing_members(self):
        with self.assertRaises(ValueError):self.catalogue.import_zip(self.archive({'../escape.pdf':b'%PDF-'}))
        self.assertEqual(self.catalogue.summary()['total'],0)

    def test_bad_header_and_shortcuts_are_inventory_only(self):
        self.catalogue.import_zip(self.archive({'bad.pdf':b'not PDF','shortcut.lnk':b'not executed'}))
        with self.assertRaises(ValueError):self.catalogue.pdf(1)
        self.assertEqual(len(list((self.catalogue.root/'files').iterdir())),0)

    def test_source_checksum_tamper_is_detected(self):
        self.catalogue.import_zip(self.archive({'test.pdf':pdf_bytes()}))
        path=next((self.catalogue.root/'files').iterdir());path.write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'checksum'):self.catalogue.pdf(1)

    def test_index_marks_scanned_and_search_escapes_query(self):
        self.catalogue.import_zip(self.archive({'Specs/ALLOY/TEST_A.pdf':pdf_bytes()}))
        summary=self.catalogue.index()
        self.assertEqual(summary['statuses']['Scanned / sparse text — needs OCR'],1)
        found=self.catalogue.search('TEST')
        self.assertEqual(found['total'],1)
        self.assertEqual(found['items'][0]['pages'],1)
        self.assertEqual(self.catalogue.search('" OR * NOT')['total'],0)

    def test_worker_timeout_keeps_inventory_available(self):
        self.catalogue.import_zip(self.archive({'test.pdf':pdf_bytes()}))
        import subprocess
        with patch('catalogue.subprocess.run',side_effect=subprocess.TimeoutExpired('worker',30)):
            self.catalogue.index()
        self.assertEqual(self.catalogue.summary()['statuses']['PDF indexing error'],1)

    def test_library_never_approves_registry(self):
        self.catalogue.import_zip(self.archive({'test.pdf':pdf_bytes()}))
        from registry import Registry
        registry=Registry(self.root/'governed')
        self.assertEqual(registry.list(),[])
