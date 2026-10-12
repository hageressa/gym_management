
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from gym_management.gym_management.doctype.gym_check_in.gym_check_in import (
    GymCheckIn,
)


class TestGymCheckIn(unittest.TestCase):
    def test_rejects_member_without_active_membership(self):
        checkin = GymCheckIn({
            "doctype": "Gym Check In",
            "member": "TEST-MEMBER",
        })

        with patch(
            "gym_management.gym_management.doctype.gym_check_in.gym_check_in.frappe.db.get_value",
            return_value=None,
        ):
            with self.assertRaises(Exception):
                checkin.validate_membership()

    def test_rejects_membership_for_another_member(self):
        checkin = GymCheckIn({
            "doctype": "Gym Check In",
            "member": "TEST-MEMBER",
        })

        membership = SimpleNamespace(
            name="TEST-MEMBERSHIP",
            member="ANOTHER-MEMBER",
            docstatus=1,
            status="Active",
            start_date=None,
            end_date=None,
        )

        checkin.gym_membership = "TEST-MEMBERSHIP"

        with patch(
            "gym_management.gym_management.doctype.gym_check_in.gym_check_in.frappe.get_doc",
            return_value=membership,
        ):
            with self.assertRaises(Exception):
                checkin.validate_membership()