import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from gym_management.gym_management.doctype.class_session.class_session import ClassSession


class TestClassSession(unittest.TestCase):
    @patch("gym_management.gym_management.doctype.class_session.class_session.frappe.db.get_value", return_value=45)
    @patch("gym_management.gym_management.doctype.class_session.class_session.frappe.db.exists", return_value=False)
    @patch("gym_management.gym_management.doctype.class_session.class_session.frappe.get_doc")
    @patch("gym_management.gym_management.doctype.class_session.class_session.now_datetime", return_value=datetime(2026, 10, 14, 8, 0))
    def test_sets_end_datetime_from_class_duration(self, now, get_doc, exists, get_value):
        get_doc.side_effect = [
            SimpleNamespace(status="Active", capacity=20),
        ]
        session = ClassSession({
            "doctype": "Class Session",
            "gym_class": "CLASS-0001",
            "start_datetime": "2026-10-15 10:00:00",
            "capacity": 10,
            "status": "Scheduled",
        })
        session.set_end_datetime()
        self.assertEqual(str(session.end_datetime), "2026-10-15 10:45:00")

    @patch("gym_management.gym_management.doctype.class_session.class_session.frappe.throw", side_effect=Exception("invalid range"))
    def test_rejects_end_before_start(self, throw):
        session = ClassSession({
            "doctype": "Class Session",
            "start_datetime": "2026-10-15 11:00:00",
            "end_datetime": "2026-10-15 10:00:00",
            "status": "Scheduled",
        })
        with self.assertRaises(Exception):
            session.validate_time_range()

    @patch("gym_management.gym_management.doctype.class_session.class_session.frappe.db.exists", return_value=True)
    def test_detects_overlapping_trainer_or_room(self, exists):
        session = ClassSession({
            "doctype": "Class Session",
            "trainer": "TRAINER-0001",
            "room": "ROOM-0001",
            "start_datetime": "2026-10-15 10:00:00",
            "end_datetime": "2026-10-15 11:00:00",
            "status": "Scheduled",
        })
        with self.assertRaises(Exception):
            session.validate_no_overlaps()
        self.assertEqual(exists.call_count, 1)


    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.throw",
        side_effect=Exception("Only active gym classes can be scheduled."),
    )
    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.get_doc"
    )
    def test_rejects_inactive_gym_class(self, get_doc, throw):
        get_doc.return_value = SimpleNamespace(status="Inactive", capacity=20)
        session = ClassSession({
            "doctype": "Class Session",
            "gym_class": "CLASS-0001",
            "capacity": 10,
        })
        with self.assertRaises(Exception):
            session.validate_class_and_capacity()

    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.throw",
        side_effect=Exception("Session capacity cannot exceed the class capacity."),
    )
    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.get_doc"
    )
    def test_rejects_capacity_above_gym_class_capacity(self, get_doc, throw):
        get_doc.return_value = SimpleNamespace(status="Active", capacity=10)
        session = ClassSession({
            "doctype": "Class Session",
            "gym_class": "CLASS-0001",
            "capacity": 15,
        })
        with self.assertRaises(Exception):
            session.validate_class_and_capacity()

    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.throw",
        side_effect=Exception("The selected trainer is not active."),
    )
    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.get_doc"
    )
    def test_rejects_inactive_trainer(self, get_doc, throw):
        get_doc.return_value = SimpleNamespace(status="Inactive")
        session = ClassSession({
            "doctype": "Class Session",
            "trainer": "TRAINER-0001",
            "start_datetime": "2026-10-15 10:00:00",
            "end_datetime": "2026-10-15 11:00:00",
        })
        with self.assertRaises(Exception):
            session.validate_room_and_trainer_availability()

    @patch(
        "gym_management.gym_management.doctype.class_session.class_session.frappe.db.exists",
        return_value=False,
    )
    def test_overlap_check_excludes_current_session_when_editing(self, exists):
        session = ClassSession({
            "doctype": "Class Session",
            "name": "SESS-0001",
            "trainer": "TRAINER-0001",
            "room": "ROOM-0001",
            "start_datetime": "2026-10-15 10:00:00",
            "end_datetime": "2026-10-15 11:00:00",
            "status": "Scheduled",
        })
        session.validate_no_overlaps()
        self.assertEqual(exists.call_count, 2)
        for call in exists.call_args_list:
            self.assertEqual(call.args[0], "Class Session")
            self.assertEqual(call.args[1]["name"], ["!=", "SESS-0001"])
