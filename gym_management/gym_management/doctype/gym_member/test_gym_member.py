import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


class TestGymMember(FrappeTestCase):
    def test_customer_is_created_automatically(self):
        member = frappe.get_doc({
            "doctype": "Gym Member",
            "member_name": f"Test Member {frappe.generate_hash(length=8)}",
        })

        member.insert(ignore_permissions=True)

        self.assertTrue(member.customer)
        self.assertTrue(
            frappe.db.exists("Customer", member.customer)
        )
        self.assertEqual(
            frappe.db.get_value("Customer", member.customer, "customer_name"),
            member.member_name,
        )

    def test_future_date_of_birth_is_rejected(self):
        member = frappe.get_doc({
            "doctype": "Gym Member",
            "member_name": f"Test Member {frappe.generate_hash(length=8)}",
            "date_of_birth": add_days(today(), 1),
        })

        with self.assertRaises(frappe.ValidationError):
            member.insert(ignore_permissions=True)
