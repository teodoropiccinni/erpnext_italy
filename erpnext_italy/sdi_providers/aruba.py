"""Aruba Fatture in Cloud SDI provider.

API documentation: https://developers.aruba.it/en/fatturazione-elettronica
"""

import base64

import requests

import frappe

from .base import ReceivedInvoice, SDIProvider, SendResult

ARUBA_PROD_BASE = "https://fatturazioneelettronica.aruba.it/v1"
ARUBA_SAND_BASE = "https://sandbox.fatturazioneelettronica.aruba.it/v1"


class ArubaProvider(SDIProvider):

    @property
    def base_url(self) -> str:
        return ARUBA_SAND_BASE if self.settings.test_mode else ARUBA_PROD_BASE

    def _auth_headers(self) -> dict:
        password = frappe.utils.password.get_decrypted_password(
            "SDI Provider Settings", self.settings.name, "password"
        )
        token = base64.b64encode(
            f"{self.settings.username}:{password}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {token}",
            "Content-Type": "application/xml",
        }

    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        url = f"{self.base_url}/send"
        try:
            resp = requests.post(
                url,
                data=xml_bytes,
                headers={**self._auth_headers(), "X-Filename": filename},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return SendResult(
                success=True,
                provider_id=data.get("id"),
                sdi_id=data.get("sdi_id"),
                error=None,
            )
        except requests.HTTPError as exc:
            return SendResult(success=False, provider_id=None, sdi_id=None, error=str(exc))

    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        """Fetch unacknowledged inbound invoices from the Aruba inbox."""
        url = f"{self.base_url}/inbox"
        resp = requests.get(url, headers=self._auth_headers(), timeout=30)
        resp.raise_for_status()
        invoices = []
        for item in resp.json().get("items", []):
            xml_bytes = base64.b64decode(item.get("xml_base64", ""))
            p7m_b64 = item.get("p7m_base64")
            invoices.append(ReceivedInvoice(
                filename=item.get("filename", ""),
                xml_bytes=xml_bytes,
                p7m_bytes=base64.b64decode(p7m_b64) if p7m_b64 else None,
                provider_metadata={"id": item.get("id")},
            ))
        return invoices

    def acknowledge_invoice(self, provider_id: str) -> bool:
        url = f"{self.base_url}/inbox/{provider_id}/ack"
        resp = requests.post(url, headers=self._auth_headers(), timeout=15)
        return resp.ok

    def test_connection(self) -> bool:
        try:
            resp = requests.get(
                f"{self.base_url}/ping",
                headers=self._auth_headers(),
                timeout=10,
            )
            return resp.ok
        except requests.RequestException:
            return False
