"""Scheduled background tasks for SDI provider integrations."""

import frappe


def poll_inbound_invoices():
    """Fetch inbound invoices from all active SDI providers and create Purchase Invoices.

    Scheduled to run every 30 minutes on weekdays (see hooks.py scheduler_events).
    """
    from erpnext_italy.sdi_providers.registry import get_provider
    from erpnext_italy.utils.sdi_import_base import (
        create_purchase_invoice_doc,
        create_supplier,
        create_address,
        get_supplier_details,
        get_taxes_from_file,
        get_payment_terms_from_file,
        get_destination_code_from_file,
        _build_items,
    )
    from bs4 import BeautifulSoup as bs
    from frappe.utils import get_datetime_str, today
    import frappe._dict as fdict

    active_settings = frappe.get_all(
        "SDI Provider Settings",
        filters={"is_active": 1},
        fields=["name", "company", "provider"],
    )

    seen_companies = set()
    for row in active_settings:
        company = row["company"]
        if company in seen_companies:
            continue
        seen_companies.add(company)

        try:
            provider = get_provider(company)
            invoices = provider.fetch_received_invoices()

            # Resolve import config for this company
            config = _get_import_config(company)
            if not config:
                frappe.log_error(
                    message=(
                        "No Purchase Invoice IT SDI Import document found for company {0}. "
                        "Create one to configure default item, supplier group, etc."
                    ).format(company),
                    title="SDI poll: missing import config for " + company,
                )
                continue

            for inv in invoices:
                try:
                    xml_bytes = inv.p7m_bytes or inv.xml_bytes
                    file_content = bs(xml_bytes, "xml")
                    invoices_args = _parse_invoice_args(file_content, config, inv.filename)
                    supp_dict = get_supplier_details(file_content)
                    supplier_name = create_supplier(config["supplier_group"], supp_dict)
                    create_address("Supplier", supplier_name, supp_dict)
                    doc_name = create_purchase_invoice_doc(supplier_name, inv.filename, invoices_args, None)
                    if doc_name:
                        provider.acknowledge_invoice(inv.provider_metadata.get("id", ""))
                except Exception as exc:
                    frappe.log_error(
                        message=exc,
                        title="SDI poll: failed to import {0}".format(inv.filename),
                    )

        except Exception as exc:
            frappe.log_error(
                message=exc,
                title="SDI poll error for company: " + company,
            )


def _get_import_config(company: str) -> dict | None:
    """Look up the most recent Purchase Invoice IT SDI Import doc for this company."""
    name = frappe.db.get_value(
        "Purchase Invoice It Sdi Import",
        {"company": company},
        "name",
        order_by="modified desc",
    )
    if not name:
        return None
    doc = frappe.get_doc("Purchase Invoice It Sdi Import", name)
    return {
        "company": doc.company,
        "invoice_series": doc.invoice_series,
        "item_code": doc.item_code,
        "tax_account": doc.tax_account,
        "default_uom": frappe.db.get_value("Stock Settings", fieldname="stock_uom") or "Nos",
        "supplier_group": doc.supplier_group,
        "default_buying_price_list": doc.default_buying_price_list,
    }


def _parse_invoice_args(file_content, config: dict, file_name: str) -> dict:
    from frappe.utils import get_datetime_str
    from erpnext_italy.utils.sdi_import_base import (
        get_taxes_from_file,
        get_payment_terms_from_file,
        get_destination_code_from_file,
        _build_items,
    )

    for line in file_content.find_all("DatiGeneraliDocumento"):
        args = {
            "company": config["company"],
            "naming_series": config["invoice_series"],
            "document_type": line.TipoDocumento.text,
            "bill_date": get_datetime_str(line.Data.text),
            "bill_no": line.Numero.text,
            "total_discount": 0,
            "items": [],
            "buying_price_list": config["default_buying_price_list"],
            "destination_code": get_destination_code_from_file(file_content),
        }
        _build_items(file_content, args, config["item_code"], config["default_uom"])
        args["taxes"] = get_taxes_from_file(file_content, config["tax_account"])
        args["terms"] = get_payment_terms_from_file(file_content)
        return args
    frappe.throw("No DatiGeneraliDocumento found in XML: " + file_name)
