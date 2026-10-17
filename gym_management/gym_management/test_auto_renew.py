import unittest
from unittest.mock import patch

import frappe

from gym_management import tasks

MODULE = "gym_management.tasks"


def rows(*pairs):
    return [frappe._dict(name=name, member=member) for name, member in pairs]


class TestAutoRenew(unittest.TestCase):
    @patch(f"{MODULE}.frappe.db.commit")
    @patch("gym_management.api.renew_membership")
    @patch(f"{MODULE}.get_latest_membership", return_value="GYM-MEM-2")
    @patch(f"{MODULE}.frappe.get_all")
    def test_only_the_latest_membership_is_renewed(self, get_all, latest, renew, commit):
        get_all.return_value = rows(("GYM-MEM-1", "MEM-1"), ("GYM-MEM-2", "MEM-1"))

        tasks.renew_auto_renew_memberships()

        renew.assert_called_once_with("GYM-MEM-2")
        self.assertEqual(get_all.call_args.kwargs["filters"]["auto_renew"], 1)

    @patch(f"{MODULE}.frappe.log_error")
    @patch(f"{MODULE}.frappe.db.rollback")
    @patch(f"{MODULE}.frappe.db.commit")
    @patch("gym_management.api.renew_membership")
    @patch(f"{MODULE}.get_latest_membership", side_effect=lambda member: {"MEM-1": "A", "MEM-2": "B"}[member])
    @patch(f"{MODULE}.frappe.get_all")
    def test_one_failure_does_not_stop_the_others(
        self, get_all, latest, renew, commit, rollback, log_error
    ):
        get_all.return_value = rows(("A", "MEM-1"), ("B", "MEM-2"))
        renew.side_effect = [Exception("inactive plan"), {"name": "NEW"}]

        tasks.renew_auto_renew_memberships()

        self.assertEqual(renew.call_count, 2)
        rollback.assert_called_once()
        log_error.assert_called_once()
        commit.assert_called_once()
