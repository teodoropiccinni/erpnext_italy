"""
Tests for the three SDI import DocType controllers:
  PurchaseInvoiceItSDIImport
  SalesInvoiceItSDIImport
  ForeignPurchaseInvoiceItSDIImport

Frappe database calls are fully mocked so these tests run without a bench.

Run with:
    bench --site <site> run-tests --app erpnext_italy \
          --module erpnext_italy.tests.test_sdi_import_doctypes
"""

import os
import unittest
from unittest.mock import MagicMock, patch, call

from bs4 import BeautifulSoup as bs

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def _load_xml():
    with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
        return bs(f.read(), "xml")


def _make_import_doc(**overrides):
    """Build a minimal mock import document."""
    doc = MagicMock()
    doc.company = "Test Company SRL"
    doc.invoice_series = "ACC-PINV-.YYYY.-"
    doc.item_code = "Default Item"
    doc.supplier_group = "All Supplier Groups"
    doc.customer_group = "All Customer Groups"
    doc.tax_account = "IVA 22% - TC"
    doc.default_buying_price_list = "Standard Buying"
    doc.default_selling_price_list = "Standard Selling"
    doc.default_uom = "Nos"
    doc.file_count = 0
    doc.invoice_count = 0
    doc.name = "TEST-IMPORT-0001"
    doc.doctype = "Purchase Invoice It Sdi Import"
    for k, v in overrides.items():
        setattr(doc, k, v)
    return doc


# ---------------------------------------------------------------------------
# PurchaseInvoiceItSDIImport
# ---------------------------------------------------------------------------

