import frappe
from frappe import _
from frappe.utils import get_datetime_str
from frappe.utils.file_manager import save_file

from erpnext_italy.utils.sdi_import_base import (
	AUTOFATTURA_TYPES,
	SDIImportBase,
	create_autofattura_doc,
	get_supplier_details,
	get_destination_code_from_file,
	get_taxes_from_file,
	get_payment_terms_from_file,
	create_supplier,
	create_address,
)


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
			si_name = create_autofattura_doc(self.company, file_name, invoices_args, self.name)

			self.file_count += 1
			if si_name:
				self.invoice_count += 1
				save_file(file_name, encoded_content, "Sales Invoice",
					si_name, folder=None, decode=False, is_private=0, df=None)
