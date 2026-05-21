"""Abstract base class for Italian SDI intermediary providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class SendResult:
    success: bool
    provider_id: str | None  # provider's internal reference
    sdi_id: str | None       # SDI protocol number
    error: str | None


@dataclass
class ReceivedInvoice:
    filename: str
    xml_bytes: bytes
    p7m_bytes: bytes | None
    provider_metadata: dict = field(default_factory=dict)


class SDIProvider(ABC):
    """Common interface for all SDI intermediary providers."""

    def __init__(self, settings_doc):
        self.settings = settings_doc

    @abstractmethod
    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        """Transmit a FatturaPA XML to the SDI via this provider."""

    @abstractmethod
    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        """Poll for inbound supplier invoices not yet acknowledged."""

    @abstractmethod
    def acknowledge_invoice(self, provider_id: str) -> bool:
        """Mark a received invoice as processed so it is not returned again."""

    def test_connection(self) -> bool:
        """Lightweight connectivity check. Override per-provider."""
        return True
