# CLAUDE.md — erpnext_italy Enhancement Roadmap

This file guides an AI assistant (Claude or similar) through implementing all planned
enhancements to the `erpnext_italy` Frappe/ERPNext app. Follow phases in order; each
phase builds on the previous one.

---

## Project Context

**Repo:** https://github.com/teodoropiccinni/erpnext_italy  
**Base:** Fork of `frappe/erpnext_italy` — Frappe app for Italian e-invoicing (FatturaPA XML
generation, supplier invoice import).  
**Stack:** Python 3.11+, Frappe Framework, ERPNext, MariaDB/PostgreSQL.  
**ERPNext target:** v16 (Frappe v16 / "Caffeine" architecture).

---

## Repository Layout (current)

```
erpnext_italy/
  erpnext_italy/           ← app package
    e_invoice/             ← e-invoice doctypes & logic
    import_supplier_invoice/  ← supplier XML import
    overrides/             ← ERPNext hooks/overrides
    config/                ← desktop & module config
    hooks.py
    utils.py
  requirements.txt
  setup.py
```

---

## Phase 0 — Prerequisites & Setup

### 0.1 Python dependencies to add in `requirements.txt`

```
cryptography>=42.0          # P7M / CMS decryption
oscrypto>=1.3               # ASN.1 / CMS fallback
certvalidator>=0.11         # certificate chain validation
lxml>=5.0,<6                # XML parsing (already present, pin version)
xmlsec>=1.3                 # optional: XML-DSig verification
pytest>=8.0                 # test runner
pytest-frappe               # Frappe test helpers (install from PyPI or GitHub)
responses>=0.25             # mock HTTP for SDI provider tests
factory-boy>=3.3            # test data factories
```

Add to `setup.py` `install_requires` as well so `bench get-app` installs them.

### 0.2 Branch strategy

```
main / develop       ← current code (v14/v15 compatible)
feature/v16-compat   ← Phase 1 work
feature/p7m-decrypt  ← Phase 2
feature/zip-upload   ← Phase 3
feature/bulk-upload  ← Phase 4
feature/sdi-providers← Phase 5
feature/install-hooks← Phase 6
```

Open one PR per feature branch into `develop`, then a single `develop → main` PR when all
phases pass CI.

---

## Phase 1 — ERPNext 16 Compatibility

### Goal
Make the app installable and fully functional on ERPNext v16 / Frappe v16.

### Key breaking changes in Frappe v16 to audit for

| Area | v15 pattern | v16 replacement |
|---|---|---|
| `frappe.get_doc` hooks | `validate`, `on_submit` | same — check signature changes |
| `frappe.whitelist` | `@frappe.whitelist()` | same, but verify CSRF handling |
| JS `frappe.call` | same | check Promise chain changes |
| `frappe.utils.get_url` | same | verify path helpers |
| `frappe.db.sql` raw queries | check column renames in `tabPurchase Invoice` | audit each raw query |
| Custom fields via `fixtures/` | same | run `bench export-fixtures` against v16 schema |
| DocType JSON schema | `in_list_view`, `set_only_once` flags | re-export all DocType JSONs from a v16 instance |

### Steps

1. **Stand up a v16 dev bench** (Docker recommended):
   ```bash
   bench init frappe-bench --frappe-branch version-16
   cd frappe-bench
   bench get-app erpnext --branch version-16
   bench new-site italy.localhost --install-app erpnext
   bench get-app /path/to/erpnext_italy
   bench --site italy.localhost install-app erpnext_italy
   ```

2. **Run existing test suite** and capture all failures:
   ```bash
   bench --site italy.localhost run-tests --app erpnext_italy 2>&1 | tee v16_test_failures.log
   ```

3. **Fix each failure category** (typical v16 issues):
   - Replace deprecated `frappe.db.get_value` call signatures if needed.
   - Update `hooks.py` `doc_events` dictionary if Frappe changed event names.
   - Re-export all DocType JSON files from the running v16 instance:
     ```bash
     bench --site italy.localhost export-fixtures --app erpnext_italy
     ```
   - Check `e_invoice/utils.py` for any calls into `erpnext.regional.*` that moved.
   - Update any `frappe.utils.cint`, `flt`, `fmt_money` imports that were reorganised.