class TestPurchaseInvoiceImport(unittest.TestCase):

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Fornitore SRL")
    @patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value="PINV-0001")
    @patch("frappe.utils.file_manager.save_file")
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_prepare_data_increments_counters(self, _terms, _save, mock_create, mock_supp, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.purchase_invoice_it_sdi_import.purchase_invoice_it_sdi_import import (
            PurchaseInvoiceItSDIImport,
        )
        doc = _make_import_doc()
        xml = _load_xml()
        PurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        self.assertEqual(doc.file_count, 1)
        self.assertEqual(doc.invoice_count, 1)

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Fornitore SRL")
    @patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value=None)
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_failed_creation_increments_file_not_invoice(self, _terms, mock_create, mock_supp, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.purchase_invoice_it_sdi_import.purchase_invoice_it_sdi_import import (
            PurchaseInvoiceItSDIImport,
        )
        doc = _make_import_doc()
        xml = _load_xml()
        PurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        self.assertEqual(doc.file_count, 1)
        self.assertEqual(doc.invoice_count, 0)

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Test Fornitore SRL")
    @patch("erpnext_italy.utils.sdi_import_base.create_purchase_invoice_doc", return_value="PINV-0001")
    @patch("frappe.utils.file_manager.save_file")
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_supplier_created_with_correct_group(self, _terms, _save, mock_create, mock_supp, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.purchase_invoice_it_sdi_import.purchase_invoice_it_sdi_import import (
            PurchaseInvoiceItSDIImport,
        )
        doc = _make_import_doc(supplier_group="Foreign Suppliers")
        xml = _load_xml()
        PurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        self.assertEqual(mock_supp.call_args[0][0], "Foreign Suppliers")

    @patch("frappe.throw")
    def test_missing_numero_raises(self, mock_throw):
        from erpnext_italy.erpnext_italy.doctype.purchase_invoice_it_sdi_import.purchase_invoice_it_sdi_import import (
            PurchaseInvoiceItSDIImport,
        )
        xml_str = """<?xml version="1.0"?>
        <FatturaElettronica>
          <FatturaElettronicaBody>
            <DatiGenerali>
              <DatiGeneraliDocumento>
                <TipoDocumento>TD01</TipoDocumento>
                <Data>2026-01-15</Data>
                <Numero></Numero>
              </DatiGeneraliDocumento>
            </DatiGenerali>
          </FatturaElettronicaBody>
        </FatturaElettronica>"""
        doc = _make_import_doc()
        xml = bs(xml_str.encode(), "xml")
        PurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "test.xml", b"")
        mock_throw.assert_called_once()


# ---------------------------------------------------------------------------
# SalesInvoiceItSDIImport
# ---------------------------------------------------------------------------

class TestSalesInvoiceImport(unittest.TestCase):

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_customer", return_value="Test Cliente SRL")
    @patch("erpnext_italy.utils.sdi_import_base.create_sales_invoice_doc", return_value="SINV-0001")
    @patch("frappe.utils.file_manager.save_file")
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_prepare_data_increments_counters(self, _terms, _save, mock_create, mock_cust, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.sales_invoice_it_sdi_import.sales_invoice_it_sdi_import import (
            SalesInvoiceItSDIImport,
        )
        doc = _make_import_doc(doctype="Sales Invoice It Sdi Import")
        xml = _load_xml()
        SalesInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        self.assertEqual(doc.file_count, 1)
        self.assertEqual(doc.invoice_count, 1)

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_customer", return_value="Test Cliente SRL")
    @patch("erpnext_italy.utils.sdi_import_base.create_sales_invoice_doc", return_value="SINV-0001")
    @patch("frappe.utils.file_manager.save_file")
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_customer_created_with_correct_group(self, _terms, _save, mock_create, mock_cust, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.sales_invoice_it_sdi_import.sales_invoice_it_sdi_import import (
            SalesInvoiceItSDIImport,
        )
        doc = _make_import_doc(customer_group="Italian Customers", doctype="Sales Invoice It Sdi Import")
        xml = _load_xml()
        SalesInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        self.assertEqual(mock_cust.call_args[0][0], "Italian Customers")


# ---------------------------------------------------------------------------
# ForeignPurchaseInvoiceItSDIImport
# ---------------------------------------------------------------------------

class TestForeignPurchaseInvoiceImport(unittest.TestCase):

    def _make_xml(self, doc_type: str) -> bs:
        with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
            content = f.read().replace(b"<TipoDocumento>TD01</TipoDocumento>",
                                       f"<TipoDocumento>{doc_type}</TipoDocumento>".encode())
        return bs(content, "xml")

    @patch("erpnext_italy.utils.sdi_import_base.create_address")
    @patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="Foreign Supplier")
    @patch("erpnext_italy.utils.sdi_import_base.create_autofattura_doc", return_value="SINV-AUTO-0001")
    @patch("frappe.utils.file_manager.save_file")
    @patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[])
    def test_td17_creates_autofattura(self, _terms, _save, mock_auto, mock_supp, mock_addr):
        from erpnext_italy.erpnext_italy.doctype.foreign_purchase_invoice_it_sdi_import.foreign_purchase_invoice_it_sdi_import import (
            ForeignPurchaseInvoiceItSDIImport,
        )
        doc = _make_import_doc(doctype="Foreign Purchase Invoice It Sdi Import")
        xml = self._make_xml("TD17")
        ForeignPurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        mock_auto.assert_called_once()
        self.assertEqual(doc.file_count, 1)
        self.assertEqual(doc.invoice_count, 1)

    @patch("frappe.log_error")
    def test_td01_skipped_with_log(self, mock_log):
        from erpnext_italy.erpnext_italy.doctype.foreign_purchase_invoice_it_sdi_import.foreign_purchase_invoice_it_sdi_import import (
            ForeignPurchaseInvoiceItSDIImport,
        )
        doc = _make_import_doc(doctype="Foreign Purchase Invoice It Sdi Import")
        xml = self._make_xml("TD01")
        ForeignPurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")

        # file_count stays 0 because TD01 is skipped before incrementing
        self.assertEqual(doc.file_count, 0)
        self.assertEqual(doc.invoice_count, 0)
        mock_log.assert_called_once()

    def test_all_autofattura_types_accepted(self):
        """Every TD17–TD27 code must reach create_autofattura_doc without being skipped."""
        from erpnext_italy.utils.sdi_import_base import AUTOFATTURA_TYPES
        from erpnext_italy.erpnext_italy.doctype.foreign_purchase_invoice_it_sdi_import.foreign_purchase_invoice_it_sdi_import import (
            ForeignPurchaseInvoiceItSDIImport,
        )

        for code in AUTOFATTURA_TYPES:
            with patch("erpnext_italy.utils.sdi_import_base.create_address"), \
                 patch("erpnext_italy.utils.sdi_import_base.create_supplier", return_value="S"), \
                 patch("erpnext_italy.utils.sdi_import_base.create_autofattura_doc", return_value="SI-1") as mock_auto, \
                 patch("frappe.utils.file_manager.save_file"), \
                 patch("erpnext_italy.utils.sdi_import_base.get_payment_terms_from_file", return_value=[]):

                doc = _make_import_doc(doctype="Foreign Purchase Invoice It Sdi Import")
                xml = self._make_xml(code)
                ForeignPurchaseInvoiceItSDIImport.prepare_data_for_import(doc, xml, "IT_00001.xml", b"<xml/>")
                mock_auto.assert_called_once(), f"{code} did not call create_autofattura_doc"


# ---------------------------------------------------------------------------
# SDIImportBase shared logic
# ---------------------------------------------------------------------------

class TestSDIImportBaseItems(unittest.TestCase):
    """prepare_items_for_invoice must correctly parse DettaglioLinee."""

    def test_single_line_item_parsed(self):
        from erpnext_italy.utils.sdi_import_base import SDIImportBase
        doc = MagicMock()
        doc.item_code = "Default Item"
        doc.default_uom = "Nos"

        args = {"items": [], "total_discount": 0}
        xml = _load_xml()
        SDIImportBase.prepare_items_for_invoice(doc, xml, args)

        self.assertEqual(len(args["items"]), 1)
        item = args["items"][0]
        self.assertEqual(item["item_code"], "Default Item")
        self.assertAlmostEqual(item["rate"], 100.0)
        self.assertAlmostEqual(item["tax_rate"], 22.0)

    def test_negative_price_sets_return_flag(self):
        from erpnext_italy.utils.sdi_import_base import SDIImportBase
        doc = MagicMock()
        doc.item_code = "Default Item"
        doc.default_uom = "Nos"

        xml_str = """<root>
          <DettaglioLinee>
            <NumeroLinea>1</NumeroLinea>
            <Descrizione>Nota credito</Descrizione>
            <PrezzoUnitario>-50.00</PrezzoUnitario>
            <PrezzoTotale>-50.00</PrezzoTotale>
            <AliquotaIVA>22.00</AliquotaIVA>
          </DettaglioLinee>
        </root>"""
        xml = bs(xml_str, "xml")
        args = {"items": [], "total_discount": 0}
        SDIImportBase.prepare_items_for_invoice(doc, xml, args)

        self.assertEqual(args.get("return_invoice"), 1)
        self.assertGreater(args["items"][0]["rate"], 0)  # rate stored as abs
