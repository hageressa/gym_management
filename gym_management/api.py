import frappe
from frappe.utils import add_days, getdate, today


@frappe.whitelist()
def book_class(session, member):
    if not session or not member:
        frappe.throw("Session and member are required.")

    booking = frappe.get_doc({
        "doctype": "Class Booking",
        "class_session": session,
        "member": member,
        "booking_date": today(),
        "status": "Booked",
    })

    booking.insert()

    return {
        "booking": booking.name,
        "status": booking.status,
        "waitlist_position": booking.waitlist_position,
    }


@frappe.whitelist()
def get_available_sessions(date_from, date_to):
    start_date = getdate(date_from)
    end_date = getdate(date_to)

    if end_date < start_date:
        frappe.throw("End date cannot be before start date.")

    sessions = frappe.get_all(
        "Class Session",
        filters={
            "status": "Scheduled",
            "start_datetime": [
                "between",
                [
                    f"{start_date} 00:00:00",
                    f"{add_days(end_date, 1)} 00:00:00",
                ],
            ],
        },
        fields=[
            "name",
            "gym_class",
            "trainer",
            "room",
            "start_datetime",
            "end_datetime",
            "capacity",
            "status",
        ],
        order_by="start_datetime asc",
    )

    available_sessions = []

    for session in sessions:
        booked = frappe.db.count(
            "Class Booking",
            {
                "class_session": session.name,
                "status": ["in", ["Booked", "Attended"]],
            },
        )

        capacity = session.capacity or 0
        available_spots = max(capacity - booked, 0)

        if available_spots > 0:
            session["available_spots"] = available_spots
            available_sessions.append(session)

    return available_sessions


@frappe.whitelist()
def freeze_membership(membership_name, freeze_from, freeze_to, reason=None):
    if not membership_name or not freeze_from or not freeze_to:
        frappe.throw("Membership, Freeze From, and Freeze To are required.")

    membership = frappe.get_doc("Gym Membership", membership_name)
    membership.check_permission("write")

    if membership.docstatus != 1:
        frappe.throw("Only submitted memberships can be frozen.")
    if membership.status not in ("Active", "Frozen"):
        frappe.throw("Only active or frozen memberships can be frozen.")

    start = getdate(freeze_from)
    end = getdate(freeze_to)
    current_date = getdate(today())

    if end <= start:
        frappe.throw("Freeze To must be after Freeze From.")
    if end < current_date:
        frappe.throw("Freeze To cannot be in the past.")

    plan = frappe.get_doc("Membership Plan", membership.membership_plan)
    max_days = int(getattr(plan, "max_freeze_days", 0) or 0)

    periods = []
    total_days = 0
    for row in membership.get("freeze_history") or []:
        if not row.freeze_from or not row.freeze_to:
            frappe.throw("Freeze From and Freeze To are required.")
        row_start = getdate(row.freeze_from)
        row_end = getdate(row.freeze_to)
        if row_end <= row_start:
            frappe.throw("Freeze To must be after Freeze From.")
        row.days = (row_end - row_start).days + 1
        total_days += row.days
        periods.append((row_start, row_end))

    if any(start <= old_end and end >= old_start for old_start, old_end in periods):
        frappe.throw("Membership freeze periods cannot overlap.")

    new_days = (end - start).days + 1
    if total_days + new_days > max_days:
        frappe.throw(
            f"Total freeze days ({total_days + new_days}) exceed "
            f"the plan limit ({max_days})."
        )

    membership.append(
        "freeze_history",
        {
            "freeze_from": start,
            "freeze_to": end,
            "days": new_days,
            "reason": reason,
        },
    )

    # Explicitly calculate extension because this document is already submitted.
    membership.end_date = add_days(getdate(membership.end_date), new_days)
    membership.save()

    # Persist values explicitly for a submitted document.
    for row in membership.get("freeze_history") or []:
        if row.freeze_from and row.freeze_to:
            row.db_set(
                "days",
                (getdate(row.freeze_to) - getdate(row.freeze_from)).days + 1,
            )
    membership.db_set("end_date", membership.end_date)

    if start <= current_date <= end:
        membership.db_set("status", "Frozen")

    return {
        "membership": membership.name,
        "end_date": membership.end_date,
        "status": "Frozen" if start <= current_date <= end else membership.status,
        "message": "Freeze period added successfully.",
    }

@frappe.whitelist()
def renew_membership(membership_name):
    """Create and submit a replacement membership for an expired membership."""
    if not membership_name:
        frappe.throw("Membership is required.")

    old = frappe.get_doc("Gym Membership", membership_name)
    old.check_permission("read")

    if old.docstatus != 1:
        frappe.throw("Only submitted memberships can be renewed.")

    if old.status != "Expired":
        frappe.throw("Only expired memberships can be renewed.")

    if frappe.db.exists(
        "Gym Membership",
        {
            "member": old.member,
            "docstatus": 1,
            "status": "Active",
        },
    ):
        frappe.throw("This member already has an active membership.")

    start_date = getdate(today())

    if old.end_date and getdate(old.end_date) >= start_date:
        start_date = add_days(getdate(old.end_date), 1)

    new_membership = frappe.get_doc({
        "doctype": "Gym Membership",
        "member": old.member,
        "membership_plan": old.membership_plan,
        "start_date": start_date,
        "status": "Draft",
    })

    new_membership.insert()
    new_membership.submit()

    return {
        "name": new_membership.name,
        "status": new_membership.status,
        "sales_invoice": new_membership.sales_invoice,
    }
