import unittest
from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch

from gym_management.gym_management.doctype.gym_check_in.gym_check_in import (
    GymCheckIn,
)


class TestMembershipEdgeCases(unittest.TestCase):
    def make_checkin(self):
        return GymCheckIn({
            "doctype": "Gym Check In",
            "member": "TEST-MEMBER",
            "membership": "TEST-MEMBERSHIP",
        })

    def make_membership(self, **overrides):
        today = date.today()
        values = {
            "name": "TEST-MEMBERSHIP",
            "member": "TEST-MEMBER",
            "docstatus": 1,
            "status": "Active",
            "start_date": today - timedelta(days=10),
            "end_date": today + timedelta(days=10),
            "get": lambda field: [],
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def assert_membership_rejected(self, membership):
        checkin = self.make_checkin()
        with patch(
            "gym_management.gym_management.doctype.gym_check_in.gym_check_in.frappe.get_doc",
            return_value=membership,
        ):
            with self.assertRaises(Exception):
                checkin.validate_membership()

    def test_rejects_membership_frozen_today(self):
        today = date.today()
        membership = self.make_membership(
            get=lambda field: [
                SimpleNamespace(
                    freeze_from=today - timedelta(days=1),
                    freeze_to=today + timedelta(days=1),
                )
            ] if field == "freeze_history" else []
        )
        self.assert_membership_rejected(membership)

    def test_rejects_expired_membership(self):
        today = date.today()
        membership = self.make_membership(
            end_date=today - timedelta(days=1)
        )
        self.assert_membership_rejected(membership)

    def test_rejects_membership_with_frozen_status(self):
        membership = self.make_membership(status="Frozen")
        self.assert_membership_rejected(membership)


if __name__ == "__main__":
    unittest.main()
