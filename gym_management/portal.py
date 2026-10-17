"""Member portal: what a signed-in member can do from the website.

A member signs in with a Website User whose email matches the email on their
Gym Member record. Website users hold no permission on the gym DocTypes, so
every function here first resolves the member from the session and only then
acts, with ``ignore_permissions`` limited to that member's own records. The
booking rules themselves are not repeated: they live in the Class Booking
controller, exactly as for the front desk.
"""

import frappe
from frappe import _
from frappe.utils import add_days, formatdate, now_datetime, today

from gym_management.api import create_booking, get_titles
from gym_management.utils import (
    combine_date_time,
    format_time,
    get_latest_membership,
    get_membership_block_reason,
)

PORTAL_DAYS = 7
OPEN_STATUSES = ["Booked", "Waitlisted"]
SESSION_FIELDS = [
    "name",
    "gym_class",
    "trainer",
    "session_date",
    "start_time",
    "end_time",
    "capacity",
    "booked_count",
]


def get_portal_member(user=None):
    """The Gym Member signed in as ``user``, or None."""
    user = user or frappe.session.user
    if user == "Guest":
        return None

    email = frappe.db.get_value("User", user, "email")
    if not email:
        return None

    members = frappe.get_all("Gym Member", filters={"email": email}, pluck="name", limit=2)
    if len(members) > 1:
        # Guessing would let one person act on another member's bookings.
        frappe.throw(
            _("More than one member uses {0}. Please contact the front desk.").format(email)
        )

    return members[0] if members else None


def require_portal_member():
    member = get_portal_member()
    if not member:
        frappe.throw(_("Your account is not linked to a gym member."), frappe.PermissionError)
    return member


@frappe.whitelist()
def book_session(session):
    """Book the signed-in member onto ``session``; the member is never taken from the request."""
    member = require_portal_member()
    return create_booking(session, member, ignore_permissions=True)


@frappe.whitelist()
def cancel_booking(booking):
    member = require_portal_member()

    doc = frappe.get_doc("Class Booking", booking)
    if doc.member != member:
        frappe.throw(_("You can only cancel your own bookings."), frappe.PermissionError)

    if doc.status not in OPEN_STATUSES:
        frappe.throw(_("Only booked or waitlisted classes can be cancelled."))

    # Saving as Cancelled runs the usual hooks: the spot count, the class-pack
    # credit and the waitlist promotion all happen in the controller.
    doc.status = "Cancelled"
    doc.save(ignore_permissions=True)

    return {"booking": doc.name, "status": doc.status}


def get_portal_context(member):
    """Everything the page shows: membership, upcoming sessions, own bookings."""
    membership_name = get_latest_membership(member)
    membership = frappe.get_doc("Gym Membership", membership_name) if membership_name else None
    block_reason = (
        get_membership_block_reason(membership, today()) if membership else _("no membership on file")
    )

    bookings = frappe.get_all(
        "Class Booking",
        filters={"member": member, "status": ["in", OPEN_STATUSES]},
        fields=["name", "class_session", "status", "waitlist_position"],
    )
    booking_by_session = {row.class_session: row for row in bookings}

    window = frappe.get_all(
        "Class Session",
        filters={
            "status": "Scheduled",
            "session_date": ["between", [today(), add_days(today(), PORTAL_DAYS)]],
        },
        fields=SESSION_FIELDS,
        order_by="session_date asc, start_time asc",
    )

    booked = []
    if booking_by_session:
        booked = frappe.get_all(
            "Class Session",
            filters={"name": ["in", list(booking_by_session)], "session_date": [">=", today()]},
            fields=SESSION_FIELDS,
            order_by="session_date asc, start_time asc",
        )

    sessions = [row for row in window if not has_started(row)]
    my_bookings = [row for row in booked if not has_started(row)]
    describe_sessions(sessions + my_bookings, booking_by_session)

    return {
        "member_name": frappe.db.get_value("Gym Member", member, "member_name"),
        "membership": membership,
        "membership_end": formatdate(membership.end_date) if membership else None,
        "block_reason": block_reason,
        "sessions": sessions,
        "my_bookings": my_bookings,
        "enable_waitlist": frappe.db.get_single_value("Gym Settings", "enable_waitlist"),
    }


def has_started(session):
    return combine_date_time(session.session_date, session.start_time) <= now_datetime()


def describe_sessions(sessions, booking_by_session):
    """Add the display fields, with one query per linked DocType rather than per row."""
    class_names = get_titles("Gym Class", {r.gym_class for r in sessions if r.gym_class}, "class_name")
    trainer_names = get_titles("Gym Trainer", {r.trainer for r in sessions if r.trainer}, "trainer_name")

    for row in sessions:
        row.class_name = class_names.get(row.gym_class, row.gym_class)
        row.trainer_name = trainer_names.get(row.trainer, "")
        row.date_label = formatdate(row.session_date, "EEE d MMM")
        row.time_label = f"{format_time(row.start_time)[:5]} - {format_time(row.end_time)[:5]}"
        row.spots_left = max((row.capacity or 0) - (row.booked_count or 0), 0)
        row.my_booking = booking_by_session.get(row.name)

