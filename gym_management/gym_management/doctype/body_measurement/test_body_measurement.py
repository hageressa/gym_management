import unittest

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today


def make_measurement(**values):
    measurement = {
        "doctype": "Body Measurement",
        "member": "MEM-0001",
        "measurement_date": today(),
        "weight_kg": 80,
        "height_cm": 180,
    }
    measurement.update(values)
    return frappe.get_doc(measurement)


class TestBodyMeasurementRules(unittest.TestCase):
    def test_bmi_is_weight_over_height_squared(self):
        measurement = make_measurement(weight_kg=80, height_cm=180)

        measurement.set_bmi()

        # 80 / 1.8^2 = 24.69 -> 24.7
        self.assertEqual(measurement.bmi, 24.7)

    def test_bmi_is_left_empty_without_a_height(self):
        measurement = make_measurement(height_cm=0)

        measurement.set_bmi()

        self.assertIsNone(measurement.bmi)

    def test_a_future_date_is_refused(self):
        measurement = make_measurement(measurement_date=add_days(today(), 1))

        with self.assertRaises(frappe.ValidationError):
            measurement.validate_date()

    def test_zero_weight_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            make_measurement(weight_kg=0).validate_values()

    def test_a_negative_waist_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            make_measurement(waist_cm=-3).validate_values()

    def test_body_fat_above_100_is_refused(self):
        with self.assertRaises(frappe.ValidationError):
            make_measurement(body_fat_percent=120).validate_values()


class TestBodyMeasurementSaved(FrappeTestCase):
    def test_saving_stores_the_bmi(self):
        member = frappe.get_doc(
            {
                "doctype": "Gym Member",
                "member_name": f"Measured Member {frappe.generate_hash(length=8)}",
            }
        ).insert(ignore_permissions=True)

        measurement = make_measurement(member=member.name, weight_kg=72, height_cm=170)
        measurement.insert(ignore_permissions=True)

        self.assertEqual(
            frappe.db.get_value("Body Measurement", measurement.name, "bmi"), 24.9
        )
