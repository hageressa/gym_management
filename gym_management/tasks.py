import frappe
from frappe.utils import getdate, today


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
