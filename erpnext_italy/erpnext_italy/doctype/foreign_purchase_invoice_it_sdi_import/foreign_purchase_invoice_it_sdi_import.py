import frappe
import erpnext
from frappe import _
from frappe.utils import flt, get_datetime_str, today
from frappe.utils.file_manager import save_file

from erpnext_italy.utils.sdi_import_base import (
	SDIImportBase,
	get_supplier_details,
	get_destination_code_from_file,
	get_taxes_from_file,
	get_payment_terms_from_file,
	create_supplier,
	create_address,
)

# Only these TipoDocumento values represent autofattura / reverse-charge self-invoices.
# Files with any other code are logged and skipped without raising an error.
AUTOFATTURA_TYPES = frozenset({
	"TD17", "TD18", "TD19", "TD20", "TD21", "TD22",
	"TD23", "TD24", "TD25", "TD26", "TD27",
})


class ForeignPurchaseInvoiceItSDIImport(SDIImportBase):

	def _import_label(self):
		return "Autofattura SDI Import"

	def prepare_data_for_import(self, file_content, file_name, encoded_content):
		for line in file_content.find_all("DatiGeneraliDocumento"):
			doc_type = line.TipoDocumento.text

			if doc_type not in AUTOFATTURA_TYPES:
				frappe.log_error(
					message=(
						"File {0}: TipoDocumento '{1}' is not an autofattura type — skipped. "
						"Use Purchase Invoice IT SDI Import for standard supplier invoices."
					).format(file_name, doc_type),
					title="Foreign Purchase SDI Import: skipped non-autofattura document",
				)
				continue

			invoices_args = {
				"company": self.company,
				"naming_series": self.invoice_series,
				"document_type": doc_type,
				"posting_date": get_datetime_str(line.Data.text),
				"bill_no": line.Numero.text,
				"total_discount": 0,
				"items": [],
				"selling_price_list": self.default_selling_price_list,
			}

			supp_dict = get_supplier_details(file_content)
			invoices_args["destination_code"] = get_destination_code_from_file(file_content)
			self.prepare_items_for_invoice(file_content, invoices_args)
			invoices_args["taxes"] = get_taxes_from_file(file_content, self.tax_account)
			invoices_args["terms"] = get_payment_terms_from_file(file_content)

			supplier_name = create_supplier(self.supplier_group, supp_dict)
			create_address("Supplier", supplier_name, supp_dict)
			si_name = _create_autofattura(self.company, file_name, invoices_args, self.name)

			self.file_count += 1
			if si_name:
				self.invoice_count += 1
				save_file(file_name, encoded_content, "Sales Invoice",
					si_name, folder=None, decode=False, is_private=0, df=None)


def _create_autofattura(company, file_name, args, import_doc_name):
	"""
	Create a Sales Invoice for autofattura.

	The company self-invoices for services/goods from foreign suppliers.
	Italian accounting registers this in the sales register (registro vendite),
	hence it becomes a Sales Invoice — the customer is the company itself.
	"""
	args = frappe._dict(args)

	# The company must have a linked Customer record (itself).
	# Look up by company name first; fall back to company name as customer name.
	self_customer = (
		frappe.db.get_value("Customer", {"customer_name": company}, "name")
		or company
	)

	si = frappe.get_doc({
		"doctype": "Sales Invoice",
		"company": company,
		"currency": erpnext.get_company_currency(company),
		"naming_series": args.naming_series,
		"customer": self_customer,
		"posting_date": args.posting_date or today(),
		"selling_price_list": args.selling_price_list,
		"destination_code": args.destination_code,
		"document_type": args.document_type,
		"disable_rounded_total": 1,
		"items": args["items"],
		"taxes": args["taxes"],
	})

	try:
		si.set_missing_values()
		si.insert(ignore_mandatory=True)
		si.save()
		return si.name

	except Exception as e:
		frappe.db.set_value(
			"Foreign Purchase Invoice It Sdi Import", import_doc_name, "status", "Error"
		)
		frappe.log_error(
			message=e,
			title="Create Autofattura: {0} | File: {1}".format(args.bill_no, file_name),
		)
		return None
