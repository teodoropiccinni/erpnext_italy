"""Provider registry and factory for SDI intermediary providers."""

import frappe

from .aruba import ArubaProvider
from .teamsystem import TeamSystemProvider
from .wolters_kluwer import WoltersKluwerProvider

PROVIDERS: dict = {
    "Aruba": ArubaProvider,
    "Wolters Kluwer": WoltersKluwerProvider,
    "TeamSystem": TeamSystemProvider,
}


def get_provider(company: str | None = None):
    """Return an instantiated SDIProvider for the given company's active settings.

    Raises frappe.DoesNotExistError if no active settings are found.
    Raises frappe.ValidationError if the configured provider is not supported.
    """
    filters = {"is_active": 1}
    if company:
        filters["company"] = company

    settings_name = frappe.db.get_value("SDI Provider Settings", filters, "name")
    if not settings_name:
        frappe.throw(
            "No active SDI Provider Settings found{0}.".format(
                f" for company {company}" if company else ""
            )
        )

    settings = frappe.get_doc("SDI Provider Settings", settings_name)
    cls = PROVIDERS.get(settings.provider)
    if not cls:
        frappe.throw(f"SDI provider '{settings.provider}' is not supported.")

    return cls(settings)
