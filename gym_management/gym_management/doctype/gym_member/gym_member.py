import frappe
from frappe.model.document import Document
from frappe.utils import getdate, today


class GymMember(Document):
    def validate(self):
        self.validate_date_of_birth()

    def before_insert(self):
        self.create_customer()

    def validate_date_of_birth(self):
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
            frappe.throw("Date of Birth cannot be in the future.")

    def create_customer(self):
        if self.customer or not self.member_name:
            return

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": self.member_name,
            "customer_type": "Individual",
            "customer_group": "Individual",
            "territory": "Egypt",
        })

        customer.insert(ignore_permissions=True)
        self.customer = customer.name