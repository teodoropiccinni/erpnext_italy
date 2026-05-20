"""
Tests for erpnext_italy.utils.sdi_import_base — file filtering, content reading,
XML parsing helpers.

Run with:
    bench --site <site> run-tests --app erpnext_italy --module erpnext_italy.tests.test_sdi_import_base
"""

import io
import os
import unittest
import zipfile

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestIsInvoiceFile(unittest.TestCase):
	"""_is_invoice_file must accept invoices and reject SDI receipt/notification files."""

	def _check(self, name, expected):
		from erpnext_italy.utils.sdi_import_base import _is_invoice_file
		self.assertEqual(_is_invoice_file(name), expected, msg=name)

	def test_plain_xml_accepted(self):
		self._check("IT01234567890_00001.xml", True)

	def test_p7m_accepted(self):
		self._check("IT01234567890_00001.xml.p7m", True)

	def test_rc_receipt_skipped(self):
		self._check("IT01234567890_00001_RC_001.xml", False)

	def test_ns_notification_skipped(self):
		self._check("IT01234567890_00001_NS_001.xml", False)

	def test_mc_notification_skipped(self):
		self._check("IT01234567890_00001_MC_001.xml", False)

	def test_non_xml_skipped(self):
		self._check("readme.txt", False)
		self._check("IT01234567890_00001.pdf", False)


class TestGetFileContent(unittest.TestCase):
	"""get_file_content must decode .xml and extract .xml.p7m transparently."""

	def _make_zip(self, files: dict) -> zipfile.ZipFile:
		buf = io.BytesIO()
		with zipfile.ZipFile(buf, "w") as zf:
			for name, content in files.items():
				if isinstance(content, str):
					content = content.encode("utf-8")
				zf.writestr(name, content)
		buf.seek(0)
		return zipfile.ZipFile(buf)

	def test_plain_xml_decoded(self):
		from erpnext_italy.utils.sdi_import_base import get_file_content
		xml = "<root>test</root>"
		zf = self._make_zip({"invoice.xml": xml})
		result = get_file_content("invoice.xml", zf)
		self.assertIn("test", result)

	def test_p7m_file_extracted(self):
		from erpnext_italy.utils.sdi_import_base import get_file_content
		p7m_path = os.path.join(FIXTURES, "sample_invoice.xml.p7m")
		with open(p7m_path, "rb") as f:
			p7m_bytes = f.read()
		zf = self._make_zip({"invoice.xml.p7m": p7m_bytes})
		result = get_file_content("invoice.xml.p7m", zf)
		self.assertIn("FatturaElettronica", result)

	def test_invalid_p7m_returns_empty_string(self):
		from erpnext_italy.utils.sdi_import_base import get_file_content
		zf = self._make_zip({"bad.xml.p7m": b"not a p7m"})
		result = get_file_content("bad.xml.p7m", zf)
		self.assertEqual(result, "")


class TestXMLParsing(unittest.TestCase):
	"""get_supplier_details and get_customer_details must extract correct fields."""

	def _parsed(self):
		from bs4 import BeautifulSoup as bs
		with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
			return bs(f.read(), "xml")

	def test_get_supplier_details(self):
		from erpnext_italy.utils.sdi_import_base import get_supplier_details
		info = get_supplier_details(self._parsed())
		self.assertEqual(info["supplier"], "Test Fornitore SRL")
		self.assertEqual(info["tax_id"], "IT09876543210")
		self.assertEqual(info["city"], "Roma")
		self.assertIn("IT", info["country"])

	def test_get_customer_details(self):
		from erpnext_italy.utils.sdi_import_base import get_customer_details
		info = get_customer_details(self._parsed())
		self.assertEqual(info["customer"], "Test Cliente SRL")
		self.assertEqual(info["tax_id"], "IT01234567890")
		self.assertEqual(info["city"], "Milano")

	def test_get_taxes_from_file(self):
		from erpnext_italy.utils.sdi_import_base import get_taxes_from_file
		taxes = get_taxes_from_file(self._parsed(), "IVA 22% - IT")
		self.assertEqual(len(taxes), 1)
		self.assertEqual(taxes[0]["tax_rate"], 22.0)
		self.assertEqual(taxes[0]["tax_amount"], 22.0)
		self.assertEqual(taxes[0]["account_head"], "IVA 22% - IT")

	def test_get_destination_code(self):
		from erpnext_italy.utils.sdi_import_base import get_destination_code_from_file
		code = get_destination_code_from_file(self._parsed())
		self.assertEqual(code, "ABC1234")


class TestSDIDeliveryZIP(unittest.TestCase):
	"""End-to-end: open the sample SDI delivery ZIP and verify filtering."""

	def test_zip_filtering(self):
		from erpnext_italy.utils.sdi_import_base import _is_invoice_file
		zip_path = os.path.join(FIXTURES, "sample_sdi_delivery.zip")
		with zipfile.ZipFile(zip_path) as zf:
			all_files = zf.namelist()
			invoices = [f for f in all_files if _is_invoice_file(f)]
			skipped  = [f for f in all_files if not _is_invoice_file(f)]

		# ZIP has xml + p7m (both invoices) + RC receipt (skipped)
		self.assertEqual(len(invoices), 2)
		self.assertEqual(len(skipped), 1)
		self.assertTrue(any("RC" in s for s in skipped))

	def test_zip_p7m_content_readable(self):
		from erpnext_italy.utils.sdi_import_base import get_file_content, _is_invoice_file
		zip_path = os.path.join(FIXTURES, "sample_sdi_delivery.zip")
		with zipfile.ZipFile(zip_path) as zf:
			for name in zf.namelist():
				if not _is_invoice_file(name):
					continue
				content = get_file_content(name, zf)
				self.assertIn("FatturaElettronica", content, msg=f"Failed for {name}")
