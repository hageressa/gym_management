import frappe
from frappe import _
from frappe.contacts.address_and_contact import load_address_and_contact
from frappe.model.document import Document
from frappe.utils import getdate, today

from gym_management.utils import get_default_customer_group, get_default_territory


class GymMember(Document):
    def onload(self):
        """Addresses and contacts linked to this member, for the form's HTML fields."""
        load_address_and_contact(self)

    def validate(self):
        self.validate_date_of_birth()
        self.validate_unique_customer()

    def before_insert(self):
        self.create_customer()

    def on_update(self):
        self.sync_contact()

    def validate_date_of_birth(self):
        if self.date_of_birth and getdate(self.date_of_birth) > getdate(today()):
            frappe.throw(_("Date of Birth cannot be in the future."))

    def validate_unique_customer(self):
        """One Gym Member per Customer, the brief's 1:1 rule."""
        if not self.customer:
            return
        other = frappe.db.get_value(
            "Gym Member", {"customer": self.customer, "name": ["!=", self.name]}, "name"
        )
        if other:
            frappe.throw(
                _("Customer {0} is already linked to Gym Member {1}.").format(self.customer, other)
            )

    def create_customer(self):
        if self.customer or not self.member_name:
            return

        customer = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": self.member_name,
            "customer_type": "Individual",
            "customer_group": get_default_customer_group(),
            "territory": get_default_territory(),
        })

        customer.insert(ignore_permissions=True)
        self.customer = customer.name

    def sync_contact(self):
        """Keep one standard Contact for the member, linked to the member and its Customer.

        The contact is a built-in Contact with Dynamic Links rather than copied
        fields, so the same person shows up on the Customer and on invoices.
        """
        if not (self.email or self.phone):
            return

        name = frappe.db.get_value(
            "Dynamic Link",
            {"parenttype": "Contact", "link_doctype": "Gym Member", "link_name": self.name},
            "parent",
        )
        contact = frappe.get_doc("Contact", name) if name else frappe.new_doc("Contact")
        contact.first_name = self.member_name

        if self.email and not any(row.email_id == self.email for row in contact.email_ids):
            for row in contact.email_ids:
                row.is_primary = 0
            contact.append("email_ids", {"email_id": self.email, "is_primary": 1})

        if self.phone and not any(row.phone == self.phone for row in contact.phone_nos):
            for row in contact.phone_nos:
                row.is_primary_mobile_no = 0
            contact.append("phone_nos", {"phone": self.phone, "is_primary_mobile_no": 1})

        for doctype, link_name in (("Gym Member", self.name), ("Customer", self.customer)):
            linked = any(
                row.link_doctype == doctype and row.link_name == link_name for row in contact.links
            )
            if link_name and not linked:
                contact.append("links", {"link_doctype": doctype, "link_name": link_name})

        contact.save(ignore_permissions=True)
