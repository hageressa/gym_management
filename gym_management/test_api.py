import unittest
from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from gym_management.api import get_available_sessions


class TestGymAPI(FrappeTestCase):
    def test_available_sessions_rejects_reversed_dates(self):
        with self.assertRaises(frappe.ValidationError):
            get_available_sessions("2026-10-14", "2026-10-13")

    def test_available_sessions_returns_only_sessions_with_spots(self):
        sessions = [
            frappe._dict(name="SESSION-1", capacity=10),
            frappe._dict(name="SESSION-2", capacity=5),
        ]

        with patch("gym_management.api.frappe.get_all", return_value=sessions), \
             patch("gym_management.api.frappe.db.count", side_effect=[3, 5]):
            result = get_available_sessions("2026-10-13", "2026-10-13")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "SESSION-1")
        self.assertEqual(result[0].available_spots, 7)
