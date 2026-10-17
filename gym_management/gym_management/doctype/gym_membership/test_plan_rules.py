import unittest
from unittest.mock import patch

import frappe

MODULE = "gym_management.gym_management.doctype.gym_membership.gym_membership"


def make_membership(**values):
    membership = {
        "doctype": "Gym Membership",
        "member": "MEM-0001",
        "membership_plan": "Monthly 8",
        "start_date": "2030-01-01",
    }
    membership.update(values)
    return frappe.get_doc(membership)


class TestPlanRules(unittest.TestCase):
    def test_an_inactive_plan_cannot_be_sold(self):
        membership = make_membership()

        with patch(f"{MODULE}.frappe.db.get_value", return_value=0):
            with self.assertRaises(frappe.ValidationError):
                membership.validate_plan_is_active()

    def test_a_submitted_membership_keeps_a_plan_switched_off_later(self):
        membership = make_membership()
        membership.docstatus = 1

        with patch(f"{MODULE}.frappe.db.get_value", return_value=0) as get_value:
            membership.validate_plan_is_active()

        get_value.assert_not_called()

    def test_a_monthly_plan_with_an_allowance_starts_with_its_classes(self):
        membership = make_membership()
        plan = frappe._dict(duration_type="Months", classes_included=8, duration_value=1)

        with patch(f"{MODULE}.frappe.get_doc", return_value=plan):
            membership.set_class_pack_balance()

        self.assertEqual(membership.classes_remaining, 8)

    def test_an_unlimited_plan_tracks_no_classes(self):
        membership = make_membership()
        plan = frappe._dict(duration_type="Months", classes_included=0, duration_value=1)

        with patch(f"{MODULE}.frappe.get_doc", return_value=plan):
            membership.set_class_pack_balance()

        self.assertFalse(membership.classes_remaining)


class TestDuplicateMembership(unittest.TestCase):
    def test_a_copy_does_not_inherit_the_invoice_or_status(self):
        """Otherwise the invoice guard in on_submit would skip billing the copy."""
        original = make_membership(sales_invoice="ACC-SINV-0001", status="Active", classes_remaining=3)

        copy = frappe.copy_doc(original)

        self.assertFalse(copy.sales_invoice)
        self.assertFalse(copy.classes_remaining)
        self.assertEqual(copy.status, "Draft")
