"""Shared helpers for the gym_management app."""

import frappe
from frappe.utils import getdate


def get_default_company():
    """Company used for billing: the global default set in ERPNext."""
    return frappe.defaults.get_global_default("company") or frappe.db.get_single_value(
        "Global Defaults", "default_company"
    )


def get_selling_price_list():
    """Selling price list from Selling Settings, else any enabled selling list."""
    return frappe.db.get_single_value(
        "Selling Settings", "selling_price_list"
    ) or frappe.db.get_value("Price List", {"selling": 1, "enabled": 1}, "name")


def get_default_territory():
    return (
        frappe.db.get_single_value("Selling Settings", "territory")
        or "All Territories"
    )


def get_default_customer_group():
    """Return a valid non-group Customer Group."""
    customer_group = frappe.db.get_single_value(
        "Selling Settings", "customer_group"
    )

    if customer_group and not frappe.db.get_value(
        "Customer Group",
        {"name": customer_group, "is_group": 0},
        "name",
    ):
        customer_group = None

    if not customer_group:
        customer_group = frappe.db.get_value(
            "Customer Group",
            {"is_group": 0},
            "name",
        )

    if not customer_group:
        frappe.throw(
            "Create at least one non-group Customer Group before adding a Gym Member."
        )

    return customer_group


def is_frozen_on(membership, on_date):
    """True if any freeze period of the membership covers ``on_date``."""
    on_date = getdate(on_date)
    return any(
        row.freeze_from
        and row.freeze_to
        and getdate(row.freeze_from) <= on_date <= getdate(row.freeze_to)
        for row in (membership.get("freeze_history") or [])
    )


def get_valid_membership(member, on_date):
    """Return the name of the member's submitted, Active, non-frozen membership
    that covers ``on_date``, or None."""
    on_date = getdate(on_date)
    rows = frappe.get_all(
        "Gym Membership",
        filters={"member": member, "docstatus": 1, "status": "Active"},
        fields=["name", "start_date", "end_date"],
    )
    for row in rows:
        if row.start_date and getdate(row.start_date) > on_date:
            continue
        if row.end_date and getdate(row.end_date) < on_date:
            continue
        membership = frappe.get_doc("Gym Membership", row.name)
        if not is_frozen_on(membership, on_date):
            return row.name
    return None
