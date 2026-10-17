from html import escape

import frappe
from frappe.utils import add_days, getdate, today

from gym_management.utils import get_latest_membership, is_frozen_on, sync_member_active_membership


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
            sync_member_active_membership(membership.member)

    frappe.db.commit()


def renew_auto_renew_memberships():
    """Daily: renew expired memberships marked auto_renew.

    Only the member's latest membership is renewed, so a term that was already
    renewed is never renewed again. Each renewal commits on its own; one that
    fails (an inactive plan, say) is logged and does not stop the rest.
    """
    from gym_management.api import renew_membership

    names = frappe.get_all(
        "Gym Membership",
        filters={"docstatus": 1, "status": "Expired", "auto_renew": 1},
        fields=["name", "member"],
    )

    for row in names:
        if get_latest_membership(row.member) != row.name:
            continue
        try:
            renew_membership(row.name)
            frappe.db.commit()
        except Exception:
            frappe.db.rollback()
            frappe.log_error(title="Gym membership auto-renew failed", message=frappe.get_traceback())


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
                title=f"Membership expiry reminder failed: {membership_name}",
                message=frappe.get_traceback(),
            )


def sync_freeze_statuses():
    """Keep each membership's Active/Frozen status in line with its freeze periods.

    Runs daily: freezes memberships whose freeze period covers today and
    reactivates the ones whose freeze period has ended.
    """
    current_date = getdate(today())
    membership_names = frappe.get_all(
        "Gym Membership",
        filters={"docstatus": 1, "status": ["in", ["Active", "Frozen"]]},
        pluck="name",
    )

    for membership_name in membership_names:
        membership = frappe.get_doc("Gym Membership", membership_name)
        is_frozen_today = is_frozen_on(membership, current_date)
        if membership.end_date and getdate(membership.end_date) < current_date:
            new_status = "Expired"
        else:
            new_status = "Frozen" if is_frozen_today else "Active"

        if membership.status != new_status:
            membership.db_set("status", new_status, update_modified=False)
            sync_member_active_membership(membership.member)
