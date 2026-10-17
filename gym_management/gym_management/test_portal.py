import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from gym_management import portal

MODULE = "gym_management.portal"


class TestPortalMember(unittest.TestCase):
    def test_a_guest_has_no_member(self):
        self.assertIsNone(portal.get_portal_member("Guest"))

    @patch(f"{MODULE}.frappe.get_all", return_value=["MEM-0004"])
    @patch(f"{MODULE}.frappe.db.get_value", return_value="omar@example.com")
    def test_the_member_is_found_by_the_login_email(self, get_value, get_all):
        self.assertEqual(portal.get_portal_member("omar@example.com"), "MEM-0004")
        self.assertEqual(get_all.call_args.kwargs["filters"], {"email": "omar@example.com"})

    @patch(f"{MODULE}.frappe.get_all", return_value=["MEM-0001", "MEM-0002"])
    @patch(f"{MODULE}.frappe.db.get_value", return_value="shared@example.com")
    def test_two_members_sharing_an_email_are_refused(self, get_value, get_all):
        with self.assertRaises(frappe.ValidationError):
            portal.get_portal_member("shared@example.com")

    @patch(f"{MODULE}.get_portal_member", return_value=None)
    def test_an_unlinked_account_cannot_act(self, member):
        with self.assertRaises(frappe.PermissionError):
            portal.book_session("SESS-0001")


class TestPortalBooking(unittest.TestCase):
    @patch(f"{MODULE}.create_booking", return_value={"status": "Booked"})
    @patch(f"{MODULE}.get_portal_member", return_value="MEM-0004")
    def test_booking_uses_the_signed_in_member(self, member, create_booking):
        portal.book_session("SESS-0001")

        create_booking.assert_called_once_with("SESS-0001", "MEM-0004", ignore_permissions=True)


class TestPortalCancel(unittest.TestCase):
    def booking(self, member, status):
        doc = MagicMock()
        doc.name, doc.member, doc.status = "BOOK-0001", member, status
        return doc

    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_portal_member", return_value="MEM-0004")
    def test_a_member_cancels_their_own_booking(self, member, get_doc):
        doc = self.booking("MEM-0004", "Booked")
        get_doc.return_value = doc

        result = portal.cancel_booking("BOOK-0001")

        self.assertEqual(result["status"], "Cancelled")
        doc.save.assert_called_once_with(ignore_permissions=True)

    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_portal_member", return_value="MEM-0004")
    def test_another_members_booking_cannot_be_cancelled(self, member, get_doc):
        doc = self.booking("MEM-0003", "Booked")
        get_doc.return_value = doc

        with self.assertRaises(frappe.PermissionError):
            portal.cancel_booking("BOOK-0001")

        doc.save.assert_not_called()

    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_portal_member", return_value="MEM-0004")
    def test_an_attended_booking_cannot_be_cancelled(self, member, get_doc):
        doc = self.booking("MEM-0004", "Attended")
        get_doc.return_value = doc

        with self.assertRaises(frappe.ValidationError):
            portal.cancel_booking("BOOK-0001")

        doc.save.assert_not_called()


class TestDescribeSessions(unittest.TestCase):
    @patch(f"{MODULE}.get_titles")
    def test_rows_get_names_spots_and_the_members_booking(self, get_titles):
        get_titles.side_effect = [{"CLASS-0001": "Yoga"}, {"TRN-0001": "Ahmed Hassan"}]
        row = frappe._dict(
            name="SESS-0001", gym_class="CLASS-0001", trainer="TRN-0001",
            session_date="2030-01-07", start_time="10:00:00", end_time="11:00:00",
            capacity=10, booked_count=12,
        )
        mine = SimpleNamespace(name="BOOK-0001", status="Waitlisted", waitlist_position=2)

        portal.describe_sessions([row], {"SESS-0001": mine})

        self.assertEqual(row.class_name, "Yoga")
        self.assertEqual(row.trainer_name, "Ahmed Hassan")
        self.assertEqual(row.time_label, "10:00 - 11:00")
        self.assertEqual(row.spots_left, 0)
        self.assertIs(row.my_booking, mine)
