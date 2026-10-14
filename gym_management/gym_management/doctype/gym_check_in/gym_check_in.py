import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime, today

from gym_management.utils import is_frozen_on


class GymCheckIn(Document):
    def validate(self):
        self.validate_membership()
        self.validate_class_booking()

    def validate_membership(self):
        if not self.member:
            frappe.throw(_("Please select a Gym Member."))

        membership_name = self.gym_membership or self.get_latest_membership_name()
        if not membership_name:
            frappe.throw(_("This member has no submitted membership."))

        membership = frappe.get_doc("Gym Membership", membership_name)
        if membership.member != self.member:
            frappe.throw(_("The membership does not belong to this member."))

        self.check_membership_allows_entry(membership)

        self.gym_membership = membership.name
        if not self.check_in_time:
            self.check_in_time = now_datetime()

    def get_latest_membership_name(self):
        """أحدث عضوية متسجلة للعضو، حتى لو منتهية، عشان نقدر نعرض السبب الصح."""
        return frappe.db.get_value(
            "Gym Membership",
            {"member": self.member, "docstatus": 1},
            "name",
            order_by="end_date desc",
        )

    def check_membership_allows_entry(self, membership):
    
        today_date = getdate(today())

        if membership.status == "Cancelled":
            frappe.throw(_("Entry denied: membership is cancelled."))

        if membership.status == "Expired" or (
            membership.end_date and getdate(membership.end_date) < today_date
        ):
            frappe.throw(_("Entry denied: membership has expired."))

        if membership.status == "Frozen" or is_frozen_on(membership, today_date):
            frappe.throw(_("Entry denied: membership is frozen today."))

        if membership.start_date and getdate(membership.start_date) > today_date:
            frappe.throw(_("Entry denied: membership has not started yet."))

        if membership.status != "Active":
            frappe.throw(_("Entry denied: membership is not active."))
    def validate_class_booking(self):
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)

        if booking.member != self.member:
            frappe.throw(_("The class booking does not belong to this member."))

        if booking.status not in ("Booked", "Attended"):
            frappe.throw(_("Check-in requires a confirmed class booking."))

    def on_update(self):
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)
        if booking.status == "Booked":
            booking.status = "Attended"
            booking.save(ignore_permissions=True)