import frappe


def before_tests():
    """Load System Settings into frappe.local before any test runs.

    Some unit tests patch frappe.get_doc. If a patched call is the first to need
    System Settings (for the time zone), Frappe caches the mock in frappe.local
    and every later date call fails. Loading the real settings first prevents it.
    """
    frappe.get_system_settings("time_zone")
