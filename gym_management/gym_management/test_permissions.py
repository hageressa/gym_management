import unittest
from types import SimpleNamespace
from unittest.mock import patch

from gym_management import permissions

MODULE = "gym_management.permissions"


class TestTrainerScope(unittest.TestCase):
    @patch(f"{MODULE}.frappe.get_roles", return_value=["Trainer", "Gym Manager"])
    def test_a_manager_who_also_trains_is_not_narrowed(self, roles):
        self.assertEqual(permissions.class_session_query("manager@gym.test"), "")

    @patch(f"{MODULE}.get_trainer_for_user", return_value="TRN-0001")
    @patch(f"{MODULE}.frappe.get_roles", return_value=["Trainer"])
    def test_a_trainer_lists_only_their_sessions(self, roles, trainer):
        condition = permissions.class_session_query("ahmed@gym.test")

        self.assertIn("`trainer` = 'TRN-0001'", condition)

    @patch(f"{MODULE}.get_trainer_for_user", return_value=None)
    @patch(f"{MODULE}.frappe.get_roles", return_value=["Trainer"])
    def test_a_trainer_user_with_no_trainer_record_sees_nothing(self, roles, trainer):
        self.assertEqual(permissions.class_session_query("new@gym.test"), "1=0")
        self.assertEqual(permissions.class_booking_query("new@gym.test"), "1=0")

    @patch(f"{MODULE}.get_trainer_for_user", return_value="TRN-0001")
    @patch(f"{MODULE}.frappe.get_roles", return_value=["Trainer"])
    def test_a_trainer_opens_their_own_session_but_not_another(self, roles, trainer):
        own = SimpleNamespace(trainer="TRN-0001")
        other = SimpleNamespace(trainer="TRN-0002")

        self.assertTrue(permissions.class_session_has_permission(own, "read", "ahmed@gym.test"))
        self.assertFalse(permissions.class_session_has_permission(other, "read", "ahmed@gym.test"))

    @patch(f"{MODULE}.frappe.db.get_value", return_value="TRN-0002")
    @patch(f"{MODULE}.get_trainer_for_user", return_value="TRN-0001")
    @patch(f"{MODULE}.frappe.get_roles", return_value=["Trainer"])
    def test_a_trainer_cannot_mark_attendance_on_another_trainers_class(self, roles, trainer, get_value):
        booking = SimpleNamespace(class_session="SESS-0009")

        self.assertFalse(permissions.class_booking_has_permission(booking, "write", "ahmed@gym.test"))