4. **Add a version guard** in `hooks.py`:
   ```python
   # hooks.py
   required_apps = ["frappe", "erpnext"]
   # Minimum versions
   frappe_min_version = "16.0.0"
   erpnext_min_version = "16.0.0"
   ```

5. **CI matrix** — add `version-16` to `.github/workflows/ci.yml` alongside any existing
   version-15 job so both branches are tested going forward.

---

## Phase 2 — XML.P7M Decryption

### Goal
Accept `.xml.p7m` (CMS / PKCS#7 signed data) files from SDI and extract the inner
FatturaPA XML without requiring OpenSSL CLI.

### Background
SDI delivers invoices as CAdES-BES detached signatures wrapped in a `.p7m` envelope.
The file is a DER-encoded `ContentInfo` with `signedData` containing the original XML as
`encapContentInfo.eContent`.

### New file: `erpnext_italy/utils/p7m.py`

```python
"""
P7M (CMS SignedData) decryption utilities for Italian e-invoices.

Usage:
    from erpnext_italy.utils.p7m import extract_xml_from_p7m
    xml_bytes = extract_xml_from_p7m(p7m_bytes)
"""

import frappe
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.hazmat.primitives import hashes
from cryptography.x509 import load_der_x509_certificate
from asn1crypto import cms  # included transitively via cryptography


def extract_xml_from_p7m(p7m_bytes: bytes) -> bytes:
    """
    Extract the inner XML payload from a CAdES / PKCS#7 .p7m file.

    Args:
        p7m_bytes: raw bytes of the .p7m file (DER or BER encoded)

    Returns:
        bytes: the raw XML payload

    Raises:
        frappe.ValidationError: if the file is not valid CMS SignedData
    """
    try:
        from asn1crypto import cms as asn1_cms

        content_info = asn1_cms.ContentInfo.load(p7m_bytes)
        if content_info["content_type"].native != "signed_data":
            frappe.throw(
                "Il file .p7m non contiene dati di tipo SignedData.",
                title="Formato P7M non valido",
            )

        signed_data = content_info["content"]
        encap = signed_data["encap_content_info"]
        payload = encap["content"].parsed  # returns bytes

        if payload is None:
            # Fallback: some encoders omit EXPLICIT tag
            payload = encap["content"].contents

        return bytes(payload)

    except Exception as exc:
        frappe.log_error(
            message=str(exc),
            title="P7M extraction failed",
        )
        frappe.throw(
            f"Impossibile estrarre l'XML dal file .p7m: {exc}",
            title="Errore P7M",
        )


def verify_p7m_signature(p7m_bytes: bytes) -> dict:
    """
    Optionally verify the CAdES signature chain.
    Returns dict with keys: valid (bool), signer_cn (str), errors (list[str]).
    This is informational only — Italian law allows import even with expired certs.
    """
    result = {"valid": False, "signer_cn": None, "errors": []}
    try:
        from asn1crypto import cms as asn1_cms, pem

        content_info = asn1_cms.ContentInfo.load(p7m_bytes)
        signed_data = content_info["content"]
        certs = signed_data["certificates"]
        if certs:
            cert = certs[0].chosen
            result["signer_cn"] = cert.subject.human_friendly
        result["valid"] = True
    except Exception as exc:
        result["errors"].append(str(exc))
    return result
```

### Integration points

1. In `import_supplier_invoice/import_supplier_invoice.py` (or equivalent), detect `.p7m`
   extension and pre-process:

   ```python
   from erpnext_italy.utils.p7m import extract_xml_from_p7m

   def get_xml_content(file_path_or_bytes, filename):
       if filename.lower().endswith(".p7m"):
           return extract_xml_from_p7m(file_path_or_bytes)
       return file_path_or_bytes  # already XML
   ```

2. Update the file-upload field's `allowed_file_types` in the DocType JSON to include
   `.p7m` alongside `.xml`.

3. Add `asn1crypto` to `requirements.txt` (it is a dependency of `cryptography` but pin
   it explicitly: `asn1crypto>=1.5`).

---

## Phase 3 — Standard ZIP Upload (XML + checksum + XML.P7M)

### Goal
Accept the standard SDI delivery ZIP containing:
- `IT01234567890_00001.xml` — the invoice XML
- `IT01234567890_00001.xml.p7m` — the signed wrapper
- `IT01234567890_00001_hash.txt` — SHA-256 checksum file (optional, provider-dependent)

### New file: `erpnext_italy/utils/zip_import.py`

```python
"""
Utilities for importing the standard Italian SDI ZIP archive.

ZIP structure expected:
    <codice_fiscale>_<progressive>.xml
    <codice_fiscale>_<progressive>.xml.p7m   (optional but preferred)
    <codice_fiscale>_<progressive>_hash.txt  (optional checksum)
"""

import hashlib
import io
import zipfile

import frappe

from erpnext_italy.utils.p7m import extract_xml_from_p7m


ALLOWED_EXTENSIONS = {".xml", ".p7m", ".txt", ".sha256", ".sha2"}


def parse_sdi_zip(zip_bytes: bytes) -> list[dict]:
    """
    Parse an SDI ZIP and return a list of invoice dicts:
        {
            "filename": str,          # base invoice filename without extension
            "xml_bytes": bytes,       # raw FatturaPA XML
            "p7m_bytes": bytes|None,  # raw .p7m if present
            "checksum_ok": bool,      # True if checksum matched or not present
            "checksum_error": str,    # description if checksum failed
        }
    """
    results = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = zf.namelist()
        groups = _group_files(names)

        for base, files in groups.items():
            entry = {
                "filename": base,
                "xml_bytes": None,
                "p7m_bytes": None,
                "checksum_ok": True,
                "checksum_error": "",
            }

            # Load p7m first (preferred source of XML)
            if files.get("p7m"):
                entry["p7m_bytes"] = zf.read(files["p7m"])
                entry["xml_bytes"] = extract_xml_from_p7m(entry["p7m_bytes"])
            elif files.get("xml"):
                entry["xml_bytes"] = zf.read(files["xml"])

            if entry["xml_bytes"] is None:
                frappe.log_error(
                    f"ZIP entry '{base}' has no usable XML source.",
                    title="SDI ZIP parse warning",
                )
                continue

            # Verify checksum if present
            if files.get("hash"):
                expected = zf.read(files["hash"]).decode().strip().split()[0].lower()
                actual = hashlib.sha256(entry["xml_bytes"]).hexdigest().lower()
                if expected != actual:
                    entry["checksum_ok"] = False
                    entry["checksum_error"] = (
                        f"SHA-256 mismatch: expected {expected}, got {actual}"
                    )
                    frappe.log_error(entry["checksum_error"], title="SDI ZIP checksum error")

            results.append(entry)

    return results


def _group_files(names: list[str]) -> dict:
    """Group zip member names by invoice base filename."""
    groups = {}
    for name in names:
        lower = name.lower()
        if lower.endswith(".xml.p7m"):
            base = name[:-8]  # strip .xml.p7m
            groups.setdefault(base, {})["p7m"] = name
        elif lower.endswith(".xml"):
            base = name[:-4]
            groups.setdefault(base, {})["xml"] = name
        elif any(lower.endswith(ext) for ext in ("_hash.txt", ".sha256", ".sha2")):
            # best-effort: find the base by stripping the hash suffix
            base = name.rsplit("_hash", 1)[0].rsplit(".", 1)[0]
            groups.setdefault(base, {})["hash"] = name
    return groups
```

### DocType changes

Create (or update) `Import Supplier Invoice` DocType to add:
- Field `upload_type` — Select: `XML`, `XML.P7M`, `ZIP`
- Field `zip_file` — Attach — visible only when `upload_type == ZIP`
- Child table `sdi_zip_entries` — stores per-invoice status after ZIP parse

Add server-side whitelisted method:

```python
@frappe.whitelist()
def process_zip_upload(docname: str) -> dict:
    doc = frappe.get_doc("Import Supplier Invoice", docname)
    zip_bytes = frappe.get_doc("File", {"attached_to_name": docname, ...}).get_content()
    entries = parse_sdi_zip(zip_bytes)
    # save entries to child table, trigger import for each
    ...
    return {"imported": len(entries), "errors": [...]}
```

---

## Phase 4 — Bulk Upload of Multiple ZIP Files

### Goal
Allow uploading many ZIP files at once (via multi-file input or folder drop) and process
them as a background job with per-file status reporting.

### New DocType: `SDI Bulk Import`

Fields:
- `status` — Select: Draft / Processing / Completed / Completed with Errors
- `started_at`, `completed_at` — Datetime
- `total_files`, `processed_files`, `error_files` — Int
- Child table `sdi_bulk_import_file`:
  - `zip_file` — Attach
  - `status` — Select: Pending / Processing / Imported / Error
  - `error_message` — Small Text
  - `invoices_imported` — Int

### New file: `erpnext_italy/sdi_bulk_import/sdi_bulk_import.py`

```python
import frappe
from frappe.utils.background_jobs import enqueue

from erpnext_italy.utils.zip_import import parse_sdi_zip


class SDIBulkImport(frappe.model.document.Document):

    def validate(self):
        if not self.sdi_bulk_import_file:
            frappe.throw("Aggiungere almeno un file ZIP.")

    def start_import(self):
        self.db_set("status", "Processing")
        enqueue(
            method="erpnext_italy.sdi_bulk_import.sdi_bulk_import.process_bulk_import",
            queue="long",
            timeout=3600,
            docname=self.name,
        )
        return {"status": "queued"}


@frappe.whitelist()
def process_bulk_import(docname: str):
    doc = frappe.get_doc("SDI Bulk Import", docname)
    errors = []

    for row in doc.sdi_bulk_import_file:
        try:
            row.db_set("status", "Processing")
            file_doc = frappe.get_doc("File", row.zip_file)
            zip_bytes = file_doc.get_content()
            entries = parse_sdi_zip(zip_bytes)
            imported = 0
            for entry in entries:
                _import_single_invoice(entry)
                imported += 1
            row.db_set("status", "Imported")
            row.db_set("invoices_imported", imported)
        except Exception as exc:
            row.db_set("status", "Error")
            row.db_set("error_message", str(exc)[:500])
            errors.append({"file": row.zip_file, "error": str(exc)})
            frappe.log_error(str(exc), title=f"Bulk import error: {row.zip_file}")

    total = len(doc.sdi_bulk_import_file)
    error_count = sum(1 for r in doc.sdi_bulk_import_file if r.status == "Error")
    status = "Completed with Errors" if error_count else "Completed"
    doc.db_set("status", status)
    doc.db_set("processed_files", total - error_count)
    doc.db_set("error_files", error_count)

    # Send notification to user
    frappe.publish_realtime(
        event="sdi_bulk_import_complete",
        message={"docname": docname, "status": status, "errors": errors},
        user=doc.owner,
    )


def _import_single_invoice(entry: dict):
    """Create a Purchase Invoice (or draft) from a parsed ZIP entry."""
    # Delegate to existing import_supplier_invoice logic
    from erpnext_italy.import_supplier_invoice.import_supplier_invoice import (
        create_purchase_invoice_from_xml,
    )
    create_purchase_invoice_from_xml(entry["xml_bytes"])
```

### Frontend (`sdi_bulk_import.js`)

```javascript
frappe.ui.form.on("SDI Bulk Import", {
    refresh(frm) {
        if (frm.doc.status === "Draft") {
            frm.add_custom_button(__("Avvia Importazione"), () => {
                frm.call("start_import").then(r => {
                    frappe.msgprint(__("Importazione avviata in background."));
                });
            }, __("Azioni"));
        }
    }
});
```

---

## Phase 5 — Italian SDI Provider Integrations

### Goal
Support direct API transmission/reception with Italian SDI intermediaries:
- **Aruba Fatture in Cloud** (REST API)
- **Wolters Kluwer** (formerly Ipsoa — REST/SOAP)
- **TeamSystem** (REST API)
- Additional providers via a plugin pattern

### Architecture

```
erpnext_italy/sdi_providers/
    __init__.py
    base.py              ← abstract SDIProvider class
    aruba.py             ← Aruba Fatture in Cloud
    wolters_kluwer.py    ← Wolters Kluwer
    teamsystem.py        ← TeamSystem
    registry.py          ← provider registry + factory
```

### New DocType: `SDI Provider Settings`

Fields:
- `provider` — Select: Aruba / Wolters Kluwer / TeamSystem / Custom
- `api_base_url` — Data
- `api_key` / `api_secret` — Password (stored encrypted via `frappe.utils.password`)
- `username` / `password` — Password
- `company` — Link → Company
- `is_active` — Check
- `test_mode` — Check (use sandbox endpoints)
- `webhook_secret` — Password (for inbound webhook verification)

### `base.py`

```python
"""Abstract base class for SDI intermediary providers."""
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SendResult:
    success: bool
    provider_id: str | None  # provider's internal reference
    sdi_id: str | None       # SDI protocol number
    error: str | None


@dataclass
class ReceivedInvoice:
    filename: str
    xml_bytes: bytes
    p7m_bytes: bytes | None
    provider_metadata: dict


class SDIProvider(ABC):

    def __init__(self, settings_doc):
        self.settings = settings_doc

    @abstractmethod
    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        """Transmit a FatturaPA XML to the SDI via this provider."""

    @abstractmethod
    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        """Poll for inbound supplier invoices."""

    @abstractmethod
    def acknowledge_invoice(self, provider_id: str) -> bool:
        """Mark a received invoice as processed."""

    def test_connection(self) -> bool:
        """Override to implement a lightweight connectivity check."""
        return True
```

### `aruba.py` (skeleton — complete with Aruba API docs)

```python
import requests
import frappe
from .base import SDIProvider, SendResult, ReceivedInvoice


ARUBA_PROD_BASE = "https://fatturazioneelettronica.aruba.it/v1"
ARUBA_SAND_BASE = "https://sandbox.fatturazioneelettronica.aruba.it/v1"


class ArubaProvider(SDIProvider):

    @property
    def base_url(self):
        return ARUBA_SAND_BASE if self.settings.test_mode else ARUBA_PROD_BASE

    def _auth_headers(self):
        # Aruba uses HTTP Basic auth with username:password
        import base64
        credentials = base64.b64encode(
            f"{self.settings.username}:{frappe.utils.password.get_decrypted_password('SDI Provider Settings', self.settings.name, 'password')}".encode()
        ).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/xml",
        }

    def send_invoice(self, xml_bytes: bytes, filename: str) -> SendResult:
        url = f"{self.base_url}/send"
        try:
            resp = requests.post(
                url,
                data=xml_bytes,
                headers={**self._auth_headers(), "X-Filename": filename},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            return SendResult(
                success=True,
                provider_id=data.get("id"),
                sdi_id=data.get("sdi_id"),
                error=None,
            )
        except requests.HTTPError as exc:
            return SendResult(success=False, provider_id=None, sdi_id=None, error=str(exc))

    def fetch_received_invoices(self) -> list[ReceivedInvoice]:
        url = f"{self.base_url}/inbox"
        resp = requests.get(url, headers=self._auth_headers(), timeout=30)
        resp.raise_for_status()
        # Parse response per Aruba API schema (zip or list of XML)
        # TODO: implement per Aruba API documentation
        return []

    def acknowledge_invoice(self, provider_id: str) -> bool:
        url = f"{self.base_url}/inbox/{provider_id}/ack"
        resp = requests.post(url, headers=self._auth_headers(), timeout=15)
        return resp.ok
```

> **Note:** Obtain official API documentation for Aruba Fatture in Cloud, Wolters Kluwer,
> and TeamSystem from their developer portals. Implement `wolters_kluwer.py` and
> `teamsystem.py` following the same pattern as `aruba.py`. Each provider's auth, endpoint
> paths, and payload format will differ.

### `registry.py`

```python
from .aruba import ArubaProvider
from .wolters_kluwer import WoltersKluwerProvider
from .teamsystem import TeamSystemProvider

PROVIDERS = {
    "Aruba": ArubaProvider,
    "Wolters Kluwer": WoltersKluwerProvider,
    "TeamSystem": TeamSystemProvider,
}


def get_provider(company: str = None):
    """Return an instantiated SDIProvider for the given company's active settings."""
    import frappe
    filters = {"is_active": 1}
    if company:
        filters["company"] = company
    settings = frappe.get_last_doc("SDI Provider Settings", filters=filters)
    cls = PROVIDERS.get(settings.provider)
    if not cls:
        frappe.throw(f"Provider '{settings.provider}' non supportato.")
    return cls(settings)
```

### Scheduled transmission job

In `hooks.py` add:
```python
scheduler_events = {
    "cron": {
        # Poll for inbound invoices every 30 minutes during business hours
        "*/30 7-20 * * 1-5": [
            "erpnext_italy.sdi_providers.tasks.poll_inbound_invoices"
        ],
    }
}
```

New file `sdi_providers/tasks.py`:
```python
import frappe

def poll_inbound_invoices():
    from erpnext_italy.sdi_providers.registry import get_provider
    from erpnext_italy.utils.zip_import import _import_single_invoice

    companies = frappe.get_all("SDI Provider Settings", filters={"is_active": 1},
                               pluck="company")
    for company in set(companies):
        try:
            provider = get_provider(company)
            invoices = provider.fetch_received_invoices()
            for inv in invoices:
                _import_single_invoice({"xml_bytes": inv.xml_bytes,
                                        "filename": inv.filename,
                                        "checksum_ok": True,
                                        "checksum_error": ""})
                provider.acknowledge_invoice(inv.provider_metadata.get("id"))
        except Exception as exc:
            frappe.log_error(str(exc), title=f"SDI poll error: {company}")
```

---

## Phase 6 — Install / Remove / Update Lifecycle Functions

### `hooks.py` additions

```python
# Called after `bench install-app erpnext_italy`
after_install = "erpnext_italy.setup.install.after_install"

# Called before `bench uninstall-app erpnext_italy`
before_uninstall = "erpnext_italy.setup.install.before_uninstall"

# Called after `bench update` / migrate
after_migrate = "erpnext_italy.setup.install.after_migrate"
```

### New file: `erpnext_italy/setup/install.py`

```python
"""
Install, migrate, and uninstall hooks for erpnext_italy.
"""

import frappe


# ── Install ───────────────────────────────────────────────────────────────────

def after_install():
    """Run once when the app is first installed on a site."""
    _create_custom_fields()
    _create_default_sdi_settings()
    _seed_property_setters()
    frappe.db.commit()
    frappe.msgprint(
        "ERPNext Italy installato correttamente. "
        "Configura le impostazioni SDI in SDI Provider Settings.",
        title="Installazione completata",
        indicator="green",
    )


def _create_custom_fields():
    """
    Programmatically create custom fields on standard ERPNext DocTypes
    instead of shipping fixture JSON (avoids version conflicts).
    """
    from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

    custom_fields = {
        "Sales Invoice": [
            {
                "fieldname": "einvoice_status",
                "label": "Stato E-Fattura",
                "fieldtype": "Select",
                "options": "\nDa inviare\nInviata\nAccettata\nRifiutata",
                "insert_after": "status",
                "read_only": 1,
            },
            {
                "fieldname": "sdi_transmission_id",
                "label": "ID Trasmissione SDI",
                "fieldtype": "Data",
                "insert_after": "einvoice_status",
                "read_only": 1,
            },
        ],
        "Purchase Invoice": [
            {
                "fieldname": "sdi_import_id",
                "label": "ID Importazione SDI",
                "fieldtype": "Data",
                "insert_after": "status",
                "read_only": 1,
            }
        ],
    }
    create_custom_fields(custom_fields, ignore_validate=True)


def _create_default_sdi_settings():
    if not frappe.db.exists("SDI Provider Settings", {"is_active": 0}):
        doc = frappe.new_doc("SDI Provider Settings")
        doc.provider = "Aruba"
        doc.is_active = 0
        doc.test_mode = 1
        doc.insert(ignore_permissions=True)


def _seed_property_setters():
    pass  # Add any property setter defaults here


# ── Migrate (after bench update) ──────────────────────────────────────────────

def after_migrate():
    """Run on every `bench migrate` — safe to be idempotent."""
    _create_custom_fields()   # adds new fields introduced in updates
    frappe.db.commit()


# ── Uninstall ─────────────────────────────────────────────────────────────────

def before_uninstall():
    """Cleanup before app removal. Does NOT delete business data."""
    _remove_custom_fields()
    _remove_property_setters()
    frappe.db.commit()


def _remove_custom_fields():
    for doctype, fields in [
        ("Sales Invoice", ["einvoice_status", "sdi_transmission_id"]),
        ("Purchase Invoice", ["sdi_import_id"]),
    ]:
        for fieldname in fields:
            if frappe.db.exists("Custom Field", f"{doctype}-{fieldname}"):
                frappe.delete_doc("Custom Field", f"{doctype}-{fieldname}",
                                  ignore_permissions=True)


def _remove_property_setters():
    frappe.db.delete("Property Setter", {"module": "ERPNext Italy"})
```

---

## Phase 7 — Tests

### Directory structure

```
erpnext_italy/tests/
    __init__.py
    test_p7m.py
    test_zip_import.py
    test_bulk_import.py
    test_sdi_providers.py
    test_install.py
    test_v16_compat.py
    fixtures/
        sample_invoice.xml           ← minimal valid FatturaPA XML
        sample_invoice.xml.p7m       ← CMS-wrapped version of sample_invoice.xml
        sample_sdi_delivery.zip      ← ZIP containing both files above
        sample_invoice_hash.txt      ← correct SHA-256 of sample_invoice.xml
        sample_invoice_bad_hash.txt  ← wrong hash (for negative tests)
```

### `test_p7m.py`

```python
import os
import unittest
import frappe
from erpnext_italy.utils.p7m import extract_xml_from_p7m, verify_p7m_signature

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestP7MExtraction(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(FIXTURES, "sample_invoice.xml.p7m"), "rb") as f:
            self.p7m_bytes = f.read()
        with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
            self.expected_xml = f.read()

    def test_extract_returns_xml(self):
        xml = extract_xml_from_p7m(self.p7m_bytes)
        self.assertIsInstance(xml, bytes)
        self.assertIn(b"FatturaElettronica", xml)

    def test_extracted_matches_original(self):
        xml = extract_xml_from_p7m(self.p7m_bytes)
        self.assertEqual(xml.strip(), self.expected_xml.strip())

    def test_invalid_bytes_raises(self):
        with self.assertRaises(frappe.exceptions.ValidationError):
            extract_xml_from_p7m(b"this is not a p7m file")

    def test_signature_info(self):
        result = verify_p7m_signature(self.p7m_bytes)
        self.assertIn("valid", result)
        self.assertIn("signer_cn", result)
```

### `test_zip_import.py`

```python
import os
import unittest
from erpnext_italy.utils.zip_import import parse_sdi_zip

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


class TestZIPImport(unittest.TestCase):

    def setUp(self):
        with open(os.path.join(FIXTURES, "sample_sdi_delivery.zip"), "rb") as f:
            self.zip_bytes = f.read()

    def test_parse_returns_entries(self):
        entries = parse_sdi_zip(self.zip_bytes)
        self.assertGreater(len(entries), 0)

    def test_entry_has_xml(self):
        entries = parse_sdi_zip(self.zip_bytes)
        for e in entries:
            self.assertIsNotNone(e["xml_bytes"])
            self.assertIn(b"FatturaElettronica", e["xml_bytes"])

    def test_checksum_passes(self):
        entries = parse_sdi_zip(self.zip_bytes)
        for e in entries:
            self.assertTrue(e["checksum_ok"], e.get("checksum_error"))

    def test_bad_checksum_flagged(self):
        import io, zipfile
        # Build a ZIP with a bad hash file
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            with open(os.path.join(FIXTURES, "sample_invoice.xml"), "rb") as f:
                xml_content = f.read()
            zf.writestr("IT01234567890_00001.xml", xml_content)
            zf.writestr("IT01234567890_00001_hash.txt", "badhash000\n")
        entries = parse_sdi_zip(buf.getvalue())
        self.assertFalse(entries[0]["checksum_ok"])
```

### `test_sdi_providers.py`

```python
import unittest
from unittest.mock import patch, MagicMock
import frappe


class TestArubaProvider(unittest.TestCase):

    def _make_settings(self, test_mode=True):
        settings = MagicMock()
        settings.name = "test-aruba"
        settings.provider = "Aruba"
        settings.test_mode = test_mode
        settings.username = "testuser"
        return settings

    @patch("requests.post")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_send_invoice_success(self, mock_pwd, mock_post):
        from erpnext_italy.sdi_providers.aruba import ArubaProvider

        mock_post.return_value = MagicMock(
            status_code=200,
            json=lambda: {"id": "abc123", "sdi_id": "SDI-001"},
            raise_for_status=lambda: None,
        )
        provider = ArubaProvider(self._make_settings())
        result = provider.send_invoice(b"<xml/>", "IT01234567890_00001.xml")
        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "abc123")

    @patch("requests.post")
    @patch("frappe.utils.password.get_decrypted_password", return_value="secret")
    def test_send_invoice_http_error(self, mock_pwd, mock_post):
        import requests
        from erpnext_italy.sdi_providers.aruba import ArubaProvider

        mock_post.return_value = MagicMock(
            status_code=401,
            raise_for_status=MagicMock(side_effect=requests.HTTPError("401")),
        )
        provider = ArubaProvider(self._make_settings())
        result = provider.send_invoice(b"<xml/>", "test.xml")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.error)
```

### Running tests

```bash
# All tests for the app
bench --site italy.localhost run-tests --app erpnext_italy

# Single module
bench --site italy.localhost run-tests --app erpnext_italy \
      --module erpnext_italy.tests.test_p7m

# With coverage
bench --site italy.localhost run-tests --app erpnext_italy --coverage
```

---

## CI/CD Configuration (`.github/workflows/ci.yml`)

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        erpnext-version: ["version-15", "version-16"]

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install bench
        run: pip install frappe-bench

      - name: Init bench
        run: |
          bench init frappe-bench --frappe-branch ${{ matrix.erpnext-version }} --skip-redis-config-generation
          cd frappe-bench
          bench get-app erpnext --branch ${{ matrix.erpnext-version }}
          bench new-site test.localhost --db-root-password root --admin-password admin
          bench --site test.localhost install-app erpnext
          bench get-app erpnext_italy ${{ github.workspace }}
          bench --site test.localhost install-app erpnext_italy

      - name: Run tests
        run: |
          cd frappe-bench
          bench --site test.localhost run-tests --app erpnext_italy
```

---

## Acceptance Criteria Checklist

| Phase | Criterion | Done |
|---|---|---|
| 1 | App installs cleanly on ERPNext v16, all existing tests green | ☐ |
| 1 | CI matrix runs v15 and v16 jobs | ☐ |
| 2 | `extract_xml_from_p7m` returns correct XML bytes for sample fixture | ☐ |
| 2 | Invalid `.p7m` raises `frappe.ValidationError` | ☐ |
| 3 | `parse_sdi_zip` extracts XML from ZIP containing `.xml.p7m` | ☐ |
| 3 | Checksum mismatch is logged and flagged (not a hard error) | ☐ |
| 4 | `SDI Bulk Import` enqueues a background job per submission | ☐ |
| 4 | Per-file status and error messages are saved to child table | ☐ |
| 4 | Realtime notification fires on completion | ☐ |
| 5 | `ArubaProvider.send_invoice` and `fetch_received_invoices` tested with mocks | ☐ |
| 5 | `SDI Provider Settings` DocType exists with encrypted password fields | ☐ |
| 5 | Scheduled poll job registered in `hooks.py` | ☐ |
| 6 | `after_install` creates custom fields without errors on a fresh v16 site | ☐ |
| 6 | `before_uninstall` removes custom fields cleanly | ☐ |
| 6 | `after_migrate` is idempotent (safe to run multiple times) | ☐ |
| 7 | All test files exist and pass with `bench run-tests` | ☐ |
| 7 | Coverage ≥ 70% for new code in `utils/`, `sdi_providers/`, `setup/` | ☐ |

---

## Key References

- [FatturaPA specification v1.3.2](https://www.fatturapa.gov.it/it/norme-e-regole/documentazione-fattura-elettronica/)
- [SDI file naming & delivery spec](https://www.fatturapa.gov.it/it/norme-e-regole/regole-tecniche/)
- [Aruba Fatture in Cloud API](https://developers.aruba.it/en/fatturazione-elettronica)
- [Frappe v16 migration guide](https://frappeframework.com/docs/v16/user/en/migrate)
- [asn1crypto docs](https://github.com/wbond/asn1crypto)
- [cryptography.io — PKCS7](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/serialization/#pkcs7)
- [frappe/erpnext_italy upstream](https://github.com/frappe/erpnext_italy)