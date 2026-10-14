
import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class GymCheckIn(Document):
    def validate(self):
        self.validate_membership()
        self.validate_class_booking()

    def validate_class_booking(self):
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)

        if booking.member != self.member:
            frappe.throw("The class booking does not belong to this member.")

        if booking.status not in ("Booked", "Attended"):
            frappe.throw(
                "Check-in requires a confirmed class booking."
            )

    def on_update(self):
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)
        if booking.status == "Booked":
            booking.status = "Attended"
            booking.save(ignore_permissions=True)

    def validate_membership(self):
        if not self.member:
            frappe.throw("Please select a Gym Member.")

        membership_name = self.gym_membership

        if not membership_name:
            membership_name = frappe.db.get_value(
                "Gym Membership",
                {
                    "member": self.member,
                    "docstatus": 1,
                    "status": "Active",
                },
                "name",
            )

        if not membership_name:
            frappe.throw("No active membership found for this member.")

        membership = frappe.get_doc("Gym Membership", membership_name)

        if membership.member != self.member:
            frappe.throw("The membership does not belong to this member.")

        if membership.docstatus != 1 or membership.status != "Active":
            frappe.throw("Entry denied: membership is not active.")

        today = getdate()

        if membership.start_date and getdate(membership.start_date) > today:
            frappe.throw("Entry denied: membership has not started yet.")

        if membership.end_date and getdate(membership.end_date) < today:
            frappe.throw("Entry denied: membership has expired.")

        for row in membership.get("freeze_history") or []:
            if (
                row.freeze_from
                and row.freeze_to
                and getdate(row.freeze_from) <= today <= getdate(row.freeze_to)
            ):
                frappe.throw(
                    "Entry denied: membership is frozen today."
                )

        self.gym_membership = membership.name

        if not self.check_in_time:
            self.check_in_time = now_datetime()