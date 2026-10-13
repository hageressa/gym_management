from unittest.mock import patch, Mock

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from gym_management.tasks import (
    update_expired_memberships,
    send_membership_expiry_reminders,
)


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


class TestMembershipExpiryReminders(FrappeTestCase):
    @patch("gym_management.tasks.frappe.sendmail")
    @patch("gym_management.tasks.frappe.get_doc")
    @patch("gym_management.tasks.frappe.get_all")
    @patch("gym_management.tasks.frappe.get_single")
    def test_sends_reminder_and_marks_it_sent(
        self, get_single, get_all, get_doc, sendmail
    ):
        settings = Mock()
        settings.expiry_reminder_days = 7
        get_single.return_value = settings
        get_all.return_value = ["TEST-MEMBERSHIP"]

        membership = Mock()
        membership.member = "TEST-MEMBER"
        membership.name = "TEST-MEMBERSHIP"
        membership.end_date = add_days(today(), 3)

        member = Mock()
        member.email = "member@example.com"
        member.member_name = "Test Member"
        get_doc.side_effect = [membership, member]

        send_membership_expiry_reminders()

        sendmail.assert_called_once()
        membership.db_set.assert_called_once_with(
            "expiry_reminder_sent", 1, update_modified=False
        )
        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["status"], "Active")
        self.assertEqual(filters["expiry_reminder_sent"], 0)

    @patch("gym_management.tasks.frappe.get_all")
    @patch("gym_management.tasks.frappe.get_single")
    def test_skips_when_reminders_disabled(self, get_single, get_all):
        settings = Mock()
        settings.expiry_reminder_days = 0
        get_single.return_value = settings

        send_membership_expiry_reminders()

        get_all.assert_not_called()

    @patch("gym_management.tasks.frappe.sendmail")
    @patch("gym_management.tasks.frappe.get_doc")
    @patch("gym_management.tasks.frappe.get_all")
    @patch("gym_management.tasks.frappe.get_single")
    def test_does_not_mark_sent_without_member_email(
        self, get_single, get_all, get_doc, sendmail
    ):
        settings = Mock()
        settings.expiry_reminder_days = 7
        get_single.return_value = settings
        get_all.return_value = ["TEST-MEMBERSHIP"]

        membership = Mock()
        membership.member = "TEST-MEMBER"
        get_doc.side_effect = [membership, Mock(email=None)]

        send_membership_expiry_reminders()

        sendmail.assert_not_called()
        membership.db_set.assert_not_called()
