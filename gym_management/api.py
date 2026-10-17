import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, getdate, today

from gym_management.utils import (
    combine_date_time,
    get_latest_membership,
    get_membership_block_reason,
    sync_member_active_membership,
)

SESSION_FIELDS = [
    "name",
    "gym_class",
    "trainer",
    "room",
    "session_date",
    "start_time",
    "end_time",
    "capacity",
    "booked_count",
    "status",
]


@frappe.whitelist()
def book_class(session, member):
    """Book a member onto a session. The controller decides Booked vs Waitlisted."""
    return create_booking(session, member)


def create_booking(session, member, ignore_permissions=False):
    """Insert the booking; the Class Booking controller applies every rule.

    ``ignore_permissions`` is for the member portal only, which has already
    confirmed that ``member`` is the signed-in user.
    """
    if not session or not member:
        frappe.throw(_("Session and member are required."))

    booking = frappe.get_doc({
        "doctype": "Class Booking",
        "class_session": session,
        "member": member,
        "booking_date": today(),
        "status": "Booked",
    })

    booking.insert(ignore_permissions=ignore_permissions)

    return {
        "booking": booking.name,
        "status": booking.status,
        "waitlist_position": booking.waitlist_position,
    }


@frappe.whitelist()
def get_available_sessions(date_from, date_to):
    """Scheduled sessions in the date range that still have a free spot."""
    start_date = getdate(date_from)
    end_date = getdate(date_to)

    if end_date < start_date:
        frappe.throw(_("End date cannot be before start date."))

    sessions = frappe.get_all(
        "Class Session",
        filters={
            "status": "Scheduled",
            "session_date": ["between", [start_date, end_date]],
        },
        fields=SESSION_FIELDS,
        order_by="session_date asc, start_time asc",
    )

    available_sessions = []

    for session in sessions:
        # booked_count is kept current by the Class Booking hooks, so there is
        # no need for a count query per session here.
        available_spots = max((session.capacity or 0) - (session.booked_count or 0), 0)

        if available_spots > 0:
            session["available_spots"] = available_spots
            available_sessions.append(session)

    return available_sessions


@frappe.whitelist()
def freeze_membership(membership_name, freeze_from, freeze_to, reason=None):
    """Pause a submitted membership for a date range and push its end date out."""
    membership = frappe.get_doc("Gym Membership", membership_name)
    membership.check_permission("write")

    start, end = getdate(freeze_from), getdate(freeze_to)
    validate_freeze_period(membership, start, end)

    days = (end - start).days + 1

    # The membership is submitted, so write the changes directly instead of save().
    row = membership.append(
        "freeze_history",
        {"freeze_from": start, "freeze_to": end, "days": days, "reason": reason},
    )
    row.db_insert()

    new_end_date = add_days(getdate(membership.end_date), days)
    membership.db_set("end_date", new_end_date)

    if start <= getdate(today()) <= end:
        membership.db_set("status", "Frozen")
        sync_member_active_membership(membership.member)

    return {
        "membership": membership.name,
        "end_date": new_end_date,
        "status": membership.status,
    }


def validate_freeze_period(membership, start, end):
    """Check the range is sane, does not overlap an earlier freeze, and fits the plan limit."""
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
        {"member": old.member, "docstatus": 1, "status": ["in", ["Active", "Frozen"]]},
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
        "auto_renew": old.auto_renew,
        "status": "Draft",
    })

    new_membership.insert()
    new_membership.submit()

    return {
        "name": new_membership.name,
        "status": new_membership.status,
        "sales_invoice": new_membership.sales_invoice,
    }


@frappe.whitelist()
def get_dashboard_data():
    """Every figure the Gym Dashboard page shows, gathered in one call.

    Revenue is in here, so only the roles the page is given may call it.
    """
    frappe.only_for(("System Manager", "Gym Manager"))
    today_date = getdate(today())
    month_start = today_date.replace(day=1)

    return {
        "active_members": count_active_members(),
        "expiring_soon": count_memberships_expiring_within(today_date, 7),
        "today_sessions": get_sessions_on(today_date),
        "revenue_this_month": get_membership_revenue_since(month_start),
        "currency": frappe.defaults.get_global_default("currency"),
    }


def count_active_members():
    """How many distinct members hold a submitted, Active membership.

    Our own rule allows only one active membership per member, but counting
    distinct members keeps the figure right even if the data drifts.
    """
    members = frappe.get_all(
        "Gym Membership",
        filters={"docstatus": 1, "status": "Active"},
        pluck="member",
    )
    return len(set(members))


def count_memberships_expiring_within(from_date, days):
    return frappe.db.count(
        "Gym Membership",
        {
            "docstatus": 1,
            "status": "Active",
            "end_date": ["between", [from_date, add_days(from_date, days)]],
        },
    )


