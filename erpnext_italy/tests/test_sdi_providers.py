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


def _make_wk_settings():
    s = MagicMock()
    s.name = "test-wk-settings"
    s.provider = "Wolters Kluwer"
    s.company = "Test Company SRL"
    s.is_active = 1
    s.test_mode = False
    s.username = "ftpuser"
    s.ftp_host = "ftp.wolterskluwer.example.com"
    s.ftp_port = 21
    s.ftp_use_ftps = False
    s.ftp_upload_path = "/outgoing"
    s.ftp_inbox_path = "/incoming"
    s.ftp_processed_path = "/processed"
    return s


class TestWoltersKluwerProvider(unittest.TestCase):

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_send_invoice_success(self, mock_ftp_cls, _mock_pwd):
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        mock_ftp = MagicMock()
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(_make_wk_settings())
        result = provider.send_invoice(b"<xml/>", "IT_00001.xml")

        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "/outgoing/IT_00001.xml")
        mock_ftp.storbinary.assert_called_once()
        mock_ftp.quit.assert_called_once()

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_send_invoice_ftp_error(self, mock_ftp_cls, _mock_pwd):
        import ftplib as ftplib_mod
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        mock_ftp = MagicMock()
        mock_ftp.storbinary.side_effect = ftplib_mod.error_perm("550 Permission denied")
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(_make_wk_settings())
        result = provider.send_invoice(b"<xml/>", "IT_00001.xml")

        self.assertFalse(result.success)
        self.assertIn("550", result.error)

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_fetch_received_invoices_xml_and_p7m(self, mock_ftp_cls, _mock_pwd):
        import io as io_mod
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider

        xml_content = b"<FatturaElettronica/>"
        p7m_content = b"\x30\x82\x00\x01"  # fake p7m bytes

        def fake_retrbinary(cmd, callback):
            name = cmd.split()[-1]
            if name.endswith(".xml"):
                callback(xml_content)
            else:
                callback(p7m_content)

        mock_ftp = MagicMock()
        mock_ftp.nlst.return_value = ["IT_00001.xml", "IT_00001.xml.p7m", "readme.txt"]
        mock_ftp.retrbinary.side_effect = fake_retrbinary
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(_make_wk_settings())
        invoices = provider.fetch_received_invoices()

        self.assertEqual(len(invoices), 2)
        xml_inv = next(i for i in invoices if i.filename.endswith(".xml") and not i.filename.endswith(".p7m"))
        p7m_inv = next(i for i in invoices if i.filename.endswith(".p7m"))
        self.assertEqual(xml_inv.xml_bytes, xml_content)
        self.assertIsNone(xml_inv.p7m_bytes)
        self.assertEqual(p7m_inv.p7m_bytes, p7m_content)
        self.assertEqual(p7m_inv.xml_bytes, b"")

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_acknowledge_moves_to_processed(self, mock_ftp_cls, _mock_pwd):
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        mock_ftp = MagicMock()
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(_make_wk_settings())
        ok = provider.acknowledge_invoice("/incoming/IT_00001.xml")

        self.assertTrue(ok)
        mock_ftp.rename.assert_called_once_with(
            "/incoming/IT_00001.xml", "/processed/IT_00001.xml"
        )

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_acknowledge_deletes_when_no_processed_path(self, mock_ftp_cls, _mock_pwd):
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        settings = _make_wk_settings()
        settings.ftp_processed_path = ""
        mock_ftp = MagicMock()
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(settings)
        ok = provider.acknowledge_invoice("/incoming/IT_00001.xml")

        self.assertTrue(ok)
        mock_ftp.delete.assert_called_once_with("/incoming/IT_00001.xml")
        mock_ftp.rename.assert_not_called()

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_connection_success(self, mock_ftp_cls, _mock_pwd):
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        mock_ftp_cls.return_value = MagicMock()
        provider = WoltersKluwerProvider(_make_wk_settings())
        self.assertTrue(provider.test_connection())

    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    @patch("ftplib.FTP")
    def test_connection_failure(self, mock_ftp_cls, _mock_pwd):
        import ftplib as ftplib_mod
        from erpnext_italy.sdi_providers.wolters_kluwer import WoltersKluwerProvider
        mock_ftp = MagicMock()
        mock_ftp.connect.side_effect = ftplib_mod.error_temp("421 Service not available")
        mock_ftp_cls.return_value = mock_ftp

        provider = WoltersKluwerProvider(_make_wk_settings())
        self.assertFalse(provider.test_connection())


class TestTeamSystemNotImplemented(unittest.TestCase):
    """TeamSystem stub raises NotImplementedError until API docs are obtained."""

    def test_send_not_implemented(self):
        from erpnext_italy.sdi_providers.teamsystem import TeamSystemProvider
        p = TeamSystemProvider(_make_settings())
        with self.assertRaises(NotImplementedError):
            p.send_invoice(b"<xml/>", "test.xml")
