

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
                fields=["name", "start_date", "end_date"],
            )

            has_valid_membership = False
            for membership_row in memberships:
                if (
                    membership_row.start_date
                    and getdate(membership_row.start_date) > session_date
                ):
                    continue

                if (
                    membership_row.end_date
                    and getdate(membership_row.end_date) < session_date
                ):
                    continue

                membership_doc = frappe.get_doc(
                    "Gym Membership", membership_row.name
                )
                is_frozen = any(
                    freeze.freeze_from
                    and freeze.freeze_to
                    and getdate(freeze.freeze_from)
                    <= session_date
                    <= getdate(freeze.freeze_to)
                    for freeze in (membership_doc.get("freeze_history") or [])
                )

                if not is_frozen:
                    has_valid_membership = True
                    break

            if not has_valid_membership:
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
                frappe.get_traceback(),
                "Gym waitlist promotion email failed",
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

        session = frappe.get_doc("Class Session", self.class_session)
        if not session.start_datetime:
            frappe.throw("The class session must have a start datetime.")

        session_date = getdate(session.start_datetime)

        for membership_row in memberships:
            if (
                membership_row.start_date
                and getdate(membership_row.start_date) > session_date
            ):
                continue

            if (
                membership_row.end_date
                and getdate(membership_row.end_date) < session_date
            ):
                continue

            membership = frappe.get_doc(
                "Gym Membership", membership_row.name
            )
            frozen = any(
                row.freeze_from
                and row.freeze_to
                and getdate(row.freeze_from) <= session_date
                <= getdate(row.freeze_to)
                for row in (membership.get("freeze_history") or [])
            )

            if frozen:
                continue

            return

        if memberships:
            frappe.throw(
                "The member has no valid membership for this session date, "
                "or the membership is frozen."
            )

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
            frappe.throw("Set a valid capacity on the Class Session.")

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
                frappe.throw(
                    "This class session is full and the waitlist is disabled."
                )
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
