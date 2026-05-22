frappe.ui.form.on("SDI Provider Settings", {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Test Connection"), () => {
				frm.call("test_connection");
			});
		}

		if (frm.doc.test_mode) {
			frm.set_intro(
				__("Sandbox / test mode is enabled. Invoices will NOT be transmitted to the real SDI."),
				"orange"
			);
		}
	},

	provider(frm) {
		// Pre-fill known sandbox base URLs when a provider is selected
		const sandboxUrls = {
			"Aruba": "https://sandbox.fatturazioneelettronica.aruba.it/v1",
			"Wolters Kluwer": "https://sandbox.wolterskluwercloud.it/sdi/v1",
			"TeamSystem": "https://sandbox.api.teamsystem.com/sdi/v1",
		};
		const url = sandboxUrls[frm.doc.provider];
		if (url && !frm.doc.api_base_url) {
			frm.set_value("api_base_url", url);
		}
	},
});
