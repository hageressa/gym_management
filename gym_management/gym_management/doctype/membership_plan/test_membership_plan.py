# Copyright (c) 2026, hager essa and contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestMembershipPlan(FrappeTestCase):
    def test_duplicate_plan_name_is_rejected(self):
        plan_name = f"Test Plan {frappe.generate_hash(length=8)}"

        plan = frappe.get_doc({
            "doctype": "Membership Plan",
            "plan_name": plan_name,
            "duration_type": "Days",
            "duration_value": 30,
            "price": 100,
            "is_active": 1,
        })
        plan.insert(ignore_permissions=True)

        duplicate = frappe.get_doc({
            "doctype": "Membership Plan",
            "plan_name": plan_name,
            "duration_type": "Days",
            "duration_value": 30,
            "price": 100,
            "is_active": 1,
        })

        with self.assertRaises(frappe.ValidationError):
            duplicate.insert(ignore_permissions=True)
