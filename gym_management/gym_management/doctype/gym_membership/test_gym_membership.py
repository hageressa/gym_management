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

        with patch.object(membership, "db_set") as mock_db_set:
            membership.on_submit()

        mock_get_doc.assert_not_called()
        mock_db_set.assert_not_called()

    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    def test_calculate_end_date_includes_freeze_days(self, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(
            duration_type="Days",
            duration_value=30,
            max_freeze_days=10,
        )

        membership = self.make_membership()
        membership.append("freeze_history", {
            "freeze_from": "2026-10-20",
            "freeze_to": "2026-10-24",
            "days": 5,
        })

        membership.calculate_end_date()

        expected_date = add_days(getdate("2026-10-13"), 35)
        self.assertEqual(getdate(membership.end_date), getdate(expected_date))

    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.throw",
        side_effect=Exception("Freeze limit exceeded"),
    )
    def test_rejects_freeze_days_over_plan_limit(self, mock_throw, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(max_freeze_days=3)

        membership = self.make_membership()
        membership.append("freeze_history", {
            "freeze_from": "2026-10-20",
            "freeze_to": "2026-10-24",
        })

        with self.assertRaisesRegex(Exception, "Freeze limit exceeded"):
            membership.validate_freeze_history()

    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
    )
    @patch(
        "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.throw",
        side_effect=Exception("periods cannot overlap"),
    )
    def test_rejects_overlapping_freeze_periods(self, mock_throw, mock_get_doc):
        mock_get_doc.return_value = SimpleNamespace(max_freeze_days=30)

        membership = self.make_membership()
        membership.append("freeze_history", {
            "freeze_from": "2026-10-20",
            "freeze_to": "2026-10-24",
        })
        membership.append("freeze_history", {
            "freeze_from": "2026-10-23",
            "freeze_to": "2026-10-25",
        })

        with self.assertRaisesRegex(Exception, "periods cannot overlap"):
            membership.validate_freeze_history()

    def test_renew_rejects_frozen_membership(self):
        from gym_management.api import renew_membership

        with self.assertRaises(Exception):
            renew_membership("GYM-MEM-2026-00001")

    def test_existing_sales_invoice_is_not_recreated(self):
        from unittest.mock import MagicMock, patch
        from gym_management.gym_management.doctype.gym_membership.gym_membership import GymMembership

        doc = GymMembership.__new__(GymMembership)
        doc.sales_invoice = "ACC-SINV-2026-00001"
        doc.status = "Frozen"
        doc.db_set = MagicMock()

        with patch.object(doc, "db_set") as db_set, patch(
            "gym_management.gym_management.doctype.gym_membership.gym_membership.frappe.get_doc"
        ) as get_doc:
            doc.on_submit()
            db_set.assert_not_called()
            get_doc.assert_not_called()
