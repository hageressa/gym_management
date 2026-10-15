import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from gym_management.gym_management.doctype.class_session.class_session import ClassSession

MODULE = "gym_management.gym_management.doctype.class_session.class_session"


def frappe_dict(**values):
    """Stand-in for the dict frappe.db.get_value returns with as_dict=True."""
    return SimpleNamespace(**values)


def make_session(**values):
    defaults = {
        "doctype": "Class Session",
        "session_date": "2026-10-15",
        "start_time": "10:00:00",
        "end_time": "11:00:00",
        "status": "Scheduled",
    }
    defaults.update(values)
    return ClassSession(defaults)


class TestClassSessionTiming(unittest.TestCase):
    @patch(f"{MODULE}.frappe.db.get_value", return_value=45)
    def test_end_time_is_computed_from_the_class_duration(self, get_value):
        session = make_session(gym_class="CLASS-0001", end_time=None)

        session.set_end_time()

        self.assertEqual(session.end_time, "10:45:00")

    @patch(f"{MODULE}.frappe.db.get_value", return_value=45)
    def test_an_end_time_already_on_the_document_is_recomputed(self, get_value):
        """Frappe seeds an empty Time field with the current time, so a value
        sitting there is not an instruction to keep it."""
        session = make_session(gym_class="CLASS-0001", end_time="00:27:15")

        session.set_end_time()

        self.assertEqual(session.end_time, "10:45:00")

    @patch(f"{MODULE}.frappe.throw", side_effect=Exception("invalid range"))
    def test_rejects_end_before_start(self, throw):
        session = make_session(start_time="11:00:00", end_time="10:00:00")

        with self.assertRaises(Exception):
            session.validate_time_range()

    @patch(f"{MODULE}.now_datetime", return_value=datetime(2026, 10, 16, 8, 0))
    @patch(f"{MODULE}.frappe.throw", side_effect=Exception("starts in the past"))
    def test_rejects_a_new_session_that_starts_in_the_past(self, throw, now):
        session = make_session()  # 15 Oct, a day before the mocked "now"

        with self.assertRaises(Exception):
            session.validate_not_in_the_past()

    @patch(f"{MODULE}.now_datetime", return_value=datetime(2026, 10, 16, 8, 0))
    def test_editing_a_past_session_without_moving_it_is_allowed(self, now):
        """Changing the room on yesterday's session must still save."""
        session = make_session(name="SESS-0001")

        with patch.object(session, "is_new", return_value=False), patch.object(
            session, "has_value_changed", return_value=False
        ):
            session.validate_not_in_the_past()

    @patch(f"{MODULE}.now_datetime", return_value=datetime(2026, 10, 16, 8, 0))
    def test_a_cancelled_session_may_sit_in_the_past(self, now):
        session = make_session(status="Cancelled")

        session.validate_not_in_the_past()


class TestClassSessionCapacity(unittest.TestCase):
    @patch(f"{MODULE}.frappe.get_doc")
    def test_rejects_inactive_gym_class(self, get_doc):
        get_doc.return_value = SimpleNamespace(status="Inactive", default_capacity=20)
        session = make_session(gym_class="CLASS-0001", capacity=10)

        with self.assertRaises(Exception):
            session.validate_class_and_capacity()

    @patch(f"{MODULE}.frappe.get_doc")
    def test_rejects_capacity_above_the_class_default(self, get_doc):
        get_doc.return_value = SimpleNamespace(status="Active", default_capacity=10)
        session = make_session(gym_class="CLASS-0001", capacity=15)

        with self.assertRaises(Exception):
            session.validate_class_and_capacity()

    @patch(f"{MODULE}.frappe.get_doc")
    def test_capacity_falls_back_to_the_class_default(self, get_doc):
        get_doc.return_value = SimpleNamespace(status="Active", default_capacity=12)
        session = make_session(gym_class="CLASS-0001", capacity=0)

        session.validate_class_and_capacity()

        self.assertEqual(session.capacity, 12)

    @patch(f"{MODULE}.frappe.get_doc")
    def test_rejects_inactive_trainer(self, get_doc):
        get_doc.return_value = SimpleNamespace(is_active=0)
        session = make_session(trainer="TRN-0001")

        with self.assertRaises(Exception):
            session.validate_room_and_trainer_availability()

    @patch(f"{MODULE}.frappe.get_doc")
    def test_rejects_inactive_room(self, get_doc):
        get_doc.return_value = SimpleNamespace(is_active=0, capacity=10)
        session = make_session(room="ROOM-0001", capacity=5)

        with self.assertRaises(Exception):
            session.validate_room_and_trainer_availability()

    @patch(f"{MODULE}.frappe.get_doc")
    def test_rejects_capacity_above_the_room_capacity(self, get_doc):
        get_doc.return_value = SimpleNamespace(is_active=1, capacity=5)
        session = make_session(room="ROOM-0001", capacity=10)

        with self.assertRaises(Exception):
            session.validate_room_and_trainer_availability()


class TestClassSessionOverlaps(unittest.TestCase):
    @patch(f"{MODULE}.frappe.db.exists", return_value=True)
    def test_detects_an_overlapping_trainer_or_room(self, exists):
        session = make_session(trainer="TRN-0001", room="ROOM-0001")

        with self.assertRaises(Exception):
            session.validate_no_overlaps()

        # It stops at the first clash rather than checking both.
        self.assertEqual(exists.call_count, 1)

    @patch(f"{MODULE}.frappe.db.exists", return_value=False)
    def test_overlap_check_excludes_the_session_being_edited(self, exists):
        session = make_session(name="SESS-0001", trainer="TRN-0001", room="ROOM-0001")

        session.validate_no_overlaps()

        self.assertEqual(exists.call_count, 2)
        for call in exists.call_args_list:
            self.assertEqual(call.args[0], "Class Session")
            self.assertEqual(call.args[1]["name"], ["!=", "SESS-0001"])

    @patch(f"{MODULE}.frappe.db.exists", return_value=False)
    def test_overlap_query_compares_times_within_the_same_date(self, exists):
        session = make_session(trainer="TRN-0001")

        session.validate_no_overlaps()

        filters = exists.call_args.args[1]
        self.assertEqual(filters["session_date"], "2026-10-15")
        self.assertEqual(filters["start_time"], ["<", "11:00:00"])
        self.assertEqual(filters["end_time"], [">", "10:00:00"])


class TestClassSessionDefaults(unittest.TestCase):
    @patch(f"{MODULE}.frappe.db.get_value")
    def test_trainer_room_and_capacity_come_from_the_class(self, get_value):
        get_value.return_value = frappe_dict(
            default_trainer="TRN-0001", default_room="ROOM-0001", default_capacity=12
        )
        session = make_session(gym_class="CLASS-0001")

        session.set_defaults_from_class()

        self.assertEqual(session.trainer, "TRN-0001")
        self.assertEqual(session.room, "ROOM-0001")
        self.assertEqual(session.capacity, 12)

    @patch(f"{MODULE}.frappe.db.get_value")
    def test_values_set_on_the_session_win_over_the_class(self, get_value):
        get_value.return_value = frappe_dict(
            default_trainer="TRN-0001", default_room="ROOM-0001", default_capacity=12
        )
        session = make_session(gym_class="CLASS-0001", trainer="TRN-0009", capacity=4)

        session.set_defaults_from_class()

        self.assertEqual(session.trainer, "TRN-0009")
        self.assertEqual(session.capacity, 4)
        self.assertEqual(session.room, "ROOM-0001")
