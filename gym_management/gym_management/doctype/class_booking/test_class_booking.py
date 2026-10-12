
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