def get_sessions_on(on_date):
    """Sessions starting on ``on_date``, with their fill rate and display names."""
    sessions = frappe.get_all(
        "Class Session",
        filters={"session_date": on_date},
        fields=SESSION_FIELDS,
        order_by="start_time asc",
    )

    if not sessions:
        return []

    # Two lookups for the whole page rather than one per session.
    class_names = get_titles(
        "Gym Class", {s.gym_class for s in sessions if s.gym_class}, "class_name"
    )
    trainer_names = get_titles(
        "Gym Trainer", {s.trainer for s in sessions if s.trainer}, "trainer_name"
    )

    for session in sessions:
        session["class_name"] = class_names.get(session.gym_class)
        session["trainer_name"] = trainer_names.get(session.trainer)
        session["fill_rate"] = (
            round((session.booked_count or 0) * 100 / session.capacity)
            if session.capacity
            else 0
        )

    return sessions


def get_titles(doctype, names, title_field):
    """Map of name -> title for the given records, in a single query."""
    if not names:
        return {}

    rows = frappe.get_all(
        doctype,
        filters={"name": ["in", list(names)]},
        fields=["name", title_field],
        as_list=True,
    )
    return dict(rows)


def get_membership_revenue_since(from_date):
    """Total value of submitted membership invoices posted on or after ``from_date``.

    The join runs in SQL, so the invoice table never comes into Python.
    """
    membership = frappe.qb.DocType("Gym Membership")
    invoice = frappe.qb.DocType("Sales Invoice")

    result = (
        frappe.qb.from_(invoice)
        .join(membership)
        .on(membership.sales_invoice == invoice.name)
        .select(Sum(invoice.grand_total))
        .where(invoice.docstatus == 1)
        .where(invoice.posting_date >= from_date)
    ).run()

    return (result[0][0] if result else 0) or 0


@frappe.whitelist()
def find_members(search_text):
    """Front desk lookup by name, phone, email or member id.

    A QR scanner types the member id into the same box, so scanning is covered
    by the id match and needs no separate endpoint.
    """
    search_text = (search_text or "").strip()
    if len(search_text) < 2:
        return []

    pattern = f"%{search_text}%"

    # get_list, not get_all: a portal member must not be able to search everyone.
    return frappe.get_list(
        "Gym Member",
        or_filters={
            "name": ["like", pattern],
            "member_name": ["like", pattern],
            "phone": ["like", pattern],
            "email": ["like", pattern],
        },
        fields=["name", "member_name", "phone", "status"],
        order_by="member_name asc",
        limit=10,
    )


@frappe.whitelist()
def get_check_in_status(member):
    """Whether this member may enter today, and the reason when they may not."""
    frappe.has_permission("Gym Check In", "create", throw=True)
    membership_name = get_latest_membership(member)

    if not membership_name:
        return {
            "member": member,
            "allowed": False,
            "reason": _("no membership on file"),
        }

    membership = frappe.get_doc("Gym Membership", membership_name)
    reason = get_membership_block_reason(membership, today())

    return {
        "member": member,
        "allowed": reason is None,
        "reason": reason,
        "membership": membership.name,
        "plan": membership.membership_plan,
        "status": membership.status,
        "end_date": membership.end_date,
        "classes_remaining": membership.classes_remaining,
    }


@frappe.whitelist()
def check_in_member(member, method="Front Desk"):
    """Record a check-in.

    The Gym Check In controller re-checks the entry rules, so a member blocked
    between the status call and this one is still refused.
    """
    check_in = frappe.get_doc({
        "doctype": "Gym Check In",
        "member": member,
        "method": method,
    })
    check_in.insert()

    return {"name": check_in.name, "check_in_time": check_in.check_in_time}


@frappe.whitelist()
def get_session_calendar_events(start, end, filters=None):
    """Class sessions for the Class Session calendar view.

    The calendar wants one datetime for the start and one for the end, while
    the sessions store a date and two times, so they are combined here.
    get_list, not get_all, so a trainer's calendar shows only their sessions.
    """
    sessions = frappe.get_list(
        "Class Session",
        filters={"session_date": ["between", [start, end]]},
        fields=["name", "gym_class", "session_date", "start_time", "end_time", "status"],
        order_by="session_date asc, start_time asc",
    )

    return [
        {
            "name": session.name,
            "subject": session.gym_class,
            "starts_on": combine_date_time(session.session_date, session.start_time),
            "ends_on": combine_date_time(session.session_date, session.end_time),
            "status": session.status,
        }
        for session in sessions
        if session.start_time and session.end_time
    ]
