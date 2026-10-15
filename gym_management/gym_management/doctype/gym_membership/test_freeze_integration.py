from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, getdate, today

from gym_management.api import freeze_membership
from gym_management.gym_management.doctype.gym_membership.gym_membership import GymMembership


class TestFreezeMembershipIntegration(FrappeTestCase):
    def setUp(self):
        # Gym Settings لازم يكون فيه مجموعة Item عشان الـ Membership Plan يعمل Item تلقائي
        frappe.db.set_single_value("Gym Settings", "default_item_group", "All Item Groups")

        self.plan = frappe.get_doc({
            "doctype": "Membership Plan",
            "plan_name": f"Freeze Test {frappe.generate_hash(length=6)}",
            "duration_type": "Days",
            "duration_value": 30,
            "price": 100,
            "max_freeze_days": 10,
            "is_active": 1,
        }).insert(ignore_permissions=True)

        self.member = frappe.get_doc({
            "doctype": "Gym Member",
            "member_name": "Freeze Tester",
        }).insert(ignore_permissions=True)

    def make_active_membership(self):
        membership = frappe.get_doc({
            "doctype": "Gym Membership",
            "member": self.member.name,
            "membership_plan": self.plan.name,
            "start_date": today(),
        }).insert(ignore_permissions=True)

        with patch.object(
            GymMembership,
            "create_sales_invoice",
            return_value=frappe._dict(name="SINV-TEST"),
        ):
            membership.submit()

        return membership

    def test_freeze_extends_end_date_and_adds_freeze_row(self):
        membership = self.make_active_membership()
        original_end = getdate(membership.end_date)

        freeze_membership(
            membership.name,
            add_days(today(), 2),
            add_days(today(), 3),
        )

        saved = frappe.get_doc("Gym Membership", membership.name)
        self.assertEqual(len(saved.freeze_history), 1)
        self.assertEqual(saved.freeze_history[0].days, 2)
        self.assertEqual(getdate(saved.end_date), add_days(original_end, 2))
        self.assertEqual(saved.status, "Active")

    def test_freeze_covering_today_sets_frozen_status(self):
        membership = self.make_active_membership()

        freeze_membership(membership.name, today(), add_days(today(), 1))

        status = frappe.db.get_value("Gym Membership", membership.name, "status")
        self.assertEqual(status, "Frozen")

    def test_freeze_over_plan_limit_is_rejected(self):
        membership = self.make_active_membership()

        with self.assertRaises(frappe.ValidationError):
            freeze_membership(
                membership.name,
                add_days(today(), 1),
                add_days(today(), 20),
            )
