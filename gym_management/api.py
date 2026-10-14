import frappe
from frappe import _
from frappe.utils import add_days, getdate, today


@frappe.whitelist()
def book_class(session, member):
    if not session or not member:
        frappe.throw(_("Session and member are required."))

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
        frappe.throw(_("End date cannot be before start date."))

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
    membership = frappe.get_doc("Gym Membership", membership_name)
    membership.check_permission("write")

    start, end = getdate(freeze_from), getdate(freeze_to)
    validate_freeze_period(membership, start, end)

    days = (end - start).days + 1

    # الـ Membership submitted، فبنكتب التغييرات مباشرة بدل save()
    row = membership.append(
        "freeze_history",
        {"freeze_from": start, "freeze_to": end, "days": days, "reason": reason},
    )
    row.db_insert()

    new_end_date = add_days(getdate(membership.end_date), days)
    membership.db_set("end_date", new_end_date)

    if start <= getdate(today()) <= end:
        membership.db_set("status", "Frozen")

    return {
        "membership": membership.name,
        "end_date": new_end_date,
        "status": membership.status,
    }


def validate_freeze_period(membership, start, end):
    """يتأكد إن الفترة صحيحة، ومتداخلتش مع فترات سابقة، ومش تعدي الحد المسموح."""
    if membership.docstatus != 1 or membership.status not in ("Active", "Frozen"):
        frappe.throw(_("Only active or frozen memberships can be frozen."))

    if end <= start:
        frappe.throw(_("Freeze To must be after Freeze From."))

    if end < getdate(today()):
        frappe.throw(_("Freeze To cannot be in the past."))

    plan = frappe.get_doc("Membership Plan", membership.membership_plan)
    plan_limit = int(plan.max_freeze_days or 0)

    used_days = 0
    for old in membership.freeze_history:
        old_start, old_end = getdate(old.freeze_from), getdate(old.freeze_to)
        if start <= old_end and end >= old_start:
            frappe.throw(_("Membership freeze periods cannot overlap."))
        used_days += (old_end - old_start).days + 1

    new_days = (end - start).days + 1
    if used_days + new_days > plan_limit:
        frappe.throw(
            _("Total freeze days ({0}) exceed the plan limit ({1}).").format(
                used_days + new_days, plan_limit
            )
        )


@frappe.whitelist()
def renew_membership(membership_name):
    """Create and submit a replacement membership for an expired membership."""
    if not membership_name:
        frappe.throw(_("Membership is required."))

    old = frappe.get_doc("Gym Membership", membership_name)
    old.check_permission("read")

    if old.docstatus != 1:
        frappe.throw(_("Only submitted memberships can be renewed."))

    if old.status != "Expired":
        frappe.throw(_("Only expired memberships can be renewed."))

    if frappe.db.exists(
        "Gym Membership",
        {"member": old.member, "docstatus": 1, "status": "Active"},
    ):
        frappe.throw(_("This member already has an active membership."))

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