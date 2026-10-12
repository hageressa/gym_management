import frappe
from unittest.mock import patch

from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from gym_management.gym_management.report.membership_expiry_report.membership_expiry_report import execute


class TestMembershipExpiryReport(FrappeTestCase):
    def test_report_returns_days_remaining(self):
        sample_row = frappe._dict(
            name="TEST-MEMBERSHIP",
            end_date=add_days(today(), 5),
        )

        with patch(
            "gym_management.gym_management.report.membership_expiry_report.membership_expiry_report.frappe.db.sql",
            return_value=[sample_row],
        ) as sql_mock:
            columns, rows = execute({"status": "Active", "days": 30})

        self.assertEqual(len(columns), 8)
        self.assertEqual(rows[0].days_remaining, 5)

        values = sql_mock.call_args.args[1]
        self.assertEqual(values["status"], "Active")
        self.assertEqual(values["end_date"], add_days(today(), 30))

    def test_negative_days_are_treated_as_zero(self):
        with patch(
            "gym_management.gym_management.report.membership_expiry_report.membership_expiry_report.frappe.db.sql",
            return_value=[],
        ) as sql_mock:
            columns, rows = execute({"days": -5})

        values = sql_mock.call_args.args[1]
        self.assertEqual(values["end_date"], today())
        self.assertEqual(rows, [])
        self.assertEqual(len(columns), 8)
