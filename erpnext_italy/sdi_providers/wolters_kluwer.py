"""Wolters Kluwer (formerly Ipsoa) SDI provider — FTP/FTPS file delivery.

Wolters Kluwer delivers and receives FatturaPA files via an FTP server:
- Outgoing invoices: upload XML/p7m to the configured upload folder.
- Incoming invoices: poll the inbox folder, download all XML/p7m files,
  then move each processed file to the processed folder (or delete it).

Configure in SDI Provider Settings:
  - ftp_host / ftp_port (default 21)
  - username / password
  - ftp_use_ftps (enable FTPS / FTP over TLS)
  - ftp_upload_path  — remote folder for outgoing invoices
  - ftp_inbox_path   — remote folder where WK places incoming invoices
  - ftp_processed_path — remote folder to move processed files to
                         (leave empty to delete instead of move)
"""

import ftplib
import io

import frappe

from .base import ReceivedInvoice, SDIProvider, SendResult

_INVOICE_EXTS = (".xml", ".p7m")


class WoltersKluwerProvider(SDIProvider):

    # ------------------------------------------------------------------
    # FTP connection context manager
    # ------------------------------------------------------------------

    def _connect(self) -> ftplib.FTP:
        password = frappe.utils.password.get_decrypted_password(
            "SDI Provider Settings", self.settings.name, "password"
        )
        host = self.settings.ftp_host
        port = int(self.settings.ftp_port or 21)

        if self.settings.ftp_use_ftps:
            ftp = ftplib.FTP_TLS()
            ftp.connect(host, port, timeout=30)
            ftp.login(self.settings.username, password)
            ftp.prot_p()  # enable encrypted data channel
        else:
            ftp = ftplib.FTP()
            ftp.connect(host, port, timeout=30)
            ftp.login(self.settings.username, password)

        return ftp

    # ------------------------------------------------------------------
    # SDIProvider interface
    # ------------------------------------------------------------------

    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        upload_path = (self.settings.ftp_upload_path or "").rstrip("/")
        remote_path = f"{upload_path}/{filename}" if upload_path else filename

        try:
            ftp = self._connect()
            try:
                ftp.storbinary(f"STOR {remote_path}", io.BytesIO(xml_bytes))
            finally:
                ftp.quit()

            return SendResult(
                success=True,
                provider_id=remote_path,
                sdi_id=None,
                error=None,
            )
        except ftplib.all_errors as exc:
            return SendResult(success=False, provider_id=None, sdi_id=None, error=str(exc))

    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        inbox_path = (self.settings.ftp_inbox_path or "").rstrip("/")
        invoices = []

        ftp = self._connect()
        try:
            if inbox_path:
                ftp.cwd(inbox_path)

            filenames = ftp.nlst()
            for name in filenames:
                lower = name.lower()
                if not any(lower.endswith(ext) for ext in _INVOICE_EXTS):
                    continue

                buf = io.BytesIO()
                ftp.retrbinary(f"RETR {name}", buf.write)
                raw = buf.getvalue()

                is_p7m = lower.endswith(".p7m")
                remote_full = f"{inbox_path}/{name}" if inbox_path else name

                invoices.append(ReceivedInvoice(
                    filename=name,
                    xml_bytes=b"" if is_p7m else raw,
                    p7m_bytes=raw if is_p7m else None,
                    provider_metadata={"remote_path": remote_full},
                ))
        finally:
            ftp.quit()

        return invoices

    def acknowledge_invoice(self, provider_id: str) -> bool:
        """Move the file to ftp_processed_path, or delete it if that path is not set."""
        processed_path = (self.settings.ftp_processed_path or "").rstrip("/")
        remote_path = provider_id  # stored as the full remote path in provider_metadata

        try:
            ftp = self._connect()
            try:
                if processed_path:
                    filename = remote_path.rsplit("/", 1)[-1]
                    dest = f"{processed_path}/{filename}"
                    ftp.rename(remote_path, dest)
                else:
                    ftp.delete(remote_path)
            finally:
                ftp.quit()
            return True
        except ftplib.all_errors as exc:
            frappe.log_error(
                message=exc,
                title="WK FTP acknowledge error: " + remote_path,
            )
            return False

    def test_connection(self) -> bool:
        try:
            ftp = self._connect()
            ftp.quit()
            return True
        except ftplib.all_errors:
            return False
