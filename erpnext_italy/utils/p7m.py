"""
P7M (CMS SignedData) extraction utilities for Italian e-invoices (CAdES-BES).

The SDI wraps FatturaPA XML in a DER-encoded ContentInfo / SignedData envelope.
This module extracts the inner XML payload without verifying the signature chain,
which is intentional: Italian law allows import even with expired certificates.
"""

import frappe
from frappe import _


def extract_xml_from_p7m(p7m_bytes: bytes) -> bytes:
	"""
	Extract the inner XML payload from a CAdES / PKCS#7 .p7m file.

	Args:
		p7m_bytes: raw bytes of the .p7m file (DER-encoded CMS SignedData)

	Returns:
		bytes: the raw FatturaPA XML payload

	Raises:
		frappe.ValidationError: if the file is not valid CMS SignedData or content is missing
	"""
	try:
		from asn1crypto import cms as asn1_cms
	except ImportError:
		frappe.throw(
			_("La libreria asn1crypto è richiesta per processare i file .p7m. Eseguire: pip install asn1crypto"),
			title=_("Dipendenza mancante"),
		)

	try:
		content_info = asn1_cms.ContentInfo.load(p7m_bytes)

		if content_info["content_type"].native != "signed_data":
			frappe.throw(
				_("Il file .p7m non contiene dati di tipo SignedData (trovato: {0}).").format(
					content_info["content_type"].native
				),
				title=_("Formato P7M non valido"),
			)

		signed_data = content_info["content"]
		econtent = signed_data["encap_content_info"]["content"]

		if econtent is None or econtent.native is None:
			frappe.throw(
				_("Nessun contenuto trovato nel file .p7m (firma detached non supportata)."),
				title=_("Errore P7M"),
			)

		# For id-data content type the eContent is an OctetString; .parsed gives the
		# OctetString object and .native returns the raw bytes.
		inner = econtent.parsed
		xml_bytes = inner.native if hasattr(inner, "native") else bytes(inner)

		if not xml_bytes:
			frappe.throw(
				_("Il payload estratto dal file .p7m è vuoto."),
				title=_("Errore P7M"),
			)

		return xml_bytes

	except frappe.exceptions.ValidationError:
		raise
	except Exception as exc:
		frappe.log_error(message=str(exc), title="P7M extraction failed")
		frappe.throw(
			_("Impossibile estrarre l'XML dal file .p7m: {0}").format(str(exc)),
			title=_("Errore P7M"),
		)


def verify_p7m_signature(p7m_bytes: bytes) -> dict:
	"""
	Read signer certificate info from a .p7m file (informational only — does not
	validate the chain or check revocation).

	Returns:
		dict with keys: valid (bool), signer_cn (str | None), errors (list[str])
	"""
	result = {"valid": False, "signer_cn": None, "errors": []}
	try:
		from asn1crypto import cms as asn1_cms

		content_info = asn1_cms.ContentInfo.load(p7m_bytes)
		signed_data = content_info["content"]
		certs = signed_data["certificates"]
		if certs:
			cert = certs[0].chosen
			result["signer_cn"] = cert.subject.human_friendly
		result["valid"] = True
	except Exception as exc:
		result["errors"].append(str(exc))
	return result
