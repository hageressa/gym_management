from unittest.mock import patch, Mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from gym_management.tasks import update_expired_memberships


class TestExpiredMembershipTask(FrappeTestCase):
    @patch("gym_management.tasks.frappe.db.commit")
    @patch("gym_management.tasks.frappe.get_doc")
    @patch("gym_management.tasks.frappe.get_all")
    def test_updates_only_expired_active_memberships(
        self, get_all, get_doc, db_commit
    ):
        membership = Mock()
        membership.end_date = add_days(today(), -1)
        get_all.return_value = ["TEST-MEMBERSHIP"]
        get_doc.return_value = membership

        update_expired_memberships()

        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["docstatus"], 1)
        self.assertEqual(filters["status"], "Active")
        self.assertEqual(filters["end_date"], ["<", today()])
        membership.db_set.assert_called_once_with(
            "status", "Expired", update_modified=False
        )
        db_commit.assert_called_once()

    @patch("gym_management.tasks.frappe.db.commit")
    @patch("gym_management.tasks.frappe.get_doc")
    @patch("gym_management.tasks.frappe.get_all")
    def test_does_not_update_when_no_memberships_expired(
        self, get_all, get_doc, db_commit
    ):
        get_all.return_value = []

        update_expired_memberships()

        get_doc.assert_not_called()
        db_commit.assert_called_once()
