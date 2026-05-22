"""TeamSystem SDI provider.

Obtain API documentation from the TeamSystem developer portal before completing
this implementation. The base_url and auth_headers must be updated to match their
current API specification.
"""

import requests

import frappe

from .base import ReceivedInvoice, SDIProvider, SendResult

TS_PROD_BASE = "https://api.teamsystem.com/sdi/v1"
TS_SAND_BASE = "https://sandbox.api.teamsystem.com/sdi/v1"


class TeamSystemProvider(SDIProvider):

    @property
    def base_url(self) -> str:
        return TS_SAND_BASE if self.settings.test_mode else TS_PROD_BASE

    def _auth_headers(self) -> dict:
        api_key = frappe.utils.password.get_decrypted_password(
            "SDI Provider Settings", self.settings.name, "api_key"
        )
        api_secret = frappe.utils.password.get_decrypted_password(
            "SDI Provider Settings", self.settings.name, "api_secret"
        )
        return {
            "X-API-Key": api_key,
            "X-API-Secret": api_secret,
            "Content-Type": "application/xml",
        }

    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        # TODO: implement per TeamSystem API documentation
        raise NotImplementedError("TeamSystemProvider.send_invoice not yet implemented")

    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        # TODO: implement per TeamSystem API documentation
        raise NotImplementedError("TeamSystemProvider.fetch_received_invoices not yet implemented")

    def acknowledge_invoice(self, provider_id: str) -> bool:
        # TODO: implement per TeamSystem API documentation
        raise NotImplementedError("TeamSystemProvider.acknowledge_invoice not yet implemented")
