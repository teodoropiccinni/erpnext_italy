frappe.ui.form.on("SDI Bulk Import", {
	refresh(frm) {
		if (frm.doc.status === "Draft" && !frm.doc.__islocal) {
			frm.add_custom_button(__("Start Import"), () => {
				frappe.confirm(
					__("Start bulk import for {0} ZIP file(s)?", [frm.doc.zip_files.length]),
					() => {
						frm.call("start_import").then(() => {
							frappe.show_alert({
								message: __("Import queued. You will be notified on completion."),
								indicator: "blue",
							});
							frm.refresh();
						});
					}
				);
			}, __("Actions"));
		}

		if (frm.doc.status === "Processing") {
			frm.disable_save();
			frm.set_intro(__("Import is running in the background…"), "blue");
		}

		frappe.realtime.on("sdi_bulk_import_complete", (data) => {
			if (data.docname === frm.docname) {
				frappe.show_alert({
					message: __("Bulk import completed: {0}", [data.status]),
					indicator: data.errors > 0 ? "orange" : "green",
				});
				frm.refresh();
			}
		});
	},

	import_type(frm) {
		// Update invoice_series default based on import type
		if (frm.doc.import_type === "purchase") {
			frm.set_value("invoice_series", "ACC-PINV-.YYYY.-");
		} else {
			frm.set_value("invoice_series", "ACC-SINV-.YYYY.-");
		}
	},
});
