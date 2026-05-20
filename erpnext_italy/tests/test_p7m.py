"""
Tests for erpnext_italy.utils.p7m — CMS SignedData extraction.

Run with:
    bench --site <site> run-tests --app erpnext_italy --module erpnext_italy.tests.test_p7m
"""

import os
import unittest

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestP7MExtraction(unittest.TestCase):

	def setUp(self):
		with open(os.path.join(FIXTURES, "sample_invoice.xml.p7m"), "rb") as f:
			self.p7m_bytes = f.read()
		with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
			self.expected_xml = f.read()

	def test_extract_returns_bytes(self):
		from erpnext_italy.utils.p7m import extract_xml_from_p7m
		xml = extract_xml_from_p7m(self.p7m_bytes)
		self.assertIsInstance(xml, bytes)

	def test_extracted_contains_fattura_elettronica(self):
		from erpnext_italy.utils.p7m import extract_xml_from_p7m
		xml = extract_xml_from_p7m(self.p7m_bytes)
		self.assertIn(b"FatturaElettronica", xml)

	def test_extracted_contains_invoice_data(self):
		from erpnext_italy.utils.p7m import extract_xml_from_p7m
		xml = extract_xml_from_p7m(self.p7m_bytes)
		self.assertIn(b"Test Fornitore SRL", xml)
		self.assertIn(b"TD01", xml)

	def test_invalid_bytes_raises_validation_error(self):
		import frappe
		from erpnext_italy.utils.p7m import extract_xml_from_p7m
		with self.assertRaises(frappe.exceptions.ValidationError):
			extract_xml_from_p7m(b"this is not a valid p7m file")

	def test_verify_signature_returns_dict(self):
		from erpnext_italy.utils.p7m import verify_p7m_signature
		result = verify_p7m_signature(self.p7m_bytes)
		self.assertIn("valid", result)
		self.assertIn("signer_cn", result)
		self.assertIn("errors", result)
		self.assertIsInstance(result["errors"], list)

	def test_verify_signature_finds_signer_cn(self):
		from erpnext_italy.utils.p7m import verify_p7m_signature
		result = verify_p7m_signature(self.p7m_bytes)
		self.assertTrue(result["valid"])
		self.assertIsNotNone(result["signer_cn"])
		self.assertIn("Test SDI Signer", result["signer_cn"])
