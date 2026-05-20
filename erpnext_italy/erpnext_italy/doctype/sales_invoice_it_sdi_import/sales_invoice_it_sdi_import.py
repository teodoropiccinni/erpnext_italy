import frappe
from frappe import _
from frappe.utils import get_datetime_str
from frappe.utils.file_manager import save_file

from erpnext_italy.utils.sdi_import_base import (
	SDIImportBase,
	create_sales_invoice_doc,
	get_customer_details,
	get_destination_code_from_file,
	get_taxes_from_file,
	get_payment_terms_from_file,
	create_customer,
	create_address,
)


class SalesInvoiceItSDIImport(SDIImportBase):

	def _import_label(self):
		return "Sales SDI Import"

	def prepare_data_for_import(self, file_content, file_name, encoded_content):
		for line in file_content.find_all("DatiGeneraliDocumento"):
			invoices_args = {
				"company": self.company,
				"naming_series": self.invoice_series,
				"document_type": line.TipoDocumento.text,
				"posting_date": get_datetime_str(line.Data.text),
				"invoice_no": line.Numero.text,
				"total_discount": 0,
				"items": [],
				"selling_price_list": self.default_selling_price_list,
			}

			if not invoices_args.get("invoice_no"):
				frappe.throw(_("Numero (invoice number) not found in XML file: {0}").format(file_name))

			cust_dict = get_customer_details(file_content)
			invoices_args["destination_code"] = get_destination_code_from_file(file_content)
			self.prepare_items_for_invoice(file_content, invoices_args)
			invoices_args["taxes"] = get_taxes_from_file(file_content, self.tax_account)
			invoices_args["terms"] = get_payment_terms_from_file(file_content)

			customer_name = create_customer(self.customer_group, cust_dict)
			create_address("Customer", customer_name, cust_dict)
			si_name = create_sales_invoice_doc(customer_name, file_name, invoices_args, self.name)

			self.file_count += 1
			if si_name:
				self.invoice_count += 1
				save_file(file_name, encoded_content, "Sales Invoice",
					si_name, folder=None, decode=False, is_private=0, df=None)
