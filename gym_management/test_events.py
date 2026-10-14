import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from frappe.tests.utils import FrappeTestCase

from gym_management import events


def make_booking(**values):
    booking = MagicMock()
    defaults = {
        "status": "Booked",
        "booked_on": None,
        "cancelled_on": None,
        "membership": None,
        "member": "MEMBER-1",
        "class_session": "SESS-1",
    }
    defaults.update(values)
    for key, value in defaults.items():
        setattr(booking, key, value)
    return booking


class TestBookingMetadata(FrappeTestCase):
    @patch("gym_management.events.get_valid_membership", return_value="MEM-1")
    @patch("gym_management.events.frappe.db.get_value")
    def test_sets_booked_on_and_membership(self, get_value, get_valid):
        get_value.return_value = datetime.datetime(2026, 10, 20, 9, 0)
        booking = make_booking()

        events.set_booking_metadata(booking)

        self.assertIsNotNone(booking.booked_on)
        self.assertEqual(booking.membership, "MEM-1")
        get_valid.assert_called_once_with("MEMBER-1", datetime.date(2026, 10, 20))

    @patch("gym_management.events.get_valid_membership", return_value=None)
    @patch("gym_management.events.frappe.db.get_value", return_value=None)
    def test_sets_cancelled_on_when_cancelled(self, get_value, get_valid):
        booking = make_booking(status="Cancelled")

        events.set_booking_metadata(booking)

        self.assertIsNotNone(booking.cancelled_on)
        self.assertIsNone(booking.booked_on)

    @patch("gym_management.events.get_valid_membership", return_value=None)
    @patch("gym_management.events.frappe.db.get_value")
    def test_keeps_original_booked_on(self, get_value, get_valid):
        get_value.return_value = None
        original = datetime.datetime(2026, 1, 1, 8, 0)
        booking = make_booking(booked_on=original)

        events.set_booking_metadata(booking)

        self.assertEqual(booking.booked_on, original)


class TestSessionBookedCount(FrappeTestCase):
    @patch("gym_management.events.frappe.db.set_value")
    @patch("gym_management.events.frappe.db.count", return_value=3)
    def test_stores_confirmed_booking_count(self, count, set_value):
        events.update_session_booked_count(make_booking(), "on_update")

        set_value.assert_called_once_with(
            "Class Session", "SESS-1", "booked_count", 3, update_modified=False
        )

    @patch("gym_management.events.frappe.db.set_value")
    @patch("gym_management.events.frappe.db.count", return_value=2)
    def test_on_trash_excludes_deleted_booking(self, count, set_value):
        booking = make_booking(name="BOOK-9")

        events.update_session_booked_count(booking, "on_trash")

        filters = count.call_args[0][1]
        self.assertEqual(filters["name"], ["!=", "BOOK-9"])


class TestClassPackCredits(FrappeTestCase):
    @patch("gym_management.events.frappe.db.set_value")
    @patch("gym_management.events.frappe.db.get_value")
    def test_attended_booking_deducts_one_class(self, get_value, set_value):
        get_value.side_effect = ["PLAN-PACK", "Class Pack", 5]
        booking = make_booking(status="Attended", membership="MEM-1")
        booking.has_value_changed.return_value = True

        events.apply_booking_status_effects(booking)

        set_value.assert_called_once_with(
            "Gym Membership", "MEM-1", "classes_remaining", 4, update_modified=False
        )

    @patch("gym_management.events.frappe.db.set_value")
    @patch("gym_management.events.frappe.db.get_value")
    def test_time_based_membership_is_not_charged(self, get_value, set_value):
        get_value.side_effect = ["PLAN-MONTH", "Months"]
        booking = make_booking(status="Attended", membership="MEM-1")
        booking.has_value_changed.return_value = True

        events.apply_booking_status_effects(booking)

        set_value.assert_not_called()

    @patch("gym_management.events.frappe.throw", side_effect=Exception("empty"))
    @patch("gym_management.events.frappe.db.get_value")
    def test_empty_class_pack_blocks_new_booking(self, get_value, throw):
        get_value.side_effect = ["PLAN-PACK", "Class Pack", 0]
        booking = make_booking(membership="MEM-1")

        with self.assertRaises(Exception):
            events._validate_class_pack_balance(booking)

    @patch("gym_management.events.frappe.db.get_value")
    def test_unchanged_status_has_no_effect(self, get_value):
        booking = make_booking(status="Attended", membership="MEM-1")
        booking.has_value_changed.return_value = False

        events.apply_booking_status_effects(booking)

        get_value.assert_not_called()
