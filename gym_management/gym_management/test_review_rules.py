import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import add_days, getdate, today

from gym_management import api, utils


def membership(status="Active", freezes=(), start=-30, end=60):
    rows = [SimpleNamespace(freeze_from=add_days(today(), a), freeze_to=add_days(today(), b)) for a, b in freezes]
    return SimpleNamespace(
        status=status,
        start_date=add_days(today(), start),
        end_date=add_days(today(), end),
        get=lambda field: rows if field == "freeze_history" else None,
    )


class TestFreezeIsJudgedOnTheDateAsked(unittest.TestCase):
    def test_frozen_today_can_still_book_after_the_freeze(self):
        frozen = membership(status="Frozen", freezes=[(-2, 5)])

        self.assertIsNotNone(utils.get_membership_block_reason(frozen, today()))
        self.assertIsNone(utils.get_membership_block_reason(frozen, add_days(today(), 10)))

    def test_a_future_freeze_blocks_its_own_dates_only(self):
        active = membership(freezes=[(10, 12)])

        self.assertIsNone(utils.get_membership_block_reason(active, today()))
        self.assertIsNotNone(utils.get_membership_block_reason(active, add_days(today(), 11)))

    def test_a_stored_frozen_status_counts_for_today(self):
        # The daily job may not have run yet, so the status is trusted for today.
        self.assertIsNotNone(utils.get_membership_block_reason(membership(status="Frozen"), getdate(today())))

    @patch("gym_management.utils.frappe.get_all", return_value=[])
    def test_valid_membership_search_includes_frozen_ones(self, get_all):
        utils.get_valid_membership("MEM-0001", today())

        self.assertEqual(get_all.call_args.kwargs["filters"]["status"], ["in", ["Active", "Frozen"]])


class TestStaffOnlyEndpoints(unittest.TestCase):
    @patch("gym_management.api.frappe.only_for", side_effect=frappe.PermissionError)
    def test_dashboard_figures_are_for_managers(self, only_for):
        with self.assertRaises(frappe.PermissionError):
            api.get_dashboard_data()

        only_for.assert_called_once_with(("System Manager", "Gym Manager"))

    @patch("gym_management.api.frappe.get_list", return_value=[])
    @patch("gym_management.api.frappe.get_all")
    def test_member_search_respects_permissions(self, get_all, get_list):
        api.find_members("omar")

        get_list.assert_called_once()
        get_all.assert_not_called()

    @patch("gym_management.api.frappe.has_permission", side_effect=frappe.PermissionError)
    def test_check_in_status_needs_check_in_rights(self, has_permission):
        with self.assertRaises(frappe.PermissionError):
            api.get_check_in_status("MEM-0001")


class TestOneRunningMembership(unittest.TestCase):
    def test_a_frozen_membership_blocks_a_second_one(self):
        from gym_management.gym_management.doctype.gym_membership.gym_membership import GymMembership

        doc = GymMembership({"doctype": "Gym Membership", "member": "MEM-0001", "name": "NEW"})
        module = "gym_management.gym_management.doctype.gym_membership.gym_membership"

        with patch(f"{module}.frappe.db.exists", return_value=True) as exists:
            with self.assertRaises(frappe.ValidationError):
                doc.validate_single_active_membership()

        self.assertEqual(exists.call_args.args[1]["status"], ["in", ["Active", "Frozen"]])
