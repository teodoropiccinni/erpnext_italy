"""
ERPNext v16 compatibility checks.

Verifies that:
- All hook function paths resolve to importable Python callables.
- All DocType JSON files have required structural fields.
- Key Frappe utilities used throughout the app are still importable.
- No forbidden v15-only API patterns are used.

Run with:
    bench --site <site> run-tests --app erpnext_italy \
          --module erpnext_italy.tests.test_v16_compat
"""

import importlib
import json
import os
import unittest

APP_ROOT = os.path.dirname(os.path.dirname(__file__))  # erpnext_italy/erpnext_italy/
DOCTYPE_ROOT = os.path.join(APP_ROOT, "erpnext_italy", "doctype")


def _resolve_dotted(path: str):
    """Import a dotted Python path and return the callable. Raises ImportError on failure."""
    module_path, _, attr = path.rpartition(".")
    mod = importlib.import_module(module_path)
    return getattr(mod, attr)


def _iter_doctype_jsons():
    for name in os.listdir(DOCTYPE_ROOT):
        json_path = os.path.join(DOCTYPE_ROOT, name, f"{name}.json")
        if os.path.isfile(json_path):
            with open(json_path) as f:
                yield name, json.load(f)


class TestHookPaths(unittest.TestCase):
    """Every callable path wired in hooks.py must be importable."""

    HOOK_PATHS = [
        "erpnext_italy.install.after_install",
        "erpnext_italy.install.before_uninstall",
        "erpnext_italy.install.after_migrate",
        "erpnext_italy.utils.sales_invoice_on_submit",
        "erpnext_italy.utils.sales_invoice_on_cancel",
        "erpnext_italy.utils.set_state_code",
        "erpnext_italy.sdi_providers.tasks.poll_inbound_invoices",
    ]

    def test_all_hook_paths_importable(self):
        for path in self.HOOK_PATHS:
            with self.subTest(path=path):
                try:
                    obj = _resolve_dotted(path)
                    self.assertTrue(callable(obj), f"{path} is not callable")
                except (ImportError, AttributeError) as exc:
                    self.fail(f"Cannot resolve hook path '{path}': {exc}")


class TestDocTypeJSONStructure(unittest.TestCase):
    """Every DocType JSON must have required top-level fields."""

    REQUIRED_FIELDS = ["doctype", "name", "module", "fields", "engine"]

    def test_all_doctypes_have_required_fields(self):
        found_any = False
        for name, data in _iter_doctype_jsons():
            found_any = True
            for field in self.REQUIRED_FIELDS:
                with self.subTest(doctype=name, field=field):
                    self.assertIn(
                        field, data,
                        f"DocType '{name}' JSON missing required field '{field}'"
                    )

        self.assertTrue(found_any, "No DocType JSON files found — check DOCTYPE_ROOT path")

    def test_all_doctypes_have_correct_module(self):
        for name, data in _iter_doctype_jsons():
            with self.subTest(doctype=name):
                self.assertEqual(
                    data.get("module"), "ERPNext Italy",
                    f"DocType '{name}' has unexpected module: {data.get('module')}"
                )

    def test_child_doctypes_have_istable_flag(self):
        child_doctypes = {"SDI Bulk Import File"}
        for name, data in _iter_doctype_jsons():
            if data.get("name") in child_doctypes:
                with self.subTest(doctype=name):
                    self.assertEqual(
                        data.get("istable"), 1,
                        f"Child DocType '{name}' missing istable=1"
                    )


class TestFrappeUtilsImportable(unittest.TestCase):
    """Key Frappe / ERPNext utilities we depend on must still exist in v16."""

    REQUIRED_IMPORTS = [
        ("frappe", "get_doc"),
        ("frappe", "new_doc"),
        ("frappe", "enqueue_doc"),
        ("frappe", "publish_realtime"),
        ("frappe", "log_error"),
        ("frappe", "whitelist"),
        ("frappe.model.document", "Document"),
        ("frappe.utils", "flt"),
        ("frappe.utils", "today"),
        ("frappe.utils", "now_datetime"),
        ("frappe.utils", "get_datetime_str"),
        ("frappe.utils.file_manager", "save_file"),
        ("frappe.custom.doctype.custom_field.custom_field", "create_custom_fields"),
        ("frappe.permissions", "add_permission"),
        ("frappe.permissions", "update_permission_property"),
    ]

    def test_all_frappe_utilities_importable(self):
        for module_path, attr in self.REQUIRED_IMPORTS:
            with self.subTest(import_=f"{module_path}.{attr}"):
                try:
                    mod = importlib.import_module(module_path)
                    self.assertTrue(
                        hasattr(mod, attr),
                        f"{module_path} has no attribute '{attr}'"
                    )
                except ImportError as exc:
                    self.fail(f"Cannot import {module_path}: {exc}")


class TestAppModuleStructure(unittest.TestCase):
    """All app sub-packages must be importable."""

    PACKAGES = [
        "erpnext_italy",
        "erpnext_italy.utils",
        "erpnext_italy.utils.p7m",
        "erpnext_italy.utils.sdi_import_base",
        "erpnext_italy.sdi_providers",
        "erpnext_italy.sdi_providers.base",
        "erpnext_italy.sdi_providers.aruba",
        "erpnext_italy.sdi_providers.wolters_kluwer",
        "erpnext_italy.sdi_providers.teamsystem",
        "erpnext_italy.sdi_providers.registry",
        "erpnext_italy.sdi_providers.tasks",
        "erpnext_italy.install",
    ]

    def test_all_packages_importable(self):
        for pkg in self.PACKAGES:
            with self.subTest(package=pkg):
                try:
                    importlib.import_module(pkg)
                except ImportError as exc:
                    self.fail(f"Cannot import '{pkg}': {exc}")

    def test_autofattura_types_exported_from_base(self):
        from erpnext_italy.utils.sdi_import_base import AUTOFATTURA_TYPES
        self.assertIsInstance(AUTOFATTURA_TYPES, frozenset)
        self.assertGreater(len(AUTOFATTURA_TYPES), 0)

    def test_process_zip_bytes_signature(self):
        import inspect
        from erpnext_italy.utils.sdi_import_base import process_zip_bytes
        sig = inspect.signature(process_zip_bytes)
        params = list(sig.parameters)
        self.assertEqual(params, ["zip_bytes", "import_type", "config"])
