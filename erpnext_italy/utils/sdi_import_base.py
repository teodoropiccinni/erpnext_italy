"""
Shared base class and helper functions for Italian SDI e-invoice import DocTypes.

Three DocTypes extend SDIImportBase:
  PurchaseInvoiceItSDIImport         → Purchase Invoice (inbound supplier invoices)
  SalesInvoiceItSDIImport            → Sales Invoice (outbound XML migration / reconciliation)
  ForeignPurchaseInvoiceItSDIImport  → Sales Invoice (autofattura, TD17-TD27)

See EINVOICING.md for full feature design and XML field mapping.
"""

import re
import zipfile

import dateutil.parser
import frappe
from bs4 import BeautifulSoup as bs
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, today
from frappe.utils.data import format_datetime

from erpnext_italy.utils.p7m import extract_xml_from_p7m


# ---------------------------------------------------------------------------
# Base document class
# ---------------------------------------------------------------------------

class SDIImportBase(Document):

	def validate(self):
		if not frappe.db.get_value("Stock Settings", fieldname="stock_uom"):
			frappe.throw(_("Please set default UOM in Stock Settings"))

	def autoname(self):
		if not self.name:
			self.name = self._import_label() + " on " + format_datetime(self.creation)

	def _import_label(self):
		return "SDI Import"

	def import_xml_data(self):
		zip_file = frappe.get_doc("File", {
			"file_url": self.zip_file,
			"attached_to_doctype": self.doctype,
			"attached_to_name": self.name,
		})

		self.publish("File Import", _("Processing XML Files"), 1, 3)
		self.file_count = 0
		self.invoice_count = 0
		self.default_uom = frappe.db.get_value("Stock Settings", fieldname="stock_uom")

		with zipfile.ZipFile(zip_file.get_full_path()) as zf:
			for file_name in zf.namelist():
				if not _is_invoice_file(file_name):
					continue
				content = get_file_content(file_name, zf)
				if not content:
					continue
				file_content = bs(content, "xml")
				self.prepare_data_for_import(file_content, file_name, content)

		if self.invoice_count == self.file_count:
			self.status = "File Import Completed"
		else:
			self.status = "Partially Completed - Check Error Log"

		self.publish("File Import", _("XML Files Processed"), 2, 3)
		self.save()
		self.publish("File Import", _("XML Files Processed"), 3, 3)

	def prepare_data_for_import(self, file_content, file_name, encoded_content):
		"""Override in each subclass to create the appropriate ERPNext invoice."""
		raise NotImplementedError

	def prepare_items_for_invoice(self, file_content, invoices_args):
		"""Parse DettaglioLinee line items — identical logic for all three DocTypes."""
		qty = 1
		rate = tax_rate = 0
		uom = self.default_uom

		for line in file_content.find_all("DettaglioLinee"):
			if not (line.find("PrezzoUnitario") and line.find("PrezzoTotale")):
				continue

			rate = flt(line.PrezzoUnitario.text) or 0
			line_total = flt(line.PrezzoTotale.text) or 0

			if rate and flt(line_total) / rate != 1.0 and line.find("Quantita"):
				qty = flt(line.Quantita.text) or 0
				if line.find("UnitaMisura"):
					uom = create_uom(line.UnitaMisura.text)

			if rate < 0 and line_total < 0:
				qty *= -1
				invoices_args["return_invoice"] = 1

			if line.find("AliquotaIVA"):
				tax_rate = flt(line.AliquotaIVA.text)

			line_str = re.sub(r'[^A-Za-z0-9]+', '-', line.Descrizione.text)
			item_name = line_str[:140]

			invoices_args["items"].append({
				"item_code": self.item_code,
				"item_name": item_name,
				"description": line_str,
				"qty": qty,
				"uom": uom,
				"rate": abs(rate),
				"conversion_factor": 1.0,
				"tax_rate": tax_rate,
			})

			for disc_line in line.find_all("ScontoMaggiorazione"):
				if disc_line.find("Percentuale"):
					invoices_args["total_discount"] += flt(
						(flt(disc_line.Percentuale.text) / 100) * (rate * qty)
					)

	@frappe.whitelist()
	def process_file_data(self):
		self.db_set("status", "Processing File Data", notify=True, commit=True)
		frappe.enqueue_doc(self.doctype, self.name, "import_xml_data", queue="long", timeout=3600)

	def publish(self, title, message, count, total):
		frappe.publish_realtime(
			"import_invoice_update",
			{"title": title, "message": message, "count": count, "total": total},
		)


# ---------------------------------------------------------------------------
# File handling
# ---------------------------------------------------------------------------

def _is_invoice_file(file_name: str) -> bool:
	"""Return True only for actual FatturaPA invoice files.

	SDI delivery ZIPs include receipt/notification files (_RC_, _NS_, _MC_) whose XML
	structure differs from FatturaPA. They must be skipped.
	"""
	lower = file_name.lower()
	if lower.endswith(".xml.p7m"):
		return True
	if lower.endswith(".xml"):
		return not re.search(r'_[A-Z]{2}_\d+\.xml$', file_name)
	return False


