from datetime import date
from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from gym_management import api
from gym_management.api import freeze_membership, get_available_sessions


class TestGymAPI(FrappeTestCase):
    def setUp(self):
        # Pin "today" so the freeze tests do not drift with the real date.
        today_patcher = patch("gym_management.api.today", return_value="2026-10-14")
        today_patcher.start()
        self.addCleanup(today_patcher.stop)

    def test_available_sessions_rejects_reversed_dates(self):
        with self.assertRaises(frappe.ValidationError):
            get_available_sessions("2026-10-14", "2026-10-13")

    def test_available_sessions_returns_only_sessions_with_spots(self):
        sessions = [
            frappe._dict(name="SESSION-1", capacity=10, booked_count=3),
            frappe._dict(name="SESSION-2", capacity=5, booked_count=5),
        ]

        with patch("gym_management.api.frappe.get_all", return_value=sessions):
            result = get_available_sessions("2026-10-13", "2026-10-13")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].name, "SESSION-1")
        self.assertEqual(result[0].available_spots, 7)

    def test_freeze_membership_rejects_when_plan_limit_is_zero(self):
        membership = frappe._dict(
            docstatus=1,
            status="Active",
            membership_plan="Test Plan",
            freeze_history=[],
        )
        membership.check_permission = MagicMock()
        membership.append = MagicMock()
        plan = frappe._dict(max_freeze_days=0)

        with patch(
            "gym_management.api.frappe.get_doc",
            side_effect=[membership, plan],
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                r"Total freeze days \(2\) exceed the plan limit \(0\)",
            ):
                freeze_membership(
                    "TEST-MEMBERSHIP",
                    "2026-10-16",
                    "2026-10-17",
                )

        membership.append.assert_not_called()

    def test_freeze_membership_rejects_expired_membership(self):
        membership = frappe._dict(
            docstatus=1,
            status="Expired",
            membership_plan="Test Plan",
            freeze_history=[],
        )
        membership.check_permission = MagicMock()

        with patch(
            "gym_management.api.frappe.get_doc",
            return_value=membership,
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "Only active or frozen memberships can be frozen.",
            ):
                freeze_membership(
                    "TEST-MEMBERSHIP",
                    "2026-10-16",
                    "2026-10-17",
                )

    def test_freeze_membership_rejects_overlapping_periods(self):
        membership = frappe._dict(
            docstatus=1,
            status="Active",
            membership_plan="Test Plan",
            freeze_history=[
                frappe._dict(
                    freeze_from="2026-10-16",
                    freeze_to="2026-10-18",
                    days=3,
                )
            ],
        )
        membership.check_permission = MagicMock()
        plan = frappe._dict(max_freeze_days=30)

        with patch(
            "gym_management.api.frappe.get_doc",
            side_effect=[membership, plan],
        ):
            with self.assertRaisesRegex(
                frappe.ValidationError,
                "Membership freeze periods cannot overlap.",
            ):
                freeze_membership(
                    "TEST-MEMBERSHIP",
                    "2026-10-17",
                    "2026-10-19",
                )

    def test_freeze_membership_successfully_extends_end_date(self):
        membership = frappe._dict(
            name="TEST-MEMBERSHIP",
            docstatus=1,
            status="Active",
            membership_plan="Test Plan",
            end_date="2026-12-31",
            freeze_history=[],
        )
        membership.check_permission = MagicMock()
        membership.db_set = MagicMock()

        def append_freeze_row(field, values):
            row = frappe._dict(values)
            row.db_insert = MagicMock()
            membership.freeze_history.append(row)
            return row

        membership.append = MagicMock(side_effect=append_freeze_row)
        plan = frappe._dict(max_freeze_days=30)

        with patch(
            "gym_management.api.frappe.get_doc",
            side_effect=[membership, plan],
        ):
            result = freeze_membership(
                "TEST-MEMBERSHIP",
                "2026-10-16",
                "2026-10-17",
                reason="Test",
            )

        self.assertEqual(result["membership"], "TEST-MEMBERSHIP")
        self.assertEqual(result["end_date"], date(2027, 1, 2))
        self.assertEqual(result["status"], "Active")
        self.assertEqual(membership.freeze_history[0].days, 2)
        membership.db_set.assert_any_call("end_date", date(2027, 1, 2))


class TestDashboardData(FrappeTestCase):
    def test_fill_rate_and_names_are_added_to_sessions(self):
        sessions = [
            frappe._dict(
                name="SESS-1",
                gym_class="CLASS-1",
                trainer=None,
                capacity=10,
                booked_count=5,
            )
        ]

        with patch(
            "gym_management.api.frappe.get_all",
            side_effect=[sessions, [["CLASS-1", "Yoga Basics"]]],
        ):
            result = api.get_sessions_on("2026-10-15")

        self.assertEqual(result[0].fill_rate, 50)
        self.assertEqual(result[0].class_name, "Yoga Basics")
        self.assertIsNone(result[0].trainer_name)

    def test_session_without_capacity_has_zero_fill_rate(self):
        sessions = [
            frappe._dict(
                name="SESS-1",
                gym_class=None,
                trainer=None,
                capacity=0,
                booked_count=0,
            )
        ]

        with patch("gym_management.api.frappe.get_all", return_value=sessions):
            result = api.get_sessions_on("2026-10-15")

        self.assertEqual(result[0].fill_rate, 0)

    def test_get_titles_skips_the_query_when_there_is_nothing_to_look_up(self):
        with patch("gym_management.api.frappe.get_all") as get_all:
            self.assertEqual(api.get_titles("Gym Class", set(), "class_name"), {})

        get_all.assert_not_called()

    def test_active_members_counts_each_member_once(self):
        with patch(
            "gym_management.api.frappe.get_all",
            return_value=["MEM-1", "MEM-2", "MEM-1"],
        ):
            self.assertEqual(api.count_active_members(), 2)
