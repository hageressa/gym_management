import frappe
from frappe.tests.utils import FrappeTestCase


def contact_for(member):
    name = frappe.db.get_value(
        "Dynamic Link",
        {"parenttype": "Contact", "link_doctype": "Gym Member", "link_name": member},
        "parent",
    )
    return frappe.get_doc("Contact", name) if name else None


class TestMemberContact(FrappeTestCase):
    def make_member(self, **values):
        suffix = frappe.generate_hash(length=8)
        member = {
            "doctype": "Gym Member",
            "member_name": f"Contact Member {suffix}",
            "email": f"contact.{suffix}@example.com",
            "phone": "+20 100 000 0000",
        }
        member.update(values)
        return frappe.get_doc(member).insert(ignore_permissions=True)

    def test_saving_a_member_creates_a_linked_contact(self):
        member = self.make_member()

        contact = contact_for(member.name)

        self.assertIsNotNone(contact)
        self.assertEqual(contact.email_id, member.email)
        links = {(row.link_doctype, row.link_name) for row in contact.links}
        self.assertIn(("Gym Member", member.name), links)
        self.assertIn(("Customer", member.customer), links)

    def test_a_changed_email_becomes_the_primary_on_the_same_contact(self):
        member = self.make_member()
        first = contact_for(member.name).name

        member.email = f"new.{frappe.generate_hash(length=8)}@example.com"
        member.save(ignore_permissions=True)

        contact = contact_for(member.name)
        self.assertEqual(contact.name, first)
        self.assertEqual(contact.email_id, member.email)

    def test_a_member_without_email_or_phone_gets_no_contact(self):
        member = self.make_member(email=None, phone=None)

        self.assertIsNone(contact_for(member.name))
