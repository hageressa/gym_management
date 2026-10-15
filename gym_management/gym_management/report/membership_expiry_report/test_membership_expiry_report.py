from unittest.mock import patch

import frappe
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

    def test_date_range_and_plan_filters(self):
        filters = {
            "from_date": "2026-11-01",
            "to_date": "2026-11-30",
            "membership_plan": "Test 30 Days",
            "days": 30,
        }

        with patch(
            "gym_management.gym_management.report.membership_expiry_report.membership_expiry_report.frappe.db.sql",
            return_value=[],
        ) as sql_mock:
            _columns, rows = execute(filters)

        query = sql_mock.call_args.args[0]
        values = sql_mock.call_args.args[1]

        self.assertIn("end_date >= %(from_date)s", query)
        self.assertIn("end_date <= %(to_date)s", query)
        self.assertIn("membership_plan = %(membership_plan)s", query)
        self.assertEqual(values["from_date"], "2026-11-01")
        self.assertEqual(values["to_date"], "2026-11-30")
        self.assertEqual(values["membership_plan"], "Test 30 Days")
        self.assertNotIn("end_date", values)
        self.assertEqual(rows, [])


    def test_invalid_date_range_is_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            execute({
                "from_date": "2026-11-30",
                "to_date": "2026-11-01",
            })
