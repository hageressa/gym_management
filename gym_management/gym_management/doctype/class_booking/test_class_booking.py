
import unittest
from unittest.mock import patch
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
