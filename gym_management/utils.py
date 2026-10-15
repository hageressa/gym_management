"""Shared helpers for the gym_management app."""

from datetime import datetime

import frappe
from frappe import _
from frappe.utils import get_time, getdate


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
    return frappe.db.get_single_value("Selling Settings", "territory") or "All Territories"


def get_default_customer_group():
    """Return a valid non-group Customer Group."""
    customer_group = frappe.db.get_single_value("Selling Settings", "customer_group")

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
            _("Create at least one non-group Customer Group before adding a Gym Member.")
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


def get_membership_block_reason(membership, on_date):
    """Why this membership cannot be used on ``on_date``, or None if it is usable.

    This is the one place that decides whether a membership is usable. Bookings,
    waitlist promotion and check-ins all call it.
    """
    on_date = getdate(on_date)

    if membership.status == "Cancelled":
        return _("membership is cancelled")

    if membership.status == "Expired" or (
        membership.end_date and getdate(membership.end_date) < on_date
    ):
        return _("membership has expired")

    if membership.start_date and getdate(membership.start_date) > on_date:
        return _("membership has not started yet")

    # The stored status can lag behind the freeze dates, so check both.
    if membership.status == "Frozen" or is_frozen_on(membership, on_date):
        return _("membership is frozen today")

    if membership.status != "Active":
        return _("membership is not active")

    return None


def get_valid_membership(member, on_date):
    """Name of the member's first usable submitted membership on ``on_date``, or None."""
    rows = frappe.get_all(
        "Gym Membership",
        filters={"member": member, "docstatus": 1, "status": "Active"},
        fields=["name"],
    )
    for row in rows:
        membership = frappe.get_doc("Gym Membership", row.name)
        if get_membership_block_reason(membership, on_date) is None:
            return row.name
    return None


def get_latest_membership(member):
    """The member's most recent submitted membership, expired ones included.

    The front desk needs this to explain *why* entry is refused, which a
    search for Active memberships alone could not tell them.
    """
    return frappe.db.get_value(
        "Gym Membership",
        {"member": member, "docstatus": 1},
        "name",
        order_by="end_date desc",
    )


def combine_date_time(date_value, time_value):
    """A Date field and a Time field as one datetime, for comparing against now."""
    return datetime.combine(getdate(date_value), get_time(time_value))


def format_time(value):
    """A time value as HH:MM:SS, the form SQL comparisons expect."""
    return get_time(value).strftime("%H:%M:%S")
