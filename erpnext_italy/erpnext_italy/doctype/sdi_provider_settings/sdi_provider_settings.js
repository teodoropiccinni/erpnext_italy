frappe.ui.form.on("SDI Provider Settings", {
	refresh(frm) {
		if (!frm.doc.__islocal) {
			frm.add_custom_button(__("Test Connection"), () => {
				frm.call("test_connection");
			});
		}

		if (frm.doc.test_mode && frm.doc.provider !== "Wolters Kluwer") {
			frm.set_intro(
				__("Sandbox / test mode is enabled. Invoices will NOT be transmitted to the real SDI."),
				"orange"
			);
		}

		if (frm.doc.provider === "Wolters Kluwer") {
			frm.set_intro(
				__("Wolters Kluwer uses FTP/FTPS file delivery. Fill in the FTP Connection section below."),
				"blue"
			);
		}
	},

	provider(frm) {
		const sandboxUrls = {
			"Aruba": "https://sandbox.fatturazioneelettronica.aruba.it/v1",
			"TeamSystem": "https://sandbox.api.teamsystem.com/sdi/v1",
		};

		if (frm.doc.provider === "Wolters Kluwer") {
			// Clear REST API fields — not used for WK
			frm.set_value("api_base_url", "");
			frm.set_value("api_key", "");
			frm.set_value("api_secret", "");
			// Suggest sensible defaults
			if (!frm.doc.ftp_port) frm.set_value("ftp_port", 21);
			if (!frm.doc.ftp_use_ftps) frm.set_value("ftp_use_ftps", 1);
		} else {
			const url = sandboxUrls[frm.doc.provider];
			if (url && !frm.doc.api_base_url) {
				frm.set_value("api_base_url", url);
			}
		}
	},
});
