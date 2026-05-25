"""
Tests for erpnext_italy.install — lifecycle functions (after_install, after_migrate,
before_uninstall) and custom-field management.

Run with:
    bench --site <site> run-tests --app erpnext_italy --module erpnext_italy.tests.test_install
"""

import unittest
from unittest.mock import MagicMock, call, patch


class TestMakeCustomFields(unittest.TestCase):
    """make_custom_fields must include all expected doctypes and key fieldnames."""

    def _get_custom_fields_dict(self):
        """Call make_custom_fields with a spy on create_custom_fields."""
        from erpnext_italy.install import make_custom_fields
        captured = {}

        def fake_create(fields_dict, **kw):
            captured.update(fields_dict)

        with patch(
            "erpnext_italy.install.create_custom_fields",
            side_effect=fake_create,
        ), patch("frappe.flags", MagicMock(in_patch=False)):
            make_custom_fields()

        return captured

    def test_covers_expected_doctypes(self):
        fields = self._get_custom_fields_dict()
        for dt in (
            "Company", "Sales Invoice", "Purchase Invoice", "Customer",
            "Supplier", "Address", "Payment Schedule",
        ):
            self.assertIn(dt, fields, msg=f"Missing DocType: {dt}")

    def test_sales_invoice_has_einvoice_status(self):
        fields = self._get_custom_fields_dict()
        names = [f["fieldname"] for f in fields["Sales Invoice"]]
        self.assertIn("einvoice_status", names)
        self.assertIn("sdi_transmission_id", names)

    def test_purchase_invoice_has_sdi_import_id(self):
        fields = self._get_custom_fields_dict()
        names = [f["fieldname"] for f in fields["Purchase Invoice"]]
        self.assertIn("sdi_import_id", names)
        self.assertIn("document_type", names)
        self.assertIn("destination_code", names)
        self.assertIn("imported_grand_total", names)

    def test_supplier_has_fiscal_code(self):
        fields = self._get_custom_fields_dict()
        names = [f["fieldname"] for f in fields["Supplier"]]
        self.assertIn("fiscal_code", names)
        self.assertIn("fiscal_regime", names)

    def test_address_has_state_code(self):
        fields = self._get_custom_fields_dict()
        names = [f["fieldname"] for f in fields["Address"]]
        self.assertIn("state_code", names)
        self.assertIn("country_code", names)


class TestAddPermissions(unittest.TestCase):
    """add_permissions must cover the four SDI import DocTypes."""

    def test_permissions_added_for_all_sdi_doctypes(self):
        from erpnext_italy.install import add_permissions

        added = []
        with patch("erpnext_italy.install.add_permission", side_effect=lambda *a, **kw: added.append(a[0])), \
             patch("erpnext_italy.install.update_permission_property"):
            add_permissions()

        for dt in (
            "Purchase Invoice It Sdi Import",
            "Sales Invoice It Sdi Import",
            "Foreign Purchase Invoice It Sdi Import",
            "SDI Bulk Import",
        ):
            self.assertIn(dt, added, msg=f"No permission added for: {dt}")

    def test_import_supplier_invoice_no_longer_referenced(self):
        from erpnext_italy.install import add_permissions

        added = []
        with patch("erpnext_italy.install.add_permission", side_effect=lambda *a, **kw: added.append(a[0])), \
             patch("erpnext_italy.install.update_permission_property"):
            add_permissions()

        self.assertNotIn("Import Supplier Invoice", added)


class TestAfterInstall(unittest.TestCase):

    def test_after_install_calls_all_setup_functions(self):
        from erpnext_italy import install as install_mod

        with patch.object(install_mod, "make_custom_fields") as m_cf, \
             patch.object(install_mod, "setup_report") as m_sr, \
             patch.object(install_mod, "add_permissions") as m_ap:
            install_mod.after_install()

        m_cf.assert_called_once()
        m_sr.assert_called_once()
        m_ap.assert_called_once()


class TestAfterMigrate(unittest.TestCase):

    def test_after_migrate_reruns_custom_fields_and_permissions(self):
        from erpnext_italy import install as install_mod

        with patch.object(install_mod, "make_custom_fields") as m_cf, \
             patch.object(install_mod, "add_permissions") as m_ap, \
             patch("frappe.db.commit"):
            install_mod.after_migrate()

        m_cf.assert_called_once_with(update=True)
        m_ap.assert_called_once()

    def test_after_migrate_is_safe_to_call_twice(self):
        """Calling after_migrate twice must not raise."""
        from erpnext_italy import install as install_mod

        with patch.object(install_mod, "make_custom_fields"), \
             patch.object(install_mod, "add_permissions"), \
             patch("frappe.db.commit"):
            install_mod.after_migrate()
            install_mod.after_migrate()  # second call — must not raise


class TestBeforeUninstall(unittest.TestCase):

    def test_before_uninstall_removes_known_fields(self):
        from erpnext_italy import install as install_mod

        deleted = []

        def fake_db_exists(doctype, name):
            return True  # pretend every field exists

        def fake_delete(doctype, name, **kw):
            deleted.append(name)

        with patch("frappe.db.exists", side_effect=fake_db_exists), \
             patch("frappe.delete_doc", side_effect=fake_delete), \
             patch("frappe.db.commit"):
            install_mod.before_uninstall()

        # Spot-check a few critical field names
        self.assertIn("Sales Invoice-einvoice_status", deleted)
        self.assertIn("Sales Invoice-sdi_transmission_id", deleted)
        self.assertIn("Purchase Invoice-sdi_import_id", deleted)
        self.assertIn("Supplier-fiscal_code", deleted)
        self.assertIn("Address-state_code", deleted)

    def test_before_uninstall_skips_nonexistent_fields(self):
        """If a custom field doesn't exist, no exception is raised."""
        from erpnext_italy import install as install_mod

        with patch("frappe.db.exists", return_value=False), \
             patch("frappe.delete_doc") as m_del, \
             patch("frappe.db.commit"):
            install_mod.before_uninstall()

        m_del.assert_not_called()
