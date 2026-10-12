# Copyright (c) 2026, hager essa and contributors
# For license information, please see license.txt



import frappe
from frappe.model.document import Document


class MembershipPlan(Document):
    def validate(self):
        if not self.plan_name:
            return

        filters = {"plan_name": self.plan_name}

        if not self.is_new():
            filters["name"] = ["!=", self.name]

        existing = frappe.db.get_value(
            "Membership Plan", filters, "name"
        )

        if existing:
            frappe.throw("Plan Name must be unique.")
