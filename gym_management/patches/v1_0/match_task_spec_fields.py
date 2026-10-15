"""Carry data across the last round of field changes.

- Gym Check In.gym_membership became ``membership``.
- Gym Member.active_membership is now written by the system, so it is
  backfilled for members who already hold an Active membership.
"""

import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
    rename_check_in_membership()
    backfill_active_membership()


def rename_check_in_membership():
    if frappe.db.has_column("Gym Check In", "gym_membership"):
        rename_field("Gym Check In", "gym_membership", "membership")


def backfill_active_membership():
    """One UPDATE for every member, rather than a query each."""
    frappe.db.sql(
        """
        UPDATE `tabGym Member` member
        LEFT JOIN `tabGym Membership` membership
            ON membership.member = member.name
           AND membership.docstatus = 1
           AND membership.status = 'Active'
        SET member.active_membership = membership.name
        """
    )
