import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import frappe

from gym_management import door

MODULE = "gym_management.door"


def settings_with_token(token):
    single = MagicMock()
    single.get_password.return_value = token
    return single


class TestDoorToken(unittest.TestCase):
    @patch(f"{MODULE}.frappe.get_single", return_value=settings_with_token("s3cret"))
    def test_the_right_token_passes(self, get_single):
        door.verify_door_token("s3cret")

    @patch(f"{MODULE}.frappe.log_error")
    @patch(f"{MODULE}.frappe.get_single", return_value=settings_with_token("s3cret"))
    def test_a_wrong_token_is_refused_and_logged(self, get_single, log_error):
        with self.assertRaises(frappe.PermissionError):
            door.verify_door_token("guess")

        log_error.assert_called_once()

    @patch(f"{MODULE}.frappe.get_single", return_value=settings_with_token(None))
    def test_an_unconfigured_door_refuses_everything(self, get_single):
        """No token set must fail closed, not open."""
        with self.assertRaises(frappe.PermissionError):
            door.verify_door_token("anything")

    @patch(f"{MODULE}.frappe.log_error")
    @patch(f"{MODULE}.frappe.get_single", return_value=settings_with_token("s3cret"))
    def test_an_empty_token_is_refused(self, get_single, log_error):
        with self.assertRaises(frappe.PermissionError):
            door.verify_door_token("")


class TestDoorAccess(unittest.TestCase):
    def setUp(self):
        patcher = patch(
            f"{MODULE}.frappe.get_single", return_value=settings_with_token("s3cret")
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        name_patcher = patch(f"{MODULE}.get_member_name", return_value="Nour Hassan")
        name_patcher.start()
        self.addCleanup(name_patcher.stop)

    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_latest_membership", return_value=None)
    def test_a_member_without_a_membership_is_refused(self, latest, get_doc):
        result = door.door_access(member="MEM-0001", token="s3cret")

        self.assertFalse(result["open"])
        self.assertIn("no membership", result["reason"])
        get_doc.assert_not_called()

    @patch(f"{MODULE}.get_membership_block_reason", return_value="membership is frozen today")
    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_latest_membership", return_value="GYM-MEM-0001")
    def test_a_blocked_membership_does_not_record_a_check_in(self, latest, get_doc, reason):
        get_doc.return_value = SimpleNamespace(name="GYM-MEM-0001")

        result = door.door_access(member="MEM-0001", token="s3cret")

        self.assertFalse(result["open"])
        self.assertEqual(result["reason"], "membership is frozen today")
        # One call to read the membership, and no second call to create a check-in.
        self.assertEqual(get_doc.call_count, 1)

    @patch(f"{MODULE}.get_membership_block_reason", return_value=None)
    @patch(f"{MODULE}.frappe.get_doc")
    @patch(f"{MODULE}.get_latest_membership", return_value="GYM-MEM-0001")
    def test_a_valid_membership_opens_the_door_and_is_recorded(self, latest, get_doc, reason):
        membership = SimpleNamespace(name="GYM-MEM-0001")
        check_in = MagicMock()
        check_in.name = "CHECKIN-0001"
        get_doc.side_effect = [membership, check_in]

        result = door.door_access(member="MEM-0001", token="s3cret")

        self.assertTrue(result["open"])
        self.assertEqual(result["check_in"], "CHECKIN-0001")
        self.assertEqual(result["member_name"], "Nour Hassan")

        # Guest holds no permission on Gym Check In; the token is the authorisation.
        check_in.insert.assert_called_once_with(ignore_permissions=True)
        self.assertEqual(get_doc.call_args.args[0]["method"], "Card")

    @patch(f"{MODULE}.frappe.log_error")
    @patch(f"{MODULE}.get_latest_membership")
    def test_a_bad_token_never_reaches_the_membership_lookup(self, latest, log_error):
        with self.assertRaises(frappe.PermissionError):
            door.door_access(member="MEM-0001", token="guess")

        latest.assert_not_called()
