import unittest
from unittest.mock import patch

import frappe
from frappe.utils import add_days, today

MODULE = "gym_management.gym_management.doctype.personal_training_session.personal_training_session"

# A Monday far enough ahead that "not in the past" never interferes.
MONDAY = "2030-01-07"


def make_session(**values):
    session = {
        "doctype": "Personal Training Session",
        "member": "MEM-0001",
        "trainer": "TRN-0001",
        "session_date": MONDAY,
        "start_time": "10:00:00",
        "duration_minutes": 60,
        "status": "Scheduled",
    }
    session.update(values)
    doc = frappe.get_doc(session)
    doc.set_end_time()
    return doc


def window(from_time, to_time):
    return frappe._dict(from_time=from_time, to_time=to_time)


class TestTiming(unittest.TestCase):
    def test_end_time_follows_from_the_duration(self):
        self.assertEqual(make_session(duration_minutes=45).end_time, "10:45:00")

    def test_a_session_past_midnight_is_refused(self):
        session = make_session(start_time="23:30:00", duration_minutes=60)

        with self.assertRaises(frappe.ValidationError):
            session.validate_time_range()

    def test_zero_duration_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            make_session(duration_minutes=0)

    def test_a_new_session_in_the_past_is_refused(self):
        session = make_session(session_date=add_days(today(), -1))

        with self.assertRaises(frappe.ValidationError):
            session.validate_not_in_the_past()


class TestMembership(unittest.TestCase):
    def test_a_member_without_a_valid_membership_is_refused(self):
        session = make_session()

        with patch(f"{MODULE}.get_valid_membership", return_value=None):
            with self.assertRaises(frappe.ValidationError):
                session.validate_membership()

    def test_the_valid_membership_is_recorded_on_the_session(self):
        session = make_session()

        with patch(f"{MODULE}.get_valid_membership", return_value="GYM-MEM-0001") as valid:
            session.validate_membership()

        self.assertEqual(session.membership, "GYM-MEM-0001")
        valid.assert_called_once_with("MEM-0001", MONDAY)

    def test_a_cancelled_session_skips_the_booking_rules(self):
        session = make_session(status="Cancelled")

        with patch(f"{MODULE}.get_valid_membership") as valid:
            session.validate()

        valid.assert_not_called()


class TestAvailability(unittest.TestCase):
    def test_a_session_inside_a_window_passes(self):
        session = make_session(start_time="10:00:00")

        with patch(f"{MODULE}.frappe.get_all", return_value=[window("09:00:00", "12:00:00")]) as get_all:
            session.validate_within_availability()

        self.assertEqual(get_all.call_args.kwargs["filters"]["day_of_week"], "Monday")

    def test_a_session_running_past_the_window_is_refused(self):
        session = make_session(start_time="11:30:00")

        with patch(f"{MODULE}.frappe.get_all", return_value=[window("09:00:00", "12:00:00")]):
            with self.assertRaises(frappe.ValidationError):
                session.validate_within_availability()

    def test_a_day_without_windows_is_refused(self):
        session = make_session()

        with patch(f"{MODULE}.frappe.get_all", return_value=[]):
            with self.assertRaises(frappe.ValidationError):
                session.validate_within_availability()


class TestConflicts(unittest.TestCase):
    def test_another_personal_session_for_the_trainer_is_refused(self):
        session = make_session()

        with patch(f"{MODULE}.frappe.db.exists", side_effect=[True]):
            with self.assertRaisesRegex(frappe.ValidationError, "personal training"):
                session.validate_no_trainer_conflict()

    def test_a_class_the_trainer_teaches_is_refused(self):
        session = make_session()

        with patch(f"{MODULE}.frappe.db.exists", side_effect=[False, True]) as exists:
            with self.assertRaisesRegex(frappe.ValidationError, "teaching a class"):
                session.validate_no_trainer_conflict()

        self.assertEqual(exists.call_args.args[0], "Class Session")

    def test_overlap_filters_compare_times_on_the_same_date(self):
        filters = make_session(start_time="10:00:00").overlapping(member="MEM-0001")

        self.assertEqual(filters["session_date"], MONDAY)
        self.assertEqual(filters["start_time"], ["<", "11:00:00"])
        self.assertEqual(filters["end_time"], [">", "10:00:00"])
        self.assertEqual(filters["status"], "Scheduled")

    def test_the_member_cannot_hold_two_sessions_at_once(self):
        session = make_session()

        with patch(f"{MODULE}.frappe.db.exists", return_value=True):
            with self.assertRaises(frappe.ValidationError):
                session.validate_no_member_conflict()
