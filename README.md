# ERPNext Italy

Regional customisations for Italy built on top of ERPNext, targeting **ERPNext v16**.

---

## Features

### Italian E-Invoicing (FatturaPA / SDI)

Generate and transmit FatturaPA XML from Sales Invoices in compliance with the Italian
Sistema di Interscambio (SDI) specification.

- XML generation from Sales Invoices, including all required fields (fiscal codes,
  payment terms, VAT collectability, destination codes).
- Export as single file or ZIP archive for batch upload.

### SDI Invoice Import

Import supplier and self-issued invoices from SDI delivery ZIPs — including plain XML
and CAdES-BES signed `.xml.p7m` files — with automatic party, address, and invoice
creation in ERPNext.

Three purpose-specific import wizards share a common base class:

| DocType | Direction | Creates |
|---|---|---|
| **Purchase Invoice IT SDI Import** | Inbound supplier invoices | Purchase Invoice |
| **Sales Invoice IT SDI Import** | Outbound XML migration / reconciliation | Sales Invoice |
| **Foreign Purchase Invoice IT SDI Import** | Autofattura (TD17–TD27) | Sales Invoice (self-invoice) |

Features:
- Transparent `.xml.p7m` decryption using `asn1crypto` (no OpenSSL CLI dependency).
- Automatic filtering of SDI receipt/notification files (`_RC_`, `_NS_`, `_MC_`).
- Upsert-style party creation: matches existing Supplier/Customer by tax ID before creating.
- Background processing with real-time progress updates.

### SDI Bulk Import

Process many SDI delivery ZIPs in a single background job.

- Upload multiple ZIP files to the **SDI Bulk Import** DocType.
- Choose import type (purchase / sales / autofattura) once for the entire batch.
- Per-file status, invoice count, and error messages stored in a child table.
- Real-time notification on completion.

### SDI Provider Integrations

Direct API and FTP integration with Italian SDI intermediaries:

| Provider | Transport | Status |
|---|---|---|
| **Aruba Fatture in Cloud** | REST API (HTTP Basic auth) | Implemented |
| **Wolters Kluwer** | FTP / FTPS file delivery | Implemented |
| **TeamSystem** | REST API | Stub — needs API docs |

Configure in **SDI Provider Settings**. Inbound invoices are polled automatically
every 30 minutes on weekdays (07:00–20:00) via a scheduled background job.

---

## Installation

1. Install ERPNext v16 via bench:
   ```sh
   bench init frappe-bench --frappe-branch version-16
   cd frappe-bench
   bench get-app erpnext --branch version-16
   bench new-site italy.localhost --install-app erpnext
   ```

2. Add this app:
   ```sh
   bench get-app https://github.com/teodoropiccinni/erpnext_italy.git
   bench --site italy.localhost install-app erpnext_italy
   ```

3. Python dependency (`asn1crypto`) is listed in `requirements.txt` and installed
   automatically by bench.

---

## Usage

### Import supplier invoices (single batch)

1. Open **Purchase Invoice IT SDI Import** → New.
2. Set Company, Default Item Code, Supplier Group, Tax Account, Invoice Series.
3. Attach the SDI delivery ZIP.
4. Click **Import Invoices**. Processing runs in the background.

### Import autofattura (TD17–TD27)

Use **Foreign Purchase Invoice IT SDI Import** instead. Documents with any other
`TipoDocumento` are automatically skipped and logged.

### Bulk import multiple ZIPs

1. Open **SDI Bulk Import** → New.
2. Choose Import Type (purchase / sales / autofattura) and fill in the defaults.
3. Add all ZIP files to the child table.
4. Save, then click **Start Import**.

### Configure an SDI provider

1. Open **SDI Provider Settings** → New.
2. Select provider (Aruba, Wolters Kluwer, TeamSystem).
3. Fill in credentials (REST API key/password or FTP host/credentials).
4. Enable **Active** when ready. Only one active provider per company is allowed.
5. Use **Test Connection** to verify connectivity before going live.

---

## Running tests

```sh
# Full test suite
bench --site italy.localhost run-tests --app erpnext_italy

# Individual modules
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_p7m
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_sdi_import_base
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_bulk_import
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_sdi_providers
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_install
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_sdi_import_doctypes
bench --site italy.localhost run-tests --app erpnext_italy --module erpnext_italy.tests.test_v16_compat
```

---

## Architecture

See [EINVOICING.md](EINVOICING.md) for the full e-invoicing feature design, XML field
mapping, and processing pipeline documentation.

See [CLAUDE.md](CLAUDE.md) for the implementation roadmap and acceptance criteria.

```
erpnext_italy/
  erpnext_italy/
    erpnext_italy/doctype/
      purchase_invoice_it_sdi_import/
      sales_invoice_it_sdi_import/
      foreign_purchase_invoice_it_sdi_import/
      sdi_bulk_import/
      sdi_bulk_import_file/
      sdi_provider_settings/
    utils/
      p7m.py               # CMS SignedData extraction (asn1crypto)
      sdi_import_base.py   # shared base class + XML helpers + process_zip_bytes
    sdi_providers/
      base.py              # abstract SDIProvider interface
      aruba.py             # Aruba REST implementation
      wolters_kluwer.py    # Wolters Kluwer FTP/FTPS implementation
      teamsystem.py        # TeamSystem stub
      registry.py          # provider factory
      tasks.py             # scheduled poll job
    install.py             # after_install / before_uninstall / after_migrate
    hooks.py
  tests/
    test_p7m.py
    test_sdi_import_base.py
    test_bulk_import.py
    test_sdi_providers.py
    test_install.py
    test_sdi_import_doctypes.py
    test_v16_compat.py
    fixtures/
```

---

## License

GNU GPL V3. See [license.txt](license.txt) for more information.
