import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import now_datetime, today

from gym_management.utils import get_latest_membership, get_membership_block_reason


class GymCheckIn(Document):
    def validate(self):
        self.validate_membership()
        self.validate_class_booking()

    def validate_membership(self):
        """Resolve which membership to judge, then apply the entry rules to it."""
        if not self.member:
            frappe.throw(_("Please select a Gym Member."))

        membership_name = self.membership or self.get_latest_membership_name()
        if not membership_name:
            frappe.throw(_("This member has no submitted membership."))

        membership = frappe.get_doc("Gym Membership", membership_name)
        if membership.member != self.member:
            frappe.throw(_("The membership does not belong to this member."))

        self.check_membership_allows_entry(membership)

        self.membership = membership.name
        if not self.check_in_time:
            self.check_in_time = now_datetime()

    def get_latest_membership_name(self):
        """Latest submitted membership, expired included, so the refusal can say why."""
        return get_latest_membership(self.member)

    def check_membership_allows_entry(self, membership):
        """Entry is allowed only when the shared rule says the membership is usable today."""
        reason = get_membership_block_reason(membership, today())
        if reason:
            frappe.throw(_("Entry denied: {0}.").format(reason))

    def validate_class_booking(self):
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)

        if booking.member != self.member:
            frappe.throw(_("The class booking does not belong to this member."))

        if booking.status not in ("Booked", "Attended"):
            frappe.throw(_("Check-in requires a confirmed class booking."))

    def on_update(self):
        """A check-in made against a booking marks that booking as Attended."""
        if not self.class_booking:
            return

        booking = frappe.get_doc("Class Booking", self.class_booking)
        if booking.status == "Booked":
            booking.status = "Attended"
            booking.save(ignore_permissions=True)
