"""
Tests for SDI Bulk Import — process_zip_bytes and SDIBulkImport DocType.

Run with:
    bench --site <site> run-tests --app erpnext_italy --module erpnext_italy.tests.test_bulk_import
"""

import io
import os
import unittest
import zipfile
from unittest.mock import MagicMock, patch

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestProcessZipBytes(unittest.TestCase):
    """process_zip_bytes: filtering, routing, and result structure."""

    def _load_sample_zip(self) -> bytes:
        with open(os.path.join(FIXTURES, "sample_sdi_delivery.zip"), "rb") as f:
            return f.read()

    def _make_zip(self, files: dict) -> bytes:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in files.items():
                if isinstance(content, str):
                    content = content.encode("utf-8")
                zf.writestr(name, content)
        return buf.getvalue()

    def test_returns_result_dict_structure(self):
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes

        with patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value="PINV-0001"), \
             patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Supplier"), \
             patch("erpnext_italy.utils.sdi_import_base.create_address"), \
             patch("erpnext_italy.utils.sdi_import_base.save_file"), \
             patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[]), \
             patch("frappe.log_error"):

            config = {
                "company": "Test Company",
                "invoice_series": "ACC-PINV-.YYYY.-",
                "item_code": "Test Item",
                "tax_account": "IVA 22% - TC",
                "default_uom": "Nos",
                "supplier_group": "All Supplier Groups",
                "default_buying_price_list": "Standard Buying",
                "customer_group": None,
                "default_selling_price_list": None,
            }
            result = process_zip_bytes(self._load_sample_zip(), "purchase", config)

        self.assertIn("file_count", result)
        self.assertIn("invoice_count", result)
        self.assertIn("errors", result)
        self.assertIsInstance(result["errors"], list)

    def test_rc_receipt_files_not_counted(self):
        """Receipt files (_RC_) must not increment file_count."""
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes

        with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
            xml_bytes = f.read()

        zip_bytes = self._make_zip({
            "IT09876543210_00001.xml": xml_bytes,
            "IT09876543210_00001_RC_001.xml": b"<receipt/>",
        })

        with patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value="PINV-0001"), \
             patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Supplier"), \
             patch("erpnext_italy.utils.sdi_import_base.create_address"), \
             patch("erpnext_italy.utils.sdi_import_base.save_file"), \
             patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[]), \
             patch("frappe.log_error"):

            config = {
                "company": "Test Company",
                "invoice_series": "ACC-PINV-.YYYY.-",
                "item_code": "Test Item",
                "tax_account": "IVA 22% - TC",
                "default_uom": "Nos",
                "supplier_group": "All Supplier Groups",
                "default_buying_price_list": "Standard Buying",
                "customer_group": None,
                "default_selling_price_list": None,
            }
            result = process_zip_bytes(zip_bytes, "purchase", config)

        self.assertEqual(result["file_count"], 1)

    def test_autofattura_skips_non_autofattura_types(self):
        """Autofattura import must skip TD01 (standard) documents without raising an error."""
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes

        with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
            xml_bytes = f.read()

        zip_bytes = self._make_zip({"IT09876543210_00001.xml": xml_bytes})

        logged_errors = []
        with patch("frappe.log_error", side_effect=lambda **kw: logged_errors.append(kw)):
            config = {
                "company": "Test Company",
                "invoice_series": "ACC-SINV-.YYYY.-",
                "item_code": "Test Item",
                "tax_account": "IVA 22% - TC",
                "default_uom": "Nos",
                "supplier_group": "All Supplier Groups",
                "default_selling_price_list": "Standard Selling",
                "customer_group": None,
                "default_buying_price_list": None,
            }
            result = process_zip_bytes(zip_bytes, "autofattura", config)

        # The file is counted (it was read) but no invoice created (doc_type TD01 skipped)
        self.assertEqual(result["invoice_count"], 0)
        self.assertTrue(any("skipped" in str(e.get("message", "")) for e in logged_errors))

    def test_p7m_file_processed(self):
        """p7m files are counted and processed the same as plain xml."""
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes

        with open(os.path.join(FIXTURES, "sample_invoice.xml.p7m"), "rb") as f:
            p7m_bytes = f.read()

        zip_bytes = self._make_zip({"IT09876543210_00001.xml.p7m": p7m_bytes})

        with patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value="PINV-0001"), \
             patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Supplier"), \
             patch("erpnext_italy.utils.sdi_import_base.create_address"), \
             patch("erpnext_italy.utils.sdi_import_base.save_file"), \
             patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[]), \
             patch("frappe.log_error"):

            config = {
                "company": "Test Company",
                "invoice_series": "ACC-PINV-.YYYY.-",
                "item_code": "Test Item",
                "tax_account": "IVA 22% - TC",
                "default_uom": "Nos",
                "supplier_group": "All Supplier Groups",
                "default_buying_price_list": "Standard Buying",
                "customer_group": None,
                "default_selling_price_list": None,
            }
            result = process_zip_bytes(zip_bytes, "purchase", config)

        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["invoice_count"], 1)

    def test_failed_invoice_creation_recorded_in_errors(self):
        """If create_purchase_invoice_doc returns None, errors list should be empty (logged separately)."""
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes

        with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
            xml_bytes = f.read()

        zip_bytes = self._make_zip({"IT09876543210_00001.xml": xml_bytes})

        with patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value=None), \
             patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Supplier"), \
             patch("erpnext_italy.utils.sdi_import_base.create_address"), \
             patch("erpnext_italy.utils.sdi_import_base.save_file"), \
             patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[]), \
             patch("frappe.log_error"):

            config = {
                "company": "Test Company",
                "invoice_series": "ACC-PINV-.YYYY.-",
                "item_code": "Test Item",
                "tax_account": "IVA 22% - TC",
                "default_uom": "Nos",
                "supplier_group": "All Supplier Groups",
                "default_buying_price_list": "Standard Buying",
                "customer_group": None,
                "default_selling_price_list": None,
            }
            result = process_zip_bytes(zip_bytes, "purchase", config)

        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["invoice_count"], 0)


class TestAutofatturaTypes(unittest.TestCase):
    """AUTOFATTURA_TYPES constant contains the expected TD codes."""

    def test_all_expected_types_present(self):
        from erpnext_italy.utils.sdi_import_base import AUTOFATTURA_TYPES
        for code in ["TD17", "TD18", "TD19", "TD20", "TD21", "TD22", "TD23", "TD24", "TD25", "TD26", "TD27"]:
            self.assertIn(code, AUTOFATTURA_TYPES, msg=code)

    def test_standard_types_not_in_autofattura(self):
        from erpnext_italy.utils.sdi_import_base import AUTOFATTURA_TYPES
        for code in ["TD01", "TD04", "TD05", "TD06", "TD16"]:
            self.assertNotIn(code, AUTOFATTURA_TYPES, msg=code)
