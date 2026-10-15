import unittest
from unittest.mock import patch

from gym_management.utils import sync_member_active_membership

MODULE = "gym_management.utils"


class TestActiveMembershipSync(unittest.TestCase):
    """Gym Member.active_membership is read-only, so only this helper writes it."""

    @patch(f"{MODULE}.frappe.db.set_value")
    @patch(f"{MODULE}.frappe.db.get_value", return_value="GYM-MEM-2026-00001")
    def test_points_the_member_at_their_active_membership(self, get_value, set_value):
        sync_member_active_membership("MEM-0001")

        set_value.assert_called_once_with(
            "Gym Member",
            "MEM-0001",
            "active_membership",
            "GYM-MEM-2026-00001",
            update_modified=False,
        )

    @patch(f"{MODULE}.frappe.db.set_value")
    @patch(f"{MODULE}.frappe.db.get_value", return_value=None)
    def test_clears_the_field_when_nothing_is_active(self, get_value, set_value):
        sync_member_active_membership("MEM-0001")

        set_value.assert_called_once_with(
            "Gym Member",
            "MEM-0001",
            "active_membership",
            None,
            update_modified=False,
        )

    @patch(f"{MODULE}.frappe.db.set_value")
    def test_does_nothing_without_a_member(self, set_value):
        sync_member_active_membership(None)

        set_value.assert_not_called()
