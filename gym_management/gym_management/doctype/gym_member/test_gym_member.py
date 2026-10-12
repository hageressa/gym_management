import frappe
from frappe.tests.utils import FrappeTestCase


class TestGymMember(FrappeTestCase):
    def test_customer_is_required(self):
        member = frappe.get_doc({
            "doctype": "Gym Member",
        })

        with self.assertRaises(frappe.MandatoryError):
            member.insert(ignore_permissions=True)