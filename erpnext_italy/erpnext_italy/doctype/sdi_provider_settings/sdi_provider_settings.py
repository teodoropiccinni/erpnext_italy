import frappe
from frappe import _
from frappe.model.document import Document


class SDIProviderSettings(Document):

    def validate(self):
        if self.is_active:
            # Only one active provider per company
            existing = frappe.db.get_value(
                "SDI Provider Settings",
                {"company": self.company, "is_active": 1, "name": ("!=", self.name)},
                "name",
            )
            if existing:
                frappe.throw(
                    _("Company {0} already has an active SDI Provider Settings ({1}). "
                      "Deactivate it before activating this one.").format(
                        self.company, existing
                    )
                )

    @frappe.whitelist()
    def test_connection(self):
        from erpnext_italy.sdi_providers.registry import get_provider
        try:
            provider = get_provider(self.company)
            ok = provider.test_connection()
            if ok:
                frappe.msgprint(_("Connection successful."), indicator="green", alert=True)
            else:
                frappe.msgprint(_("Connection failed. Check credentials and base URL."),
                                indicator="red", alert=True)
        except Exception as exc:
            frappe.msgprint(str(exc), indicator="red", alert=True)
