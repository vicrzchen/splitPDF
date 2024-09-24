import os
import sys
import unittest
from PyPDF2 import PdfReader
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from kits.file_processor import save_document_pages

class TestFileProcessor(unittest.TestCase):

    def setUp(self):
        self.input_dir = 'testdata/in'
        self.output_dir = 'testdata/out'
        self.pdf_name = 'scan doc'
        self.doc_type = 'test_type'
        self.reader = PdfReader(os.path.join(self.input_dir, f"{self.pdf_name}.pdf"))
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def tearDown(self):
        for file in os.listdir(self.output_dir):
            os.remove(os.path.join(self.output_dir, file))

    def test_save_document_pages(self):
        page_indices = [0, 1]  # 假设我们要保存前两页
        output_filename = save_document_pages(self.reader, page_indices, self.pdf_name, self.doc_type, self.output_dir)
        self.assertIsNotNone(output_filename)
        self.assertTrue(os.path.exists(os.path.join(self.output_dir, output_filename)))

if __name__ == '__main__':
    unittest.main()