def get_file_content(file_name: str, zip_file_object) -> str:
	"""Read a ZIP entry and return decoded XML string.

	Handles both plain .xml (UTF-8/UTF-16) and .xml.p7m (CMS SignedData).
	Returns empty string on decode failure (error is logged).
	"""
	encoded_content = zip_file_object.read(file_name)

	if file_name.lower().endswith(".p7m"):
		try:
			xml_bytes = extract_xml_from_p7m(encoded_content)
		except Exception as e:
			frappe.log_error(message=e, title="P7M extraction error: " + file_name)
			return ""
		try:
			return xml_bytes.decode("utf-8-sig")
		except UnicodeDecodeError:
			return xml_bytes.decode("utf-16")

	try:
		return encoded_content.decode("utf-8-sig")
	except UnicodeDecodeError:
		try:
			return encoded_content.decode("utf-16")
		except UnicodeDecodeError as e:
			frappe.log_error(message=e, title="UTF-16 encoding error: " + file_name)
	return ""


# ---------------------------------------------------------------------------
# XML data extraction helpers
# ---------------------------------------------------------------------------

def get_supplier_details(file_content) -> dict:
	"""Extract supplier identity from CedentePrestatore."""
	for line in file_content.find_all("CedentePrestatore"):
		info = {}
		dati = line.DatiAnagrafici
		if dati.find("IdFiscaleIVA"):
			info["tax_id"] = dati.IdFiscaleIVA.IdPaese.text + dati.IdFiscaleIVA.IdCodice.text
		elif dati.find("IdPaese") and dati.find("IdCodice"):
			info["tax_id"] = dati.IdPaese.text + dati.IdCodice.text
		else:
			info["tax_id"] = ""
		if dati.find("CodiceFiscale"):
			info["fiscal_code"] = dati.CodiceFiscale.text
		if dati.find("RegimeFiscale"):
			info["fiscal_regime"] = dati.RegimeFiscale.text
		if dati.Anagrafica.find("Denominazione"):
			info["supplier"] = dati.Anagrafica.Denominazione.text
		elif dati.Anagrafica.find("Nome"):
			info["supplier"] = dati.Anagrafica.Nome.text + " " + dati.Anagrafica.Cognome.text
		info["address_line1"] = line.Sede.Indirizzo.text
		info["city"] = line.Sede.Comune.text
		if line.Sede.find("Provincia"):
			info["province"] = line.Sede.Provincia.text
		info["pin_code"] = line.Sede.CAP.text
		info["country"] = get_country(line.Sede.Nazione.text)
		return info
	return {}


def get_customer_details(file_content) -> dict:
	"""Extract customer identity from CessionarioCommittente."""
	for line in file_content.find_all("CessionarioCommittente"):
		info = {}
		dati = line.DatiAnagrafici
		if dati.find("IdFiscaleIVA"):
			info["tax_id"] = dati.IdFiscaleIVA.IdPaese.text + dati.IdFiscaleIVA.IdCodice.text
		if dati.find("CodiceFiscale"):
			info["fiscal_code"] = dati.CodiceFiscale.text
		if dati.Anagrafica.find("Denominazione"):
			info["customer"] = dati.Anagrafica.Denominazione.text
		elif dati.Anagrafica.find("Nome"):
			info["customer"] = dati.Anagrafica.Nome.text + " " + dati.Anagrafica.Cognome.text
		if line.find("Sede"):
			info["address_line1"] = line.Sede.Indirizzo.text
			info["city"] = line.Sede.Comune.text
			if line.Sede.find("Provincia"):
				info["province"] = line.Sede.Provincia.text
			info["pin_code"] = line.Sede.CAP.text
			info["country"] = get_country(line.Sede.Nazione.text)
		return info
	return {}


def get_taxes_from_file(file_content, tax_account: str) -> list:
	taxes = []
	for line in file_content.find_all("DatiRiepilogo"):
		if not line.find("AliquotaIVA"):
			continue
		descr = line.EsigibilitaIVA.text if line.find("EsigibilitaIVA") else "None"
		imposta_tag = line.find("Imposta")
		taxes.append({
			"charge_type": "Actual",
			"account_head": tax_account,
			"tax_rate": flt(line.AliquotaIVA.text) or 0,
			"description": descr,
			"tax_amount": flt(imposta_tag.text) if imposta_tag else 0,
		})
	return taxes


