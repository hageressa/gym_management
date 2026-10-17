import frappe


def execute():
    """Give members created before contacts were synced their standard Contact."""
    for name in frappe.get_all("Gym Member", pluck="name"):
        frappe.get_doc("Gym Member", name).sync_contact()
