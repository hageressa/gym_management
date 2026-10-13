
import unittest
from unittest.mock import patch, Mock
from types import SimpleNamespace

from gym_management.gym_management.doctype.class_booking.class_booking import (
    ClassBooking,
)


class TestClassBooking(unittest.TestCase):
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_rejects_non_scheduled_session(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(
            status="Cancelled",
            start_datetime=None,
        )

        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
        })

        with self.assertRaises(Exception):
            booking.validate_session()

    def test_requires_member(self):
        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
        })

        with self.assertRaises(Exception):
            booking.validate_membership()

    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_single"
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.db.count",
        return_value=2,
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_full_session_rejects_booking_when_waitlist_disabled(
        self, mock_get_doc, mock_count, mock_get_single
    ):
        mock_get_doc.return_value = SimpleNamespace(capacity=2)
        mock_get_single.return_value = SimpleNamespace(enable_waitlist=0)

        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
            "status": "Booked",
        })

        with self.assertRaises(Exception):
            booking.validate_capacity()

    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.db.get_value",
        return_value=3,
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_single"
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.db.count",
        return_value=2,
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_full_session_adds_booking_to_waitlist(
        self, mock_get_doc, mock_count, mock_get_single, mock_get_value
    ):
        mock_get_doc.return_value = SimpleNamespace(capacity=2)
        mock_get_single.return_value = SimpleNamespace(enable_waitlist=1)

        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
            "status": "Booked",
        })

        booking.validate_capacity()

        self.assertEqual(booking.status, "Waitlisted")
        self.assertEqual(booking.waitlist_position, 4)

    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_cancelled_booking_clears_waitlist_position(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(capacity=2)

        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
            "status": "Cancelled",
            "waitlist_position": 3,
        })

        booking.validate_capacity()

        self.assertEqual(booking.status, "Cancelled")
        self.assertIsNone(booking.waitlist_position)


    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_all"
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.db.count",
        return_value=0,
    )
    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_cancelling_booking_promotes_first_valid_waitlisted_member(
        self, mock_get_doc, mock_count, mock_get_all
    ):
        session = SimpleNamespace(
            status="Scheduled",
            start_datetime=None,
            capacity=2,
        )
        promoted_booking = SimpleNamespace(
            status="Waitlisted",
            waitlist_position=1,
            name="BOOKING-2",
            save=Mock(),
        )

        def get_doc_side_effect(doctype, name=None):
            if doctype == "Class Session":
                return session
            return promoted_booking

        mock_get_doc.side_effect = get_doc_side_effect
        mock_get_all.side_effect = [
            [SimpleNamespace(name="BOOKING-2", member="MEMBER-2")],
            [SimpleNamespace(start_date=None, end_date=None)],
        ]

        cancelled_booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
            "status": "Cancelled",
        })

        with patch.object(
            ClassBooking,
            "get_doc_before_save",
            return_value=SimpleNamespace(status="Booked"),
        ), patch.object(
            cancelled_booking,
            "notify_member_booking_confirmed",
        ) as notify_member, patch(
            "gym_management.gym_management.doctype.class_booking.class_booking.getdate",
            return_value=__import__("datetime").date(2026, 10, 13),
        ):
            cancelled_booking.on_update()

        self.assertEqual(promoted_booking.status, "Booked")
        self.assertIsNone(promoted_booking.waitlist_position)
        promoted_booking.save.assert_called_once_with(ignore_permissions=True)
        notify_member.assert_called_once_with("MEMBER-2", "BOOKING-2")

    @patch(
        "gym_management.gym_management.doctype.class_booking.class_booking.frappe.get_doc"
    )
    def test_cancellation_skips_session_and_membership_validation(self, mock_get_doc):
        booking = ClassBooking({
            "doctype": "Class Booking",
            "class_session": "SESSION-TEST",
            "member": "MEMBER-TEST",
            "status": "Cancelled",
            "waitlist_position": 2,
        })

        with patch.object(booking, "validate_session") as validate_session, patch.object(
            booking, "validate_membership"
        ) as validate_membership, patch.object(
            booking, "validate_duplicate_booking"
        ) as validate_duplicate, patch.object(
            booking, "validate_capacity"
        ) as validate_capacity:
            booking.validate()

        self.assertIsNone(booking.waitlist_position)
        validate_session.assert_not_called()
        validate_membership.assert_not_called()
        validate_duplicate.assert_not_called()
        validate_capacity.assert_not_called()