def get_payment_terms_from_file(file_content) -> list:
	terms = []
	mop_options = frappe.get_meta("Mode of Payment").fields[4].options
	mop_str = re.sub(r'\n', ',', mop_options)
	mop_dict = dict(item.split("-") for item in mop_str.split(",") if "-" in item)
	for line in file_content.find_all("DettaglioPagamento"):
		mop_code = line.ModalitaPagamento.text + "-" + mop_dict.get(line.ModalitaPagamento.text, "")
		if line.find("DataScadenzaPagamento"):
			due_date = dateutil.parser.parse(line.DataScadenzaPagamento.text).strftime("%Y-%m-%d")
		else:
			due_date = today()
		terms.append({
			"mode_of_payment_code": mop_code,
			"bank_account_iban": line.IBAN.text if line.find("IBAN") else "",
			"due_date": due_date,
			"payment_amount": line.ImportoPagamento.text,
		})
	return terms


def get_destination_code_from_file(file_content) -> str:
	for line in file_content.find_all("DatiTrasmissione"):
		return line.CodiceDestinatario.text
	return ""


# ---------------------------------------------------------------------------
# Party creation helpers
# ---------------------------------------------------------------------------

def create_supplier(supplier_group: str, args: dict) -> str:
	"""Upsert Supplier record. Matches by tax_id first, then by name."""
	args = frappe._dict(args)
	existing = (
		frappe.db.get_value("Supplier", {"tax_id": args.tax_id}, "name")
		if args.get("tax_id")
		else None
	) or frappe.db.get_value("Supplier", {"name": args.supplier}, "name")

	if existing:
		_ensure_contact("Supplier", existing, args.supplier)
		return existing

	new_supplier = frappe.new_doc("Supplier")
	new_supplier.supplier_name = re.sub(r'&amp;?', '&', args.supplier)
	new_supplier.supplier_group = supplier_group
	new_supplier.tax_id = args.get("tax_id", "")
	new_supplier.fiscal_code = args.get("fiscal_code", "")
	new_supplier.fiscal_regime = args.get("fiscal_regime", "")
	new_supplier.save()
	_ensure_contact("Supplier", new_supplier.name, args.supplier)
	return new_supplier.name


def create_customer(customer_group: str, args: dict) -> str:
	"""Upsert Customer record. Matches by tax_id first, then by name."""
	args = frappe._dict(args)
	existing = (
		frappe.db.get_value("Customer", {"tax_id": args.tax_id}, "name")
		if args.get("tax_id")
		else None
	) or frappe.db.get_value("Customer", {"name": args.customer}, "name")

	if existing:
		return existing

	new_customer = frappe.new_doc("Customer")
	new_customer.customer_name = re.sub(r'&amp;?', '&', args.customer)
	new_customer.customer_group = customer_group
	if args.get("tax_id"):
		new_customer.tax_id = args.tax_id
	new_customer.save()
	return new_customer.name


def create_address(party_type: str, party_name: str, args: dict):
	"""Upsert billing Address for a Supplier or Customer."""
	args = frappe._dict(args)
	if not args.get("address_line1"):
		return None

	filters = [
		["Dynamic Link", "link_doctype", "=", party_type],
		["Dynamic Link", "link_name", "=", party_name],
		["Dynamic Link", "parenttype", "=", "Address"],
	]
	for existing in frappe.get_list("Address", filters):
		addr = frappe.get_doc("Address", existing["name"])
		if addr.address_line1 == args.address_line1 and addr.pincode == args.get("pin_code"):
			return existing["name"]

	new_addr = frappe.new_doc("Address")
	new_addr.address_line1 = args.address_line1
	new_addr.city = args.city or "Not Provided"
	for field, src in [("province", "province"), ("pincode", "pin_code"), ("country", "country")]:
		if args.get(src):
			new_addr.set(field, args.get(src))
	new_addr.append("links", {"link_doctype": party_type, "link_name": party_name})
	new_addr.address_type = "Billing"
	new_addr.insert(ignore_mandatory=True)
	return new_addr.name


# ---------------------------------------------------------------------------
# Misc helpers
# ---------------------------------------------------------------------------

def create_uom(uom: str) -> str:
	existing = frappe.db.get_value("UOM", {"uom_name": uom}, "uom_name")
	if existing:
		return existing
	doc = frappe.new_doc("UOM")
	doc.uom_name = uom
	doc.save()
	return doc.uom_name


def get_country(code: str) -> str:
	name = frappe.db.get_value("Country", {"code": code}, "name")
	if name:
		return name
	frappe.throw(_("Country code '{0}' not found in ERPNext. Add it in Country master.").format(code))


def _ensure_contact(party_type: str, party_name: str, display_name: str):
	"""Create a Contact linked to the party if none exists."""
	if frappe.get_list("Contact", filters=[
		["Dynamic Link", "link_doctype", "=", party_type],
		["Dynamic Link", "link_name", "=", party_name],
		["Dynamic Link", "parenttype", "=", "Contact"],
	]):
		return
	c = frappe.new_doc("Contact")
	c.first_name = display_name[:30]
	c.append("links", {"link_doctype": party_type, "link_name": party_name})
	c.insert(ignore_mandatory=True)
