

import frappe
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime


class ClassBooking(Document):
    def on_update(self):
        previous = self.get_doc_before_save()

        if not previous or previous.status == "Cancelled":
            return

        if self.status != "Cancelled":
            return

        session = frappe.get_doc("Class Session", self.class_session)

        if session.status != "Scheduled":
            return

        if session.start_datetime and session.start_datetime <= now_datetime():
            return

        confirmed_count = frappe.db.count(
            "Class Booking",
            {
                "class_session": self.class_session,
                "status": ["in", ["Booked", "Attended"]],
            },
        )

        if confirmed_count >= session.capacity:
            return

        waitlisted = frappe.get_all(
            "Class Booking",
            filters={
                "class_session": self.class_session,
                "status": "Waitlisted",
            },
            fields=["name", "member"],
            order_by="waitlist_position asc",
        )

        session_date = (
            getdate(session.start_datetime)
            if session.start_datetime
            else getdate()
        )

        for row in waitlisted:
            memberships = frappe.get_all(
                "Gym Membership",
                filters={
                    "member": row.member,
                    "docstatus": 1,
                    "status": "Active",
                },
                fields=["start_date", "end_date"],
            )

            has_valid_membership = any(
                (not membership.start_date or getdate(membership.start_date) <= session_date)
                and (
                    not membership.end_date
                    or getdate(membership.end_date) >= session_date
                )
                for membership in memberships
            )

            if not has_valid_membership:
                continue

            booking = frappe.get_doc("Class Booking", row.name)
            booking.status = "Booked"
            booking.waitlist_position = None
            booking.save(ignore_permissions=True)
            break

    def validate(self):
        if self.status == "Cancelled":
            self.waitlist_position = None
            return

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

        if self.status == "Cancelled":
            self.waitlist_position = None
            return

        confirmed_count = frappe.db.count(
            "Class Booking",
            {
                "class_session": self.class_session,
                "status": ["in", ["Booked", "Attended"]],
                "name": ["!=", self.name or ""],
            },
        )

        if confirmed_count >= session.capacity:
            settings = frappe.get_single("Gym Settings")

            if not settings.enable_waitlist:
                frappe.throw(
                    "This class session is full and the waitlist is disabled."
                )

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
