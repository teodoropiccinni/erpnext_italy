import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime


class SDIBulkImport(Document):

	def validate(self):
		if not self.zip_files:
			frappe.throw(_("Add at least one ZIP file before starting the import."))

	@frappe.whitelist()
	def start_import(self):
		if self.status != "Draft":
			frappe.throw(_("Import has already been started."))

		self.db_set("status", "Processing", notify=True, commit=True)
		self.db_set("started_at", now_datetime(), commit=True)
		self.db_set("total_files", len(self.zip_files), commit=True)

		frappe.enqueue_doc(
			self.doctype,
			self.name,
			"_run_bulk_import",
			queue="long",
			timeout=7200,
		)

	def _run_bulk_import(self):
		from erpnext_italy.utils.sdi_import_base import process_zip_bytes

		config = self._build_config()
		processed = 0
		errors = 0

		for row in self.zip_files:
			row.db_set("status", "Processing", commit=True)
			try:
				file_doc = frappe.get_doc("File", {"file_url": row.zip_file})
				with open(file_doc.get_full_path(), "rb") as fh:
					zip_bytes = fh.read()

				result = process_zip_bytes(zip_bytes, self.import_type, config)

				row.db_set("status", "Imported", commit=True)
				row.db_set("invoices_imported", result["invoice_count"], commit=True)
				if result["errors"]:
					row.db_set(
						"error_message",
						"; ".join(e["error"] for e in result["errors"])[:500],
						commit=True,
					)
				processed += 1

			except Exception as exc:
				row.db_set("status", "Error", commit=True)
				row.db_set("error_message", str(exc)[:500], commit=True)
				errors += 1
				frappe.log_error(
					message=exc,
					title="SDI Bulk Import error: {0}".format(row.zip_file),
				)

		final_status = "Completed with Errors" if errors else "Completed"
		self.db_set("status", final_status, notify=True, commit=True)
		self.db_set("completed_at", now_datetime(), commit=True)
		self.db_set("processed_files", processed, commit=True)
		self.db_set("error_files", errors, commit=True)

		frappe.publish_realtime(
			event="sdi_bulk_import_complete",
			message={
				"docname": self.name,
				"status": final_status,
				"processed": processed,
				"errors": errors,
			},
			user=self.owner,
		)

	def _build_config(self) -> dict:
		return {
			"company": self.company,
			"invoice_series": self.invoice_series,
			"item_code": self.item_code,
			"tax_account": self.tax_account,
			"default_uom": frappe.db.get_value("Stock Settings", fieldname="stock_uom") or "Nos",
			"supplier_group": self.supplier_group,
			"customer_group": self.customer_group,
			"default_buying_price_list": self.default_buying_price_list,
			"default_selling_price_list": self.default_selling_price_list,
		}
