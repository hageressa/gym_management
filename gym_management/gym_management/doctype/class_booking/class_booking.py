import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import getdate, now_datetime

from gym_management.utils import combine_date_time, get_valid_membership


class ClassBooking(Document):
    def on_update(self):
        """Promote the first valid waitlisted booking when a confirmed one is cancelled early."""
        previous = self.get_doc_before_save()

        if not previous or previous.status == "Cancelled":
            return

        if self.status != "Cancelled":
            return

        session = frappe.get_doc("Class Session", self.class_session)

        if session.status != "Scheduled":
            return

        if session.session_date and session.start_time:
            if combine_date_time(session.session_date, session.start_time) <= now_datetime():
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

        session_date = getdate(session.session_date) if session.session_date else getdate()

        for row in waitlisted:
            if not get_valid_membership(row.member, session_date):
                continue

            booking = frappe.get_doc("Class Booking", row.name)
            booking.status = "Booked"
            booking.waitlist_position = None
            booking.save(ignore_permissions=True)
            self.notify_member_booking_confirmed(row.member, booking.name)
            break

    def notify_member_booking_confirmed(self, member_id, booking_name):
        member = frappe.db.get_value(
            "Gym Member",
            member_id,
            ["member_name", "email"],
            as_dict=True,
        )

        if not member or not member.email:
            return

        try:
            frappe.sendmail(
                recipients=[member.email],
                subject="Your gym class booking is confirmed",
                message=(
                    f"Hello {frappe.utils.escape_html(member.member_name or 'Member')},"
                    f"<p>Your waitlisted class booking has been confirmed.</p>"
                    f"<p>Booking reference: {frappe.utils.escape_html(booking_name)}</p>"
                ),
                delayed=True,
            )
        except Exception:
            frappe.log_error(
                title="Gym waitlist promotion email failed",
                message=frappe.get_traceback(),
            )

    def validate(self):
        if self.status == "Cancelled":
            self.waitlist_position = None
            return

        # Completed bookings must remain editable after the session ends.
        if not self.is_new() and self.status in ("Attended", "No Show"):
            self.validate_duplicate_booking()
            self.waitlist_position = None
            return

        self.validate_session()
        self.validate_membership()
        self.validate_duplicate_booking()
        self.validate_capacity()

    def validate_session(self):
        if not self.class_session:
            frappe.throw(_("Please select a Class Session."))

        session = frappe.get_doc("Class Session", self.class_session)

        if session.status != "Scheduled":
            frappe.throw(_("Bookings are allowed only for scheduled sessions."))

        if session.session_date and session.start_time:
            if combine_date_time(session.session_date, session.start_time) < now_datetime():
                frappe.throw(_("Cannot book a session that has already started."))

    def validate_membership(self):
        if not self.member:
            frappe.throw(_("Please select a Gym Member."))

        session = frappe.get_doc("Class Session", self.class_session)
        if not session.session_date:
            frappe.throw(_("The class session must have a session date."))

        if not get_valid_membership(self.member, getdate(session.session_date)):
            frappe.throw(_("The member does not have a valid membership for this session date."))

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
            frappe.throw(_("This member already has a booking for this session."))

    def validate_capacity(self):
        if not self.class_session:
            return

        # Lock the session row so concurrent booking transactions serialize
        # their capacity checks. The lock is held until the transaction ends.
        frappe.db.get_value(
            "Class Session",
            self.class_session,
            "name",
            for_update=True,
        )
        session = frappe.get_doc("Class Session", self.class_session)

        if not session.capacity or session.capacity < 1:
            frappe.throw(_("Set a valid capacity on the Class Session."))

        if self.status == "Cancelled":
            self.waitlist_position = None
            return

        # Preserve completed states during unrelated edits.
        if self.status in ("Attended", "No Show"):
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
                frappe.throw(_("This class session is full and the waitlist is disabled."))
            self.status = "Waitlisted"

        if self.status == "Waitlisted":
            if not self.waitlist_position:
                last_position = frappe.db.get_value(
                    "Class Booking",
                    {
                        "class_session": self.class_session,
                        "status": "Waitlisted",
                        "name": ["!=", self.name or ""],
                    },
                    "waitlist_position",
                    order_by="waitlist_position desc",
                )
                self.waitlist_position = (last_position or 0) + 1
        else:
            self.waitlist_position = None
