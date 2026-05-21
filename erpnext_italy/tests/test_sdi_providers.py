"""
Tests for erpnext_italy.sdi_providers — provider registry, base class, Aruba implementation.

Run with:
    bench --site <site> run-tests --app erpnext_italy --module erpnext_italy.tests.test_sdi_providers
"""

import unittest
from unittest.mock import MagicMock, patch


def _make_settings(provider="Aruba", test_mode=True):
    s = MagicMock()
    s.name = "test-settings"
    s.provider = provider
    s.company = "Test Company SRL"
    s.is_active = 1
    s.test_mode = test_mode
    s.username = "testuser"
    s.api_base_url = ""
    return s


class TestSDIProviderBase(unittest.TestCase):

    def test_base_is_abstract(self):
        from erpnext_italy.sdi_providers.base import SDIProvider
        with self.assertRaises(TypeError):
            SDIProvider(_make_settings())  # abstract — cannot instantiate

    def test_send_result_fields(self):
        from erpnext_italy.sdi_providers.base import SendResult
        r = SendResult(success=True, provider_id="abc", sdi_id="SDI-1", error=None)
        self.assertTrue(r.success)
        self.assertEqual(r.provider_id, "abc")

    def test_received_invoice_defaults(self):
        from erpnext_italy.sdi_providers.base import ReceivedInvoice
        inv = ReceivedInvoice(filename="test.xml", xml_bytes=b"<xml/>", p7m_bytes=None)
        self.assertEqual(inv.provider_metadata, {})


class TestArubaProvider(unittest.TestCase):

    def test_base_url_sandbox(self):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider, ARUBA_SAND_BASE
        p = ArubaProvider(_make_settings(test_mode=True))
        self.assertEqual(p.base_url, ARUBA_SAND_BASE)

    def test_base_url_production(self):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider, ARUBA_PROD_BASE
        p = ArubaProvider(_make_settings(test_mode=False))
        self.assertEqual(p.base_url, ARUBA_PROD_BASE)

    @patch("requests.post")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_send_invoice_success(self, _mock_pwd, mock_post):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "abc123", "sdi_id": "SDI-001"},
            raise_for_status=lambda: None,
        )
        provider = ArubaProvider(_make_settings())
        result = provider.send_invoice(b"<xml/>", "IT01234567890_00001.xml")
        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "abc123")
        self.assertEqual(result.sdi_id, "SDI-001")
        self.assertIsNone(result.error)

    @patch("requests.post")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_send_invoice_http_error(self, _mock_pwd, mock_post):
        import requests as req_lib
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_post.return_value = MagicMock(
            status_code=401,
            raise_for_status=MagicMock(side_effect=req_lib.HTTPError("401 Unauthorized")),
        )
        provider = ArubaProvider(_make_settings())
        result = provider.send_invoice(b"<xml/>", "test.xml")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
        self.assertIn("401", result.error)

    @patch("requests.get")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_fetch_received_invoices_empty(self, _mock_pwd, mock_get):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": []},
            raise_for_status=lambda: None,
        )
        provider = ArubaProvider(_make_settings())
        invoices = provider.fetch_received_invoices()
        self.assertEqual(invoices, [])

    @patch("requests.get")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_fetch_received_invoices_with_items(self, _mock_pwd, mock_get):
        import base64
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        xml_b64 = base64.b64encode(b"<FatturaElettronica/>").decode()
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"items": [{"id": "inv-1", "filename": "IT_00001.xml", "xml_base64": xml_b64}]},
            raise_for_status=lambda: None,
        )
        provider = ArubaProvider(_make_settings())
        invoices = provider.fetch_received_invoices()
        self.assertEqual(len(invoices), 1)
        self.assertEqual(invoices[0].filename, "IT_00001.xml")
        self.assertEqual(invoices[0].xml_bytes, b"<FatturaElettronica/>")
        self.assertIsNone(invoices[0].p7m_bytes)

    @patch("requests.post")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_acknowledge_invoice_ok(self, _mock_pwd, mock_post):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_post.return_value = MagicMock(ok=True)
        provider = ArubaProvider(_make_settings())
        self.assertTrue(provider.acknowledge_invoice("inv-1"))

    @patch("requests.get")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_test_connection_success(self, _mock_pwd, mock_get):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_get.return_value = MagicMock(ok=True)
        provider = ArubaProvider(_make_settings())
        self.assertTrue(provider.test_connection())

    @patch("requests.get")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_test_connection_failure(self, _mock_pwd, mock_get):
        import requests as req_lib
        from erpnext_italy.sdi_providers.aruba import ArubaProvider
        mock_get.side_effect = req_lib.ConnectionError("unreachable")
        provider = ArubaProvider(_make_settings())
        self.assertFalse(provider.test_connection())


class TestRegistry(unittest.TestCase):

    def test_unknown_provider_raises(self):
        from erpnext_italy.sdi_providers.registry import PROVIDERS
        self.assertNotIn("Unknown", PROVIDERS)

    def test_all_known_providers_registered(self):
        from erpnext_italy.sdi_providers.registry import PROVIDERS
        for name in ("Aruba", "Wolters Kluwer", "TeamSystem"):
            self.assertIn(name, PROVIDERS)

    def test_get_provider_no_settings_raises(self):
        from erpnext_italy.sdi_providers.registry import get_provider
        with patch("frappe.db.get_value", return_value=None), \
             patch("frappe.throw", side_effect=Exception("No settings")):
            with self.assertRaises(Exception):
                get_provider("Nonexistent Company")


class TestWKAndTeamSystemNotImplemented(unittest.TestCase):
    """Stubs raise NotImplementedError until API docs are obtained."""

    def _provider(self, cls_path):
        from importlib import import_module
        module_path, cls_name = cls_path.rsplit(".", 1)
        mod = import_module(module_path)
        return getattr(mod, cls_name)(_make_settings())

    def test_wolters_kluwer_send_not_implemented(self):
        p = self._provider("erpnext_italy.sdi_providers.wolters_kluwer.WoltersKluwerProvider")
        with self.assertRaises(NotImplementedError):
            p.send_invoice(b"<xml/>", "test.xml")

    def test_teamsystem_send_not_implemented(self):
        p = self._provider("erpnext_italy.sdi_providers.teamsystem.TeamSystemProvider")
        with self.assertRaises(NotImplementedError):
            p.send_invoice(b"<xml/>", "test.xml")
