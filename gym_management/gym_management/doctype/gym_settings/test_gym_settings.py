# Copyright (c) 2026, hager essa and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase


class TestGymSettings(FrappeTestCase):
    def test_settings_singleton_loads(self):
        settings = frappe.get_single("Gym Settings")
        meta = frappe.get_meta("Gym Settings")

        self.assertEqual(settings.doctype, "Gym Settings")
        self.assertTrue(meta.issingle)
