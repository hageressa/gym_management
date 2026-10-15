from unittest.mock import Mock, patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from gym_management.tasks import (
    send_membership_expiry_reminders,
    sync_freeze_statuses,
    update_expired_memberships,
)


class TestExpiredMembershipTask(FrappeTestCase):
    @patch("gym_management.tasks.frappe.db.commit")
    @patch("gym_management.tasks.frappe.get_doc")
    @patch("gym_management.tasks.frappe.get_all")
    def test_updates_only_expired_active_memberships(
        self, get_all, get_doc, db_commit
    ):
        membership = Mock()
        membership.end_date = "2026-10-13"
        get_all.return_value = ["TEST-MEMBERSHIP"]
        get_doc.return_value = membership

        with patch("gym_management.tasks.today", return_value="2026-10-14"):
            update_expired_memberships()

        filters = get_all.call_args.kwargs["filters"]
        self.assertEqual(filters["docstatus"], 1)
        self.assertEqual(filters["status"], "Active")
        self.assertEqual(filters["end_date"], ["<", "2026-10-14"])
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

        with patch("gym_management.tasks.today", return_value="2026-10-14"):
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
        membership.end_date = "2026-10-17"

        member = Mock()
        member.email = "member@example.com"
        member.member_name = "Test Member"
        get_doc.side_effect = [membership, member]

        with patch("gym_management.tasks.today", return_value="2026-10-14"), patch(
            "gym_management.tasks.add_days", return_value="2026-10-21"
        ):
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

        with patch("gym_management.tasks.today", return_value="2026-10-14"), patch(
            "gym_management.tasks.add_days", return_value="2026-10-21"
        ):
            send_membership_expiry_reminders()

        sendmail.assert_not_called()
        membership.db_set.assert_not_called()


class TestSyncFreezeStatuses(FrappeTestCase):
    def _run_sync(self, status, freeze_from, freeze_to, end_date=None):
        row = Mock()
        row.freeze_from = freeze_from
        row.freeze_to = freeze_to
        membership = Mock()
        membership.status = status
        membership.end_date = end_date or add_days(today(), 10)
        membership.get.return_value = [row]

        with patch(
            "gym_management.tasks.frappe.get_all", return_value=["TEST-MEMBERSHIP"]
        ), patch("gym_management.tasks.frappe.get_doc", return_value=membership):
            sync_freeze_statuses()

        return membership

    def test_freezes_active_membership_inside_freeze_period(self):
        membership = self._run_sync(
            "Active", add_days(today(), -1), add_days(today(), 5)
        )

        membership.db_set.assert_called_once_with(
            "status", "Frozen", update_modified=False
        )

    def test_reactivates_membership_after_freeze_ended(self):
        membership = self._run_sync(
            "Frozen", add_days(today(), -10), add_days(today(), -1)
        )

        membership.db_set.assert_called_once_with(
            "status", "Active", update_modified=False
        )

    def test_expired_membership_during_freeze_becomes_expired(self):
        membership = self._run_sync(
            "Frozen",
            add_days(today(), -10),
            add_days(today(), 5),
            end_date=add_days(today(), -1),
        )

        membership.db_set.assert_called_once_with(
            "status", "Expired", update_modified=False
        )

    def test_does_not_touch_status_that_is_already_correct(self):
        membership = self._run_sync(
            "Active", add_days(today(), -10), add_days(today(), -1)
        )

        membership.db_set.assert_not_called()
