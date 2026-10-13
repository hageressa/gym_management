import frappe
from html import escape
from frappe.utils import add_days, getdate, today


def update_expired_memberships():
    expired_memberships = frappe.get_all(
        "Gym Membership",
        filters={
            "docstatus": 1,
            "status": "Active",
            "end_date": ["<", today()],
        },
        pluck="name",
    )

    for membership_name in expired_memberships:
        membership = frappe.get_doc("Gym Membership", membership_name)
        if membership.end_date and getdate(membership.end_date) < getdate(today()):
            membership.db_set("status", "Expired", update_modified=False)

    frappe.db.commit()


def send_membership_expiry_reminders():
    settings = frappe.get_single("Gym Settings")
    reminder_days = int(settings.expiry_reminder_days or 0)

    if reminder_days <= 0:
        return

    memberships = frappe.get_all(
        "Gym Membership",
        filters={
            "docstatus": 1,
            "status": "Active",
            "end_date": ["between", [today(), add_days(today(), reminder_days)]],
            "expiry_reminder_sent": 0,
        },
        pluck="name",
    )

    for membership_name in memberships:
        try:
            membership = frappe.get_doc("Gym Membership", membership_name)
            member = frappe.get_doc("Gym Member", membership.member)

            if not member.email:
                continue

            member_name = escape(member.member_name or membership.member)

            frappe.sendmail(
                recipients=[member.email],
                subject="Your gym membership is expiring soon",
                message=(
                    f"<p>Hello {member_name},</p>"
                    f"<p>Your gym membership <b>{escape(membership.name)}</b> "
                    f"expires on <b>{membership.end_date}</b>.</p>"
                    "<p>Please contact the gym to renew your membership.</p>"
                ),
                delayed=True,
            )

            membership.db_set(
                "expiry_reminder_sent", 1, update_modified=False
            )

        except Exception:
            frappe.log_error(
                frappe.get_traceback(),
                f"Membership expiry reminder failed: {membership_name}",
            )
