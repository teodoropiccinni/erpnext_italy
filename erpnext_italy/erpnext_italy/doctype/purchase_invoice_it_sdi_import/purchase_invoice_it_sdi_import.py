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


class PurchaseInvoiceItSDIImport(SDIImportBase):

	def _import_label(self):
		return "Purchase SDI Import"

	def prepare_data_for_import(self, file_content, file_name, encoded_content):
		for line in file_content.find_all("DatiGeneraliDocumento"):
			invoices_args = {
				"company": self.company,
				"naming_series": self.invoice_series,
				"document_type": line.TipoDocumento.text,
				"bill_date": get_datetime_str(line.Data.text),
				"bill_no": line.Numero.text,
				"total_discount": 0,
				"items": [],
				"buying_price_list": self.default_buying_price_list,
			}

			if not invoices_args.get("bill_no"):
				frappe.throw(_("Numero (invoice number) not found in XML file: {0}").format(file_name))

			supp_dict = get_supplier_details(file_content)
			invoices_args["destination_code"] = get_destination_code_from_file(file_content)
			self.prepare_items_for_invoice(file_content, invoices_args)
			invoices_args["taxes"] = get_taxes_from_file(file_content, self.tax_account)
			invoices_args["terms"] = get_payment_terms_from_file(file_content)

			supplier_name = create_supplier(self.supplier_group, supp_dict)
			create_address("Supplier", supplier_name, supp_dict)
			pi_name = _create_purchase_invoice(supplier_name, file_name, invoices_args, self.name)

			self.file_count += 1
			if pi_name:
				self.invoice_count += 1
				save_file(file_name, encoded_content, "Purchase Invoice",
					pi_name, folder=None, decode=False, is_private=0, df=None)


def _create_purchase_invoice(supplier_name, file_name, args, import_doc_name):
	args = frappe._dict(args)
	pi = frappe.get_doc({
		"doctype": "Purchase Invoice",
		"company": args.company,
		"currency": erpnext.get_company_currency(args.company),
		"naming_series": args.naming_series,
		"supplier": supplier_name,
		"is_return": args.get("return_invoice", 0),
		"posting_date": today(),
		"bill_no": args.bill_no,
		"buying_price_list": args.buying_price_list,
		"bill_date": args.bill_date,
		"destination_code": args.destination_code,
		"document_type": args.document_type,
		"disable_rounded_total": 1,
		"items": args["items"],
		"taxes": args["taxes"],
	})

	try:
		pi.set_missing_values()
		pi.insert(ignore_mandatory=True)

		if args.total_discount > 0:
			pi.apply_discount_on = "Grand Total"
			pi.discount_amount = args.total_discount
			pi.save()

		calc_total = sum(flt(t["payment_amount"]) for t in args.terms)
		adj = flt(calc_total - flt(pi.grand_total))
		pi.payment_schedule = []
		for term in args.terms:
			pi.append("payment_schedule", {
				"mode_of_payment_code": term["mode_of_payment_code"],
				"bank_account_iban": term["bank_account_iban"],
				"due_date": term["due_date"],
				"payment_amount": flt(term["payment_amount"]) - adj,
			})
			adj = 0
		pi.imported_grand_total = calc_total
		pi.save()
		return pi.name

	except Exception as e:
		frappe.db.set_value("Purchase Invoice It Sdi Import", import_doc_name, "status", "Error")
		frappe.log_error(
			message=e,
			title="Create Purchase Invoice: {0} | File: {1}".format(args.bill_no, file_name),
		)
		return None
