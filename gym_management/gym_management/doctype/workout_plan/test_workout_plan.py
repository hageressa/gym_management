import unittest

import frappe


def make_plan(**values):
    plan = {
        "doctype": "Workout Plan",
        "plan_title": "Strength Base",
        "member": "MEM-0001",
        "start_date": "2026-10-01",
    }
    plan.update(values)
    return frappe.get_doc(plan)


class TestWorkoutPlan(unittest.TestCase):
    def test_end_date_before_start_is_refused(self):
        plan = make_plan(end_date="2026-09-30")

        with self.assertRaises(frappe.ValidationError):
            plan.validate_dates()

    def test_open_ended_plan_is_allowed(self):
        make_plan(end_date=None).validate_dates()

    def test_negative_reps_are_refused(self):
        plan = make_plan()
        plan.append("exercises", {"day": "Monday", "exercise": "Squat", "sets": 3, "reps": -5})

        with self.assertRaises(frappe.ValidationError):
            plan.validate_exercises()

    def test_ordinary_exercises_pass(self):
        plan = make_plan()
        plan.append(
            "exercises",
            {"day": "Monday", "exercise": "Squat", "sets": 3, "reps": 8, "weight_kg": 60},
        )

        plan.validate_exercises()
