

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ClassBooking(Document):
    def validate(self):
        self.validate_session()
        self.validate_membership()
        self.validate_duplicate_booking()
        self.validate_capacity()

    def validate_session(self):
        if not self.class_session:
            frappe.throw("Please select a Class Session.")

        session = frappe.get_doc("Class Session", self.class_session)

        if session.status != "Scheduled":
            frappe.throw("Bookings are allowed only for scheduled sessions.")

        if session.start_datetime and session.start_datetime < now_datetime():
            frappe.throw("Cannot book a session that has already started.")

    def validate_membership(self):
        if not self.member:
            frappe.throw("Please select a Gym Member.")

        memberships = frappe.get_all(
            "Gym Membership",
            filters={
                "member": self.member,
                "docstatus": 1,
                "status": "Active",
            },
            fields=["name", "start_date", "end_date"],
        )

        today = getdate()
        valid = any(
            (not m.start_date or getdate(m.start_date) <= today)
            and (not m.end_date or getdate(m.end_date) >= today)
            for m in memberships
        )

        if not valid:
            frappe.throw("The member does not have a valid active membership.")

    def validate_duplicate_booking(self):
        if not self.member or not self.class_session:
            return

        filters = {
            "member": self.member,
            "class_session": self.class_session,
            "status": ["in", ["Booked", "Waitlisted", "Attended"]],
        }

        if not self.is_new():
            filters["name"] = ["!=", self.name]

        if frappe.db.exists("Class Booking", filters):
            frappe.throw("This member already has a booking for this session.")

    def validate_capacity(self):
        if not self.class_session:
            return

        session = frappe.get_doc("Class Session", self.class_session)

        if not session.capacity or session.capacity < 1:
            frappe.throw("Set a valid capacity on the Class Session.")

        confirmed_count = frappe.db.count(
            "Class Booking",
            {
                "class_session": self.class_session,
                "status": ["in", ["Booked", "Attended"]],
                "name": ["!=", self.name or ""],
            },
        )

        if confirmed_count >= session.capacity:
            self.status = "Waitlisted"

        if self.status == "Waitlisted" and not self.waitlist_position:
            last_position = frappe.db.get_value(
                "Class Booking",
                {
                    "class_session": self.class_session,
                    "status": "Waitlisted",
                },
                "waitlist_position",
                order_by="waitlist_position desc",
            )
            self.waitlist_position = (last_position or 0) + 1
        elif self.status != "Waitlisted":
            self.waitlist_position = None