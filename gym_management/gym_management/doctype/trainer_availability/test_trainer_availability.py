import unittest
from unittest.mock import patch

import frappe

MODULE = "gym_management.gym_management.doctype.trainer_availability.trainer_availability"


def make_window(**values):
    window = {
        "doctype": "Trainer Availability",
        "trainer": "TRN-0001",
        "day_of_week": "Monday",
        "from_time": "09:00:00",
        "to_time": "12:00:00",
    }
    window.update(values)
    return frappe.get_doc(window)


class TestTrainerAvailability(unittest.TestCase):
    def test_to_time_must_be_after_from_time(self):
        with self.assertRaises(frappe.ValidationError):
            make_window(from_time="12:00:00", to_time="09:00:00").validate_time_range()

    def test_an_ordinary_window_passes(self):
        make_window().validate_time_range()

    def test_an_overlapping_window_is_refused(self):
        window = make_window()

        with patch(f"{MODULE}.frappe.db.exists", return_value=True) as exists:
            with self.assertRaises(frappe.ValidationError):
                window.validate_no_overlap()

        filters = exists.call_args.args[1]
        self.assertEqual(filters["from_time"], ["<", "12:00:00"])
        self.assertEqual(filters["to_time"], [">", "09:00:00"])
