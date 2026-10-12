import unittest
from types import SimpleNamespace
from unittest.mock import patch

import frappe
from frappe.utils import add_days, add_months, getdate

from gym_management.gym_management.doctype.gym_membership.gym_membership import (
    GymMembership,
)


class TestGymMembership(unittest.TestCase):
    def make_membership(self, start_date="2026-10-13"):
        membership = GymMembership({
            "doctype": "Gym Membership",
            "member": "Test Member",
            "membership_plan": "Test Plan",
            "start_date": start_date,
        })
        return membership

    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    def test_calculate_end_date_in_days(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(
            duration_type="Days",
            duration_value=30,
        )

        membership = self.make_membership()
        membership.calculate_end_date()

        expected_date = add_days(getdate("2026-10-13"), 30)
        self.assertEqual(
            getdate(membership.end_date),
            getdate(expected_date),
        )

    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    def test_calculate_end_date_in_months(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(
            duration_type="Months",
            duration_value=3,
        )

        membership = self.make_membership()
        membership.calculate_end_date()

        expected_date = add_months(getdate("2026-10-13"), 3)
        self.assertEqual(
            getdate(membership.end_date),
            getdate(expected_date),
        )

    def test_missing_start_date_does_not_calculate(self):
        membership = self.make_membership(start_date=None)
        membership.end_date = None

        membership.calculate_end_date()

        self.assertIsNone(membership.end_date)
        
    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    def test_on_submit_skips_existing_invoice(self, mock_get_doc):
        membership = self.make_membership()
        membership.sales_invoice = "ACC-SINV-2026-00001"

        membership.on_submit()

        mock_get_doc.assert_not_called()