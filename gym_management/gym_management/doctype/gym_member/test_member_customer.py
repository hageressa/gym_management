import unittest
from unittest.mock import patch

import frappe

MODULE = "gym_management.gym_management.doctype.gym_member.gym_member"


class TestOneMemberPerCustomer(unittest.TestCase):
    def make_member(self):
        member = frappe.new_doc("Gym Member")
        member.update({"member_name": "Omar Fathy", "customer": "Omar Fathy", "name": "MEM-0009"})
        return member

    def test_a_customer_already_linked_elsewhere_is_refused(self):
        member = self.make_member()

        with patch(f"{MODULE}.frappe.db.get_value", return_value="MEM-0004"):
            with self.assertRaises(frappe.ValidationError):
                member.validate_unique_customer()

    def test_a_customer_of_its_own_passes(self):
        member = self.make_member()

        with patch(f"{MODULE}.frappe.db.get_value", return_value=None) as get_value:
            member.validate_unique_customer()

        self.assertEqual(get_value.call_args.args[1]["name"], ["!=", "MEM-0009"])
