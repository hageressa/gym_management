"""Document event handlers (registered in hooks.py ``doc_events``)."""

import frappe
from frappe import _
from frappe.utils import getdate, get_datetime, now_datetime, today

from gym_management.utils import get_valid_membership

CONFIRMED_STATUSES = ["Booked", "Attended"]


def set_booking_metadata(doc, method=None):
    """Class Booking before_save: fill booked_on, cancelled_on and membership."""
    if doc.status in ("Booked", "Waitlisted") and not doc.booked_on:
        doc.booked_on = now_datetime()

    if doc.status == "Cancelled" and not doc.cancelled_on:
        doc.cancelled_on = now_datetime()

    if doc.member and doc.class_session and not doc.membership:
        start = frappe.db.get_value("Class Session", doc.class_session, "start_datetime")
        if start:
            doc.membership = get_valid_membership(doc.member, getdate(start))


def update_session_booked_count(doc, method=None):
    """Class Booking after_insert / on_update / on_trash: keep booked_count in sync."""
    if not doc.class_session:
        return

    filters = {"class_session": doc.class_session, "status": ["in", CONFIRMED_STATUSES]}
    if method == "on_trash":
        filters["name"] = ["!=", doc.name]

    frappe.db.set_value(
        "Class Session",
        doc.class_session,
        "booked_count",
        frappe.db.count("Class Booking", filters),
        update_modified=False,
    )


def apply_booking_status_effects(doc, method=None):
    """Class Booking after_insert / on_update: class-pack credit, late-cancel and no-show warnings."""
    previous = doc.get_doc_before_save()
    previous_status = previous.status if previous else None

    # Class pack: taking a Booked spot uses one class, cancelling it gives the class back.
    if doc.status == "Booked" and previous_status != "Booked":
        _adjust_class_credit(doc, -1)
    elif previous_status == "Booked" and doc.status == "Cancelled":
        _adjust_class_credit(doc, +1)

    if previous_status == doc.status:
        return

    if doc.status == "Cancelled":
        _warn_late_cancellation(doc)
    elif doc.status == "No Show":
        _warn_no_show_limit(doc)


def _is_class_pack(membership_name):
    plan = frappe.db.get_value("Gym Membership", membership_name, "membership_plan")
    return bool(plan) and (
        frappe.db.get_value("Membership Plan", plan, "duration_type") == "Class Pack"
    )


def _adjust_class_credit(doc, change):
    """Add (+1) or remove (-1) one class from the booking's class pack.

    Raises when a booking would take a class from an empty pack. Raising inside
    the save rolls back the booking too, so the member is never charged twice.
    """
    if not doc.membership or not _is_class_pack(doc.membership):
        return

    remaining = frappe.db.get_value("Gym Membership", doc.membership, "classes_remaining") or 0
    new_remaining = remaining + change

    if new_remaining < 0:
        frappe.throw(_("This class pack has no classes remaining."))

    frappe.db.set_value(
        "Gym Membership",
        doc.membership,
        "classes_remaining",
        new_remaining,
        update_modified=False,
    )


def _warn_late_cancellation(doc):
    window = frappe.db.get_single_value("Gym Settings", "cancellation_window_hours") or 0
    start = frappe.db.get_value("Class Session", doc.class_session, "start_datetime")
    if not window or not start:
        return
    hours_left = (get_datetime(start) - now_datetime()).total_seconds() / 3600
    if 0 <= hours_left < window:
        frappe.msgprint(
            _("Late cancellation: less than {0} hours before the session.").format(window),
            indicator="orange",
        )


def _warn_no_show_limit(doc):
    limit = frappe.db.get_single_value("Gym Settings", "no_show_limit") or 0
    if not limit:
        return
    month_start = getdate(today()).replace(day=1)
    no_shows = frappe.db.count(
        "Class Booking",
        {"member": doc.member, "status": "No Show", "modified": [">=", month_start]},
    )
    if no_shows >= limit:
        frappe.msgprint(
            _("{0} has reached the monthly no-show limit ({1}).").format(doc.member, limit),
            indicator="red",
        )
